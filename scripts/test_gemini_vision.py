import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import datetime
import random

load_dotenv() # Load environment variables from .env file

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Function to find the first image file in a directory
def find_first_image(directory):
    for filename in os.listdir(directory):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            return os.path.join(directory, filename)
    return None

image_directory = "img/ready/"
image_path = find_first_image(image_directory)

if image_path:
    # Load the image file as bytes
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # Determine mime type based on file extension
    mime_type = "image/jpeg" if image_path.lower().endswith(('.jpg', '.jpeg')) else "image/png"

    # Package the image for the API
    image_part = types.Part.from_bytes(
        data=image_bytes,
        mime_type=mime_type
    )
else:
    print(f"No image files found in {image_directory}")
    exit()

# Send the image and prompt to Gemini for description
response = client.models.generate_content(
    model="gemini-2.5-flash",  # Or another Gemini vision-capable model
    contents=[
        image_part,
        "Describe this image in detail."
    ],
)

# Get a brief description for renaming
brief_response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        image_part,
        "Provide a very brief, one or two word description of the main object in this image."
    ],
)
brief_description = brief_response.text.strip().replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_").replace("*", "_").replace("?", "_").replace("\"", "_").replace("<", "_").replace(">", "_").replace("|", "_")

# Generate a timestamp and random number for the new filename
timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
random_num = random.randint(1000, 9999)
file_extension = os.path.splitext(image_path)[1]
new_filename = f"{brief_description}_{timestamp}_{random_num}{file_extension}"
new_image_path = os.path.join(image_directory, new_filename)

# Rename the image file
os.rename(image_path, new_image_path)
print(f"Image renamed to: {new_filename}")

print("API call successful. Writing description to file...")
with open("src/image_description.txt", "w") as f:
    f.write(response.text)
print("Description written to src/image_description.txt")

# Generate image generation prompt
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

# Generate video generation prompt
video_prompt_response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        f"Convert the following image description into a concise prompt suitable for a video generation model: {response.text}"
    ],
)
video_prompt = video_prompt_response.text
with open("src/video_gen.txt", "w") as f:
    f.write(video_prompt)
print("Video generation prompt written to src/video_gen.txt")
