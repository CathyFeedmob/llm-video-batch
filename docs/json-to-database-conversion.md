# JSON to Database Conversion Instructions

This document provides detailed instructions for converting JSON files to the SQLite database, including handling of edge cases and log integration.

## Overview

The conversion process transforms JSON files from `out/prompt_json/used/` into structured database records across three tables: images, prompts, and videos. The process integrates with existing logs to ensure accurate status tracking.

## Conversion Scripts

### Primary Script: `scripts/convert_used_json_to_db.py`

**Purpose**: Convert JSON files from the 'used' directory with full log integration

**Features**:
- Processes all JSON files in `out/prompt_json/used/`
- Integrates with `logs/image_uploading.csv` for image metadata
- Integrates with `logs/video_generation_log.jsonl` for video status
- Handles missing image references with legacy placeholder
- Avoids duplicate records through smart matching

**Usage**:
```bash
python scripts/convert_used_json_to_db.py
```

### Alternative Script: `scripts/convert_json_to_db.py`

**Purpose**: Convert JSON files from the main directory (not 'used')

**Usage**:
```bash
python scripts/convert_json_to_db.py
```

## JSON File Structure

### Expected JSON Format
```json
{
  "pic_name": "filename.jpeg",
  "video_name": "filename.mp4", 
  "video_prompt": "Base video generation prompt",
  "image_prompt": "Image description prompt",
  "image_url": "https://example.com/image.jpg",
  "refined_video_prompt": "Refined video prompt",
  "creative_video_prompt_1": "First creative variation",
  "creative_video_prompt_2": "Second creative variation", 
  "creative_video_prompt_3": "Third creative variation"
}
```

### Required Fields
- At least one of: `pic_name`, `image_url`, or corresponding upload log entry
- `video_prompt` (for meaningful prompt records)

### Optional Fields
- All other prompt variations
- `video_name` (for video tracking)

## Log File Integration

### Image Upload Logs (`logs/image_uploading.csv`)

**Columns Used**:
- `json_filename` - Matches to JSON files
- `original_filename` - Original image filename
- `upload_url` - Hosted image URL
- `file_size_bytes` - Image file size
- `processing_time_seconds` - Upload processing time
- `status` - Upload status
- `timestamp` - Upload timestamp

**Matching Logic**:
1. Extract base filename from JSON file (remove .json extension)
2. Match against `json_filename` in CSV
3. Use upload data to populate image record

### Video Generation Logs (`logs/video_generation_log.jsonl`)

**Fields Used**:
- `video_name` - Matches to video files
- `status` - Generation result ('success' or 'failure')
- `processing_duration_seconds` - Generation time
- `image_used` - Source image reference
- `timestamp` - Generation timestamp

**Status Mapping**:
- `success` → `completed`
- `failure` → `failed`
- No log entry → `pending`

## Handling Edge Cases

### 1. Missing Image References

**Problem**: JSON files without `pic_name`, `image_url`, or upload log entries

**Solution**: Use legacy placeholder image (ID: 462)
- Creates single placeholder record with `status = 'legacy'`
- All orphaned prompts reference this placeholder
- Maintains database integrity while preserving prompt data

### 2. Duplicate Processing

**Problem**: Multiple JSON files referencing the same image

**Solution**: Smart matching and updating
- Match by descriptive name, filename, or upload URL
- Update existing records instead of creating duplicates
- Preserve most recent prompt variations

### 3. Missing Video Files

**Problem**: JSON references video files that don't exist

**Solution**: Status from logs takes precedence
- Check generation logs for actual status
- Set appropriate status based on log results
- Don't assume 'pending' for all missing files

### 4. Log File Mismatches

**Problem**: JSON files without corresponding log entries

**Solution**: Graceful degradation
- Use available data from JSON file
- Set default statuses where logs are missing
- Continue processing other files

## Database Constraints

### NOT NULL Requirements
- `images.original_filename` - Must have a filename
- `images.status` - Must have a status
- `prompts.image_id` - Must reference an image (use legacy placeholder if needed)
- `videos.image_id` - Must reference an image
- `videos.status` - Must have a status

### Missing Columns
- `videos` table has no `updated_at` column
- Don't attempt to set `updated_at` on videos table

## Verification Queries

### Check Conversion Results
```sql
-- Image status distribution
SELECT status, COUNT(*) FROM images GROUP BY status;

-- Video status distribution  
SELECT status, COUNT(*) FROM videos GROUP BY status;

-- Prompt reference types
SELECT 
    CASE 
        WHEN i.descriptive_name = 'Legacy System Migration' THEN 'Legacy' 
        ELSE 'Real Image' 
    END as type,
    COUNT(*) 
FROM prompts p 
JOIN images i ON p.image_id = i.id 
GROUP BY type;
```

### Data Quality Checks
```sql
-- Find orphaned records
SELECT COUNT(*) FROM prompts p 
LEFT JOIN images i ON p.image_id = i.id 
WHERE i.id IS NULL;

-- Check for missing video records
SELECT COUNT(*) FROM prompts p 
LEFT JOIN videos v ON p.image_id = v.image_id 
WHERE v.id IS NULL;
```

## Best Practices

### Before Running Conversion
1. **Backup database**: `cp data/llm_video_batch.db data/llm_video_batch.db.backup`
2. **Verify log files exist**: Check `logs/` directory
3. **Check JSON directory**: Ensure `out/prompt_json/used/` exists

### During Conversion
1. **Monitor output**: Watch for error messages
2. **Check progress**: Note processed/error counts
3. **Verify log loading**: Ensure logs are loaded successfully

### After Conversion
1. **Run verification queries**: Check data integrity
2. **Review status distributions**: Ensure reasonable results
3. **Spot check records**: Manually verify a few entries

## Troubleshooting

### Common Issues

**"NOT NULL constraint failed: prompts.image_id"**
- Solution: Ensure legacy placeholder creation is working
- Check: `get_or_create_legacy_image_id()` function

**"table videos has no column named updated_at"**
- Solution: Remove `updated_at` references from video operations
- Check: Video table schema documentation

**"No JSON files found"**
- Solution: Verify directory path and file permissions
- Check: `out/prompt_json/used/` directory exists

**"Log files not found"**
- Solution: Verify log file paths
- Check: `logs/image_uploading.csv` and `logs/video_generation_log.jsonl`

### Recovery Procedures

**Partial Conversion Failure**:
1. Check error messages for specific issues
2. Fix data/script issues
3. Re-run conversion (script handles duplicates)

**Database Corruption**:
1. Restore from backup
2. Investigate root cause
3. Fix issues before re-running

## Performance Considerations

- **Batch Processing**: Script processes files in batches with commits
- **Memory Usage**: Loads all logs into memory for fast lookup
- **Transaction Safety**: Uses database transactions for consistency
- **Error Isolation**: Individual file errors don't stop entire process

## Future Enhancements

1. **Incremental Processing**: Only process new/changed files
2. **Parallel Processing**: Multi-threaded conversion for large datasets
3. **Advanced Matching**: Fuzzy matching for better log correlation
4. **Status Validation**: Cross-reference file existence with database status
