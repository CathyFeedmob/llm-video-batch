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

# Example 1: Basic usage with image URLs and prompt
image_urls = [
  "https://aisp.ttaibot.com/uploads/xz_aivideo/1735500936.jpg",
  "https://db.xiaohuhd.com/1.jpeg"
]

prompt = "一只卡通小猫，穿着棕色皮夹克，戴着墨镜，在舞台上向镜头微笑"

result = duomi_service.generate_video(
  image_urls: image_urls,
  prompt: prompt
)

puts "Status: #{result[:status]}"
puts "Success: #{result[:success]}"
puts "Response: #{result[:body]}"

# Example 2: Advanced usage with custom options
result_advanced = duomi_service.generate_video(
  image_urls: image_urls,
  prompt: prompt,
  model_name: "kling-v1-6",
  negative_prompt: "blurry, low quality",
  cfg_scale: 0.7,
  mode: "std",
  duration: 10,
  callback_url: "https://webhook.site/your-webhook-url"
)

puts "\nAdvanced Result:"
puts "Status: #{result_advanced[:status]}"
puts "Success: #{result_advanced[:success]}"
puts "Response: #{result_advanced[:body]}"
