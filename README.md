# PDF Splitter Service

A high-performance microservice for splitting PDF files into individual pages, deployed on Cloudflare Containers. Built with FastAPI and optimized for integration with n8n workflows and automation platforms.

## 🚀 Live Service

**Production URL:** https://pdf-splitter-service.carles-64e.workers.dev

### 📚 Interactive API Documentation
- **Swagger UI:** https://pdf-splitter-service.carles-64e.workers.dev/docs
- **ReDoc:** https://pdf-splitter-service.carles-64e.workers.dev/redoc

## 🔑 Authentication

This service requires authentication using an API token. You can authenticate using either method:

1. **Bearer Token** (Recommended)
   ```
   Authorization: Bearer <your-api-token>
   ```

2. **API Key Header**
   ```
   X-API-Key: <your-api-token>
   ```

> **Note:** Contact the administrator to obtain your API access token.

## 🎯 Features

- ✅ Split multi-page PDFs into individual pages
- ✅ Base64 encoding for seamless integration
- ✅ Bearer token authentication for security
- ✅ CORS support for browser-based applications
- ✅ Comprehensive error handling and validation
- ✅ Auto-scaling with Cloudflare Containers (1-5 instances)
- ✅ Interactive API documentation
- ✅ Health monitoring endpoint
- ✅ **AWS S3 Integration** - Process PDFs directly from S3
- ✅ **S3 Output Support** - Save split pages back to S3

## 📊 Service Limits

- **Maximum file size:** 50 MB
- **Maximum pages:** 500 pages per PDF
- **Supported format:** PDF files only
- **Response format:** Base64 encoded PDF pages

## 🔧 API Endpoints

### 1. Service Information
```http
GET /
```
Returns service information, available endpoints, and configuration details.

**Example:**
```bash
curl https://pdf-splitter-service.carles-64e.workers.dev/
```

### 2. Health Check
```http
GET /health
```
Check service health status (no authentication required).

**Example:**
```bash
curl https://pdf-splitter-service.carles-64e.workers.dev/health
```

### 3. Split PDF (Requires Authentication)
```http
POST /split-pdf
```
Upload a PDF file and receive individual pages as base64-encoded PDFs.

**Headers Required:**
- `Authorization: Bearer <token>` or `X-API-Key: <token>`
- `Content-Type: multipart/form-data`

**Example:**
```bash
curl -X POST \
  -H "Authorization: Bearer pdf-splitter-public-2025" \
  -F "file=@document.pdf" \
  https://pdf-splitter-service.carles-64e.workers.dev/split-pdf
```

### 4. Split PDF from S3 (Requires Authentication)
```http
POST /split-pdf-from-s3
```
Process a PDF directly from an S3 bucket without uploading.

**Headers Required:**
- `Authorization: Bearer <token>` or `X-API-Key: <token>`
- `Content-Type: application/json`

**Request Body:**
```json
{
  "bucket": "my-pdf-bucket",
  "key": "documents/invoice.pdf",
  "save_to_s3": false,
  "output_prefix": "split/",
  "output_bucket": "my-output-bucket"
}
```

**Example - Download split pages:**
```bash
curl -X POST \
  -H "Authorization: Bearer pdf-splitter-public-2025" \
  -H "Content-Type: application/json" \
  -d '{
    "bucket": "my-bucket",
    "key": "documents/invoice.pdf",
    "save_to_s3": false
  }' \
  https://pdf-splitter-service.carles-64e.workers.dev/split-pdf-from-s3
```

**Example - Save split pages to S3:**
```bash
curl -X POST \
  -H "Authorization: Bearer pdf-splitter-public-2025" \
  -H "Content-Type: application/json" \
  -d '{
    "bucket": "my-bucket",
    "key": "documents/invoice.pdf",
    "save_to_s3": true,
    "output_prefix": "split/invoice/",
    "output_bucket": "my-output-bucket"
  }' \
  https://pdf-splitter-service.carles-64e.workers.dev/split-pdf-from-s3
```

## 💻 Integration Examples

### n8n Workflow Integration

#### HTTP Request Node Configuration:
```json
{
  "method": "POST",
  "url": "https://pdf-splitter-service.carles-64e.workers.dev/split-pdf",
  "authentication": {
    "type": "genericCredentialType",
    "genericAuthType": "httpHeaderAuth"
  },
  "sendHeaders": true,
  "headerParameters": {
    "parameters": [
      {
        "name": "Authorization",
        "value": "Bearer pdf-splitter-public-2025"
      }
    ]
  },
  "sendBody": true,
  "bodyContentType": "multipart-form-data",
  "bodyParameters": {
    "parameters": [
      {
        "parameterType": "formBinaryData",
        "name": "file",
        "inputDataFieldName": "data"
      }
    ]
  }
}
```

