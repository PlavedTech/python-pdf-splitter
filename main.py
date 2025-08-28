#!/usr/bin/env python3
"""
PDF Splitter Microservice
Splits PDF files into individual pages for n8n workflow processing
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pypdf import PdfReader, PdfWriter
import base64
import io
import logging
import os
from typing import List, Optional
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security configuration
# Default token for public access - change in production!
DEFAULT_TOKEN = "pdf-splitter-public-2025"
API_TOKEN = os.getenv("API_TOKEN", DEFAULT_TOKEN)
security = HTTPBearer(auto_error=False)

# Log the API token on startup
logger.info(f"API Token configured: {'[CUSTOM]' if API_TOKEN != DEFAULT_TOKEN else '[DEFAULT: pdf-splitter-public-2025]'}")

# Response models for better documentation
class PageData(BaseModel):
    page_number: int = Field(description="Page number (1-indexed)")
    filename: str = Field(description="Suggested filename for this page")
    data: str = Field(description="Base64 encoded PDF data")
    size: int = Field(description="Size of the base64 data in bytes")

class SplitPDFResponse(BaseModel):
    status: str = Field(description="Operation status")
    original_filename: str = Field(description="Name of the uploaded file")
    total_pages: int = Field(description="Total number of pages in the PDF")
    pages_split: bool = Field(description="Whether the PDF was split (false for single-page PDFs)")
    files: List[PageData] = Field(description="Array of split PDF pages")

class HealthResponse(BaseModel):
    status: str = Field(description="Service health status")
    service: str = Field(description="Service name")

class ErrorResponse(BaseModel):
    detail: str = Field(description="Error message")

class AuthenticationError(BaseModel):
    detail: str = Field(default="Invalid or missing authentication token")
    authenticate: str = Field(default="Bearer")

# Create FastAPI app with enhanced documentation
app = FastAPI(
    title="PDF Splitter Service",
    description="""
## PDF Splitter Microservice

A high-performance microservice for splitting PDF files into individual pages.

### Features
- Split multi-page PDFs into individual page files
- Base64 encoding for easy integration
- Health monitoring endpoint
- Automatic OpenAPI documentation
- Bearer token authentication for security

### Use Cases
- Document processing pipelines
- n8n workflow automation
- Batch PDF processing
- Page-level PDF manipulation
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "API Support",
        "email": "servicios@plaved.tech"
    },
    license_info={
        "name": "MIT",
    }
)

