# OpenRouter Base Model Usage Instructions

This document provides comprehensive usage instructions for the OpenRouter base model (`openrouter_base.py`) to help AI assistants and developers understand how to use this module effectively.

## Overview

The OpenRouter base model provides a unified interface for interacting with OpenRouter API and Gemini API, with automatic fallback mechanisms, retry logic, and structured response handling. It's designed to be the central hub for all LLM-based operations in the project.

## Quick Start

### Basic Import and Initialization

```python
from scripts.openrouter_base import OpenRouterClient, GenerationResult

# Initialize with default settings (uses environment variables)
client = OpenRouterClient()

# Initialize with custom settings
client = OpenRouterClient(
    openrouter_api_key="your_key_here",
    openrouter_model="google/gemini-2.5-flash",
    max_retries=5,
    retry_delay=3.0
)
```

### Environment Variables Required

```bash
# Required
OPENROUTER_API_KEY=your_openrouter_api_key

# Optional (with defaults)
OPENROUTER_MODEL_NAME=google/gemini-2.5-flash
GEMINI_API_KEY=your_gemini_api_key
USE_OPENROUTER_FALLBACK=true
```

## Core Methods

### 1. Text Generation

```python
# Simple text generation
result = client.generate_content("What is the capital of France?")

if result.success:
    print(f"Response: {result.content}")
    print(f"API used: {result.api_source}")
    print(f"Response time: {result.response_time:.2f}s")
else:
    print(f"Error: {result.error}")
```

### 2. Image Analysis

```python
# Analyze image from URL
result = client.analyze_image(
    image_url="https://example.com/image.jpg",
    prompt="Describe this image in detail"
)

# Analyze image from raw bytes (for Gemini API)
with open("image.jpg", "rb") as f:
    image_data = f.read()

result = client.analyze_image(
    image_data=image_data,
    mime_type="image/jpeg",
    prompt="What objects are in this image?",
    api_source="gemini"
)
```

### 3. Specialized Prompt Generation

```python
# Generate image generation prompt
description = "A beautiful sunset over mountains"
result = client.generate_image_prompt(description)

# Generate video generation prompt
result = client.generate_video_prompt(description)

# Get brief object description
result = client.get_brief_description(image_url="https://example.com/image.jpg")
```

## Advanced Usage Patterns

### 1. Error Handling and Retry Logic

```python
# The client automatically handles retries, but you can customize
client = OpenRouterClient(max_retries=5, retry_delay=2.0)

result = client.generate_content("Complex prompt here")

# Check result details
if result.success:
    print(f"Success after {result.response_time:.2f}s using {result.api_source}")
else:
    print(f"Failed: {result.error}")
    # The client already tried all retries and fallbacks
```

### 2. API Source Selection

```python
# Force OpenRouter usage
result = client.generate_content("Prompt", api_source="openrouter")

# Force Gemini usage
result = client.generate_content("Prompt", api_source="gemini")

# Let the client decide (default: openrouter)
result = client.generate_content("Prompt")
```

### 3. Batch Processing

```python
prompts = [
    "Describe a sunset",
    "Explain quantum physics",
    "Write a haiku about coding"
]

results = []
for prompt in prompts:
    result = client.generate_content(prompt)
    results.append(result)
    
    # Optional: Add delay between requests
    time.sleep(1)

# Process results
successful = [r for r in results if r.success]
failed = [r for r in results if not r.success]

print(f"Success rate: {len(successful)}/{len(results)}")
```

## Integration with Existing Scripts

### 1. Replacing Direct OpenRouter Calls

**Before (in existing scripts):**
```python
def openrouter_generate_content(model_name, contents):
    # Complex implementation with manual retry logic
    pass

response = openrouter_generate_content("google/gemini-2.5-flash", [prompt])
```

**After (using base model):**
```python
from scripts.openrouter_base import OpenRouterClient

client = OpenRouterClient()
result = client.generate_content(prompt)
content = result.content if result.success else None
```

### 2. Image Processing Workflows

```python
def process_image_with_base_model(image_url):
    client = OpenRouterClient()
    
    # Get detailed description
    desc_result = client.analyze_image(
        image_url=image_url,
        prompt="Describe this image in detail."
    )
    
    if not desc_result.success:
        return None
    
    # Generate brief description for filename
    brief_result = client.get_brief_description(image_url=image_url)
    
    # Generate video prompt
    video_result = client.generate_video_prompt(desc_result.content)
    
    # Generate image prompt
    image_result = client.generate_image_prompt(desc_result.content)
    
    return {
        "description": desc_result.content,
        "brief_description": brief_result.content if brief_result.success else "Unknown",
        "video_prompt": video_result.content if video_result.success else "",
        "image_prompt": image_result.content if image_result.success else ""
    }
```

### 3. Fallback Handling

