#!/usr/bin/env python3
"""
Generate a short video using Duomi AI's imageToVideo API (proxy for Kling).

Usage:
  pip install python-dotenv requests
  export DUOMI_API_KEY="YOUR_API_KEY"
  python3 scripts/generate_video_duomi_v2.py <path_to_image_file> <path_to_json_file>

This script:
- Reads an image file and video prompt from a JSON file.
- Calls the Duomi AI imageToVideo API to generate a video.
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
import base64
import google.generativeai as genai
from google.generativeai import types
import subprocess

OUT_DIR = Path("out")
OUT_DIR.mkdir(parents=True, exist_ok=True)
JSON_USED_DIR = Path("out/prompt_json/used")
JSON_USED_DIR.mkdir(parents=True, exist_ok=True)
IMG_GENERATED_DIR = Path("img/generated")
IMG_GENERATED_DIR.mkdir(parents=True, exist_ok=True)
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

def upload_image_to_freeimage_host(image_path):
    """Uploads an image to freeimage.host and returns the URL."""
    FREEIMAGE_API_KEY = os.getenv("FREEIMAGE_API_KEY")
    if not FREEIMAGE_API_KEY:
        print("Error: FREEIMAGE_API_KEY environment variable not set. Cannot upload image.")
        return None

    try:
        with open(image_path, "rb") as f:
            image_data = f.read()

        files = {
            'source': (os.path.basename(image_path), image_data, 'image/png'), # Assuming PNG, adjust if needed
            'key': (None, FREEIMAGE_API_KEY),
            'format': (None, 'json')
        }
        
        print(f"Uploading image {image_path} to freeimage.host...")
        response = requests.post("https://freeimage.host/api/1/upload", files=files)
        response.raise_for_status()
        
        upload_result = response.json()
        if upload_result.get("status_code") == 200 and upload_result.get("success"):
            image_url = upload_result["image"]["url"]
            print(f"Image uploaded successfully: {image_url}")
            return image_url
        else:
            print(f"Freeimage.host upload failed: {upload_result.get('error', {}).get('message', 'Unknown error')}")
            return None
    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error uploading to freeimage.host: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during freeimage.host upload: {e}")
        return None

def main():
    # Initialize variables for logging
    generation_start_time = time.time()
    generation_status = "failure"
    final_video_name = None
    final_image_file_path = None
    final_json_file_path = None

    try:
        print("Executing scripts/test_gemini_vision.py to prepare image and JSON data...")
        result = subprocess.run(["python3", "scripts/test_gemini_vision.py"], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error executing test_gemini_vision.py: {result.stderr}")
            return
        print("test_gemini_vision.py executed successfully.")

        DUOMI_API_KEY = os.environ.get("DUOMI_API_KEY")
        if not DUOMI_API_KEY:
            print("Error: set DUOMI_API_KEY environment variable with your API key.")
            return
        
        GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
        if not GEMINI_API_KEY:
            print("Error: set GEMINI_API_KEY environment variable with your API key.")
            return

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
            
            json_file_path = json_files[0]
            json_stem = json_file_path.stem
            print(f"Found JSON file: {json_file_path}")

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

        final_json_file_path = json_file_path

        try:
            with open(json_file_path, "r") as f:
                data = json.load(f)
                video_prompt = data.get("video_prompt")
                video_name = data.get("video_name")
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

        print(f"Original video prompt: {video_prompt}")
        refined_video_prompt = refine_prompt_with_gemini(video_prompt)
        print(f"Refined video prompt: '{refined_video_prompt}'")
        video_prompt = refined_video_prompt
        
        print("Step 0: Prompts and image path loaded.")

        video_name_stem = Path(video_name).stem
        OUT_FILE = OUT_DIR / f"{video_name_stem}.mp4"
        final_video_name = OUT_FILE

        # Handle image upload if it's a local file
        image_url_for_duomi = image_file_path
        if Path(image_file_path).exists():
            print(f"Local image file detected: {image_file_path}. Uploading to freeimage.host...")
            uploaded_url = upload_image_to_freeimage_host(image_file_path)
            if uploaded_url:
                image_url_for_duomi = uploaded_url
                final_image_file_path = uploaded_url # Update for logging
            else:
                print("Image upload to freeimage.host failed. Cannot proceed with video generation.")
                return
        else:
            print(f"Image path is not a local file: {image_file_path}. Assuming it's a URL.")
            final_image_file_path = image_file_path # Keep original for logging if it's already a URL

        print("Step 1: Calling Duomi AI image2video API...")
        print(f"Using image URL for Duomi API: {image_url_for_duomi}") # Added print statement
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
                "image": image_url_for_duomi, # Image URL from freeimage.host or original URL
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

                # Ensure 'data' and 'task_status' exist in the response
                if not status_data.get("data") or "task_status" not in status_data["data"]:
                    print(f"Warning: 'data' or 'task_status' not found in Duomi API response. Response: {status_data}")
                    time.sleep(10)
                    continue

                task_status = status_data["data"]["task_status"]
                video_url = status_data["data"].get("task_result", {}).get("videos", [{}])[0].get("url")
                
                elapsed_time = time.time() - poll_start_time
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
                    generation_status = "success"
                    break
                elif task_status in ["failed", "canceled"]:
                    print(f"Video generation failed or was canceled. Status: {task_status}")
                    generation_status = "failure"
                    break
                else:
                    print("Waiting for video generation to complete...")
                    time.sleep(10)

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

        # Move the original local image file to IMG_GENERATED_DIR if it was a local file
        # and not already a URL.
        if Path(image_file_path).exists() and not str(image_file_path).startswith("http"):
            try:
                shutil.move(image_file_path, IMG_GENERATED_DIR / Path(image_file_path).name)
                print(f"Moved image file to {IMG_GENERATED_DIR / Path(image_file_path).name}")
            except Exception as e:
                print(f"Error moving image file: {e}")
        else:
            print(f"Image file was not a local path or was already a URL, skipping move to {IMG_GENERATED_DIR}.")

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
