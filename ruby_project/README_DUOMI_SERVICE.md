# Duomi Video Service

A Ruby service class for generating videos using the Duomi API with support for video status checking and automatic downloading.

## Installation

Make sure you have the required gems:

```ruby
require "uri"
require "json"
require "net/http"
require "fileutils"
```

For environment variable support, install the dotenv gem:

```bash
gem install dotenv
```

## Environment Setup

1. Create a `.env` file in the project root:

```bash
DUOMI_API_KEY=your_api_key_here
```

2. The `.env` file is automatically ignored by git to keep your API key secure.

## Usage

### Basic Setup

```ruby
require_relative 'lib/duomi_video_service'
require 'dotenv/load' rescue LoadError

# Initialize the service with API key from environment
api_key = ENV['DUOMI_API_KEY']
duomi_service = DuomiVideoService.new(api_key)
```

### Simple Video Generation

```ruby
image_urls = [
  "https://example.com/image1.jpg",
  "https://example.com/image2.jpg"
]

prompt = "Your video description prompt"

result = duomi_service.generate_video(
  image_urls: image_urls,
  prompt: prompt
)

puts "Status: #{result[:status]}"
puts "Success: #{result[:success]}"
puts "Response: #{result[:body]}"
```

### Advanced Usage with Custom Options

```ruby
result = duomi_service.generate_video(
  image_urls: image_urls,
  prompt: prompt,
  model_name: "kling-v1-6",           # Model to use
  negative_prompt: "blurry, low quality", # What to avoid
  cfg_scale: 0.7,                     # Guidance scale (0.1-2.0)
  mode: "std",                        # Generation mode
  duration: 10,                       # Video duration in seconds
  callback_url: "https://your-webhook.com" # Optional webhook
)
```

## Parameters

### Required Parameters
- `image_urls`: Array of image URLs to use for video generation
- `prompt`: Text description of the desired video

### Optional Parameters
- `model_name`: Model to use (default: "kling-v1-6")
- `negative_prompt`: What to avoid in the generation (default: "")
- `cfg_scale`: Guidance scale from 0.1 to 2.0 (default: 0.5)
- `mode`: Generation mode (default: "std")
- `duration`: Video duration in seconds (default: 5)
- `callback_url`: Webhook URL for completion notification

## Video Status Checking and Downloading

### Check Video Status

```ruby
task_id = "your_task_id_from_generation"
status_result = duomi_service.check_video_status(task_id)

if status_result[:success]
  data = status_result[:body]["data"]
  puts "Task Status: #{data['task_status']}"  # submitted, processing, succeed, failed
end
```

### Download Completed Video

```ruby
# Download video once it's completed
download_result = duomi_service.download_video(task_id, "video_downloaded")

if download_result[:success]
  puts "Videos downloaded to: #{download_result[:download_dir]}"
  download_result[:downloaded_files].each do |file|
    puts "Downloaded: #{file[:filepath]}"
  end
end
```

### Wait for Completion and Auto-Download

```ruby
# Automatically wait for completion and download
download_result = duomi_service.wait_and_download(
  task_id,
  "video_downloaded",  # Download directory
  300,                 # Max wait time in seconds (5 minutes)
  15                   # Check interval in seconds
)
```

## Response Format

The service returns a hash with:
- `status`: HTTP status code
- `success`: Boolean indicating if the request was successful
- `body`: Response body (parsed JSON on success, raw text on error)

## Error Handling

The service includes built-in error handling for:
- Network errors
- JSON parsing errors
- HTTP errors
- File download errors

All errors are captured and returned in the response format.

## File Structure

```
ruby_project/
├── .env                              # API key (not committed to git)
├── .gitignore                        # Git ignore file
├── README_DUOMI_SERVICE.md          # This documentation
├── lib/
│   └── duomi_video_service.rb       # Main service class
├── examples/
│   ├── duomi_video_example.rb       # Basic usage example
│   └── video_download_example.rb    # Download functionality example
└── video_downloaded/                # Downloaded videos directory
```

## Examples

- `examples/duomi_video_example.rb` - Basic video generation
- `examples/video_download_example.rb` - Complete workflow with downloading
