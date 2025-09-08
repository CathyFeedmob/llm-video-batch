#!/usr/bin/env python3
"""
Temporary Script: Process Generated Images

This script:
1. Finds generated images in database with status 'pending' (created by first script)
2. Processes them through upload and prompt generation pipeline
3. Updates existing database records instead of creating duplicates
4. Limits processing to 5 images (as requested)

Usage:
    python scripts/temp_process_generated_images.py
"""

import os
import sys
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import logging

# Add scripts directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__)))

from image_uploader import FreeImageHostUploader
from openrouter_base import OpenRouterClient
from database_manager import DatabaseManager, PromptRecord, VideoRecord

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/temp_image_processing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TempImageProcessor:
    """Temporary class for processing generated images using existing database records"""
    
    def __init__(self):
        self.db_path = "data/llm_video_batch.db"
        self.uploaded_dir = Path("img/uploaded")
        self.processed_dir = Path("img/processed")
        self.json_output_dir = Path("out/prompt_json")
        
        # Create directories
        self.uploaded_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.json_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.uploader = FreeImageHostUploader()
        self.openrouter_client = OpenRouterClient()
        self.db_manager = DatabaseManager()
        
        # Ensure logs directory exists
        Path("logs").mkdir(exist_ok=True)
    
    def get_pending_generated_images(self, limit: int = 5) -> List[Dict]:
        """
        Get generated images with status 'pending' from database.
        
        Args:
            limit: Maximum number of images to retrieve
            
        Returns:
            List of image data from database
        """
        images = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Query for generated images that need processing
            query = """
            SELECT 
                i.id,
                i.original_filename,
                i.original_path,
                i.file_size_bytes,
                i.descriptive_name,
                i.origin_image_id,
                i.status,
                orig.descriptive_name as origin_name
            FROM images i
            LEFT JOIN images orig ON i.origin_image_id = orig.id
            WHERE i.status = 'pending' 
            AND i.origin_image_id IS NOT NULL
            ORDER BY i.created_at DESC
            LIMIT ?
            """
            
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            
            for row in rows:
                images.append({
                    "id": row["id"],
                    "original_filename": row["original_filename"],
                    "original_path": row["original_path"],
                    "file_size_bytes": row["file_size_bytes"],
                    "descriptive_name": row["descriptive_name"],
                    "origin_image_id": row["origin_image_id"],
                    "origin_name": row["origin_name"],
                    "status": row["status"]
                })
            
            conn.close()
            logger.info(f"Retrieved {len(images)} pending generated images")
            
        except Exception as e:
            logger.error(f"Failed to retrieve pending images: {str(e)}")
            
        return images
    
    def update_image_status(self, image_id: int, status: str, error_message: str = None, **kwargs):
        """Update image record status and other fields."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build update query dynamically
            update_fields = ["status = ?"]
            values = [status]
            
            if error_message:
                update_fields.append("error_message = ?")
                values.append(error_message)
            
            for field, value in kwargs.items():
                update_fields.append(f"{field} = ?")
                values.append(value)
            
            values.append(image_id)  # For WHERE clause
            
            query = f"UPDATE images SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to update image status: {str(e)}")
    
    def upload_and_process_image(self, image_data: Dict) -> Dict:
        """
        Upload image and generate prompts, updating existing database record.
        
        Args:
            image_data: Image data from database
            
        Returns:
            Processing result dictionary
        """
        image_id = image_data["id"]
        image_path = Path(image_data["original_path"])
        
        logger.info(f"Processing image ID {image_id}: {image_data['original_filename']}")
        
        try:
            # Check if file exists
            if not image_path.exists():
                error_msg = f"Image file not found: {image_path}"
                logger.error(error_msg)
                self.update_image_status(image_id, "failed", error_msg)
                return {"success": False, "error": error_msg}
            
            # Step 1: Upload image
            logger.info("Uploading image...")
            upload_result = self.uploader.upload_image(str(image_path))
            
            if not upload_result.success:
                error_msg = f"Upload failed: {upload_result.error}"
                logger.error(error_msg)
                self.update_image_status(image_id, "failed", error_msg)
                return {"success": False, "error": error_msg}
            
            upload_url = upload_result.url
            logger.info(f"Upload successful: {upload_url}")
            
            # Update database with upload URL
            self.update_image_status(image_id, "uploaded", upload_url=upload_url)
            
            # Step 2: Generate prompts using OpenRouter
            logger.info("Generating prompts...")
            prompt_data = self.generate_video_json_with_openrouter(upload_url, image_data["original_filename"])
            
            if not prompt_data:
                error_msg = "Failed to generate prompts"
                logger.error(error_msg)
                self.update_image_status(image_id, "failed", error_msg)
                return {"success": False, "error": error_msg}
            
            # Step 3: Create prompt record in database
            logger.info("Creating prompt record...")
            prompt_record = PromptRecord(
                image_id=image_id,
                image_prompt=prompt_data["image_prompt"],
                video_prompt=prompt_data["video_prompt"],
                refined_video_prompt=prompt_data["refined_video_prompt"],
                creative_video_prompt_1=prompt_data["creative_video_prompt_1"],
                creative_video_prompt_2=prompt_data["creative_video_prompt_2"],
                creative_video_prompt_3=prompt_data["creative_video_prompt_3"]
            )
            prompt_id = self.db_manager.insert_prompt_record(prompt_record)
            logger.info(f"Prompt record created with ID: {prompt_id}")
            
            # Step 4: Create filenames
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            descriptive_name = image_data["descriptive_name"] or "Generated_Image"
            # Clean descriptive name for filename
            safe_name = descriptive_name.replace("Generated from prompt: ", "").replace(" ", "_")[:30]
            
            json_filename = f"{safe_name}_{timestamp}.json"
            image_filename = f"{safe_name}_{timestamp}{image_path.suffix}"
            video_filename = f"{safe_name}_{timestamp}.mp4"
            
            # Step 5: Download image to img/uploaded
            logger.info("Downloading image...")
            downloaded_path = self.uploaded_dir / image_filename
            
            import subprocess
            result = subprocess.run([
                'wget', '-q', '--timeout=30', '--tries=3', 
                '-O', str(downloaded_path), upload_url
            ], capture_output=True, text=True)
            
            if result.returncode != 0 or not downloaded_path.exists():
                error_msg = f"Download failed: {result.stderr}"
                logger.error(error_msg)
                self.update_image_status(image_id, "failed", error_msg)
                return {"success": False, "error": error_msg}
            
            downloaded_size = downloaded_path.stat().st_size
            logger.info(f"Download successful: {downloaded_size} bytes")
            
            # Step 6: Create and save JSON file
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
            
            json_path = self.json_output_dir / json_filename
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(video_json, f, indent=4, ensure_ascii=False)
            logger.info(f"JSON saved: {json_filename}")
            
            # Step 7: Create video record
            logger.info("Creating video record...")
            video_record = VideoRecord(
                image_id=image_id,
                prompt_id=prompt_id,
                video_filename=video_filename,
                prompt_used=prompt_data["video_prompt"],
                prompt_type="base",
                status="pending"
            )
            video_id = self.db_manager.insert_video_record(video_record)
            logger.info(f"Video record created with ID: {video_id}")
            
            # Step 8: Move original to processed
            processed_path = None
            try:
                processed_filename = f"{safe_name}_{timestamp}_PROCESSED{image_path.suffix}"
                processed_path = self.processed_dir / processed_filename
                image_path.rename(processed_path)
                logger.info(f"Moved to processed: {processed_filename}")
            except Exception as e:
                logger.warning(f"Could not move to processed: {e}")
            
            # Step 9: Final database update
            self.update_image_status(
                image_id, 
                "success",
                uploaded_filename=image_filename,
                uploaded_path=str(downloaded_path),
                downloaded_size_bytes=downloaded_size,
                processed_path=str(processed_path) if processed_path else None
            )
            
            logger.info("Processing completed successfully")
            return {
                "success": True,
                "image_id": image_id,
                "prompt_id": prompt_id,
                "video_id": video_id,
                "json_filename": json_filename,
                "uploaded_filename": image_filename
            }
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            self.update_image_status(image_id, "failed", error_msg)
            return {"success": False, "error": error_msg}
    
    def generate_video_json_with_openrouter(self, image_url: str, original_filename: str) -> Optional[Dict]:
        """Generate video prompts using OpenRouter (simplified version)."""
        try:
            # Generate image prompt
            image_prompt = (
                "Analyze this image and create a detailed image generation prompt that could recreate this image. "
                "Focus on visual elements, style, composition, colors, lighting, and atmosphere. "
                "Be specific and descriptive but concise."
            )
            
            image_result = self.openrouter_client.generate_content(
                prompt=image_prompt,
                image_url=image_url,
                api_source="openrouter"
            )
            
            if not image_result.success:
                logger.error(f"Image prompt generation failed: {image_result.error}")
                return None
            
            # Generate video prompt
            video_prompt = (
                "Based on this image, create a video generation prompt that describes subtle movements, "
                "animations, or changes that could bring this static image to life. "
                "Focus on natural movements and keep it concise."
            )
            
            video_result = self.openrouter_client.generate_content(
                prompt=video_prompt,
                image_url=image_url,
                api_source="openrouter"
            )
            
            if not video_result.success:
                logger.error(f"Video prompt generation failed: {video_result.error}")
                return None
            
            base_video_prompt = video_result.content.strip()
            
            return {
                "image_prompt": image_result.content.strip(),
                "video_prompt": base_video_prompt,
                "refined_video_prompt": base_video_prompt,  # Simplified
                "creative_video_prompt_1": f"Enhanced dynamic version: {base_video_prompt}",
                "creative_video_prompt_2": f"Surreal version: {base_video_prompt}",
                "creative_video_prompt_3": f"Cinematic version: {base_video_prompt}"
            }
            
        except Exception as e:
            logger.error(f"Error generating prompts: {e}")
            return None
    
    def format_file_size(self, size_bytes: int) -> str:
        """Convert file size to human readable format."""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        size = float(size_bytes)
        
        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1
        
        return f"{size:.1f} {size_names[i]}" if i > 0 else f"{int(size)} {size_names[i]}"
    
    def process_images(self, limit: int = 5) -> List[Dict]:
        """Process pending generated images."""
        logger.info(f"Starting processing of pending generated images (limit: {limit})")
        
        # Get pending images from database
        pending_images = self.get_pending_generated_images(limit)
        
        if not pending_images:
            logger.info("No pending generated images found")
            return []
        
        results = []
        
        for i, image_data in enumerate(pending_images, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing {i}/{len(pending_images)}: {image_data['original_filename']}")
            logger.info(f"Origin: {image_data['origin_name']} (ID: {image_data['origin_image_id']})")
            logger.info(f"{'='*60}")
            
            result = self.upload_and_process_image(image_data)
            result["original_filename"] = image_data["original_filename"]
            result["origin_name"] = image_data["origin_name"]
            results.append(result)
            
            # Delay between processing
            if i < len(pending_images):
                logger.info("Waiting 2 seconds before next image...")
                time.sleep(2)
        
        return results
    
    def print_summary(self, results: List[Dict]):
        """Print processing summary."""
        if not results:
            print("\n📭 No images were processed.")
            return
        
        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful
        
        print(f"\n{'='*60}")
        print(f"PROCESSING SUMMARY")
        print(f"{'='*60}")
        print(f"Total processed: {len(results)}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Success rate: {(successful/len(results)*100):.1f}%")
        
        if successful > 0:
            print(f"\n✅ Successfully processed:")
            for result in results:
                if result["success"]:
                    print(f"  - {result['original_filename']}")
                    print(f"    → Origin: {result['origin_name']}")
                    print(f"    → JSON: {result['json_filename']}")
                    print(f"    → Database IDs: Image={result['image_id']}, Prompt={result['prompt_id']}, Video={result['video_id']}")
        
        if failed > 0:
            print(f"\n❌ Failed to process:")
            for result in results:
                if not result["success"]:
                    print(f"  - {result['original_filename']}: {result['error']}")


def main():
    """Main function"""
    processor = TempImageProcessor()
    
    print("🚀 Starting processing of pending generated images...")
    print("📋 This will process up to 5 generated images that are pending in the database")
    print("🔄 Each image will be processed through:")
    print("   1. Upload to image hosting service")
    print("   2. Generate prompts using AI vision")
    print("   3. Update existing database records (no duplicates)")
    print("   4. Create prompt and video records")
    print("   5. Download and organize files")
    
    # Process images
    start_time = time.time()
    results = processor.process_images(limit=5)
    total_time = time.time() - start_time
    
    # Print summary
    processor.print_summary(results)
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"logs/temp_processing_results_{timestamp}.json"
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": timestamp,
            "total_processing_time": total_time,
            "results": results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 Detailed results saved to: {results_file}")
    print(f"⏱️ Total processing time: {total_time:.2f} seconds")


if __name__ == "__main__":
    main()
