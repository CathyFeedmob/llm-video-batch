#!/usr/bin/env python3
"""
Update Existing JSON Files with New Video Prompt Fields

This script adds the missing fields to existing JSON files:
- refined_video_prompt
- creative_video_prompt_1 (aggressive/dynamic movement)
- creative_video_prompt_2 (surreal/impossible movement)  
- creative_video_prompt_3 (cinematic/dramatic movement)

Usage:
    python3 scripts/update_existing_json.py [--dry-run] [--backup]
    
Options:
    --dry-run: Show what would be updated without making changes
    --backup: Create backup copies before updating files
"""

import os
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
import time

# Import existing modules
from openrouter_base import OpenRouterClient

class JSONUpdater:
    """Updates existing JSON files with new video prompt fields."""
    
    def __init__(self, dry_run: bool = False, backup: bool = False):
        """
        Initialize the JSON updater.
        
        Args:
            dry_run: If True, show what would be updated without making changes
            backup: If True, create backup copies before updating files
        """
        self.dry_run = dry_run
        self.backup = backup
        self.openrouter_client = OpenRouterClient()
        
        # Directories to scan - only active files, not processed ones
        self.json_dirs = [
            Path("out/prompt_json")
        ]
        
        # Required new fields
        self.new_fields = [
            "refined_video_prompt",
            "creative_video_prompt_1", 
            "creative_video_prompt_2",
            "creative_video_prompt_3"
        ]
        
        # Statistics
        self.stats = {
            "total_files": 0,
            "files_needing_update": 0,
            "files_updated": 0,
            "files_failed": 0,
            "files_skipped": 0
        }
    
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
            
            print(f"  🔄 Refining prompt...")
            result = self.openrouter_client.generate_content(
                prompt=refine_prompt,
                api_source="openrouter"
            )
            
            if result.success and result.content:
                refined_prompt = result.content.strip()
                print(f"  ✅ Refined prompt generated")
                return refined_prompt
            else:
                print(f"  ❌ Prompt refinement failed: {result.error}")
                return original_prompt
                
        except Exception as e:
            print(f"  ❌ Error refining prompt: {e}")
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
                print(f"  🔄 Generating {prompt_type} creative movement prompt...")
                result = self.openrouter_client.generate_content(
                    prompt=prompt_text,
                    image_url=image_url,
                    api_source="openrouter"
                )
                
                if result.success and result.content:
                    creative_prompts.append(result.content.strip())
                    print(f"  ✅ {prompt_type.capitalize()} prompt generated")
                else:
                    print(f"  ❌ {prompt_type.capitalize()} prompt generation failed: {result.error}")
                    # Fallback prompt
                    creative_prompts.append(f"Enhanced {prompt_type} movement based on: {base_prompt}")
                    
            except Exception as e:
                print(f"  ❌ Error generating {prompt_type} prompt: {e}")
                creative_prompts.append(f"Enhanced {prompt_type} movement based on: {base_prompt}")
        
        return creative_prompts
    
    def needs_update(self, json_data: Dict[str, Any]) -> bool:
        """
        Check if a JSON file needs updating (missing any of the new fields).
        
        Args:
            json_data: JSON data to check
            
        Returns:
            True if file needs updating, False otherwise
        """
        for field in self.new_fields:
            if field not in json_data:
                return True
        return False
    
    def create_backup(self, file_path: Path) -> bool:
        """
        Create a backup copy of the file.
        
        Args:
            file_path: Path to file to backup
            
        Returns:
            True if backup created successfully, False otherwise
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = file_path.with_suffix(f".backup_{timestamp}.json")
            shutil.copy2(file_path, backup_path)
            print(f"  📋 Backup created: {backup_path.name}")
            return True
        except Exception as e:
            print(f"  ❌ Failed to create backup: {e}")
            return False
    
    def update_json_file(self, file_path: Path) -> bool:
        """
        Update a single JSON file with missing fields.
        
        Args:
            file_path: Path to JSON file to update
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            # Load existing JSON data
            with open(file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            # Check if update is needed
            if not self.needs_update(json_data):
                print(f"  ⏭️ File already has all new fields, skipping")
                self.stats["files_skipped"] += 1
                return True
            
            # Verify required fields exist
            required_fields = ["video_prompt", "image_url"]
            for field in required_fields:
                if field not in json_data:
                    print(f"  ❌ Missing required field '{field}', skipping file")
                    self.stats["files_failed"] += 1
                    return False
            
            if self.dry_run:
                print(f"  🔍 [DRY RUN] Would update with missing fields: {[f for f in self.new_fields if f not in json_data]}")
                return True
            
            # Create backup if requested
            if self.backup and not self.create_backup(file_path):
                print(f"  ❌ Backup failed, skipping update for safety")
                self.stats["files_failed"] += 1
                return False
            
            # Generate missing fields
            base_video_prompt = json_data["video_prompt"]
            image_url = json_data["image_url"]
            
            # Generate refined prompt if missing
            if "refined_video_prompt" not in json_data:
                json_data["refined_video_prompt"] = self.refine_prompt_with_openrouter(base_video_prompt)
            
            # Generate creative prompts if missing
            missing_creative = [f for f in ["creative_video_prompt_1", "creative_video_prompt_2", "creative_video_prompt_3"] if f not in json_data]
            if missing_creative:
                creative_prompts = self.generate_creative_movement_prompts(image_url, base_video_prompt)
                
                if "creative_video_prompt_1" not in json_data:
                    json_data["creative_video_prompt_1"] = creative_prompts[0] if len(creative_prompts) > 0 else "Enhanced aggressive movement"
                if "creative_video_prompt_2" not in json_data:
                    json_data["creative_video_prompt_2"] = creative_prompts[1] if len(creative_prompts) > 1 else "Enhanced surreal movement"
                if "creative_video_prompt_3" not in json_data:
                    json_data["creative_video_prompt_3"] = creative_prompts[2] if len(creative_prompts) > 2 else "Enhanced cinematic movement"
            
            # Save updated JSON
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            print(f"  ✅ File updated successfully")
            self.stats["files_updated"] += 1
            return True
            
        except Exception as e:
            print(f"  ❌ Error updating file: {e}")
            self.stats["files_failed"] += 1
            return False
    
    def find_json_files(self) -> List[Path]:
        """
        Find all JSON files in the target directories.
        
        Returns:
            List of JSON file paths
        """
        json_files = []
        
        for json_dir in self.json_dirs:
            if json_dir.exists():
                for file_path in json_dir.glob("*.json"):
                    # Skip error files
                    if file_path.name.lower().startswith("error_message"):
                        continue
                    json_files.append(file_path)
                print(f"📁 Found {len([f for f in json_dir.glob('*.json') if not f.name.lower().startswith('error_message')])} JSON files in {json_dir}")
            else:
                print(f"📁 Directory {json_dir} does not exist")
        
        return sorted(json_files)
    
    def update_all_files(self) -> None:
        """Update all JSON files that need the new fields."""
        print(f"🔍 Scanning for JSON files to update...")
        json_files = self.find_json_files()
        
        if not json_files:
            print("No JSON files found to process.")
            return
        
        self.stats["total_files"] = len(json_files)
        
        # First pass: count files needing update
        files_needing_update = []
        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                if self.needs_update(json_data):
                    files_needing_update.append(file_path)
            except Exception as e:
                print(f"❌ Error reading {file_path}: {e}")
                continue
        
        self.stats["files_needing_update"] = len(files_needing_update)
        
        if not files_needing_update:
            print("✅ All JSON files already have the new fields!")
            return
        
        print(f"\n📊 Summary:")
        print(f"   Total JSON files found: {self.stats['total_files']}")
        print(f"   Files needing update: {self.stats['files_needing_update']}")
        
        if self.dry_run:
            print(f"\n🔍 DRY RUN MODE - No files will be modified")
        else:
            print(f"\n🚀 Starting update process...")
        
        # Update files
        for i, file_path in enumerate(files_needing_update, 1):
            print(f"\n{'='*60}")
            print(f"Processing file {i}/{len(files_needing_update)}: {file_path.name}")
            print(f"{'='*60}")
            
            self.update_json_file(file_path)
            
            # Small delay to avoid overwhelming the API
            if not self.dry_run:
                time.sleep(1)
        
        # Final summary
        print(f"\n{'='*60}")
        print(f"UPDATE COMPLETE")
        print(f"{'='*60}")
        print(f"Total files: {self.stats['total_files']}")
        print(f"Files needing update: {self.stats['files_needing_update']}")
        print(f"Files updated: {self.stats['files_updated']}")
        print(f"Files failed: {self.stats['files_failed']}")
        print(f"Files skipped: {self.stats['files_skipped']}")
        
        if self.stats['files_updated'] > 0:
            print(f"\n✅ Successfully updated {self.stats['files_updated']} JSON files with new video prompt fields!")
        if self.stats['files_failed'] > 0:
            print(f"\n⚠️ {self.stats['files_failed']} files failed to update - check the logs above")

def main():
    """Main function to run the JSON updater."""
    parser = argparse.ArgumentParser(description="Update existing JSON files with new video prompt fields")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without making changes")
    parser.add_argument("--backup", action="store_true", help="Create backup copies before updating files")
    
    args = parser.parse_args()
    
    print("🔄 JSON File Updater - Adding New Video Prompt Fields")
    print("=" * 60)
    
    if args.dry_run:
        print("🔍 Running in DRY RUN mode - no files will be modified")
    if args.backup:
        print("📋 Backup mode enabled - creating backups before updates")
    
    updater = JSONUpdater(dry_run=args.dry_run, backup=args.backup)
    updater.update_all_files()

if __name__ == "__main__":
    main()
