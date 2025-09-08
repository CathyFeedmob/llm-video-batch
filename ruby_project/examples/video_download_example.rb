require_relative '../lib/duomi_video_service'

# Load environment variables
require 'dotenv/load' rescue LoadError

# Initialize the service with API key from environment
api_key = ENV['DUOMI_API_KEY']
if api_key.nil? || api_key.empty?
  puts "Error: DUOMI_API_KEY not found in environment variables"
  puts "Please create a .env file with: DUOMI_API_KEY=your_api_key_here"
  exit 1
end

duomi_service = DuomiVideoService.new(api_key)

# Example 1: Generate video and get task ID
puts "=== Generating Video ==="
image_urls = [
  "https://aisp.ttaibot.com/uploads/xz_aivideo/1735500936.jpg",
  "https://db.xiaohuhd.com/1.jpeg"
]

prompt = "一只卡通小猫，穿着棕色皮夹克，戴着墨镜，在舞台上向镜头微笑"

result = duomi_service.generate_video(
  image_urls: image_urls,
  prompt: prompt,
  duration: 5
)

if result[:success]
  task_id = result[:body]["data"]["task_id"]
  puts "Video generation started successfully!"
  puts "Task ID: #{task_id}"
  
  # Example 2: Check video status manually
  puts "\n=== Checking Video Status ==="
  status_result = duomi_service.check_video_status(task_id)
  if status_result[:success]
    data = status_result[:body]["data"]
    puts "Task Status: #{data['task_status']}"
    puts "Created At: #{data['created_at']}"
    puts "Updated At: #{data['updated_at']}"
  end
  
  # Example 3: Wait for completion and download automatically
  puts "\n=== Waiting for Completion and Downloading ==="
  download_result = duomi_service.wait_and_download(
    task_id, 
    "video_downloaded",  # Download directory
    300,                 # Max wait time (5 minutes)
    15                   # Check every 15 seconds
  )
  
  if download_result[:success]
    puts "Videos downloaded successfully!"
    puts "Download directory: #{download_result[:download_dir]}"
    puts "Downloaded files:"
    download_result[:downloaded_files].each do |file|
      puts "  - ID: #{file[:id]}"
      puts "    Duration: #{file[:duration]}s"
      puts "    File: #{file[:filepath]}"
      puts "    Original URL: #{file[:url]}"
      puts ""
    end
  else
    puts "Download failed: #{download_result[:message]}"
  end
  
else
  puts "Failed to generate video: #{result[:body]}"
end

# Example 4: Download existing completed video (if you have a task ID)
puts "\n=== Download Existing Video Example ==="
puts "# To download an existing completed video, use:"
puts "# download_result = duomi_service.download_video('your_task_id_here', 'video_downloaded')"
