# LLM Video Batch Generation

This project provides scripts to generate videos using different Large Language Models (LLMs) and their respective APIs. Currently, it supports video generation via Kling AI and is being set up to use Gemini for refining video prompts.

## Table of Contents
- [Kling AI Video Generation](#kling-ai-video-generation)
  - [Prerequisites](#prerequisites)
  - [JSON File Preparation](#json-file-preparation)
  - [Execution](#execution)
- [Gemini Video Prompt Refinement](#gemini-video-prompt-refinement)
  - [Prerequisites](#prerequisites-1)
  - [JSON File Preparation](#json-file-preparation-1)
  - [Execution](#execution-1)

---

## Kling AI Video Generation

This section details how to use the `scripts/generate_video_kling.py` script to generate videos using the Kling AI API.

### Prerequisites
- Python 3.x
- `python-dotenv`
- `requests`
- `PyJWT`

You can install the required Python packages using pip:
```bash
pip install python-dotenv requests PyJWT
```

You will also need to set up your Kling AI API keys as environment variables. Create a `.env` file in the project root with the following:
```
KLING_ACCESS_KEY="YOUR_KLING_ACCESS_KEY"
KLING_SECRET_KEY="YOUR_KLING_SECRET_KEY"
```
Replace `"YOUR_KLING_ACCESS_KEY"` and `"YOUR_KLING_SECRET_KEY"` with your actual API keys from Kling AI.

### JSON File Preparation
The script requires a JSON file that specifies the `video_prompt` and `video_name`.

Example `video_prompt.json`:
```json
{
  "video_prompt": "A highly stylized and vibrant digital illustration of a young woman's face in a tight close-up. Fantastical, ethereal, and psychedelic, her face and long, flowing hair are a luminous canvas of vibrant neon and pastel blues, purples, yellows, oranges, pinks, and teals, adorned with iridescent flecks, glitter, and cosmic dust creating a glowing texture. She has large bright blue eyes with exaggerated dark lashes and full brows, and striking, glossy fiery red lips slightly parted. The background is a dark, dreamlike starry night sky with glittering celestial elements. An otherworldly beauty infused with cosmic energy.",
  "video_name": "MyAwesomeVideo"
}
```
- `video_prompt`: The textual prompt for video generation.
- `video_name`: The desired name for the output video file (without extension).

### Execution
The `generate_video_kling.py` script takes two command-line arguments: the path to the local image file and the path to the JSON file. The image file will be read, base64 encoded, and sent to the API.

```bash
python3 scripts/generate_video_kling.py <path_to_image_file> <path_to_json_file>
```
Example:
```bash
python3 scripts/generate_video_kling.py img/ready/my_image.jpeg src/video_prompt.json
```
The generated video (MP4 format) will be saved in the `out/` directory. The processed JSON file will be moved to `out/prompt_json/used/`.

---

## Gemini Video Prompt Refinement

This section details how to use the `scripts/generate_video_gemini.py` script to refine video prompts using Gemini 2.5 Flash and generate videos with VEO 3.0.

### Prerequisites
- Python 3.x
- `google-genai`
- `Pillow` (PIL)
- `python-dotenv`

You can install the required Python packages using pip:
```bash
pip install google-genai Pillow python-dotenv
```

You will also need to set up your Gemini API key as an environment variable. Create a `.env` file in the project root with the following:
```
GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
```
Replace `"YOUR_GEMINI_API_KEY"` with your actual API key from Google AI Studio. Alternatively, you can use `GOOGLE_API_KEY`.

### JSON File Preparation
The script requires a JSON file that specifies the `video_prompt`, `image_prompt`, and `video_name`.

Example `gemini_prompt.json`:
```json
{
  "video_prompt": "A highly stylized and vibrant digital illustration of a young woman's face in a tight close-up. Fantastical, ethereal, and psychedelic, her face and long, flowing hair are a luminous canvas of vibrant neon and pastel blues, purples, yellows, oranges, pinks, and teals, adorned with iridescent flecks, glitter, and cosmic dust creating a glowing texture. She has large bright blue eyes with exaggerated dark lashes and full brows, and striking, glossy fiery red lips slightly parted. The background is a dark, dreamlike starry night sky with glittering celestial elements. An otherworldly beauty infused with cosmic energy.",
  "image_prompt": "A vibrant digital illustration of a fantastical creature.",
  "video_name": "GeminiGeneratedVideo"
}
```
- `video_prompt`: The initial textual prompt for video generation. This prompt will be refined by Gemini 2.5 Flash before being used for video generation. The refinement process will specifically avoid describing the image and focus on action and narrative.
- `image_prompt`: The textual prompt for image generation (used by Imagen).
- `video_name`: The desired name for the output video file (without extension) and the generated image file.

### Execution
The `generate_video_gemini.py` script takes one command-line argument: the path to the JSON file.

```bash
python3 scripts/generate_video_gemini.py <path_to_json_file>
```
Example:
```bash
python3 scripts/generate_video_gemini.py src/gemini_prompt.json
```
The script will:
1. Refine the `video_prompt` using Gemini 2.5 Flash, focusing on action and narrative without describing the image.
2. Generate an image based on `image_prompt` using Imagen.
3. Generate a video using VEO 3.0, combining the refined video prompt and the generated image.

The generated video (MP4 format) will be saved in the `out/` directory. The generated image will be saved in the `out/img/` directory. The processed JSON file will be moved to `out/prompt_json/used/`.