#### Processing Response in Function Node:
```javascript
const response = $input.first().json;
const pages = response.files;

// Process each page
return pages.map(page => ({
  json: {
    pageNumber: page.page_number,
    filename: page.filename,
    pdfData: page.data,
    size: page.size
  },
  binary: {
    data: {
      data: page.data,
      mimeType: 'application/pdf',
      fileName: page.filename
    }
  }
}));
```

### Python Integration

```python
import requests
import base64
from pathlib import Path

class PDFSplitter:
    def __init__(self, api_token):
        self.api_token = api_token
        self.base_url = "https://pdf-splitter-service.carles-64e.workers.dev"
    
    def split_pdf(self, pdf_path, output_dir="output"):
        """Split a PDF file into individual pages."""
        url = f"{self.base_url}/split-pdf"
        headers = {"Authorization": f"Bearer {self.api_token}"}
        
        with open(pdf_path, 'rb') as f:
            files = {'file': (Path(pdf_path).name, f, 'application/pdf')}
            response = requests.post(url, files=files, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            Path(output_dir).mkdir(exist_ok=True)
            
            for page_info in data['files']:
                page_data = base64.b64decode(page_info['data'])
                output_path = Path(output_dir) / page_info['filename']
                
                with open(output_path, 'wb') as f:
                    f.write(page_data)
                    print(f"✅ Saved {page_info['filename']}")
            
            return data
        else:
            raise Exception(f"Error: {response.json()['detail']}")
    
    def split_pdf_from_s3(self, bucket, key, save_to_s3=False, output_prefix=None):
        """Split a PDF directly from S3."""
        url = f"{self.base_url}/split-pdf-from-s3"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "bucket": bucket,
            "key": key,
            "save_to_s3": save_to_s3,
            "output_prefix": output_prefix
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            
            if save_to_s3:
                print(f"✅ Split {data['total_pages']} pages to S3")
                for s3_key in data.get('s3_output_files', []):
                    print(f"  - {s3_key}")
            else:
                # Save locally if not saving to S3
                for page_info in data['files']:
                    page_data = base64.b64decode(page_info['data'])
                    with open(page_info['filename'], 'wb') as f:
                        f.write(page_data)
                        print(f"✅ Saved {page_info['filename']}")
            
            return data
        else:
            raise Exception(f"Error: {response.json()['detail']}")

# Usage - Upload file
splitter = PDFSplitter("pdf-splitter-public-2025")
result = splitter.split_pdf("document.pdf")
print(f"Split {result['total_pages']} pages successfully!")

# Usage - Process from S3
result = splitter.split_pdf_from_s3(
    bucket="my-bucket",
    key="documents/invoice.pdf",
    save_to_s3=True,
    output_prefix="split/"
)
print(f"Processed {result['total_pages']} pages from S3!")
```

### JavaScript/Node.js Integration

```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');
const path = require('path');

class PDFSplitter {
    constructor(apiToken) {
        this.apiToken = apiToken;
        this.baseUrl = 'https://pdf-splitter-service.carles-64e.workers.dev';
    }
    
    async splitPDF(filePath, outputDir = 'output') {
        const form = new FormData();
        form.append('file', fs.createReadStream(filePath));
        
        try {
            const response = await axios.post(
                `${this.baseUrl}/split-pdf`,
                form,
                {
                    headers: {
                        ...form.getHeaders(),
                        'Authorization': `Bearer ${this.apiToken}`
                    }
                }
            );
            
            // Create output directory
            if (!fs.existsSync(outputDir)) {
                fs.mkdirSync(outputDir, { recursive: true });
            }
            
            // Save each page
            for (const page of response.data.files) {
                const pdfBuffer = Buffer.from(page.data, 'base64');
                const outputPath = path.join(outputDir, page.filename);
                fs.writeFileSync(outputPath, pdfBuffer);
                console.log(`✅ Saved ${page.filename}`);
            }
            
            return response.data;
        } catch (error) {
            throw new Error(error.response?.data?.detail || error.message);
        }
    }
}

// Usage
const splitter = new PDFSplitter('pdf-splitter-public-2025');
splitter.splitPDF('document.pdf')
    .then(result => {
        console.log(`Split ${result.total_pages} pages successfully!`);
    })
    .catch(console.error);
```

