# LLM Video Batch Database Schema

This document provides a comprehensive overview of the SQLite database schema used in the LLM Video Batch project.

## Database Location
- **File**: `data/llm_video_batch.db`
- **Type**: SQLite 3

## Table Overview

The database consists of three main tables that track the complete workflow from image upload through prompt generation to video creation:

1. **images** - Stores uploaded image files and their metadata
2. **prompts** - Stores various prompt variations generated for images
3. **videos** - Stores video generation results and metadata

## Table Schemas

### images Table

Stores information about uploaded images and their processing status.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| id | INTEGER | PRIMARY KEY | - | Unique identifier |
| timestamp | TEXT | NOT NULL | datetime('now') | Creation timestamp |
| original_filename | TEXT | NOT NULL | - | Original filename before upload |
| original_path | TEXT | - | - | Original file path |
| file_size_bytes | INTEGER | - | - | File size in bytes |
| upload_url | TEXT | - | - | URL after upload to image hosting service |
| uploaded_filename | TEXT | - | - | Filename after upload |
| uploaded_path | TEXT | - | - | Path after upload |
| downloaded_size_bytes | INTEGER | - | - | Size after download verification |
| processing_time_seconds | REAL | - | - | Time taken to process/upload |
| status | TEXT | NOT NULL | 'pending' | Processing status |
| error_message | TEXT | - | - | Error details if processing failed |
| descriptive_name | TEXT | - | - | Human-readable name extracted from filename |
| processed_path | TEXT | - | - | Path to processed image |
| created_at | TEXT | NOT NULL | datetime('now') | Record creation time |
| updated_at | TEXT | NOT NULL | datetime('now') | Last update time |
| origin_image_id | INTEGER | FK | - | Reference to original image if this image was generated based on another |

**Status Values:**
- `pending` - Image queued for processing
- `success` - Image successfully uploaded and processed
- `failed` - Image processing failed
- `legacy` - Placeholder for legacy system migrations

### prompts Table

Stores various prompt variations generated for each image.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| id | INTEGER | PRIMARY KEY | - | Unique identifier |
| image_id | INTEGER | NOT NULL, FK | - | Reference to images table |
| image_prompt | TEXT | - | - | Prompt used to generate/describe the image |
| video_prompt | TEXT | - | - | Base prompt for video generation |
| refined_video_prompt | TEXT | - | - | Refined version of video prompt |
| creative_video_prompt_1 | TEXT | - | - | First creative variation |
| creative_video_prompt_2 | TEXT | - | - | Second creative variation |
| creative_video_prompt_3 | TEXT | - | - | Third creative variation |
| created_at | TEXT | NOT NULL | datetime('now') | Record creation time |
| updated_at | TEXT | NOT NULL | datetime('now') | Last update time |

**Foreign Keys:**
- `image_id` → `images.id`
- `origin_image_id` → `images.id` (self-referencing for image-to-image generation)

### videos Table

Stores video generation results and metadata.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| id | INTEGER | PRIMARY KEY | - | Unique identifier |
| image_id | INTEGER | NOT NULL, FK | - | Reference to images table |
| prompt_id | INTEGER | FK | - | Reference to prompts table |
| video_filename | TEXT | - | - | Generated video filename |
| video_path | TEXT | - | - | Path to generated video file |
| prompt_used | TEXT | - | - | Actual prompt text used for generation |
| prompt_type | TEXT | - | 'base' | Type of prompt used |
| generation_service | TEXT | - | - | Service used for generation (e.g., 'duomi') |
| generation_time_seconds | REAL | - | - | Time taken to generate video |
| file_size_bytes | INTEGER | - | - | Generated video file size |
| status | TEXT | NOT NULL | 'pending' | Generation status |
| error_message | TEXT | - | - | Error details if generation failed |
| created_at | TEXT | NOT NULL | datetime('now') | Record creation time |
| metadata | TEXT | - | - | Additional metadata (JSON format) |

**Status Values:**
- `pending` - Video queued for generation
- `completed` - Video successfully generated
- `failed` - Video generation failed

