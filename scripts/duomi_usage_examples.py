#!/usr/bin/env python3
"""
Usage examples for the Duomi Image Generator

This file demonstrates how to use the DuomiImageGenerator class programmatically
"""

from duomi_image_generator import DuomiImageGenerator
import json

def example_single_image():
    """Example: Generate a single image from a prompt"""
    print("=== Example 1: Single Image Generation ===")
    
    generator = DuomiImageGenerator()
    
    prompt = "a majestic dragon flying over a medieval castle at sunset"
    result = generator.generate_image(prompt)
    
    if result["success"]:
        saved_path = generator.save_generated_image(result, "dragon_castle")
        print(f"✅ Image generated and saved to: {saved_path}")
    else:
        print(f"❌ Generation failed: {result['error']}")
    
    return result

def example_database_batch():
    """Example: Generate images from database prompts"""
    print("\n=== Example 2: Database Batch Generation ===")
    
    generator = DuomiImageGenerator()
    
    # Generate images for first 3 prompts from database
    results = generator.batch_generate_from_database(limit=3, delay=2.0)
    
    successful = sum(1 for r in results if r["success"])
    print(f"✅ Generated {successful}/{len(results)} images from database")
    
    return results

def example_json_batch():
    """Example: Generate images from JSON files"""
    print("\n=== Example 3: JSON Files Batch Generation ===")
    
    generator = DuomiImageGenerator()
    
    # Generate images from JSON files
    results = generator.batch_generate_from_json(delay=2.0)
    
    successful = sum(1 for r in results if r["success"])
    print(f"✅ Generated {successful}/{len(results)} images from JSON files")
    
    return results

def example_custom_parameters():
    """Example: Generate image with custom parameters"""
    print("\n=== Example 4: Custom Parameters ===")
    
    generator = DuomiImageGenerator()
    
    prompt = "a cyberpunk cityscape with neon lights"
    
    # Custom parameters
    custom_params = {
        "image_size": "1024x1024",
        "guidance_scale": 10.0,
        "num_inference_steps": 30,
        "seed": 42
    }
    
    result = generator.generate_image(prompt, **custom_params)
    
    if result["success"]:
        saved_path = generator.save_generated_image(result, "cyberpunk_custom")
        print(f"✅ Custom image generated and saved to: {saved_path}")
    else:
        print(f"❌ Generation failed: {result['error']}")
    
    return result

def example_check_database_prompts():
    """Example: Check what prompts are available in database"""
    print("\n=== Example 5: Check Available Database Prompts ===")
    
    generator = DuomiImageGenerator()
    
    prompts = generator.get_prompts_from_database(limit=5)
    
    print(f"Found {len(prompts)} prompts in database:")
    for i, prompt_data in enumerate(prompts, 1):
        print(f"{i}. ID: {prompt_data['id']}, Image ID: {prompt_data['image_id']}")
        print(f"   Prompt: {prompt_data['prompt'][:100]}...")
        print(f"   File: {prompt_data['original_filename']}")
        print()
    
    return prompts

def example_check_json_prompts():
    """Example: Check what prompts are available in JSON files"""
    print("\n=== Example 6: Check Available JSON Prompts ===")
    
    generator = DuomiImageGenerator()
    
    prompts = generator.get_prompts_from_json_files()
    
    print(f"Found {len(prompts)} prompts in JSON files:")
    for i, prompt_data in enumerate(prompts, 1):
        print(f"{i}. File: {prompt_data['filename']}")
        print(f"   Prompt: {prompt_data['prompt'][:100]}...")
        print()
    
    return prompts

if __name__ == "__main__":
    print("Duomi Image Generator - Usage Examples")
    print("=" * 50)
    
    # Run examples (uncomment the ones you want to test)
    
    # Check available prompts first
    example_check_database_prompts()
    example_check_json_prompts()
    
    # Generate single image
    # example_single_image()
    
    # Generate with custom parameters
    # example_custom_parameters()
    
    # Batch generation (uncomment with caution - will use API credits)
    # example_database_batch()
    # example_json_batch()
    
    print("\n✅ Examples completed!")
    print("\nTo run batch generation, uncomment the desired example functions.")
    print("Note: Batch generation will consume API credits.")
