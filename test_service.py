#!/usr/bin/env python3
"""
PDF Splitter Service Test Script
Tests the microservice functionality before n8n integration
"""

import requests
import json
import base64
import os
from pathlib import Path

def test_service_health():
    """Test if the service is running"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Service is healthy!")
            return True
        else:
            print(f"❌ Service health check failed: {response.status_code}")
            return False
    except requests.ConnectionError:
        print("❌ Cannot connect to service. Is it running?")
        print("   Run: docker-compose up -d")
        return False

def test_pdf_upload(pdf_path):
    """Test PDF upload and splitting"""
    if not os.path.exists(pdf_path):
        print(f"❌ Test PDF not found: {pdf_path}")
        return False
    
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (os.path.basename(pdf_path), f, 'application/pdf')}
            response = requests.post(
                "http://localhost:8000/split-pdf",
                files=files,
                timeout=30
            )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ PDF processed successfully!")
            print(f"   📄 Total pages: {result['total_pages']}")
            print(f"   ✂️ Split needed: {result['pages_split']}")
            print(f"   📁 Files returned: {len(result['files'])}")
            
            # Test base64 data validity
            for i, file_data in enumerate(result['files']):
                try:
                    decoded = base64.b64decode(file_data['data'])
                    print(f"   ✅ Page {i+1}: {len(decoded)} bytes, valid base64")
                except Exception as e:
                    print(f"   ❌ Page {i+1}: Invalid base64 data - {e}")
            
            return True
        else:
            print(f"❌ PDF processing failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing PDF upload: {e}")
        return False

def create_test_pdf():
    """Create a simple test PDF if none exists"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        pdf_path = "test_multi_page.pdf"
        c = canvas.Canvas(pdf_path, pagesize=letter)
        
        # Create 3 pages
        for page in range(1, 4):
            c.drawString(100, 750, f"This is page {page}")
            c.drawString(100, 700, f"Generated for PDF splitter testing")
            if page < 3:
                c.showPage()
        
        c.save()
        print(f"✅ Created test PDF: {pdf_path}")
        return pdf_path
        
    except ImportError:
        print("📝 Install reportlab to auto-generate test PDF:")
        print("   pip install reportlab")
        print("   Or provide your own test PDF file")
        return None

def main():
    print("🧪 PDF Splitter Service Test")
    print("=" * 40)
    
    # Test 1: Service Health
    print("\n1. Testing service health...")
    if not test_service_health():
        return
    
    # Test 2: PDF Processing
    print("\n2. Testing PDF processing...")
    
    # Look for test PDF files
    test_files = [
        "test.pdf",
        "test_multi_page.pdf", 
        "sample.pdf"
    ]
    
    pdf_found = None
    for test_file in test_files:
        if os.path.exists(test_file):
            pdf_found = test_file
            break
    
    if not pdf_found:
        print("📁 No test PDF found, trying to create one...")
        pdf_found = create_test_pdf()
    
    if pdf_found:
        test_pdf_upload(pdf_found)
    else:
        print("❌ No test PDF available")
        print("   Place a PDF file named 'test.pdf' in this directory")
    
    print("\n🎉 Testing complete!")
    print("If all tests passed, your service is ready for n8n integration!")

if __name__ == "__main__":
    main()