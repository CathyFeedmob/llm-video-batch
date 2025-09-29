#!/usr/bin/env python3
"""
Generate a short video using Gemini (GenAI) Python client following the
example from https://ai.google.dev/gemini-api/docs/video?example=dialogue

Usage:
  pip install google-genai
  export GEMINI_API_KEY="API KEY"
  python3 scripts/generate_video_gemini.py

This script:
- Creates a GenAI client using GEMINI_API_KEY
- Generates an image with Imagen
- Generates a video with VEO using the generated image
- Polls the operation until completion
- Downloads and saves the resulting MP4 to ./out/veo3_with_image_input.mp4
"""
import time
import os
import json # Import json
import sys # Import sys for command line arguments
from pathlib import Path
from datetime import datetime
from google import genai
import dotenv # Import dotenv
from PIL import Image # Import Image
from io import BytesIO # Import BytesIO
import shutil # Import shutil for file operations

OUT_DIR = Path("out")
OUT_DIR.mkdir(parents=True, exist_ok=True)
IMG_OUT_DIR = Path("out/img") # New directory for images
IMG_OUT_DIR.mkdir(parents=True, exist_ok=True) # Create the directory if it doesn't exist
JSON_USED_DIR = Path("out/prompt_json/used") # New directory for used JSON files
JSON_USED_DIR.mkdir(parents=True, exist_ok=True) # Create the directory if it doesn't exist

dotenv.load_dotenv() # Load environment variables from .env

def get_single_prompt_from_text(client, text_content, purpose, instruction=""):
    """
    Uses a Gemini model to extract or refine a prompt from text.
    """
    prompt_instruction = f"Given the following text, extract the single most suitable and accurate prompt for {purpose} generation. "
    if instruction:
        prompt_instruction = f"Given the following text, refine the prompt for {purpose} generation. {instruction} "
    
    response = client.models.generate_content(
        model="gemini-2.5-flash", # Use the model directly here
        contents=[
            f"{prompt_instruction}"
            "Focus on clarity, conciseness, and effectiveness for a generative AI model. "
            "Do not include any introductory or concluding remarks, just the prompt itself.\n\n"
            f"Text:\n{text_content}"
        ]
    )
    try:
        return response.text.strip()
    except ValueError:
        print(f"Error: Could not get text from Gemini response for {purpose}. Full response: {response}")
        return ""

def main():
    # Require the API key to be present as an env var. The official example uses
    # `client = genai.Client()` which reads credentials from the environment.
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        print("Error: set GEMINI_API_KEY or GOOGLE_API_KEY environment variable with your API key.")
        return

    # Create client using the SDK default behavior (matches the example on the docs)
    client = genai.Client()

    # Check for JSON file path argument
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/generate_video_gemini.py <path_to_json_file>")
        return
    
    json_file_path = sys.argv[1]

    # Read JSON file
    try:
        with open(json_file_path, "r") as f:
            data = json.load(f)
            video_prompt = data.get("video_prompt")
            image_prompt = data.get("image_prompt")
            video_name = data.get("video_name")
    except FileNotFoundError:
        print(f"Error: JSON file not found at {json_file_path}")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {json_file_path}")
        return
    
    if not video_prompt or not image_prompt or not video_name:
        print("Error: JSON file must contain 'video_prompt', 'image_prompt', and 'video_name' keys.")
        return

    print("Step 0: Prompts loaded from JSON.")

    # Refine the video prompt using Gemini 2.5 Flash
    refined_video_prompt = get_single_prompt_from_text(
        client,
        video_prompt,
        "video",
        "Do not describe the image. Focus on the action and narrative."
    )
    if not refined_video_prompt:
        print("Error: Failed to refine video prompt.")
        return
    video_prompt = refined_video_prompt
    print(f"Refined video prompt: {video_prompt}")

    # Ensure video_name does not have a duplicate .mp4 extension
    video_name_stem = Path(video_name).stem
    OUT_FILE = OUT_DIR / f"{video_name_stem}.mp4" # Use video_name from JSON

    print("Step 1: Generate an image with Imagen...")
    imagen = client.models.generate_images(
        model="imagen-4.0-generate-001",
        prompt=image_prompt,
    )

    if not getattr(imagen, "generated_images", None):
        print("Error: imagen did not return generated_images. Full response:", imagen)
        return

    # Save the generated image
    image_data = imagen.generated_images[0].image
    image_filename = IMG_OUT_DIR / f"{video_name}_gen4.png" # Using video_name as base
    try:
        image_data.save(image_filename) # Use the save method of the Image object
        print(f"Generated image saved to {image_filename}")
    except Exception as e:
        print(f"Error saving image: {e}")

    print("Image generated. Step 2: Generate video with VEO 3...")
    operation = client.models.generate_videos(
        model="veo-3.0-generate-preview",
        prompt=video_prompt,
        image=image_data,
    )

    # Poll the operation until the video is ready (matches the example flow)
    while not operation.done:
        print("Waiting for video generation to complete...")
        time.sleep(10)
        operation = client.operations.get(operation)

    # Expect generated_videos in the operation response
    resp = operation.response
    if not getattr(resp, "generated_videos", None):
        print("Error: operation completed but no generated_videos found. Full response:", resp)
        return

    video = resp.generated_videos[0]
    print("Downloading the video...")

    try:
        res = client.files.download(file=video.video)

        if hasattr(res, "save"):
            res.save(str(OUT_FILE))
        elif hasattr(video.video, "save"):
            video.video.save(str(OUT_FILE))
        elif hasattr(res, "read"):
            with open(OUT_FILE, "wb") as f:
                f.write(res.read())
        else:
            data = getattr(video.video, "data", None)
            if data:
                with open(OUT_FILE, "wb") as f:
                    f.write(data)
            else:
                print("Downloaded, but could not determine how to save the file. Inspect 'video' object:", video)
                return

    except Exception as e:
        print("Failed to download or save video:", e)
        return

    print(f"Generated video saved to {OUT_FILE}")

    # Move the processed JSON file to the 'used' directory
    try:
        shutil.move(json_file_path, JSON_USED_DIR / Path(json_file_path).name)
        print(f"Moved JSON file to {JSON_USED_DIR / Path(json_file_path).name}")
    except Exception as e:
        print(f"Error moving JSON file: {e}")

if __name__ == "__main__":
    main()
