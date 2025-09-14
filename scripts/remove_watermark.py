#!/usr/bin/env python3
"""
Script to remove imgai.com watermark from the upper left corner of images using Gemini API.
Takes a folder of watermarked images as input and outputs processed images to a specified output folder.
"""

import os
import sys
import argparse
import time
import random
from pathlib import Path
from io import BytesIO
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Required libraries
try:
    from google import genai
    from PIL import Image
except ImportError:
    print("Required libraries not found. Please install them using:")
    print("pip install google-genai pillow python-dotenv")
    sys.exit(1)

def remove_watermark_with_gemini(image_path, output_path, max_retries=3, retry_delay=2):
    """
    Remove the imgai.com watermark from an image using Gemini API with retry mechanism.
    
    Args:
        image_path (str): Path to the input image
        output_path (str): Path to save the processed image
        max_retries (int): Maximum number of retry attempts
        retry_delay (int): Base delay between retries in seconds
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Get API key from environment
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment variables")
        return False
    
    # Initialize Gemini client
    client = genai.Client(api_key=api_key)
    
    # Open the image
    try:
        image = Image.open(image_path)
    except Exception as e:
        print(f"  Error opening image {image_path}: {e}")
        return False
    
    # Prompt for watermark removal
    prompt = "Remove imgnai.com watermark signature from upper left of the image, and add c29 watermark to bottom right in proper art form."
    
    # Try processing with retries
    for attempt in range(max_retries):
        try:
            # Call Gemini API for image editing
            print(f"  Calling Gemini API to remove watermark... (Attempt {attempt + 1}/{max_retries})")
            resp = client.models.generate_content(
                model="gemini-2.5-flash-image-preview",
                contents=[prompt, image],
            )
            
            # Process the response
            for part in resp.candidates[0].content.parts:
                if getattr(part, "inline_data", None):
                    # Create output directory if it doesn't exist
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    
                    # Save the processed image
                    Image.open(BytesIO(part.inline_data.data)).save(output_path)
                    print(f"  Watermark removed successfully on attempt {attempt + 1}")
                    return True
            
            print(f"  No image data found in API response (Attempt {attempt + 1}/{max_retries})")
            
        except Exception as e:
            print(f"  Error processing {image_path} (Attempt {attempt + 1}/{max_retries}): {e}")
        
        # If this wasn't the last attempt, wait before retrying
        if attempt < max_retries - 1:
            # Add jitter to retry delay to avoid thundering herd problem
            jitter = random.uniform(0.5, 1.5)
            wait_time = retry_delay * (2 ** attempt) * jitter  # Exponential backoff with jitter
            print(f"  Retrying in {wait_time:.2f} seconds...")
            time.sleep(wait_time)
    
    # If we get here, all retries failed
    print(f"  Failed to process image after {max_retries} attempts")
    return False

def process_folder(input_folder, output_folder, max_retries=3, retry_delay=2):
    """
    Process all images in the input folder and save to the output folder.
    
    Args:
        input_folder (str): Path to the folder containing watermarked images
        output_folder (str): Path to save processed images
        max_retries (int): Maximum number of retry attempts per image
        retry_delay (int): Base delay between retries in seconds
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)
    
    # Get all image files in the input folder
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']
    image_files = [f for f in os.listdir(input_folder) 
                  if os.path.isfile(os.path.join(input_folder, f)) and 
                  os.path.splitext(f)[1].lower() in image_extensions]
    
    if not image_files:
        print(f"No image files found in {input_folder}")
        return
    
    # Process each image
    success_count = 0
    for i, filename in enumerate(image_files):
        input_path = os.path.join(input_folder, filename)
        
        # Get file components
        file_basename = os.path.basename(filename)
        file_name, file_ext = os.path.splitext(file_basename)
        
        print(f"Processing [{i+1}/{len(image_files)}]: {filename}")
        
        # Process the image with retries
        result = remove_watermark_with_gemini(
            input_path, 
            os.path.join(output_folder, f"temp_{file_name}{file_ext}"),
            max_retries=max_retries,
            retry_delay=retry_delay
        )
        
        # Rename the output file based on the result
        if result:
            success_count += 1
            final_output_path = os.path.join(output_folder, f"success_{file_name}{file_ext}")
            # Rename the temporary file to the final name
            os.rename(
                os.path.join(output_folder, f"temp_{file_name}{file_ext}"),
                final_output_path
            )
            print(f"  Saved as: success_{file_name}{file_ext}")
        else:
            # For failed images, create an empty file with "failed_" prefix
            # or copy the original image if you prefer
            final_output_path = os.path.join(output_folder, f"failed_{file_name}{file_ext}")
            # Copy the original image to the failed location
            Image.open(input_path).save(final_output_path)
            print(f"  Saved as: failed_{file_name}{file_ext}")
            
        # Add a small delay between processing different images to avoid rate limiting
        if i < len(image_files) - 1:
            time.sleep(1)
    
    print(f"Processed {success_count} out of {len(image_files)} images")
    print(f"Processed images saved to: {output_folder}")

def main():
    """Main function to parse arguments and process images."""
    parser = argparse.ArgumentParser(description='Remove imgnai.com watermark from images using Gemini API')
    parser.add_argument('--input', '-i', type=str, default='img/ready/watermark',
                        help='Input folder containing watermarked images (default: img/ready/watermark)')
    parser.add_argument('--output', '-o', type=str, default='img/ready/no-watermark',
                        help='Output folder for processed images (default: img/ready/no-watermark)')
    parser.add_argument('--retries', '-r', type=int, default=3,
                        help='Maximum number of retry attempts per image (default: 3)')
    parser.add_argument('--retry-delay', '-d', type=int, default=2,
                        help='Base delay between retries in seconds (default: 2)')
    
    args = parser.parse_args()
    
    # Convert relative paths to absolute paths based on the current working directory
    input_folder = os.path.abspath(args.input)
    output_folder = os.path.abspath(args.output)
    
    # Check if input folder exists
    if not os.path.isdir(input_folder):
        print(f"Error: Input folder '{input_folder}' does not exist")
        sys.exit(1)
    
    print(f"Input folder: {input_folder}")
    print(f"Output folder: {output_folder}")
    print(f"Max retries: {args.retries}")
    print(f"Retry delay: {args.retry_delay} seconds")
    
    # Process the folder
    process_folder(input_folder, output_folder, max_retries=args.retries, retry_delay=args.retry_delay)

if __name__ == "__main__":
    main()
