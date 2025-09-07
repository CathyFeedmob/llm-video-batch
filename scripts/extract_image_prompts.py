#!/usr/bin/env python3
"""
Extract image_id and video_prompt from SQLite database and generate CSV file.
"""

import sqlite3
import csv
import os
from pathlib import Path

def extract_video_prompts_to_csv():
    """Extract image_id and video_prompt from the prompts table and save to CSV."""
    
    # Database path
    db_path = Path(__file__).parent.parent / "data" / "llm_video_batch.db"
    
    # Output CSV path in docs directory
    output_path = Path(__file__).parent.parent / "docs" / "video_prompts_extract.csv"
    
    # Ensure docs directory exists
    output_path.parent.mkdir(exist_ok=True)
    
    try:
        # Connect to SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Query to extract image_id and video_prompt where video_prompt is not null
        query = """
        SELECT image_id, video_prompt 
        FROM prompts 
        WHERE video_prompt IS NOT NULL 
        ORDER BY image_id
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        # Write to CSV file
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow(['image_id', 'video_prompt'])
            
            # Write data rows
            for row in results:
                writer.writerow(row)
        
        print(f"Successfully extracted {len(results)} records to {output_path}")
        print(f"CSV file created: {output_path}")
        
        # Display first few records for verification
        if results:
            print("\nFirst 3 records:")
            for i, (image_id, prompt) in enumerate(results[:3]):
                print(f"Image ID {image_id}: {prompt[:100]}...")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    extract_video_prompts_to_csv()
