# AdTao Campaign

A comprehensive AI-powered advertising campaign generator that helps create integrated ad campaigns with copy, images, and audience targeting.

## Features

- **Ad Copy Generation**: Create compelling ad headlines, primary text, and descriptions
- **Image Recommendations**: Get AI-powered image style and composition recommendations
- **Image Generation**: Generate images using DALL-E 3 based on product descriptions
- **Image Analysis**: Analyze existing images for quality, composition, and audience appeal
- **Caption Generation**: Generate captions and alt-text for advertising images
- **Integrated Ad Creation**: Generate complete ads with matching copy and images
- **Brand Profile Management**: Create and manage brand profiles to maintain consistent messaging
- **Competitor Analysis**: Upload and analyze competitor ads for insights

## Tech Stack

- FastAPI for the backend API
- SQLite for data storage
- Azure OpenAI for AI capabilities (GPT-4o and DALL-E 3)
- Pydantic for data validation
- Pillow for image processing

## Getting Started

### Prerequisites

- Python 3.8+
- An Azure OpenAI API key

### Environment Setup

Create a `.env` file with the following variables:

```
AZURE_OPENAI_KEY=your_azure_openai_key
AZURE_OPENAI_ENDPOINT=your_azure_openai_endpoint
DEPLOYMENT_NAME=gpt-4o
```

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/Kulraj69/adtao-campaign.git
   cd adtao-campaign
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Initialize the database:
   ```
   python -c "import main; main.init_db()"
   ```

4. Run the application:
   ```
   uvicorn main:app --reload
   ```

## API Endpoints

The application provides various endpoints organized into the following categories:

- **Ad Copy**: Generate advertising copy
- **Images**: Generate, analyze, and caption images
- **Integrated Ads**: Create complete ad campaigns
- **Brand Profiles**: Manage brand guidelines and profiles
- **Competitor Analysis**: Upload and analyze competitor ads
- **Database**: View and manage application data

For detailed API documentation, visit `/docs` after starting the application.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- Azure OpenAI for providing the AI capabilities
- FastAPI for the efficient API framework 