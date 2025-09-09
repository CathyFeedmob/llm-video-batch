#!/usr/bin/env python3
"""
JSON Image Checker Script

This script checks JSON files in out/prompt_json/, downloads images via image_url,
and moves JSON files with failed downloads to a failed_json folder.

Usage:
    python3 scripts/check_json_images.py
    python3 scripts/check_json_images.py --limit 10

Features:
- Scans all JSON files in out/prompt_json/ directory
- Downloads images from image_url field in each JSON
- Moves JSON files to failed_json/ folder if download fails
- Provides detailed logging and progress tracking
- Handles network errors and missing URLs gracefully
"""

import os
import sys
import json
import requests
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import time
import argparse

class JSONImageChecker:
    """Handles checking JSON files and downloading their associated images."""
    
    def __init__(self, json_dir: str = "out/prompt_json", failed_dir: str = "out/failed_json"):
        self.json_dir = Path(json_dir)
        self.failed_dir = Path(failed_dir)
        self.tmp_dir = Path("tmp")
        
        # Create directories if they don't exist
        self.failed_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(exist_ok=True)
        
        # Verify JSON directory exists
        if not self.json_dir.exists():
            raise FileNotFoundError(f"JSON directory not found: {self.json_dir}")
    
    def get_json_files(self, limit: int = None) -> List[Path]:
        """Get list of JSON files to process."""
        json_files = []
        
        # Get all .json files in the directory
        for file_path in self.json_dir.glob("*.json"):
            if file_path.is_file():
                json_files.append(file_path)
        
        # Sort by name for consistent processing order
        json_files.sort()
        
        # Apply limit if specified
        if limit:
            json_files = json_files[:limit]
        
        return json_files
    
    def load_json_file(self, json_path: Path) -> Optional[Dict]:
        """Load and parse a JSON file."""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except json.JSONDecodeError as e:
            print(f"   ❌ Invalid JSON format: {e}")
            return None
        except Exception as e:
            print(f"   ❌ Error reading file: {e}")
            return None
    
    def download_image(self, url: str, filename: str) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Download an image from URL to tmp folder.
        
        Returns:
            Tuple of (success, file_size_bytes, error_message)
        """
        try:
            # Create safe filename
            safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
            if not safe_filename:
                safe_filename = f"image_{int(time.time())}.png"
            
            file_path = self.tmp_dir / safe_filename
            
            print(f"   📥 Downloading to: {file_path}")
            
            # Download with timeout and proper headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()
            
            # Write file in chunks
            total_size = 0
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_size += len(chunk)
            
            # Verify file was written
            actual_size = file_path.stat().st_size
            if actual_size != total_size:
                return False, None, f"File size mismatch during download: expected {total_size}, got {actual_size}"
            
            print(f"   ✅ Downloaded successfully: {actual_size:,} bytes")
            return True, actual_size, None
            
        except requests.exceptions.Timeout:
            return False, None, "Download timeout (30s)"
        except requests.exceptions.RequestException as e:
            return False, None, f"Network error: {str(e)}"
        except Exception as e:
            return False, None, f"Unexpected error: {str(e)}"
    
    def move_to_failed(self, json_path: Path, error_message: str) -> bool:
        """Move a JSON file to the failed_json directory."""
        try:
            failed_path = self.failed_dir / json_path.name
            
            # If file already exists in failed directory, add timestamp
            if failed_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                name_parts = json_path.stem, timestamp, json_path.suffix
                failed_path = self.failed_dir / f"{name_parts[0]}_{name_parts[1]}{name_parts[2]}"
            
            shutil.move(str(json_path), str(failed_path))
            print(f"   📁 Moved to failed directory: {failed_path.name}")
            
            # Create error log file alongside the JSON
            error_log_path = failed_path.with_suffix('.error.txt')
            with open(error_log_path, 'w', encoding='utf-8') as f:
                f.write(f"Error: {error_message}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            
            return True
            
        except Exception as e:
            print(f"   ⚠️  Failed to move file to failed directory: {e}")
            return False
    
    def check_json_images(self, limit: int = None) -> Tuple[int, int, int]:
        """
        Check JSON files and download their images.
        
        Returns:
            Tuple of (total_processed, download_success, download_failures)
        """
        if limit:
            print(f"🔍 Finding {limit} JSON files to check...")
        else:
            print(f"🔍 Finding ALL JSON files to check...")
        
        # Get JSON files
        json_files = self.get_json_files(limit)
        
        if not json_files:
            print("❌ No JSON files found")
            return 0, 0, 0
        
        print(f"📋 Found {len(json_files)} JSON files to process")
        print("-" * 80)
        
        total_processed = 0
        download_success = 0
        download_failures = 0
        
        for i, json_path in enumerate(json_files, 1):
            print(f"\n📄 [{i}/{len(json_files)}] Processing: {json_path.name}")
            
            total_processed += 1
            
            # Load JSON file
            json_data = self.load_json_file(json_path)
            if json_data is None:
                print(f"   ❌ Failed to load JSON file")
                if self.move_to_failed(json_path, "Invalid JSON format"):
                    download_failures += 1
                continue
            
            # Check for image_url field
            image_url = json_data.get('image_url')
            if not image_url:
                print(f"   ❌ No image_url field found in JSON")
                if self.move_to_failed(json_path, "Missing image_url field"):
                    download_failures += 1
                continue
            
            print(f"   🔗 Image URL: {image_url}")
            
            # Get expected filename from JSON
            pic_name = json_data.get('pic_name', f"image_{int(time.time())}.png")
            print(f"   📷 Expected filename: {pic_name}")
            
            # Try to download the image
            success, file_size, error = self.download_image(image_url, pic_name)
            
            if success:
                print(f"   ✅ Download successful: {file_size:,} bytes")
                download_success += 1
                
                # Optionally verify image size matches JSON
                json_size = json_data.get('image_size', '')
                if json_size:
                    print(f"   📊 JSON reported size: {json_size}")
                
            else:
                print(f"   ❌ Download failed: {error}")
                if self.move_to_failed(json_path, f"Download failed: {error}"):
                    download_failures += 1
        
        return total_processed, download_success, download_failures
    
    def cleanup_tmp_files(self):
        """Clean up downloaded temporary files."""
        try:
            for file_path in self.tmp_dir.glob("*"):
                if file_path.is_file():
                    file_path.unlink()
                    print(f"🗑️  Cleaned up: {file_path.name}")
        except Exception as e:
            print(f"⚠️  Warning: Could not clean up tmp files: {e}")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='JSON Image Checker Tool')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of JSON files to process')
    parser.add_argument('--json-dir', default='out/prompt_json',
                       help='Directory containing JSON files (default: out/prompt_json)')
    parser.add_argument('--failed-dir', default='out/failed_json',
                       help='Directory for failed JSON files (default: out/failed_json)')
    
    args = parser.parse_args()
    
    print("🚀 JSON Image Checker Tool")
    print("=" * 80)
    
    try:
        # Create checker instance
        checker = JSONImageChecker(json_dir=args.json_dir, failed_dir=args.failed_dir)
        
        # Check JSON files and download images
        total, success, failures = checker.check_json_images(limit=args.limit)
        
        # Print summary
        print("\n" + "=" * 80)
        print("📊 PROCESSING SUMMARY")
        print("=" * 80)
        print(f"📄 Total JSON files processed: {total}")
        print(f"✅ Download successes: {success}")
        print(f"❌ Download failures (moved to failed_json): {failures}")
        
        if total > 0:
            success_rate = (success / total) * 100
            print(f"📈 Success rate: {success_rate:.1f}%")
        
        # Clean up temporary files
        print(f"\n🧹 Cleaning up temporary files...")
        checker.cleanup_tmp_files()
        
        # Exit with appropriate code
        if failures == 0:
            print("\n🎉 All JSON images downloaded successfully!")
            sys.exit(0)
        else:
            print(f"\n⚠️  Found {failures} download failures - JSON files moved to failed_json/")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Processing interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
