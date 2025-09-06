#!/usr/bin/env python3
"""
OpenRouter Base Model

This module provides a base class for OpenRouter API interactions, including
support for image analysis, text generation, and fallback mechanisms.

Usage:
    from openrouter_base import OpenRouterClient
    
    client = OpenRouterClient()
    result = client.generate_content("Describe this image", image_url="https://example.com/image.jpg")
    print(result)
"""

import os
import requests
import time
from typing import List, Union, Optional, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

@dataclass
class GenerationResult:
    """Result of a content generation operation."""
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    api_source: Optional[str] = None
    model_used: Optional[str] = None
    response_time: Optional[float] = None

class MockTextResponse:
    """Mock response object to maintain compatibility with Gemini API format."""
    def __init__(self, text: str):
        self.text = text

class OpenRouterClient:
    """
    Base client for OpenRouter API interactions with Gemini fallback support.
    
    Provides methods for text generation, image analysis, and prompt processing
    with automatic retry logic and fallback mechanisms.
    """
    
    def __init__(self, 
                 openrouter_api_key: Optional[str] = None,
                 openrouter_model: Optional[str] = None,
                 gemini_api_key: Optional[str] = None,
                 use_fallback: bool = None,
                 max_retries: int = 3,
                 retry_delay: float = 5.0):
        """
        Initialize OpenRouter client.
        
        Args:
            openrouter_api_key: OpenRouter API key (defaults to env var)
            openrouter_model: Model name to use (defaults to env var)
            gemini_api_key: Gemini API key for fallback (defaults to env var)
            use_fallback: Enable Gemini fallback on 503 errors (defaults to env var)
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.openrouter_api_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        self.openrouter_model = openrouter_model or os.getenv("OPENROUTER_MODEL_NAME", "google/gemini-2.5-flash")
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.use_fallback = use_fallback if use_fallback is not None else os.getenv("USE_OPENROUTER_FALLBACK", "false").lower() == "true"
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Initialize Gemini client if available
        self.gemini_client = None
        if self.gemini_api_key:
            try:
                self.gemini_client = genai.Client(api_key=self.gemini_api_key)
            except Exception as e:
                print(f"Warning: Failed to initialize Gemini client: {e}")
        
        # Validate required credentials
        if not self.openrouter_api_key:
            raise ValueError("OpenRouter API key is required. Set OPENROUTER_API_KEY environment variable.")
    
    def _prepare_messages(self, contents: List[Union[str, Dict, types.Part]]) -> List[Dict]:
        """
        Convert various content formats to OpenRouter message format.
        
        Args:
            contents: List of content parts (text, image URLs, Gemini types.Part)
            
        Returns:
            List of message parts in OpenRouter format
        """
        parts_for_message = []
        
        for content_part in contents:
            if isinstance(content_part, types.Part):
                # Handle Gemini types.Part
                if content_part.text:
                    parts_for_message.append({"type": "text", "text": content_part.text})
                elif content_part.inline_data:
                    parts_for_message.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{content_part.inline_data.mime_type};base64,{content_part.inline_data.data}"}
                    })
            elif isinstance(content_part, dict) and content_part.get("type") == "image_url":
                # Already in correct format
                parts_for_message.append(content_part)
            elif isinstance(content_part, str):
                # Plain text content
                parts_for_message.append({"type": "text", "text": content_part})
            else:
                # Try to convert to string
                parts_for_message.append({"type": "text", "text": str(content_part)})
        
        return parts_for_message
    
    def _call_openrouter_api(self, messages: List[Dict], model: Optional[str] = None) -> Optional[str]:
        """
        Make a direct call to OpenRouter API.
        
        Args:
            messages: Messages in OpenRouter format
            model: Model name to use (defaults to instance default)
            
        Returns:
            Generated text content or None if failed
        """
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model or self.openrouter_model,
            "messages": [{"role": "user", "content": messages}]
        }
        
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions", 
                headers=headers, 
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            openrouter_response = response.json()
            
            if openrouter_response and openrouter_response.get("choices"):
                return openrouter_response["choices"][0]["message"]["content"]
            else:
                print("OpenRouter response did not contain expected content (choices not found).")
                return None
                
        except requests.exceptions.HTTPError as e:
            print(f"OpenRouter HTTP Error: {e}")
            print(f"OpenRouter Response Content: {response.text}")
            raise
        except requests.exceptions.RequestException as e:
            print(f"OpenRouter Request Error: {e}")
            raise
        except Exception as e:
            print(f"OpenRouter API Error: {e}")
            raise
    
    def _call_gemini_api(self, contents: List[Union[str, Dict, types.Part]], model: str = "gemini-2.5-flash") -> Optional[str]:
        """
        Make a fallback call to Gemini API.
        
        Args:
            contents: Content in Gemini format
            model: Gemini model name
            
        Returns:
            Generated text content or None if failed
        """
        if not self.gemini_client:
            raise Exception("Gemini client not available for fallback")
        
        try:
            response = self.gemini_client.models.generate_content(model=model, contents=contents)
            return response.text if hasattr(response, 'text') else str(response)
        except Exception as e:
            print(f"Gemini API Error: {e}")
            raise
    
    def generate_content(self, 
                        prompt: str, 
                        image_url: Optional[str] = None,
                        image_data: Optional[bytes] = None,
                        mime_type: Optional[str] = None,
                        model: Optional[str] = None,
                        api_source: str = "openrouter") -> GenerationResult:
        """
        Generate content using OpenRouter or Gemini API.
        
        Args:
            prompt: Text prompt for generation
            image_url: URL of image to analyze (for OpenRouter)
            image_data: Raw image bytes (for Gemini)
            mime_type: MIME type of image data
            model: Model name to use
            api_source: "openrouter" or "gemini"
            
        Returns:
            GenerationResult with success status and content
        """
        start_time = time.time()
        
        try:
            # Prepare content based on API source
            if api_source == "openrouter":
                contents = [prompt]
                if image_url:
                    contents.insert(0, {
                        "type": "image_url",
                        "image_url": {"url": image_url}
                    })
                
                # Try OpenRouter with retries
                last_error = None
                for attempt in range(self.max_retries):
                    try:
                        print(f"Using OpenRouter API for model: {model or self.openrouter_model} (attempt {attempt + 1})")
                        messages = self._prepare_messages(contents)
                        result = self._call_openrouter_api(messages, model)
                        
                        if result:
                            return GenerationResult(
                                success=True,
                                content=result,
                                api_source="openrouter",
                                model_used=model or self.openrouter_model,
                                response_time=time.time() - start_time
                            )
                        
                        print(f"Attempt {attempt + 1} of {self.max_retries} failed, returned None. Retrying in {self.retry_delay} seconds...")
                        if attempt < self.max_retries - 1:
                            time.sleep(self.retry_delay)
                            
                    except Exception as e:
                        last_error = str(e)
                        print(f"An exception occurred on attempt {attempt + 1}: {e}")
                        if attempt < self.max_retries - 1:
                            time.sleep(self.retry_delay)
                
                # If all OpenRouter attempts failed, try Gemini fallback
                if self.use_fallback and self.gemini_client:
                    print("OpenRouter failed. Attempting Gemini fallback...")
                    try:
                        gemini_contents = [prompt]
                        if image_data and mime_type:
                            gemini_contents.insert(0, types.Part.from_bytes(data=image_data, mime_type=mime_type))
                        
                        result = self._call_gemini_api(gemini_contents, "gemini-2.5-flash")
                        if result:
                            return GenerationResult(
                                success=True,
                                content=result,
                                api_source="gemini_fallback",
                                model_used="gemini-2.5-flash",
                                response_time=time.time() - start_time
                            )
                    except Exception as fallback_error:
                        print(f"Gemini fallback also failed: {fallback_error}")
                
                return GenerationResult(
                    success=False,
                    error=f"Failed after {self.max_retries} attempts. Last error: {last_error}",
                    api_source="openrouter",
                    response_time=time.time() - start_time
                )
                
            else:  # api_source == "gemini"
                if not self.gemini_client:
                    return GenerationResult(
                        success=False,
                        error="Gemini client not available",
                        api_source="gemini"
                    )
                
                try:
                    print(f"Using Gemini API for model: {model or 'gemini-2.5-flash'}")
                    contents = [prompt]
                    if image_data and mime_type:
                        contents.insert(0, types.Part.from_bytes(data=image_data, mime_type=mime_type))
                    
                    result = self._call_gemini_api(contents, model or "gemini-2.5-flash")
                    
                    return GenerationResult(
                        success=True,
                        content=result,
                        api_source="gemini",
                        model_used=model or "gemini-2.5-flash",
                        response_time=time.time() - start_time
                    )
                    
                except Exception as e:
                    # Check for 503 error and try OpenRouter fallback
                    if "503" in str(e) and self.use_fallback:
                        print(f"Gemini API overloaded (503). Falling back to OpenRouter.")
                        return self.generate_content(
                            prompt=prompt,
                            image_url=image_url,
                            model=model,
                            api_source="openrouter"
                        )
                    else:
                        return GenerationResult(
                            success=False,
                            error=str(e),
                            api_source="gemini",
                            response_time=time.time() - start_time
                        )
                        
        except Exception as e:
            return GenerationResult(
                success=False,
                error=str(e),
                api_source=api_source,
                response_time=time.time() - start_time
            )
    
    def analyze_image(self, 
                     image_url: Optional[str] = None,
                     image_data: Optional[bytes] = None,
                     mime_type: Optional[str] = None,
                     prompt: str = "Describe this image in detail.",
                     api_source: str = "openrouter") -> GenerationResult:
        """
        Analyze an image with a custom prompt.
        
        Args:
            image_url: URL of image to analyze
            image_data: Raw image bytes
            mime_type: MIME type of image data
            prompt: Analysis prompt
            api_source: "openrouter" or "gemini"
            
        Returns:
            GenerationResult with image analysis
        """
        return self.generate_content(
            prompt=prompt,
            image_url=image_url,
            image_data=image_data,
            mime_type=mime_type,
            api_source=api_source
        )
    
    def generate_image_prompt(self, description: str, api_source: str = "openrouter") -> GenerationResult:
        """
        Convert image description to image generation prompt.
        
        Args:
            description: Image description text
            api_source: "openrouter" or "gemini"
            
        Returns:
            GenerationResult with image generation prompt
        """
        prompt = f"Convert the following image description into a concise prompt suitable for an image generation model: {description}"
        return self.generate_content(prompt=prompt, api_source=api_source)
    
    def generate_video_prompt(self, description: str, api_source: str = "openrouter") -> GenerationResult:
        """
        Convert image description to video generation prompt.
        
        Args:
            description: Image description text
            api_source: "openrouter" or "gemini"
            
        Returns:
            GenerationResult with video generation prompt
        """
        prompt = (f"Convert the following image description into a concise prompt suitable for a video generation model. "
                 f"Focus exclusively on movement, changes, human expression, or background alterations. "
                 f"Absolutely avoid any static image descriptions. Keep it concise (under 100 words): {description}")
        return self.generate_content(prompt=prompt, api_source=api_source)
    
    def get_brief_description(self, 
                            image_url: Optional[str] = None,
                            image_data: Optional[bytes] = None,
                            mime_type: Optional[str] = None,
                            api_source: str = "openrouter") -> GenerationResult:
        """
        Get a brief 1-2 word description of the main object in an image.
        
        Args:
            image_url: URL of image to analyze
            image_data: Raw image bytes
            mime_type: MIME type of image data
            api_source: "openrouter" or "gemini"
            
        Returns:
            GenerationResult with brief description
        """
        prompt = "Provide a very brief, one or two word description of the main object in this image."
        return self.analyze_image(
            image_url=image_url,
            image_data=image_data,
            mime_type=mime_type,
            prompt=prompt,
            api_source=api_source
        )

# Factory function for easy instantiation
def create_openrouter_client(**kwargs) -> OpenRouterClient:
    """
    Factory function to create an OpenRouter client instance.
    
    Args:
        **kwargs: Arguments passed to OpenRouterClient constructor
        
    Returns:
        OpenRouterClient instance
    """
    return OpenRouterClient(**kwargs)

# Backward compatibility functions for existing code
def openrouter_generate_content(model_name: str, contents: List[Union[str, Dict, types.Part]]) -> Optional[str]:
    """
    Legacy function for backward compatibility.
    
    Args:
        model_name: Model name to use
        contents: Content to generate from
        
    Returns:
        Generated text or None
    """
    client = OpenRouterClient(openrouter_model=model_name)
    result = client.generate_content(
        prompt=contents[-1] if isinstance(contents[-1], str) else "Analyze this content",
        image_url=contents[0].get("image_url", {}).get("url") if isinstance(contents[0], dict) else None,
        api_source="openrouter"
    )
    return result.content if result.success else None

if __name__ == "__main__":
    # Simple test
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 openrouter_base.py <prompt> [image_url]")
        sys.exit(1)
    
    prompt = sys.argv[1]
    image_url = sys.argv[2] if len(sys.argv) > 2 else None
    
    client = OpenRouterClient()
    result = client.generate_content(prompt=prompt, image_url=image_url)
    
    if result.success:
        print(f"✅ Success ({result.api_source}):")
        print(result.content)
        print(f"Response time: {result.response_time:.2f}s")
    else:
        print(f"❌ Failed: {result.error}")
