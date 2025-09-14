# Watermark Removal Script

This script removes the imgai.com watermark from the upper left corner of images using the Gemini API. It processes all images in a specified input folder and saves the processed images to an output folder.

## Requirements

- Python 3.x
- Pillow (PIL) library
- Google Generative AI Python SDK
- python-dotenv

Install the required libraries with:

```bash
pip install pillow google-genai python-dotenv
```

## API Key Setup

The script requires a Gemini API key to function. It reads the key from the `.env` file in the project root directory. Make sure your `.env` file contains the following line:

```
GEMINI_API_KEY=your_api_key_here
```

If you don't have a Gemini API key, you can get one from [Google AI Studio](https://ai.google.dev/).

## Usage

```bash
python remove_watermark.py [--input INPUT_FOLDER] [--output OUTPUT_FOLDER] [--retries MAX_RETRIES] [--retry-delay DELAY]
```

### Arguments

- `--input`, `-i`: Input folder containing watermarked images (default: `img/ready/watermark`)
- `--output`, `-o`: Output folder for processed images (default: `img/ready/no-watermark`)
- `--retries`, `-r`: Maximum number of retry attempts per image (default: 3)
- `--retry-delay`, `-d`: Base delay between retries in seconds (default: 2)

### Examples

1. Using default folders:

```bash
python remove_watermark.py
```

2. Specifying custom input and output folders:

```bash
python remove_watermark.py --input custom/input/folder --output custom/output/folder
```

3. Using short form arguments:

```bash
python remove_watermark.py -i custom/input/folder -o custom/output/folder
```

4. Specifying retry parameters:

```bash
python remove_watermark.py --retries 5 --retry-delay 3
```

## How It Works

The script:

1. Takes each image from the input folder
2. Sends the image to the Gemini API with a prompt to remove the watermark
3. If the API call fails, retries with exponential backoff up to the specified maximum retries
4. Receives the processed image from the API
5. Saves the processed image to the output folder with a prefix based on the result:
   - `success_` prefix for successfully processed images
   - `failed_` prefix for images that couldn't be processed after all retry attempts

## Retry Mechanism

The script implements an exponential backoff strategy with jitter for retries:
- Initial retry delay is specified by the `--retry-delay` parameter
- Each subsequent retry increases the delay exponentially (delay * 2^attempt)
- Random jitter is added to avoid the "thundering herd" problem
- The maximum number of retry attempts is controlled by the `--retries` parameter

## Notes

- The script processes images one by one with a small delay between API calls to avoid rate limiting
- Supported image formats: jpg, jpeg, png, gif, bmp, tiff
- The script will create the output directory if it doesn't exist
- The Gemini API may have usage limits depending on your account type
- For failed images (after all retry attempts), the original image is copied to the output folder with the `failed_` prefix
