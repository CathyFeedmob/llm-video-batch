#!/usr/bin/env python3
"""
Duomi Image Generation Base Model

This script generates images using the Duomi API based on prompts from:
1. SQLite database (prompts table with image_prompt field)
2. JSON files in out/prompt_json/ directory

Usage:
    python scripts/duomi_image_generator.py --source sqlite --limit 5
    python scripts/duomi_image_generator.py --source json --input-dir out/prompt_json/
    python scripts/duomi_image_generator.py --source sqlite --prompt "custom prompt here"
"""

import os
import sys
import json
import sqlite3
import requests
import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/duomi_image_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DuomiImageGenerator:
    """Base model for generating images using Duomi API"""
    
    def __init__(self, api_key: str = "hpZyr8TglNSwMXcwlFnqVH4IgN"):
        """
        Initialize the Duomi Image Generator
        
        Args:
            api_key: Duomi API key
        """
        self.api_key = api_key
        self.api_url = "https://duomiapi.com/v1/images/generations"
        self.headers = {
            'Authorization': api_key,
            'Content-Type': 'application/json'
        }
        
        # Default generation parameters
        self.default_params = {
            "model": "stabilityai/stable-diffusion-xl-base-1.0",
            "negative_prompt": "",
            "image_size": "1080x1920",
            "batch_size": 1,
            "seed": 51515151,
            "num_inference_steps": 20,
            "guidance_scale": 7.5
        }
        
        # Ensure output directory exists
        self.output_dir = Path("out/generated_images")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Database path
        self.db_path = "data/llm_video_batch.db"
    
    def generate_image(self, prompt: str, **kwargs) -> Dict:
        """
        Generate a single image using Duomi API
        
        Args:
            prompt: Text prompt for image generation
            **kwargs: Additional parameters to override defaults
            
        Returns:
            Dictionary containing generation result
        """
        # Prepare request payload
        payload = self.default_params.copy()
        payload["prompt"] = prompt
        payload.update(kwargs)
        
        logger.info(f"Generating image with prompt: {prompt[:100]}...")
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info("Image generated successfully")
                return {
                    "success": True,
                    "data": result,
                    "prompt": prompt,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                error_msg = f"API request failed with status {response.status_code}: {response.text}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "prompt": prompt,
                    "timestamp": datetime.now().isoformat()
                }
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Request exception: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "prompt": prompt,
                "timestamp": datetime.now().isoformat()
            }
    
    def save_generated_image(self, result: Dict, filename_prefix: str = "generated") -> Optional[str]:
        """
        Save generated image to disk
        
        Args:
            result: Generation result from generate_image()
            filename_prefix: Prefix for the saved filename
            
        Returns:
            Path to saved image file or None if failed
        """
        if not result.get("success") or not result.get("data"):
            return None
            
        try:
            # Extract image URL from result
            image_data = result["data"]
            if "data" in image_data and len(image_data["data"]) > 0:
                image_url = image_data["data"][0].get("url")
                
                if image_url:
                    # Download image
                    img_response = requests.get(image_url, timeout=30)
                    if img_response.status_code == 200:
                        # Generate filename
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"{filename_prefix}_{timestamp}.png"
                        filepath = self.output_dir / filename
                        
                        # Save image
                        with open(filepath, 'wb') as f:
                            f.write(img_response.content)
                        
                        logger.info(f"Image saved to: {filepath}")
                        return str(filepath)
                        
        except Exception as e:
            logger.error(f"Failed to save image: {str(e)}")
            
        return None
    
    def get_prompts_from_database(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Retrieve image prompts from SQLite database
        
        Args:
            limit: Maximum number of prompts to retrieve
            
        Returns:
            List of prompt dictionaries
        """
        prompts = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
            SELECT p.id, p.image_id, p.image_prompt, i.original_filename, i.descriptive_name
            FROM prompts p
            LEFT JOIN images i ON p.image_id = i.id
            WHERE p.image_prompt IS NOT NULL AND p.image_prompt != ''
            ORDER BY p.id
            """
            
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            for row in rows:
                prompts.append({
                    "id": row["id"],
                    "image_id": row["image_id"],
                    "prompt": row["image_prompt"],
                    "original_filename": row["original_filename"],
                    "descriptive_name": row["descriptive_name"]
                })
            
            conn.close()
            logger.info(f"Retrieved {len(prompts)} prompts from database")
            
        except Exception as e:
            logger.error(f"Failed to retrieve prompts from database: {str(e)}")
            
        return prompts
    
    def get_prompts_from_json_files(self, json_dir: str = "out/prompt_json") -> List[Dict]:
        """
        Retrieve image prompts from JSON files
        
        Args:
            json_dir: Directory containing JSON files
            
        Returns:
            List of prompt dictionaries
        """
        prompts = []
        json_path = Path(json_dir)
        
        if not json_path.exists():
            logger.warning(f"JSON directory does not exist: {json_dir}")
            return prompts
        
        try:
            for json_file in json_path.glob("*.json"):
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    if "image_prompt" in data and data["image_prompt"]:
                        prompts.append({
                            "filename": json_file.name,
                            "prompt": data["image_prompt"],
                            "pic_name": data.get("pic_name"),
                            "image_url": data.get("image_url")
                        })
            
            logger.info(f"Retrieved {len(prompts)} prompts from JSON files")
            
        except Exception as e:
            logger.error(f"Failed to retrieve prompts from JSON files: {str(e)}")
            
        return prompts
    
    def batch_generate_from_database(self, limit: Optional[int] = None, delay: float = 1.0) -> List[Dict]:
        """
        Generate images for all prompts in database
        
        Args:
            limit: Maximum number of images to generate
            delay: Delay between API calls in seconds
            
        Returns:
            List of generation results
        """
        prompts = self.get_prompts_from_database(limit)
        results = []
        
        for i, prompt_data in enumerate(prompts, 1):
            logger.info(f"Processing prompt {i}/{len(prompts)} (ID: {prompt_data['id']})")
            
            result = self.generate_image(prompt_data["prompt"])
            result["source"] = "database"
            result["source_id"] = prompt_data["id"]
            result["image_id"] = prompt_data["image_id"]
            
            # Save image if generation was successful
            if result["success"]:
                filename_prefix = f"db_{prompt_data['id']}"
                if prompt_data["descriptive_name"]:
                    filename_prefix = f"db_{prompt_data['descriptive_name']}"
                
                saved_path = self.save_generated_image(result, filename_prefix)
                result["saved_path"] = saved_path
            
            results.append(result)
            
            # Add delay between requests
            if i < len(prompts):
                time.sleep(delay)
        
        return results
    
    def batch_generate_from_json(self, json_dir: str = "out/prompt_json", delay: float = 1.0) -> List[Dict]:
        """
        Generate images for all prompts in JSON files
        
        Args:
            json_dir: Directory containing JSON files
            delay: Delay between API calls in seconds
            
        Returns:
            List of generation results
        """
        prompts = self.get_prompts_from_json_files(json_dir)
        results = []
        
        for i, prompt_data in enumerate(prompts, 1):
            logger.info(f"Processing JSON file {i}/{len(prompts)}: {prompt_data['filename']}")
            
            result = self.generate_image(prompt_data["prompt"])
            result["source"] = "json"
            result["source_file"] = prompt_data["filename"]
            
            # Save image if generation was successful
            if result["success"]:
                filename_prefix = prompt_data["filename"].replace(".json", "")
                saved_path = self.save_generated_image(result, filename_prefix)
                result["saved_path"] = saved_path
            
            results.append(result)
            
            # Add delay between requests
            if i < len(prompts):
                time.sleep(delay)
        
        return results
    
    def save_results_log(self, results: List[Dict], output_file: str = None) -> str:
        """
        Save generation results to a log file
        
        Args:
            results: List of generation results
            output_file: Output file path (optional)
            
        Returns:
            Path to saved log file
        """
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"logs/duomi_generation_results_{timestamp}.json"
        
        # Ensure logs directory exists
        Path("logs").mkdir(exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to: {output_file}")
        return output_file


def main():
    """Main function for command-line usage"""
    parser = argparse.ArgumentParser(description="Generate images using Duomi API")
    parser.add_argument("--source", choices=["sqlite", "json", "prompt"], required=True,
                       help="Source of prompts: sqlite database, json files, or single prompt")
    parser.add_argument("--limit", type=int, help="Limit number of prompts to process")
    parser.add_argument("--input-dir", default="out/prompt_json", 
                       help="Directory containing JSON files (for json source)")
    parser.add_argument("--prompt", help="Single prompt to generate (for prompt source)")
    parser.add_argument("--delay", type=float, default=1.0,
                       help="Delay between API calls in seconds")
    parser.add_argument("--api-key", default="hpZyr8TglNSwMXcwlFnqVH4IgN",
                       help="Duomi API key")
    
    args = parser.parse_args()
    
    # Initialize generator
    generator = DuomiImageGenerator(api_key=args.api_key)
    
    results = []
    
    if args.source == "sqlite":
        logger.info("Generating images from SQLite database prompts...")
        results = generator.batch_generate_from_database(limit=args.limit, delay=args.delay)
        
    elif args.source == "json":
        logger.info(f"Generating images from JSON files in {args.input_dir}...")
        results = generator.batch_generate_from_json(json_dir=args.input_dir, delay=args.delay)
        
    elif args.source == "prompt":
        if not args.prompt:
            logger.error("--prompt argument is required when using 'prompt' source")
            sys.exit(1)
        
        logger.info("Generating image from single prompt...")
        result = generator.generate_image(args.prompt)
        result["source"] = "single_prompt"
        
        if result["success"]:
            saved_path = generator.save_generated_image(result, "single_prompt")
            result["saved_path"] = saved_path
        
        results = [result]
    
    # Save results
    if results:
        log_file = generator.save_results_log(results)
        
        # Print summary
        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful
        
        print(f"\n=== Generation Summary ===")
        print(f"Total processed: {len(results)}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Results saved to: {log_file}")
        print(f"Images saved to: {generator.output_dir}")
        
        if failed > 0:
            print(f"\nFailed generations:")
            for result in results:
                if not result["success"]:
                    print(f"  - {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()
