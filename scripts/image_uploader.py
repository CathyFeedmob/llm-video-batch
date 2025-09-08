#!/usr/bin/env python3
"""
Enhanced Image Uploader Module

This module provides a base class for image uploading services with implementations
for both freeimagehost.com and ImageKit.io. It includes error handling, retry logic,
and comprehensive logging capabilities.

Usage:
    from image_uploader import create_uploader
    
    # Use FreeImageHost
    uploader = create_uploader("freeimagehost")
    
    # Use ImageKit
    uploader = create_uploader("imagekit")
    
    result = uploader.upload_image("path/to/image.jpg")
    if result.success:
        print(f"Image uploaded: {result.url}")
    else:
        print(f"Upload failed: {result.error}")
"""

import os
import requests
import time
import base64
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import mimetypes
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

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
    thumbnail_url: Optional[str] = None
    file_path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    tags: Optional[List[str]] = field(default_factory=list)
    is_private: Optional[bool] = False

class BaseImageUploader(ABC):
    """Abstract base class for image uploaders."""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    @abstractmethod
    def _upload_single(self, image_path: str, **kwargs) -> UploadResult:
        """Upload a single image. Must be implemented by subclasses."""
        pass
    
    def upload_image(self, image_path: str, **kwargs) -> UploadResult:
        """
        Upload an image with retry logic.
        
        Args:
            image_path: Path to the image file
            **kwargs: Additional parameters for specific uploaders
            
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
                result = self._upload_single(image_path, **kwargs)
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
        valid_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff'}
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
            '.webp': 'image/webp',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon',
            '.tiff': 'image/tiff'
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
    
    def _upload_single(self, image_path: str, **kwargs) -> UploadResult:
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

class ImageKitUploader(BaseImageUploader):
    """Image uploader for ImageKit.io service."""
    
    def __init__(self, 
                 private_key: Optional[str] = None,
                 public_key: Optional[str] = None,
                 url_endpoint: Optional[str] = None,
                 **kwargs):
        super().__init__(**kwargs)
        
        # Load credentials from environment or parameters
        self.private_key = private_key or os.getenv("IMAGEKIT_PRIVATE_KEY", 
                                                    "private_5Ji8+7B4RNbsgUXdQ0Kj7H3P4yQ=")
        self.public_key = public_key or os.getenv("IMAGEKIT_PUBLIC_KEY",
                                                  "public_OIIGftQX0WI1J3Fj9YWxndpuZ1w=")
        self.url_endpoint = url_endpoint or os.getenv("IMAGEKIT_URL_ENDPOINT",
                                                      "https://ik.imagekit.io/ozpin2055")
        
        self.api_url = "https://upload.imagekit.io/api/v1/files/upload"
        
        if not self.private_key:
            raise ValueError("IMAGEKIT_PRIVATE_KEY not set or private_key not provided")
    
    def _upload_single(self, image_path: str, **kwargs) -> UploadResult:
        """
        Upload a single image to ImageKit.io.
        
        Additional kwargs:
            folder: Folder path to upload the file to
            tags: Comma-separated tags to associate with the file
            is_private_file: Mark file as private (default: False)
            use_unique_file_name: Add unique suffix to filename (default: True)
            custom_coordinates: Custom crop coordinates (x,y,width,height)
            response_fields: Extra fields to include in response
            overwrite_file: Overwrite existing file (default: True)
            description: Description of the file
        """
        start_time = time.time()
        
        try:
            # Read image file
            with open(image_path, "rb") as f:
                image_data = f.read()
            
            file_size = len(image_data)
            filename = os.path.basename(image_path)
            
            # Prepare multipart form data
            files = {
                'file': (filename, image_data, self._get_mime_type(image_path))
            }
            
            # Prepare form data with required fields
            data = {
                'fileName': filename,
                'useUniqueFileName': str(kwargs.get('use_unique_file_name', 'true')).lower(),
            }
            
            # Add optional fields if provided
            if 'folder' in kwargs:
                data['folder'] = kwargs['folder']
            if 'tags' in kwargs:
                if isinstance(kwargs['tags'], list):
                    data['tags'] = ','.join(kwargs['tags'])
                else:
                    data['tags'] = kwargs['tags']
            if 'is_private_file' in kwargs:
                data['isPrivateFile'] = str(kwargs['is_private_file']).lower()
            if 'custom_coordinates' in kwargs:
                data['customCoordinates'] = kwargs['custom_coordinates']
            if 'response_fields' in kwargs:
                data['responseFields'] = kwargs['response_fields']
            if 'overwrite_file' in kwargs:
                data['overwriteFile'] = str(kwargs['overwrite_file']).lower()
            if 'description' in kwargs:
                data['description'] = kwargs['description']
            
            # Make the request with Basic Authentication
            auth = HTTPBasicAuth(self.private_key, '')
            response = requests.post(
                self.api_url,
                files=files,
                data=data,
                auth=auth,
                timeout=60
            )
            upload_time = time.time() - start_time
            
            # Parse response
            try:
                result_data = response.json()
            except ValueError:
                return UploadResult(
                    success=False,
                    error=f"Invalid JSON response: {response.text}",
                    upload_time=upload_time,
                    file_size=file_size
                )
            
            # Check response status
            if response.status_code == 200:
                return UploadResult(
                    success=True,
                    url=result_data.get('url'),
                    image_id=result_data.get('fileId'),
                    thumbnail_url=result_data.get('thumbnailUrl'),
                    file_path=result_data.get('filePath'),
                    width=result_data.get('width'),
                    height=result_data.get('height'),
                    tags=result_data.get('tags', []),
                    is_private=result_data.get('isPrivateFile', False),
                    response_data=result_data,
                    upload_time=upload_time,
                    file_size=file_size
                )
            elif response.status_code == 202:
                # File accepted and queued for processing
                return UploadResult(
                    success=True,
                    url="Processing queued",
                    error="File is being processed. Check back later.",
                    response_data=result_data,
                    upload_time=upload_time,
                    file_size=file_size
                )
            else:
                error_message = result_data.get('message', 'Unknown error')
                return UploadResult(
                    success=False,
                    error=f"Upload failed ({response.status_code}): {error_message}",
                    response_data=result_data,
                    upload_time=upload_time,
                    file_size=file_size
                )
                
        except requests.exceptions.Timeout:
            return UploadResult(
                success=False,
                error="Upload timeout (60s)",
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
def create_uploader(service: str = "imagekit", **kwargs) -> BaseImageUploader:
    """
    Factory function to create an uploader instance.
    
    Args:
        service: The upload service to use ("freeimagehost" or "imagekit")
        **kwargs: Additional arguments passed to the uploader
        
    Returns:
        BaseImageUploader instance
        
    Examples:
        # Create ImageKit uploader with default credentials from env
        uploader = create_uploader("imagekit")
        
        # Create ImageKit uploader with custom credentials
        uploader = create_uploader(
            "imagekit",
            private_key="your_private_key",
            public_key="your_public_key",
            url_endpoint="your_endpoint"
        )
        
        # Upload with options
        result = uploader.upload_image(
            "image.jpg",
            folder="/uploads/2024",
            tags=["product", "thumbnail"],
            is_private_file=False
        )
    """
    service_lower = service.lower()
    
    if service_lower in ["freeimagehost", "freeimage"]:
        return FreeImageHostUploader(**kwargs)
    elif service_lower in ["imagekit", "imagekit.io"]:
        return ImageKitUploader(**kwargs)
    else:
        raise ValueError(f"Unsupported upload service: {service}. Supported: 'freeimagehost', 'imagekit'")

def batch_upload(uploader: BaseImageUploader, 
                 image_paths: List[str], 
                 **kwargs) -> List[UploadResult]:
    """
    Upload multiple images using the specified uploader.
    
    Args:
        uploader: The uploader instance to use
        image_paths: List of image file paths
        **kwargs: Additional parameters passed to each upload
        
    Returns:
        List of UploadResult objects
    """
    results = []
    total = len(image_paths)
    
    for i, path in enumerate(image_paths, 1):
        print(f"Uploading {i}/{total}: {path}")
        result = uploader.upload_image(path, **kwargs)
        results.append(result)
        
        if result.success:
            print(f"  ✅ Success: {result.url}")
        else:
            print(f"  ❌ Failed: {result.error}")
    
    return results

if __name__ == "__main__":
    # Enhanced command-line interface
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Upload images to various services")
    parser.add_argument("image_path", help="Path to the image file")
    parser.add_argument(
        "--service", 
        default="imagekit",
        choices=["imagekit", "freeimagehost"],
        help="Upload service to use (default: imagekit)"
    )
    parser.add_argument("--folder", help="Folder path for ImageKit uploads")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument("--private", action="store_true", help="Mark as private file")
    parser.add_argument("--no-unique", action="store_true", help="Don't use unique filename")
    parser.add_argument("--description", help="File description")
    
    args = parser.parse_args()
    
    # Prepare kwargs for upload
    upload_kwargs = {}
    if args.folder:
        upload_kwargs['folder'] = args.folder
    if args.tags:
        upload_kwargs['tags'] = args.tags
    if args.private:
        upload_kwargs['is_private_file'] = True
    if args.no_unique:
        upload_kwargs['use_unique_file_name'] = False
    if args.description:
        upload_kwargs['description'] = args.description
    
    try:
        # Create uploader
        uploader = create_uploader(args.service)
        
        # Upload image
        print(f"Uploading to {args.service}...")
        result = uploader.upload_image(args.image_path, **upload_kwargs)
        
        if result.success:
            print(f"✅ Upload successful!")
            print(f"URL: {result.url}")
            if result.thumbnail_url:
                print(f"Thumbnail: {result.thumbnail_url}")
            if result.file_path:
                print(f"File path: {result.file_path}")
            print(f"Upload time: {result.upload_time:.2f}s")
            print(f"File size: {result.file_size} bytes")
            if result.width and result.height:
                print(f"Dimensions: {result.width}x{result.height}")
            if result.tags:
                print(f"Tags: {', '.join(result.tags)}")
        else:
            print(f"❌ Upload failed: {result.error}")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)