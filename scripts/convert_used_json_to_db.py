#!/usr/bin/env python3
"""
Convert JSON files from out/prompt_json/used/ directory to SQLite database records.
Updates images, prompts, and videos tables with appropriate status values.
Uses logs/image_uploading.csv and logs/video_generation_log.jsonl to match files and set correct statuses.
Creates a legacy placeholder image_id only for prompts that truly have no reference images.

This script specifically processes the 'used' directory which contains processed JSON files.
"""

import os
import json
import sqlite3
import csv
from datetime import datetime
from pathlib import Path

def get_db_connection():
    """Get database connection."""
    db_path = "data/llm_video_batch.db"
    return sqlite3.connect(db_path)

def parse_filename_for_descriptive_name(filename):
    """Extract descriptive name from filename."""
    # Remove timestamp and extension
    name = filename.replace('.json', '').replace('.jpg', '').replace('.jpeg', '').replace('.mp4', '')
    # Find the last underscore followed by timestamp pattern
    parts = name.split('_')
    if len(parts) >= 3:
        # Remove the last 3 parts (date and time components)
        descriptive_parts = parts[:-3]
        return '_'.join(descriptive_parts).replace('_', ' ').title()
    return name.replace('_', ' ').title()

def load_image_upload_logs():
    """Load image upload logs to match JSON files with uploaded images."""
    log_file = Path("logs/image_uploading.csv")
    image_logs = {}
    
    if not log_file.exists():
        print("Warning: image_uploading.csv not found")
        return image_logs
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                json_filename = row.get('json_filename', '').strip()
                if json_filename and json_filename.endswith('.json'):
                    # Remove .json extension for matching
                    json_base = json_filename.replace('.json', '')
                    image_logs[json_base] = {
                        'original_filename': row.get('original_filename'),
                        'upload_url': row.get('upload_url'),
                        'file_size_bytes': row.get('file_size_bytes'),
                        'downloaded_filename': row.get('downloaded_filename'),
                        'processing_time_seconds': row.get('processing_time_seconds'),
                        'status': row.get('status'),
                        'timestamp': row.get('timestamp')
                    }
    
    except Exception as e:
        print(f"Error loading image upload logs: {str(e)}")
    
    print(f"Loaded {len(image_logs)} image upload log entries")
    return image_logs

def load_video_generation_logs():
    """Load video generation logs to determine video statuses."""
    log_file = Path("logs/video_generation_log.jsonl")
    video_logs = {}
    
    if not log_file.exists():
        print("Warning: video_generation_log.jsonl not found")
        return video_logs
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    log_entry = json.loads(line.strip())
                    video_name = log_entry.get('video_name')
                    json_file_path = log_entry.get('json_file_path')
                    
                    if video_name and video_name != 'N/A':
                        # Extract base filename for matching
                        video_base = video_name.replace('out/', '').replace('.mp4', '')
                        video_logs[video_base] = {
                            'status': 'completed' if log_entry.get('status') == 'success' else 'failed',
                            'generation_time_seconds': log_entry.get('processing_duration_seconds'),
                            'json_file_path': json_file_path,
                            'timestamp': log_entry.get('timestamp'),
                            'image_used': log_entry.get('image_used')
                        }
    
    except Exception as e:
        print(f"Error loading video generation logs: {str(e)}")
    
    print(f"Loaded {len(video_logs)} video generation log entries")
    return video_logs

def get_or_create_legacy_image_id(cursor):
    """Get or create a placeholder image record for legacy/migrated prompts without reference images."""
    
    # Check if legacy placeholder already exists
    cursor.execute("""
        SELECT id FROM images 
        WHERE descriptive_name = 'Legacy System Migration' 
        AND original_filename = 'legacy_placeholder'
    """)
    
    result = cursor.fetchone()
    if result:
        return result[0]
    
    # Create legacy placeholder image record
    cursor.execute("""
        INSERT INTO images (
            original_filename, descriptive_name, status, 
            created_at, updated_at
        ) VALUES ('legacy_placeholder', 'Legacy System Migration', 'legacy', datetime('now'), datetime('now'))
    """)
    
    return cursor.lastrowid

