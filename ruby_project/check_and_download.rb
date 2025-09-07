require_relative 'lib/duomi_video_service'

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

# Task ID from previous generation
task_id = "08921088-1078-c398-0eb1-085a4e27aeed"

puts "=== Checking Status for Task: #{task_id} ==="

# Check current status
status_result = duomi_service.check_video_status(task_id)

if status_result[:success]
  data = status_result[:body]["data"]
  puts "Task Status: #{data['task_status']}"
  puts "Created At: #{data['created_at']}"
  puts "Updated At: #{data['updated_at']}"
  
  if data['task_status'] == 'succeed'
    puts "\n=== Video is ready! Downloading... ==="
    download_result = duomi_service.download_video(task_id, "video_downloaded")
    
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
    puts "\n=== Video not ready yet. Current status: #{data['task_status']} ==="
    puts "You can use wait_and_download to automatically wait for completion:"
    puts "duomi_service.wait_and_download('#{task_id}', 'video_downloaded')"
  end
else
  puts "Failed to check status: #{status_result[:body]}"
end
