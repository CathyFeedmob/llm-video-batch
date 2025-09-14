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
python remove_watermark.py [--input INPUT_FOLDER] [--output OUTPUT_FOLDER]
```

### Arguments

- `--input`, `-i`: Input folder containing watermarked images (default: `img/ready/watermark`)
- `--output`, `-o`: Output folder for processed images (default: `img/ready/no-watermark`)

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

## How It Works

The script:

1. Takes each image from the input folder
2. Sends the image to the Gemini API with a prompt to remove the watermark
3. Receives the processed image from the API
4. Saves the processed image to the output folder

## Notes

- The script processes images one by one with a small delay between API calls to avoid rate limiting
- Supported image formats: jpg, jpeg, png, gif, bmp, tiff
- The script will create the output directory if it doesn't exist
- The Gemini API may have usage limits depending on your account type
