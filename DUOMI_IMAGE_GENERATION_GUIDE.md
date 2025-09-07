# Duomi Image Generation Guide

This guide provides comprehensive instructions for using the Duomi Image Generation system to generate images from prompts stored in your SQLite database or JSON files.

## Overview

The Duomi Image Generation system is a Python-based tool that uses the Duomi API to generate high-quality images from text prompts. It supports multiple data sources and provides batch processing capabilities.

## Features

- **Multiple Data Sources**: Generate images from SQLite database, JSON files, or single prompts
- **Batch Processing**: Process multiple prompts with configurable delays
- **9:16 Aspect Ratio**: Default vertical format (1080x1920) optimized for mobile/social media
- **Automatic Image Saving**: Downloads and saves generated images locally
- **Comprehensive Logging**: Detailed logs of all operations and results
- **Error Handling**: Robust error handling with detailed error messages

## Prerequisites

- Python 3.7 or higher
- Required Python packages: `requests`, `sqlite3`, `pathlib`
- Duomi API access with valid API key

## Installation

1. Ensure all required Python packages are installed:
```bash
pip install requests
```

2. The system uses the following directory structure:
```
/workspaces/llm-video-batch/
├── scripts/
│   ├── duomi_image_generator.py      # Main generator script
│   ├── duomi_usage_examples.py       # Usage examples
│   └── test_duomi_models.py          # Model testing utility
├── data/
│   └── llm_video_batch.db            # SQLite database
├── out/
│   ├── prompt_json/                  # JSON prompt files
│   └── generated_images/             # Output directory for generated images
└── logs/                             # Log files
```

## Configuration

### API Configuration
- **API Key**: `hpZyr8TglNSwMXcwlFnqVH4IgN`
- **API Endpoint**: `https://duomiapi.com/v1/images/generations`
- **Model**: `stabilityai/stable-diffusion-xl-base-1.0`

### Default Parameters
- **Image Size**: 1080x1920 (9:16 aspect ratio)
- **Batch Size**: 1
- **Inference Steps**: 20
- **Guidance Scale**: 7.5
- **Seed**: 51515151 (for reproducible results)

## Usage

### Command Line Interface

#### 1. Generate from SQLite Database
Generate images from prompts stored in the database:

```bash
# Generate from all available prompts
python scripts/duomi_image_generator.py --source sqlite

# Limit to first 5 prompts
python scripts/duomi_image_generator.py --source sqlite --limit 5

# Add delay between requests (recommended for large batches)
python scripts/duomi_image_generator.py --source sqlite --limit 10 --delay 2.0
```

#### 2. Generate from JSON Files
Generate images from JSON files in the prompt directory:

```bash
# Generate from all JSON files in default directory
python scripts/duomi_image_generator.py --source json

# Specify custom JSON directory
python scripts/duomi_image_generator.py --source json --input-dir path/to/json/files

# Add delay between requests
python scripts/duomi_image_generator.py --source json --delay 2.0
```

#### 3. Generate Single Image
Generate a single image from a custom prompt:

```bash
# Basic single image generation
python scripts/duomi_image_generator.py --source prompt --prompt "a beautiful sunset over mountains"

# Single image with custom prompt
python scripts/duomi_image_generator.py --source prompt --prompt "a cyberpunk cityscape with neon lights, vertical composition"
```

#### 4. Custom API Key
Use a different API key:

```bash
python scripts/duomi_image_generator.py --source prompt --prompt "your prompt" --api-key "your_api_key_here"
```

### Programmatic Usage

#### Basic Example
```python
from scripts.duomi_image_generator import DuomiImageGenerator

# Initialize generator
generator = DuomiImageGenerator()

# Generate single image
result = generator.generate_image("a majestic dragon flying over a castle")

if result["success"]:
    saved_path = generator.save_generated_image(result, "dragon_castle")
    print(f"Image saved to: {saved_path}")
```

#### Batch Processing from Database
```python
# Generate images for first 3 database prompts
results = generator.batch_generate_from_database(limit=3, delay=2.0)

successful = sum(1 for r in results if r["success"])
print(f"Generated {successful}/{len(results)} images")
```

#### Custom Parameters
```python
# Generate with custom parameters
custom_params = {
    "image_size": "1024x1024",  # Square format
    "guidance_scale": 10.0,     # Higher guidance
    "num_inference_steps": 30,  # More steps for quality
    "seed": 42                  # Custom seed
}

result = generator.generate_image("your prompt", **custom_params)
```

## Data Sources

### SQLite Database
The system reads from the `prompts` table with the following structure:
- **id**: Primary key
- **image_id**: Foreign key to images table
- **image_prompt**: Text prompt for image generation
- **Other fields**: video_prompt, refined_video_prompt, etc.

Query used:
```sql
SELECT p.id, p.image_id, p.image_prompt, i.original_filename, i.descriptive_name
FROM prompts p
LEFT JOIN images i ON p.image_id = i.id
WHERE p.image_prompt IS NOT NULL AND p.image_prompt != ''
ORDER BY p.id
```

