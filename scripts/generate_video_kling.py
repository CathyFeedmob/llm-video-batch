#!/usr/bin/env python3
"""
Generate a short video using Kling AI's imageToVideo API.

Usage:
  pip install python-dotenv requests
  export KLING_API_KEY="YOUR_API_KEY"
  python3 scripts/generate_video_kling.py <path_to_image_file> <path_to_json_file>

This script:
- Reads an image file and video prompt from a JSON file.
- Calls the Kling AI imageToVideo API to generate a video.
- Polls the operation until completion.
- Downloads and saves the resulting MP4.
"""
import time
import os
import json
import sys
import requests
import shutil
from pathlib import Path
from datetime import datetime
import dotenv
import jwt
import base64 # Import base64
import google.generativeai as genai # Import google.generativeai
import subprocess # Import subprocess

OUT_DIR = Path("out")
OUT_DIR.mkdir(parents=True, exist_ok=True)
JSON_USED_DIR = Path("out/prompt_json/used")
JSON_USED_DIR.mkdir(parents=True, exist_ok=True)
IMG_GENERATED_DIR = Path("img/generated")
IMG_GENERATED_DIR.mkdir(parents=True, exist_ok=True)

dotenv.load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

def encode_jwt_token(ak, sk):
    headers = {
        "alg": "HS256",
        "typ": "JWT"
    }
    payload = {
        "iss": ak,
        "exp": int(time.time()) + 1800,
        "nbf": int(time.time()) - 5
    }
    token = jwt.encode(payload, sk, headers=headers)
    return token

def refine_prompt_with_gemini(original_prompt):
    """Refines the given prompt using Gemini 2.5 Flash."""
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        print(f"Refining prompt with Gemini 2.5 Flash: '{original_prompt}'")
        response = model.generate_content(
            f"Refine the following video prompt for an image-to-video model. Focus exclusively on movement, changes, human expression, or background alterations. Absolutely avoid any static image descriptions. Keep it concise (under 100 words): {original_prompt}"
        )
        refined_prompt = response.text.strip()
        print(f"Refined prompt: '{refined_prompt}'")
        return refined_prompt
    except Exception as e:
        print(f"Error refining prompt with Gemini: {e}")
        return original_prompt # Return original prompt if refinement fails

