#!/usr/bin/env python3
"""
Generate a short video using Gemini (GenAI) Python client following the
example from https://ai.google.dev/gemini-api/docs/video?example=dialogue

Usage:
  pip install google-genai
  export GEMINI_API_KEY="YOUR_API_KEY"
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
from pathlib import Path
from datetime import datetime
from google import genai
import dotenv # Import dotenv

OUT_DIR = Path("out")
OUT_DIR.mkdir(parents=True, exist_ok=True)

dotenv.load_dotenv() # Load environment variables from .env

def get_single_prompt_from_text(client, text_content, purpose):
    """
    Uses a Gemini model to extract a single, accurate prompt from multi-option text.
    """
    response = client.models.generate_content(
        model="gemini-2.5-flash", # Use the model directly here
        contents=[
            f"Given the following text, extract the single most suitable and accurate prompt for {purpose} generation. "
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

    # Read raw content of image generation prompt file
    try:
        with open("src/img_gen.txt", "r") as f:
            raw_image_text = f.read()
    except FileNotFoundError:
        print("Error: src/img_gen.txt not found. Using default raw image text.")
        raw_image_text = "A futuristic city at sunset, with flying cars and neon lights."

    # Read raw content of video generation prompt file
    try:
        with open("src/video_gen.txt", "r") as f:
            raw_video_text = f.read()
    except FileNotFoundError:
        print("Error: src/video_gen.txt not found. Using default raw video text.")
        raw_video_text = "A short video of a futuristic city at sunset, with flying cars moving through neon-lit streets."

    print("Step 0: Using Gemini to refine prompts...")
    image_prompt = get_single_prompt_from_text(client, raw_image_text, "image")
    video_prompt = get_single_prompt_from_text(client, raw_video_text, "video")

    if not image_prompt:
        print("Error: Failed to get a refined image prompt. Exiting.")
        return
    if not video_prompt:
        print("Error: Failed to get a refined video prompt. Exiting.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    concise_image_idea = get_single_prompt_from_text(
        client,
        image_prompt,
        "a 5-letter concise main idea for an image generation prompt. Only return the 5 letters, no other text."
    )
    # Ensure it's exactly 5 letters and alphanumeric
    concise_image_idea = "".join(filter(str.isalnum, concise_image_idea)).lower()[:5]
    if len(concise_image_idea) < 5:
        # Fallback if Gemini doesn't return 5 letters
        concise_image_idea = "idea_" + concise_image_idea # Add a prefix to make it unique

    OUT_FILE = OUT_DIR / f"generated_video_{concise_image_idea}_{timestamp}.mp4"

    print("Step 1: Generate an image with Imagen...")
    imagen = client.models.generate_images(
        model="imagen-4.0-generate-001",
        prompt=image_prompt,
    )

    if not getattr(imagen, "generated_images", None):
        print("Error: imagen did not return generated_images. Full response:", imagen)
        return

    print("Image generated. Step 2: Generate video with VEO 3...")
    operation = client.models.generate_videos(
        model="veo-3.0-generate-preview",
        prompt=video_prompt,
        image=imagen.generated_images[0].image,
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

if __name__ == "__main__":
    main()