### JSON Files
JSON files should contain an `image_prompt` field:
```json
{
    "pic_name": "example.jpg",
    "image_prompt": "A detailed description for image generation",
    "video_prompt": "...",
    "image_url": "https://example.com/image.jpg"
}
```

## Output

### Generated Images
- **Location**: `out/generated_images/`
- **Format**: PNG files
- **Naming Convention**: 
  - Database: `db_{id}_{timestamp}.png` or `db_{descriptive_name}_{timestamp}.png`
  - JSON: `{filename}_{timestamp}.png`
  - Single prompt: `single_prompt_{timestamp}.png`

### Log Files
- **Generation Log**: `logs/duomi_image_generation.log`
- **Results Log**: `logs/duomi_generation_results_{timestamp}.json`

### Result Structure
```json
{
  "success": true,
  "data": { /* API response data */ },
  "prompt": "the original prompt",
  "timestamp": "2025-09-07T13:36:31.245",
  "source": "database|json|single_prompt",
  "saved_path": "out/generated_images/example.png"
}
```

## Error Handling

The system handles various error conditions:
- **API Errors**: Invalid API key, model unavailable, rate limits
- **Network Errors**: Connection timeouts, network failures
- **File Errors**: Missing directories, permission issues
- **Data Errors**: Invalid JSON, missing database tables

All errors are logged with detailed information for troubleshooting.

## Best Practices

### Rate Limiting
- Use `--delay` parameter for batch processing (recommended: 1-2 seconds)
- Monitor API usage to avoid rate limits
- Process large batches during off-peak hours

### Prompt Optimization
- Use descriptive, detailed prompts for better results
- Include composition hints for vertical format: "vertical composition", "portrait orientation"
- Specify style and quality modifiers: "high quality", "detailed", "professional"

### Resource Management
- Monitor disk space in `out/generated_images/` directory
- Regularly clean up old log files
- Consider compressing or archiving old generated images

## Troubleshooting

### Common Issues

#### API Key Issues
```
Error: API request failed with status 403
```
**Solution**: Verify API key is correct and has sufficient credits

#### Model Unavailable
```
Error: {"code":30003,"message":"Model disabled.","data":null}
```
**Solution**: The model may be temporarily unavailable. Try again later or use the test script to find alternative models.

#### Network Timeouts
```
Error: Request exception: HTTPSConnectionPool timeout
```
**Solution**: Check internet connection, increase timeout, or try again later

#### Database Connection Issues
```
Error: Failed to retrieve prompts from database
```
**Solution**: Verify database file exists at `data/llm_video_batch.db` and has correct permissions

### Testing Models
Use the model testing utility to check available models:
```bash
python scripts/test_duomi_models.py
```

## Advanced Usage

### Custom Model Configuration
Modify the default parameters in the script or pass custom parameters:
```python
generator = DuomiImageGenerator()
generator.default_params["model"] = "different-model-name"
generator.default_params["guidance_scale"] = 10.0
```

### Batch Processing with Custom Logic
```python
# Custom batch processing with error handling
prompts = generator.get_prompts_from_database(limit=10)
successful_results = []

for prompt_data in prompts:
    result = generator.generate_image(prompt_data["prompt"])
    if result["success"]:
        saved_path = generator.save_generated_image(result, f"custom_{prompt_data['id']}")
        successful_results.append(result)
    else:
        print(f"Failed to generate image for prompt {prompt_data['id']}: {result['error']}")
```

## Support and Maintenance

### Log Monitoring
Regularly check log files for errors or performance issues:
```bash
tail -f logs/duomi_image_generation.log
```

### Performance Optimization
- Adjust `num_inference_steps` for quality vs speed trade-off
- Use appropriate `guidance_scale` values (7.5 is recommended)
- Monitor generation times and adjust batch sizes accordingly

### Updates and Maintenance
- Keep the script updated with latest API changes
- Monitor Duomi API documentation for new features or model updates
- Regularly backup generated images and important results

## Examples

See `scripts/duomi_usage_examples.py` for comprehensive programmatic examples including:
- Single image generation
- Database batch processing
- JSON file batch processing
- Custom parameter usage
- Prompt inspection utilities

## API Reference

### DuomiImageGenerator Class

#### Methods
- `__init__(api_key)`: Initialize generator
- `generate_image(prompt, **kwargs)`: Generate single image
- `save_generated_image(result, filename_prefix)`: Save image to disk
- `get_prompts_from_database(limit)`: Retrieve database prompts
- `get_prompts_from_json_files(json_dir)`: Retrieve JSON prompts
- `batch_generate_from_database(limit, delay)`: Batch process database
- `batch_generate_from_json(json_dir, delay)`: Batch process JSON files
- `save_results_log(results, output_file)`: Save results to log file

#### Parameters
- `api_key`: Duomi API key
- `prompt`: Text prompt for generation
- `limit`: Maximum number of prompts to process
- `delay`: Delay between API calls (seconds)
- `json_dir`: Directory containing JSON files
- `**kwargs`: Custom generation parameters

For detailed parameter descriptions and return values, see the docstrings in the source code.
