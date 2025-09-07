#!/usr/bin/env python3
"""
Batch Image Upload Script

This script uploads multiple images from img/ready directory to freeimagehost
and generates a CSV log with local image names and uploaded URLs.

Usage:
  python3 scripts/batch_image_upload.py [--count N] [--output CSV_FILE] [--move-uploaded]

Options:
  --count N           Number of images to upload (default: 10, max: 20)
  --output CSV_FILE   Output CSV file path (default: logs/image_uploads.csv)
  --move-uploaded     Move successfully uploaded images to img/generated
  --dry-run          Show what would be uploaded without actually uploading
  --resume           Resume from existing CSV log (skip already uploaded images)

Features:
- Uploads 10-20 images from img/ready directory
- Generates CSV log with local filename and uploaded URL
- Error handling with retry logic (handles ~1 in 10 failure rate)
- Progress tracking and detailed logging
- Option to move uploaded images to img/generated
- Resume capability to continue interrupted uploads
"""

import os
import csv
import sys
import argparse
import time
from pathlib import Path
from datetime import datetime
from typing import List, Set, Tuple, Optional
import shutil

# Import our custom image uploader
from image_uploader import FreeImageHostUploader, UploadResult

class BatchImageUploader:
    """Handles batch uploading of images with CSV logging."""
    
    def __init__(self, 
                 source_dir: str = "img/ready",
                 output_csv: str = "logs/image_uploads.csv",
                 move_uploaded: bool = False,
                 max_retries: int = 3):
        self.source_dir = Path(source_dir)
        self.output_csv = Path(output_csv)
        self.move_uploaded = move_uploaded
        self.generated_dir = Path("img/generated")
        
        # Ensure directories exist
        self.output_csv.parent.mkdir(parents=True, exist_ok=True)
        if self.move_uploaded:
            self.generated_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize uploader with retry logic
        self.uploader = FreeImageHostUploader(max_retries=max_retries, retry_delay=2.0)
        
        # CSV headers
        self.csv_headers = [
            'timestamp',
            'local_filename',
            'file_size_bytes',
            'upload_status',
            'image_url',
            'image_id',
            'upload_time_seconds',
            'error_message',
            'attempt_number'
        ]
    
    def get_image_files(self, count: int) -> List[Path]:
        """Get list of image files to upload."""
        if not self.source_dir.exists():
            print(f"❌ Source directory {self.source_dir} does not exist")
            return []
        
        # Supported image extensions
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        
        # Find all image files
        image_files = []
        for file_path in self.source_dir.iterdir():
            if (file_path.is_file() and 
                file_path.suffix.lower() in image_extensions and
                not file_path.name.lower().startswith('error_message')):
                image_files.append(file_path)
        
        # Sort by modification time (oldest first) for consistent ordering
        image_files.sort(key=lambda x: x.stat().st_mtime)
        
        # Limit to requested count
        return image_files[:count]
    
    def get_already_uploaded(self) -> Set[str]:
        """Get set of filenames that have already been successfully uploaded."""
        uploaded = set()
        
        if not self.output_csv.exists():
            return uploaded
        
        try:
            with open(self.output_csv, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    if row.get('upload_status') == 'success':
                        uploaded.add(row.get('local_filename', ''))
        except Exception as e:
            print(f"⚠️ Warning: Could not read existing CSV file: {e}")
        
        return uploaded
    
    def write_csv_header(self):
        """Write CSV header if file doesn't exist."""
        if not self.output_csv.exists():
            with open(self.output_csv, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.csv_headers)
                writer.writeheader()
    
    def log_upload_result(self, 
                         filename: str, 
                         file_size: int,
                         result: UploadResult, 
                         attempt_number: int):
        """Log upload result to CSV file."""
        timestamp = datetime.now().isoformat()
        
        row_data = {
            'timestamp': timestamp,
            'local_filename': filename,
            'file_size_bytes': file_size,
            'upload_status': 'success' if result.success else 'failure',
            'image_url': result.url or '',
            'image_id': result.image_id or '',
            'upload_time_seconds': f"{result.upload_time:.2f}" if result.upload_time else '',
            'error_message': result.error or '',
            'attempt_number': attempt_number
        }
        
        # Append to CSV file
        with open(self.output_csv, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.csv_headers)
            writer.writerow(row_data)
    
    def move_uploaded_image(self, image_path: Path) -> bool:
        """Move successfully uploaded image to generated directory."""
        if not self.move_uploaded:
            return True
        
        try:
            destination = self.generated_dir / image_path.name
            shutil.move(str(image_path), str(destination))
            print(f"📁 Moved {image_path.name} to {self.generated_dir}")
            return True
        except Exception as e:
            print(f"⚠️ Warning: Could not move {image_path.name}: {e}")
            return False
    
    def upload_batch(self, 
                    count: int, 
                    resume: bool = False, 
                    dry_run: bool = False) -> Tuple[int, int]:
        """
        Upload a batch of images.
        
        Returns:
            Tuple of (successful_uploads, total_attempts)
        """
        print(f"🚀 Starting batch upload of up to {count} images")
        print(f"📂 Source directory: {self.source_dir}")
        print(f"📊 Output CSV: {self.output_csv}")
        print(f"🔄 Resume mode: {'ON' if resume else 'OFF'}")
        print(f"🧪 Dry run mode: {'ON' if dry_run else 'OFF'}")
        print("-" * 60)
        
        # Get list of images to upload
        image_files = self.get_image_files(count)
        
        if not image_files:
            print("❌ No image files found to upload")
            return 0, 0
        
        print(f"📋 Found {len(image_files)} image files")
        
        # Filter out already uploaded files if resuming
        already_uploaded = set()
        if resume:
            already_uploaded = self.get_already_uploaded()
            if already_uploaded:
                print(f"⏭️ Skipping {len(already_uploaded)} already uploaded images")
                image_files = [f for f in image_files if f.name not in already_uploaded]
        
        if not image_files:
            print("✅ All images have already been uploaded")
            return 0, 0
        
        print(f"📤 Will upload {len(image_files)} images")
        
        if dry_run:
            print("\n🧪 DRY RUN - Images that would be uploaded:")
            for i, image_file in enumerate(image_files, 1):
                file_size = image_file.stat().st_size
                print(f"  {i:2d}. {image_file.name} ({file_size:,} bytes)")
            return 0, len(image_files)
        
        # Initialize CSV file
        self.write_csv_header()
        
        successful_uploads = 0
        total_attempts = 0
        
        # Upload each image
        for i, image_file in enumerate(image_files, 1):
            print(f"\n📤 [{i}/{len(image_files)}] Uploading: {image_file.name}")
            
            file_size = image_file.stat().st_size
            print(f"   📏 File size: {file_size:,} bytes")
            
            total_attempts += 1
            
            # Upload the image
            start_time = time.time()
            result = self.uploader.upload_image(str(image_file))
            
            # Log the result
            self.log_upload_result(image_file.name, file_size, result, total_attempts)
            
            if result.success:
                successful_uploads += 1
                print(f"   ✅ Success! URL: {result.url}")
                print(f"   ⏱️ Upload time: {result.upload_time:.2f}s")
                
                # Move file if requested
                self.move_uploaded_image(image_file)
                
            else:
                print(f"   ❌ Failed: {result.error}")
            
            # Add small delay between uploads to be respectful to the service
            if i < len(image_files):
                time.sleep(1)
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 BATCH UPLOAD SUMMARY")
        print("=" * 60)
        print(f"✅ Successful uploads: {successful_uploads}")
        print(f"❌ Failed uploads: {total_attempts - successful_uploads}")
        print(f"📈 Success rate: {(successful_uploads/total_attempts)*100:.1f}%")
        print(f"📄 Results logged to: {self.output_csv}")
        
        if already_uploaded:
            print(f"⏭️ Previously uploaded: {len(already_uploaded)}")
        
        return successful_uploads, total_attempts

def main():
    parser = argparse.ArgumentParser(
        description="Batch upload images from img/ready to freeimagehost",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/batch_image_upload.py                    # Upload 10 images
  python3 scripts/batch_image_upload.py --count 15         # Upload 15 images
  python3 scripts/batch_image_upload.py --move-uploaded    # Move uploaded images
  python3 scripts/batch_image_upload.py --resume           # Resume interrupted upload
  python3 scripts/batch_image_upload.py --dry-run          # Preview what would be uploaded
        """
    )
    
    parser.add_argument(
        '--count', 
        type=int, 
        default=10, 
        help='Number of images to upload (default: 10, max: 20)'
    )
    
    parser.add_argument(
        '--output', 
        type=str, 
        default='logs/image_uploads.csv',
        help='Output CSV file path (default: logs/image_uploads.csv)'
    )
    
    parser.add_argument(
        '--move-uploaded', 
        action='store_true',
        help='Move successfully uploaded images to img/generated'
    )
    
    parser.add_argument(
        '--dry-run', 
        action='store_true',
        help='Show what would be uploaded without actually uploading'
    )
    
    parser.add_argument(
        '--resume', 
        action='store_true',
        help='Resume from existing CSV log (skip already uploaded images)'
    )
    
    parser.add_argument(
        '--source-dir',
        type=str,
        default='img/ready',
        help='Source directory for images (default: img/ready)'
    )
    
    args = parser.parse_args()
    
    # Validate count
    if args.count < 1:
        print("❌ Error: Count must be at least 1")
        sys.exit(1)
    
    if args.count > 20:
        print("❌ Error: Count cannot exceed 20")
        sys.exit(1)
    
    # Check if API key is available
    if not args.dry_run and not os.getenv("FREEIMAGE_API_KEY"):
        print("❌ Error: FREEIMAGE_API_KEY environment variable not set")
        print("Please set your API key in the .env file")
        sys.exit(1)
    
    try:
        # Create uploader instance
        uploader = BatchImageUploader(
            source_dir=args.source_dir,
            output_csv=args.output,
            move_uploaded=args.move_uploaded
        )
        
        # Run batch upload
        successful, total = uploader.upload_batch(
            count=args.count,
            resume=args.resume,
            dry_run=args.dry_run
        )
        
        # Exit with appropriate code
        if args.dry_run:
            sys.exit(0)
        elif successful == total:
            print("\n🎉 All uploads completed successfully!")
            sys.exit(0)
        elif successful > 0:
            print(f"\n⚠️ Partial success: {successful}/{total} uploads completed")
            sys.exit(1)
        else:
            print("\n💥 All uploads failed")
            sys.exit(2)
            
    except KeyboardInterrupt:
        print("\n\n⏹️ Upload interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
