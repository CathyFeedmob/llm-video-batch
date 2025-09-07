#!/usr/bin/env python3
"""
Test script to isolate and test freeimagehost image uploading functionality.

Usage:
  python3 scripts/test_freeimagehost_upload.py [image_path]

This script:
- Tests the freeimagehost upload function in isolation
- Provides detailed response information including status codes
- Uses the first image from img/ready if no path is specified
- Returns the uploaded image URL for verification
"""

import os
import requests
from pathlib import Path
from dotenv import load_dotenv
import json
import sys

load_dotenv()

FREEIMAGE_API_KEY = os.getenv("FREEIMAGE_API_KEY")

def find_first_image(directory):
    """Find the first image file in the specified directory."""
    directory_path = Path(directory)
    if not directory_path.exists():
        print(f"Directory {directory} does not exist.")
        return None
        
    for filename in directory_path.iterdir():
        if filename.is_file() and filename.suffix.lower() in ['.png', '.jpg', '.jpeg']:
            return str(filename)
    return None

def test_upload_image_to_freeimagehost(image_path):
    """Test upload an image to freeimage.host and return detailed response information."""
    print(f"=== Testing freeimage.host Upload ===")
    print(f"Image path: {image_path}")
    print(f"API Key present: {'Yes' if FREEIMAGE_API_KEY else 'No'}")
    
    if not FREEIMAGE_API_KEY:
        print("❌ Error: FREEIMAGE_API_KEY environment variable not set. Cannot upload image.")
        return None

    if not os.path.exists(image_path):
        print(f"❌ Error: Image file not found at {image_path}")
        return None

    try:
        # Read image file
        with open(image_path, "rb") as f:
            image_data = f.read()
        
        print(f"📁 Image file size: {len(image_data)} bytes")

        # Determine mime type dynamically
        mime_type = "image/jpeg" if image_path.lower().endswith(('.jpg', '.jpeg')) else "image/png"
        print(f"🎨 Detected MIME type: {mime_type}")

        # Prepare files for upload
        files = {
            'source': (os.path.basename(image_path), image_data, mime_type),
            'key': (None, FREEIMAGE_API_KEY),
            'format': (None, 'json')
        }
        
        print(f"🚀 Uploading image {os.path.basename(image_path)} to freeimage.host...")
        print(f"📡 API Endpoint: https://freeimage.host/api/1/upload")
        
        # Make the request
        response = requests.post("https://freeimage.host/api/1/upload", files=files)
        
        # Print detailed response information
        print(f"\n=== Response Details ===")
        print(f"🔢 HTTP Status Code: {response.status_code}")
        print(f"📋 Response Headers:")
        for key, value in response.headers.items():
            print(f"   {key}: {value}")
        
        print(f"\n📄 Raw Response Content:")
        print(response.text)
        
        # Try to parse JSON response
        try:
            upload_result = response.json()
            print(f"\n📊 Parsed JSON Response:")
            print(json.dumps(upload_result, indent=2))
            
            # Check if upload was successful
            if upload_result.get("status_code") == 200 and upload_result.get("success"):
                image_url = upload_result["image"]["url"]
                print(f"\n✅ Upload successful!")
                print(f"🔗 Image URL: {image_url}")
                print(f"🆔 Image ID: {upload_result['image'].get('id', 'N/A')}")
                print(f"📏 Image Size: {upload_result['image'].get('size', 'N/A')} bytes")
                print(f"📐 Dimensions: {upload_result['image'].get('width', 'N/A')}x{upload_result['image'].get('height', 'N/A')}")
                
                # Test if the URL is accessible
                print(f"\n🔍 Testing image URL accessibility...")
                try:
                    url_test = requests.head(image_url, timeout=10)
                    print(f"✅ URL accessible - Status: {url_test.status_code}")
                except Exception as e:
                    print(f"❌ URL test failed: {e}")
                
                return image_url
            else:
                print(f"\n❌ Upload failed!")
                error_info = upload_result.get('error', {})
                print(f"Error message: {error_info.get('message', 'Unknown error')}")
                print(f"Error code: {error_info.get('code', 'N/A')}")
                return None
                
        except json.JSONDecodeError as e:
            print(f"\n❌ Failed to parse JSON response: {e}")
            return None
            
    except FileNotFoundError:
        print(f"❌ Error: Image file not found at {image_path}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Error uploading to freeimage.host: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text}")
        return None
    except Exception as e:
        print(f"❌ An unexpected error occurred during freeimage.host upload: {e}")
        return None

def main():
    print("🧪 Freeimage.host Upload Test Script")
    print("=" * 50)
    
    # Determine image path
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        print(f"Using specified image: {image_path}")
    else:
        print("No image path specified. Looking for first image in img/ready/...")
        image_path = find_first_image("img/ready")
        if not image_path:
            print("❌ No image files found in img/ready directory.")
            print("Usage: python3 scripts/test_freeimagehost_upload.py [image_path]")
            return
        print(f"Found image: {image_path}")
    
    # Test the upload
    result_url = test_upload_image_to_freeimagehost(image_path)
    
    if result_url:
        print(f"\n🎉 Test completed successfully!")
        print(f"📋 Summary:")
        print(f"   - Image uploaded: {os.path.basename(image_path)}")
        print(f"   - URL: {result_url}")
        print(f"   - You can verify the image by opening the URL in a browser")
    else:
        print(f"\n💥 Test failed!")
        print(f"📋 Troubleshooting tips:")
        print(f"   - Check if FREEIMAGE_API_KEY is set in .env file")
        print(f"   - Verify the image file exists and is readable")
        print(f"   - Check your internet connection")
        print(f"   - Ensure the API key is valid")

if __name__ == "__main__":
    main()