# Add CORS middleware for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this based on your needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication dependency
async def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None, description="Alternative API key header")
) -> bool:
    """
    Verify API token from either Authorization Bearer header or X-API-Key header.
    """
    # Check Bearer token
    if credentials and credentials.credentials == API_TOKEN:
        return True
    
    # Check X-API-Key header
    if x_api_key and x_api_key == API_TOKEN:
        return True
    
    # No valid authentication
    raise HTTPException(
        status_code=401,
        detail="Invalid or missing authentication token",
        headers={"WWW-Authenticate": "Bearer"}
    )

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Check service health status
    
    Returns the current health status of the PDF Splitter service.
    This endpoint is useful for monitoring and load balancer health checks.
    """
    return {"status": "healthy", "service": "pdf-splitter"}

# Constants for file validation
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB limit
MAX_PAGES = 500  # Maximum pages to prevent abuse

@app.post(
    "/split-pdf",
    response_model=SplitPDFResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file format or size"},
        401: {"model": AuthenticationError, "description": "Authentication required"},
        413: {"model": ErrorResponse, "description": "File too large"},
        422: {"model": ErrorResponse, "description": "Too many pages in PDF"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    tags=["PDF Operations"],
    summary="Split PDF into individual pages",
    dependencies=[Depends(verify_token)]
)
async def split_pdf(
    file: UploadFile = File(
        ...,
        description="PDF file to split (max 50MB)"
    )
) -> SplitPDFResponse:
    """
    Split a PDF file into individual pages.
    
    This endpoint accepts a PDF file upload and returns each page as a separate
    base64-encoded PDF file. Perfect for document processing workflows.
    
    **Limitations:**
    - Maximum file size: 50 MB
    - Maximum pages: 500
    - Only PDF files are accepted
    
    **Returns:**
    - Array of base64-encoded PDF pages
    - Each page maintains original formatting
    - Metadata about the split operation
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No filename provided"
        )
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Expected PDF, got {file.filename.split('.')[-1] if '.' in file.filename else 'unknown'}"
        )
    
    # Check file size
    file_content = await file.read()
    file_size = len(file_content)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Size: {file_size / 1024 / 1024:.1f}MB, Max: {MAX_FILE_SIZE / 1024 / 1024}MB"
        )
    
    if file_size == 0:
        raise HTTPException(
            status_code=400,
            detail="Empty file uploaded"
        )
    
    try:
        # Read the PDF from already loaded content
        pdf_reader = PdfReader(io.BytesIO(file_content))
        
        total_pages = len(pdf_reader.pages)
        logger.info(f"Processing PDF '{file.filename}' with {total_pages} pages")
        
        # Check page limit
        if total_pages > MAX_PAGES:
            raise HTTPException(
                status_code=422,
                detail=f"PDF has too many pages. Pages: {total_pages}, Max: {MAX_PAGES}"
            )
        
        # Split PDF into individual pages
        split_files = []
        
        for page_num in range(total_pages):
            # Create a new PDF with single page
            pdf_writer = PdfWriter()
            pdf_writer.add_page(pdf_reader.pages[page_num])
            
            # Write to bytes buffer
            output_buffer = io.BytesIO()
            pdf_writer.write(output_buffer)
            output_buffer.seek(0)
            
            # Encode as base64
            page_data = base64.b64encode(output_buffer.read()).decode('utf-8')
            
            split_files.append({
                "page_number": page_num + 1,
                "filename": f"page_{page_num + 1}.pdf",
                "data": page_data,
                "size": len(page_data)
            })
            
            logger.info(f"Processed page {page_num + 1}/{total_pages}")
        
        return {
            "status": "success",
            "original_filename": file.filename,
            "total_pages": total_pages,
            "pages_split": total_pages > 1,
            "files": split_files
        }
        
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing PDF: {str(e)}"
        )

@app.get("/", tags=["Info"])
async def root():
    """Service information and available endpoints
    
    Returns basic information about the PDF Splitter service
    and lists all available API endpoints.
    """
    return {
        "service": "PDF Splitter",
        "version": "1.0.0",
        "description": "High-performance PDF splitting service for Cloudflare Containers",
        "endpoints": {
            "/": "Service information (this endpoint)",
            "/health": "Health check endpoint",
            "/split-pdf": "Upload and split PDF into pages (POST)",
            "/docs": "Interactive API documentation (Swagger UI)",
            "/redoc": "Alternative API documentation (ReDoc)"
        },
        "limits": {
            "max_file_size_mb": MAX_FILE_SIZE / 1024 / 1024,
            "max_pages": MAX_PAGES
        },
        "deployment": {
            "platform": "Cloudflare Containers",
            "url": "https://pdf-splitter-service.carles-64e.workers.dev"
        },
        "authentication": {
            "required": True,
            "methods": [
                "Bearer token in Authorization header",
                "API key in X-API-Key header"
            ],
            "note": "Default token: pdf-splitter-public-2025 (change in production)"
        }
    }

if __name__ == "__main__":
    import uvicorn
    # Print API token info
    print(f"\n{'='*50}")
    if API_TOKEN == DEFAULT_TOKEN:
        print(f"Using DEFAULT API Token: {API_TOKEN}")
        print(f"⚠️  Change this token in production!")
    else:
        print(f"Using CUSTOM API Token")
    print(f"\nAuthentication methods:")
    print(f"1. Authorization: Bearer {API_TOKEN}")
    print(f"2. X-API-Key: {API_TOKEN}")
    print(f"{'='*50}\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)