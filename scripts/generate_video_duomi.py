#!/usr/bin/env python3
"""
Generate a short video using Duomi AI's imageToVideo API.

Usage:
  pip install python-dotenv requests
  export DUOMI_API_KEY="YOUR_API_KEY"
  python3 scripts/generate_video_duomi.py <image_url> <path_to_json_file>

This script:
- Checks for existing JSON files in out/prompt_json and matches them with images in img/ready
- Uses existing JSON files instead of regenerating them when possible
- Only calls test_gemini_vision.py when no matching JSON file exists
- Calls the Duomi AI imageToVideo API to generate a video
- Polls the operation until completion
- Downloads and saves the resulting MP4
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
import google.generativeai as genai
from google.generativeai import types
import subprocess

OUT_DIR = Path("out")
OUT_DIR.mkdir(parents=True, exist_ok=True)
JSON_USED_DIR = Path("out/prompt_json/used")
JSON_USED_DIR.mkdir(parents=True, exist_ok=True)
IMG_GENERATED_DIR = Path("img/generated")
IMG_GENERATED_DIR.mkdir(parents=True, exist_ok=True)
IMG_READY_DIR = Path("img/ready")
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "video_generation_log.jsonl"

dotenv.load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL_NAME = os.getenv("OPENROUTER_MODEL_NAME")
USE_OPENROUTER_FALLBACK = os.getenv("USE_OPENROUTER_FALLBACK", "false").lower() == "true"

def openrouter_generate_content(model_name, contents):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    messages = []
    for content_part in contents:
        if isinstance(content_part, types.Part):
            if content_part.text:
                messages.append({"role": "user", "content": content_part.text})
            elif content_part.inline_data:
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{content_part.inline_data.mime_type};base64,{content_part.inline_data.data.decode('utf-8')}"}}
                    ]
                })
        else:
            messages.append({"role": "user", "content": content_part})

    payload = {
        "model": model_name,
        "messages": messages
    }

    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    response.raise_for_status()

    openrouter_response = response.json()
    
    class MockTextResponse:
        def __init__(self, text):
            self.text = text
            
    class MockContentResponse:
        def __init__(self, text_response):
            self.text = text_response.text
            self.parts = [types.Part(text=text_response.text)]

    if openrouter_response and openrouter_response.get("choices"):
        generated_text = openrouter_response["choices"][0]["message"]["content"]
        return MockContentResponse(MockTextResponse(generated_text))
    else:
        raise Exception("OpenRouter response did not contain expected content.")

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
    except genai.errors.ServerError as e:
        if e.status_code == 503 and USE_OPENROUTER_FALLBACK:
            print("Gemini API overloaded (503). Falling back to OpenRouter for prompt refinement.")
            response = openrouter_generate_content(
                model_name=OPENROUTER_MODEL_NAME,
                contents=[
                    f"Refine the following video prompt for an image-to-video model. Focus exclusively on movement, changes, human expression, or background alterations. Absolutely avoid any static image descriptions. Keep it concise (under 100 words): {original_prompt}"
                ]
            )
            refined_prompt = response.text.strip()
            print(f"Refined prompt (via OpenRouter): '{refined_prompt}'")
            return refined_prompt
        else:
            print(f"Error refining prompt with Gemini: {e}")
            return original_prompt
    except Exception as e:
        print(f"Error refining prompt with Gemini: {e}")
        return original_prompt

def log_video_generation(timestamp, image_used, video_name, processing_duration_seconds, json_file_path, status):
    """Logs video generation details to a JSONL file."""
    log_entry = {
        "timestamp": timestamp,
        "image_used": str(image_used) if image_used else "N/A",
        "video_name": str(video_name) if video_name else "N/A",
        "processing_duration_seconds": processing_duration_seconds,
        "json_file_path": str(json_file_path) if json_file_path else "N/A",
        "status": status
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    print(f"Logged video generation: {status}")

def find_matching_json_for_image(image_path, json_dir):
    """Find a JSON file that matches the given image based on pic_name."""
    image_name = Path(image_path).name
    
    # Look for JSON files in the directory
    for json_file in json_dir.glob("*.json"):
        # Skip JSON files that start with "Error_message" (case-insensitive)
        if json_file.name.lower().startswith("error_message"):
            print(f"Skipping failure JSON file: {json_file}")
            continue
            
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
                pic_name = data.get("pic_name")
                if pic_name and pic_name == image_name:
                    print(f"Found matching JSON file: {json_file} for image: {image_name}")
                    return json_file
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error reading JSON file {json_file}: {e}")
            continue
    
    return None

def find_images_without_json(img_ready_dir, json_dir):
    """Find images in img/ready that don't have corresponding JSON files."""
    images_without_json = []
    
    # Get all image files in img/ready
    image_extensions = {'.png', '.jpg', '.jpeg'}
    for image_file in img_ready_dir.iterdir():
        if image_file.is_file() and image_file.suffix.lower() in image_extensions:
            # Check if there's a matching JSON file
            matching_json = find_matching_json_for_image(image_file, json_dir)
            if not matching_json:
                images_without_json.append(image_file)
    
    return images_without_json