```python
def robust_content_generation(prompt, image_url=None):
    client = OpenRouterClient(use_fallback=True)
    
    # Try OpenRouter first
    result = client.generate_content(
        prompt=prompt,
        image_url=image_url,
        api_source="openrouter"
    )
    
    # If OpenRouter fails and no automatic fallback occurred, try Gemini
    if not result.success and "503" not in result.error:
        print("Trying Gemini as manual fallback...")
        result = client.generate_content(
            prompt=prompt,
            api_source="gemini"
        )
    
    return result
```

## Response Structure

### GenerationResult Object

```python
@dataclass
class GenerationResult:
    success: bool                    # True if generation succeeded
    content: Optional[str] = None    # Generated content
    error: Optional[str] = None      # Error message if failed
    api_source: Optional[str] = None # "openrouter", "gemini", or "gemini_fallback"
    model_used: Optional[str] = None # Model name that was used
    response_time: Optional[float] = None # Time taken in seconds
```

### Example Response Handling

```python
result = client.generate_content("Hello world")

# Always check success first
if result.success:
    print(f"✅ Generated content: {result.content}")
    print(f"📡 API: {result.api_source}")
    print(f"🤖 Model: {result.model_used}")
    print(f"⏱️ Time: {result.response_time:.2f}s")
else:
    print(f"❌ Generation failed: {result.error}")
    print(f"📡 Attempted API: {result.api_source}")
    
    # Handle specific error types
    if "API key" in result.error:
        print("🔑 Check your API key configuration")
    elif "timeout" in result.error.lower():
        print("⏰ Request timed out, try again")
    elif "503" in result.error:
        print("🚫 Service temporarily unavailable")
```

## Common Use Cases

### 1. Image Description for Video Generation

```python
def describe_image_for_video(image_path_or_url):
    """Get image description suitable for video generation."""
    client = OpenRouterClient()
    
    # Upload image if it's a local path
    if not image_path_or_url.startswith('http'):
        # Use image upload system
        from scripts.image_uploader import FreeImageHostUploader
        uploader = FreeImageHostUploader()
        upload_result = uploader.upload_image(image_path_or_url)
        if not upload_result.success:
            return None
        image_url = upload_result.url
    else:
        image_url = image_path_or_url
    
    # Analyze image
    result = client.analyze_image(
        image_url=image_url,
        prompt="Describe this image focusing on elements that could move or change in a video."
    )
    
    return result.content if result.success else None
```

### 2. Prompt Refinement

```python
def refine_video_prompt(original_prompt):
    """Refine a video prompt using the base model."""
    client = OpenRouterClient()
    
    refinement_prompt = (
        f"Refine the following video prompt for an image-to-video model. "
        f"Focus exclusively on movement, changes, human expression, or background alterations. "
        f"Absolutely avoid any static image descriptions. "
        f"Keep it concise (under 100 words): {original_prompt}"
    )
    
    result = client.generate_content(refinement_prompt)
    return result.content if result.success else original_prompt
```

### 3. Batch Image Analysis

```python
def analyze_image_batch(image_urls, custom_prompt=None):
    """Analyze multiple images with optional custom prompt."""
    client = OpenRouterClient()
    results = []
    
    default_prompt = "Describe this image in detail."
    prompt = custom_prompt or default_prompt
    
    for i, image_url in enumerate(image_urls):
        print(f"Processing image {i+1}/{len(image_urls)}")
        
        result = client.analyze_image(
            image_url=image_url,
            prompt=prompt
        )
        
        results.append({
            'image_url': image_url,
            'success': result.success,
            'description': result.content,
            'error': result.error,
            'response_time': result.response_time
        })
        
        # Be respectful to the API
        time.sleep(1)
    
    return results
```

## Error Handling Best Practices

### 1. Graceful Degradation

```python
def generate_with_fallback(prompt, image_url=None):
    """Generate content with multiple fallback strategies."""
    client = OpenRouterClient()
    
    # Try primary method
    result = client.generate_content(prompt, image_url=image_url)
    
    if result.success:
        return result.content
    
    # Fallback 1: Try without image if image was provided
    if image_url:
        print("Retrying without image...")
        result = client.generate_content(prompt)
        if result.success:
            return result.content
    
    # Fallback 2: Try simpler prompt
    simple_prompt = "Please provide a brief response to this request."
    result = client.generate_content(simple_prompt)
    
    if result.success:
        return f"Simplified response: {result.content}"
    
    # Final fallback
    return "Unable to generate content at this time."
```

### 2. Logging and Monitoring

```python
import logging

def monitored_generation(prompt, **kwargs):
    """Generate content with comprehensive logging."""
    client = OpenRouterClient()
    
    logging.info(f"Starting generation with prompt: {prompt[:50]}...")
    
    result = client.generate_content(prompt, **kwargs)
    
    if result.success:
        logging.info(f"Generation successful via {result.api_source} in {result.response_time:.2f}s")
        logging.debug(f"Generated content length: {len(result.content)} characters")
    else:
        logging.error(f"Generation failed: {result.error}")
        logging.debug(f"Failed after {result.response_time:.2f}s using {result.api_source}")
    
    return result
```

