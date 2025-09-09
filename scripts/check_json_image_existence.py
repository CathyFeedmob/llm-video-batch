#!/usr/bin/env python3
"""
Script to loop through JSON files in out/prompt_json/ and check if the corresponding
image exists in img/uploaded/ based on the pic_name field.
"""

import json
import os
from pathlib import Path

def check_json_image_existence():
    """Check if images exist for all JSON files."""
    json_dir = "out/prompt_json"
    uploaded_dir = "img/uploaded"
    
    # Get all JSON files (excluding the 'used' subdirectory)
    json_files = []
    for file in os.listdir(json_dir):
        if file.endswith('.json') and os.path.isfile(os.path.join(json_dir, file)):
            json_files.append(file)
    
    json_files.sort()
    
    print(f"Found {len(json_files)} JSON files to check")
    print("=" * 80)
    
    missing_images = []
    existing_images = []
    error_files = []
    
    for json_file in json_files:
        json_path = os.path.join(json_dir, json_file)
        
        try:
            # Read JSON file
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Get pic_name from JSON
            pic_name = data.get('pic_name')
            if not pic_name:
                print(f"❌ {json_file}: No 'pic_name' field found")
                error_files.append(json_file)
                continue
            
            # Check if image exists in uploaded directory
            image_path = os.path.join(uploaded_dir, pic_name)
            
            if os.path.exists(image_path):
                print(f"✅ {json_file}: {pic_name} EXISTS")
                existing_images.append((json_file, pic_name))
            else:
                print(f"❌ {json_file}: {pic_name} MISSING")
                missing_images.append((json_file, pic_name))
                
        except json.JSONDecodeError as e:
            print(f"❌ {json_file}: JSON decode error - {e}")
            error_files.append(json_file)
        except Exception as e:
            print(f"❌ {json_file}: Error - {e}")
            error_files.append(json_file)
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print(f"Total JSON files processed: {len(json_files)}")
    print(f"Images that exist: {len(existing_images)}")
    print(f"Images that are missing: {len(missing_images)}")
    print(f"Files with errors: {len(error_files)}")
    
    if missing_images:
        print(f"\n📋 MISSING IMAGES ({len(missing_images)}):")
        for json_file, pic_name in missing_images:
            print(f"  - {json_file} → {pic_name}")
    
    if error_files:
        print(f"\n⚠️  ERROR FILES ({len(error_files)}):")
        for error_file in error_files:
            print(f"  - {error_file}")
    
    # Check for orphaned images (images without corresponding JSON)
    print(f"\n🔍 CHECKING FOR ORPHANED IMAGES...")
    
    # Get all images in uploaded directory
    uploaded_images = set()
    for file in os.listdir(uploaded_dir):
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
            uploaded_images.add(file)
    
    # Get all pic_names from JSON files
    json_pic_names = set()
    for json_file, pic_name in existing_images:
        json_pic_names.add(pic_name)
    for json_file, pic_name in missing_images:
        json_pic_names.add(pic_name)
    
    # Find orphaned images
    orphaned_images = uploaded_images - json_pic_names
    
    print(f"Total images in uploaded directory: {len(uploaded_images)}")
    print(f"Images referenced by JSON files: {len(json_pic_names)}")
    print(f"Orphaned images (no JSON): {len(orphaned_images)}")
    
    if orphaned_images:
        print(f"\n🗂️  ORPHANED IMAGES ({len(orphaned_images)}):")
        for orphaned in sorted(orphaned_images):
            print(f"  - {orphaned}")

if __name__ == "__main__":
    check_json_image_existence()
