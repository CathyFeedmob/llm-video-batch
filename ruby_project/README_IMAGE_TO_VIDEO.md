# Image to Video Processor

This script processes a CSV file of image URLs, generates refined Chinese video prompts using OpenRouter, and creates videos using the Duomi video service.

## Features

- **Batch Processing**: Process multiple images from a CSV file
- **Chinese Prompt Generation**: Uses OpenRouter to generate Chinese video prompts
- **Video Generation**: Creates videos using Duomi video service
- **Enhanced Logging**: Tracks waiting times and maintains both detailed JSON and basic CSV logs
- **Real-time Progress**: Shows processing progress with timing information
- **Error Handling**: Robust error handling with detailed error messages

## Setup

1. **Environment Variables**: Create a `.env` file with:
   ```
   OPENROUTER_API_KEY=your_openrouter_key
   DUOMI_API_KEY=your_duomi_key
   OPENROUTER_MODEL_NAME=google/gemini-2.5-flash  # optional
   ```

2. **Dependencies**: Make sure you have the required Ruby gems:
   ```bash
   gem install dotenv
   ```

## Usage

### List Images
View all images in the CSV file:
```bash
ruby image_to_video_processor.rb list
```

### Process All Images
Process all images from the CSV file:
```bash
ruby image_to_video_processor.rb process
```

### Process Single Image
Process a single image:
```bash
ruby image_to_video_processor.rb single <image_url> <image_id>
```

Example:
```bash
ruby image_to_video_processor.rb single https://iili.io/KoWubXS.jpg 1
```

## Input Format

The script expects a CSV file at `ruby_project/data/image_list.csv` with the following format:
```csv
id,image_url
1,https://iili.io/KoWubXS.jpg
2,https://iili.io/KoWuDI2.jpg
...
```

## Output

### Log Files
The script generates two types of log files in `ruby_project/logs/`:

1. **Detailed JSON Log**: `video_processing_detailed_YYYYMMDD_HHMMSS.json`
   - Complete processing results with all API responses
   - Timing information
   - Error details

2. **Basic CSV Log**: `video_processing_basic_YYYYMMDD_HHMMSS.csv`
   - Simple success/failure tracking
   - Chinese prompts
   - Video file paths
   - Waiting times

### Video Files
Generated videos are saved to `ruby_project/video_downloaded/` with filenames like:
```
{task_id}_{video_id}_{duration}s.mp4
```

## Processing Flow

1. **Image Analysis**: OpenRouter analyzes the image and generates a description
2. **Prompt Generation**: Converts the description to English and Chinese video prompts
3. **Video Generation**: Submits the image and Chinese prompt to Duomi video service
4. **Status Monitoring**: Monitors video generation progress with real-time timing
5. **Download**: Downloads completed videos automatically

## Timing and Performance

- **Real-time Monitoring**: Shows elapsed time during video generation waiting
- **Average Timing**: Calculates and displays average waiting times
- **Progress Tracking**: Shows completion status for each step
- **API Rate Limiting**: Includes delays to avoid overwhelming APIs

## Error Handling

The script handles various error scenarios:
- Missing API keys
- Invalid image URLs
- API failures
- Network timeouts
- Video generation failures

## Batch Processing Notes

**OpenRouter Batch Processing**: OpenRouter doesn't have a specific batch API, but the script optimizes processing by:
- Processing images sequentially to avoid rate limits
- Reusing the same client connection
- Implementing retry logic for failed requests
- Adding appropriate delays between requests

**Benefits of Current Approach**:
- Better error isolation (one failed image doesn't stop the batch)
- Real-time progress monitoring
- Intermediate result saving
- Memory efficient processing

## Example Output

```
🚀 Starting image to video processing...
📁 Reading images from: ruby_project/data/image_list.csv
📝 Detailed results will be logged to: ruby_project/logs/video_processing_detailed_20250907_191922.json
📊 Basic results will be logged to: ruby_project/logs/video_processing_basic_20250907_191922.csv
============================================================
📊 Found 18 images to process

🖼️  Processing image 1/18 (ID: 1)
🔗 URL: https://iili.io/KoWubXS.jpg
  🤖 Generating Chinese video prompt...
  ✅ Prompt generated successfully
  🇨🇳 Chinese prompt: 一只可爱的小猫咪轻柔地眨眼，尾巴缓缓摆动
  🎬 Generating video...
  ⏳ Video generation started. Task ID: abc123
  ⏰ Checking video status for task: abc123 (elapsed: 15.0s)
  📊 Task status: processing (elapsed: 15.0s)
  ⏳ Video still processing... waiting 15 seconds (total elapsed: 15.0s)
  🎉 Video generation completed! (total wait time: 45.2s)
  📥 Downloading...
  ✅ Video generated and downloaded successfully
  📁 Video files: ruby_project/video_downloaded/abc123_video1_5s.mp4
✅ Completed image 1/18
----------------------------------------

📊 PROCESSING SUMMARY
==============================
Total images processed: 18
Successful prompt generations: 18/18
Successful video generations: 16/18
Overall success rate: 88.9%
Average video waiting time: 52.3s
