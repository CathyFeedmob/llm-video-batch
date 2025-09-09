#!/usr/bin/env python3
"""
Test script to fix failed images by copying them from processed_path to uploaded_path
and updating their status in the database. This version processes only 5 images for testing.
"""

import sqlite3
import os
import shutil
from pathlib import Path

def connect_db():
    """Connect to the SQLite database."""
    return sqlite3.connect('data/llm_video_batch.db')

def get_failed_images(limit=5):
    """Get first 5 failed images that have processed_path but need fixing."""
    conn = connect_db()
    cursor = conn.cursor()
    
    query = """
    SELECT id, original_filename, processed_path, uploaded_path, status 
    FROM images 
    WHERE processed_path IS NOT NULL 
    AND status = 'failed' 
    ORDER BY id
    LIMIT ?
    """
    
    cursor.execute(query, (limit,))
    results = cursor.fetchall()
    conn.close()
    
    return results

def copy_and_fix_image(image_record):
    """Copy image from processed_path to uploaded_path and update database."""
    image_id, original_filename, processed_path, uploaded_path, status = image_record
    
    print(f"Processing image ID {image_id}: {original_filename}")
    print(f"  From: {processed_path}")
    print(f"  To: {uploaded_path}")
    
    # Check if processed file exists
    if not os.path.exists(processed_path):
        print(f"  ERROR: Processed file not found: {processed_path}")
        return False
    
    # Check if uploaded file already exists
    if os.path.exists(uploaded_path):
        print(f"  INFO: Uploaded file already exists: {uploaded_path}")
        # Still update status since file exists
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE images 
            SET status = 'completed', 
                updated_at = datetime('now')
            WHERE id = ?
        """, (image_id,))
        conn.commit()
        conn.close()
        print(f"  SUCCESS: Updated database status to 'completed' for ID {image_id}")
        return True
    
    # Create uploaded directory if it doesn't exist
    uploaded_dir = os.path.dirname(uploaded_path)
    os.makedirs(uploaded_dir, exist_ok=True)
    
    try:
        # Copy the file from processed to uploaded location
        shutil.copy2(processed_path, uploaded_path)
        print(f"  SUCCESS: Copied file")
        
        # Verify the copy was successful
        if os.path.exists(uploaded_path):
            file_size = os.path.getsize(uploaded_path)
            print(f"  SUCCESS: File copied successfully, size: {file_size} bytes")
            
            # Update database status to 'completed'
            conn = connect_db()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE images 
                SET status = 'completed', 
                    updated_at = datetime('now')
                WHERE id = ?
            """, (image_id,))
            
            conn.commit()
            conn.close()
            
            print(f"  SUCCESS: Updated database status to 'completed' for ID {image_id}")
            return True
        else:
            print(f"  ERROR: File copy verification failed")
            return False
        
    except Exception as e:
        print(f"  ERROR: Failed to copy file: {e}")
        return False

def main():
    """Main function to fix first 5 failed images."""
    print("Starting failed images fix process (TEST - 5 images only)...")
    
    # Get first 5 failed images
    failed_images = get_failed_images(5)
    print(f"Found {len(failed_images)} failed images to process")
    
    if not failed_images:
        print("No failed images found. Nothing to do.")
        return
    
    success_count = 0
    error_count = 0
    
    # Process each failed image
    for i, image_record in enumerate(failed_images, 1):
        print(f"\n--- Processing image {i}/{len(failed_images)} ---")
        if copy_and_fix_image(image_record):
            success_count += 1
        else:
            error_count += 1
    
    print(f"\n=== TEST PROCESS COMPLETED ===")
    print(f"Successfully fixed: {success_count} images")
    print(f"Errors encountered: {error_count} images")
    
    # Show final status
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM images WHERE status = 'failed' AND processed_path IS NOT NULL")
    remaining_failed = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM images WHERE status = 'completed'")
    total_completed = cursor.fetchone()[0]
    conn.close()
    
    print(f"Remaining failed images with processed_path: {remaining_failed}")
    print(f"Total completed images: {total_completed}")

if __name__ == "__main__":
    main()
