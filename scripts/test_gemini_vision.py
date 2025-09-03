import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import datetime
import random
import json
import requests
from pathlib import Path
import argparse # Import argparse for command-line arguments
import time

load_dotenv() # Load environment variables from .env file

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL_NAME = os.getenv("OPENROUTER_MODEL_NAME")
USE_OPENROUTER_FALLBACK = os.getenv("USE_OPENROUTER_FALLBACK", "false").lower() == "true"
FREEIMAGE_API_KEY = os.getenv("FREEIMAGE_API_KEY")

class MockTextResponse:
    def __init__(self, text):
        self.text = text

def openrouter_generate_content(model_name, contents):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # OpenRouter expects 'model' and 'messages' in the payload
    # We need to convert the 'contents' from Gemini format to OpenRouter's 'messages' format
    messages = []
    parts_for_message = []
    for content_part in contents:
        if isinstance(content_part, types.Part): # This is for Gemini's types.Part
            if content_part.text:
                parts_for_message.append({"type": "text", "text": content_part.text})
            elif content_part.inline_data: # This case should ideally not be hit if image_url is used
                parts_for_message.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{content_part.inline_data.mime_type};base64,{content_part.inline_data.data}"}
                })
        elif isinstance(content_part, dict) and content_part.get("type") == "image_url":
            # This is for the image_url dictionary we construct in process_image_and_generate_prompts
            parts_for_message.append(content_part)
        else: # Assuming it's a string for text content
            parts_for_message.append({"type": "text", "text": content_part})

    messages.append({"role": "user", "content": parts_for_message})

    payload = {
        "model": model_name,
        "messages": messages
    }

    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    try:
        response.raise_for_status() # Raise an exception for HTTP errors
    except requests.exceptions.HTTPError as e:
        print(f"OpenRouter HTTP Error: {e}")
        print(f"OpenRouter Response Content: {response.text}")
        raise # Re-raise the exception after printing details

    openrouter_response = response.json()
    
    if openrouter_response and openrouter_response.get("choices"):
        # Assuming the first choice contains the relevant text
        generated_text = openrouter_response["choices"][0]["message"]["content"]
        return generated_text
    else:
        print("OpenRouter response did not contain expected content (choices not found).")
        return None # Explicitly return None if choices are not found

