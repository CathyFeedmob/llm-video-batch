#!/usr/bin/env python3
"""
Temporary Script: Generate Images from Database Video Prompts

This script:
1. Finds images in database without origin_image_id (original images)
2. Uses their video_prompt to generate new images via Duomi API
3. Moves generated images to img/ready for further processing
4. Updates database with origin_image_id reference

Limit: 5 images (as requested)

Usage:
    python scripts/temp_generate_images_from_db.py
"""

import os
import sys
import json
import sqlite3
import requests
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging

# Add scripts directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__)))

from duomi_image_generator import DuomiImageGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/temp_image_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TempImageGenerator:
    """Temporary class for generating images from database video prompts"""
    
    def __init__(self):
        self.db_path = "data/llm_video_batch.db"
        self.ready_dir = Path("img/ready")
        self.ready_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Duomi generator
        self.duomi_generator = DuomiImageGenerator()
        
        # Ensure logs directory exists
        Path("logs").mkdir(exist_ok=True)
    
    def get_original_images_with_prompts(self, limit: int = 5) -> List[Dict]:
        """
        Get original images (without origin_image_id) that have video prompts.
        
        Args:
            limit: Maximum number of images to retrieve
            
        Returns:
            List of image and prompt data
        """
        images_with_prompts = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Query for original images with video prompts
            query = """
            SELECT 
                i.id as image_id,
                i.descriptive_name,
                i.original_filename,
                i.upload_url,
                p.id as prompt_id,
                p.video_prompt,
                p.refined_video_prompt,
                p.creative_video_prompt_1,
                p.creative_video_prompt_2,
                p.creative_video_prompt_3
            FROM images i
            JOIN prompts p ON i.id = p.image_id
            WHERE i.origin_image_id IS NULL 
            AND i.status = 'success'
            AND p.video_prompt IS NOT NULL 
            AND p.video_prompt != ''
            ORDER BY i.created_at DESC
            LIMIT ?
            """
            
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            
            for row in rows:
                images_with_prompts.append({
                    "image_id": row["image_id"],
                    "descriptive_name": row["descriptive_name"],
                    "original_filename": row["original_filename"],
                    "upload_url": row["upload_url"],
                    "prompt_id": row["prompt_id"],
                    "video_prompt": row["video_prompt"],
                    "refined_video_prompt": row["refined_video_prompt"],
                    "creative_video_prompt_1": row["creative_video_prompt_1"],
                    "creative_video_prompt_2": row["creative_video_prompt_2"],
                    "creative_video_prompt_3": row["creative_video_prompt_3"]
                })
            
            conn.close()
            logger.info(f"Retrieved {len(images_with_prompts)} original images with prompts")
            
        except Exception as e:
            logger.error(f"Failed to retrieve images from database: {str(e)}")
            
        return images_with_prompts
    
    def generate_image_from_prompt(self, prompt: str, image_data: Dict) -> Optional[str]:
        """
        Generate image using Duomi API and save to img/ready.
        
        Args:
            prompt: Video prompt to use for image generation
            image_data: Original image data for context
            
        Returns:
            Path to generated image file or None if failed
        """
        try:
            logger.info(f"Generating image for: {image_data['descriptive_name']}")
            logger.info(f"Using prompt: {prompt[:100]}...")
            
            # Generate image using Duomi
            result = self.duomi_generator.generate_image(prompt)
            
            if not result.get("success"):
                logger.error(f"Image generation failed: {result.get('error')}")
                return None
            
            # Extract image URL from result
            image_url = None
            if "data" in result["data"] and len(result["data"]["data"]) > 0:
                image_url = result["data"]["data"][0].get("url")
            
            if not image_url:
                logger.error("No image URL in generation result")
                return None
            
            # Download and save image to img/ready
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            safe_name = image_data["descriptive_name"].replace(" ", "_")[:30]
            filename = f"generated_{safe_name}_{timestamp}.png"
            filepath = self.ready_dir / filename
            
            # Download image
            img_response = requests.get(image_url, timeout=30)
            if img_response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(img_response.content)
                
                logger.info(f"Image saved to: {filepath}")
                return str(filepath)
            else:
                logger.error(f"Failed to download generated image: {img_response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating image: {str(e)}")
            return None
    
    def create_new_image_record(self, generated_path: str, origin_image_id: int, prompt_used: str) -> Optional[int]:
        """
        Create new image record in database for generated image.
        
        Args:
            generated_path: Path to generated image
            origin_image_id: ID of original image this was generated from
            prompt_used: Prompt used for generation
            
        Returns:
            New image ID or None if failed
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get file info
            file_path = Path(generated_path)
            file_size = file_path.stat().st_size
            
            # Insert new image record
            cursor.execute("""
                INSERT INTO images (
                    original_filename, original_path, file_size_bytes,
                    descriptive_name, processed_path, status, origin_image_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                file_path.name,
                str(file_path),
                file_size,
                f"Generated from prompt: {prompt_used[:50]}...",
                str(file_path),
                "pending",  # Will be processed by next script
                origin_image_id
            ))
            
            new_image_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"Created new image record with ID: {new_image_id}")
            return new_image_id
            
        except Exception as e:
            logger.error(f"Failed to create image record: {str(e)}")
            return None
    
    def process_images(self, limit: int = 5) -> List[Dict]:
        """
        Main processing function.
        
        Args:
            limit: Maximum number of images to process
            
        Returns:
            List of processing results
        """
        logger.info(f"Starting image generation from database prompts (limit: {limit})")
        
        # Get original images with prompts
        images_data = self.get_original_images_with_prompts(limit)
        
        if not images_data:
            logger.info("No original images with prompts found")
            return []
        
        results = []
        
        for i, image_data in enumerate(images_data, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing {i}/{len(images_data)}: {image_data['descriptive_name']}")
            logger.info(f"{'='*60}")
            
            # Try different prompts in order of preference
            prompts_to_try = [
                ("refined_video_prompt", image_data.get("refined_video_prompt")),
                ("video_prompt", image_data.get("video_prompt")),
                ("creative_video_prompt_1", image_data.get("creative_video_prompt_1")),
                ("creative_video_prompt_2", image_data.get("creative_video_prompt_2")),
                ("creative_video_prompt_3", image_data.get("creative_video_prompt_3"))
            ]
            
            generated_path = None
            prompt_used = None
            prompt_type = None
            
            for prompt_name, prompt_text in prompts_to_try:
                if prompt_text and prompt_text.strip():
                    logger.info(f"Trying {prompt_name}...")
                    generated_path = self.generate_image_from_prompt(prompt_text, image_data)
                    if generated_path:
                        prompt_used = prompt_text
                        prompt_type = prompt_name
                        break
                    else:
                        logger.warning(f"Failed with {prompt_name}, trying next...")
                        time.sleep(2)  # Brief delay before retry
            
            result = {
                "success": generated_path is not None,
                "original_image_id": image_data["image_id"],
                "original_name": image_data["descriptive_name"],
                "generated_path": generated_path,
                "prompt_used": prompt_used,
                "prompt_type": prompt_type,
                "error": None if generated_path else "All prompts failed"
            }
            
            # Create database record for generated image
            if generated_path:
                new_image_id = self.create_new_image_record(
                    generated_path, 
                    image_data["image_id"], 
                    prompt_used
                )
                result["new_image_id"] = new_image_id
            
            results.append(result)
            
            # Delay between generations to avoid rate limiting
            if i < len(images_data):
                logger.info("Waiting 3 seconds before next generation...")
                time.sleep(3)
        
        return results
    
    def print_summary(self, results: List[Dict]):
        """Print processing summary."""
        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful
        
        print(f"\n{'='*60}")
        print(f"GENERATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total processed: {len(results)}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Success rate: {(successful/len(results)*100):.1f}%" if results else "0%")
        
        if successful > 0:
            print(f"\nGenerated images saved to: {self.ready_dir}")
            print("These images are ready for processing by the next script.")
        
        if failed > 0:
            print(f"\nFailed generations:")
            for result in results:
                if not result["success"]:
                    print(f"  - {result['original_name']}: {result['error']}")


def main():
    """Main function"""
    generator = TempImageGenerator()
    
    print("🚀 Starting temporary image generation from database video prompts...")
    print("📋 This will generate up to 5 new images based on existing video prompts")
    print("📁 Generated images will be saved to img/ready/ for further processing")
    
    # Process images (limit to 5 as requested)
    results = generator.process_images(limit=5)
    
    # Print summary
    generator.print_summary(results)
    
    # Save detailed results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"logs/temp_generation_results_{timestamp}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 Detailed results saved to: {results_file}")


if __name__ == "__main__":
    main()
