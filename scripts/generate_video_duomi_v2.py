#!/usr/bin/env python3
"""
Generate a short video using Duomi AI's imageToVideo API.

Usage:
  pip install python-dotenv requests
  export DUOMI_API_KEY="YOUR_API_KEY"
  python3 scripts/generate_video_duomi_v2.py

This script:
- Processes JSON files from out/prompt_json/
- Uses image_url, video_prompt, and video_name from JSON files
- Moves processed JSON files to out/prompt_json/used/
- Calls the Duomi AI imageToVideo API to generate videos
"""
import time
import os
import json
import requests
import shutil
import random
from pathlib import Path
from datetime import datetime
import dotenv

OUT_DIR = Path("out")
OUT_DIR.mkdir(parents=True, exist_ok=True)
JSON_PROMPT_DIR = Path("out/prompt_json")
JSON_USED_DIR = Path("out/prompt_json/used")
JSON_USED_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "video_generation_log.jsonl"

dotenv.load_dotenv()

def select_video_prompt(data):
    """
    Select video prompt based on probability distribution:
    - 45% chance: refined_video_prompt
    - 25% chance: creative_video_prompt_3
    - 15% chance: creative_video_prompt_1
    - 15% chance: creative_video_prompt_2
    """
    # Get available prompts from data
    refined_prompt = data.get("refined_video_prompt")
    creative_prompt_1 = data.get("creative_video_prompt_1")
    creative_prompt_2 = data.get("creative_video_prompt_2")
    creative_prompt_3 = data.get("creative_video_prompt_3")
    fallback_prompt = data.get("video_prompt")
    
    # Generate random number between 0 and 100
    rand = random.randint(1, 100)
    
    # Select prompt based on probability distribution
    if rand <= 45 and refined_prompt:  # 45% chance
        selected_prompt = refined_prompt
        prompt_type = "refined_video_prompt"
    elif rand <= 70 and creative_prompt_3:  # 25% chance (45 + 25 = 70)
        selected_prompt = creative_prompt_3
        prompt_type = "creative_video_prompt_3"
    elif rand <= 85 and creative_prompt_1:  # 15% chance (70 + 15 = 85)
        selected_prompt = creative_prompt_1
        prompt_type = "creative_video_prompt_1"
    elif rand <= 100 and creative_prompt_2:  # 15% chance (85 + 15 = 100)
        selected_prompt = creative_prompt_2
        prompt_type = "creative_video_prompt_2"
    else:
        # Fallback to original video_prompt if selected prompt is not available
        selected_prompt = fallback_prompt
        prompt_type = "video_prompt (fallback)"
    
    print(f"Selected prompt type: {prompt_type} (random: {rand})")
    return selected_prompt, prompt_type

