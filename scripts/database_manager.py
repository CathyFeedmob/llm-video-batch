#!/usr/bin/env python3
"""
Database Manager for LLM Video Batch Processing

This module provides SQLite3 database management for:
1. Image processing records (replacing logs/image_uploading.csv)
2. Video generation records (replacing logs/video_generation_log.jsonl)
3. Prompt data (replacing out/prompt_json/*.json files)

Usage:
    from database_manager import DatabaseManager
    
    db = DatabaseManager()
    db.initialize_database()
"""

import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import logging

@dataclass
class ImageRecord:
    """Image processing record."""
    id: Optional[int] = None
    timestamp: Optional[str] = None
    original_filename: Optional[str] = None
    original_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    upload_url: Optional[str] = None
    uploaded_filename: Optional[str] = None
    uploaded_path: Optional[str] = None
    downloaded_size_bytes: Optional[int] = None
    processing_time_seconds: Optional[float] = None
    status: Optional[str] = None
    error_message: Optional[str] = None
    descriptive_name: Optional[str] = None
    processed_path: Optional[str] = None

@dataclass
class PromptRecord:
    """Prompt data record."""
    id: Optional[int] = None
    image_id: Optional[int] = None  # Foreign key to images table
    image_prompt: Optional[str] = None
    video_prompt: Optional[str] = None
    refined_video_prompt: Optional[str] = None
    creative_video_prompt_1: Optional[str] = None
    creative_video_prompt_2: Optional[str] = None
    creative_video_prompt_3: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

@dataclass
class VideoRecord:
    """Video generation record."""
    id: Optional[int] = None
    image_id: Optional[int] = None  # Foreign key to images table
    prompt_id: Optional[int] = None  # Foreign key to prompts table
    video_filename: Optional[str] = None
    video_path: Optional[str] = None
    prompt_used: Optional[str] = None
    prompt_type: Optional[str] = None  # 'base', 'refined', 'creative_1', 'creative_2', 'creative_3'
    generation_service: Optional[str] = None  # 'duomi', 'kling', 'gemini', etc.
    generation_time_seconds: Optional[float] = None
    file_size_bytes: Optional[int] = None
    status: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    metadata: Optional[str] = None  # JSON string for additional data

