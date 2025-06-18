# AdTao Campaign

A comprehensive AI-powered advertising campaign generator that helps create integrated ad campaigns with 
copy, images, videos, and audio for effective marketing.

## Features

- **Ad Copy Generation**: Create compelling ad headlines, primary text, and descriptions
- **Image Recommendations**: Get AI-powered image style and composition recommendations
- **Image Generation**: Generate images using DALL-E 3 based on product descriptions
- **Image Analysis**: Analyze existing images for quality, composition, and audience appeal
- **Caption Generation**: Generate captions and alt-text for advertising images
- **Integrated Ad Creation**: Generate complete ads with matching copy and images
- **Brand Profile Management**: Create and manage brand profiles to maintain consistent messaging
- **Competitor Analysis**: Upload and analyze competitor ads for insights
- **Video Generation**: Create AI-generated videos using Azure OpenAI Sora
- **Video Ad Prompts**: Generate optimized video prompts for social media campaigns
- **Text-to-Speech**: Convert ad scripts to natural-sounding speech for video voiceovers
- **Ad Script Generation**: Create professional ad scripts optimized for TTS conversion

## Tech Stack

- FastAPI for the backend API
- SQLite for data storage
- Azure OpenAI for AI capabilities (GPT-4o, DALL-E 3, Sora, and TTS)
- Pydantic for data validation
- Pillow for image processing

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/adtao-campaign.git
   cd adtao-campaign
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create required directories:
   ```
   mkdir -p uploads static generated_images generated_videos generated_audio db
   ```

4. Set up environment variables in a `.env` file:
   ```
   AZURE_GPT_KEY=your_azure_openai_key
   AZURE_GPT_ENDPOINT=your_azure_openai_endpoint
   AZURE_DALLE_KEY=your_azure_dalle_key
   AZURE_DALLE_ENDPOINT=your_azure_dalle_endpoint
   AZURE_SORA_KEY=your_azure_sora_key
   AZURE_SORA_ENDPOINT=your_azure_sora_endpoint
   AZURE_TTS_KEY=your_azure_tts_key
   AZURE_TTS_ENDPOINT=your_azure_tts_endpoint
   ```

## Running the Application

Start the server:
```
python3 main.py
```

The API will be available at http://localhost:8000 with interactive documentation at http://localhost:8000/docs.

## API Endpoints

The API includes endpoints for:

- `/generate-ad-copy` - Generate ad copy
- `/generate-image` - Generate images with DALL-E 3
- `/generate-integrated-ad` - Create complete ads with copy and images
- `/generate-video` - Generate videos with Sora
- `/generate-video-ad-prompt` - Create optimized video prompts
- `/generate-ad-script` - Create ad scripts for voiceovers
- `/text-to-speech` - Convert text to speech
- `/brand-profiles` - Manage brand profiles
- `/competitor-ads` - Analyze competitor ads

## Project Structure

- `/static`: Contains generated images and competitor ad images for analysis
- `/generated_images`: Stores AI-generated images for ad campaigns
- `/uploads`: Temporary storage for uploaded images before processing
- `/db`: Contains the SQLite database file

## Latest Updates

- Added competitor analysis images for enhanced ad benchmarking
- Implemented improved image storage and organization
- Added support for multiple competitor ad analysis
- Enhanced database schema for better performance

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- Azure OpenAI for providing the AI capabilities
- FastAPI for the efficient API framework 