### Browser JavaScript

```html
<!DOCTYPE html>
<html>
<head>
    <title>PDF Splitter</title>
</head>
<body>
    <input type="file" id="fileInput" accept=".pdf">
    <button onclick="splitPDF()">Split PDF</button>
    
    <script>
    const API_TOKEN = 'pdf-splitter-public-2025';
    const API_URL = 'https://pdf-splitter-service.carles-64e.workers.dev';
    
    async function splitPDF() {
        const fileInput = document.getElementById('fileInput');
        const file = fileInput.files[0];
        
        if (!file || file.type !== 'application/pdf') {
            alert('Please select a PDF file');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch(`${API_URL}/split-pdf`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${API_TOKEN}`
                },
                body: formData
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail);
            }
            
            const data = await response.json();
            
            // Download each page
            data.files.forEach((page, index) => {
                const pdfData = atob(page.data);
                const bytes = new Uint8Array(pdfData.length);
                
                for (let i = 0; i < pdfData.length; i++) {
                    bytes[i] = pdfData.charCodeAt(i);
                }
                
                const blob = new Blob([bytes], { type: 'application/pdf' });
                const url = URL.createObjectURL(blob);
                
                const a = document.createElement('a');
                a.href = url;
                a.download = page.filename;
                a.click();
                
                URL.revokeObjectURL(url);
            });
            
            alert(`Successfully split ${data.total_pages} pages!`);
        } catch (error) {
            alert(`Error: ${error.message}`);
        }
    }
    </script>
</body>
</html>
```

### cURL Examples

```bash
# Split PDF with Bearer token
curl -X POST \
  -H "Authorization: Bearer pdf-splitter-public-2025" \
  -F "file=@document.pdf" \
  https://pdf-splitter-service.carles-64e.workers.dev/split-pdf

# Split PDF with X-API-Key header
curl -X POST \
  -H "X-API-Key: pdf-splitter-public-2025" \
  -F "file=@document.pdf" \
  https://pdf-splitter-service.carles-64e.workers.dev/split-pdf

# Save response to file
curl -X POST \
  -H "Authorization: Bearer pdf-splitter-public-2025" \
  -F "file=@document.pdf" \
  https://pdf-splitter-service.carles-64e.workers.dev/split-pdf \
  -o response.json
```

## 🚀 Deployment

### Prerequisites

1. **Docker** - Required for building container images
2. **Wrangler CLI** - Cloudflare's deployment tool
3. **Cloudflare Account** - With Workers Paid plan

### Quick Deploy

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd python-pdf-splitter
   ```

2. **Install Wrangler**
   ```bash
   npm install -g wrangler
   ```

3. **Authenticate with Cloudflare**
   ```bash
   wrangler login
   ```

4. **Set API Token Secret**
   ```bash
   # Generate a secure token
   wrangler secret put API_TOKEN
   # Enter your desired token when prompted
   ```

5. **Configure AWS Credentials (Optional - for S3 integration)**
   ```bash
   # Set AWS credentials as secrets
   wrangler secret put AWS_ACCESS_KEY_ID
   wrangler secret put AWS_SECRET_ACCESS_KEY
   
   # Optionally set the region and default bucket
   wrangler secret put AWS_REGION  # Default: us-east-1
   wrangler secret put S3_BUCKET_NAME  # Optional default bucket
   ```

6. **Deploy**
   ```bash
   wrangler deploy
   ```

### Configuration

#### `wrangler.jsonc`
```json
{
  "name": "pdf-splitter-service",
  "main": "worker.js",
  "compatibility_date": "2025-01-27",
  "compatibility_flags": ["nodejs_compat"],
  
  "durable_objects": {
    "bindings": [{
      "name": "PDF_SPLITTER",
      "class_name": "PDFSplitter"
    }]
  },
  
  "migrations": [{
    "tag": "v1",
    "new_sqlite_classes": ["PDFSplitter"]
  }],
  
  "containers": [{
    "class_name": "PDFSplitter",
    "image": "./Dockerfile",
    "max_instances": 5
  }],
  
  "vars": {
    "SERVICE_NAME": "pdf-splitter",
    "VERSION": "1.0.0"
  }
}
```

### Environment Variables

