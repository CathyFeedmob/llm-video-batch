#!/usr/bin/env python3
"""
Script to remove imgai.com watermark from the upper left corner of images using Gemini API.
Takes a folder of watermarked images as input and outputs processed images to a specified output folder.
"""

import os
import sys
import argparse
import time
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

def remove_watermark_with_gemini(image_path, output_path):
    """
    Remove the imgai.com watermark from an image using Gemini API.
    
    Args:
        image_path (str): Path to the input image
        output_path (str): Path to save the processed image
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get API key from environment
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            print("Error: GEMINI_API_KEY not found in environment variables")
            return False
        
        # Initialize Gemini client
        client = genai.Client(api_key=api_key)
        
        # Open the image
        image = Image.open(image_path)
        
        # Prompt for watermark removal
        prompt = "Remove imgai.com watermark signature from upper left of the image"
        
        # Call Gemini API for image editing
        print(f"  Calling Gemini API to remove watermark...")
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
                print(f"  Watermark removed successfully")
                return True
        
        print(f"  No image data found in API response")
        return False
    except Exception as e:
        print(f"  Error processing {image_path}: {e}")
        return False

def process_folder(input_folder, output_folder):
    """
    Process all images in the input folder and save to the output folder.
    
    Args:
        input_folder (str): Path to the folder containing watermarked images
        output_folder (str): Path to save processed images
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
        output_path = os.path.join(output_folder, filename)
        
        print(f"Processing [{i+1}/{len(image_files)}]: {filename}")
        if remove_watermark_with_gemini(input_path, output_path):
            success_count += 1
            
        # Add a small delay between API calls to avoid rate limiting
        if i < len(image_files) - 1:
            time.sleep(1)
    
    print(f"Processed {success_count} out of {len(image_files)} images")
    print(f"Processed images saved to: {output_folder}")

def main():
    """Main function to parse arguments and process images."""
    parser = argparse.ArgumentParser(description='Remove imgai.com watermark from images using Gemini API')
    parser.add_argument('--input', '-i', type=str, default='img/ready/watermark',
                        help='Input folder containing watermarked images (default: img/ready/watermark)')
    parser.add_argument('--output', '-o', type=str, default='img/ready/no-watermark',
                        help='Output folder for processed images (default: img/ready/no-watermark)')
    
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
    
    # Process the folder
    process_folder(input_folder, output_folder)

if __name__ == "__main__":
    main()