def main():
    print("Executing scripts/test_gemini_vision.py to prepare image and JSON data...")
    result = subprocess.run(["python3", "scripts/test_gemini_vision.py"], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error executing test_gemini_vision.py: {result.stderr}")
        return
    print("test_gemini_vision.py executed successfully.")

    KLING_ACCESS_KEY = os.environ.get("KLING_ACCESS_KEY")
    KLING_SECRET_KEY = os.environ.get("KLING_SECRET_KEY")
    if not KLING_ACCESS_KEY or not KLING_SECRET_KEY:
        print("Error: set KLING_ACCESS_KEY and KLING_SECRET_KEY environment variables with your API keys.")
        return
    
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        print("Error: set GEMINI_API_KEY environment variable with your API key.")
        return

    api_token = encode_jwt_token(KLING_ACCESS_KEY, KLING_SECRET_KEY)

    JSON_PROMPT_DIR = Path("out/prompt_json")
    IMG_READY_DIR = Path("img/ready")

    image_file_path = None
    json_file_path = None

    if len(sys.argv) < 3:
        print("No image or JSON file paths provided. Attempting to find files automatically...")
        json_files = list(JSON_PROMPT_DIR.glob("*.json"))
        if not json_files:
            print(f"Error: No JSON files found in {JSON_PROMPT_DIR}. Please provide paths or ensure files exist.")
            return
        
        # For simplicity, pick the first JSON file found
        json_file_path = json_files[0]
        json_stem = json_file_path.stem
        print(f"Found JSON file: {json_file_path}")

        # Try to find a corresponding image file in img/ready/
        for ext in [".png", ".jpg", ".jpeg"]:
            potential_image_path = IMG_READY_DIR / f"{json_stem}{ext}"
            if potential_image_path.exists():
                image_file_path = potential_image_path
                print(f"Found corresponding image file: {image_file_path}")
                break
        
        if not image_file_path:
            print(f"Error: No image file found in {IMG_READY_DIR} corresponding to {json_stem}. Looked for {json_stem}.png, {json_stem}.jpg, {json_stem}.jpeg")
            return
    else:
        image_file_path = sys.argv[1]
        json_file_path = sys.argv[2]
        if not Path(image_file_path).exists():
            print(f"Error: Image file not found at {image_file_path}")
            return

    try:
        with open(json_file_path, "r") as f:
            data = json.load(f)
            video_prompt = data.get("video_prompt")
            video_name = data.get("video_name")
    except FileNotFoundError:
        print(f"Error: JSON file not found at {json_file_path}")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {json_file_path}")
        return
    
    if not video_prompt or not video_name:
        print("Error: JSON file must contain 'video_prompt' and 'video_name' keys.")
        return

    print(f"Original video prompt: {video_prompt}") # Print the original video prompt
    refined_video_prompt = refine_prompt_with_gemini(video_prompt)
    print(f"Refined video prompt: {refined_video_prompt}") # Print the refined video prompt
    video_prompt = refined_video_prompt # Use the refined prompt for video generation
    
    print("Step 0: Prompts and image path loaded.")

    video_name_stem = Path(video_name).stem
    OUT_FILE = OUT_DIR / f"{video_name_stem}.mp4"

    print("Step 1: Calling Kling AI image2video API...")
    HEADERS = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    KLING_API_BASE_URL = "https://api-beijing.klingai.com" # Base URL for Kling API

    try:
        # Read image from local file and base64 encode it
        print(f"Reading image from {image_file_path} and base64 encoding...")
        image_content = Path(image_file_path).read_bytes()
        encoded_image = base64.b64encode(image_content).decode('utf-8')
        print("Image read and base64 encoded.")

        payload = {
            "model_name": "kling-v2-1",
            "mode": "std",
            "duration": "5",
            "image": encoded_image, # Send base64 encoded image
            "prompt": video_prompt,
            "negative_prompt": "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走",
            "cfg_scale": 0.5
        }
        response = requests.post(
            f"{KLING_API_BASE_URL}/v1/videos/image2video",
            headers=HEADERS,
            json=payload # Send payload as JSON
        )
        response.raise_for_status()
        try:
            initial_response = response.json()
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from Kling API response. Raw response: {response.text}")
            return
        
        if initial_response.get("code") != 0: # Changed from 200 to 0 for success
            print(f"Error from Kling API: {initial_response.get('message', 'Unknown error')}")
            return

        task_id = initial_response["data"]["task_id"]
        print(f"Video generation started. Task ID: {task_id}")

    except requests.exceptions.RequestException as e:
        print(f"Error calling Kling API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text}")
        return
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return

    # Poll for video generation status
    start_time = time.time()
    while True:
        try:
            status_response = requests.get(
                f"{KLING_API_BASE_URL}/v1/videos/image2video/{task_id}", # Updated polling URL based on docs
                headers=HEADERS
            )
            status_response.raise_for_status()
            status_data = status_response.json()

            if status_data.get("code") != 0: # Changed from 200 to 0 for success
                print(f"Error getting task status: {status_data.get('message', 'Unknown error')}")
                time.sleep(10) # Wait before retrying
                continue

            task_status = status_data["data"]["task_status"]
            # Correctly extract video_url from nested structure
            video_url = status_data["data"].get("task_result", {}).get("videos", [{}])[0].get("url")
            
            elapsed_time = time.time() - start_time
            print(f"Current video generation status: {task_status}, Video URL: {video_url}, Elapsed time: {elapsed_time:.2f}s")

            if task_status == "succeed" and video_url:
                print("Video generation complete. Downloading video...")
                video_response = requests.get(video_url, stream=True)
                video_response.raise_for_status()

                with open(OUT_FILE, "wb") as f:
                    for chunk in video_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"Generated video saved to {OUT_FILE}")
                print(f"Total video generation and download time: {elapsed_time:.2f}s")
                break
            elif task_status in ["failed", "canceled"]: # Changed to lowercase based on API response
                print(f"Video generation failed or was canceled. Status: {task_status}")
                return
            else:
                print("Waiting for video generation to complete...")
                time.sleep(10) # Poll every 10 seconds

        except requests.exceptions.RequestException as e:
            print(f"Error polling Kling API status: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            return
        except Exception as e:
            print(f"An unexpected error occurred during polling: {e}")
            return

    # Save the refined video prompt to the JSON file before moving
    try:
        with open(json_file_path, "r+") as f:
            data = json.load(f)
            data["refined_video_prompt"] = refined_video_prompt
            f.seek(0)  # Rewind to the beginning of the file
            json.dump(data, f, indent=2)
            f.truncate() # Truncate any remaining old content
        print(f"Saved refined video prompt to {json_file_path}")
    except Exception as e:
        print(f"Error saving refined video prompt to JSON file: {e}")

    # Move the processed JSON file to the 'used' directory
    try:
        shutil.move(json_file_path, JSON_USED_DIR / Path(json_file_path).name)
        print(f"Moved JSON file to {JSON_USED_DIR / Path(json_file_path).name}")
    except Exception as e:
        print(f"Error moving JSON file: {e}")

    # Move the input image file to the 'generated' directory
    try:
        shutil.move(image_file_path, IMG_GENERATED_DIR / Path(image_file_path).name)
        print(f"Moved image file to {IMG_GENERATED_DIR / Path(image_file_path).name}")
    except Exception as e:
        print(f"Error moving image file: {e}")

if __name__ == "__main__":
    main()
