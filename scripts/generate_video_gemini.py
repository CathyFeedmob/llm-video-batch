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
from google import genai

OUT_DIR = Path("out")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "veo3_with_image_input.mp4"

def main():
    # Require the API key to be present as an env var. The official example uses
    # `client = genai.Client()` which reads credentials from the environment.
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        print("Error: set GEMINI_API_KEY or GOOGLE_API_KEY environment variable with your API key.")
        return

    # Create client using the SDK default behavior (matches the example on the docs)
    client = genai.Client()

    # Read prompt from src/video_prompt.txt
    try:
        with open("src/video_prompt.txt", "r") as f:
            prompt = f.read().strip()
    except FileNotFoundError:
        print("Error: src/video_prompt.txt not found. Using default prompt.")
        prompt = """In the center of the futuristic circus, a lone acrobat, known as the "Neon Blade," takes the stage. Her cybernetic arms gleam under the pulsing neon lights, each finger tipped with micro-lasers that carve glowing trails through the air. She leaps onto a hovering platform, suspended by anti-gravity drones, and begins her act. With a single flip, she activates her retractable leg blades, slicing through holographic rings projected mid-air. Her movements are precise and calculated, enhanced by neural implants that synchronize her performance with the rhythm of the electronic music blasting through the arena. Sparks fly as she lands on a spinning metallic wheel, balancing effortlessly while igniting a cascade of shimmering plasma from her suit. The audience gasps, their faces illuminated by the ever-changing hues of her dazzling performance."""

    print("Step 1: Generate an image with Imagen...")
    imagen = client.models.generate_images(
        model="imagen-4.0-generate-001",
        prompt=prompt,
    )

    if not getattr(imagen, "generated_images", None):
        print("Error: imagen did not return generated_images. Full response:", imagen)
        return

    print("Image generated. Step 2: Generate video with VEO 3...")
    operation = client.models.generate_videos(
        model="veo-3.0-generate-preview",
        prompt=prompt,
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
