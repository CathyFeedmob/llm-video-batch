#!/usr/bin/env python3
"""
Script to rename images in img/ready directory with 6-character UUID-like identifiers.
Preserves file extensions and ensures no duplicate names.
"""

import os
import random
import string
from pathlib import Path

def generate_6char_id():
    """Generate a 6-character ID using letters and numbers."""
    characters = string.ascii_letters + string.digits  # a-z, A-Z, 0-9
    return ''.join(random.choices(characters, k=6))

def rename_images_in_ready():
    """Rename all images in img/ready directory with 6-character UUID-like IDs."""
    ready_dir = Path("img/ready")
    
    if not ready_dir.exists():
        print(f"Directory {ready_dir} does not exist!")
        return
    
    # Get all image files
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    image_files = []
    
    for file_path in ready_dir.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in image_extensions:
            image_files.append(file_path)
    
    if not image_files:
        print("No image files found in img/ready directory!")
        return
    
    print(f"Found {len(image_files)} image files to rename")
    
    # Keep track of used IDs to avoid duplicates
    used_ids = set()
    renamed_count = 0
    
    for old_path in image_files:
        # Generate unique 6-character ID
        while True:
            new_id = generate_6char_id()
            if new_id not in used_ids:
                used_ids.add(new_id)
                break
        
        # Create new filename with same extension
        new_filename = f"{new_id}{old_path.suffix}"
        new_path = ready_dir / new_filename
        
        try:
            # Rename the file
            old_path.rename(new_path)
            print(f"Renamed: {old_path.name} -> {new_filename}")
            renamed_count += 1
        except Exception as e:
            print(f"Error renaming {old_path.name}: {e}")
    
    print(f"\nSuccessfully renamed {renamed_count} out of {len(image_files)} files")

if __name__ == "__main__":
    print("Starting image renaming process...")
    rename_images_in_ready()
    print("Image renaming process completed!")