def find_or_create_image_record(cursor, pic_name, image_url, descriptive_name, image_logs, json_base_name):
    """Find existing image record or create new one using upload logs."""
    
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
    
    # Check if we have upload log data for this JSON file
    upload_data = image_logs.get(json_base_name)
    if upload_data:
        # Use data from upload logs
        original_filename = upload_data.get('original_filename', pic_name)
        upload_url = upload_data.get('upload_url', image_url)
        file_size = upload_data.get('file_size_bytes')
        processing_time = upload_data.get('processing_time_seconds')
        
        # Convert file_size and processing_time to appropriate types
        try:
            file_size = int(file_size) if file_size else None
        except (ValueError, TypeError):
            file_size = None
            
        try:
            processing_time = float(processing_time) if processing_time else None
        except (ValueError, TypeError):
            processing_time = None
        
        # Create new image record with upload log data
        cursor.execute("""
            INSERT INTO images (
                original_filename, upload_url, uploaded_filename, 
                file_size_bytes, processing_time_seconds,
                status, descriptive_name, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'success', ?, datetime('now'), datetime('now'))
        """, (original_filename, upload_url, pic_name, file_size, processing_time, descriptive_name))
    else:
        # Create new image record with basic data
        cursor.execute("""
            INSERT INTO images (
                original_filename, upload_url, uploaded_filename, 
                status, descriptive_name, created_at, updated_at
            ) VALUES (?, ?, ?, 'success', ?, datetime('now'), datetime('now'))
        """, (pic_name, image_url, pic_name, descriptive_name))
    
    return cursor.lastrowid

def create_prompt_record(cursor, image_id, json_data, json_filename):
    """Create prompt record with all prompt variations.
    
    Args:
        cursor: Database cursor
        image_id: ID of associated image (real or legacy placeholder)
        json_data: JSON data containing prompts
        json_filename: Name of the JSON file for identification
    """
    
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

def create_video_record(cursor, image_id, prompt_id, json_data, video_logs):
    """Create video record with status from generation logs.
    
    Args:
        cursor: Database cursor
        image_id: ID of associated image
        prompt_id: ID of associated prompt
        json_data: JSON data containing video information
        video_logs: Dictionary of video generation log data
    """
    video_name = json_data.get('video_name')
    video_path = f"out/{video_name}" if video_name else None
    
    # Check if video file exists to get file size
    file_size = None
    if video_path and os.path.exists(video_path):
        file_size = os.path.getsize(video_path)
    
    # Determine video status from logs
    video_status = 'pending'  # default
    generation_time = None
    generation_service = None
    
    if video_name:
        video_base = video_name.replace('.mp4', '')
        if video_base in video_logs:
            log_data = video_logs[video_base]
            video_status = log_data['status']
            generation_time = log_data.get('generation_time_seconds')
            # Assume duomi service based on the logs pattern
            generation_service = 'duomi'
    
    # Check if video record already exists for this image
    cursor.execute("SELECT id FROM videos WHERE image_id = ?", (image_id,))
    existing = cursor.fetchone()
    
    if existing:
        # Update existing record (no updated_at column in videos table)
        cursor.execute("""
            UPDATE videos SET
                prompt_id = ?, video_filename = ?, video_path = ?,
                prompt_used = ?, prompt_type = 'base', file_size_bytes = ?, 
                status = ?, generation_time_seconds = ?, generation_service = ?
            WHERE image_id = ?
        """, (
            prompt_id, video_name, video_path,
            json_data.get('video_prompt'), file_size, video_status, generation_time, generation_service, image_id
        ))
        return existing[0]
    
    # Create new record with status from logs
    cursor.execute("""
        INSERT INTO videos (
            image_id, prompt_id, video_filename, video_path,
            prompt_used, prompt_type, file_size_bytes, status,
            generation_time_seconds, generation_service, created_at
        ) VALUES (?, ?, ?, ?, ?, 'base', ?, ?, ?, ?, datetime('now'))
    """, (
        image_id,
        prompt_id, video_name, video_path,
        json_data.get('video_prompt'), file_size, video_status, generation_time, generation_service
    ))
    
    return cursor.lastrowid

