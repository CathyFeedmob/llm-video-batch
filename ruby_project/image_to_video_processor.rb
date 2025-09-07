#!/usr/bin/env ruby
# frozen_string_literal: true

require 'csv'
require 'json'
require 'fileutils'
require 'dotenv/load'
require_relative 'lib/openrouter_base'
require_relative 'lib/duomi_video_service'

##
# Image to Video Processor
#
# This script processes a CSV file of image URLs, generates refined Chinese video prompts
# using OpenRouter, and then creates videos using the Duomi video service.
#
class ImageToVideoProcessor
  attr_reader :openrouter_client, :duomi_service, :results_log, :basic_log

  def initialize
    # Initialize OpenRouter client
    @openrouter_client = OpenRouterClient.new
    
    # Initialize Duomi video service
    duomi_api_key = ENV['DUOMI_API_KEY']
    raise ArgumentError, 'DUOMI_API_KEY is required. Set it in your .env file.' unless duomi_api_key
    
    @duomi_service = DuomiVideoService.new(duomi_api_key)
    
    # Initialize results log
    @results_log = []
    @basic_log = []
    
    # Create necessary directories
    FileUtils.mkdir_p('logs')
    FileUtils.mkdir_p('video_downloaded')
  end

  ##
  # Process all images from CSV file
  #
  # @param csv_file_path [String] Path to CSV file containing image URLs
  # @param output_log_file [String] Path to output log file
  # @param basic_log_file [String] Path to basic log file
  #
  def process_images_from_csv(csv_file_path = 'data/image_list.csv', output_log_file = nil, basic_log_file = nil)
    unless File.exist?(csv_file_path)
      puts "❌ CSV file not found: #{csv_file_path}"
      return false
    end

    # Generate output log filenames if not provided
    timestamp = Time.now.strftime('%Y%m%d_%H%M%S')
    output_log_file ||= "logs/video_processing_detailed_#{timestamp}.json"
    basic_log_file ||= "logs/video_processing_basic_#{timestamp}.csv"

    puts "🚀 Starting image to video processing..."
    puts "📁 Reading images from: #{csv_file_path}"
    puts "📝 Detailed results will be logged to: #{output_log_file}"
    puts "📊 Basic results will be logged to: #{basic_log_file}"
    puts "=" * 60

    # Initialize basic log CSV
    initialize_basic_log(basic_log_file)

    # Read CSV file
    images = []
    CSV.foreach(csv_file_path, headers: true) do |row|
      images << {
        id: row['id'].to_i,
        image_url: row['image_url']
      }
    end

    puts "📊 Found #{images.length} images to process"
    puts

    # Process each image
    images.each_with_index do |image_data, index|
      puts "🖼️  Processing image #{index + 1}/#{images.length} (ID: #{image_data[:id]})"
      puts "🔗 URL: #{image_data[:image_url]}"
      
      result = process_single_image(image_data[:image_url], image_data[:id])
      @results_log << result
      
      # Add to basic log
      add_to_basic_log(result)
      
      # Save intermediate results
      save_results_log(output_log_file)
      save_basic_log(basic_log_file)
      
      puts "✅ Completed image #{index + 1}/#{images.length}"
      puts "-" * 40
      
      # Add a small delay to avoid overwhelming the APIs
      sleep(2)
    end

    puts "🎉 All images processed!"
    puts "📄 Detailed results saved to: #{output_log_file}"
    puts "📊 Basic results saved to: #{basic_log_file}"
    
    # Print summary
    print_processing_summary
    
    true
  end

  ##
  # Process a single image URL
  #
  # @param image_url [String] URL of the image to process
  # @param image_id [Integer] ID of the image
  # @return [Hash] Processing result
  #
  def process_single_image(image_url, image_id)
    start_time = Time.now
    
    result = {
      image_id: image_id,
      image_url: image_url,
      timestamp: start_time.iso8601,
      prompt_generation: {},
      video_generation: {},
      total_processing_time: 0,
      success: false
    }

    begin
      # Step 1: Generate refined video prompt using OpenRouter
      puts "  🤖 Generating Chinese video prompt..."
      prompt_result = @openrouter_client.generate_refined_video_prompt(image_url)
      
      result[:prompt_generation] = prompt_result
      
      if prompt_result[:success]
        puts "  ✅ Prompt generated successfully"
        puts "  🇨🇳 Chinese prompt: #{prompt_result[:refined_video_prompt_cn]}"
        
        # Step 2: Generate video using Duomi service
        puts "  🎬 Generating video..."
        video_result = generate_video_with_prompt(
          image_url, 
          prompt_result[:refined_video_prompt_cn],
          image_id
        )
        
        result[:video_generation] = video_result
        result[:success] = video_result[:success]
        
        if video_result[:success]
          puts "  ✅ Video generated and downloaded successfully"
          puts "  📁 Video files: #{video_result[:downloaded_files]&.map { |f| f[:filepath] }&.join(', ')}"
        else
          puts "  ❌ Video generation failed: #{video_result[:error]}"
        end
      else
        puts "  ❌ Prompt generation failed: #{prompt_result[:error]}"
        result[:video_generation] = { success: false, error: "Prompt generation failed" }
      end

    rescue => e
      puts "  ❌ Unexpected error: #{e.message}"
      result[:video_generation] = { success: false, error: e.message }
    end

    result[:total_processing_time] = Time.now - start_time
    result
  end

  ##
  # Generate video with the given prompt
  #
  # @param image_url [String] URL of the image
  # @param chinese_prompt [String] Chinese video generation prompt
  # @param image_id [Integer] ID of the image
  # @return [Hash] Video generation result
  #
  def generate_video_with_prompt(image_url, chinese_prompt, image_id)
    begin
      # Generate video
      generation_result = @duomi_service.generate_video(
        image_urls: [image_url],
        prompt: chinese_prompt,
        duration: 5,
        mode: "std"
      )

      unless generation_result[:success]
        return {
          success: false,
          error: "Video generation API failed: #{generation_result[:body]}",
          api_response: generation_result
        }
      end

      # Extract task ID
      task_id = generation_result.dig(:body, "data", "task_id")
      unless task_id
        return {
          success: false,
          error: "No task ID returned from video generation API",
          api_response: generation_result
        }
      end

      puts "  ⏳ Video generation started. Task ID: #{task_id}"
      puts "  ⏳ Waiting for video completion..."

      # Wait for completion and download with enhanced logging
      download_result = wait_and_download_with_logging(
        task_id,
        "video_downloaded",
        300, # max wait time: 5 minutes
        15   # check interval: 15 seconds
      )

      result = {
        success: download_result[:success],
        task_id: task_id,
        downloaded_files: download_result[:downloaded_files],
        download_dir: download_result[:download_dir],
        waiting_time: download_result[:waiting_time],
        generation_response: generation_result,
        download_response: download_result
      }
      
      result[:error] = download_result[:message] unless download_result[:success]
      result

    rescue => e
      {
        success: false,
        error: "Exception during video generation: #{e.message}",
        exception: e.class.name
      }
    end
  end

  ##
  # Enhanced wait and download with better logging
  #
  # @param task_id [String] Task ID from video generation
  # @param download_dir [String] Directory to download videos
  # @param max_wait_time [Integer] Maximum wait time in seconds
  # @param check_interval [Integer] Check interval in seconds
  # @return [Hash] Download result with timing information
  #
  def wait_and_download_with_logging(task_id, download_dir, max_wait_time, check_interval)
    start_time = Time.now
    
    loop do
      elapsed_time = Time.now - start_time
      puts "  ⏰ Checking video status for task: #{task_id} (elapsed: #{elapsed_time.round(1)}s)"
      
      status_result = @duomi_service.check_video_status(task_id)
      
      if status_result[:success]
        data = status_result[:body]["data"]
        task_status = data["task_status"]
        
        puts "  📊 Task status: #{task_status} (elapsed: #{elapsed_time.round(1)}s)"
        
        case task_status
        when "succeed"
          puts "  🎉 Video generation completed! (total wait time: #{elapsed_time.round(1)}s)"
          puts "  📥 Downloading..."
          download_result = @duomi_service.download_video(task_id, download_dir)
          download_result[:waiting_time] = elapsed_time.round(1)
          return download_result
        when "failed"
          return {
            success: false,
            message: "Video generation failed",
            task_status: task_status,
            waiting_time: elapsed_time.round(1)
          }
        when "submitted", "processing"
          if elapsed_time > max_wait_time
            return {
              success: false,
              message: "Timeout waiting for video completion",
              elapsed_time: elapsed_time.round(1),
              waiting_time: elapsed_time.round(1)
            }
          end
          
          puts "  ⏳ Video still processing... waiting #{check_interval} seconds (total elapsed: #{elapsed_time.round(1)}s)"
          sleep(check_interval)
        else
          puts "  ❓ Unknown status: #{task_status} (elapsed: #{elapsed_time.round(1)}s)"
          sleep(check_interval)
        end
      else
        return {
          success: false,
          message: "Failed to check video status",
          error: status_result[:body],
          waiting_time: elapsed_time.round(1)
        }
      end
    end
  end

  ##
  # Initialize basic log CSV file
  #
  # @param basic_log_file [String] Path to basic log file
  #
  def initialize_basic_log(basic_log_file)
    CSV.open(basic_log_file, 'w') do |csv|
      csv << ['image_id', 'image_url', 'timestamp', 'prompt_success', 'video_success', 'overall_success', 'chinese_prompt', 'task_id', 'waiting_time_seconds', 'video_files', 'error_message']
    end
  end

  ##
  # Add result to basic log
  #
  # @param result [Hash] Processing result
  #
  def add_to_basic_log(result)
    @basic_log << {
      image_id: result[:image_id],
      image_url: result[:image_url],
      timestamp: result[:timestamp],
      prompt_success: result[:prompt_generation][:success] || false,
      video_success: result[:video_generation][:success] || false,
      overall_success: result[:success],
      chinese_prompt: result[:prompt_generation][:refined_video_prompt_cn] || '',
      task_id: result[:video_generation][:task_id] || '',
      waiting_time_seconds: result[:video_generation][:waiting_time] || 0,
      video_files: result[:video_generation][:downloaded_files]&.map { |f| f[:filepath] }&.join(';') || '',
      error_message: result[:video_generation][:error] || result[:prompt_generation][:error] || ''
    }
  end

  ##
  # Save basic log to CSV file
  #
  # @param basic_log_file [String] Path to basic log file
  #
  def save_basic_log(basic_log_file)
    CSV.open(basic_log_file, 'w') do |csv|
      csv << ['image_id', 'image_url', 'timestamp', 'prompt_success', 'video_success', 'overall_success', 'chinese_prompt', 'task_id', 'waiting_time_seconds', 'video_files', 'error_message']
      @basic_log.each do |log_entry|
        csv << [
          log_entry[:image_id],
          log_entry[:image_url],
          log_entry[:timestamp],
          log_entry[:prompt_success],
          log_entry[:video_success],
          log_entry[:overall_success],
          log_entry[:chinese_prompt],
          log_entry[:task_id],
          log_entry[:waiting_time_seconds],
          log_entry[:video_files],
          log_entry[:error_message]
        ]
      end
    end
  end

  ##
  # Save results log to JSON file
  #
  # @param output_file [String] Path to output file
  #
  def save_results_log(output_file)
    File.write(output_file, JSON.pretty_generate(@results_log))
  end

  ##
  # Print processing summary
  #
  def print_processing_summary
    total_images = @results_log.length
    successful_prompts = @results_log.count { |r| r[:prompt_generation][:success] }
    successful_videos = @results_log.count { |r| r[:video_generation][:success] }
    
    # Calculate average waiting time for successful videos
    successful_video_results = @results_log.select { |r| r[:video_generation][:success] }
    avg_waiting_time = if successful_video_results.any?
      total_waiting_time = successful_video_results.sum { |r| r[:video_generation][:waiting_time] || 0 }
      (total_waiting_time / successful_video_results.length).round(1)
    else
      0
    end
    
    puts
    puts "📊 PROCESSING SUMMARY"
    puts "=" * 30
    puts "Total images processed: #{total_images}"
    puts "Successful prompt generations: #{successful_prompts}/#{total_images}"
    puts "Successful video generations: #{successful_videos}/#{total_images}"
    puts "Overall success rate: #{total_images > 0 ? (successful_videos.to_f / total_images * 100).round(1) : 0}%"
    puts "Average video waiting time: #{avg_waiting_time}s"
    
    if successful_videos > 0
      puts
      puts "✅ Successfully generated videos:"
      @results_log.each do |result|
        if result[:video_generation][:success]
          files = result[:video_generation][:downloaded_files] || []
          waiting_time = result[:video_generation][:waiting_time] || 0
          files.each do |file|
            puts "  - Image ID #{result[:image_id]}: #{file[:filepath]} (waited #{waiting_time}s)"
          end
        end
      end
    end
    
    failed_results = @results_log.select { |r| !r[:success] }
    if failed_results.any?
      puts
      puts "❌ Failed processing:"
      failed_results.each do |result|
        error_msg = result[:video_generation][:error] || result[:prompt_generation][:error] || "Unknown error"
        puts "  - Image ID #{result[:image_id]}: #{error_msg}"
      end
    end
  end

  ##
  # List all images from CSV
  #
  # @param csv_file_path [String] Path to CSV file
  #
  def list_images(csv_file_path = 'data/image_list.csv')
    unless File.exist?(csv_file_path)
      puts "❌ CSV file not found: #{csv_file_path}"
      return
    end

    puts "📋 IMAGE LIST"
    puts "=" * 40
    
    CSV.foreach(csv_file_path, headers: true) do |row|
      puts "ID: #{row['id'].ljust(3)} | URL: #{row['image_url']}"
    end
  end
