# Gemini Image Generation — Quick Syntax Cheatsheet
_Last updated: 2025-09-15 • Source: Google AI docs_

This sheet gives **copy‑paste** snippets for the **Gemini API** image generation features plus **Imagen** via the same SDK. Works great with VS Code + Cline.

---

## 0) Setup

**Env**
```bash
export GEMINI_API_KEY="YOUR_KEY"
```

**Install SDKs**
```bash
# JavaScript / Node
npm i @google/genai

# Python
pip install google-genai pillow
```

---

## 1) Models (names to paste)

- **Gemini native image (preview)**: `gemini-2.5-flash-image-preview`
- **Imagen 4 (GA)**: `imagen-4.0-generate-001`

> Rule of thumb: Start with **Gemini** for conversational edits/multi‑turn; use **Imagen** for **highest fidelity** and typography/logo work.

---

## 2) Text → Image (Gemini native)

### JavaScript (Node)
```js
import { GoogleGenAI } from "@google/genai";
import * as fs from "node:fs";

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

const prompt = "Create a picture of a nano banana dish in a fancy restaurant with a Gemini theme";

const res = await ai.models.generateContent({
  model: "gemini-2.5-flash-image-preview",
  contents: prompt,
});

for (const part of res.candidates[0].content.parts) {
  if (part.inlineData) {
    const buf = Buffer.from(part.inlineData.data, "base64");
    fs.writeFileSync("gemini-native-image.png", buf);
  }
}
```

### Python
```py
from google import genai
from PIL import Image
from io import BytesIO

client = genai.Client(api_key=None)  # reads GEMINI_API_KEY

prompt = "Create a picture of a nano banana dish in a fancy restaurant with a Gemini theme"

resp = client.models.generate_content(
    model="gemini-2.5-flash-image-preview",
    contents=[prompt],
)

for part in resp.candidates[0].content.parts:
    if getattr(part, "inline_data", None):
        Image.open(BytesIO(part.inline_data.data)).save("generated_image.png")
```

### REST (curl)
```bash
curl -s -X POST   "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image-preview:generateContent"   -H "x-goog-api-key: $GEMINI_API_KEY"   -H "Content-Type: application/json"   -d '{
    "contents": [{"parts":[{"text":"Create a picture of a nano banana dish in a fancy restaurant with a Gemini theme"}]}]
  }' | jq -r '..|.data? // empty' | head -n1 | base64 --decode > gemini-native-image.png
```

---

## 3) Image Editing (Text **+** Image → Image)

### JavaScript (Node)
```js
import { GoogleGenAI } from "@google/genai";
import * as fs from "node:fs";

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

const imageB64 = fs.readFileSync("path/to/cat_image.png").toString("base64");

const res = await ai.models.generateContent({
  model: "gemini-2.5-flash-image-preview",
  contents: [
    { text: "Make the cat eat a nano-banana under the Gemini constellation" },
    { inlineData: { mimeType: "image/png", data: imageB64 } },
  ],
});

for (const part of res.candidates[0].content.parts) {
  if (part.inlineData) {
    fs.writeFileSync("gemini-edited-image.png", Buffer.from(part.inlineData.data, "base64"));
  }
}
```

### Python
```py
from google import genai
from PIL import Image
from io import BytesIO

client = genai.Client()

prompt = "Make the cat eat a nano-banana under the Gemini constellation"
image = Image.open("path/to/cat_image.png")

resp = client.models.generate_content(
    model="gemini-2.5-flash-image-preview",
    contents=[prompt, image],
)

for part in resp.candidates[0].content.parts:
    if getattr(part, "inline_data", None):
        Image.open(BytesIO(part.inline_data.data)).save("gemini-edited-image.png")
```

### REST (curl)
```bash
IMG_BASE64=$(base64 -w 0 path/to/cat_image.jpg)
curl -s -X POST   "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image-preview:generateContent"   -H "x-goog-api-key: $GEMINI_API_KEY"   -H "Content-Type: application/json"   -d "{
    "contents": [{
      "parts": [
        {"text": "Make the cat eat a nano-banana under the Gemini constellation"},
        {"inlineData": {"mimeType": "image/jpeg", "data": "$IMG_BASE64"}}
      ]
    }]
  }" | jq -r '..|.data? // empty' | head -n1 | base64 --decode > gemini-edited-image.png
```

> Tip: You can pass **multiple images** by adding more `inlineData` (or `Image` objects in Python) to `contents`.

---

## 4) Text → Image with **Imagen 4**

### JavaScript (Node)
```js
import { GoogleGenAI } from "@google/genai";
import * as fs from "node:fs";

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

const res = await ai.models.generateImages({
  model: "imagen-4.0-generate-001",
  prompt: "Robot holding a red skateboard",
  config: { numberOfImages: 4 } // 1..4
});

let i = 1;
for (const g of res.generatedImages) {
  const buf = Buffer.from(g.image.imageBytes, "base64");
  fs.writeFileSync(`imagen-${i++}.png`, buf);
}
```

### Python
```py
from google import genai
client = genai.Client()

resp = client.models.generate_images(
    model="imagen-4.0-generate-001",
    prompt="Robot holding a red skateboard",
    config={"number_of_images": 4}  # 1..4
)
for idx, g in enumerate(resp.generated_images, start=1):
    g.image.save(f"imagen-{idx}.png")  # bytes are handled by SDK helpers
```

### REST (curl)
```bash
curl -s -X POST   "https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict"   -H "x-goog-api-key: $GEMINI_API_KEY"   -H "Content-Type: application/json"   -d '{
    "instances": [{"prompt": "Robot holding a red skateboard"}],
    "parameters": {"sampleCount": 4}
  }' | jq -r '..|.imageBytes? // empty' | nl -ba | while read n b; do echo "$b" | base64 --decode > "imagen-$n.png"; done
```

**Imagen params (selected):**
- `numberOfImages` (1–4, default 4)
- `aspectRatio`: `"1:1"`, `"3:4"`, `"4:3"`, `"9:16"`, `"16:9"`
- `sampleImageSize`: `"1K"` or `"2K"` (Std/Ultra)
- `personGeneration`: `"dont_allow" | "allow_adult" | "allow_all"` (see regional restrictions)

---

## 5) Response Shapes (quick reference)

- **Gemini native**: `candidates[0].content.parts[]` where each part is either `{text}` or `{inlineData: { mimeType, data (base64) }}`.
- **Imagen**: `generatedImages[]` where each item has `image.imageBytes` (base64 string).

---

## 6) Practical Tips

- Use **descriptive paragraphs**, not keyword bags.
- For text in images (logos/posters), Imagen tends to spell more reliably.
- Keep input images ≤ a few MB each; Gemini native works best with **≤3 input images**.
- Every output includes a **SynthID** watermark.
- Store your API key in env or a secret manager; never hardcode.

---

## 7) Common Snags

- Wrong field casing (`inlineData` vs `inline_data`) when switching JS ↔ Python.
- Missing `mimeType` on `inlineData` for uploads.
- Trying to request >4 images in Imagen.
- Regional limits on `personGeneration` (EU/UK/CH/MENA).