def process_used_json_files():
    """Process all JSON files in out/prompt_json/used directory."""
    json_dir = Path("out/prompt_json/used")
    
    if not json_dir.exists():
        print(f"Directory {json_dir} does not exist!")
        return
    
    # Load log data
    print("Loading log data...")
    image_logs = load_image_upload_logs()
    video_logs = load_video_generation_logs()
    
    # Get all JSON files
    json_files = [f for f in json_dir.glob("*.json") if f.is_file()]
    print(f"Found {len(json_files)} JSON files to process in used directory")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    processed_count = 0
    error_count = 0
    no_reference_count = 0
    legacy_image_id = None
    
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
                json_base_name = json_file.stem  # filename without extension
                
                # Check if this JSON has reference to actual image or video
                has_reference = has_reference_image_or_video(json_data)
                
                # Try to find image data in upload logs first
                upload_data = image_logs.get(json_base_name)
                
                image_id = None
                if has_reference and (pic_name or upload_data):
                    # Generate descriptive name
                    descriptive_name = parse_filename_for_descriptive_name(pic_name or json_base_name)
                    
                    # Find or create image record using upload logs
                    image_id = find_or_create_image_record(
                        cursor, pic_name, image_url, descriptive_name, image_logs, json_base_name
                    )
                    print(f"  Image ID: {image_id}")
                elif upload_data:
                    # We have upload data but no direct reference - still create image record
                    descriptive_name = parse_filename_for_descriptive_name(json_base_name)
                    image_id = find_or_create_image_record(
                        cursor, upload_data.get('downloaded_filename'), upload_data.get('upload_url'), 
                        descriptive_name, image_logs, json_base_name
                    )
                    print(f"  Image ID from upload logs: {image_id}")
                else:
                    # No reference image/video found - use legacy placeholder
                    if legacy_image_id is None:
                        legacy_image_id = get_or_create_legacy_image_id(cursor)
                    image_id = legacy_image_id
                    print(f"  Using legacy placeholder image ID: {image_id}")
                    no_reference_count += 1
                
                # Create/update prompt record
                prompt_id = create_prompt_record(cursor, image_id, json_data, json_file.name)
                print(f"  Prompt ID: {prompt_id}")
                
                # Create/update video record with status from logs
                video_id = create_video_record(cursor, image_id, prompt_id, json_data, video_logs)
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
        print(f"Files using legacy placeholder: {no_reference_count} files")
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
        
        # Check prompts with legacy vs real image references
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN i.descriptive_name = 'Legacy System Migration' THEN 'Legacy Placeholder' 
                    ELSE 'Real Image Reference' 
                END as ref_type,
                COUNT(*) as count 
            FROM prompts p
            JOIN images i ON p.image_id = i.id
            GROUP BY CASE 
                WHEN i.descriptive_name = 'Legacy System Migration' THEN 'Legacy Placeholder' 
                ELSE 'Real Image Reference' 
            END
            ORDER BY ref_type
        """)
        prompt_refs = cursor.fetchall()
        
        print("\nPrompt Reference Summary:")
        for ref_type, count in prompt_refs:
            print(f"  {ref_type}: {count}")
        
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
        
        # Show some sample records with legacy placeholder
        cursor.execute("""
            SELECT p.id, p.video_prompt, i.descriptive_name
            FROM prompts p
            JOIN images i ON p.image_id = i.id
            WHERE i.descriptive_name = 'Legacy System Migration'
            LIMIT 5
        """)
        legacy_samples = cursor.fetchall()
        
        if legacy_samples:
            print(f"\nSample Records with Legacy Placeholder:")
            for prompt_id, video_prompt, desc_name in legacy_samples:
                prompt_preview = (video_prompt[:50] + '...') if video_prompt and len(video_prompt) > 50 else video_prompt
                print(f"  Prompt ID {prompt_id}: '{prompt_preview}'")
        
        # Show some sample records with real image references
        cursor.execute("""
            SELECT i.id, i.descriptive_name, i.status as img_status, v.status as vid_status
            FROM images i
            LEFT JOIN videos v ON i.id = v.image_id
            WHERE i.descriptive_name != 'Legacy System Migration'
            LIMIT 5
        """)
        samples = cursor.fetchall()
        
        print(f"\nSample Records with Real Image References:")
        for img_id, desc_name, img_status, vid_status in samples:
            print(f"  ID {img_id}: {desc_name} | Image: {img_status} | Video: {vid_status}")
        
    except Exception as e:
        print(f"Error verifying database: {str(e)}")
    finally:
        conn.close()

def has_reference_image_or_video(json_data):
    """Check if JSON data contains reference to an actual image or video."""
    # Check for image URL (indicates uploaded image)
    image_url = json_data.get('image_url', '').strip()
    if image_url and image_url != '' and not image_url.lower() in ['none', 'null', 'undefined']:
        return True
    
    # Check for pic_name (indicates image file)
    pic_name = json_data.get('pic_name', '').strip()
    if pic_name and pic_name != '' and not pic_name.lower() in ['none', 'null', 'undefined']:
        # Verify the image file actually exists
        possible_paths = [
            f"img/{pic_name}",
            f"out/{pic_name}",
            f"data/{pic_name}",
            pic_name  # relative to current directory
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return True
    
    # Check for video_name (indicates video file)
    video_name = json_data.get('video_name', '').strip()
    if video_name and video_name != '' and not video_name.lower() in ['none', 'null', 'undefined']:
        # Verify the video file actually exists
        possible_paths = [
            f"out/{video_name}",
            f"data/{video_name}",
            video_name  # relative to current directory
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return True
    
    return False

def main():
    """Main function."""
    print("Starting JSON to database conversion for 'used' directory...")
    print("=" * 60)
    
    # Process JSON files from used directory
    process_used_json_files()
    
    print("\n" + "=" * 60)
    print("Verifying database records...")
    
    # Verify the results
    verify_database_status()
    
    print("\n" + "=" * 60)
    print("Conversion complete!")
    print("\nStatus Summary:")
    print("- Images: 'success' (already processed and uploaded) or 'legacy' (placeholder)")
    print("- Videos: Status from generation logs ('completed', 'failed', or 'pending')")
    print("- Prompts without reference images: use legacy placeholder image_id")

if __name__ == "__main__":
    main()
