# Database Conversion Insights

## Overview
This document provides insights into the JSON-to-database conversion process and current system state for the LLM Video Batch project.

## Conversion Summary (2025-01-07)

### Files Processed
- **Source**: `out/prompt_json/` directory
- **Count**: 29 JSON files successfully converted
- **Errors**: 0 failures

### Database Records Created/Updated

#### Images Table
- **Total Records**: 155
- **Status**: All set to `'success'` 
- **Reasoning**: Images are already processed and uploaded (have upload URLs)
- **Key Fields Updated**:
  - `upload_url`: Image hosting URLs (iili.io)
  - `uploaded_filename`: Descriptive filenames
  - `descriptive_name`: AI-generated meaningful names
  - `status`: `'success'` (processed and uploaded)

#### Prompts Table  
- **Total Records**: 28 (new)
- **Content**: Complete prompt variations for each image
- **Fields Populated**:
  - `image_prompt`: Description for image generation
  - `video_prompt`: Base video movement prompt
  - `refined_video_prompt`: Refined movement-focused prompt
  - `creative_video_prompt_1`: Aggressive/dynamic movement
  - `creative_video_prompt_2`: Surreal/impossible movement  
  - `creative_video_prompt_3`: Cinematic/dramatic movement

#### Videos Table
- **Total Records**: 28 (new)
- **Status**: All set to `'pending'`
- **Reasoning**: Ready for video generation by `generate_video_duomi_v2.py`
- **Key Fields**:
  - `video_filename`: Target MP4 filename
  - `video_path`: Expected output path (`out/`)
  - `prompt_used`: Base video prompt
  - `prompt_type`: `'base'`
  - `status`: `'pending'` (ready to generate)

## Workflow Status Understanding

### Image Processing Pipeline
```
img/ready → upload → download → JSON generation → database → img/processed
Status:   processing → uploaded → downloaded → success
```

### Video Generation Pipeline  
```
pending → generating → completed/failed
```

### Current State
- **Images**: All in `'success'` state (fully processed)
- **Videos**: All in `'pending'` state (ready for generation)

## Key Insights

### 1. Status Meanings
- **Image `'success'`**: Image has been uploaded, processed, and JSON generated
- **Video `'pending'`**: Ready for video generation (not yet started)
- **Video `'generating'`**: Currently being processed by Duomi API
- **Video `'completed'`**: Video successfully generated
- **Video `'failed'`**: Video generation failed

### 2. Filename Patterns
- **JSON Files**: `{Descriptive_Name}_{YYYYMMDD}_{HHMMSS}_{milliseconds}.json`
- **Image Files**: `{Descriptive_Name}_{YYYYMMDD}_{HHMMSS}_{milliseconds}.jpg`
- **Video Files**: `{Descriptive_Name}_{YYYYMMDD}_{HHMMSS}_{milliseconds}.mp4`

### 3. Descriptive Names Generated
Examples of AI-generated descriptive names:
- "Blue-Haired Woman"
- "White Lion" 
- "Cybernetic Gorilla"
- "Fantasy Bread City"
- "Open Book With Flowers"

### 4. Prompt Strategy
The system generates multiple prompt variations:
- **Base**: Natural movement description
- **Refined**: Movement-focused, concise
- **Creative 1**: Aggressive/dynamic movement
- **Creative 2**: Surreal/impossible movement
- **Creative 3**: Cinematic/dramatic movement

## Next Steps for Video Generation

### Ready to Generate
All 28 videos are in `'pending'` status and ready for generation using:
```bash
python3 scripts/generate_video_duomi_v2.py
```

### Expected Behavior
The video generation script will:
1. Query videos with `'pending'` status
2. Use `refined_video_prompt` by default
3. Update status to `'generating'` during processing
4. Update to `'completed'` or `'failed'` when done
5. Save videos to `out/` directory

## Database Schema Notes

### Important Relationships
- `images.id` → `prompts.image_id` (1:1)
- `images.id` → `videos.image_id` (1:1) 
- `prompts.id` → `videos.prompt_id` (1:1)

### Key Fields for Video Generation
- `videos.status = 'pending'`: Videos ready to generate
- `prompts.refined_video_prompt`: Preferred prompt for generation
- `images.upload_url`: Source image URL for video generation

## File Locations

### Input/Output Directories
- **JSON Source**: `out/prompt_json/`
- **Video Output**: `out/`
- **Processed Images**: `img/processed/`
- **Database**: `data/llm_video_batch.db`

### Scripts
- **Conversion**: `scripts/convert_json_to_db.py`
- **Video Generation**: `scripts/generate_video_duomi_v2.py`
- **Image Processing**: `scripts/parse_image_and_generate_json.py`

## Troubleshooting

### Common Issues
1. **Missing JSON files**: Check `out/prompt_json/` directory
2. **Database connection**: Verify `data/llm_video_batch.db` exists
3. **Video generation**: Ensure `DUOMI_API_KEY` environment variable is set

### Verification Queries
```sql
-- Check image statuses
SELECT status, COUNT(*) FROM images GROUP BY status;

-- Check video statuses  
SELECT status, COUNT(*) FROM videos GROUP BY status;

-- View pending videos
SELECT v.id, i.descriptive_name, v.video_filename 
FROM videos v 
JOIN images i ON v.image_id = i.id 
WHERE v.status = 'pending';
```

## Performance Notes
- **Conversion Time**: ~30 seconds for 29 files
- **Success Rate**: 100% (29/29 files processed)
- **Database Size**: 155 images, 28 prompts, 28 videos

---
*Generated: 2025-01-07 02:59 UTC*
*Last Updated: After JSON-to-database conversion*
