#!/usr/bin/env ruby

# ============================================================================
# VideoGenerator - Duomi Video Generation Interface
# ============================================================================
#
# This class provides a simple interface to generate videos using the Duomi API
# with custom prompts and image URLs. It handles the complete workflow from
# video generation to download.
#
# REQUIREMENTS:
# - DUOMI_API_KEY must be set in environment variables or .env file
# - Internet connection for API calls and video downloads
#
# USAGE EXAMPLES:
#
# 1. Basic Usage (run this file directly):
#    ruby video_generator.rb
#    (Uses the default image_url and prompt defined at the bottom)
#
# 2. Use as a class in other scripts:
#    require_relative 'video_generator'
#    
#    generator = VideoGenerator.new
#    result = generator.generate_and_download_video(
#      image_url: "https://example.com/image.jpg",
#      prompt: "A beautiful sunset over mountains"
#    )
#
# 3. Quick generation method:
#    generator = VideoGenerator.new
#    result = generator.quick_generate(
#      "https://example.com/image.jpg", 
#      "A cat dancing in the rain"
#    )
#
# 4. Advanced usage with custom options:
#    generator = VideoGenerator.new
#    result = generator.generate_and_download_video(
#      image_url: "https://example.com/image.jpg",
#      prompt: "Epic battle scene",
#      model_name: "kling-v1-6",
#      duration: 10,
#      cfg_scale: 0.7,
#      download_dir: "my_videos",
#      max_wait_time: 900  # 15 minutes
#    )
#
# AVAILABLE OPTIONS:
# - model_name: "kling-v2-1" (default), "kling-v1-6"
# - duration: 5 (default), 10 seconds
# - cfg_scale: 0.5 (default), range 0.1-1.0
# - mode: "std" (default)
# - download_dir: "video_downloaded" (default)
# - max_wait_time: 600 seconds (default)
# - check_interval: 15 seconds (default)
#
# RETURN VALUE:
# Returns a hash with:
# - success: true/false
# - task_id: Duomi task ID
# - downloaded_files: Array of downloaded file info (if successful)
# - download_dir: Directory where files were saved
# - error: Error message (if failed)
#
# EXAMPLE RETURN VALUE:
# {
#   success: true,
#   task_id: "12345",
#   downloaded_files: [
#     {
#       id: "video_123",
#       duration: 5,
#       filepath: "video_downloaded/12345_video_123_5s.mp4",
#       url: "https://..."
#     }
#   ],
#   download_dir: "video_downloaded"
# }
#
# ============================================================================

require_relative 'lib/duomi_video_service'

# Load environment variables
require 'dotenv/load' rescue LoadError

class VideoGenerator
  def initialize
    @api_key = ENV['DUOMI_API_KEY']
    if @api_key.nil? || @api_key.empty?
      raise "Error: DUOMI_API_KEY not found in environment variables"
    end
    
    @duomi_service = DuomiVideoService.new(@api_key)
  end

  def generate_and_download_video(image_url:, prompt:, **options)
    # Default options
    default_options = {
      model_name: "kling-v2-1",
      duration: 5,
      cfg_scale: 0.5,
      mode: "std",
      download_dir: "video_downloaded",
      max_wait_time: 600,  # 10 minutes
      check_interval: 15   # Check every 15 seconds
    }
    
    # Merge user options with defaults
    opts = default_options.merge(options)
    
    puts "=== Duomi Video Generation ==="
    puts "Image URL: #{image_url}"
    puts "Prompt: #{prompt}"
    puts "Model: #{opts[:model_name]}"
    puts "Duration: #{opts[:duration]}s"
    puts ""

    # Generate video
    puts "=== Starting Video Generation ==="
    result = @duomi_service.generate_video(
      image_urls: [image_url],
      prompt: prompt,
      model_name: opts[:model_name],
      duration: opts[:duration],
      cfg_scale: opts[:cfg_scale],
      mode: opts[:mode]
    )

    puts "Status: #{result[:status]}"
    puts "Success: #{result[:success]}"

    if result[:success]
      task_id = result[:body]["data"]["task_id"]
      puts "Video generation started successfully!"
      puts "Task ID: #{task_id}"
      
      # Wait for completion and download automatically
      puts "\n=== Waiting for Completion and Downloading ==="
      puts "This may take several minutes..."
      
      download_result = @duomi_service.wait_and_download(
        task_id, 
        opts[:download_dir],
        opts[:max_wait_time],
        opts[:check_interval]
      )
      
      if download_result[:success]
        puts "\n🎉 SUCCESS! Videos downloaded successfully!"
        puts "Download directory: #{download_result[:download_dir]}"
        puts "Downloaded files:"
        download_result[:downloaded_files].each do |file|
          puts "  📹 Video ID: #{file[:id]}"
          puts "     Duration: #{file[:duration]}s"
          puts "     File: #{file[:filepath]}"
          puts "     Size: #{File.size(file[:filepath]) / 1024 / 1024}MB" if File.exist?(file[:filepath])
          puts ""
        end
        
        return {
          success: true,
          task_id: task_id,
          downloaded_files: download_result[:downloaded_files],
          download_dir: download_result[:download_dir]
        }
      else
        puts "\n❌ Download failed: #{download_result[:message]}"
        return {
          success: false,
          task_id: task_id,
          error: download_result[:message],
          task_status: download_result[:task_status]
        }
      end
      
    else
      puts "\n❌ Failed to generate video:"
      puts "Response: #{result[:body]}"
      return {
        success: false,
        error: result[:body]
      }
    end
  end

  # Convenience method for quick generation
  def quick_generate(image_url, prompt)
    generate_and_download_video(image_url: image_url, prompt: prompt)
  end
end

# If this file is run directly, use the provided parameters
if __FILE__ == $0
  # User provided parameters
  image_url = "https://iili.io/KnmAW4S.jpg"
  prompt = "紫发少女凝视前方，神情忧郁，嘴角微动。她轻抚手腕上的黑色手环，头顶恶魔角上的红光闪烁。背景中，海面波光粼粼，小船随波起伏，远方建筑逐渐模糊，天空云朵飘动。整体动画风格。"

  begin
    generator = VideoGenerator.new
    result = generator.generate_and_download_video(
      image_url: image_url,
      prompt: prompt
    )
    
    if result[:success]
      puts "✅ Video generation completed successfully!"
    else
      puts "❌ Video generation failed!"
    end
  rescue => e
    puts "Error: #{e.message}"
    exit 1
  end
end
