#!/usr/bin/env python3
"""
Generate a short video using Duomi AI's imageToVideo API with SQLite database integration.

Usage:
  pip install python-dotenv requests
  export DUOMI_API_KEY="YOUR_API_KEY"
  python3 scripts/generate_video_duomi_v2.py

This script:
- Queries pending videos from SQLite database
- Uses refined_video_prompt from database
- Updates video status in database during generation
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

# Import database manager
from database_manager import DatabaseManager

OUT_DIR = Path("out")
OUT_DIR.mkdir(parents=True, exist_ok=True)
JSON_PROMPT_DIR = Path("out/prompt_json")
JSON_USED_DIR = Path("out/prompt_json/used")
JSON_USED_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "video_generation_log.jsonl"

dotenv.load_dotenv()

def get_video_prompt_from_db(video_record):
    """
    Get the refined video prompt from database record.
    Always use refined_video_prompt as specified in requirements.
    """
    refined_prompt = video_record.get("refined_video_prompt")
    
    if refined_prompt:
        selected_prompt = refined_prompt
        prompt_type = "refined"
        print(f"Using refined video prompt: {prompt_type}")
        return selected_prompt, prompt_type
    else:
        # Fallback to base video prompt if refined is not available
        fallback_prompt = video_record.get("video_prompt")
        prompt_type = "base"
        print(f"Refined prompt not available, using fallback: {prompt_type}")
        return fallback_prompt, prompt_type

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

def process_video_from_db(db_manager, video_record):
    """Process a single video record from database and generate video."""
    generation_start_time = time.time()
    generation_status = "failed"
    final_video_name = None
    final_image_url = None
    selected_prompt_type = None
    video_id = video_record['id']

    try:
        DUOMI_API_KEY = os.environ.get("DUOMI_API_KEY")
        if not DUOMI_API_KEY:
            print("Error: set DUOMI_API_KEY environment variable with your API key.")
            return False

        # Extract data from database record
        video_filename = video_record.get("video_filename")
        image_url = video_record.get("upload_url")
        
        # Get video prompt from database (use refined prompt)
        selected_video_prompt, selected_prompt_type = get_video_prompt_from_db(video_record)
        
        if not selected_video_prompt or not video_filename or not image_url:
            error_msg = "Missing required data: video_prompt, video_filename, or image_url"
            print(f"Error: {error_msg}")
            db_manager.update_video_status(video_id, "failed", error_message=error_msg)
            return False

        final_image_url = image_url
        
        print(f"Processing Video ID: {video_id}")
        print(f"Image URL: {image_url}")
        print(f"Selected video prompt: {selected_video_prompt}")
        print(f"Video filename: {video_filename}")

        video_name_stem = Path(video_filename).stem
        OUT_FILE = OUT_DIR / f"{video_name_stem}.mp4"
        final_video_name = OUT_FILE

        # Update database status to "generating"
        print(f"📝 Updating video status to 'generating'...")
        db_manager.update_video_status(video_id, "generating")

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
                "duration": 5,  # Default duration
                "image": image_url,
                "image_tail": "",
                "image_list": [],
                "aspect_ratio": "16:9",
                "prompt": selected_video_prompt,
                "negative_prompt": "Over-saturated tones, overexposed, static, blurred details, subtitles, style, artwork, painting, frame, motionless, overall grayish, worst quality, low quality, JPEG compression artifacts, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, limbs in distorted shapes, fused fingers, motionless frames, chaotic backgrounds, three legs, crowded background with many people, walking backward.",
                "cfg_scale": 0.5,
                "callback_url": ""
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
                error_msg = f"Could not decode JSON from Duomi API response. Raw response: {response.text}"
                print(f"Error: {error_msg}")
                db_manager.update_video_status(video_id, "failed", error_message=error_msg)
                return False
            
            if initial_response.get("code") != 0:
                error_msg = f"Error from Duomi API: {initial_response.get('message', 'Unknown error')}"
                print(f"Error: {error_msg}")
                db_manager.update_video_status(video_id, "failed", error_message=error_msg)
                return False

            task_id = initial_response["data"]["task_id"]
            print(f"Video generation started. Task ID: {task_id}")

        except requests.exceptions.RequestException as e:
            error_msg = f"Error calling Duomi API: {e}"
            print(error_msg)
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f" Response: {e.response.text}"
                print(f"Response content: {e.response.text}")
            db_manager.update_video_status(video_id, "failed", error_message=error_msg)
            return False
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}"
            print(error_msg)
            db_manager.update_video_status(video_id, "failed", error_message=error_msg)
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
                        
                        file_size = OUT_FILE.stat().st_size
                        print(f"Generated video saved to {OUT_FILE}")
                        print(f"Total video generation and download time: {elapsed_time:.2f}s")
                        
                        # Update database with success
                        db_manager.update_video_status(
                            video_id, 
                            "completed", 
                            video_path=str(OUT_FILE),
                            file_size=file_size,
                            generation_time=elapsed_time
                        )
                        generation_status = "completed"
                    else:
                        print("Video generation succeeded, but no video URL found in response. Waiting for video URL...")
                        time.sleep(10)
                        continue
                elif task_status in ["failed", "canceled"]:
                    error_msg = f"Video generation failed or was canceled. Status: {task_status}"
                    print(error_msg)
                    db_manager.update_video_status(video_id, "failed", error_message=error_msg)
                    generation_status = "failed"
                else:
                    print("Waiting for video generation to complete...")
                    time.sleep(10)
                    continue

                break

            except requests.exceptions.RequestException as e:
                error_msg = f"Error polling Duomi API status: {e}"
                print(error_msg)
                if hasattr(e, 'response') and e.response is not None:
                    error_msg += f" Response: {e.response.text}"
                    print(f"Response content: {e.response.text}")
                db_manager.update_video_status(video_id, "failed", error_message=error_msg)
                generation_status = "failed"
                break
            except Exception as e:
                error_msg = f"An unexpected error occurred during polling: {e}"
                print(error_msg)
                db_manager.update_video_status(video_id, "failed", error_message=error_msg)
                generation_status = "failed"
                break

        return generation_status == "completed"

    except Exception as e:
        error_msg = f"An unhandled error occurred processing video ID {video_id}: {e}"
        print(error_msg)
        db_manager.update_video_status(video_id, "failed", error_message=error_msg)
        generation_status = "failed"
        return False
    finally:
        processing_duration = time.time() - generation_start_time
        log_video_generation(
            timestamp=datetime.now().isoformat(),
            image_url=final_image_url,
            video_name=final_video_name,
            processing_duration_seconds=processing_duration,
            json_file_path=f"video_id_{video_id}",
            status=generation_status,
            prompt_type=selected_prompt_type
        )

def main():
    """Main function to process pending videos from SQLite database."""
    print("Starting video generation from SQLite database...")
    
    # Initialize database manager
    try:
        db_manager = DatabaseManager()
        db_manager.initialize_database()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        return
    
    # Get pending videos from database
    try:
        pending_videos = db_manager.get_pending_videos()
        print(f"📊 Found {len(pending_videos)} pending videos in database")
    except Exception as e:
        print(f"❌ Error querying pending videos: {e}")
        return
    
    if not pending_videos:
        print("No pending videos found to process.")
        return
    
    print(f"Found {len(pending_videos)} pending videos to process:")
    for video in pending_videos:
        print(f"  - Video ID {video['id']}: {video.get('video_filename', 'N/A')}")
    
    # Process each pending video
    successful_count = 0
    failed_count = 0
    
    for video_record in pending_videos:
        print(f"\n{'='*60}")
        print(f"Processing video {successful_count + failed_count + 1}/{len(pending_videos)}: ID {video_record['id']}")
        print(f"{'='*60}")
        
        success = process_video_from_db(db_manager, video_record)
        if success:
            successful_count += 1
            print(f"✅ Successfully processed video ID: {video_record['id']}")
        else:
            failed_count += 1
            print(f"❌ Failed to process video ID: {video_record['id']}")
    
    print(f"\n{'='*60}")
    print(f"Processing complete!")
    print(f"Successful: {successful_count}")
    print(f"Failed: {failed_count}")
    print(f"Total: {len(pending_videos)}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
