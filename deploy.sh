#!/bin/bash

echo "🚀 Cloudflare Containers Deployment Script for PDF Splitter Service"
echo "================================================================="

# Check if Docker is running
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    echo "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop/"
    echo ""
    echo "Alternative options:"
    echo "1. Install Docker Desktop for Mac"
    echo "2. Use Podman as an alternative: brew install podman"
    echo "3. Use Colima: brew install colima docker"
    exit 1
fi

if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker daemon is not running"
    echo "Please start Docker Desktop and try again"
    exit 1
fi

echo "✅ Docker is running"

# Check if Wrangler is authenticated
if ! wrangler whoami > /dev/null 2>&1; then
    echo "❌ Not authenticated with Cloudflare"
    echo "Running: wrangler login"
    wrangler login
fi

echo "✅ Authenticated with Cloudflare"

# Build and deploy
echo "📦 Building and deploying container to Cloudflare..."
wrangler deploy

if [ $? -eq 0 ]; then
    echo "✅ Deployment successful!"
    echo ""
    echo "Your PDF Splitter service is now deployed to Cloudflare Containers!"
    echo "Check your deployment at: https://dash.cloudflare.com/"
else
    echo "❌ Deployment failed. Please check the error messages above."
    exit 1
fi