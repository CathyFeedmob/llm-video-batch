#!/usr/bin/env python3
"""
Base Image Uploader Model

This module provides a base class for image uploading services and a specific
implementation for freeimagehost.com. It includes error handling, retry logic,
and logging capabilities.

Usage:
    from image_uploader import FreeImageHostUploader
    
    uploader = FreeImageHostUploader()
    result = uploader.upload_image("path/to/image.jpg")
    if result.success:
        print(f"Image uploaded: {result.url}")
    else:
        print(f"Upload failed: {result.error}")
"""

import os
import requests
import time
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod
import mimetypes
from dotenv import load_dotenv

load_dotenv()

@dataclass
class UploadResult:
    """Result of an image upload operation."""
    success: bool
    url: Optional[str] = None
    error: Optional[str] = None
    response_data: Optional[Dict[Any, Any]] = None
    upload_time: Optional[float] = None
    file_size: Optional[int] = None
    image_id: Optional[str] = None

class BaseImageUploader(ABC):
    """Abstract base class for image uploaders."""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    @abstractmethod
    def _upload_single(self, image_path: str) -> UploadResult:
        """Upload a single image. Must be implemented by subclasses."""
        pass
    
    def upload_image(self, image_path: str) -> UploadResult:
        """
        Upload an image with retry logic.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            UploadResult object with success status and details
        """
        if not os.path.exists(image_path):
            return UploadResult(
                success=False,
                error=f"Image file not found: {image_path}"
            )
        
        # Validate file type
        if not self._is_valid_image(image_path):
            return UploadResult(
                success=False,
                error=f"Invalid image file type: {image_path}"
            )
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                result = self._upload_single(image_path)
                if result.success:
                    return result
                last_error = result.error
                
                if attempt < self.max_retries - 1:
                    print(f"Upload attempt {attempt + 1} failed: {result.error}. Retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                    
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    print(f"Upload attempt {attempt + 1} failed with exception: {e}. Retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
        
        return UploadResult(
            success=False,
            error=f"Upload failed after {self.max_retries} attempts. Last error: {last_error}"
        )
    
    def _is_valid_image(self, image_path: str) -> bool:
        """Check if the file is a valid image."""
        valid_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        return Path(image_path).suffix.lower() in valid_extensions
    
    def _get_file_size(self, image_path: str) -> int:
        """Get file size in bytes."""
        return os.path.getsize(image_path)
    
    def _get_mime_type(self, image_path: str) -> str:
        """Get MIME type for the image."""
        mime_type, _ = mimetypes.guess_type(image_path)
        if mime_type and mime_type.startswith('image/'):
            return mime_type
        
        # Fallback based on extension
        ext = Path(image_path).suffix.lower()
        mime_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp'
        }
        return mime_map.get(ext, 'image/jpeg')

class FreeImageHostUploader(BaseImageUploader):
    """Image uploader for freeimage.host service."""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key or os.getenv("FREEIMAGE_API_KEY")
        self.api_url = "https://freeimage.host/api/1/upload"
        
        if not self.api_key:
            raise ValueError("FREEIMAGE_API_KEY environment variable not set or api_key not provided")
    
    def _upload_single(self, image_path: str) -> UploadResult:
        """Upload a single image to freeimage.host."""
        start_time = time.time()
        
        try:
            # Read image file
            with open(image_path, "rb") as f:
                image_data = f.read()
            
            file_size = len(image_data)
            mime_type = self._get_mime_type(image_path)
            
            # Prepare files for upload
            files = {
                'source': (os.path.basename(image_path), image_data, mime_type),
                'key': (None, self.api_key),
                'format': (None, 'json')
            }
            
            # Make the request
            response = requests.post(self.api_url, files=files, timeout=30)
            upload_time = time.time() - start_time
            
            # Parse response
            try:
                upload_result = response.json()
            except ValueError:
                return UploadResult(
                    success=False,
                    error=f"Invalid JSON response: {response.text}",
                    upload_time=upload_time,
                    file_size=file_size
                )
            
            # Check if upload was successful
            if upload_result.get("status_code") == 200 and upload_result.get("success"):
                image_url = upload_result["image"]["url"]
                image_id = upload_result["image"].get("id")
                
                return UploadResult(
                    success=True,
                    url=image_url,
                    response_data=upload_result,
                    upload_time=upload_time,
                    file_size=file_size,
                    image_id=image_id
                )
            else:
                error_info = upload_result.get('error', {})
                error_message = error_info.get('message', 'Unknown error')
                error_code = error_info.get('code', 'N/A')
                
                return UploadResult(
                    success=False,
                    error=f"Upload failed: {error_message} (Code: {error_code})",
                    response_data=upload_result,
                    upload_time=upload_time,
                    file_size=file_size
                )
                
        except requests.exceptions.Timeout:
            return UploadResult(
                success=False,
                error="Upload timeout (30s)",
                upload_time=time.time() - start_time,
                file_size=self._get_file_size(image_path)
            )
        except requests.exceptions.RequestException as e:
            return UploadResult(
                success=False,
                error=f"Network error: {str(e)}",
                upload_time=time.time() - start_time,
                file_size=self._get_file_size(image_path)
            )
        except Exception as e:
            return UploadResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
                upload_time=time.time() - start_time,
                file_size=self._get_file_size(image_path) if os.path.exists(image_path) else None
            )

# Factory function for easy instantiation
def create_uploader(service: str = "freeimagehost", **kwargs) -> BaseImageUploader:
    """
    Factory function to create an uploader instance.
    
    Args:
        service: The upload service to use ("freeimagehost")
        **kwargs: Additional arguments passed to the uploader
        
    Returns:
        BaseImageUploader instance
    """
    if service.lower() == "freeimagehost":
        return FreeImageHostUploader(**kwargs)
    else:
        raise ValueError(f"Unsupported upload service: {service}")

if __name__ == "__main__":
    # Simple test
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 image_uploader.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    uploader = FreeImageHostUploader()
    result = uploader.upload_image(image_path)
    
    if result.success:
        print(f"✅ Upload successful!")
        print(f"URL: {result.url}")
        print(f"Upload time: {result.upload_time:.2f}s")
        print(f"File size: {result.file_size} bytes")
    else:
        print(f"❌ Upload failed: {result.error}")