## Performance Considerations

### 1. Connection Reuse

```python
# Good: Reuse client instance
client = OpenRouterClient()
for prompt in prompts:
    result = client.generate_content(prompt)

# Avoid: Creating new client for each request
for prompt in prompts:
    client = OpenRouterClient()  # Inefficient
    result = client.generate_content(prompt)
```

### 2. Timeout Configuration

```python
# For time-sensitive applications
client = OpenRouterClient(max_retries=1, retry_delay=1.0)

# For robust applications
client = OpenRouterClient(max_retries=5, retry_delay=3.0)
```

### 3. Rate Limiting

```python
import time

def rate_limited_generation(prompts, delay=1.0):
    """Generate content with rate limiting."""
    client = OpenRouterClient()
    results = []
    
    for i, prompt in enumerate(prompts):
        result = client.generate_content(prompt)
        results.append(result)
        
        # Rate limiting
        if i < len(prompts) - 1:  # Don't delay after last request
            time.sleep(delay)
    
    return results
```

## Testing and Debugging

### 1. Test Connection

```python
def test_openrouter_connection():
    """Test if OpenRouter base model is working."""
    try:
        client = OpenRouterClient()
        result = client.generate_content("Hello, world!")
        
        if result.success:
            print("✅ OpenRouter base model is working")
            print(f"Response: {result.content}")
            return True
        else:
            print(f"❌ Connection test failed: {result.error}")
            return False
    except Exception as e:
        print(f"❌ Exception during test: {e}")
        return False
```

### 2. Debug Mode

```python
def debug_generation(prompt, **kwargs):
    """Generate content with debug information."""
    client = OpenRouterClient()
    
    print(f"🔍 Debug: Generating content for prompt: {prompt}")
    print(f"🔍 Debug: Additional args: {kwargs}")
    
    start_time = time.time()
    result = client.generate_content(prompt, **kwargs)
    total_time = time.time() - start_time
    
    print(f"🔍 Debug: Total time (including retries): {total_time:.2f}s")
    print(f"🔍 Debug: Result success: {result.success}")
    print(f"🔍 Debug: API source: {result.api_source}")
    print(f"🔍 Debug: Model used: {result.model_used}")
    
    if not result.success:
        print(f"🔍 Debug: Error details: {result.error}")
    
    return result
```

## Migration Guide

### From Direct OpenRouter Calls

**Old Pattern:**
```python
def old_openrouter_call():
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"model": "google/gemini-2.5-flash", "messages": [...]}
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", ...)
    # Manual error handling, retry logic, etc.
```

**New Pattern:**
```python
def new_openrouter_call():
    client = OpenRouterClient()
    result = client.generate_content("Your prompt here")
    return result.content if result.success else None
```

### From test_gemini_vision.py Functions

**Old Pattern:**
```python
from scripts.test_gemini_vision import openrouter_generate_content, _generate_content

response = openrouter_generate_content("google/gemini-2.5-flash", [prompt])
```

**New Pattern:**
```python
from scripts.openrouter_base import OpenRouterClient

client = OpenRouterClient()
result = client.generate_content(prompt)
response = result.content if result.success else None
```

## Troubleshooting

### Common Issues

1. **"OpenRouter API key is required"**
   - Set `OPENROUTER_API_KEY` in your `.env` file
   - Or pass `openrouter_api_key` parameter to constructor

2. **"Failed after N attempts"**
   - Check internet connection
   - Verify API key is valid
   - Check OpenRouter service status

3. **"Gemini client not available for fallback"**
   - Set `GEMINI_API_KEY` in your `.env` file
   - Or disable fallback with `use_fallback=False`

4. **Slow response times**
   - Reduce `max_retries` for faster failure
   - Use simpler prompts
   - Check network connectivity

### Debug Checklist

- [ ] Environment variables are set correctly
- [ ] API keys are valid and have sufficient credits
- [ ] Network connectivity is working
- [ ] Image URLs are accessible (for image analysis)
- [ ] Prompts are not too long or complex
- [ ] Rate limits are not being exceeded

## Best Practices Summary

1. **Always check `result.success`** before using `result.content`
2. **Reuse client instances** for multiple requests
3. **Handle errors gracefully** with fallback strategies
4. **Use appropriate timeouts** based on your use case
5. **Log important operations** for debugging
6. **Respect rate limits** with delays between requests
7. **Test thoroughly** in development before production use
8. **Monitor API usage** and costs
9. **Keep prompts concise** for better performance
10. **Use structured error handling** for different error types

This base model provides a robust foundation for all LLM operations in the project. Use it consistently across all scripts to maintain code quality and reliability.