end

##
# Main execution when run directly
#
if __FILE__ == $0
  begin
    processor = ImageToVideoProcessor.new
    
    # Check command line arguments
    case ARGV[0]
    when 'list'
      processor.list_images
    when 'process'
      processor.process_images_from_csv
    when 'single'
      if ARGV[1] && ARGV[2]
        image_url = ARGV[1]
        image_id = ARGV[2].to_i
        result = processor.process_single_image(image_url, image_id)
        puts JSON.pretty_generate(result)
      else
        puts "Usage: ruby image_to_video_processor.rb single <image_url> <image_id>"
      end
    else
      puts "Image to Video Processor"
      puts "=" * 30
      puts "Usage:"
      puts "  ruby image_to_video_processor.rb list                    # List all images from CSV"
      puts "  ruby image_to_video_processor.rb process                 # Process all images"
      puts "  ruby image_to_video_processor.rb single <url> <id>       # Process single image"
      puts
      puts "Examples:"
      puts "  ruby image_to_video_processor.rb list"
      puts "  ruby image_to_video_processor.rb process"
      puts "  ruby image_to_video_processor.rb single https://example.com/image.jpg 1"
      puts
      puts "Features:"
      puts "  - Generates Chinese video prompts using OpenRouter"
      puts "  - Creates videos using Duomi video service"
      puts "  - Tracks waiting times for video generation"
      puts "  - Maintains both detailed JSON and basic CSV logs"
      puts "  - Shows real-time progress and timing information"
    end
    
  rescue ArgumentError => e
    puts "❌ Configuration Error: #{e.message}"
    puts
    puts "Please make sure your .env file contains:"
    puts "  OPENROUTER_API_KEY=your_openrouter_key"
    puts "  DUOMI_API_KEY=your_duomi_key"
    puts "  OPENROUTER_MODEL_NAME=google/gemini-2.5-flash  # optional"
    
  rescue => e
    puts "❌ Unexpected Error: #{e.message}"
    puts e.backtrace.first(5).join("\n") if ENV['DEBUG']
  end
end
