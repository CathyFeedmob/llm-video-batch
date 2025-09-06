# Duomi Video Generation Optimization Guide

## Overview
This document describes the optimization made to the `generate_video_duomi.py` script to efficiently reuse existing JSON files instead of regenerating them through the vision processing pipeline.

## Problem Statement
The original script always called `scripts/test_gemini_vision.py` to generate JSON files containing image descriptions and video prompts, even when suitable JSON files already existed. This resulted in:
- Unnecessary API calls to vision processing services
- Increased processing time
- Redundant image analysis
- Higher costs due to repeated API usage

## Solution Architecture

### Core Logic Flow
```
1. Check for existing JSON files in out/prompt_json/
2. Match JSON files with images in img/ready/ based on pic_name field
3. If match found → Use existing JSON file
4. If no match → Generate new JSON file via test_gemini_vision.py
5. Proceed with video generation
```

### Key Functions Added

#### `find_matching_json_for_image(image_path, json_dir)`
- **Purpose**: Find a JSON file that matches a given image
- **Logic**: Reads each JSON file and compares the `pic_name` field with the image filename
- **Returns**: Path to matching JSON file or None

#### `find_images_without_json(img_ready_dir, json_dir)`
- **Purpose**: Identify images that don't have corresponding JSON files
- **Logic**: Iterates through all images in `img/ready` and checks for matching JSON files
- **Returns**: List of image paths without corresponding JSON files

### Directory Structure
```
project/
├── img/
│   ├── ready/          # Images waiting to be processed
│   └── generated/      # Images that have been processed
├── out/
│   ├── prompt_json/    # Active JSON files
│   │   └── used/       # Processed JSON files
│   └── *.mp4          # Generated videos
└── scripts/
    ├── generate_video_duomi.py    # Main script (optimized)
    └── test_gemini_vision.py      # Vision processing script
```

## JSON File Format
Each JSON file contains:
```json
{
    "pic_name": "Surreal_watermelon._20250906160200_3894.png",
    "video_name": "Surreal_watermelon._20250906160200_3894.mp4",
    "video_prompt": "Description of desired video motion...",
    "image_prompt": "Description for image generation...",
    "image_url": "https://iili.io/KnUdFpe.png"
}
```

## Implementation Details

### Matching Logic
1. **Primary Matching**: JSON `pic_name` field must exactly match image filename
2. **File Extensions**: Supports .png, .jpg, .jpeg image formats
3. **Case Sensitivity**: Exact case matching required

### Processing Priority
1. **Existing Pairs**: Process matched image-JSON pairs first
2. **New Images**: Generate JSON for unmatched images
3. **Batch Processing**: Process one pair at a time

### Error Handling
- **Invalid JSON**: Skip corrupted JSON files and continue processing
- **Missing Images**: Handle cases where JSON references non-existent images
- **API Failures**: Graceful fallback when vision processing fails
- **Failure Files**: Automatically skip JSON files starting with "Error_message" (case-insensitive) as these represent failed processing attempts

## Performance Benefits

### Before Optimization
- Always calls `test_gemini_vision.py`
- Processes every image through vision API
- Higher API costs and processing time

### After Optimization
- Reuses existing JSON files when possible
- Only processes new/unmatched images
- Significant reduction in API calls and processing time

### Measured Improvements
- **API Call Reduction**: Up to 100% for images with existing JSON files
- **Processing Time**: Immediate processing for matched pairs
- **Cost Savings**: Proportional to the number of reused JSON files

## Usage Examples

### Scenario 1: Existing JSON File Match
```bash
$ python3 scripts/generate_video_duomi.py
# Output:
# No JSON file path provided. Checking for existing JSON files and matching images...
# Found matching pair: Surreal_watermelon._20250906160200_3894.png <-> Surreal_watermelon._20250906160200_3894.json
# Using matched pair: img/ready/Surreal_watermelon._20250906160200_3894.png and out/prompt_json/Surreal_watermelon._20250906160200_3894.json
# [Proceeds directly to video generation]
```

### Scenario 2: No Existing JSON File
```bash
$ python3 scripts/generate_video_duomi.py
# Output:
# No JSON file path provided. Checking for existing JSON files and matching images...
# Found 136 images without corresponding JSON files.
# Executing scripts/test_gemini_vision.py to generate JSON for the first image...
# [Generates new JSON file, then proceeds to video generation]
```

### Scenario 3: Manual File Specification
```bash
$ python3 scripts/generate_video_duomi.py <image_url> <json_file_path>
# Uses specified files directly, bypassing automatic matching
```

## File Movement Logic

### During Processing
1. **Images**: Moved from `img/ready/` to `img/generated/` after video generation
2. **JSON Files**: Moved from `out/prompt_json/` to `out/prompt_json/used/` after processing
3. **Videos**: Saved to `out/` directory

### Cleanup Process
- Ensures processed files don't interfere with future runs
- Maintains clear separation between active and completed work
- Preserves audit trail of processed items

## Best Practices

### For Users
1. **Batch Processing**: Place multiple images in `img/ready/` for efficient processing
2. **JSON Preservation**: Keep useful JSON files in `out/prompt_json/` for reuse
3. **File Naming**: Ensure consistent naming between images and JSON files

### For Developers
1. **Error Handling**: Always handle JSON parsing errors gracefully
2. **Path Validation**: Verify file existence before processing
3. **Logging**: Maintain detailed logs for debugging and monitoring

## Troubleshooting

### Common Issues
1. **No Matching Files**: Ensure `pic_name` in JSON exactly matches image filename
2. **Permission Errors**: Check file permissions for read/write access
3. **API Failures**: Verify API keys and network connectivity

### Debug Commands
```bash
# Check for matching pairs
ls img/ready/ && ls out/prompt_json/

# Verify JSON file content
cat out/prompt_json/filename.json | jq .pic_name

# Check file permissions
ls -la img/ready/ out/prompt_json/
```

## Future Enhancements

### Potential Improvements
1. **Fuzzy Matching**: Handle slight filename variations
2. **Batch Processing**: Process multiple pairs simultaneously
3. **Cache Management**: Automatic cleanup of old JSON files
4. **Metadata Tracking**: Enhanced logging and statistics

### Configuration Options
- Configurable matching criteria
- Adjustable processing priorities
- Custom directory structures

## Conclusion
This optimization significantly improves the efficiency of the video generation pipeline by intelligently reusing existing JSON files. The implementation maintains backward compatibility while providing substantial performance benefits for repeated processing scenarios.
