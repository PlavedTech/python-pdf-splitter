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
import asyncio
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security configuration
# Default token for public access - change in production!
DEFAULT_TOKEN = "pdf-splitter-public-2025"
API_TOKEN = os.getenv("API_TOKEN", DEFAULT_TOKEN)
security = HTTPBearer(auto_error=False)

# AWS Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
DEFAULT_S3_BUCKET = os.getenv("S3_BUCKET_NAME", "")

# Initialize S3 client if AWS credentials are available
s3_client = None
if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        logger.info(f"AWS S3 client initialized for region: {AWS_REGION}")
    except Exception as e:
        logger.error(f"Failed to initialize S3 client: {str(e)}")
else:
    logger.info("AWS credentials not configured. S3 functionality disabled.")

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

class S3PDFRequest(BaseModel):
    bucket: str = Field(description="S3 bucket name", example="my-pdf-bucket")
    key: str = Field(description="S3 object key (file path)", example="documents/invoice.pdf")
    save_to_s3: bool = Field(default=False, description="Save split pages back to S3")
    output_prefix: Optional[str] = Field(default=None, description="Prefix for output files in S3", example="split/")
    output_bucket: Optional[str] = Field(default=None, description="Output bucket (defaults to input bucket)")

class S3SplitPDFResponse(BaseModel):
    status: str = Field(description="Operation status")
    original_s3_location: str = Field(description="S3 location of original file")
    total_pages: int = Field(description="Total number of pages in the PDF")
    pages_split: bool = Field(description="Whether the PDF was split")
    files: List[PageData] = Field(description="Array of split PDF pages (if not saved to S3)")
    s3_output_files: Optional[List[str]] = Field(default=None, description="S3 keys of saved files (if saved to S3)")

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

# S3 Helper functions
async def download_from_s3(bucket: str, key: str) -> bytes:
    """Download a file from S3 and return its contents."""
    if not s3_client:
        raise HTTPException(
            status_code=503,
            detail="S3 functionality is not configured. Please set AWS credentials."
        )
    
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return response['Body'].read()
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            raise HTTPException(status_code=404, detail=f"File not found: s3://{bucket}/{key}")
        elif e.response['Error']['Code'] == 'AccessDenied':
            raise HTTPException(status_code=403, detail=f"Access denied to s3://{bucket}/{key}")
        else:
            logger.error(f"S3 download error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error downloading from S3: {str(e)}")

async def upload_to_s3(bucket: str, key: str, data: bytes, content_type: str = "application/pdf") -> str:
    """Upload data to S3 and return the S3 key."""
    if not s3_client:
        raise HTTPException(
            status_code=503,
            detail="S3 functionality is not configured. Please set AWS credentials."
        )
    
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type
        )
        return f"s3://{bucket}/{key}"
    except ClientError as e:
        logger.error(f"S3 upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading to S3: {str(e)}")

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
        
        # Validate PDF integrity
        try:
            _ = pdf_reader.metadata  # Check if PDF is valid and readable
        except:
            raise HTTPException(
                status_code=400,
                detail="Corrupted or invalid PDF file"
            )
        
        total_pages = len(pdf_reader.pages)
        logger.info(f"Processing PDF '{file.filename}' with {total_pages} pages")
        
        # Check page limit
        if total_pages > MAX_PAGES:
            raise HTTPException(
                status_code=422,
                detail=f"PDF has too many pages. Pages: {total_pages}, Max: {MAX_PAGES}"
            )
        
        # Helper function for async page processing
        async def process_page(page_num: int) -> dict:
            # Create a new PDF with single page
            pdf_writer = PdfWriter()
            pdf_writer.add_page(pdf_reader.pages[page_num])
            
            # Write to bytes buffer
            output_buffer = io.BytesIO()
            pdf_writer.write(output_buffer)
            
            # Get actual size in bytes before encoding
            pdf_bytes = output_buffer.getvalue()
            size_in_bytes = len(pdf_bytes)
            
            # Encode as base64
            page_data = base64.b64encode(pdf_bytes).decode('utf-8')
            
            logger.info(f"Processed page {page_num + 1}/{total_pages}")
            
            return {
                "page_number": page_num + 1,
                "filename": f"page_{page_num + 1}.pdf",
                "data": page_data,
                "size": size_in_bytes  # Actual bytes, not base64 string length
            }
        
        # Process pages in parallel for better performance
        if total_pages > 10:  # Use parallel processing for PDFs with many pages
            tasks = [process_page(page_num) for page_num in range(total_pages)]
            split_files = await asyncio.gather(*tasks)
        else:  # Sequential for small PDFs to avoid overhead
            split_files = []
            for page_num in range(total_pages):
                split_files.append(await process_page(page_num))
        
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

