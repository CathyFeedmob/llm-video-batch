import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import datetime
import random
import json
from pathlib import Path

load_dotenv() # Load environment variables from .env file

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def find_first_image(directory):
    for filename in os.listdir(directory):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            return os.path.join(directory, filename)
    return None

def process_image_and_generate_prompts(image_directory="img/ready/"):
    image_path = find_first_image(image_directory)

    if not image_path:
        print(f"No image files found in {image_directory}")
        return None

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    mime_type = "image/jpeg" if image_path.lower().endswith(('.jpg', '.jpeg')) else "image/png"

    image_part = types.Part.from_bytes(
        data=image_bytes,
        mime_type=mime_type
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            image_part,
            "Describe this image in detail."
        ],
    )

    brief_response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            image_part,
            "Provide a very brief, one or two word description of the main object in this image."
        ],
    )
    brief_description = brief_response.text.strip().replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_").replace("*", "_").replace("?", "_").replace("\"", "_").replace("<", "_").replace(">", "_").replace("|", "_")

    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    random_num = random.randint(1000, 9999)
    file_extension = os.path.splitext(image_path)[1]
    pic_name = f"{brief_description}_{timestamp}_{random_num}{file_extension}"
    new_image_path = os.path.join(image_directory, pic_name)

    os.rename(image_path, new_image_path)
    print(f"Image renamed to: {pic_name}")

    with open("src/image_description.txt", "w") as f:
        f.write(response.text)
    print("Description written to src/image_description.txt")

    image_prompt_response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            f"Convert the following image description into a concise prompt suitable for an image generation model: {response.text}"
        ],
    )
    image_prompt = image_prompt_response.text
    with open("src/img_gen.txt", "w") as f:
        f.write(image_prompt)
    print("Image generation prompt written to src/img_gen.txt")

    video_prompt_response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            f"Convert the following image description into a concise prompt suitable for a video generation model. Focus exclusively on movement, changes, human expression, or background alterations. Absolutely avoid any static image descriptions. Keep it concise (under 100 words): {response.text}"
        ],
    )
    video_prompt = video_prompt_response.text
    with open("src/video_gen.txt", "w") as f:
        f.write(video_prompt)
    print("Video generation prompt written to src/video_gen.txt")

    video_name = os.path.splitext(pic_name)[0] + ".mp4"

    return {
        "pic_name": pic_name,
        "video_name": video_name,
        "video_prompt": video_prompt,
        "image_prompt": image_prompt
    }

if __name__ == "__main__":
    output_data = process_image_and_generate_prompts()

    if output_data:
        output_dir = Path("out/prompt_json")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        json_filename = Path(output_data["pic_name"]).stem + ".json"
        json_filepath = output_dir / json_filename

        with open(json_filepath, "w") as f:
            json.dump(output_data, f, indent=4)
        print(f"Output JSON saved to {json_filepath}")
