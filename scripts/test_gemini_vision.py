from google import genai
from google.genai import types

client = genai.Client()

# Load the image file as bytes
with open("img/0198fe94-91eb-70f8-bd2b-bd77aa35078f.jpeg", "rb") as f:
    image_bytes = f.read()

# Package the image for the API
image_part = types.Part.from_bytes(
    data=image_bytes,
    mime_type="image/jpeg"
)

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
