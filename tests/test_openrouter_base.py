#!/usr/bin/env python3
"""
Comprehensive Test Suite for OpenRouter Base Model

This test suite provides real-world testing of the OpenRouter base model
using actual API keys and test images. No mocking - real API calls.

Usage:
  python3 tests/test_openrouter_base.py
  python3 tests/test_openrouter_base.py --test text_generation
  python3 tests/test_openrouter_base.py --test image_analysis
  python3 tests/test_openrouter_base.py --verbose
"""

import sys
import os
import time
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.openrouter_base import OpenRouterClient, GenerationResult
from scripts.image_uploader import FreeImageHostUploader

class OpenRouterBaseTester:
    """Comprehensive tester for OpenRouter base model functionality."""
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.test_results = []
        self.test_image_path = Path(__file__).parent / "test_image.png"
        self.test_image_url = None
        
        # Initialize client
        try:
            self.client = OpenRouterClient()
            self.log("✅ OpenRouter client initialized successfully")
        except Exception as e:
            self.log(f"❌ Failed to initialize OpenRouter client: {e}")
            sys.exit(1)
    
    def log(self, message):
        """Log message with timestamp."""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        if self.verbose:
            print()
    
    def record_test(self, test_name, success, details=None, response_time=None):
        """Record test result."""
        self.test_results.append({
            'test_name': test_name,
            'success': success,
            'details': details,
            'response_time': response_time
        })
        
        status = "✅ PASS" if success else "❌ FAIL"
        time_info = f" ({response_time:.2f}s)" if response_time else ""
        self.log(f"{status}: {test_name}{time_info}")
        
        if details and (self.verbose or not success):
            self.log(f"   Details: {details}")
    
    def setup_test_image(self):
        """Upload test image and get URL for testing."""
        if not self.test_image_path.exists():
            self.log(f"❌ Test image not found: {self.test_image_path}")
            return False
        
        try:
            uploader = FreeImageHostUploader()
            result = uploader.upload_image(str(self.test_image_path))
            
            if result.success:
                self.test_image_url = result.url
                self.log(f"✅ Test image uploaded: {self.test_image_url}")
                return True
            else:
                self.log(f"❌ Failed to upload test image: {result.error}")
                return False
        except Exception as e:
            self.log(f"❌ Exception during image upload: {e}")
            return False
    
    def test_text_generation(self):
        """Test basic text generation functionality."""
        test_prompts = [
            "What is the capital of France?",
            "Explain quantum physics in one sentence.",
            "Write a haiku about programming.",
            "List three benefits of renewable energy."
        ]
        
        for i, prompt in enumerate(test_prompts, 1):
            self.log(f"Testing text generation {i}/{len(test_prompts)}: {prompt[:30]}...")
            
            try:
                result = self.client.generate_content(prompt)
                
                if result.success:
                    self.record_test(
                        f"Text Generation {i}",
                        True,
                        f"Generated {len(result.content)} characters via {result.api_source}",
                        result.response_time
                    )
                    
                    if self.verbose:
                        self.log(f"   Response: {result.content[:100]}...")
                else:
                    self.record_test(
                        f"Text Generation {i}",
                        False,
                        result.error,
                        result.response_time
                    )
            except Exception as e:
                self.record_test(f"Text Generation {i}", False, str(e))
            
            # Rate limiting
            time.sleep(1)
    
    def test_image_analysis(self):
        """Test image analysis functionality."""
        if not self.test_image_url:
            self.log("⚠️ Skipping image analysis tests - no test image URL")
            return
        
        test_prompts = [
            "Describe this image in detail.",
            "What is the main subject of this image?",
            "What colors are prominent in this image?",
            "Describe the mood or atmosphere of this image."
        ]
        
        for i, prompt in enumerate(test_prompts, 1):
            self.log(f"Testing image analysis {i}/{len(test_prompts)}: {prompt[:30]}...")
            
            try:
                result = self.client.analyze_image(
                    image_url=self.test_image_url,
                    prompt=prompt
                )
                
                if result.success:
                    self.record_test(
                        f"Image Analysis {i}",
                        True,
                        f"Generated {len(result.content)} characters via {result.api_source}",
                        result.response_time
                    )
                    
                    if self.verbose:
                        self.log(f"   Response: {result.content[:100]}...")
                else:
                    self.record_test(
                        f"Image Analysis {i}",
                        False,
                        result.error,
                        result.response_time
                    )
            except Exception as e:
                self.record_test(f"Image Analysis {i}", False, str(e))
            
            # Rate limiting
            time.sleep(1)
    
    def test_specialized_prompts(self):
        """Test specialized prompt generation methods."""
        if not self.test_image_url:
            self.log("⚠️ Skipping specialized prompt tests - no test image URL")
            return
        
        # Test brief description
        self.log("Testing brief description generation...")
        try:
            result = self.client.get_brief_description(image_url=self.test_image_url)
            
            if result.success:
                self.record_test(
                    "Brief Description",
                    True,
                    f"Generated: '{result.content}' via {result.api_source}",
                    result.response_time
                )
            else:
                self.record_test("Brief Description", False, result.error, result.response_time)
        except Exception as e:
            self.record_test("Brief Description", False, str(e))
        
        time.sleep(1)
        
        # Get a description first for prompt generation tests
        self.log("Getting image description for prompt generation tests...")
        try:
            desc_result = self.client.analyze_image(
                image_url=self.test_image_url,
                prompt="Describe this image in detail."
            )
            
            if desc_result.success:
                description = desc_result.content
                
                # Test image prompt generation
                self.log("Testing image prompt generation...")
                try:
                    result = self.client.generate_image_prompt(description)
                    
                    if result.success:
                        self.record_test(
                            "Image Prompt Generation",
                            True,
                            f"Generated {len(result.content)} characters via {result.api_source}",
                            result.response_time
                        )
                        
                        if self.verbose:
                            self.log(f"   Image Prompt: {result.content[:100]}...")
                    else:
                        self.record_test("Image Prompt Generation", False, result.error, result.response_time)
                except Exception as e:
                    self.record_test("Image Prompt Generation", False, str(e))
                
                time.sleep(1)
                
                # Test video prompt generation
                self.log("Testing video prompt generation...")
                try:
                    result = self.client.generate_video_prompt(description)
                    
                    if result.success:
                        self.record_test(
                            "Video Prompt Generation",
                            True,
                            f"Generated {len(result.content)} characters via {result.api_source}",
                            result.response_time
                        )
                        
                        if self.verbose:
                            self.log(f"   Video Prompt: {result.content[:100]}...")
                    else:
                        self.record_test("Video Prompt Generation", False, result.error, result.response_time)
                except Exception as e:
                    self.record_test("Video Prompt Generation", False, str(e))
            else:
                self.log(f"⚠️ Could not get image description for prompt tests: {desc_result.error}")
        except Exception as e:
            self.log(f"⚠️ Exception getting image description: {e}")
    
    def test_api_source_selection(self):
        """Test API source selection functionality."""
        test_prompt = "What is 2 + 2?"
        
        # Test OpenRouter
        self.log("Testing OpenRouter API source selection...")
        try:
            result = self.client.generate_content(test_prompt, api_source="openrouter")
            
            if result.success:
                self.record_test(
                    "OpenRouter API Source",
                    True,
                    f"Used {result.api_source} with model {result.model_used}",
                    result.response_time
                )
            else:
                self.record_test("OpenRouter API Source", False, result.error, result.response_time)
        except Exception as e:
            self.record_test("OpenRouter API Source", False, str(e))
        
        time.sleep(1)
        
        # Test Gemini (if available)
        if self.client.gemini_client:
            self.log("Testing Gemini API source selection...")
            try:
                result = self.client.generate_content(test_prompt, api_source="gemini")
                
                if result.success:
                    self.record_test(
                        "Gemini API Source",
                        True,
                        f"Used {result.api_source} with model {result.model_used}",
                        result.response_time
                    )
                else:
                    self.record_test("Gemini API Source", False, result.error, result.response_time)
            except Exception as e:
                self.record_test("Gemini API Source", False, str(e))
        else:
            self.log("⚠️ Skipping Gemini API test - client not available")
    
    def test_error_handling(self):
        """Test error handling and edge cases."""
        # Test with invalid image URL
        self.log("Testing error handling with invalid image URL...")
        try:
            result = self.client.analyze_image(
                image_url="https://invalid-url-that-does-not-exist.com/image.jpg",
                prompt="Describe this image."
            )
            
            # This should fail gracefully
            if not result.success:
                self.record_test(
                    "Invalid Image URL Handling",
                    True,
                    f"Correctly failed with: {result.error[:50]}...",
                    result.response_time
                )
            else:
                self.record_test(
                    "Invalid Image URL Handling",
                    False,
                    "Should have failed but succeeded",
                    result.response_time
                )
        except Exception as e:
            self.record_test("Invalid Image URL Handling", False, f"Unexpected exception: {e}")
        
        time.sleep(1)
        
        # Test with very long prompt
        self.log("Testing with very long prompt...")
        long_prompt = "Explain quantum physics " * 100  # Very long prompt
        try:
            result = self.client.generate_content(long_prompt)
            
            if result.success:
                self.record_test(
                    "Long Prompt Handling",
                    True,
                    f"Handled long prompt successfully via {result.api_source}",
                    result.response_time
                )
            else:
                self.record_test(
                    "Long Prompt Handling",
                    True,  # Failing gracefully is also success
                    f"Gracefully failed: {result.error[:50]}...",
                    result.response_time
                )
        except Exception as e:
            self.record_test("Long Prompt Handling", False, f"Unexpected exception: {e}")
    
    def test_performance(self):
        """Test performance characteristics."""
        # Test response times
        self.log("Testing response time consistency...")
        response_times = []
        
        for i in range(3):
            try:
                start_time = time.time()
                result = self.client.generate_content("What is the capital of Japan?")
                end_time = time.time()
                
                if result.success:
                    response_times.append(end_time - start_time)
                    self.log(f"   Response {i+1}: {end_time - start_time:.2f}s")
                else:
                    self.log(f"   Response {i+1}: Failed - {result.error}")
                
                time.sleep(1)
            except Exception as e:
                self.log(f"   Response {i+1}: Exception - {e}")
        
        if response_times:
            avg_time = sum(response_times) / len(response_times)
            max_time = max(response_times)
            min_time = min(response_times)
            
            self.record_test(
                "Performance Consistency",
                True,
                f"Avg: {avg_time:.2f}s, Min: {min_time:.2f}s, Max: {max_time:.2f}s",
                avg_time
            )
        else:
            self.record_test("Performance Consistency", False, "No successful responses")
    
    def run_all_tests(self):
        """Run all test suites."""
        self.log("🚀 Starting OpenRouter Base Model Test Suite")
        self.log("=" * 60)
        
        # Setup
        self.log("📋 Setting up test environment...")
        if not self.setup_test_image():
            self.log("⚠️ Some tests will be skipped due to image upload failure")
        
        self.log("\n🧪 Running test suites...")
        
        # Run test suites
        test_suites = [
            ("Text Generation", self.test_text_generation),
            ("Image Analysis", self.test_image_analysis),
            ("Specialized Prompts", self.test_specialized_prompts),
            ("API Source Selection", self.test_api_source_selection),
            ("Error Handling", self.test_error_handling),
            ("Performance", self.test_performance)
        ]
        
        for suite_name, test_func in test_suites:
            self.log(f"\n📝 Running {suite_name} tests...")
            try:
                test_func()
            except Exception as e:
                self.log(f"❌ Test suite {suite_name} failed with exception: {e}")
        
        # Generate report
        self.generate_report()
    
    def run_specific_test(self, test_name):
        """Run a specific test suite."""
        test_map = {
            'text_generation': self.test_text_generation,
            'image_analysis': self.test_image_analysis,
            'specialized_prompts': self.test_specialized_prompts,
            'api_source_selection': self.test_api_source_selection,
            'error_handling': self.test_error_handling,
            'performance': self.test_performance
        }
        
        if test_name not in test_map:
            self.log(f"❌ Unknown test: {test_name}")
            self.log(f"Available tests: {', '.join(test_map.keys())}")
            return
        
        self.log(f"🚀 Running specific test: {test_name}")
        self.log("=" * 60)
        
        # Setup if needed
        if test_name in ['image_analysis', 'specialized_prompts']:
            self.log("📋 Setting up test environment...")
            if not self.setup_test_image():
                self.log("❌ Cannot run image tests without test image")
                return
        
        # Run test
        try:
            test_map[test_name]()
        except Exception as e:
            self.log(f"❌ Test {test_name} failed with exception: {e}")
        
        # Generate report
        self.generate_report()
    
    def generate_report(self):
        """Generate test report."""
        self.log("\n" + "=" * 60)
        self.log("📊 TEST REPORT")
        self.log("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        self.log(f"Total Tests: {total_tests}")
        self.log(f"✅ Passed: {passed_tests}")
        self.log(f"❌ Failed: {failed_tests}")
        self.log(f"📈 Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            self.log("\n❌ Failed Tests:")
            for result in self.test_results:
                if not result['success']:
                    self.log(f"   • {result['test_name']}: {result['details']}")
        
        # Response time statistics
        response_times = [r['response_time'] for r in self.test_results if r['response_time']]
        if response_times:
            avg_time = sum(response_times) / len(response_times)
            self.log(f"\n⏱️ Average Response Time: {avg_time:.2f}s")
            self.log(f"⚡ Fastest Response: {min(response_times):.2f}s")
            self.log(f"🐌 Slowest Response: {max(response_times):.2f}s")
        
        self.log("\n🎉 Test suite completed!")
        
        # Exit with appropriate code
        sys.exit(0 if failed_tests == 0 else 1)

def main():
    parser = argparse.ArgumentParser(
        description="Test suite for OpenRouter base model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 tests/test_openrouter_base.py                    # Run all tests
  python3 tests/test_openrouter_base.py --verbose          # Run with verbose output
  python3 tests/test_openrouter_base.py --test text_generation  # Run specific test
  python3 tests/test_openrouter_base.py --test image_analysis   # Run image tests
        """
    )
    
    parser.add_argument(
        '--test',
        type=str,
        help='Run specific test suite (text_generation, image_analysis, specialized_prompts, api_source_selection, error_handling, performance)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    # Check environment
    required_env_vars = ['OPENROUTER_API_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file")
        sys.exit(1)
    
    # Create tester
    tester = OpenRouterBaseTester(verbose=args.verbose)
    
    # Run tests
    if args.test:
        tester.run_specific_test(args.test)
    else:
        tester.run_all_tests()

if __name__ == "__main__":
    main()