def main():
    # Initialize variables for logging
    generation_start_time = time.time()
    generation_status = "failure"
    final_video_name = None
    final_image_file_path = None
    final_json_file_path = None

    try:
        DUOMI_API_KEY = os.environ.get("DUOMI_API_KEY")
        if not DUOMI_API_KEY:
            print("Error: set DUOMI_API_KEY environment variable with your API key.")
            return
        
        GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
        if not GEMINI_API_KEY:
            print("Error: set GEMINI_API_KEY environment variable with your API key.")
            return

        JSON_PROMPT_DIR = Path("out/prompt_json")
        
        image_file_path = None
        json_file_path = None

        # Check if specific image and JSON paths were provided as command line arguments
        if len(sys.argv) > 1:
            image_file_path = sys.argv[1]
        
        if len(sys.argv) > 2:
            json_file_path = sys.argv[2]

        # If no JSON file path provided, look for existing JSON files and match with images
        if not json_file_path:
            print("No JSON file path provided. Checking for existing JSON files and matching images...")
            
            # Find all JSON files and try to match them with images in img/ready
            json_files = list(JSON_PROMPT_DIR.glob("*.json"))
            matched_pairs = []
            
            for json_file in json_files:
                # Skip JSON files that start with "Error_message" (case-insensitive)
                if json_file.name.lower().startswith("error_message"):
                    print(f"Skipping failure JSON file: {json_file}")
                    continue
                    
                try:
                    with open(json_file, "r") as f:
                        data = json.load(f)
                        pic_name = data.get("pic_name")
                        if pic_name:
                            image_path = IMG_READY_DIR / pic_name
                            if image_path.exists():
                                matched_pairs.append((image_path, json_file))
                                print(f"Found matching pair: {pic_name} <-> {json_file.name}")
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    print(f"Error reading JSON file {json_file}: {e}")
                    continue
            
            if matched_pairs:
                # Use the first matched pair
                image_file_path, json_file_path = matched_pairs[0]
                print(f"Using matched pair: {image_file_path} and {json_file_path}")
            else:
                # No matched pairs found, check if we need to generate JSON for any images
                images_without_json = find_images_without_json(IMG_READY_DIR, JSON_PROMPT_DIR)
                
                if images_without_json:
                    print(f"Found {len(images_without_json)} images without corresponding JSON files.")
                    print("Executing scripts/test_gemini_vision.py to generate JSON for the first image...")
                    result = subprocess.run(["python3", "scripts/test_gemini_vision.py"], capture_output=True, text=True)
                    if result.returncode != 0:
                        print(f"Error executing test_gemini_vision.py: {result.stderr}")
                        return
                    print("test_gemini_vision.py executed successfully.")
                    
                    # Now try to find the newly created JSON file
                    json_files = sorted(JSON_PROMPT_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)
                    if json_files:
                        json_file_path = json_files[0]
                        print(f"Found newly created JSON file: {json_file_path}")
                    else:
                        print("Error: No JSON files found after running test_gemini_vision.py")
                        return
                else:
                    print("No images found in img/ready directory.")
                    return

        # If we still don't have a JSON file path, try to find the latest one
        if not json_file_path:
            print("Attempting to find the latest JSON file automatically...")
            json_files = sorted(JSON_PROMPT_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)
            if not json_files:
                print(f"Error: No JSON files found in {JSON_PROMPT_DIR}. Please provide a JSON file path or ensure files exist.")
                return
            json_file_path = json_files[0]
            print(f"Found JSON file: {json_file_path}")

        final_json_file_path = json_file_path

        try:
            with open(json_file_path, "r") as f:
                data = json.load(f)
                video_prompt = data.get("video_prompt")
                video_name = data.get("video_name")
                pic_name = data.get("pic_name")
                image_url_from_json = data.get("image_url") # Get image_url from JSON
                # Duomi specific parameters from JSON, if available
                image_tail = data.get("image_tail", "")
                image_list = data.get("image_list", [])
                aspect_ratio = data.get("aspect_ratio", "16:9")
                callback_url = data.get("callback_url", "")
                duration = data.get("duration", 5) # Default to 5 seconds
        except FileNotFoundError:
            print(f"Error: JSON file not found at {json_file_path}")
            return
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {json_file_path}")
            return
        
        if not video_prompt or not video_name:
            print("Error: JSON file must contain 'video_prompt' and 'video_name' keys.")
            return

        # Use image_url from JSON if available, otherwise use placeholder or abort
        if image_url_from_json:
            image_file_path = image_url_from_json
            print(f"Using image URL from JSON: {image_file_path}")
        elif len(sys.argv) > 1: # If image_file_path was provided as a command line argument
            image_file_path = sys.argv[1]
            print(f"Using image URL from command line argument: {image_file_path}")
        else:
            print("Error: No image_url found in JSON and no image URL provided as command line argument. Aborting.")
            return
        
        final_image_file_path = image_file_path

        print(f"Original video prompt: {video_prompt}")
        refined_video_prompt = refine_prompt_with_gemini(video_prompt)
        print(f"Refined video prompt: '{refined_video_prompt}'")
        video_prompt = refined_video_prompt
        
        print("Step 0: Prompts and image path loaded.")

        video_name_stem = Path(video_name).stem
        OUT_FILE = OUT_DIR / f"{video_name_stem}.mp4"
        final_video_name = OUT_FILE

        print("Step 1: Calling Duomi AI image2video API...")
        HEADERS = {
            "Authorization": DUOMI_API_KEY, # Direct API key
            "Content-Type": "application/json"
        }
        DUOMI_API_BASE_URL = "http://duomiapi.com"

        try:
            payload = {
                "model_name": "kling-v2-1", # User specified
                "mode": "std",
                "duration": int(duration), # Ensure integer
                "image": image_file_path, # Image URL
                "image_tail": image_tail,
                "image_list": image_list,
                "aspect_ratio": aspect_ratio,
                "prompt": video_prompt,
                "negative_prompt": "Over-saturated tones, overexposed, static, blurred details, subtitles, style, artwork, painting, frame, motionless, overall grayish, worst quality, low quality, JPEG compression artifacts, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, limbs in distorted shapes, fused fingers, motionless frames, chaotic backgrounds, three legs, crowded background with many people, walking backward.",
                "cfg_scale": 0.5,
                "callback_url": callback_url
            }
            response = requests.post(
                f"{DUOMI_API_BASE_URL}/api/video/kling/v1/videos/image2video",
                headers=HEADERS,
                json=payload
            )
            response.raise_for_status()
            try:
                initial_response = response.json()
            except json.JSONDecodeError:
                print(f"Error: Could not decode JSON from Duomi API response. Raw response: {response.text}")
                return
            
            if initial_response.get("code") != 0:
                print(f"Error from Duomi API: {initial_response.get('message', 'Unknown error')}")
                return

            task_id = initial_response["data"]["task_id"]
            print(f"Video generation started. Task ID: {task_id}")

        except requests.exceptions.RequestException as e:
            print(f"Error calling Duomi API: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            return
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return

        # Poll for video generation status
        poll_start_time = time.time()
        while True:
            try:
                status_response = requests.get(
                    f"{DUOMI_API_BASE_URL}/api/video/kling/v1/videos/image2video/{task_id}",
                    headers=HEADERS
                )
                status_response.raise_for_status()
                status_data = status_response.json()

                if status_data.get("code") != 0:
                    print(f"Error getting task status: {status_data.get('message', 'Unknown error')}")
                    time.sleep(10)
                    continue

                task_status = status_data["data"]["task_status"]
                
                elapsed_time = time.time() - poll_start_time
                print(f"Current video generation status: {task_status}, Elapsed time: {elapsed_time:.2f}s")

                if task_status == "succeed":
                    video_url = status_data["data"].get("task_result", {}).get("videos", [{}])[0].get("url")
                    if video_url:
                        print("Video generation complete. Downloading video...")
                        video_response = requests.get(video_url, stream=True)
                        video_response.raise_for_status()

                        with open(OUT_FILE, "wb") as f:
                            for chunk in video_response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        print(f"Generated video saved to {OUT_FILE}")
                        print(f"Total video generation and download time: {elapsed_time:.2f}s")
                        generation_status = "success"
                    else:
                        print("Video generation succeeded, but no video URL found in response. Waiting for video URL...")
                        time.sleep(10)
                        continue # Continue polling if URL not found yet
                elif task_status in ["failed", "canceled"]:
                    print(f"Video generation failed or was canceled. Status: {task_status}")
                    generation_status = "failure"
                else:
                    print("Waiting for video generation to complete...")
                    time.sleep(10)
                    continue # Continue polling if not succeeded/failed/canceled

                # Move the image from img/ready to img/generated regardless of success or failure
                if pic_name:
                    source_image_path = IMG_READY_DIR / pic_name
                    destination_image_path = IMG_GENERATED_DIR / pic_name
                    try:
                        if source_image_path.exists():
                            shutil.move(source_image_path, destination_image_path)
                            print(f"Moved image {pic_name} from {IMG_READY_DIR} to {IMG_GENERATED_DIR}")
                        else:
                            print(f"Image {pic_name} not found in {IMG_READY_DIR}. Skipping move.")
                    except Exception as e:
                        print(f"Error moving image {pic_name}: {e}")
                else:
                    print("Image name (pic_name) not found in JSON. Cannot move image.")
                
                break # Break the loop once status is succeed, failed, or canceled

            except requests.exceptions.RequestException as e:
                print(f"Error polling Duomi API status: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"Response content: {e.response.text}")
                generation_status = "failure"
                break
            except Exception as e:
                print(f"An unexpected error occurred during polling: {e}")
                generation_status = "failure"
                break

        try:
            with open(json_file_path, "r+") as f:
                data = json.load(f)
                data["refined_video_prompt"] = refined_video_prompt
                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()
            print(f"Saved refined video prompt to {json_file_path}")
        except Exception as e:
            print(f"Error saving refined video prompt to JSON file: {e}")

        try:
            shutil.move(json_file_path, JSON_USED_DIR / Path(json_file_path).name)
            print(f"Moved JSON file to {JSON_USED_DIR / Path(json_file_path).name}")
        except Exception as e:
            print(f"Error moving JSON file: {e}")

        # The image_file_path is a URL, so it cannot be moved like a local file.
        # This block is intentionally commented out or removed.
        # try:
        #     shutil.move(image_file_path, IMG_GENERATED_DIR / Path(image_file_path).name)
        #     print(f"Moved image file to {IMG_GENERATED_DIR / Path(image_file_path).name}")
        # except Exception as e:
        #     print(f"Error moving image file: {e}")

    except Exception as e:
        print(f"An unhandled error occurred in main: {e}")
        generation_status = "failure"
    finally:
        processing_duration = time.time() - generation_start_time
        log_video_generation(
            timestamp=datetime.now().isoformat(),
            image_used=final_image_file_path,
            video_name=final_video_name,
            processing_duration_seconds=processing_duration,
            json_file_path=final_json_file_path,
            status=generation_status
        )

if __name__ == "__main__":
    main()