class DatabaseManager:
    """Main database manager class."""
    
    def __init__(self, db_path: str = "data/llm_video_batch.db"):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with foreign key support."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
        return conn
    
    def initialize_database(self):
        """Initialize database with all required tables."""
        with self.get_connection() as conn:
            # Create images table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                    original_filename TEXT NOT NULL,
                    original_path TEXT,
                    file_size_bytes INTEGER,
                    upload_url TEXT,
                    uploaded_filename TEXT,
                    uploaded_path TEXT,
                    downloaded_size_bytes INTEGER,
                    processing_time_seconds REAL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    error_message TEXT,
                    descriptive_name TEXT,
                    processed_path TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            
            # Create prompts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS prompts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_id INTEGER NOT NULL,
                    image_prompt TEXT,
                    video_prompt TEXT,
                    refined_video_prompt TEXT,
                    creative_video_prompt_1 TEXT,
                    creative_video_prompt_2 TEXT,
                    creative_video_prompt_3 TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (image_id) REFERENCES images (id) ON DELETE CASCADE
                )
            """)
            
            # Create videos table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_id INTEGER NOT NULL,
                    prompt_id INTEGER,
                    video_filename TEXT,
                    video_path TEXT,
                    prompt_used TEXT,
                    prompt_type TEXT DEFAULT 'base',
                    generation_service TEXT,
                    generation_time_seconds REAL,
                    file_size_bytes INTEGER,
                    status TEXT NOT NULL DEFAULT 'pending',
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    metadata TEXT,
                    FOREIGN KEY (image_id) REFERENCES images (id) ON DELETE CASCADE,
                    FOREIGN KEY (prompt_id) REFERENCES prompts (id) ON DELETE SET NULL
                )
            """)
            
            # Create indexes for better performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_images_status ON images (status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_images_filename ON images (original_filename)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prompts_image_id ON prompts (image_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_videos_image_id ON videos (image_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_videos_status ON videos (status)")
            
            # Create triggers to update updated_at timestamps
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS update_images_timestamp 
                AFTER UPDATE ON images
                BEGIN
                    UPDATE images SET updated_at = datetime('now') WHERE id = NEW.id;
                END
            """)
            
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS update_prompts_timestamp 
                AFTER UPDATE ON prompts
                BEGIN
                    UPDATE prompts SET updated_at = datetime('now') WHERE id = NEW.id;
                END
            """)
            
            conn.commit()
            self.logger.info("Database initialized successfully")
    
    def insert_image_record(self, record: ImageRecord) -> int:
        """
        Insert image processing record.
        
        Args:
            record: ImageRecord object
            
        Returns:
            ID of inserted record
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO images (
                    original_filename, original_path, file_size_bytes, upload_url,
                    uploaded_filename, uploaded_path, downloaded_size_bytes,
                    processing_time_seconds, status, error_message, descriptive_name,
                    processed_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.original_filename, record.original_path, record.file_size_bytes,
                record.upload_url, record.uploaded_filename, record.uploaded_path,
                record.downloaded_size_bytes, record.processing_time_seconds,
                record.status, record.error_message, record.descriptive_name,
                record.processed_path
            ))
            conn.commit()
            return cursor.lastrowid
    
    def insert_prompt_record(self, record: PromptRecord) -> int:
        """
        Insert prompt record.
        
        Args:
            record: PromptRecord object
            
        Returns:
            ID of inserted record
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO prompts (
                    image_id, image_prompt, video_prompt, refined_video_prompt,
                    creative_video_prompt_1, creative_video_prompt_2, creative_video_prompt_3
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                record.image_id, record.image_prompt, record.video_prompt,
                record.refined_video_prompt, record.creative_video_prompt_1,
                record.creative_video_prompt_2, record.creative_video_prompt_3
            ))
            conn.commit()
            return cursor.lastrowid
    
    def insert_video_record(self, record: VideoRecord) -> int:
        """
        Insert video generation record.
        
        Args:
            record: VideoRecord object
            
        Returns:
            ID of inserted record
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO videos (
                    image_id, prompt_id, video_filename, video_path, prompt_used,
                    prompt_type, generation_service, generation_time_seconds,
                    file_size_bytes, status, error_message, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.image_id, record.prompt_id, record.video_filename,
                record.video_path, record.prompt_used, record.prompt_type,
                record.generation_service, record.generation_time_seconds,
                record.file_size_bytes, record.status, record.error_message,
                record.metadata
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_image_by_filename(self, filename: str) -> Optional[ImageRecord]:
        """Get image record by original filename."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM images WHERE original_filename = ?", (filename,)
            ).fetchone()
            
            if row:
                return ImageRecord(**dict(row))
            return None
    
    def get_processed_images(self) -> List[str]:
        """Get list of successfully processed image filenames."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT original_filename FROM images WHERE status = 'success'"
            ).fetchall()
            return [row['original_filename'] for row in rows]
    
    def get_image_with_prompts(self, image_id: int) -> Optional[Dict[str, Any]]:
        """Get image record with associated prompts."""
        with self.get_connection() as conn:
            # Get image record
            image_row = conn.execute(
                "SELECT * FROM images WHERE id = ?", (image_id,)
            ).fetchone()
            
            if not image_row:
                return None
            
            # Get prompts
            prompt_row = conn.execute(
                "SELECT * FROM prompts WHERE image_id = ?", (image_id,)
            ).fetchone()
            
            result = dict(image_row)
            if prompt_row:
                result['prompts'] = dict(prompt_row)
            
            return result
    
    def get_pending_videos(self) -> List[Dict[str, Any]]:
        """Get all pending video generation records with image and prompt data."""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT 
                    v.*,
                    i.uploaded_filename as image_filename,
                    i.uploaded_path as image_path,
                    i.upload_url,
                    p.video_prompt,
                    p.refined_video_prompt,
                    p.creative_video_prompt_1,
                    p.creative_video_prompt_2,
                    p.creative_video_prompt_3
                FROM videos v
                JOIN images i ON v.image_id = i.id
                LEFT JOIN prompts p ON v.prompt_id = p.id
                WHERE v.status = 'pending'
                ORDER BY v.created_at
            """).fetchall()
            
            return [dict(row) for row in rows]
    
    def update_image_status(self, image_id: int, status: str, error_message: str = None):
        """Update image processing status."""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE images SET status = ?, error_message = ? WHERE id = ?",
                (status, error_message, image_id)
            )
            conn.commit()
    
    def update_video_status(self, video_id: int, status: str, 
                           video_path: str = None, file_size: int = None,
                           generation_time: float = None, error_message: str = None):
        """Update video generation status."""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE videos SET 
                    status = ?, 
                    video_path = COALESCE(?, video_path),
                    file_size_bytes = COALESCE(?, file_size_bytes),
                    generation_time_seconds = COALESCE(?, generation_time_seconds),
                    error_message = ?
                WHERE id = ?
            """, (status, video_path, file_size, generation_time, error_message, video_id))
            conn.commit()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics."""
        with self.get_connection() as conn:
            stats = {}
            
            # Image statistics
            image_stats = conn.execute("""
                SELECT 
                    status,
                    COUNT(*) as count,
                    AVG(processing_time_seconds) as avg_processing_time,
                    SUM(file_size_bytes) as total_size
                FROM images 
                GROUP BY status
            """).fetchall()
            
            stats['images'] = {row['status']: dict(row) for row in image_stats}
            
            # Video statistics
            video_stats = conn.execute("""
                SELECT 
                    status,
                    generation_service,
                    COUNT(*) as count,
                    AVG(generation_time_seconds) as avg_generation_time
                FROM videos 
                GROUP BY status, generation_service
            """).fetchall()
            
            stats['videos'] = [dict(row) for row in video_stats]
            
            # Total counts
            total_images = conn.execute("SELECT COUNT(*) as count FROM images").fetchone()
            total_videos = conn.execute("SELECT COUNT(*) as count FROM videos").fetchone()
            
            stats['totals'] = {
                'images': total_images['count'],
                'videos': total_videos['count']
            }
            
            return stats

