#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative '../lib/openrouter_base'

##
# Example usage of OpenRouter Base Client
#
# This example demonstrates how to use the generate_refined_video_prompt function
# to analyze an image URL and generate a refined video prompt.
#

def main
  # Example image URL (you can replace this with any valid image URL)
  image_url = 'https://iili.io/KnmAbGp.jpg'
  
  puts "OpenRouter Base Client Example"
  puts "=" * 40
  puts "Image URL: #{image_url}"
  puts

  begin
    # Create OpenRouter client
    client = OpenRouterClient.new
    
    # Generate refined video prompt from image URL
    puts "Generating refined video prompt..."
    result = client.generate_refined_video_prompt(image_url)
    
    # Display results
    if result[:success]
      puts "✅ SUCCESS!"
      puts "API Source: #{result[:api_source]}"
      puts "Model Used: #{result[:model_used]}"
      puts "Response Time: #{'%.2f' % result[:response_time]}s"
      puts
      puts "Refined Video Prompt (English):"
      puts "-" * 30
      puts result[:content]
      puts
      puts "Refined Video Prompt (Chinese):"
      puts "-" * 30
      puts result[:refined_video_prompt_cn]
    else
      puts "❌ FAILED!"
      puts "Error: #{result[:error]}"
    end
    
  rescue ArgumentError => e
    puts "❌ Configuration Error: #{e.message}"
    puts
    puts "Please make sure to:"
    puts "1. Set OPENROUTER_API_KEY in your .env file"
    puts "2. Optionally set OPENROUTER_MODEL_NAME (defaults to google/gemini-2.5-flash)"
    
  rescue => e
    puts "❌ Unexpected Error: #{e.message}"
  end
end

# Run the example if this file is executed directly
if __FILE__ == $0
  main
end