**Foreign Keys:**
- `image_id` → `images.id`
- `prompt_id` → `prompts.id`

## Relationships

```
images (1) ←→ (1) prompts ←→ (1) videos
images (1) ←→ (0..n) images (self-referencing via origin_image_id)
```

- Each image can have one set of prompts
- Each prompt set can generate one video
- Images can reference other images as their origin (for image-to-image generation)
- The relationships are maintained through foreign keys

## Special Records

### Legacy Placeholder Image
- **ID**: 462
- **Purpose**: Placeholder for prompts without reference images
- **Characteristics**:
  - `original_filename`: 'legacy_placeholder'
  - `descriptive_name`: 'Legacy System Migration'
  - `status`: 'legacy'

## Data Sources and Migration

### JSON Files
- **Location**: `out/prompt_json/used/`
- **Content**: Prompt variations and metadata
- **Processing**: Converted via `scripts/convert_used_json_to_db.py`

### Image Upload Logs
- **Location**: `logs/image_uploading.csv`
- **Content**: Image upload results and metadata
- **Usage**: Matches JSON files to uploaded images

### Video Generation Logs
- **Location**: `logs/video_generation_log.jsonl`
- **Content**: Video generation results and timing
- **Usage**: Sets accurate video statuses and generation metadata

## Common Queries

### Get all completed videos with their prompts
```sql
SELECT 
    i.descriptive_name,
    p.video_prompt,
    v.video_filename,
    v.generation_time_seconds,
    v.status
FROM images i
JOIN prompts p ON i.id = p.image_id
JOIN videos v ON i.id = v.image_id
WHERE v.status = 'completed'
ORDER BY v.generation_time_seconds DESC;
```

### Get prompts without reference images (legacy)
```sql
SELECT 
    p.id,
    p.video_prompt,
    i.descriptive_name
FROM prompts p
JOIN images i ON p.image_id = i.id
WHERE i.descriptive_name = 'Legacy System Migration';
```

### Get video generation statistics
```sql
SELECT 
    v.status,
    COUNT(*) as count,
    AVG(v.generation_time_seconds) as avg_time,
    AVG(v.file_size_bytes) as avg_size
FROM videos v
GROUP BY v.status;
```

### Get images with upload metadata
```sql
SELECT 
    i.descriptive_name,
    i.upload_url,
    i.file_size_bytes,
    i.processing_time_seconds,
    i.status
FROM images i
WHERE i.status = 'success'
ORDER BY i.processing_time_seconds DESC;
```

### Get generated images with their origin images
```sql
SELECT 
    generated.descriptive_name as generated_image,
    original.descriptive_name as origin_image,
    generated.created_at as generation_date
FROM images generated
JOIN images original ON generated.origin_image_id = original.id
ORDER BY generated.created_at DESC;
```

### Get image generation chains (images and their derivatives)
```sql
SELECT 
    original.descriptive_name as original_image,
    COUNT(generated.id) as derivatives_count
FROM images original
LEFT JOIN images generated ON original.id = generated.origin_image_id
GROUP BY original.id, original.descriptive_name
HAVING derivatives_count > 0
ORDER BY derivatives_count DESC;
```

### Get all original images (not generated from other images)
```sql
SELECT 
    i.descriptive_name,
    i.upload_url,
    i.status,
    i.created_at
FROM images i
WHERE i.origin_image_id IS NULL
AND i.status = 'success'
ORDER BY i.created_at DESC;
```

## Migration Notes

1. **Image ID Handling**: Prompts without reference images use a legacy placeholder (ID: 462) to satisfy NOT NULL constraints
2. **Status Mapping**: Video statuses are derived from generation logs ('success' → 'completed', 'failure' → 'failed')
3. **Log Integration**: Both image upload and video generation logs are used to populate accurate metadata
4. **Duplicate Handling**: The conversion script handles duplicate entries by updating existing records

## Maintenance

- **Backup**: Regular backups recommended before major migrations
- **Indexing**: Consider adding indexes on frequently queried columns (status, image_id, etc.)
- **Cleanup**: Periodic cleanup of failed records may be beneficial