def upload_image_to_freeimagehost(image_path):
    """Uploads an image to freeimage.host and returns the URL."""
    if not FREEIMAGE_API_KEY:
        print("Error: FREEIMAGE_API_KEY environment variable not set. Cannot upload image.")
        return None

    try:
        with open(image_path, "rb") as f:
            image_data = f.read()

        # Determine mime type dynamically
        mime_type = "image/jpeg" if image_path.lower().endswith(('.jpg', '.jpeg')) else "image/png"

        files = {
            'source': (os.path.basename(image_path), image_data, mime_type),
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

def _generate_content(api_source, model_name, contents):
    if api_source == "openrouter":
        print(f"Using OpenRouter API for model: {model_name}")
        retries = 3
        delay = 5  # seconds
        for attempt in range(retries):
            try:
                result = openrouter_generate_content(model_name=OPENROUTER_MODEL_NAME, contents=contents)
                if result:
                    return result
                print(f"Attempt {attempt + 1} of {retries} failed, returned None. Retrying in {delay} seconds...")
                time.sleep(delay)
            except Exception as e:
                print(f"An exception occurred on attempt {attempt + 1}: {e}")
                if attempt + 1 == retries:
                    raise  # Re-raise the last exception
                time.sleep(delay)
        raise Exception("Failed to get a valid response from OpenRouter after several retries.")
    else: # api_source == "gemini"
        try:
            print(f"Using Gemini API for model: {model_name}")
            return client.models.generate_content(model=model_name, contents=contents)
        except Exception as e:
            if "503" in str(e) and USE_OPENROUTER_FALLBACK:
                print(f"Gemini API overloaded (503) for model {model_name}. Falling back to OpenRouter.")
                retries = 3
                delay = 5
                for attempt in range(retries):
                    try:
                        result = openrouter_generate_content(model_name=OPENROUTER_MODEL_NAME, contents=contents)
                        if result:
                            return result
                        print(f"Fallback attempt {attempt + 1} of {retries} failed, returned None. Retrying in {delay} seconds...")
                        time.sleep(delay)
                    except Exception as e_fallback:
                        print(f"An exception occurred on fallback attempt {attempt + 1}: {e_fallback}")
                        if attempt + 1 == retries:
                            raise
                        time.sleep(delay)
                raise Exception("Failed to get a valid response from OpenRouter fallback after several retries.")
            else:
                raise # Re-raise other ServerErrors or if fallback is not enabled

def find_first_image(directory):
    for filename in os.listdir(directory):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            return os.path.join(directory, filename)
    return None

def process_image_and_generate_prompts(image_directory="img/ready/", api_source="gemini"):
    image_path = find_first_image(image_directory)

    if not image_path:
        print(f"No image files found in {image_directory}")
        return None

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    mime_type = "image/jpeg" if image_path.lower().endswith(('.jpg', '.jpeg')) else "image/png"

    image_url = upload_image_to_freeimagehost(image_path)
    if not image_url:
        print("Failed to upload image to freeimage.host. Cannot proceed with image processing.")
        return None

    # Prepare contents for _generate_content based on API source
    if api_source == "openrouter":
        # For OpenRouter, use the direct image URL
        image_part_for_api = {
            "type": "image_url",
            "image_url": {"url": image_url}
        }
    else: # For Gemini, use types.Part
        image_part_for_api = types.Part.from_bytes(
            data=image_bytes,
            mime_type=mime_type
        )

    response_text = _generate_content(
        api_source=api_source,
        model_name="gemini-2.5-flash",
        contents=[
            image_part_for_api,
            "Describe this image in detail."
        ],
    )
    response = MockTextResponse(response_text) if api_source == "openrouter" else response_text

    brief_response_text = _generate_content(
        api_source=api_source,
        model_name="gemini-2.5-flash",
        contents=[
            image_part_for_api,
            "Provide a very brief, one or two word description of the main object in this image."
        ],
    )
    brief_response = MockTextResponse(brief_response_text) if api_source == "openrouter" else brief_response_text
    brief_description = brief_response.text.strip().replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_").replace("*", "_").replace("?", "_").replace("\"", "_").replace("<", "_").replace(">", "_").replace("|", "_")

    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    random_num = random.randint(1000, 9999)
    file_extension = os.path.splitext(image_path)[1]
    pic_name = f"{brief_description}_{timestamp}_{random_num}{file_extension}"
    new_image_path = os.path.join(image_directory, pic_name)

    os.rename(image_path, new_image_path)
    print(f"Image renamed to: {pic_name}")

    image_url = upload_image_to_freeimagehost(new_image_path)
    if not image_url:
        print("Failed to upload image to freeimage.host. Proceeding without image_url.")

    with open("src/image_description.txt", "w") as f:
        f.write(response.text)
    print("Description written to src/image_description.txt")

    image_prompt_response = _generate_content(
        api_source=api_source,
        model_name="gemini-2.5-flash",
        contents=[
            f"Convert the following image description into a concise prompt suitable for an image generation model: {response.text}"
        ],
    )
    image_prompt = image_prompt_response if api_source == "openrouter" else image_prompt_response.text
    with open("src/img_gen.txt", "w") as f:
        f.write(image_prompt)
    print("Image generation prompt written to src/img_gen.txt")

    video_prompt_response = _generate_content(
        api_source=api_source,
        model_name="gemini-2.5-flash",
        contents=[
            f"Convert the following image description into a concise prompt suitable for a video generation model. Focus exclusively on movement, changes, human expression, or background alterations. Absolutely avoid any static image descriptions. Keep it concise (under 100 words): {response.text}"
        ],
    )
    video_prompt = video_prompt_response if api_source == "openrouter" else video_prompt_response.text
    with open("src/video_gen.txt", "w") as f:
        f.write(video_prompt)
    print("Video generation prompt written to src/video_gen.txt")

    video_name = os.path.splitext(pic_name)[0] + ".mp4"

    return {
        "pic_name": pic_name,
        "video_name": video_name,
        "video_prompt": video_prompt,
        "image_prompt": image_prompt,
        "image_url": image_url # Add the image_url here
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process an image and generate prompts using Gemini or OpenRouter API.")
    parser.add_argument("--api-source", type=str, default="openrouter", choices=["gemini", "openrouter"],
                        help="Specify the API source to use: 'gemini' or 'openrouter'. Defaults to 'openrouter'.")
    args = parser.parse_args()

    output_data = process_image_and_generate_prompts(api_source=args.api_source)

    if output_data:
        output_dir = Path("out/prompt_json")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        json_filename = Path(output_data["pic_name"]).stem + ".json"
        json_filepath = output_dir / json_filename

        with open(json_filepath, "w") as f:
            json.dump(output_data, f, indent=4)
        print(f"Output JSON saved to {json_filepath}")
