# Facebook Ad Generator API

A comprehensive API for generating Facebook ad content, including ad copy and images. This application uses Azure OpenAI's GPT-4o and DALL-E 3 to create compelling ad content for Facebook marketing campaigns.

## Features

- Generate ad copy with headline, primary text, and description
- Generate image recommendations based on product details
- Create images using DALL-E 3
- Analyze uploaded product images for Facebook ad effectiveness
- Generate captions for product images
- Integrated ad generation (both copy and images)
- SQLite database to store generated content

## Setup

### Prerequisites

- Python 3.8 or higher
- Azure OpenAI API access
- Required Python packages (see below)

### Installation

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd adtao_campaign
   ```

2. Install required packages:
   ```bash
   pip install fastapi uvicorn pillow python-dotenv openai python-multipart
   ```

3. Create a `.env` file in the project root with your Azure OpenAI credentials:
   ```
   AZURE_OPENAI_KEY=your_azure_openai_key
   AZURE_OPENAI_ENDPOINT=your_azure_openai_endpoint
   DEPLOYMENT_NAME=gpt-4o
   ```

### Running the API

Start the server with:

```bash
python main.py
```

This will launch the API server at `http://0.0.0.0:8000`. You can access the API documentation at `http://localhost:8000/docs`.

## API Endpoints

### Ad Copy Generation

#### `POST /generate-ad-copy`

Generates Facebook ad copy with headline, primary text, and description.

Request body:
```json
{
  "product_name": "EcoFresh Water Bottle",
  "target_audience": "Eco-conscious fitness enthusiasts aged 25-40",
  "key_benefits": [
    "Made from 100% recycled materials",
    "Keeps water cold for 24 hours",
    "Portion of proceeds goes to ocean cleanup"
  ],
  "tone": "professional",
  "ad_length": "medium"
}
```

### Image Generation

#### `POST /generate-image-recommendations`

Recommends imagery for Facebook ads, including image prompts and text recommendations.

Request body:
```json
{
  "product_name": "EcoFresh Water Bottle",
  "target_audience": "Eco-conscious fitness enthusiasts aged 25-40",
  "key_benefits": [
    "Made from 100% recycled materials",
    "Keeps water cold for 24 hours",
    "Portion of proceeds goes to ocean cleanup"
  ],
  "tone": "professional",
  "image_style": "product photography",
  "color_scheme": "blue and green"
}
```

#### `POST /generate-image`

Generates an image using DALL-E 3 based on a prompt.

Request body:
```json
{
  "prompt": "A sleek, eco-friendly water bottle made from recycled materials with a blue and green color scheme. The bottle is sitting on a beach with ocean waves in the background, highlighting its connection to ocean conservation.",
  "size": "1024x1024"
}
```

### Image Analysis

#### `POST /analyze-image`

Analyzes an uploaded product image for its effectiveness in Facebook ads.

Form data:
- `file`: Image file
- `product_name`: Name of the product
- `target_audience`: Target audience for the ad (optional)

### Caption Generation

#### `POST /generate-captions`

Generates captions for a product image.

Form data:
- `file`: Image file
- `product_name`: Name of the product
- `tone`: Tone of the captions (default: "professional")

### Integrated Ad Creation

#### `POST /generate-integrated-ad`

Generates both ad copy and image recommendations in a single request.

Request body:
```json
{
  "product_name": "EcoFresh Water Bottle",
  "target_audience": "Eco-conscious fitness enthusiasts aged 25-40",
  "key_benefits": [
    "Made from 100% recycled materials",
    "Keeps water cold for 24 hours",
    "Portion of proceeds goes to ocean cleanup"
  ],
  "tone": "professional",
  "ad_length": "medium",
  "image_style": "product photography",
  "color_scheme": "blue and green",
  "generate_image": true
}
```

### Database Endpoints

#### `GET /images/recent`

Retrieves recently generated images from the database.

Query parameters:
- `limit`: Maximum number of images to retrieve (default: 10)

#### `GET /images/{image_id}`

Retrieves details about a specific image by ID.

#### `GET /ad-copies/recent`

Retrieves recently generated ad copies from the database.

Query parameters:
- `limit`: Maximum number of ad copies to retrieve (default: 10)

#### `GET /integrated-ads/recent`

Retrieves recently generated integrated ads from the database.

Query parameters:
- `limit`: Maximum number of integrated ads to retrieve (default: 10)

#### `GET /db/stats`

Retrieves statistics about the database, including counts and recent items.

## Database Schema

The application uses SQLite to store generated content with the following tables:

### Images Table
- `id`: Unique identifier
- `filename`: Name of the image file
- `prompt`: Prompt used to generate the image
- `revised_prompt`: Revised prompt used by DALL-E (if any)
- `file_path`: Path to the image file
- `static_path`: URL path for accessing the image
- `creation_date`: When the image was created
- `width`: Image width
- `height`: Image height
- `size`: Image size (e.g., "1024x1024")
- `model`: Model used to generate the image (e.g., "dall-e-3")

### Ad Copies Table
- `id`: Unique identifier
- `product_name`: Name of the product
- `target_audience`: Target audience for the ad
- `headline`: Generated headline
- `primary_text`: Generated primary text
- `description`: Generated description
- `creation_date`: When the ad copy was created

### Integrated Ads Table
- `id`: Unique identifier
- `ad_copy_id`: Reference to the ad copy
- `image_id`: Reference to the image
- `product_name`: Name of the product
- `target_audience`: Target audience for the ad
- `creation_date`: When the integrated ad was created

## License

[MIT License](LICENSE) 