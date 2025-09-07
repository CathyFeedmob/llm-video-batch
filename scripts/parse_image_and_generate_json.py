#!/usr/bin/env python3
"""
Parse Image and Generate JSON Function

This module provides functionality to:
1. Find images under img/ready
2. Upload images using freeimage host uploader
3. Keep upload records in logs/image_uploading.csv
4. Download uploaded images to img/uploaded using wget
5. Use OpenRouter to generate JSON based on image URL
6. Rename uploaded image files to match JSON file names

Usage:
    from parse_image_and_generate_json import parse_image_and_generate_json
    
    result = parse_image_and_generate_json()
    print(f"Processed {len(result)} images")
"""

import os
import csv
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import requests
from urllib.parse import urlparse
import re

# Import existing modules
from openrouter_base import OpenRouterClient
from image_uploader import FreeImageHostUploader

@dataclass
class ProcessingResult:
    """Result of processing a single image."""
    success: bool
    original_filename: str
    upload_url: Optional[str] = None
    json_filename: Optional[str] = None
    downloaded_filename: Optional[str] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None

class ImageProcessor:
    """Main class for processing images through the complete pipeline."""
    
    def __init__(self, 
                 ready_dir: str = "img/ready",
                 uploaded_dir: str = "img/uploaded",
                 processed_dir: str = "img/processed",
                 json_output_dir: str = "out/prompt_json", 
                 csv_log_path: str = "logs/image_uploading.csv"):
        """
        Initialize the image processor.
        
        Args:
            ready_dir: Directory containing images to process
            uploaded_dir: Directory to save downloaded images
            processed_dir: Directory to move processed original images
            json_output_dir: Directory to save JSON files for video generation
            csv_log_path: Path to CSV log file
        """
        self.ready_dir = Path(ready_dir)
        self.uploaded_dir = Path(uploaded_dir)
        self.processed_dir = Path(processed_dir)
        self.json_output_dir = Path(json_output_dir)
        self.csv_log_path = Path(csv_log_path)
        
        # Initialize components
        self.uploader = FreeImageHostUploader()
        self.openrouter_client = OpenRouterClient()
        
        # Ensure directories exist
        self.uploaded_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.json_output_dir.mkdir(parents=True, exist_ok=True)
        self.csv_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize CSV if it doesn't exist
        self._init_csv_log()
        
        # Load processed images cache
        self.processed_images = self._load_processed_images()
    
    def _init_csv_log(self):
        """Initialize CSV log file with headers if it doesn't exist."""
        if not self.csv_log_path.exists():
            with open(self.csv_log_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'original_filename', 'file_size_bytes', 
                    'upload_url', 'image_size_after_download', 'json_filename',
                    'downloaded_filename', 'processing_time_seconds', 'status', 'error_message'
                ])
    
    def _load_processed_images(self) -> set:
        """
        Load list of already processed images from CSV log.
        
        Returns:
            Set of processed image filenames
        """
        processed = set()
        if self.csv_log_path.exists():
            try:
                with open(self.csv_log_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get('status') == 'success':
                            processed.add(row.get('original_filename'))
                print(f"📋 Found {len(processed)} previously processed images")
            except Exception as e:
                print(f"⚠️ Warning: Could not load processed images list: {e}")
        return processed
    
    def is_already_processed(self, filename: str) -> bool:
        """
        Check if an image has already been processed successfully.
        
        Args:
            filename: Image filename to check
            
        Returns:
            True if already processed, False otherwise
        """
        return filename in self.processed_images
    
    def move_to_processed(self, image_path: Path, descriptive_name: str) -> bool:
        """
        Move successfully processed image to processed directory with descriptive name.
        
        Args:
            image_path: Original image path
            descriptive_name: AI-generated descriptive name
            
        Returns:
            True if moved successfully, False otherwise
        """
        try:
            # Create new filename with descriptive name and timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = f"{descriptive_name}_{timestamp}_PROCESSED{image_path.suffix}"
            processed_path = self.processed_dir / new_filename
            
            # Move the file
            image_path.rename(processed_path)
            print(f"📁 Moved to processed: {new_filename}")
            return True
            
        except Exception as e:
            print(f"⚠️ Warning: Could not move image to processed directory: {e}")
            return False
    
    def find_images(self) -> List[Path]:
        """
        Find all image files in the ready directory.
        
        Returns:
            List of image file paths
        """
        if not self.ready_dir.exists():
            print(f"Ready directory does not exist: {self.ready_dir}")
            return []
        
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        image_files = []
        
        for file_path in self.ready_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                image_files.append(file_path)
        
        print(f"Found {len(image_files)} image files in {self.ready_dir}")
        return sorted(image_files)
    
    def upload_image(self, image_path: Path) -> Optional[str]:
        """
        Upload image using freeimage host uploader.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Upload URL if successful, None otherwise
        """
        print(f"Uploading {image_path.name}...")
        result = self.uploader.upload_image(str(image_path))
        
        if result.success:
            print(f"✅ Upload successful: {result.url}")
            return result.url
        else:
            print(f"❌ Upload failed: {result.error}")
            return None
    
    def download_image_with_wget(self, url: str, output_path: Path) -> Optional[int]:
        """
        Download image using wget and return file size.
        
        Args:
            url: Image URL to download
            output_path: Path to save downloaded image
            
        Returns:
            File size in bytes if successful, None otherwise
        """
        try:
            print(f"Downloading image from {url}...")
            result = subprocess.run([
                'wget', '-q', '--timeout=30', '--tries=3', 
                '-O', str(output_path), url
            ], capture_output=True, text=True)
            
            if result.returncode == 0 and output_path.exists():
                file_size = output_path.stat().st_size
                print(f"✅ Downloaded successfully: {file_size} bytes")
                return file_size
            else:
                print(f"❌ Download failed: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"❌ Download error: {e}")
            return None
    
    def refine_prompt_with_openrouter(self, original_prompt: str) -> str:
        """
        Refines the given prompt using OpenRouter.
        
        Args:
            original_prompt: Original video prompt to refine
            
        Returns:
            Refined prompt focused on movement, or original prompt if refinement fails
        """
        try:
            refine_prompt = (
                f"Refine the following video prompt for an image-to-video model. Focus exclusively on movement, "
                f"changes, human expression, or background alterations. Absolutely avoid any static image descriptions. "
                f"Keep it concise (under 100 words): {original_prompt}"
            )
            
            print(f"Refining prompt with OpenRouter: '{original_prompt}'")
            result = self.openrouter_client.generate_content(
                prompt=refine_prompt,
                api_source="openrouter"
            )
            
            if result.success and result.content:
                refined_prompt = result.content.strip()
                print(f"Refined prompt: '{refined_prompt}'")
                return refined_prompt
            else:
                print(f"❌ Prompt refinement failed: {result.error}")
                return original_prompt
                
        except Exception as e:
            print(f"❌ Error refining prompt: {e}")
            return original_prompt
    
    def generate_creative_movement_prompts(self, image_url: str, base_prompt: str) -> List[str]:
        """
        Generate 3 additional creative movement-focused prompts with aggressive imagination.
        
        Args:
            image_url: URL of uploaded image
            base_prompt: Base video prompt to build upon
            
        Returns:
            List of 3 creative movement prompts
        """
        creative_prompts = []
        
        # Prompt 1: Aggressive/Dynamic Movement
        aggressive_prompt = (
            f"Based on this image and the base prompt '{base_prompt}', create an AGGRESSIVE and DYNAMIC video prompt "
            f"that focuses on intense, unexpected movements. Think of objects suddenly coming to life, dramatic "
            f"transformations, explosive energy, rapid changes, or supernatural phenomena. Make static objects move "
            f"in ways they shouldn't - buildings swaying, statues walking, water flowing upward, fire dancing wildly. "
            f"Focus purely on dramatic movement and action, not static descriptions. Keep under 100 words."
        )
        
        # Prompt 2: Surreal/Impossible Movement
        surreal_prompt = (
            f"Based on this image and the base prompt '{base_prompt}', create a SURREAL and IMPOSSIBLE video prompt "
            f"that defies physics and reality. Imagine gravity reversing, time flowing backward, objects morphing into "
            f"other forms, colors bleeding and shifting, dimensions warping, or magical transformations. Make everything "
            f"move in dreamlike, impossible ways that challenge perception. Focus on fantastical movement only. "
            f"Keep under 100 words."
        )
        
        # Prompt 3: Cinematic/Dramatic Movement
        cinematic_prompt = (
            f"Based on this image and the base prompt '{base_prompt}', create a CINEMATIC and DRAMATIC video prompt "
            f"with movie-like camera movements and theatrical actions. Think of dramatic zoom-ins, sweeping camera "
            f"movements, characters performing unexpected actions, environmental storytelling through movement, "
            f"lighting changes that create mood, or action sequences. Make it feel like a movie scene with compelling "
            f"movement and visual storytelling. Focus on cinematic motion only. Keep under 100 words."
        )
        
        prompts_to_generate = [
            ("aggressive", aggressive_prompt),
            ("surreal", surreal_prompt), 
            ("cinematic", cinematic_prompt)
        ]
        
        for prompt_type, prompt_text in prompts_to_generate:
            try:
                print(f"Generating {prompt_type} creative movement prompt...")
                result = self.openrouter_client.generate_content(
                    prompt=prompt_text,
                    image_url=image_url,
                    api_source="openrouter"
                )
                
                if result.success and result.content:
                    creative_prompts.append(result.content.strip())
                    print(f"✅ {prompt_type.capitalize()} prompt generated")
                else:
                    print(f"❌ {prompt_type.capitalize()} prompt generation failed: {result.error}")
                    # Fallback prompt
                    creative_prompts.append(f"Enhanced {prompt_type} movement based on: {base_prompt}")
                    
            except Exception as e:
                print(f"❌ Error generating {prompt_type} prompt: {e}")
                creative_prompts.append(f"Enhanced {prompt_type} movement based on: {base_prompt}")
        
        return creative_prompts

    def generate_video_json_with_openrouter(self, image_url: str, original_filename: str) -> Optional[Dict[str, Any]]:
        """
        Generate video generation JSON using OpenRouter based on image URL.
        
        Args:
            image_url: URL of uploaded image
            original_filename: Original filename for context
            
        Returns:
            Video generation JSON data if successful, None otherwise
        """
        # First, get image description
        image_prompt = (
            "Analyze this image and create a detailed image generation prompt that could recreate this image. "
            "Focus on visual elements, style, composition, colors, lighting, and atmosphere. "
            "Be specific and descriptive but concise. This will be used for image generation."
        )
        
        print(f"Generating image prompt for {original_filename}...")
        image_result = self.openrouter_client.generate_content(
            prompt=image_prompt,
            image_url=image_url,
            api_source="openrouter"
        )
        
        if not image_result.success or not image_result.content:
            print(f"❌ Image prompt generation failed: {image_result.error}")
            return None
        
        # Then, get video prompt
        video_prompt = (
            "Based on this image, create a video generation prompt that describes subtle movements, "
            "animations, or changes that could bring this static image to life. "
            "Focus on natural movements like: breathing, hair/fabric swaying, light flickering, "
            "particle effects, water movement, eye blinking, subtle camera movements, etc. "
            "Keep it concise and focused on movement only, not static descriptions. "
            "This will be used for video generation from the image."
        )
        
        print(f"Generating video prompt for {original_filename}...")
        video_result = self.openrouter_client.generate_content(
            prompt=video_prompt,
            image_url=image_url,
            api_source="openrouter"
        )
        
        if not video_result.success or not video_result.content:
            print(f"❌ Video prompt generation failed: {video_result.error}")
            return None
        
        # Refine the original video prompt
        base_video_prompt = video_result.content.strip()
        refined_video_prompt = self.refine_prompt_with_openrouter(base_video_prompt)
        
        # Generate 3 additional creative movement prompts
        creative_prompts = self.generate_creative_movement_prompts(image_url, base_video_prompt)
        
        print("✅ Video generation JSON created successfully")
        return {
            "image_prompt": image_result.content.strip(),
            "video_prompt": base_video_prompt,
            "refined_video_prompt": refined_video_prompt,
            "creative_video_prompt_1": creative_prompts[0] if len(creative_prompts) > 0 else "Enhanced aggressive movement",
            "creative_video_prompt_2": creative_prompts[1] if len(creative_prompts) > 1 else "Enhanced surreal movement", 
            "creative_video_prompt_3": creative_prompts[2] if len(creative_prompts) > 2 else "Enhanced cinematic movement"
        }
    
    def create_safe_filename(self, title: str, extension: str = ".json") -> str:
        """
        Create a safe filename from title.
        
        Args:
            title: Title to convert to filename
            extension: File extension
            
        Returns:
            Safe filename
        """
        # Remove or replace unsafe characters including commas and periods
        safe_title = re.sub(r'[<>:"/\\|?*,.]', '_', title)
        safe_title = re.sub(r'\s+', '_', safe_title)  # Replace spaces with underscores
        safe_title = re.sub(r'_+', '_', safe_title)  # Replace multiple underscores with single
        safe_title = safe_title.strip('_')  # Remove leading/trailing underscores
        safe_title = safe_title[:50]  # Limit length
        
        return f"{safe_title}{extension}"
    
    def format_file_size(self, size_bytes: int) -> str:
        """
        Convert file size in bytes to human-readable format.
        
        Args:
            size_bytes: File size in bytes
            
        Returns:
            Human-readable file size string (e.g., "16.9 MB", "1.2 KB")
        """
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)
        
        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1
        
        # Format with appropriate decimal places
        if i == 0:  # Bytes
            return f"{int(size)} {size_names[i]}"
        else:
            return f"{size:.1f} {size_names[i]}"
    
    def log_to_csv(self, result: ProcessingResult, original_size: int, downloaded_size: Optional[int]):
        """
        Log processing result to CSV file.
        
        Args:
            result: Processing result
            original_size: Original file size
            downloaded_size: Downloaded file size
        """
        with open(self.csv_log_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                result.original_filename,
                original_size,
                result.upload_url or '',
                downloaded_size or '',
                result.json_filename or '',
                result.downloaded_filename or '',
                f"{result.processing_time:.2f}" if result.processing_time else '',
                'success' if result.success else 'failed',
                result.error or ''
            ])
    
    def process_single_image(self, image_path: Path) -> ProcessingResult:
        """
        Process a single image through the complete pipeline.
        
        Args:
            image_path: Path to image file
            
        Returns:
            ProcessingResult with details of processing
        """
        start_time = time.time()
        original_filename = image_path.name
        original_size = image_path.stat().st_size
        
        print(f"\n🔄 Processing: {original_filename}")
        
        # Check if already processed
        if self.is_already_processed(original_filename):
            print(f"⏭️ Skipping {original_filename} - already processed successfully")
            return ProcessingResult(
                success=False,
                original_filename=original_filename,
                error="Already processed - skipped",
                processing_time=time.time() - start_time
            )
        
        try:
            # Step 1: Upload image
            upload_url = self.upload_image(image_path)
            if not upload_url:
                return ProcessingResult(
                    success=False,
                    original_filename=original_filename,
                    error="Failed to upload image",
                    processing_time=time.time() - start_time
                )
            
            # Step 2: Get brief description for meaningful filename
            print(f"Getting brief description for naming...")
            brief_result = self.openrouter_client.get_brief_description(
                image_url=upload_url,
                api_source="openrouter"
            )
            
            if not brief_result.success or not brief_result.content:
                print(f"❌ Brief description failed, using fallback naming")
                descriptive_name = "Unknown_Image"
            else:
                # Clean up the brief description for filename use
                descriptive_name = self.create_safe_filename(brief_result.content.strip(), "")
                print(f"✅ Descriptive name: {descriptive_name}")
            
            # Step 3: Generate video JSON using OpenRouter
            prompt_data = self.generate_video_json_with_openrouter(upload_url, original_filename)
            if not prompt_data:
                return ProcessingResult(
                    success=False,
                    original_filename=original_filename,
                    upload_url=upload_url,
                    error="Failed to generate video JSON description",
                    processing_time=time.time() - start_time
                )
            
            # Step 4: Create filenames based on AI-analyzed descriptive name (with timestamp)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # milliseconds
            json_filename = f"{descriptive_name}_{timestamp}.json"
            image_filename = f"{descriptive_name}_{timestamp}{image_path.suffix}"
            video_filename = f"{descriptive_name}_{timestamp}.mp4"
            
            # Step 5: Download image with wget to img/uploaded/
            downloaded_image_path = self.uploaded_dir / image_filename
            downloaded_size = self.download_image_with_wget(upload_url, downloaded_image_path)
            
            if downloaded_size is None:
                return ProcessingResult(
                    success=False,
                    original_filename=original_filename,
                    upload_url=upload_url,
                    json_filename=json_filename,
                    error="Failed to download image",
                    processing_time=time.time() - start_time
                )
            
            # Step 6: Create complete video generation JSON with image size and all prompts
            video_json = {
                "pic_name": image_filename,
                "video_name": video_filename,
                "video_prompt": prompt_data["video_prompt"],
                "image_prompt": prompt_data["image_prompt"],
                "refined_video_prompt": prompt_data["refined_video_prompt"],
                "creative_video_prompt_1": prompt_data["creative_video_prompt_1"],
                "creative_video_prompt_2": prompt_data["creative_video_prompt_2"],
                "creative_video_prompt_3": prompt_data["creative_video_prompt_3"],
                "image_url": upload_url,
                "image_size": self.format_file_size(downloaded_size)
            }
            
            # Step 7: Save JSON file to out/prompt_json/
            json_path = self.json_output_dir / json_filename
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(video_json, f, indent=4, ensure_ascii=False)
            print(f"✅ Video JSON saved: {json_filename}")
            
            processing_time = time.time() - start_time
            result = ProcessingResult(
                success=True,
                original_filename=original_filename,
                upload_url=upload_url,
                json_filename=json_filename,
                downloaded_filename=image_filename,
                processing_time=processing_time
            )
            
            # Step 7: Log to CSV
            self.log_to_csv(result, original_size, downloaded_size)
            
            # Step 8: Move original image to processed directory
            self.move_to_processed(image_path, descriptive_name)
            
            # Step 9: Add to processed images cache to prevent reprocessing
            self.processed_images.add(original_filename)
            
            print(f"✅ Processing completed in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"❌ {error_msg}")
            
            result = ProcessingResult(
                success=False,
                original_filename=original_filename,
                error=error_msg,
                processing_time=time.time() - start_time
            )
            
            # Log failed attempt
            self.log_to_csv(result, original_size, None)
            return result
    
    def process_all_images(self, limit: Optional[int] = None) -> List[ProcessingResult]:
        """
        Process all images in the ready directory.
        
        Args:
            limit: Maximum number of images to process (None for all)
            
        Returns:
            List of ProcessingResult objects
        """
        image_files = self.find_images()
        
        if not image_files:
            print("No images found to process.")
            return []
        
        if limit:
            image_files = image_files[:limit]
            print(f"Processing first {limit} images...")
        
        results = []
        successful = 0
        failed = 0
        
        for i, image_path in enumerate(image_files, 1):
            print(f"\n{'='*60}")
            print(f"Processing image {i}/{len(image_files)}")
            print(f"{'='*60}")
            
            result = self.process_single_image(image_path)
            results.append(result)
            
            if result.success:
                successful += 1
            else:
                failed += 1
            
            # Small delay between processing
            time.sleep(1)
        
        print(f"\n{'='*60}")
        print(f"PROCESSING COMPLETE")
        print(f"{'='*60}")
        print(f"Total processed: {len(results)}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Success rate: {(successful/len(results)*100):.1f}%")
        
        return results

def parse_image_and_generate_json(limit: Optional[int] = None) -> List[ProcessingResult]:
    """
    Main function to parse images and generate JSON files.
    
    Args:
        limit: Maximum number of images to process (None for all)
        
    Returns:
        List of ProcessingResult objects
    """
    processor = ImageProcessor()
    return processor.process_all_images(limit=limit)

if __name__ == "__main__":
    import sys
    
    # Parse command line arguments
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
            print(f"Processing limit set to: {limit}")
        except ValueError:
            print("Invalid limit argument. Processing all images.")
    
    # Run the processing
    results = parse_image_and_generate_json(limit=limit)
    
    # Print summary
    if results:
        successful = sum(1 for r in results if r.success)
        print(f"\n🎉 Final Summary:")
        print(f"   - Images processed: {len(results)}")
        print(f"   - Successful: {successful}")
        print(f"   - Failed: {len(results) - successful}")
        print(f"   - Check logs/image_uploading.csv for detailed records")
        print(f"   - Check img/uploaded/ for generated files")
    else:
        print("No images were processed.")
