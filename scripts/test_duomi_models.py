#!/usr/bin/env python3
"""
Test script to check available Duomi models and test different configurations
"""

import requests
import json

def test_duomi_models():
    """Test different models with Duomi API"""
    
    api_key = "hpZyr8TglNSwMXcwlFnqVH4IgN"
    api_url = "https://duomiapi.com/v1/images/generations"
    headers = {
        'Authorization': api_key,
        'Content-Type': 'application/json'
    }
    
    # List of models to test
    models_to_test = [
        "stabilityai/stable-diffusion-xl-base-1.0",
        "stabilityai/stable-diffusion-3-medium",
        "black-forest-labs/FLUX.1-schnell",
        "black-forest-labs/FLUX.1-dev",
        "stabilityai/stable-diffusion-3-5-large",
        "runwayml/stable-diffusion-v1-5"
    ]
    
    test_prompt = "a simple red apple on a white background"
    
    for model in models_to_test:
        print(f"\nTesting model: {model}")
        
        payload = {
            "model": model,
            "prompt": test_prompt,
            "negative_prompt": "",
            "image_size": "1024x1024",
            "batch_size": 1,
            "seed": 12345,
            "num_inference_steps": 20,
            "guidance_scale": 7.5
        }
        
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                print(f"✅ {model} - SUCCESS")
                result = response.json()
                print(f"   Response keys: {list(result.keys())}")
                break  # Stop at first successful model
            else:
                print(f"❌ {model} - FAILED: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text}")
                    
        except Exception as e:
            print(f"❌ {model} - EXCEPTION: {str(e)}")

if __name__ == "__main__":
    test_duomi_models()
