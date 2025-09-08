#!/usr/bin/env python3
"""
Convert JSON files from out/prompt_json directory to SQLite database records.
Updates images, prompts, and videos tables with appropriate status values.

Based on analysis of generate_video_duomi_v2.py and parse_image_and_generate_json.py:
- Image status should be 'success' (already processed and uploaded)
- Video status should be 'pending' (ready for video generation)
"""

import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path

def get_db_connection():
    """Get database connection."""
    db_path = "data/llm_video_batch.db"
    return sqlite3.connect(db_path)

def parse_filename_for_descriptive_name(filename):
    """Extract descriptive name from filename."""
    # Remove timestamp and extension
    name = filename.replace('.json', '').replace('.jpg', '').replace('.mp4', '')
    # Find the last underscore followed by timestamp pattern
    parts = name.split('_')
    if len(parts) >= 3:
        # Remove the last 3 parts (date and time components)
        descriptive_parts = parts[:-3]
        return '_'.join(descriptive_parts).replace('_', ' ').title()
    return name.replace('_', ' ').title()

def find_or_create_image_record(cursor, pic_name, image_url, image_size, descriptive_name):
    """Find existing image record or create new one."""
    
    # First try to find by descriptive name or filename
    cursor.execute("""
        SELECT id FROM images 
        WHERE descriptive_name = ? OR original_filename = ? OR uploaded_filename = ?
    """, (descriptive_name, pic_name, pic_name))
    
    result = cursor.fetchone()
    if result:
        image_id = result[0]
        # Update the record with new information
        cursor.execute("""
            UPDATE images 
            SET upload_url = ?, 
                uploaded_filename = ?,
                status = 'success',
                descriptive_name = ?,
                updated_at = datetime('now')
            WHERE id = ?
        """, (image_url, pic_name, descriptive_name, image_id))
        return image_id
    
    # Create new image record with 'success' status (already processed)
    cursor.execute("""
        INSERT INTO images (
            original_filename, upload_url, uploaded_filename, 
            status, descriptive_name, created_at, updated_at
        ) VALUES (?, ?, ?, 'success', ?, datetime('now'), datetime('now'))
    """, (pic_name, image_url, pic_name, descriptive_name))
    
    return cursor.lastrowid

