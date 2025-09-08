#!/usr/bin/env python3
"""
Fix Image Uploading Script

This script finds ALL images with upload URLs, downloads them to a tmp folder, 
verifies their sizes, and updates the database if there are size mismatches.

Usage:
    python3 scripts/fix_image_uploading.py

Features:
- Finds ALL images with upload_url in the database
- Downloads images to tmp folder
- Compares downloaded size with database recorded size
- Updates database if sizes don't match (sets status to 'failed' and error_message to 'size not match')
- Updates database if no downloaded_size_bytes was recorded (sets actual size and status to 'success')
"""

import os
import sys
import sqlite3
import requests
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import time

# Import the image uploader
from image_uploader import FreeImageHostUploader

class ImageSizeVerifier:
    """Handles downloading and size verification of uploaded images."""
    
    def __init__(self, db_path: str = "data/llm_video_batch.db"):
        self.db_path = Path(db_path)
        self.tmp_dir = Path("tmp")
        self.tmp_dir.mkdir(exist_ok=True)
        
        # Verify database exists
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
    
    def get_recent_images_with_urls(self, limit: int = 5) -> List[Dict]:
        """Get images that have upload URLs, focusing on success status and id < 463."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        
        try:
            cursor = conn.cursor()
            query = """
                SELECT id, timestamp, original_filename, upload_url, 
                       file_size_bytes, downloaded_size_bytes, status, error_message
                FROM images 
                WHERE upload_url IS NOT NULL AND upload_url != ''
                AND status = 'success'
                AND id < 656 and id > 650
                ORDER BY id ASC 
                LIMIT ?
            """
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            
            # Convert to list of dictionaries
            images = []
            for row in rows:
                images.append({
                    'id': row['id'],
                    'timestamp': row['timestamp'],
                    'original_filename': row['original_filename'],
                    'upload_url': row['upload_url'],
                    'file_size_bytes': row['file_size_bytes'],
                    'downloaded_size_bytes': row['downloaded_size_bytes'],
                    'status': row['status'],
                    'error_message': row['error_message']
                })
            
            return images
            
        finally:
            conn.close()
    
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
                safe_filename = f"image_{int(time.time())}"
            
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
    
    def update_image_record(self, image_id: int, downloaded_size: int, status: str, error_message: Optional[str] = None):
        """Update image record in database."""
        conn = sqlite3.connect(self.db_path)
        
        try:
            cursor = conn.cursor()
            
            # Update the record
            query = """
                UPDATE images 
                SET downloaded_size_bytes = ?, 
                    status = ?, 
                    error_message = ?,
                    updated_at = datetime('now')
                WHERE id = ?
            """
            
            cursor.execute(query, (downloaded_size, status, error_message, image_id))
            conn.commit()
            
            print(f"   📝 Updated database record (ID: {image_id})")
            
        finally:
            conn.close()
    
    def verify_image_sizes(self, limit: int = None) -> Tuple[int, int, int]:
        """
        Verify sizes of uploaded images.
        
        Returns:
            Tuple of (total_checked, size_matches, size_mismatches)
        """
        if limit:
            print(f"🔍 Finding {limit} success status images with upload URLs (ID < 463)...")
        else:
            print(f"🔍 Finding ALL success status images with upload URLs (ID < 463)...")
        
        # Get images
        images = self.get_recent_images_with_urls(limit or 999999)
        
        if not images:
            print("❌ No images with upload URLs found")
            return 0, 0, 0
        
        print(f"📋 Found {len(images)} images to verify")
        print("-" * 80)
        
        total_checked = 0
        size_matches = 0
        size_mismatches = 0
        
        for i, image in enumerate(images, 1):
            print(f"\n🖼️  [{i}/{len(images)}] Processing: {image['original_filename']}")
            print(f"   🆔 ID: {image['id']}")
            print(f"   🔗 URL: {image['upload_url']}")
            # Handle None values for formatting
            original_size_str = f"{image['file_size_bytes']:,}" if image['file_size_bytes'] is not None else "Unknown"
            downloaded_size_str = f"{image['downloaded_size_bytes']:,}" if image['downloaded_size_bytes'] is not None else "None"
            
            print(f"   📊 Original size: {original_size_str} bytes")
            print(f"   📊 Recorded downloaded size: {downloaded_size_str} bytes")
            print(f"   📊 Current status: {image['status']}")
            
            total_checked += 1
            
            # Download the image
            success, actual_size, error = self.download_image(
                image['upload_url'], 
                image['original_filename']
            )
            
            if not success:
                print(f"   ❌ Download failed: {error}")
                # Update database with download failure
                self.update_image_record(
                    image['id'], 
                    image['downloaded_size_bytes'],  # Keep existing value
                    'failed', 
                    f"Download failed: {error}"
                )
                continue
            
            # Compare sizes
            recorded_size = image['downloaded_size_bytes']
            
            if recorded_size is None:
                print(f"   ⚠️  No recorded downloaded size in database")
                # Update with actual downloaded size
                self.update_image_record(
                    image['id'], 
                    actual_size, 
                    'success', 
                    None
                )
                size_matches += 1
                print(f"   ✅ Updated database with actual size: {actual_size:,} bytes")
                
            elif actual_size == recorded_size:
                print(f"   ✅ Size match! {actual_size:,} bytes")
                size_matches += 1
                
            else:
                print(f"   ❌ Size mismatch!")
                print(f"      Expected: {recorded_size:,} bytes")
                print(f"      Actual:   {actual_size:,} bytes")
                print(f"      Difference: {abs(actual_size - recorded_size):,} bytes")
                
                # Update database with size mismatch
                self.update_image_record(
                    image['id'], 
                    actual_size, 
                    'failed', 
                    'size not match'
                )
                size_mismatches += 1
        
        return total_checked, size_matches, size_mismatches
    
    def get_failed_images_with_processed_path(self, limit: int = None) -> List[Dict]:
        """Get failed images that have processed_path for re-uploading."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        
        try:
            cursor = conn.cursor()
            query = """
                SELECT id, timestamp, original_filename, processed_path, 
                       file_size_bytes, downloaded_size_bytes, status, error_message
                FROM images 
                WHERE status = 'failed' 
                AND processed_path IS NOT NULL 
                AND processed_path != ''
                ORDER BY id ASC 
                LIMIT ?
            """
            cursor.execute(query, (limit or 999999,))
            rows = cursor.fetchall()
            
            # Convert to list of dictionaries
            images = []
            for row in rows:
                images.append({
                    'id': row['id'],
                    'timestamp': row['timestamp'],
                    'original_filename': row['original_filename'],
                    'processed_path': row['processed_path'],
                    'file_size_bytes': row['file_size_bytes'],
                    'downloaded_size_bytes': row['downloaded_size_bytes'],
                    'status': row['status'],
                    'error_message': row['error_message']
                })
            
            return images
            
        finally:
            conn.close()
    
    def update_image_upload_record(self, image_id: int, upload_url: str, downloaded_size: int, status: str, error_message: Optional[str] = None):
        """Update image record with upload URL and status."""
        conn = sqlite3.connect(self.db_path)
        
        try:
            cursor = conn.cursor()
            
            # Update the record
            query = """
                UPDATE images 
                SET upload_url = ?,
                    downloaded_size_bytes = ?, 
                    status = ?, 
                    error_message = ?,
                    updated_at = datetime('now')
                WHERE id = ?
            """
            
            cursor.execute(query, (upload_url, downloaded_size, status, error_message, image_id))
            conn.commit()
            
            print(f"   📝 Updated database record (ID: {image_id}) with upload URL")
            
        finally:
            conn.close()
    
    def upload_failed_images(self, limit: int = None) -> Tuple[int, int, int]:
        """
        Upload failed images that have processed_path.
        
        Returns:
            Tuple of (total_processed, upload_success, upload_failures)
        """
        if limit:
            print(f"🔍 Finding {limit} failed images with processed_path for re-upload...")
        else:
            print(f"🔍 Finding ALL failed images with processed_path for re-upload...")
        
        # Get failed images with processed_path
        images = self.get_failed_images_with_processed_path(limit)
        
        if not images:
            print("❌ No failed images with processed_path found")
            return 0, 0, 0
        
        print(f"📋 Found {len(images)} failed images to re-upload")
        print("-" * 80)
        
        # Initialize uploader
        try:
            uploader = FreeImageHostUploader()
        except Exception as e:
            print(f"❌ Failed to initialize uploader: {e}")
            return 0, 0, len(images)
        
        total_processed = 0
        upload_success = 0
        upload_failures = 0
        
        for i, image in enumerate(images, 1):
            print(f"\n🖼️  [{i}/{len(images)}] Processing: {image['original_filename']}")
            print(f"   🆔 ID: {image['id']}")
            print(f"   📁 Processed path: {image['processed_path']}")
            print(f"   📊 Current status: {image['status']}")
            print(f"   ❌ Error: {image['error_message']}")
            
            total_processed += 1
            
            # Check if processed file exists
            processed_path = Path(image['processed_path'])
            if not processed_path.exists():
                print(f"   ❌ Processed file not found: {processed_path}")
                self.update_image_upload_record(
                    image['id'], 
                    None,  # No upload URL
                    image['downloaded_size_bytes'],  # Keep existing value
                    'failed', 
                    f"Processed file not found: {processed_path}"
                )
                upload_failures += 1
                continue
            
            # Get file size of processed image
            processed_file_size = processed_path.stat().st_size
            print(f"   📊 Processed file size: {processed_file_size:,} bytes")
            
            # Upload the image
            print(f"   📤 Uploading image...")
            upload_result = uploader.upload_image(str(processed_path))
            
            if upload_result.success:
                print(f"   ✅ Upload successful!")
                print(f"   🔗 URL: {upload_result.url}")
                print(f"   📊 Upload file size: {upload_result.file_size:,} bytes")
                print(f"   ⏱️  Upload time: {upload_result.upload_time:.2f}s")
                
                # Verify file size matches
                if upload_result.file_size == processed_file_size:
                    print(f"   ✅ File size verification passed!")
                    self.update_image_upload_record(
                        image['id'], 
                        upload_result.url,
                        upload_result.file_size,
                        'success', 
                        None
                    )
                    upload_success += 1
                else:
                    print(f"   ❌ File size mismatch!")
                    print(f"      Expected: {processed_file_size:,} bytes")
                    print(f"      Uploaded: {upload_result.file_size:,} bytes")
                    self.update_image_upload_record(
                        image['id'], 
                        upload_result.url,
                        upload_result.file_size,
                        'failed', 
                        f"Size mismatch: expected {processed_file_size}, got {upload_result.file_size}"
                    )
                    upload_failures += 1
            else:
                print(f"   ❌ Upload failed: {upload_result.error}")
                self.update_image_upload_record(
                    image['id'], 
                    None,  # No upload URL
                    image['downloaded_size_bytes'],  # Keep existing value
                    'failed', 
                    f"Upload failed: {upload_result.error}"
                )
                upload_failures += 1
        
        return total_processed, upload_success, upload_failures
    
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
    import argparse
    
    parser = argparse.ArgumentParser(description='Image Upload Fix Tool')
    parser.add_argument('--mode', choices=['verify', 'upload'], default='verify',
                       help='Mode: verify (check sizes) or upload (re-upload failed images)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of images to process')
    
    args = parser.parse_args()
    
    if args.mode == 'verify':
        print("🚀 Image Size Verification Tool")
    else:
        print("🚀 Failed Image Re-upload Tool")
    
    print("=" * 80)
    
    try:
        # Create verifier instance
        verifier = ImageSizeVerifier()
        
        if args.mode == 'verify':
            # Verify image sizes
            total, matches, mismatches = verifier.verify_image_sizes(limit=args.limit)
            
            # Print summary
            print("\n" + "=" * 80)
            print("📊 VERIFICATION SUMMARY")
            print("=" * 80)
            print(f"🔍 Total images checked: {total}")
            print(f"✅ Size matches: {matches}")
            print(f"❌ Size mismatches: {mismatches}")
            
            if total > 0:
                match_rate = (matches / total) * 100
                print(f"📈 Match rate: {match_rate:.1f}%")
            
            # Exit with appropriate code
            if mismatches == 0:
                print("\n🎉 All image sizes verified successfully!")
                exit_code = 0
            else:
                print(f"\n⚠️  Found {mismatches} size mismatches - database updated")
                exit_code = 1
        
        else:  # upload mode
            # Upload failed images
            total, success, failures = verifier.upload_failed_images(limit=args.limit)
            
            # Print summary
            print("\n" + "=" * 80)
            print("📊 UPLOAD SUMMARY")
            print("=" * 80)
            print(f"🔍 Total images processed: {total}")
            print(f"✅ Upload successes: {success}")
            print(f"❌ Upload failures: {failures}")
            
            if total > 0:
                success_rate = (success / total) * 100
                print(f"📈 Success rate: {success_rate:.1f}%")
            
            # Exit with appropriate code
            if failures == 0:
                print("\n🎉 All failed images uploaded successfully!")
                exit_code = 0
            else:
                print(f"\n⚠️  Found {failures} upload failures - database updated")
                exit_code = 1
        
        # Clean up temporary files
        print(f"\n🧹 Cleaning up temporary files...")
        verifier.cleanup_tmp_files()
        
        sys.exit(exit_code)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Operation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