def log_video_generation(timestamp, image_url, video_name, processing_duration_seconds, json_file_path, status, prompt_type=None):
    """Logs video generation details to a JSONL file."""
    log_entry = {
        "timestamp": timestamp,
        "image_url": str(image_url) if image_url else "N/A",
        "video_name": str(video_name) if video_name else "N/A",
        "processing_duration_seconds": processing_duration_seconds,
        "json_file_path": str(json_file_path) if json_file_path else "N/A",
        "status": status,
        "prompt_type": prompt_type if prompt_type else "N/A"
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    print(f"Logged video generation: {status}")

def process_json_file(json_file_path):
    """Process a single JSON file and generate video."""
    generation_start_time = time.time()
    generation_status = "failure"
    final_video_name = None
    final_image_url = None
    selected_prompt_type = None

    try:
        DUOMI_API_KEY = os.environ.get("DUOMI_API_KEY")
        if not DUOMI_API_KEY:
            print("Error: set DUOMI_API_KEY environment variable with your API key.")
            return False

        # Load JSON data
        try:
            with open(json_file_path, "r") as f:
                data = json.load(f)
                video_prompt = data.get("video_prompt")
                video_name = data.get("video_name")
                image_url = data.get("image_url")
                
                # Optional Duomi specific parameters from JSON
                image_tail = data.get("image_tail", "")
                image_list = data.get("image_list", [])
                aspect_ratio = data.get("aspect_ratio", "16:9")
                callback_url = data.get("callback_url", "")
                duration = data.get("duration", 5)
        except FileNotFoundError:
            print(f"Error: JSON file not found at {json_file_path}")
            return False
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {json_file_path}")
            return False
        
        if not video_prompt or not video_name or not image_url:
            print(f"Error: JSON file must contain 'video_prompt', 'video_name', and 'image_url' keys. File: {json_file_path}")
            return False

        final_image_url = image_url
        
        # Select video prompt based on probability distribution
        selected_video_prompt, selected_prompt_type = select_video_prompt(data)
        
        print(f"Processing: {json_file_path}")
        print(f"Image URL: {image_url}")
        print(f"Selected video prompt: {selected_video_prompt}")
        print(f"Video name: {video_name}")

        video_name_stem = Path(video_name).stem
        OUT_FILE = OUT_DIR / f"{video_name_stem}.mp4"
        final_video_name = OUT_FILE

        print("Step 1: Calling Duomi AI image2video API...")
        HEADERS = {
            "Authorization": DUOMI_API_KEY,
            "Content-Type": "application/json"
        }
        DUOMI_API_BASE_URL = "http://duomiapi.com"

        try:
            payload = {
                "model_name": "kling-v2-1",
                "mode": "std",
                "duration": int(duration),
                "image": image_url,
                "image_tail": image_tail,
                "image_list": image_list,
                "aspect_ratio": aspect_ratio,
                "prompt": selected_video_prompt,
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
                return False
            
            if initial_response.get("code") != 0:
                print(f"Error from Duomi API: {initial_response.get('message', 'Unknown error')}")
                return False

            task_id = initial_response["data"]["task_id"]
            print(f"Video generation started. Task ID: {task_id}")

        except requests.exceptions.RequestException as e:
            print(f"Error calling Duomi API: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            return False
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return False

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
                        continue
                elif task_status in ["failed", "canceled"]:
                    print(f"Video generation failed or was canceled. Status: {task_status}")
                    generation_status = "failure"
                else:
                    print("Waiting for video generation to complete...")
                    time.sleep(10)
                    continue

                break

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

        # Move JSON file to used directory
        try:
            destination_path = JSON_USED_DIR / Path(json_file_path).name
            shutil.move(json_file_path, destination_path)
            print(f"Moved JSON file to {destination_path}")
        except Exception as e:
            print(f"Error moving JSON file: {e}")

        return generation_status == "success"

    except Exception as e:
        print(f"An unhandled error occurred processing {json_file_path}: {e}")
        generation_status = "failure"
        return False
    finally:
        processing_duration = time.time() - generation_start_time
        log_video_generation(
            timestamp=datetime.now().isoformat(),
            image_url=final_image_url,
            video_name=final_video_name,
            processing_duration_seconds=processing_duration,
            json_file_path=json_file_path,
            status=generation_status,
            prompt_type=selected_prompt_type
        )

def main():
    """Main function to process all JSON files in out/prompt_json/"""
    print("Starting video generation from JSON files...")
    
    # Check if JSON prompt directory exists
    if not JSON_PROMPT_DIR.exists():
        print(f"Error: Directory {JSON_PROMPT_DIR} does not exist.")
        return
    
    # Find all JSON files in the directory
    json_files = list(JSON_PROMPT_DIR.glob("*.json"))
    
    if not json_files:
        print(f"No JSON files found in {JSON_PROMPT_DIR}")
        return
    
    # Filter out error files
    valid_json_files = []
    for json_file in json_files:
        if json_file.name.lower().startswith("error_message"):
            print(f"Skipping error JSON file: {json_file}")
            continue
        valid_json_files.append(json_file)
    
    if not valid_json_files:
        print("No valid JSON files found to process.")
        return
    
    print(f"Found {len(valid_json_files)} JSON files to process:")
    for json_file in valid_json_files:
        print(f"  - {json_file.name}")
    
    # Process each JSON file
    successful_count = 0
    failed_count = 0
    
    for json_file in valid_json_files:
        print(f"\n{'='*60}")
        print(f"Processing file {successful_count + failed_count + 1}/{len(valid_json_files)}: {json_file.name}")
        print(f"{'='*60}")
        
        success = process_json_file(json_file)
        if success:
            successful_count += 1
            print(f"✅ Successfully processed: {json_file.name}")
        else:
            failed_count += 1
            print(f"❌ Failed to process: {json_file.name}")
    
    print(f"\n{'='*60}")
    print(f"Processing complete!")
    print(f"Successful: {successful_count}")
    print(f"Failed: {failed_count}")
    print(f"Total: {len(valid_json_files)}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
