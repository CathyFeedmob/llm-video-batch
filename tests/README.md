# OpenRouter Base Model Test Suite

This directory contains comprehensive tests for the OpenRouter base model, providing real-world testing with actual API calls (no mocking).

## Test Files

- `test_openrouter_base.py` - Main test suite with comprehensive coverage
- `test_image.png` - Test image copied from `img/ready` for image analysis tests
- `README.md` - This documentation file

## Prerequisites

### Environment Variables
Set these in your `.env` file:
```bash
# Required
OPENROUTER_API_KEY=your_openrouter_api_key
FREEIMAGE_API_KEY=your_freeimage_api_key

# Optional (for fallback testing)
GEMINI_API_KEY=your_gemini_api_key
USE_OPENROUTER_FALLBACK=true
```

### Dependencies
The test suite uses the following modules:
- `scripts.openrouter_base` - The base model being tested
- `scripts.image_uploader` - For uploading test images

## Running Tests

### Run All Tests
```bash
python3 tests/test_openrouter_base.py
```

### Run Specific Test Suites
```bash
# Text generation tests
python3 tests/test_openrouter_base.py --test text_generation

# Image analysis tests
python3 tests/test_openrouter_base.py --test image_analysis

# Specialized prompt generation tests
python3 tests/test_openrouter_base.py --test specialized_prompts

# API source selection tests
python3 tests/test_openrouter_base.py --test api_source_selection

# Error handling tests
python3 tests/test_openrouter_base.py --test error_handling

# Performance tests
python3 tests/test_openrouter_base.py --test performance
```

### Verbose Output
```bash
python3 tests/test_openrouter_base.py --verbose
```

## Test Coverage

### 1. Text Generation Tests
- Basic text generation with various prompts
- Response quality and format validation
- API source tracking and timing

### 2. Image Analysis Tests
- Image description generation
- Subject identification
- Color analysis
- Mood/atmosphere description

### 3. Specialized Prompt Tests
- Brief description generation (1-2 words)
- Image generation prompt creation
- Video generation prompt creation
- Integration with image analysis

### 4. API Source Selection Tests
- OpenRouter API usage
- Gemini API usage (if available)
- Source selection validation

### 5. Error Handling Tests
- Invalid image URL handling
- Long prompt handling
- Graceful failure validation

### 6. Performance Tests
- Response time consistency
- Performance statistics
- Rate limiting compliance

## Test Results

The test suite provides comprehensive reporting:

```
============================================================
📊 TEST REPORT
============================================================
Total Tests: 20
✅ Passed: 19
❌ Failed: 1
📈 Success Rate: 95.0%

❌ Failed Tests:
   • Long Prompt Handling: Request timeout after 60s

⏱️ Average Response Time: 2.34s
⚡ Fastest Response: 0.53s
🐌 Slowest Response: 7.46s

🎉 Test suite completed!
```

## Real API Testing

This test suite makes **real API calls** to:
- OpenRouter API for text and image analysis
- FreeImageHost API for image uploads
- Gemini API (if configured) for fallback testing

### Cost Considerations
- Each test run makes approximately 20-25 API calls
- Image analysis tests are more expensive than text generation
- Consider running specific test suites during development

### Rate Limiting
- Built-in 1-second delays between API calls
- Respects service rate limits
- Configurable retry logic

## Test Image

The test suite uses `test_image.png`, which is a copy of an image from `img/ready`. This ensures:
- Consistent test results
- Known image content for validation
- Isolated test environment

## Integration Testing

The test suite validates integration with:
- Image upload system (`scripts.image_uploader`)
- OpenRouter base model (`scripts.openrouter_base`)
- Environment variable configuration
- Error handling and fallback mechanisms

## Continuous Integration

For CI/CD pipelines:
```bash
# Run tests with exit codes
python3 tests/test_openrouter_base.py
echo "Exit code: $?"

# Run specific critical tests
python3 tests/test_openrouter_base.py --test text_generation
python3 tests/test_openrouter_base.py --test error_handling
```

## Troubleshooting

### Common Issues

1. **Missing API Keys**
   ```
   ❌ Missing required environment variables: OPENROUTER_API_KEY
   ```
   Solution: Set required environment variables in `.env`

2. **Image Upload Failures**
   ```
   ❌ Failed to upload test image: API key not set
   ```
   Solution: Set `FREEIMAGE_API_KEY` in `.env`

3. **Network Timeouts**
   ```
   ❌ Request timeout after 60s
   ```
   Solution: Check internet connection, try again later

4. **API Rate Limits**
   ```
   ❌ Rate limit exceeded
   ```
   Solution: Wait and retry, or reduce test frequency

### Debug Mode

For detailed debugging, use verbose mode:
```bash
python3 tests/test_openrouter_base.py --verbose --test text_generation
```

This will show:
- Full API responses (truncated)
- Detailed timing information
- Step-by-step execution logs

## Test Development

### Adding New Tests

1. Add test method to `OpenRouterBaseTester` class
2. Follow naming convention: `test_<category>()`
3. Use `self.record_test()` for result tracking
4. Add rate limiting with `time.sleep(1)`
5. Update test suite mapping in `run_specific_test()`

### Test Method Template

```python
def test_new_feature(self):
    """Test new feature functionality."""
    self.log("Testing new feature...")
    
    try:
        result = self.client.new_method("test input")
        
        if result.success:
            self.record_test(
                "New Feature Test",
                True,
                f"Success details: {result.content[:50]}...",
                result.response_time
            )
        else:
            self.record_test(
                "New Feature Test",
                False,
                result.error,
                result.response_time
            )
    except Exception as e:
        self.record_test("New Feature Test", False, str(e))
    
    time.sleep(1)  # Rate limiting
```

## Best Practices

1. **Always use real API calls** - No mocking for integration testing
2. **Include rate limiting** - Respect service limits
3. **Test both success and failure cases** - Comprehensive coverage
4. **Use descriptive test names** - Clear reporting
5. **Log detailed information** - Aid debugging
6. **Handle exceptions gracefully** - Robust test execution
7. **Validate response structure** - Ensure API compatibility
8. **Test with real data** - Use actual images and prompts

This test suite ensures the OpenRouter base model works correctly in real-world scenarios and provides confidence for production deployment.
