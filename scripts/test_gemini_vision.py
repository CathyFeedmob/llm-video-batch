import os
from google import genai
from google.genai import types

client = genai.Client()

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

print("API call successful. Writing description to file...")
with open("image_description.txt", "w") as f:
    f.write(response.text)
print("Description written to image_description.txt")