def migrate_existing_data():
    """Migrate existing CSV and JSON data to SQLite database."""
    db = DatabaseManager()
    db.initialize_database()
    
    print("🔄 Starting data migration...")
    
    # Migrate CSV data
    csv_path = Path("logs/image_uploading.csv")
    if csv_path.exists():
        print(f"📄 Migrating CSV data from {csv_path}")
        import csv
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    record = ImageRecord(
                        timestamp=row.get('timestamp'),
                        original_filename=row.get('original_filename'),
                        file_size_bytes=int(row.get('file_size_bytes', 0)) if row.get('file_size_bytes') else None,
                        upload_url=row.get('upload_url'),
                        uploaded_filename=row.get('downloaded_filename'),
                        downloaded_size_bytes=int(row.get('image_size_after_download', 0)) if row.get('image_size_after_download') else None,
                        processing_time_seconds=float(row.get('processing_time_seconds', 0)) if row.get('processing_time_seconds') else None,
                        status=row.get('status', 'unknown'),
                        error_message=row.get('error_message')
                    )
                    db.insert_image_record(record)
                except Exception as e:
                    print(f"⚠️ Error migrating CSV row: {e}")
    
    # Migrate JSON files
    json_dir = Path("out/prompt_json")
    if json_dir.exists():
        print(f"📁 Migrating JSON files from {json_dir}")
        
        for json_file in json_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Find corresponding image record
                pic_name = data.get('pic_name', '')
                image_record = db.get_image_by_filename(pic_name)
                
                if image_record:
                    # Insert prompt record
                    prompt_record = PromptRecord(
                        image_id=image_record.id,
                        image_prompt=data.get('image_prompt'),
                        video_prompt=data.get('video_prompt'),
                        refined_video_prompt=data.get('refined_video_prompt'),
                        creative_video_prompt_1=data.get('creative_video_prompt_1'),
                        creative_video_prompt_2=data.get('creative_video_prompt_2'),
                        creative_video_prompt_3=data.get('creative_video_prompt_3')
                    )
                    db.insert_prompt_record(prompt_record)
                    
                    # Move JSON file to used directory
                    used_dir = json_dir / "used"
                    used_dir.mkdir(exist_ok=True)
                    json_file.rename(used_dir / json_file.name)
                    
                else:
                    print(f"⚠️ No image record found for {pic_name}")
                    
            except Exception as e:
                print(f"⚠️ Error migrating JSON file {json_file}: {e}")
    
    print("✅ Data migration completed!")
    
    # Print statistics
    stats = db.get_statistics()
    print(f"\n📊 Database Statistics:")
    print(f"   Total Images: {stats['totals']['images']}")
    print(f"   Total Videos: {stats['totals']['videos']}")
    
    for status, data in stats['images'].items():
        print(f"   Images {status}: {data['count']}")

if __name__ == "__main__":
    # Initialize database and migrate existing data
    migrate_existing_data()