@app.post(
    "/split-pdf-from-s3",
    response_model=S3SplitPDFResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": AuthenticationError, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Access denied to S3 resource"},
        404: {"model": ErrorResponse, "description": "File not found in S3"},
        413: {"model": ErrorResponse, "description": "File too large"},
        422: {"model": ErrorResponse, "description": "Too many pages in PDF"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "S3 functionality not configured"}
    },
    tags=["PDF Operations"],
    summary="Split PDF from S3 bucket",
    dependencies=[Depends(verify_token)]
)
async def split_pdf_from_s3(
    request: S3PDFRequest
) -> S3SplitPDFResponse:
    """
    Split a PDF file directly from an S3 bucket.
    
    This endpoint downloads a PDF from S3, splits it into individual pages,
    and optionally saves the split pages back to S3.
    
    **Requirements:**
    - AWS credentials must be configured
    - Proper read permissions for the source bucket
    - Write permissions for the output bucket (if saving to S3)
    
    **Features:**
    - No file upload size limits (processes directly from S3)
    - Optional saving of split pages back to S3
    - Maintains all original PDF formatting
    
    **Returns:**
    - If `save_to_s3` is False: Base64-encoded pages in response
    - If `save_to_s3` is True: S3 keys of saved split pages
    """
    # Check if S3 is configured
    if not s3_client:
        raise HTTPException(
            status_code=503,
            detail="S3 functionality is not configured. Please set AWS credentials."
        )
    
    # Validate bucket names
    if not request.bucket:
        raise HTTPException(status_code=400, detail="Bucket name is required")
    
    if not request.key:
        raise HTTPException(status_code=400, detail="Object key is required")
    
    # Check if key ends with .pdf
    if not request.key.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Expected PDF, got {request.key.split('.')[-1] if '.' in request.key else 'unknown'}"
        )
    
    try:
        # Download PDF from S3
        logger.info(f"Downloading PDF from s3://{request.bucket}/{request.key}")
        file_content = await download_from_s3(request.bucket, request.key)
        
        # Check file size
        file_size = len(file_content)
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Size: {file_size / 1024 / 1024:.1f}MB, Max: {MAX_FILE_SIZE / 1024 / 1024}MB"
            )
        
        # Process PDF
        pdf_reader = PdfReader(io.BytesIO(file_content))
        
        # Validate PDF integrity
        try:
            _ = pdf_reader.metadata
        except:
            raise HTTPException(
                status_code=400,
                detail="Corrupted or invalid PDF file"
            )
        
        total_pages = len(pdf_reader.pages)
        logger.info(f"Processing S3 PDF with {total_pages} pages")
        
        # Check page limit
        if total_pages > MAX_PAGES:
            raise HTTPException(
                status_code=422,
                detail=f"PDF has too many pages. Pages: {total_pages}, Max: {MAX_PAGES}"
            )
        
        # Extract filename from key
        filename = request.key.split('/')[-1].replace('.pdf', '')
        
        # Helper function for async page processing
        async def process_page(page_num: int) -> tuple:
            # Create a new PDF with single page
            pdf_writer = PdfWriter()
            pdf_writer.add_page(pdf_reader.pages[page_num])
            
            # Write to bytes buffer
            output_buffer = io.BytesIO()
            pdf_writer.write(output_buffer)
            
            # Get actual size in bytes
            pdf_bytes = output_buffer.getvalue()
            size_in_bytes = len(pdf_bytes)
            
            # Prepare page data
            page_filename = f"{filename}_page_{page_num + 1}.pdf"
            
            # If saving to S3
            if request.save_to_s3:
                output_bucket = request.output_bucket or request.bucket
                output_prefix = request.output_prefix or ""
                output_key = f"{output_prefix}{page_filename}"
                
                # Upload to S3
                s3_location = await upload_to_s3(output_bucket, output_key, pdf_bytes)
                logger.info(f"Uploaded page {page_num + 1} to {s3_location}")
                
                return (page_num + 1, page_filename, None, size_in_bytes, output_key)
            else:
                # Encode as base64 for response
                page_data = base64.b64encode(pdf_bytes).decode('utf-8')
                return (page_num + 1, page_filename, page_data, size_in_bytes, None)
        
        # Process pages
        if total_pages > 10:  # Use parallel processing for many pages
            tasks = [process_page(page_num) for page_num in range(total_pages)]
            results = await asyncio.gather(*tasks)
        else:
            results = []
            for page_num in range(total_pages):
                results.append(await process_page(page_num))
        
        # Prepare response
        if request.save_to_s3:
            # Return S3 keys
            s3_output_files = [r[4] for r in results if r[4]]
            return {
                "status": "success",
                "original_s3_location": f"s3://{request.bucket}/{request.key}",
                "total_pages": total_pages,
                "pages_split": total_pages > 1,
                "files": [],  # Empty when saved to S3
                "s3_output_files": s3_output_files
            }
        else:
            # Return base64 encoded pages
            split_files = [
                {
                    "page_number": r[0],
                    "filename": r[1],
                    "data": r[2],
                    "size": r[3]
                }
                for r in results
            ]
            return {
                "status": "success",
                "original_s3_location": f"s3://{request.bucket}/{request.key}",
                "total_pages": total_pages,
                "pages_split": total_pages > 1,
                "files": split_files,
                "s3_output_files": None
            }
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Error processing S3 PDF: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing PDF from S3: {str(e)}"
        )

@app.get("/", tags=["Info"])
async def root():
    """Service information and available endpoints
    
    Returns basic information about the PDF Splitter service
    and lists all available API endpoints.
    """
    response = {
        "service": "PDF Splitter",
        "version": "1.0.0",
        "description": "High-performance PDF splitting service for Cloudflare Containers",
        "endpoints": {
            "/": "Service information (this endpoint)",
            "/health": "Health check endpoint",
            "/split-pdf": "Upload and split PDF into pages (POST)",
            "/split-pdf-from-s3": "Split PDF directly from S3 bucket (POST)",
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
            "note": "Authentication required - contact admin for token"
        },
        "aws_s3": {
            "enabled": s3_client is not None,
            "region": AWS_REGION if s3_client else None,
            "features": [
                "Process PDFs directly from S3",
                "Save split pages back to S3",
                "No file upload size limits for S3 files"
            ] if s3_client else ["S3 functionality not configured"]
        }
    }
    return response

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