def create_prompt_record(cursor, image_id, json_data):
    """Create prompt record with all prompt variations."""
    
    # Check if prompt record already exists for this image
    cursor.execute("SELECT id FROM prompts WHERE image_id = ?", (image_id,))
    existing = cursor.fetchone()
    
    if existing:
        # Update existing record
        cursor.execute("""
            UPDATE prompts SET
                image_prompt = ?, video_prompt = ?, refined_video_prompt = ?,
                creative_video_prompt_1 = ?, creative_video_prompt_2 = ?, creative_video_prompt_3 = ?,
                updated_at = datetime('now')
            WHERE image_id = ?
        """, (
            json_data.get('image_prompt'),
            json_data.get('video_prompt'),
            json_data.get('refined_video_prompt'),
            json_data.get('creative_video_prompt_1'),
            json_data.get('creative_video_prompt_2'),
            json_data.get('creative_video_prompt_3'),
            image_id
        ))
        return existing[0]
    else:
        # Create new record
        cursor.execute("""
            INSERT INTO prompts (
                image_id, image_prompt, video_prompt, refined_video_prompt,
                creative_video_prompt_1, creative_video_prompt_2, creative_video_prompt_3,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (
            image_id,
            json_data.get('image_prompt'),
            json_data.get('video_prompt'),
            json_data.get('refined_video_prompt'),
            json_data.get('creative_video_prompt_1'),
            json_data.get('creative_video_prompt_2'),
            json_data.get('creative_video_prompt_3')
        ))
        
        return cursor.lastrowid

def create_video_record(cursor, image_id, prompt_id, json_data):
    """Create video record with pending status (ready for generation)."""
    video_name = json_data.get('video_name')
    video_path = f"out/{video_name}" if video_name else None
    
    # Check if video file exists to get file size
    file_size = None
    if video_path and os.path.exists(video_path):
        file_size = os.path.getsize(video_path)
    
    # Check if video record already exists for this image
    cursor.execute("SELECT id FROM videos WHERE image_id = ?", (image_id,))
    existing = cursor.fetchone()
    
    if existing:
        # Update existing record
        cursor.execute("""
            UPDATE videos SET
                prompt_id = ?, video_filename = ?, video_path = ?,
                prompt_used = ?, prompt_type = 'base', file_size_bytes = ?, 
                status = 'pending'
            WHERE image_id = ?
        """, (
            prompt_id, video_name, video_path,
            json_data.get('video_prompt'), file_size, image_id
        ))
        return existing[0]
    else:
        # Create new record with 'pending' status (ready for video generation)
        cursor.execute("""
            INSERT INTO videos (
                image_id, prompt_id, video_filename, video_path,
                prompt_used, prompt_type, file_size_bytes, status,
                created_at
            ) VALUES (?, ?, ?, ?, ?, 'base', ?, 'pending', datetime('now'))
        """, (
            image_id, prompt_id, video_name, video_path,
            json_data.get('video_prompt'), file_size
        ))
        
        return cursor.lastrowid

def process_json_files():
    """Process all JSON files in out/prompt_json directory."""
    json_dir = Path("out/prompt_json")
    
    if not json_dir.exists():
        print(f"Directory {json_dir} does not exist!")
        return
    
    # Get all JSON files (excluding used directory)
    json_files = [f for f in json_dir.glob("*.json") if f.is_file()]
    print(f"Found {len(json_files)} JSON files to process")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    processed_count = 0
    updated_count = 0
    error_count = 0
    
    try:
        for json_file in json_files:
            try:
                print(f"Processing: {json_file.name}")
                
                # Load JSON data
                with open(json_file, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                
                # Extract information
                pic_name = json_data.get('pic_name')
                image_url = json_data.get('image_url')
                image_size = json_data.get('image_size')
                
                if not pic_name:
                    print(f"  Warning: No pic_name found in {json_file.name}")
                    continue
                
                # Generate descriptive name
                descriptive_name = parse_filename_for_descriptive_name(pic_name)
                
                # Find or create image record
                image_id = find_or_create_image_record(
                    cursor, pic_name, image_url, image_size, descriptive_name
                )
                print(f"  Image ID: {image_id}")
                
                # Create/update prompt record
                prompt_id = create_prompt_record(cursor, image_id, json_data)
                print(f"  Prompt ID: {prompt_id}")
                
                # Create/update video record
                video_id = create_video_record(cursor, image_id, prompt_id, json_data)
                print(f"  Video ID: {video_id}")
                
                processed_count += 1
                
            except Exception as e:
                print(f"  Error processing {json_file.name}: {str(e)}")
                error_count += 1
                continue
        
        # Commit all changes
        conn.commit()
        print(f"\nProcessing complete!")
        print(f"Successfully processed: {processed_count} files")
        print(f"Errors: {error_count} files")
        
    except Exception as e:
        print(f"Database error: {str(e)}")
        conn.rollback()
    finally:
        conn.close()

def verify_database_status():
    """Verify the database records and their statuses."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check image statuses
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM images 
            GROUP BY status 
            ORDER BY status
        """)
        image_statuses = cursor.fetchall()
        
        print("\nImage Status Summary:")
        for status, count in image_statuses:
            print(f"  {status}: {count}")
        
        # Check video statuses
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM videos 
            GROUP BY status 
            ORDER BY status
        """)
        video_statuses = cursor.fetchall()
        
        print("\nVideo Status Summary:")
        for status, count in video_statuses:
            print(f"  {status}: {count}")
        
        # Check total counts
        cursor.execute("SELECT COUNT(*) FROM images")
        total_images = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM prompts")
        total_prompts = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM videos")
        total_videos = cursor.fetchone()[0]
        
        print(f"\nTotal Records:")
        print(f"  Images: {total_images}")
        print(f"  Prompts: {total_prompts}")
        print(f"  Videos: {total_videos}")
        
        # Show some sample records
        cursor.execute("""
            SELECT i.id, i.descriptive_name, i.status as img_status, v.status as vid_status
            FROM images i
            LEFT JOIN videos v ON i.id = v.image_id
            LIMIT 5
        """)
        samples = cursor.fetchall()
        
        print(f"\nSample Records:")
        for img_id, desc_name, img_status, vid_status in samples:
            print(f"  ID {img_id}: {desc_name} | Image: {img_status} | Video: {vid_status}")
        
    except Exception as e:
        print(f"Error verifying database: {str(e)}")
    finally:
        conn.close()

def main():
    """Main function."""
    print("Starting JSON to database conversion...")
    print("=" * 50)
    
    # Process JSON files
    process_json_files()
    
    print("\n" + "=" * 50)
    print("Verifying database records...")
    
    # Verify the results
    verify_database_status()
    
    print("\n" + "=" * 50)
    print("Conversion complete!")
    print("\nStatus Summary:")
    print("- Images: 'success' (already processed and uploaded)")
    print("- Videos: 'pending' (ready for video generation)")

if __name__ == "__main__":
    main()
