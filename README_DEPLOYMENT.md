# PDF Splitter Service - Cloudflare Containers Deployment

## Prerequisites

### 1. Docker Installation (Required)
You need Docker to build and deploy containers to Cloudflare. Choose one option:

#### Option A: Docker Desktop (Recommended)
```bash
# Download from: https://www.docker.com/products/docker-desktop/
# Or install via Homebrew:
brew install --cask docker
```

#### Option B: Colima (Lightweight alternative)
```bash
brew install colima docker
colima start
```

#### Option C: Podman (Docker alternative)
```bash
brew install podman
podman machine init
podman machine start
```

### 2. Verify Prerequisites
```bash
# Check Docker is running
docker info

# Check Wrangler is installed
wrangler --version

# Check authentication
wrangler whoami
```

## Deployment Steps

### 1. Authenticate with Cloudflare (if not already done)
```bash
wrangler login
```

### 2. Deploy to Cloudflare Containers
```bash
# Using the provided script
./deploy.sh

# Or manually
wrangler deploy
```

## Configuration Files

### `wrangler.jsonc`
- Configures the container deployment
- Sets autoscaling parameters (1-5 instances)
- Defines the Worker integration

### `worker.js`
- Handles routing requests to the container
- Integrates with Cloudflare Workers

### `Dockerfile`
- Defines the container image
- Based on Python 3.11 slim
- Includes FastAPI application

## API Documentation

Your deployed service has **interactive API documentation** available at:

### 📚 Swagger UI (Recommended)
https://pdf-splitter-service.carles-64e.workers.dev/docs

- Interactive API testing
- Try endpoints directly in browser
- Complete request/response schemas
- Built-in file upload interface

### 📖 ReDoc (Alternative)
https://pdf-splitter-service.carles-64e.workers.dev/redoc

- Clean, readable documentation
- Better for printing/PDF export
- Detailed schema information

## Testing the Deployment

```bash
# Get your worker URL from deployment output
# It will look like: https://pdf-splitter-service.{your-subdomain}.workers.dev

# Test health endpoint
curl https://pdf-splitter-service.{your-subdomain}.workers.dev/health

# Test PDF splitting
curl -X POST \
  -F "file=@test.pdf" \
  https://pdf-splitter-service.{your-subdomain}.workers.dev/split-pdf
```

## Monitoring

View logs and metrics in the Cloudflare Dashboard:
1. Go to https://dash.cloudflare.com/
2. Navigate to Workers & Pages
3. Select your pdf-splitter-service
4. View logs, metrics, and configuration

## Troubleshooting

### Docker not found
Install Docker Desktop or one of the alternatives listed above.

### Wrangler authentication issues
```bash
wrangler logout
wrangler login
```

### Deployment fails
1. Ensure you have a Workers Paid plan
2. Check that Docker is running
3. Verify your account has container permissions
4. Review error messages in deployment output

## Cost Considerations

- Cloudflare Containers requires a Workers Paid plan ($5/month)
- Container usage is billed based on:
  - Number of instances running
  - CPU and memory usage
  - Request volume

## Support

For issues or questions:
- Cloudflare Containers Docs: https://developers.cloudflare.com/containers/
- Wrangler Docs: https://developers.cloudflare.com/workers/wrangler/