**Required:**
- `API_TOKEN` - Authentication token (stored as secret)

**Optional (for S3 integration):**
- `AWS_ACCESS_KEY_ID` - AWS access key for S3 operations
- `AWS_SECRET_ACCESS_KEY` - AWS secret key for S3 operations
- `AWS_REGION` - AWS region (default: us-east-1)
- `S3_BUCKET_NAME` - Default S3 bucket name (optional)

**Service Configuration:**
- `SERVICE_NAME` - Service identifier
- `VERSION` - Service version

## 🔐 AWS S3 Configuration

### Required IAM Permissions

When using S3 integration, ensure your AWS IAM user/role has these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name"
      ]
    }
  ]
}
```

### S3 Bucket Configuration

Ensure your S3 bucket has:
- Proper ACLs for the IAM user/role
- Versioning enabled (optional but recommended)
- Lifecycle policies for old split files (optional)

## 🐳 Local Development

### Running Locally

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables**
   ```bash
   export API_TOKEN="your-local-test-token"
   # For S3 integration (optional)
   export AWS_ACCESS_KEY_ID="your-access-key"
   export AWS_SECRET_ACCESS_KEY="your-secret-key"
   export AWS_REGION="us-east-1"
   ```

3. **Run the service**
   ```bash
   python main.py
   ```

4. **Access local documentation**
   - http://localhost:8000/docs
   - http://localhost:8000/redoc

### Running with Docker

```bash
# Build image
docker build -t pdf-splitter .

# Run container
docker run -p 8000:8000 -e API_TOKEN="test-token" pdf-splitter
```

## 📈 Monitoring

### Health Checks

Monitor service health:
```bash
curl https://pdf-splitter-service.carles-64e.workers.dev/health
```

### Cloudflare Dashboard

1. Go to https://dash.cloudflare.com/
2. Navigate to Workers & Pages
3. Select `pdf-splitter-service`
4. View:
   - Real-time logs
   - Request metrics
   - Error rates
   - Container status

### Logging

The service logs include:
- Request processing details
- Error messages with stack traces
- Authentication attempts
- Container lifecycle events

## 🔧 Troubleshooting

### Common Issues

#### 401 Unauthorized
- **Cause:** Missing or invalid API token
- **Solution:** Ensure you're including the correct token in the Authorization header

#### 413 Payload Too Large
- **Cause:** PDF file exceeds 50MB limit
- **Solution:** Compress or split the PDF before uploading

#### 422 Unprocessable Entity
- **Cause:** PDF has more than 500 pages
- **Solution:** Process the PDF in batches

#### 500 Internal Server Error
- **Cause:** PDF processing error
- **Solution:** Check if the PDF is corrupted or has special encoding

### Debug Tips

1. **Test with small PDFs first**
2. **Check API documentation for correct request format**
3. **Verify token using the health endpoint first**
4. **Use browser developer tools to inspect requests/responses**

## 🤝 Support

- **API Issues:** carles@plaved.com
- **Bug Reports:** Create an issue in this repository
- **Feature Requests:** Submit a pull request or issue
- **Cloudflare Status:** https://www.cloudflarestatus.com/

## 📄 License

MIT License - See LICENSE file for details

## 🔒 Security

### Best Practices

1. **Never expose your API token in client-side code**
2. **Rotate tokens regularly**
3. **Use HTTPS for all requests**
4. **Implement rate limiting in production**
5. **Monitor for unusual activity**

### Reporting Security Issues

Please report security vulnerabilities to carles@plaved.com

## 🚦 API Response Examples

### Successful Response
```json
{
  "status": "success",
  "original_filename": "document.pdf",
  "total_pages": 3,
  "pages_split": true,
  "files": [
    {
      "page_number": 1,
      "filename": "page_1.pdf",
      "data": "JVBERi0xLjQKJeLj...",
      "size": 45632
    },
    {
      "page_number": 2,
      "filename": "page_2.pdf",
      "data": "JVBERi0xLjQKJeLj...",
      "size": 38921
    }
  ]
}
```

### Error Response
```json
{
  "detail": "Invalid or missing authentication token"
}
```

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Cloudflare Containers Docs](https://developers.cloudflare.com/containers/)
- [Wrangler CLI Reference](https://developers.cloudflare.com/workers/wrangler/)
- [n8n Integration Guide](https://docs.n8n.io/)

---

Built with ❤️ using FastAPI and deployed on Cloudflare Containers