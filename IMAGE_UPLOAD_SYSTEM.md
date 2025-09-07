# Image Upload System Documentation

This document describes the image upload system for batch uploading images to freeimagehost.com with comprehensive logging and error handling.

## Overview

The image upload system consists of three main components:

1. **Base Image Uploader Model** (`scripts/image_uploader.py`) - Extensible framework for different upload services
2. **Batch Upload Script** (`scripts/batch_image_upload.py`) - Main script for batch uploading with CSV logging
3. **Legacy Test Script** (`scripts/test_freeimagehost_upload.py`) - Original single-image test script

## Features

- ✅ **Batch Upload**: Upload 1-20 images from `img/ready` directory
- ✅ **CSV Logging**: Comprehensive logging with timestamps, URLs, file sizes, and error details
- ✅ **Error Handling**: Automatic retry logic with configurable attempts and delays
- ✅ **Resume Capability**: Skip already uploaded images when resuming interrupted uploads
- ✅ **Dry Run Mode**: Preview what would be uploaded without actually uploading
- ✅ **File Management**: Optional moving of uploaded images to `img/generated`
- ✅ **Progress Tracking**: Real-time progress display with detailed status information
- ✅ **Extensible Design**: Easy to add support for other image hosting services

## Quick Start

### Prerequisites

1. Set up your freeimagehost API key in `.env`:
   ```bash
   FREEIMAGE_API_KEY=your_api_key_here
   ```

2. Ensure you have images in the `img/ready` directory

### Basic Usage

```bash
# Upload 10 images (default)
python3 scripts/batch_image_upload.py

# Upload 15 images
python3 scripts/batch_image_upload.py --count 15

# Preview what would be uploaded (dry run)
python3 scripts/batch_image_upload.py --dry-run

# Resume interrupted upload
python3 scripts/batch_image_upload.py --resume

# Move uploaded images to img/generated
python3 scripts/batch_image_upload.py --move-uploaded
```

## Detailed Usage

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--count N` | Number of images to upload (1-20) | 10 |
| `--output FILE` | CSV output file path | `logs/image_uploads.csv` |
| `--move-uploaded` | Move successful uploads to `img/generated` | False |
| `--dry-run` | Show what would be uploaded without uploading | False |
| `--resume` | Skip already uploaded images | False |
| `--source-dir DIR` | Source directory for images | `img/ready` |

### Examples

```bash
# Upload 5 images with custom output file
python3 scripts/batch_image_upload.py --count 5 --output my_uploads.csv

# Upload and move successful uploads
python3 scripts/batch_image_upload.py --count 10 --move-uploaded

# Resume from a different source directory
python3 scripts/batch_image_upload.py --source-dir img/backup --resume

# Dry run with maximum images
python3 scripts/batch_image_upload.py --count 20 --dry-run
```

## CSV Log Format

The system generates a detailed CSV log with the following columns:

| Column | Description |
|--------|-------------|
| `timestamp` | ISO format timestamp of upload attempt |
| `local_filename` | Original filename in source directory |
| `file_size_bytes` | File size in bytes |
| `upload_status` | `success` or `failure` |
| `image_url` | Uploaded image URL (if successful) |
| `image_id` | Image ID from hosting service (if available) |
| `upload_time_seconds` | Time taken for upload |
| `error_message` | Error details (if failed) |
| `attempt_number` | Sequential attempt number |

### Sample CSV Output

```csv
timestamp,local_filename,file_size_bytes,upload_status,image_url,image_id,upload_time_seconds,error_message,attempt_number
2025-09-06T19:08:04.401212,example.png,2799234,success,https://iili.io/KnigU8b.png,,2.49,,1
2025-09-06T19:08:07.598486,failed.jpg,1355393,failure,,,2.20,Network error: Connection timeout,2
```

## Error Handling

The system includes robust error handling:

### Retry Logic
- **Default**: 3 retry attempts with 2-second delays
- **Configurable**: Adjust `max_retries` and `retry_delay` in code
- **Exponential backoff**: Could be implemented for production use

### Common Error Scenarios
1. **Network timeouts** - Automatic retry with delay
2. **API rate limits** - Built-in delays between uploads
3. **Invalid files** - Skipped with error logging
4. **Missing API key** - Early validation and clear error message
5. **Service unavailable** - Retry logic handles temporary outages

### Error Rate Handling
The system is designed to handle the mentioned "1 in 10" error rate:
- Automatic retries for failed uploads
- Detailed error logging for analysis
- Resume capability to continue after fixing issues
- Success rate reporting in summary

## Integration with Video Generation

### Current Integration
The `generate_video_duomi.py` script currently expects image URLs. The upload system provides these URLs in the CSV log.

### Future Integration Options

1. **Direct Integration**: Modify `generate_video_duomi.py` to use the uploader classes
2. **URL Replacement**: Use CSV log to replace local paths with URLs
3. **Preprocessing Step**: Upload images before video generation

### Example Integration Code

```python
from scripts.image_uploader import FreeImageHostUploader

# In generate_video_duomi.py
def upload_image_if_needed(image_path):
    """Upload image if it's a local path, return URL."""
    if image_path.startswith('http'):
        return image_path  # Already a URL
    
    uploader = FreeImageHostUploader()
    result = uploader.upload_image(image_path)
    
    if result.success:
        return result.url
    else:
        raise Exception(f"Failed to upload {image_path}: {result.error}")
```

## Architecture

### Class Hierarchy

```
BaseImageUploader (ABC)
├── FreeImageHostUploader
└── [Future: ImgurUploader, CloudinaryUploader, etc.]

BatchImageUploader
├── Uses: BaseImageUploader
├── Handles: CSV logging, file management
└── Provides: CLI interface
```

### Key Design Patterns

1. **Abstract Base Class**: Easy to extend for other services
2. **Dataclass Results**: Type-safe result handling
3. **Factory Pattern**: `create_uploader()` function for service selection
4. **Command Pattern**: CLI with comprehensive options
5. **Strategy Pattern**: Different upload services with same interface

## File Structure

```
scripts/
├── image_uploader.py          # Base uploader classes
├── batch_image_upload.py      # Main batch upload script
└── test_freeimagehost_upload.py  # Legacy test script

logs/
└── image_uploads.csv          # Upload results log

img/
├── ready/                     # Source images
└── generated/                 # Uploaded images (optional)
```

## Configuration

### Environment Variables

```bash
# Required
FREEIMAGE_API_KEY=your_api_key_here

# Optional (for future extensions)
IMGUR_CLIENT_ID=your_imgur_id
CLOUDINARY_API_KEY=your_cloudinary_key
```

### Customization Options

1. **Upload Service**: Extend `BaseImageUploader` for new services
2. **Retry Logic**: Modify `max_retries` and `retry_delay`
3. **File Filters**: Adjust `image_extensions` in `get_image_files()`
4. **CSV Format**: Modify `csv_headers` in `BatchImageUploader`
5. **Progress Display**: Customize output formatting

## Performance Considerations

### Upload Speed
- **Concurrent uploads**: Not implemented (to be respectful to service)
- **File size limits**: No artificial limits (service-dependent)
- **Batch size**: Limited to 20 images per run
- **Rate limiting**: 1-second delay between uploads

### Memory Usage
- **Streaming**: Files read into memory for upload
- **Large files**: May require chunked upload for very large images
- **Batch processing**: Processes one file at a time

### Network Resilience
- **Timeout handling**: 30-second timeout per upload
- **Connection errors**: Automatic retry with exponential backoff
- **Service outages**: Graceful failure with detailed error messages

## Troubleshooting

### Common Issues

1. **"API key not set"**
   - Solution: Add `FREEIMAGE_API_KEY` to `.env` file

2. **"No image files found"**
   - Solution: Check `img/ready` directory has supported image files
   - Supported: `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp`

3. **"Upload timeout"**
   - Solution: Check internet connection, try smaller images first

4. **"All uploads failed"**
   - Solution: Check API key validity, service status, file permissions

### Debug Mode

For detailed debugging, modify the uploader initialization:

```python
# In batch_image_upload.py
self.uploader = FreeImageHostUploader(max_retries=1, retry_delay=0.5)
```

### Log Analysis

Use the CSV log to analyze upload patterns:

```bash
# Count successful uploads
grep "success" logs/image_uploads.csv | wc -l

# Find failed uploads
grep "failure" logs/image_uploads.csv

# Calculate average upload time
awk -F',' 'NR>1 && $4=="success" {sum+=$7; count++} END {print sum/count}' logs/image_uploads.csv
```

## Future Enhancements

### Planned Features
1. **Multiple Services**: Support for Imgur, Cloudinary, etc.
2. **Concurrent Uploads**: Parallel processing with rate limiting
3. **Image Optimization**: Automatic resizing/compression before upload
4. **Webhook Support**: Real-time notifications of upload status
5. **Database Integration**: Store upload metadata in database
6. **Web Interface**: Browser-based upload management

### API Extensions
1. **Bulk Operations**: Upload entire directories recursively
2. **Filtering**: Upload only images matching certain criteria
3. **Metadata Extraction**: Include EXIF data in logs
4. **Duplicate Detection**: Skip already uploaded images by hash
5. **Progress Callbacks**: Real-time progress updates for GUI integration

## Contributing

To extend the system:

1. **New Upload Service**: Inherit from `BaseImageUploader`
2. **New Features**: Add to `BatchImageUploader` class
3. **CLI Options**: Extend argument parser in `main()`
4. **Testing**: Add test cases for new functionality

### Example: Adding Imgur Support

```python
class ImgurUploader(BaseImageUploader):
    def __init__(self, client_id: str, **kwargs):
        super().__init__(**kwargs)
        self.client_id = client_id
        self.api_url = "https://api.imgur.com/3/image"
    
    def _upload_single(self, image_path: str) -> UploadResult:
        # Implementation here
        pass
```

## License

This image upload system is part of the llm-video-batch project and follows the same license terms.
