import os
import base64
import re
import json
import datetime
import uuid
import io
import sqlite3
import shutil
from typing import List, Optional, Union
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from openai import AzureOpenAI
from dotenv import load_dotenv
import requests
from PIL import Image

# Load environment variables
load_dotenv()

# DALL-E 3 credentials
AZURE_DALLE_KEY = os.getenv("AZURE_DALLE_KEY")
AZURE_DALLE_ENDPOINT = os.getenv("AZURE_DALLE_ENDPOINT")
DALLE_DEPLOYMENT = os.getenv("DALLE_DEPLOYMENT", "dall-e-3")

# GPT-4o credentials
AZURE_GPT_KEY = os.getenv("AZURE_GPT_KEY")
AZURE_GPT_ENDPOINT = os.getenv("AZURE_GPT_ENDPOINT")
GPT_DEPLOYMENT = os.getenv("GPT_DEPLOYMENT", "gpt-4o")

# Sora credentials
AZURE_SORA_KEY = os.getenv("AZURE_SORA_KEY")
AZURE_SORA_ENDPOINT = os.getenv("AZURE_SORA_ENDPOINT")
SORA_DEPLOYMENT = os.getenv("SORA_DEPLOYMENT", "sora")

# Initialize DALL-E client
dalle_client = AzureOpenAI(
    azure_endpoint=AZURE_DALLE_ENDPOINT,
    api_key=AZURE_DALLE_KEY,
    api_version="2024-02-01"
)

# Initialize GPT-4 client
gpt_client = AzureOpenAI(
    azure_endpoint=AZURE_GPT_ENDPOINT,
    api_key=AZURE_GPT_KEY,
    api_version="2025-01-01-preview",
)

# Initialize Sora client
sora_client = AzureOpenAI(
    azure_endpoint=AZURE_SORA_ENDPOINT,
    api_key=AZURE_SORA_KEY,
    api_version="2024-02-15-preview"
)

# Create directories for uploads and static files
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
GENERATED_IMAGES_DIR = os.path.join(os.getcwd(), "generated_images")
GENERATED_VIDEOS_DIR = os.path.join(os.getcwd(), "generated_videos")
STATIC_DIR = os.path.join(os.getcwd(), "static")
DB_DIR = os.path.join(os.getcwd(), "db")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(GENERATED_IMAGES_DIR, exist_ok=True)
os.makedirs(GENERATED_VIDEOS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)

# Set up the database
DB_PATH = os.path.join(DB_DIR, "adtao.db")

# SQLite datetime adapter
def adapt_datetime(dt):
    return dt.isoformat()

def convert_datetime(s):
    return datetime.datetime.fromisoformat(s.decode())

# Register the adapter and converter
sqlite3.register_adapter(datetime.datetime, adapt_datetime)
sqlite3.register_converter("datetime", convert_datetime)

def get_db_connection():
    """Create a connection to the SQLite database"""
    try:
        print(f"Connecting to database at: {DB_PATH}")
        conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        raise

def init_db():
    """Initialize the database schema"""
    try:
        print("\nInitializing database...")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Drop existing video_jobs table if it exists
        cursor.execute("DROP TABLE IF EXISTS video_jobs")
        
        # Create video_jobs table with proper schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS video_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT UNIQUE NOT NULL,
                prompt TEXT NOT NULL,
                status TEXT NOT NULL,
                video_path TEXT,
                error TEXT,
                created_at datetime NOT NULL,
                completed_at datetime,
                updated_at datetime
            )
        """)
        
        conn.commit()
        print("Database initialized successfully")
        
        # Verify the table was created correctly
        cursor.execute("PRAGMA table_info(video_jobs)")
        columns = cursor.fetchall()
        print("\nTable schema:")
        for col in columns:
            print(f"Column: {col['name']}, Type: {col['type']}")
            
    except sqlite3.Error as e:
        print(f"Error initializing database: {e}")
        raise
    finally:
        if conn:
            conn.close()

# Initialize the database
init_db()

# Create FastAPI app
app = FastAPI(
    title="Facebook Ad Generator API",
    description="An API for generating Facebook Ad content, including ad copy and images, with brand profile integration.",
    version="1.0.0",
    openapi_tags=[
        {
            "name": "General",
            "description": "General API information and health checks"
        },
        {
            "name": "Ad Copy",
            "description": "Endpoints for generating text content for Facebook ads"
        },
        {
            "name": "Images",
            "description": "Endpoints for generating, analyzing, and managing images for ads"
        },
        {
            "name": "Integrated Ads",
            "description": "Endpoints for creating complete ads with both copy and images"
        },
        {
            "name": "Brand Profiles",
            "description": "Endpoints for managing brand guidelines and profiles"
        },
        {
            "name": "Database",
            "description": "Endpoints for accessing stored content and statistics"
        },
        {
            "name": "Competitor Analysis",
            "description": "Endpoints for managing competitor ads"
        },
        {
            "name": "Videos",
            "description": "Endpoints for generating and managing videos"
        },
        {
            "name": "TTS & Audio",
            "description": "Endpoints for generating ad scripts and converting text to speech"
        }
    ],
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory for serving uploaded images
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/generated_videos", StaticFiles(directory="generated_videos"), name="generated_videos")
app.mount("/generated_audio", StaticFiles(directory="generated_audio"), name="generated_audio")

# Define request and response models

# Ad Copy Models
class AdCopyRequest(BaseModel):
    product_name: str
    target_audience: str
    key_benefits: List[str]
    tone: Optional[str] = "professional"
    ad_length: Optional[str] = "medium"

class AdCopyResponse(BaseModel):
    headline: str
    primary_text: str
    description: str

# Image Models
class ImageAnalysisRequest(BaseModel):
    image_path: str = Field(..., description="Path to the image file to analyze")
    product_name: str = Field(..., description="Name of the product in the image")
    target_audience: Optional[str] = Field(None, description="Target audience for the ad")

class ImageAnalysisResponse(BaseModel):
    image_quality: str
    composition_rating: str
    audience_appeal: str
    suggested_improvements: List[str]
    compatibility_score: float = Field(..., ge=0.0, le=10.0, description="Score out of 10 for Facebook ad compatibility")

class ImageCaptionRequest(BaseModel):
    image_path: str
    product_name: str
    tone: Optional[str] = "professional"

class ImageCaptionResponse(BaseModel):
    short_caption: str = Field(..., description="Short caption for the image (max 125 characters)")
    full_caption: str = Field(..., description="Longer, more detailed caption")
    alt_text: str = Field(..., description="Accessibility alt text for the image")

class ImageAdRequest(BaseModel):
    product_name: str
    target_audience: str
    key_benefits: List[str]
    tone: Optional[str] = "professional"
    image_style: Optional[str] = "product photography"
    color_scheme: Optional[str] = None

class ImageAdResponse(BaseModel):
    image_prompt: str
    image_description: str
    ad_text_recommendations: List[str]

class ImageGenerationRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"

class ImageGenerationResponse(BaseModel):
    image_path: str
    revised_prompt: Optional[str] = None

# Integrated Models
class IntegratedAdRequest(BaseModel):
    product_name: str
    target_audience: str
    key_benefits: List[str]
    tone: str = "professional"
    ad_length: str = "medium"
    image_style: str = "product photography"
    color_scheme: str = None
    generate_image: bool = True

class IntegratedAdResponse(BaseModel):
    headline: str
    primary_text: str
    description: str
    image_prompt: str
    image_description: str
    ad_text_recommendations: List[str]
    image_path: Optional[str] = None

# Add new Pydantic models for brand profiles
class BrandProfileBase(BaseModel):
    brand_name: str = Field(..., description="Name of the brand")
    industry: Optional[str] = Field(None, description="Industry or sector the brand operates in")
    description: str = Field(..., description="Brief description of the brand")
    tone_of_voice: str = Field(..., description="Preferred tone of voice (e.g., professional, casual, humorous)")
    values: List[str] = Field(..., description="Core brand values")
    target_audience: str = Field(..., description="Description of the target audience")
    visual_identity: str = Field(..., description="Description of visual identity")
    color_palette: Optional[str] = Field(None, description="Preferred colors (comma separated)")
    do_guidelines: Optional[List[str]] = Field(None, description="What content creators SHOULD do")
    dont_guidelines: Optional[List[str]] = Field(None, description="What content creators SHOULD NOT do")
    slogan: Optional[str] = Field(None, description="Brand slogan or tagline")
    hashtags: Optional[List[str]] = Field(None, description="Preferred hashtags")
    examples: Optional[str] = Field(None, description="Examples of good brand content")

class BrandProfileCreate(BrandProfileBase):
    pass

class BrandProfileResponse(BrandProfileBase):
    id: str
    creation_date: str
    last_updated: str

class BrandProfileUpdate(BaseModel):
    brand_name: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    tone_of_voice: Optional[str] = None
    values: Optional[List[str]] = None
    target_audience: Optional[str] = None
    visual_identity: Optional[str] = None
    color_palette: Optional[str] = None
    do_guidelines: Optional[List[str]] = None
    dont_guidelines: Optional[List[str]] = None
    slogan: Optional[str] = None
    hashtags: Optional[List[str]] = None
    examples: Optional[str] = None

# Competitor Ad models
class CompetitorAdBase(BaseModel):
    competitor_name: str = Field(..., description="Name of the competitor brand")
    product_category: str = Field(..., description="Category of the product in the ad")
    target_audience: Optional[str] = Field(None, description="Target audience for the competitor ad")

class CompetitorAdCreate(CompetitorAdBase):
    pass

class CompetitorAdResponse(CompetitorAdBase):
    id: str
    ad_image_path: str
    analysis_data: Optional[dict] = None
    positioning: Optional[str] = None
    typography: Optional[str] = None
    visual_elements: Optional[str] = None
    color_scheme: Optional[str] = None
    creation_date: str
    last_analyzed: Optional[str] = None

class CompetitorAdAnalysisResponse(BaseModel):
    id: str
    competitor_name: str
    positioning: str
    typography: str
    visual_elements: List[str]
    color_scheme: str
    guidelines: List[str]

# Extended request models to include brand integration and competitor insights
class AdCopyRequestWithBrand(AdCopyRequest):
    brand_profile_id: Optional[str] = None

class ImageAdRequestWithBrand(ImageAdRequest):
    brand_profile_id: Optional[str] = None

class IntegratedAdRequestWithBrand(IntegratedAdRequest):
    brand_profile_id: Optional[str] = None

class AdCopyRequestWithCompetitorInsights(AdCopyRequestWithBrand):
    competitor_ids: Optional[List[str]] = None

class ImageAdRequestWithCompetitorInsights(ImageAdRequestWithBrand):
    competitor_ids: Optional[List[str]] = None

class IntegratedAdRequestWithCompetitorInsights(IntegratedAdRequestWithBrand):
    competitor_ids: Optional[List[str]] = None

# Helper functions for image processing
def save_uploaded_image(image: UploadFile) -> str:
    """Save an uploaded image and return the file path"""
    # Generate a unique filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    filename = f"{timestamp}_{unique_id}_{image.filename}"
    
    # Create full path
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    # Save the file
    try:
        # Use a safe method to save the file
        contents = image.file.read()
        
        with open(file_path, "wb") as f:
            f.write(contents)
            
        # Reset the file cursor in case it needs to be read again
        image.file.seek(0)
        
        return file_path
    except Exception as e:
        print(f"Error saving uploaded image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save image: {str(e)}")

def analyze_image_content(image_path: str) -> dict:
    """Analyze image content with Azure OpenAI vision capabilities"""
    try:
        # Encode the image
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('ascii')
        
        # Create Azure OpenAI request with the image
        chat_prompt = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": "You are an expert in visual marketing and Facebook ad imagery. Analyze this image and provide detailed feedback on its effectiveness for Facebook advertising."
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Please analyze this image for use in Facebook advertising. Focus on visual appeal, composition, color usage, and how well it would perform in a Facebook ad."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encoded_image}"
                        }
                    }
                ]
            }
        ]
        
        # Call Azure OpenAI
        response = client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=chat_prompt,
            max_tokens=800,
            temperature=0.7
        )
        
        # Process and return the analysis
        analysis_text = response.choices[0].message.content
        
        # For demo purposes, return a structured analysis
        # In production, you'd want to parse the analysis_text into a structured format
        return {
            "raw_analysis": analysis_text,
            "image_path": image_path
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")

def generate_image_captions(image_path: str, product_name: str, tone: str = "professional") -> dict:
    """Generate captions for the provided image"""
    try:
        # Encode the image
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('ascii')
        
        # Create Azure OpenAI request with the image
        chat_prompt = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": f"You are a marketing expert specialized in creating compelling captions for product images. You excel at crafting captions that highlight product benefits and appeal to potential customers. Use a {tone} tone."
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Generate three captions for this image of {product_name}:\n1. A short caption (max 125 characters)\n2. A detailed caption explaining key benefits\n3. Accessibility alt text that describes the image"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encoded_image}"
                        }
                    }
                ]
            }
        ]
        
        # Call Azure OpenAI
        response = client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=chat_prompt,
            max_tokens=800,
            temperature=0.7
        )
        
        # Return the captions
        return {
            "response": response.choices[0].message.content,
            "image_path": image_path
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Caption generation failed: {str(e)}")

def generate_image_ad_recommendations(request: ImageAdRequest) -> ImageAdResponse:
    """Generate image recommendations for a Facebook ad"""
    
    # Format benefits for the prompt
    benefits = "\n".join([f"- {benefit}" for benefit in request.key_benefits])
    
    # Create the chat prompt
    chat_prompt = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": "You are an expert in visual marketing and ad imagery. You specialize in creating specific, detailed image recommendations for Facebook ads that drive engagement and conversions."
                }
            ]
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"""Create specific recommendations for Facebook ad imagery for:
                    
Product/Service: {request.product_name}
Target Audience: {request.target_audience}
Key Benefits:
{benefits}
Desired Tone: {request.tone}
Preferred Image Style: {request.image_style}
Color Scheme (if specified): {request.color_scheme or 'Not specified'}

Please provide:
1. A detailed image prompt that could be used for image generation
2. A specific description of what the image should contain
3. Three recommendations for ad text that would pair well with the imagery
"""
                }
            ]
        }
    ]
    
    try:
        # Generate completion
        completion = client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=chat_prompt,
            max_tokens=1000,
            temperature=0.7,
            top_p=0.95
        )
        
        # Extract the response
        response_text = completion.choices[0].message.content
        
        # Parse the response (this is a simple example; you might want more robust parsing)
        # For demonstration purposes, we'll extract sections based on numbering and headers
        sections = response_text.split("\n\n")
        
        image_prompt = ""
        image_description = ""
        ad_text_recommendations = []
        
        for section in sections:
            if "image prompt" in section.lower():
                image_prompt = section.split(":", 1)[1].strip() if ":" in section else section
            elif "description" in section.lower():
                image_description = section.split(":", 1)[1].strip() if ":" in section else section
            elif "recommendation" in section.lower() or "ad text" in section.lower():
                # Extract numbered recommendations
                lines = section.split("\n")
                for line in lines:
                    if any(line.strip().startswith(str(i)) for i in range(1, 4)):
                        text = line.split(".", 1)[1].strip() if "." in line else line
                        if text and len(text) > 5:  # Basic validation
                            ad_text_recommendations.append(text)
        
        # If parsing fails, use placeholders
        if not image_prompt:
            image_prompt = "No specific image prompt generated"
        if not image_description:
            image_description = "No image description generated"
        if not ad_text_recommendations:
            ad_text_recommendations = ["No specific ad text recommendations generated"]
        
        return ImageAdResponse(
            image_prompt=image_prompt,
            image_description=image_description,
            ad_text_recommendations=ad_text_recommendations
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate image recommendations: {str(e)}")

def save_image_to_db(prompt: str, filename: str, file_path: str, static_path: str, revised_prompt: str = None, size: str = "1024x1024", model: str = "dall-e-3"):
    """Save image metadata to the database"""
    try:
        # Get image dimensions
        with Image.open(file_path) as img:
            width, height = img.size
        
        # Create a unique ID
        image_id = str(uuid.uuid4())
        
        # Get current date/time
        creation_date = datetime.datetime.now().isoformat()
        
        # Insert into database
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO images (id, filename, prompt, revised_prompt, file_path, static_path, creation_date, width, height, size, model) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (image_id, filename, prompt, revised_prompt, file_path, static_path, creation_date, width, height, size, model)
        )
        conn.commit()
        conn.close()
        
        return image_id
    except Exception as e:
        print(f"Error saving image to database: {str(e)}")
        # Continue even if database save fails
        return None

def save_ad_copy_to_db(product_name: str, target_audience: str, headline: str, primary_text: str, description: str):
    """Save ad copy to the database"""
    try:
        # Create a unique ID
        ad_copy_id = str(uuid.uuid4())
        
        # Get current date/time
        creation_date = datetime.datetime.now().isoformat()
        
        # Insert into database
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO ad_copies (id, product_name, target_audience, headline, primary_text, description, creation_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ad_copy_id, product_name, target_audience, headline, primary_text, description, creation_date)
        )
        conn.commit()
        conn.close()
        
        return ad_copy_id
    except Exception as e:
        print(f"Error saving ad copy to database: {str(e)}")
        # Continue even if database save fails
        return None

def save_integrated_ad_to_db(product_name: str, target_audience: str, ad_copy_id: str = None, image_id: str = None):
    """Save integrated ad to the database"""
    try:
        # Create a unique ID
        integrated_ad_id = str(uuid.uuid4())
        
        # Get current date/time
        creation_date = datetime.datetime.now().isoformat()
        
        # Insert into database
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO integrated_ads (id, ad_copy_id, image_id, product_name, target_audience, creation_date) VALUES (?, ?, ?, ?, ?, ?)",
            (integrated_ad_id, ad_copy_id, image_id, product_name, target_audience, creation_date)
        )
        conn.commit()
        conn.close()
        
        return integrated_ad_id
    except Exception as e:
        print(f"Error saving integrated ad to database: {str(e)}")
        # Continue even if database save fails
        return None

def get_recent_images(limit: int = 10):
    """Get recent images from the database"""
    try:
        conn = get_db_connection()
        images = conn.execute(
            "SELECT * FROM images ORDER BY creation_date DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        result = []
        for img in images:
            result.append(dict(img))
        
        return result
    except Exception as e:
        print(f"Error getting recent images: {str(e)}")
        return []

def get_image_by_id(image_id: str):
    """Get image data by ID"""
    try:
        conn = get_db_connection()
        image = conn.execute(
            "SELECT * FROM images WHERE id = ?",
            (image_id,)
        ).fetchone()
        conn.close()
        
        if image:
            return dict(image)
        return None
    except Exception as e:
        print(f"Error getting image by ID: {str(e)}")
        return None

def generate_image_from_prompt(prompt: str, size: str = "1024x1024") -> str:
    """Generate an image using Azure OpenAI DALL-E and return the file path"""
    try:
        # Call DALL-E API
        result = dalle_client.images.generate(
            model=DALLE_DEPLOYMENT,
            prompt=prompt,
            n=1,
            size=size,
            quality="standard",
            style="natural"
        )
        
        # Get the image URL from the response
        response_data = json.loads(result.model_dump_json())
        image_url = response_data['data'][0]['url']
        revised_prompt = response_data['data'][0].get('revised_prompt', None)
        
        # Download the image
        image_response = requests.get(image_url)
        
        if image_response.status_code == 200:
            # Generate a unique filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            image_name = f"generated_{timestamp}_{unique_id}.png"
            image_path = os.path.join(GENERATED_IMAGES_DIR, image_name)
            
            # Save the image
            with open(image_path, "wb") as f:
                f.write(image_response.content)
                
            # Make a copy in the static directory for serving via web
            static_path = os.path.join(STATIC_DIR, image_name)
            with open(static_path, "wb") as f:
                f.write(image_response.content)
            
            # Save to database
            image_id = save_image_to_db(
                prompt=prompt,
                filename=image_name,
                file_path=image_path,
                static_path=f"/static/{image_name}",
                revised_prompt=revised_prompt,
                size=size,
                model="dall-e-3"
            )
            
            return {
                "id": image_id,
                "image_path": image_path,
                "static_path": f"/static/{image_name}",
                "revised_prompt": revised_prompt
            }
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to download image: {image_response.status_code}"
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Image generation failed: {str(e)}"
        )

# Brand profile database functions
def create_brand_profile(profile: BrandProfileCreate) -> str:
    """Create a new brand profile in the database"""
    conn = None
    try:
        # Create a unique ID
        profile_id = str(uuid.uuid4())
        
        # Get current date/time
        now = datetime.datetime.now().isoformat()
        
        # Convert lists to JSON strings for storage with proper error handling
        try:
            # Use safe JSON serialization with default handling
            values_json = json.dumps(profile.values if profile.values else [])
            do_guidelines_json = json.dumps(profile.do_guidelines) if profile.do_guidelines else None
            dont_guidelines_json = json.dumps(profile.dont_guidelines) if profile.dont_guidelines else None
            hashtags_json = json.dumps(profile.hashtags) if profile.hashtags else None
        except TypeError as e:
            print(f"JSON serialization error: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid data format: {str(e)}")
        
        # Insert into database
        conn = get_db_connection()
        conn.execute(
            """INSERT INTO brand_profiles (
                id, brand_name, industry, description, tone_of_voice, brand_values, 
                target_audience, visual_identity, color_palette, do_guidelines, 
                dont_guidelines, slogan, hashtags, examples, creation_date, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                profile_id, profile.brand_name, profile.industry, profile.description,
                profile.tone_of_voice, values_json, profile.target_audience,
                profile.visual_identity, profile.color_palette, do_guidelines_json,
                dont_guidelines_json, profile.slogan, hashtags_json, 
                profile.examples, now, now
            )
        )
        conn.commit()
        
        print(f"Successfully created brand profile with ID: {profile_id}")
        return profile_id
    except sqlite3.Error as e:
        print(f"SQLite error creating brand profile: {str(e)}")
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        print(f"Error creating brand profile: {str(e)}")
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create brand profile: {str(e)}")
    finally:
        if conn:
            conn.close()

def get_brand_profile(profile_id: str) -> dict:
    """Get a brand profile by ID"""
    try:
        conn = get_db_connection()
        profile = conn.execute(
            "SELECT * FROM brand_profiles WHERE id = ?",
            (profile_id,)
        ).fetchone()
        conn.close()
        
        if profile:
            profile_dict = dict(profile)
            
            # Parse JSON strings back to lists
            profile_dict["values"] = json.loads(profile_dict["brand_values"])
            if profile_dict["do_guidelines"]:
                profile_dict["do_guidelines"] = json.loads(profile_dict["do_guidelines"])
            if profile_dict["dont_guidelines"]:
                profile_dict["dont_guidelines"] = json.loads(profile_dict["dont_guidelines"])
            if profile_dict["hashtags"]:
                profile_dict["hashtags"] = json.loads(profile_dict["hashtags"])
            
            return profile_dict
        
        raise HTTPException(status_code=404, detail="Brand profile not found")
    except sqlite3.Error as sql_e:
        print(f"Database error retrieving brand profile: {str(sql_e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(sql_e)}")
    except json.JSONDecodeError as json_e:
        print(f"JSON parsing error in brand profile: {str(json_e)}")
        raise HTTPException(status_code=500, detail=f"Error parsing brand profile data: {str(json_e)}")
    except Exception as e:
        print(f"Error retrieving brand profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve brand profile: {str(e)}")

def update_brand_profile(profile_id: str, profile_update: BrandProfileUpdate) -> dict:
    """Update an existing brand profile"""
    try:
        # Get current profile
        conn = get_db_connection()
        current_profile = conn.execute(
            "SELECT * FROM brand_profiles WHERE id = ?",
            (profile_id,)
        ).fetchone()
        
        if not current_profile:
            conn.close()
            raise HTTPException(status_code=404, detail="Brand profile not found")
        
        current_profile = dict(current_profile)
        
        # Parse existing JSON fields
        current_values = json.loads(current_profile["brand_values"])
        current_do = json.loads(current_profile["do_guidelines"]) if current_profile["do_guidelines"] else None
        current_dont = json.loads(current_profile["dont_guidelines"]) if current_profile["dont_guidelines"] else None
        current_hashtags = json.loads(current_profile["hashtags"]) if current_profile["hashtags"] else None
        
        # Update with new values if provided
        values = profile_update.values if profile_update.values is not None else current_values
        do_guidelines = profile_update.do_guidelines if profile_update.do_guidelines is not None else current_do
        dont_guidelines = profile_update.dont_guidelines if profile_update.dont_guidelines is not None else current_dont
        hashtags = profile_update.hashtags if profile_update.hashtags is not None else current_hashtags
        
        # Convert back to JSON for storage
        values_json = json.dumps(values)
        do_guidelines_json = json.dumps(do_guidelines) if do_guidelines else None
        dont_guidelines_json = json.dumps(dont_guidelines) if dont_guidelines else None
        hashtags_json = json.dumps(hashtags) if hashtags else None
        
        # Get updated timestamp
        now = datetime.datetime.now().isoformat()
        
        # Build update statement
        update_fields = []
        params = []
        
        if profile_update.brand_name is not None:
            update_fields.append("brand_name = ?")
            params.append(profile_update.brand_name)
        
        if profile_update.industry is not None:
            update_fields.append("industry = ?")
            params.append(profile_update.industry)
        
        if profile_update.description is not None:
            update_fields.append("description = ?")
            params.append(profile_update.description)
        
        if profile_update.tone_of_voice is not None:
            update_fields.append("tone_of_voice = ?")
            params.append(profile_update.tone_of_voice)
        
        if profile_update.values is not None:
            update_fields.append("brand_values = ?")
            params.append(values_json)
        
        if profile_update.target_audience is not None:
            update_fields.append("target_audience = ?")
            params.append(profile_update.target_audience)
        
        if profile_update.visual_identity is not None:
            update_fields.append("visual_identity = ?")
            params.append(profile_update.visual_identity)
        
        if profile_update.color_palette is not None:
            update_fields.append("color_palette = ?")
            params.append(profile_update.color_palette)
        
        if profile_update.do_guidelines is not None:
            update_fields.append("do_guidelines = ?")
            params.append(do_guidelines_json)
        
        if profile_update.dont_guidelines is not None:
            update_fields.append("dont_guidelines = ?")
            params.append(dont_guidelines_json)
        
        if profile_update.slogan is not None:
            update_fields.append("slogan = ?")
            params.append(profile_update.slogan)
        
        if profile_update.hashtags is not None:
            update_fields.append("hashtags = ?")
            params.append(hashtags_json)
        
        if profile_update.examples is not None:
            update_fields.append("examples = ?")
            params.append(profile_update.examples)
        
        # Always update the last_updated field
        update_fields.append("last_updated = ?")
        params.append(now)
        
        # Add profile_id to params
        params.append(profile_id)
        
        # Execute update
        conn.execute(
            f"UPDATE brand_profiles SET {', '.join(update_fields)} WHERE id = ?",
            params
        )
        conn.commit()
        
        # Get updated profile
        updated_profile = conn.execute(
            "SELECT * FROM brand_profiles WHERE id = ?",
            (profile_id,)
        ).fetchone()
        
        conn.close()
        
        if updated_profile:
            profile_dict = dict(updated_profile)
            
            # Parse JSON fields
            profile_dict["values"] = json.loads(profile_dict["brand_values"])
            if profile_dict["do_guidelines"]:
                profile_dict["do_guidelines"] = json.loads(profile_dict["do_guidelines"])
            if profile_dict["dont_guidelines"]:
                profile_dict["dont_guidelines"] = json.loads(profile_dict["dont_guidelines"])
            if profile_dict["hashtags"]:
                profile_dict["hashtags"] = json.loads(profile_dict["hashtags"])
            
            return profile_dict
        
        raise HTTPException(status_code=404, detail="Brand profile not found after update")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating brand profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update brand profile: {str(e)}")

def list_brand_profiles(limit: int = 20, offset: int = 0) -> List[dict]:
    """List brand profiles with pagination"""
    try:
        conn = get_db_connection()
        profiles = conn.execute(
            "SELECT * FROM brand_profiles ORDER BY last_updated DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
        conn.close()
        
        result = []
        for profile in profiles:
            profile_dict = dict(profile)
            
            # Parse JSON fields
            profile_dict["values"] = json.loads(profile_dict["brand_values"])
            if profile_dict["do_guidelines"]:
                profile_dict["do_guidelines"] = json.loads(profile_dict["do_guidelines"])
            if profile_dict["dont_guidelines"]:
                profile_dict["dont_guidelines"] = json.loads(profile_dict["dont_guidelines"])
            if profile_dict["hashtags"]:
                profile_dict["hashtags"] = json.loads(profile_dict["hashtags"])
            
            result.append(profile_dict)
        
        return result
    except Exception as e:
        print(f"Error listing brand profiles: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list brand profiles: {str(e)}")

def delete_brand_profile(profile_id: str) -> bool:
    """Delete a brand profile by ID"""
    try:
        conn = get_db_connection()
        
        # Check if profile exists
        profile = conn.execute(
            "SELECT id FROM brand_profiles WHERE id = ?",
            (profile_id,)
        ).fetchone()
        
        if not profile:
            conn.close()
            raise HTTPException(status_code=404, detail="Brand profile not found")
        
        # Delete the profile
        conn.execute(
            "DELETE FROM brand_profiles WHERE id = ?",
            (profile_id,)
        )
        conn.commit()
        conn.close()
        
        return True
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting brand profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete brand profile: {str(e)}")

# Function to get brand guidelines for ad generation
def get_brand_guidelines_for_prompt(brand_profile_id: str) -> str:
    """Format brand profile information into a prompt section for AI"""
    try:
        profile = get_brand_profile(brand_profile_id)
        
        guidelines = f"""
Brand Guidelines for {profile['brand_name']}:
- Description: {profile['description']}
- Tone of Voice: {profile['tone_of_voice']}
- Values: {', '.join(profile['values'])}
- Target Audience: {profile['target_audience']}
- Visual Identity: {profile['visual_identity']}"""

        if profile.get('color_palette'):
            guidelines += f"\n- Color Palette: {profile['color_palette']}"
        
        if profile.get('slogan'):
            guidelines += f"\n- Slogan: {profile['slogan']}"
        
        if profile.get('do_guidelines'):
            do_list = '\n  * '.join(profile['do_guidelines'])
            guidelines += f"\n- DO:\n  * {do_list}"
        
        if profile.get('dont_guidelines'):
            dont_list = '\n  * '.join(profile['dont_guidelines'])
            guidelines += f"\n- DON'T:\n  * {dont_list}"
        
        if profile.get('hashtags'):
            guidelines += f"\n- Hashtags: {', '.join(profile['hashtags'])}"
        
        return guidelines
    except HTTPException:
        # If profile doesn't exist, return empty guidelines
        print(f"Brand profile with ID {brand_profile_id} not found. Continuing without brand guidelines.")
        return ""
    except Exception as e:
        print(f"Error formatting brand guidelines: {str(e)}")
        return ""

# Competitor ad functions
def save_competitor_ad(image_file: UploadFile, competitor_name: str, product_category: str, target_audience: str = None) -> str:
    """Save a competitor ad to the database"""
    try:
        # Save the uploaded image
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"competitor_{timestamp}_{unique_id}_{image_file.filename}"
        
        # Create full path
        file_path = os.path.join(UPLOAD_DIR, filename)
        static_path = f"/static/{filename}"
        
        # Copy to static directory for web access
        contents = image_file.file.read()
        
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # Create a copy in the static directory
        static_file_path = os.path.join(STATIC_DIR, filename)
        with open(static_file_path, "wb") as f:
            f.write(contents)
        
        # Reset file cursor
        image_file.file.seek(0)
        
        # Create a unique ID
        competitor_ad_id = str(uuid.uuid4())
        
        # Get current date/time
        creation_date = datetime.datetime.now().isoformat()
        
        # Insert into database
        conn = get_db_connection()
        conn.execute(
            """INSERT INTO competitor_ads (
                id, competitor_name, ad_image_path, product_category, 
                target_audience, creation_date
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                competitor_ad_id, competitor_name, static_path, 
                product_category, target_audience, creation_date
            )
        )
        conn.commit()
        conn.close()
        
        return competitor_ad_id
    except Exception as e:
        print(f"Error saving competitor ad: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save competitor ad: {str(e)}")

def analyze_competitor_ad(competitor_ad_id: str) -> dict:
    """Analyze a competitor ad for positioning, typography, and visual elements"""
    try:
        # Get the competitor ad data
        conn = get_db_connection()
        ad = conn.execute(
            "SELECT * FROM competitor_ads WHERE id = ?",
            (competitor_ad_id,)
        ).fetchone()
        
        if not ad:
            conn.close()
            raise HTTPException(status_code=404, detail="Competitor ad not found")
        
        ad = dict(ad)
        conn.close()
        
        # Get the image file path
        image_path = os.path.join(STATIC_DIR, os.path.basename(ad["ad_image_path"]))
        
        # If static path starts with /static/, adjust it
        if not os.path.exists(image_path) and ad["ad_image_path"].startswith("/static/"):
            image_path = os.path.join(STATIC_DIR, os.path.basename(ad["ad_image_path"]))
        
        # Check if file exists
        if not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail=f"Image file not found at {image_path}")
        
        # Analyze the image with Azure OpenAI vision
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('ascii')
        
        # Create Azure OpenAI request with the image
        chat_prompt = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": """You are an expert in advertising design, with deep knowledge of marketing positioning, typography, and visual elements. 
                        Analyze this advertisement in detail, looking specifically at:
                        1. Positioning: How the ad positions the product/service (premium, value, innovator, etc.)
                        2. Typography: Fonts used, text arrangement, emphasis
                        3. Visual Elements: Image composition, use of people/objects, focal points
                        4. Color Scheme: Dominant colors and how they're used
                        5. Effectiveness: Rate the overall ad effectiveness from 0-10, where 10 is extremely effective
                        
                        Then, provide actionable guidelines that could be derived from this ad's design approach."""
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Analyze this competitor ad for {ad['competitor_name']} in the {ad['product_category']} category. Provide detailed analysis on positioning, typography, visual elements, and color scheme, followed by an effectiveness score (0-10) and actionable guidelines we could apply to our own ads."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encoded_image}"
                        }
                    }
                ]
            }
        ]
        
        # Call Azure OpenAI
        response = client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=chat_prompt,
            max_tokens=1000,
            temperature=0.5
        )
        
        # Process the analysis
        analysis_text = response.choices[0].message.content
        
        # Extract sections (this is a simple parsing approach)
        positioning = ""
        typography = ""
        visual_elements = []
        color_scheme = ""
        guidelines = []
        effectiveness_score = 0.0
        
        # Simple parsing - in production, you'd want more robust extraction
        sections = analysis_text.split("\n\n")
        for section in sections:
            if "positioning" in section.lower():
                positioning = section.split(":", 1)[1].strip() if ":" in section else section
            elif "typography" in section.lower():
                typography = section.split(":", 1)[1].strip() if ":" in section else section
            elif "visual elements" in section.lower() or "visuals" in section.lower():
                visual_text = section.split(":", 1)[1].strip() if ":" in section else section
                visual_elements = [item.strip() for item in visual_text.split("-") if item.strip()]
            elif "color" in section.lower():
                color_scheme = section.split(":", 1)[1].strip() if ":" in section else section
            elif "effectiveness" in section.lower() or "score" in section.lower() or "rating" in section.lower():
                # Extract the effectiveness score
                score_text = section.split(":", 1)[1].strip() if ":" in section else section
                # Look for a number from 0-10 in the text
                score_match = re.search(r"(\d+(?:\.\d+)?)/10|(\d+(?:\.\d+)?)\s*out of\s*10|(\d+(?:\.\d+)?)(?:/|\s*out of\s*)?\s*10", score_text)
                if score_match:
                    # Get the matched group that contains the number
                    matched_group = next(group for group in score_match.groups() if group is not None)
                    effectiveness_score = float(matched_group)
                else:
                    # Try to extract any number between 0 and 10
                    number_match = re.search(r"(\d+(?:\.\d+)?)", score_text)
                    if number_match:
                        score = float(number_match.group(1))
                        if 0 <= score <= 10:
                            effectiveness_score = score
            elif "guidelines" in section.lower() or "recommendations" in section.lower():
                guidelines_text = section.split(":", 1)[1].strip() if ":" in section else section
                guidelines = [item.strip() for item in guidelines_text.split("-") if item.strip()]
        
        # Set is_exemplary flag for ads with high scores
        is_exemplary = effectiveness_score >= 8.0
        
        # Save the analysis to the database
        conn = get_db_connection()
        conn.execute(
            """UPDATE competitor_ads SET 
            analysis_data = ?, positioning = ?, typography = ?, 
            visual_elements = ?, color_scheme = ?, effectiveness_score = ?,
            is_exemplary = ?, last_analyzed = ?
            WHERE id = ?""",
            (
                analysis_text, positioning, typography,
                json.dumps(visual_elements), color_scheme, effectiveness_score,
                is_exemplary, datetime.datetime.now().isoformat(),
                competitor_ad_id
            )
        )
        conn.commit()
        conn.close()
        
        return {
            "id": competitor_ad_id,
            "competitor_name": ad["competitor_name"],
            "positioning": positioning,
            "typography": typography,
            "visual_elements": visual_elements,
            "color_scheme": color_scheme,
            "effectiveness_score": effectiveness_score,
            "is_exemplary": is_exemplary,
            "guidelines": guidelines,
            "full_analysis": analysis_text
        }
    except Exception as e:
        print(f"Error analyzing competitor ad: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze competitor ad: {str(e)}")

def get_competitor_ad(competitor_ad_id: str) -> dict:
    """Get a competitor ad by ID"""
    try:
        conn = get_db_connection()
        ad = conn.execute(
            "SELECT * FROM competitor_ads WHERE id = ?",
            (competitor_ad_id,)
        ).fetchone()
        conn.close()
        
        if ad:
            ad_dict = dict(ad)
            
            # Parse JSON fields
            if ad_dict["visual_elements"]:
                try:
                    ad_dict["visual_elements"] = json.loads(ad_dict["visual_elements"])
                except:
                    ad_dict["visual_elements"] = []
            else:
                ad_dict["visual_elements"] = []
            
            return ad_dict
        
        raise HTTPException(status_code=404, detail="Competitor ad not found")
    except Exception as e:
        print(f"Error getting competitor ad: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get competitor ad: {str(e)}")

def list_competitor_ads(limit: int = 20, offset: int = 0, product_category: str = None) -> List[dict]:
    """List competitor ads with optional filtering by product category"""
    try:
        conn = get_db_connection()
        
        if product_category:
            ads = conn.execute(
                "SELECT * FROM competitor_ads WHERE product_category = ? ORDER BY creation_date DESC LIMIT ? OFFSET ?",
                (product_category, limit, offset)
            ).fetchall()
        else:
            ads = conn.execute(
                "SELECT * FROM competitor_ads ORDER BY creation_date DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
        
        conn.close()
        
        result = []
        for ad in ads:
            ad_dict = dict(ad)
            
            # Parse JSON fields
            if ad_dict["visual_elements"]:
                try:
                    ad_dict["visual_elements"] = json.loads(ad_dict["visual_elements"])
                except:
                    ad_dict["visual_elements"] = []
            else:
                ad_dict["visual_elements"] = []
            
            result.append(ad_dict)
        
        return result
    except Exception as e:
        print(f"Error listing competitor ads: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list competitor ads: {str(e)}")

def get_competitor_guidelines_for_prompt(competitor_ids: List[str] = None, use_exemplary: bool = True, category: str = None, limit: int = 3) -> str:
    """Format competitor ad insights into a prompt section for AI"""
    try:
        guidelines = "\nCompetitor Ad Insights:"
        
        # If specific competitor IDs are provided, use those
        if competitor_ids and len(competitor_ids) > 0:
            for comp_id in competitor_ids:
                try:
                    ad = get_competitor_ad(comp_id)
                    
                    guidelines += f"\n\nCompetitor: {ad['competitor_name']} ({ad['product_category']})"
                    
                    if ad["positioning"]:
                        guidelines += f"\n- Positioning: {ad['positioning']}"
                    
                    if ad["typography"]:
                        guidelines += f"\n- Typography: {ad['typography']}"
                    
                    if ad["visual_elements"] and len(ad["visual_elements"]) > 0:
                        elements = "\n  * ".join(ad["visual_elements"])
                        guidelines += f"\n- Visual Elements:\n  * {elements}"
                    
                    if ad["color_scheme"]:
                        guidelines += f"\n- Color Scheme: {ad['color_scheme']}"
                except:
                    # Skip this competitor if there's an error
                    continue
        # Otherwise, if use_exemplary is True, use the best performing ads
        elif use_exemplary:
            exemplary_ads = get_exemplary_competitor_ads(category=category, limit=limit)
            
            if not exemplary_ads:
                # If no exemplary ads, try getting any ads for the category
                conn = get_db_connection()
                if category:
                    ads = conn.execute(
                        "SELECT * FROM competitor_ads WHERE product_category = ? ORDER BY effectiveness_score DESC LIMIT ?",
                        (category, limit)
                    ).fetchall()
                else:
                    ads = conn.execute(
                        "SELECT * FROM competitor_ads ORDER BY effectiveness_score DESC LIMIT ?",
                        (limit,)
                    ).fetchall()
                conn.close()
                
                exemplary_ads = []
                for ad in ads:
                    ad_dict = dict(ad)
                    if ad_dict["visual_elements"]:
                        try:
                            ad_dict["visual_elements"] = json.loads(ad_dict["visual_elements"])
                        except:
                            ad_dict["visual_elements"] = []
                    else:
                        ad_dict["visual_elements"] = []
                    exemplary_ads.append(ad_dict)
            
            for ad in exemplary_ads:
                guidelines += f"\n\nCompetitor: {ad['competitor_name']} ({ad['product_category']}) - Score: {ad.get('effectiveness_score', 'N/A')}"
                
                if ad.get("positioning"):
                    guidelines += f"\n- Positioning: {ad['positioning']}"
                
                if ad.get("typography"):
                    guidelines += f"\n- Typography: {ad['typography']}"
                
                if ad.get("visual_elements") and len(ad["visual_elements"]) > 0:
                    elements = "\n  * ".join(ad["visual_elements"])
                    guidelines += f"\n- Visual Elements:\n  * {elements}"
                
                if ad.get("color_scheme"):
                    guidelines += f"\n- Color Scheme: {ad['color_scheme']}"
        
        # If we have no insights, return empty string
        if guidelines == "\nCompetitor Ad Insights:":
            return ""
            
        return guidelines
    except Exception as e:
        print(f"Error formatting competitor guidelines: {str(e)}")
        return ""

# API Endpoints
@app.get("/", tags=["General"])
async def root():
    return {"message": "Facebook Ad Generator API. Use /generate-ad-copy or /generate-image endpoints."}

@app.post("/generate-ad-copy", response_model=AdCopyResponse, tags=["Ad Copy"])
async def generate_ad_copy(request: AdCopyRequestWithBrand):
    try:
        # Construct prompt for ad copy generation
        benefits_text = "\n".join([f"- {benefit}" for benefit in request.key_benefits])
        
        # Add brand guidelines if provided
        brand_guidelines = ""
        if request.brand_profile_id:
            brand_guidelines = get_brand_guidelines_for_prompt(request.brand_profile_id)
        
        # Create the chat prompt with enhanced instructions
        chat_prompt = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": """You are an expert Facebook advertising copywriter with over 10 years of experience creating high-converting ad copy for major brands. 

You excel at crafting specific, compelling, and action-oriented ad copy that targets audience pain points and communicates clear benefits. Your headlines are attention-grabbing, your primary text tells a story that resonates with the audience, and your descriptions focus on tangible outcomes.

Create Facebook ads with concrete details, specific claims, emotional appeals, and clear calls to action.

Structure your response exactly as follows WITHOUT ANY MARKDOWN or asterisks:
Headline: [Attention-grabbing headline with max 40 characters]
Primary Text: [Compelling main copy that creates urgency and speaks directly to the audience]
Description: [Additional benefits and strong call to action]"""
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""Create a highly specific, benefit-driven Facebook ad for:
                        
Product/Service: {request.product_name}
Target Audience: {request.target_audience}
Key Benefits:
{benefits_text}
Tone: {request.tone}
Length: {request.ad_length}
{brand_guidelines}

Guidelines:
1. Headline: Create a specific, benefit-focused headline that mentions the product or a key number (max 40 characters)
2. Primary Text: Start with a question or statement that addresses a pain point, then explain specific benefits with data/numbers when possible, and include social proof
3. Description: Provide specific details about the product/service and end with a strong call to action

Do not use generic phrases like "perfect solution" - be specific about exactly how the product solves problems.
Include numbers, percentages, or timeframes when discussing benefits.
DO NOT USE MARKDOWN FORMATTING or asterisks in your response.
"""
                    }
                ]
            }
        ]
        
        # Generate completion
        completion = gpt_client.chat.completions.create(
            model=GPT_DEPLOYMENT,
            messages=chat_prompt,
            max_tokens=1000,
            temperature=0.7,
            top_p=0.95
        )
        
        # Extract the response
        response_text = completion.choices[0].message.content
        
        # Parse the response
        headline_match = re.search(r"Headline:\s*(.*?)(?=\n*Primary Text:|$)", response_text, re.IGNORECASE | re.DOTALL)
        primary_text_match = re.search(r"Primary Text:\s*(.*?)(?=\n*Description:|$)", response_text, re.IGNORECASE | re.DOTALL)
        description_match = re.search(r"Description:\s*(.*?)(?=$)", response_text, re.IGNORECASE | re.DOTALL)
        
        headline = headline_match.group(1).strip() if headline_match else "No headline generated"
        primary_text = primary_text_match.group(1).strip() if primary_text_match else "No primary text generated"
        description = description_match.group(1).strip() if description_match else "No description generated"
        
        ad_copy = AdCopyResponse(
            headline=headline,
            primary_text=primary_text,
            description=description
        )
        
        # Save to database
        ad_copy_id = save_ad_copy_to_db(
            product_name=request.product_name,
            target_audience=request.target_audience,
            headline=headline,
            primary_text=primary_text,
            description=description
        )
        
        print(f"Parsed ad copy: {ad_copy}")
        return ad_copy
        
    except Exception as e:
        print(f"Error in generate_ad_copy: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating ad copy: {str(e)}")

@app.post("/generate-image-recommendations", response_model=ImageAdResponse, tags=["Images"])
async def generate_image_recommendations(request: ImageAdRequestWithBrand):
    """Generate image recommendations for a Facebook ad"""
    try:
        # Add brand guidelines if provided
        brand_guidelines = ""
        if request.brand_profile_id:
            brand_guidelines = get_brand_guidelines_for_prompt(request.brand_profile_id)
        
        # Format benefits for the prompt
        benefits = "\n".join([f"- {benefit}" for benefit in request.key_benefits])
        
        # Create the chat prompt
        chat_prompt = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": "You are an expert in visual marketing and ad imagery. You specialize in creating specific, detailed image recommendations for Facebook ads that drive engagement and conversions."
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""Create specific recommendations for Facebook ad imagery for:
                        
Product/Service: {request.product_name}
Target Audience: {request.target_audience}
Key Benefits:
{benefits}
Desired Tone: {request.tone}
Preferred Image Style: {request.image_style}
Color Scheme (if specified): {request.color_scheme or 'Not specified'}
{brand_guidelines}

Please provide:
1. A detailed image prompt that could be used for image generation
2. A specific description of what the image should contain
3. Three recommendations for ad text that would pair well with the imagery
"""
                    }
                ]
            }
        ]
        
        return generate_image_ad_recommendations(request)
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error generating image recommendations: {str(e)}"
        )

@app.post("/generate-image", tags=["Images"])
async def generate_image(request: ImageGenerationRequest):
    """Generate an image using DALL-E 3"""
    try:
        result = generate_image_from_prompt(request.prompt, request.size)
        return {
            "id": result["id"],
            "image_path": result["static_path"],
            "revised_prompt": result["revised_prompt"]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error generating image: {str(e)}"
        )

@app.post("/analyze-image", tags=["Images"])
async def analyze_image(
    file: UploadFile = File(...),
    product_name: str = Form(...),
    target_audience: str = Form(None)
):
    """Analyze an uploaded product image for Facebook ad effectiveness"""
    try:
        # Reset file position to start to ensure we can read the entire file
        await file.seek(0)
        
        # Save the uploaded image
        file_path = save_uploaded_image(file)
        
        # Analyze the image
        analysis = analyze_image_content(file_path)
        
        return analysis
    except Exception as e:
        print(f"Error in analyze_image: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing image: {str(e)}"
        )

@app.post("/generate-captions", tags=["Images"])
async def generate_captions(
    file: UploadFile = File(...),
    product_name: str = Form(...),
    tone: str = Form("professional")
):
    """Generate captions for a product image"""
    try:
        # Save the uploaded image
        file_path = save_uploaded_image(file)
        
        # Generate captions
        captions = generate_image_captions(file_path, product_name, tone)
        
        return captions
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating captions: {str(e)}"
        )

@app.post("/generate-integrated-ad", response_model=IntegratedAdResponse, tags=["Integrated Ads"])
async def generate_integrated_ad(request: IntegratedAdRequestWithBrand):
    """Generate both ad copy and image recommendations for a Facebook ad"""
    try:
        # Generate ad copy
        ad_copy_request = AdCopyRequestWithBrand(
            product_name=request.product_name,
            target_audience=request.target_audience,
            key_benefits=request.key_benefits,
            tone=request.tone,
            ad_length=request.ad_length,
            brand_profile_id=request.brand_profile_id if hasattr(request, 'brand_profile_id') else None
        )
        ad_copy = await generate_ad_copy(ad_copy_request)
        
        # Generate image recommendations
        image_ad_request = ImageAdRequestWithBrand(
            product_name=request.product_name,
            target_audience=request.target_audience,
            key_benefits=request.key_benefits,
            tone=request.tone,
            image_style=request.image_style,
            color_scheme=request.color_scheme,
            brand_profile_id=request.brand_profile_id if hasattr(request, 'brand_profile_id') else None
        )
        image_recommendations = await generate_image_recommendations(image_ad_request)
        
        # Generate actual image if requested
        image_path = None
        image_id = None
        if request.generate_image:
            image_result = generate_image_from_prompt(image_recommendations.image_prompt)
            image_path = image_result["static_path"]
            image_id = image_result["id"]
        
        # Save integrated ad to database
        integrated_ad_id = save_integrated_ad_to_db(
            product_name=request.product_name,
            target_audience=request.target_audience,
            ad_copy_id=None,  # We don't have this from the generate_ad_copy function yet
            image_id=image_id
        )
        
        # Combine responses
        return IntegratedAdResponse(
            headline=ad_copy.headline,
            primary_text=ad_copy.primary_text,
            description=ad_copy.description,
            image_prompt=image_recommendations.image_prompt,
            image_description=image_recommendations.image_description,
            ad_text_recommendations=image_recommendations.ad_text_recommendations,
            image_path=image_path
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error generating integrated ad: {str(e)}"
        )

@app.post("/create-complete-ad", response_model=IntegratedAdResponse, tags=["Integrated Ads"])
async def create_complete_ad(
    product_name: str = Form(...),
    target_audience: str = Form(...),
    key_benefits: str = Form(...),
    tone: str = Form("professional"),
    ad_length: str = Form("medium"),
    image_style: str = Form("product photography"),
    color_scheme: str = Form(None),
    brand_profile_id: str = Form(None),
    competitor_ids: str = Form(None),  # Comma-separated list of competitor ad IDs
    use_exemplary_ads: bool = Form(True),  # Whether to use exemplary ads if no specific IDs are provided
    product_category: str = Form(None)  # Product category for finding relevant exemplary ads
):
    """Create a complete ad with both copy and image in one simple request using form data"""
    try:
        # Parse key benefits from comma-separated string
        benefits_list = [benefit.strip() for benefit in key_benefits.split(',')]
        
        # Parse competitor IDs if provided
        competitor_ids_list = None
        if competitor_ids:
            competitor_ids_list = [comp_id.strip() for comp_id in competitor_ids.split(',')]
        
        # Create integrated ad request
        request = IntegratedAdRequestWithCompetitorInsights(
            product_name=product_name,
            target_audience=target_audience,
            key_benefits=benefits_list,
            tone=tone,
            ad_length=ad_length,
            image_style=image_style,
            color_scheme=color_scheme,
            generate_image=True,
            brand_profile_id=brand_profile_id,
            competitor_ids=competitor_ids_list
        )
        
        # Use the existing endpoint implementation with modifications
        try:
            # Generate ad copy
            ad_copy_request = AdCopyRequestWithCompetitorInsights(
                product_name=request.product_name,
                target_audience=request.target_audience,
                key_benefits=request.key_benefits,
                tone=request.tone,
                ad_length=request.ad_length,
                brand_profile_id=request.brand_profile_id if hasattr(request, 'brand_profile_id') else None,
                competitor_ids=request.competitor_ids if hasattr(request, 'competitor_ids') else None
            )
            
            # Add competitor guidelines to ad copy generation
            benefits_text = "\n".join([f"- {benefit}" for benefit in ad_copy_request.key_benefits])
            
            # Add brand guidelines if provided
            brand_guidelines = ""
            if hasattr(ad_copy_request, 'brand_profile_id') and ad_copy_request.brand_profile_id:
                brand_guidelines = get_brand_guidelines_for_prompt(ad_copy_request.brand_profile_id)
            
            # Add competitor guidelines
            competitor_guidelines = ""
            if hasattr(ad_copy_request, 'competitor_ids') and ad_copy_request.competitor_ids:
                competitor_guidelines = get_competitor_guidelines_for_prompt(
                    competitor_ids=ad_copy_request.competitor_ids,
                    use_exemplary=False
                )
            elif use_exemplary_ads:
                # Use exemplary ads if no specific IDs provided and use_exemplary_ads is True
                competitor_guidelines = get_competitor_guidelines_for_prompt(
                    use_exemplary=True,
                    category=product_category
                )
            
            # Create the chat prompt with enhanced instructions
            chat_prompt = [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": """You are an expert copywriter specializing in Facebook ads. You excel at creating compelling, conversion-focused ad copy that resonates with target audiences."""
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"""Create Facebook ad copy for:
                            
Product/Service: {ad_copy_request.product_name}
Target Audience: {ad_copy_request.target_audience}
Key Benefits:
{benefits_text}
Tone: {ad_copy_request.tone}
Ad Length: {ad_copy_request.ad_length}
{brand_guidelines}
{competitor_guidelines}

Please provide:
1. A compelling headline (max 40 characters)
2. Primary text (max 125 characters)
3. A detailed description (max 150 characters)

The copy should be engaging, highlight key benefits, and include a clear call to action."""
                        }
                    ]
                }
            ]
            
            # Generate completion using GPT-4
            completion = gpt_client.chat.completions.create(
                model=GPT_DEPLOYMENT,
                messages=chat_prompt,
                max_tokens=1000,
                temperature=0.7,
                top_p=0.95
            )
            
            # Extract the response
            response_text = completion.choices[0].message.content
            
            # Parse the response
            headline_match = re.search(r"Headline:\s*(.*?)(?=\n*Primary Text:|$)", response_text, re.IGNORECASE | re.DOTALL)
            primary_text_match = re.search(r"Primary Text:\s*(.*?)(?=\n*Description:|$)", response_text, re.IGNORECASE | re.DOTALL)
            description_match = re.search(r"Description:\s*(.*?)(?=$)", response_text, re.IGNORECASE | re.DOTALL)
            
            headline = headline_match.group(1).strip() if headline_match else "No headline generated"
            primary_text = primary_text_match.group(1).strip() if primary_text_match else "No primary text generated"
            description = description_match.group(1).strip() if description_match else "No description generated"
            
            ad_copy = AdCopyResponse(
                headline=headline,
                primary_text=primary_text,
                description=description
            )
            
            # Generate image recommendations
            image_ad_request = ImageAdRequestWithCompetitorInsights(
                product_name=request.product_name,
                target_audience=request.target_audience,
                key_benefits=request.key_benefits,
                tone=request.tone,
                image_style=request.image_style,
                color_scheme=request.color_scheme,
                brand_profile_id=request.brand_profile_id if hasattr(request, 'brand_profile_id') else None,
                competitor_ids=request.competitor_ids if hasattr(request, 'competitor_ids') else None
            )
            
            # Add competitor guidelines to image generation too
            # Format benefits for the prompt
            benefits = "\n".join([f"- {benefit}" for benefit in image_ad_request.key_benefits])
            
            # Add brand guidelines if provided
            brand_guidelines = ""
            if hasattr(image_ad_request, 'brand_profile_id') and image_ad_request.brand_profile_id:
                brand_guidelines = get_brand_guidelines_for_prompt(image_ad_request.brand_profile_id)
            
            # Add competitor guidelines
            competitor_guidelines = ""
            if hasattr(image_ad_request, 'competitor_ids') and image_ad_request.competitor_ids:
                competitor_guidelines = get_competitor_guidelines_for_prompt(
                    competitor_ids=image_ad_request.competitor_ids,
                    use_exemplary=False
                )
            elif use_exemplary_ads:
                # Use exemplary ads if no specific IDs provided and use_exemplary_ads is True
                competitor_guidelines = get_competitor_guidelines_for_prompt(
                    use_exemplary=True,
                    category=product_category
                )
            
            # Create the chat prompt
            chat_prompt = [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": "You are an expert in visual marketing and ad imagery. You specialize in creating specific, detailed image recommendations for Facebook ads that drive engagement and conversions."
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"""Create specific recommendations for Facebook ad imagery for:
                            
Product/Service: {image_ad_request.product_name}
Target Audience: {image_ad_request.target_audience}
Key Benefits:
{benefits}
Desired Tone: {image_ad_request.tone}
Preferred Image Style: {image_ad_request.image_style}
Color Scheme (if specified): {image_ad_request.color_scheme or 'Not specified'}
{brand_guidelines}
{competitor_guidelines}

Please provide:
1. A detailed image prompt that could be used for image generation
2. A specific description of what the image should contain
3. Three recommendations for ad text that would pair well with the imagery
"""
                        }
                    ]
                }
            ]
            
            # Generate completion
            completion = gpt_client.chat.completions.create(
                model=GPT_DEPLOYMENT,
                messages=chat_prompt,
                max_tokens=1000,
                temperature=0.7,
                top_p=0.95
            )
            
            # Extract the response
            response_text = completion.choices[0].message.content
            
            # Parse the response (this is a simple example; you might want more robust parsing)
            # For demonstration purposes, we'll extract sections based on numbering and headers
            sections = response_text.split("\n\n")
            
            image_prompt = ""
            image_description = ""
            ad_text_recommendations = []
            
            for section in sections:
                if "image prompt" in section.lower():
                    image_prompt = section.split(":", 1)[1].strip() if ":" in section else section
                elif "description" in section.lower():
                    image_description = section.split(":", 1)[1].strip() if ":" in section else section
                elif "recommendation" in section.lower() or "ad text" in section.lower():
                    # Extract numbered recommendations
                    lines = section.split("\n")
                    for line in lines:
                        if any(line.strip().startswith(str(i)) for i in range(1, 4)):
                            text = line.split(".", 1)[1].strip() if "." in line else line
                            if text and len(text) > 5:  # Basic validation
                                ad_text_recommendations.append(text)
            
            # If parsing fails, use placeholders
            if not image_prompt:
                image_prompt = "No specific image prompt generated"
            if not image_description:
                image_description = "No image description generated"
            if not ad_text_recommendations:
                ad_text_recommendations = ["No specific ad text recommendations generated"]
            
            image_recommendations = ImageAdResponse(
                image_prompt=image_prompt,
                image_description=image_description,
                ad_text_recommendations=ad_text_recommendations
            )
            
            # Generate actual image if requested
            image_path = None
            image_id = None
            if request.generate_image:
                image_result = generate_image_from_prompt(image_recommendations.image_prompt)
                image_path = image_result["static_path"]
                image_id = image_result["id"]
            
            # Save ad copy to database
            ad_copy_id = save_ad_copy_to_db(
                product_name=request.product_name,
                target_audience=request.target_audience,
                headline=headline,
                primary_text=primary_text,
                description=description
            )
            
            # Save integrated ad to database
            integrated_ad_id = save_integrated_ad_to_db(
                product_name=request.product_name,
                target_audience=request.target_audience,
                ad_copy_id=ad_copy_id,
                image_id=image_id
            )
            
            # Combine responses
            return IntegratedAdResponse(
                headline=ad_copy.headline,
                primary_text=ad_copy.primary_text,
                description=ad_copy.description,
                image_prompt=image_recommendations.image_prompt,
                image_description=image_recommendations.image_description,
                ad_text_recommendations=image_recommendations.ad_text_recommendations,
                image_path=image_path
            )
            
        except Exception as e:
            print(f"Error in integrated ad generation: {str(e)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error generating integrated ad: {str(e)}"
            )
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error creating complete ad: {str(e)}"
        )

# Add brand profile endpoints
@app.post("/brand-profiles", response_model=BrandProfileResponse, tags=["Brand Profiles"])
async def create_brand_profile_endpoint(profile: BrandProfileCreate):
    """Create a new brand profile"""
    profile_id = create_brand_profile(profile)
    return get_brand_profile(profile_id)

@app.get("/brand-profiles", response_model=List[BrandProfileResponse], tags=["Brand Profiles"])
async def list_brand_profiles_endpoint(limit: int = 20, offset: int = 0):
    """List all brand profiles with pagination"""
    return list_brand_profiles(limit, offset)

@app.get("/brand-profiles/{profile_id}", response_model=BrandProfileResponse, tags=["Brand Profiles"])
async def get_brand_profile_endpoint(profile_id: str):
    """Get a specific brand profile by ID"""
    return get_brand_profile(profile_id)

@app.patch("/brand-profiles/{profile_id}", response_model=BrandProfileResponse, tags=["Brand Profiles"])
async def update_brand_profile_endpoint(profile_id: str, profile_update: BrandProfileUpdate):
    """Update a brand profile"""
    return update_brand_profile(profile_id, profile_update)

@app.delete("/brand-profiles/{profile_id}", tags=["Brand Profiles"])
async def delete_brand_profile_endpoint(profile_id: str):
    """Delete a brand profile"""
    delete_brand_profile(profile_id)
    return {"success": True, "message": "Brand profile deleted successfully"}

# Add new endpoints for image database
@app.get("/images/recent", tags=["Database", "Images"])
async def get_recent_images_endpoint(limit: int = 10):
    """Get recent images from the database"""
    images = get_recent_images(limit)
    return {"images": images}

@app.get("/images/{image_id}", tags=["Database", "Images"])
async def get_image_endpoint(image_id: str):
    """Get image details by ID"""
    image = get_image_by_id(image_id)
    if image:
        return image
    raise HTTPException(status_code=404, detail="Image not found")

@app.get("/db/stats", tags=["Database"])
async def get_db_stats():
    """Get database statistics"""
    try:
        conn = get_db_connection()
        
        # Count items in each table
        image_count = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
        ad_copy_count = conn.execute("SELECT COUNT(*) FROM ad_copies").fetchone()[0]
        integrated_ad_count = conn.execute("SELECT COUNT(*) FROM integrated_ads").fetchone()[0]
        
        # Get recent items
        recent_images = conn.execute(
            "SELECT id, filename, prompt, creation_date FROM images ORDER BY creation_date DESC LIMIT 5"
        ).fetchall()
        
        recent_ad_copies = conn.execute(
            "SELECT id, product_name, headline, creation_date FROM ad_copies ORDER BY creation_date DESC LIMIT 5"
        ).fetchall()
        
        conn.close()
        
        return {
            "counts": {
                "images": image_count,
                "ad_copies": ad_copy_count,
                "integrated_ads": integrated_ad_count
            },
            "recent_images": [dict(img) for img in recent_images],
            "recent_ad_copies": [dict(ad) for ad in recent_ad_copies]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting database stats: {str(e)}")

@app.get("/ad-copies/recent", tags=["Database", "Ad Copy"])
async def get_recent_ad_copies(limit: int = 10):
    """Get recent ad copies from the database"""
    try:
        conn = get_db_connection()
        ad_copies = conn.execute(
            "SELECT * FROM ad_copies ORDER BY creation_date DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        result = []
        for ad in ad_copies:
            result.append(dict(ad))
        
        return {"ad_copies": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting recent ad copies: {str(e)}")

@app.get("/integrated-ads/recent", tags=["Database", "Integrated Ads"])
async def get_recent_integrated_ads(limit: int = 10):
    """Get recent integrated ads from the database"""
    try:
        conn = get_db_connection()
        integrated_ads = conn.execute(
            "SELECT ia.*, ac.headline, ac.primary_text, ac.description, " +
            "i.static_path as image_path, i.prompt as image_prompt " +
            "FROM integrated_ads ia " +
            "LEFT JOIN ad_copies ac ON ia.ad_copy_id = ac.id " +
            "LEFT JOIN images i ON ia.image_id = i.id " +
            "ORDER BY ia.creation_date DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        result = []
        for ad in integrated_ads:
            result.append(dict(ad))
        
        return {"integrated_ads": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting recent integrated ads: {str(e)}")

# Add a simplified brand profile creation endpoint that accepts form data
@app.post("/create-brand-profile", tags=["Brand Profiles"])
async def create_brand_profile_form(
    brand_name: str = Form(...),
    industry: str = Form(None),
    description: str = Form(...),
    tone_of_voice: str = Form(...),
    values: str = Form(...),  # Comma-separated values
    target_audience: str = Form(...),
    visual_identity: str = Form(...),
    color_palette: str = Form(None),
    do_guidelines: str = Form(None),  # Comma-separated guidelines
    dont_guidelines: str = Form(None),  # Comma-separated guidelines
    slogan: str = Form(None),
    hashtags: str = Form(None),  # Comma-separated hashtags
    examples: str = Form(None)
):
    """Create a brand profile using form data for easier submission"""
    try:
        # Parse comma-separated values into lists
        values_list = [v.strip() for v in values.split(',')] if values else []
        do_list = [do.strip() for do in do_guidelines.split(',')] if do_guidelines else None
        dont_list = [dont.strip() for dont in dont_guidelines.split(',')] if dont_guidelines else None
        hashtags_list = [tag.strip() for tag in hashtags.split(',')] if hashtags else None
        
        # Create profile request
        profile = BrandProfileCreate(
            brand_name=brand_name,
            industry=industry,
            description=description,
            tone_of_voice=tone_of_voice,
            values=values_list,
            target_audience=target_audience,
            visual_identity=visual_identity,
            color_palette=color_palette,
            do_guidelines=do_list,
            dont_guidelines=dont_list,
            slogan=slogan,
            hashtags=hashtags_list,
            examples=examples
        )
        
        # Create the profile
        profile_id = create_brand_profile(profile)
        
        # Return the created profile
        return get_brand_profile(profile_id)
    except Exception as e:
        print(f"Error creating brand profile via form: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create brand profile: {str(e)}")

# Add a helpful endpoint to check database initialization status
@app.get("/db/check", tags=["Database"])
async def check_database():
    """Check if the database is properly initialized and return table information"""
    try:
        conn = get_db_connection()
        # Get all tables
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        
        # Get column info for each table
        schema_info = {}
        for table in tables:
            table_name = table[0]
            columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            schema_info[table_name] = [
                {"name": col[1], "type": col[2], "notnull": bool(col[3])} 
                for col in columns
            ]
        
        # Get row counts
        counts = {}
        for table in tables:
            table_name = table[0]
            count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            counts[table_name] = count
        
        conn.close()
        
        return {
            "status": "ok",
            "tables": [table[0] for table in tables],
            "schema": schema_info,
            "row_counts": counts
        }
    except Exception as e:
        print(f"Error checking database: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

# Add a test endpoint to verify brand profile functionality
@app.post("/brand-profiles/test", tags=["Brand Profiles"])
async def test_brand_profile():
    """Create a test brand profile to verify functionality"""
    try:
        # Create a simple test profile
        profile = BrandProfileCreate(
            brand_name="Test Brand",
            description="This is a test brand profile",
            tone_of_voice="Professional",
            values=["Quality", "Innovation", "Customer Focus"],
            target_audience="Business professionals aged 25-45",
            visual_identity="Modern, clean design with blue and gray color scheme",
            color_palette="#1a73e8, #f5f5f5, #4285f4",
            do_guidelines=["Use professional language", "Focus on benefits", "Include brand colors"],
            dont_guidelines=["Don't use slang", "Avoid negative messaging"],
            slogan="Innovate. Create. Succeed.",
            hashtags=["#TestBrand", "#Innovation"],
            examples="Sample ads using professional tone and highlighting product benefits."
        )
        
        # Create profile and get ID
        profile_id = create_brand_profile(profile)
        
        # Fetch the created profile to verify it worked
        created_profile = get_brand_profile(profile_id)
        
        return {
            "status": "success",
            "message": "Test brand profile created successfully",
            "profile_id": profile_id,
            "profile": created_profile
        }
    except Exception as e:
        print(f"Error in test brand profile: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to create test brand profile: {str(e)}"
        }

# Add a database reset endpoint for development
@app.post("/db/reset", tags=["Database"])
async def reset_database():
    """⚠️ WARNING: This deletes and recreates the database schema. FOR DEVELOPMENT USE ONLY ⚠️"""
    try:
        # Close any existing connections
        conn = get_db_connection()
        conn.close()
        
        # Delete the database file
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        
        # Initialize the database again
        init_db()
        
        return {
            "status": "success",
            "message": "Database reset successfully. All tables have been recreated."
        }
    except Exception as e:
        print(f"Error resetting database: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to reset database: {str(e)}"
        }

# Competitor Ad Endpoints
@app.post("/competitor-ads", tags=["Competitor Analysis"])
async def upload_competitor_ad(
    competitor_name: str = Form(...),
    product_category: str = Form(...),
    target_audience: str = Form(None),
    file: UploadFile = File(...)
):
    """Upload a competitor's ad image for analysis"""
    try:
        # Validate file is an image
        content_type = file.content_type
        if not content_type.startswith("image/"):
            raise HTTPException(
                status_code=400, 
                detail="File must be an image (jpeg, png, etc.)"
            )
        
        # Save the competitor ad
        competitor_ad_id = save_competitor_ad(
            file, competitor_name, product_category, target_audience
        )
        
        # Automatically analyze the ad when it's uploaded
        analysis_result = analyze_competitor_ad(competitor_ad_id)
        
        # Return the analysis result instead of just the ad data
        return analysis_result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading competitor ad: {str(e)}"
        )

@app.get("/competitor-ads", tags=["Competitor Analysis"])
async def list_competitor_ads_endpoint(
    limit: int = 20, 
    offset: int = 0,
    product_category: str = None
):
    """List competitor ads with optional filtering by product category"""
    return list_competitor_ads(limit, offset, product_category)

@app.get("/competitor-ads/{competitor_ad_id}", tags=["Competitor Analysis"])
async def get_competitor_ad_endpoint(competitor_ad_id: str):
    """Get a specific competitor ad by ID"""
    return get_competitor_ad(competitor_ad_id)

@app.post("/competitor-ads/{competitor_ad_id}/analyze", tags=["Competitor Analysis"])
async def analyze_competitor_ad_endpoint(competitor_ad_id: str):
    """Analyze a competitor ad for positioning, typography, and visual elements"""
    return analyze_competitor_ad(competitor_ad_id)

@app.delete("/competitor-ads/{competitor_ad_id}", tags=["Competitor Analysis"])
async def delete_competitor_ad(competitor_ad_id: str):
    """Delete a competitor ad"""
    try:
        conn = get_db_connection()
        
        # Get the ad to check it exists and to get the image path
        ad = conn.execute(
            "SELECT * FROM competitor_ads WHERE id = ?",
            (competitor_ad_id,)
        ).fetchone()
        
        if not ad:
            conn.close()
            raise HTTPException(status_code=404, detail="Competitor ad not found")
        
        ad = dict(ad)
        
        # Delete from database
        conn.execute(
            "DELETE FROM competitor_ads WHERE id = ?",
            (competitor_ad_id,)
        )
        conn.commit()
        conn.close()
        
        # Try to delete the image file if it exists
        try:
            image_path = os.path.join(STATIC_DIR, os.path.basename(ad["ad_image_path"]))
            if os.path.exists(image_path):
                os.remove(image_path)
        except:
            # Continue even if file deletion fails
            pass
        
        return {"success": True, "message": "Competitor ad deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting competitor ad: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete competitor ad: {str(e)}")

# Add these functions to handle batch uploads and retrieving exemplary ads

def get_exemplary_competitor_ads(category: str = None, limit: int = 10, offset: int = 0) -> List[dict]:
    """Get high-performing competitor ads (those marked as exemplary)"""
    try:
        conn = get_db_connection()
        
        if category:
            # Filter by category if provided
            ads = conn.execute(
                """SELECT * FROM competitor_ads 
                WHERE is_exemplary = 1 AND product_category = ? 
                ORDER BY effectiveness_score DESC LIMIT ? OFFSET ?""",
                (category, limit, offset)
            ).fetchall()
        else:
            # Get all exemplary ads across categories
            ads = conn.execute(
                """SELECT * FROM competitor_ads 
                WHERE is_exemplary = 1 
                ORDER BY effectiveness_score DESC LIMIT ? OFFSET ?""",
                (limit, offset)
            ).fetchall()
        
        conn.close()
        
        result = []
        for ad in ads:
            ad_dict = dict(ad)
            
            # Parse JSON fields
            if ad_dict["visual_elements"]:
                try:
                    ad_dict["visual_elements"] = json.loads(ad_dict["visual_elements"])
                except:
                    ad_dict["visual_elements"] = []
            else:
                ad_dict["visual_elements"] = []
            
            result.append(ad_dict)
        
        return result
    except Exception as e:
        print(f"Error getting exemplary competitor ads: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get exemplary competitor ads: {str(e)}")

def get_competitor_insights_summary() -> dict:
    """Get a summary of insights from exemplary ads"""
    try:
        # Connect to database
        conn = get_db_connection()
        
        # Get counts
        total_ads = conn.execute("SELECT COUNT(*) FROM competitor_ads").fetchone()[0]
        exemplary_ads = conn.execute("SELECT COUNT(*) FROM competitor_ads WHERE is_exemplary = 1").fetchone()[0]
        
        # Get average effectiveness score
        avg_score = conn.execute("SELECT AVG(effectiveness_score) FROM competitor_ads").fetchone()[0]
        
        # Get top categories
        categories = conn.execute(
            "SELECT product_category, COUNT(*) as count FROM competitor_ads GROUP BY product_category ORDER BY count DESC LIMIT 5"
        ).fetchall()
        
        # Get top competitors
        competitors = conn.execute(
            "SELECT competitor_name, COUNT(*) as count FROM competitor_ads GROUP BY competitor_name ORDER BY count DESC LIMIT 5"
        ).fetchall()
        
        # Get most common visual elements from exemplary ads
        # This is a bit tricky since visual_elements is stored as JSON
        exemplary_ads_data = conn.execute(
            "SELECT visual_elements FROM competitor_ads WHERE is_exemplary = 1"
        ).fetchall()
        
        # Process visual elements 
        element_counts = {}
        for ad in exemplary_ads_data:
            if ad[0]:  # Check if visual_elements is not None
                try:
                    elements = json.loads(ad[0])
                    for element in elements:
                        # Count the occurrences of keywords
                        for keyword in ["people", "person", "product", "text", "background", "color", "logo"]:
                            if keyword in element.lower():
                                element_counts[keyword] = element_counts.get(keyword, 0) + 1
                except json.JSONDecodeError:
                    # Skip if we can't parse the JSON
                    pass
        
        # Sort element_counts by value (count)
        sorted_elements = sorted(element_counts.items(), key=lambda x: x[1], reverse=True)
        
        conn.close()
        
        return {
            "total_ads": total_ads,
            "exemplary_ads": exemplary_ads,
            "avg_effectiveness_score": avg_score if avg_score else 0,
            "top_categories": [{"category": cat[0], "count": cat[1]} for cat in categories],
            "top_competitors": [{"name": comp[0], "count": comp[1]} for comp in competitors],
            "common_visual_elements": [{"element": elem[0], "occurrences": elem[1]} for elem in sorted_elements[:5]]
        }
    except Exception as e:
        print(f"Error getting competitor insights summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get competitor insights summary: {str(e)}")

# Add these API endpoints
@app.get("/competitor-ads/exemplary", tags=["Competitor Analysis"])
async def get_exemplary_ads_endpoint(
    category: str = None,
    limit: int = 10, 
    offset: int = 0
):
    """Get high-performing competitor ads (with effectiveness score >= 8)"""
    return get_exemplary_competitor_ads(category, limit, offset)

@app.get("/competitor-ads/insights", tags=["Competitor Analysis"])
async def get_competitor_insights():
    """Get aggregated insights from all analyzed competitor ads"""
    return get_competitor_insights_summary()

@app.post("/competitor-ads/batch", tags=["Competitor Analysis"])
async def batch_upload_competitor_ads(
    competitor_name: str = Form(...),
    product_category: str = Form(...),
    target_audience: str = Form(None),
    files: List[UploadFile] = File(...)
):
    """Upload and analyze multiple competitor ad images at once"""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided for upload")
    
    results = []
    errors = []
    
    for file in files:
        try:
            # Validate file is an image
            content_type = file.content_type
            if not content_type.startswith("image/"):
                errors.append({
                    "filename": file.filename,
                    "error": "File must be an image (jpeg, png, etc.)"
                })
                continue
            
            # Save and analyze the competitor ad
            competitor_ad_id = save_competitor_ad(
                file, competitor_name, product_category, target_audience
            )
            
            # Analyze the ad
            analysis_result = analyze_competitor_ad(competitor_ad_id)
            results.append(analysis_result)
            
        except Exception as e:
            errors.append({
                "filename": file.filename,
                "error": str(e)
            })
    
    # Return batch results
    return {
        "success": len(results),
        "errors": len(errors),
        "results": results,
        "error_details": errors
    }

@app.put("/competitor-ads/{competitor_ad_id}/exemplary", tags=["Competitor Analysis"])
async def mark_ad_exemplary(competitor_ad_id: str, is_exemplary: bool = True):
    """Manually mark or unmark an ad as exemplary"""
    try:
        conn = get_db_connection()
        
        # Check if ad exists
        ad = conn.execute(
            "SELECT id FROM competitor_ads WHERE id = ?",
            (competitor_ad_id,)
        ).fetchone()
        
        if not ad:
            conn.close()
            raise HTTPException(status_code=404, detail="Competitor ad not found")
        
        # Update is_exemplary status
        conn.execute(
            "UPDATE competitor_ads SET is_exemplary = ? WHERE id = ?",
            (1 if is_exemplary else 0, competitor_ad_id)
        )
        conn.commit()
        conn.close()
        
        return {
            "id": competitor_ad_id,
            "is_exemplary": is_exemplary
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating exemplary status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update exemplary status: {str(e)}")

# Add new models for video generation
class VideoGenerationRequest(BaseModel):
    prompt: str
    height: Optional[str] = "1080"
    width: Optional[str] = "1080"
    n_seconds: Optional[str] = "5"
    n_variants: Optional[str] = "1"

class VideoGenerationResponse(BaseModel):
    job_id: str
    status: str
    video_path: Optional[str] = None
    error: Optional[str] = None

class VideoGenerationStatus(BaseModel):
    job_id: str
    status: str
    progress: Optional[float] = None
    video_path: Optional[str] = None
    error: Optional[str] = None

# Add video generation functions
def save_video_job(job_id: str, prompt: str, status: str = "pending", error: str = None) -> None:
    """Save or update a video job in the database"""
    try:
        print(f"\nSaving video job to database:")
        print(f"Job ID: {job_id}")
        print(f"Status: {status}")
        print(f"Error: {error}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if job already exists
        cursor.execute("SELECT job_id FROM video_jobs WHERE job_id = ?", (job_id,))
        existing_job = cursor.fetchone()
        
        if existing_job:
            print(f"Updating existing job in database")
            cursor.execute("""
                UPDATE video_jobs 
                SET status = ?, error = ?, updated_at = ?
                WHERE job_id = ?
            """, (status, error, datetime.datetime.now(), job_id))
        else:
            print(f"Creating new job in database")
            cursor.execute("""
                INSERT INTO video_jobs (job_id, prompt, status, error, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (job_id, prompt, status, error, datetime.datetime.now()))
        
        conn.commit()
        print("Database update successful")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def get_video_job(job_id: str) -> dict:
    """Get a video job from the database"""
    try:
        print(f"\nRetrieving video job from database:")
        print(f"Job ID: {job_id}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM video_jobs 
            WHERE job_id = ?
        """, (job_id,))
        
        job = cursor.fetchone()
        if job:
            print(f"Found job in database: {dict(job)}")
            return dict(job)
        else:
            print(f"No job found with ID: {job_id}")
            return None
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def generate_video_from_prompt(prompt: str, height: str = "1080", width: str = "1080", n_seconds: str = "5", n_variants: str = "1") -> dict:
    try:
        print(f"\nGenerating video with prompt: {prompt}")
        print(f"Parameters: height={height}, width={width}, n_seconds={n_seconds}, n_variants={n_variants}")
        
        headers = {
            "api-key": AZURE_SORA_KEY,
            "Content-Type": "application/json"
        }
        
        data = {
            "model": SORA_DEPLOYMENT,
            "prompt": prompt,
            "height": height,
            "width": width,
            "n_seconds": n_seconds,
            "n_variants": n_variants
        }
        
        print(f"Making request to: {AZURE_SORA_ENDPOINT}")
        print(f"Request data: {data}")
        
        response = requests.post(AZURE_SORA_ENDPOINT, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        print(f"API Response: {result}")
        
        job_id = result.get("id")
        if not job_id:
            raise Exception("No job ID received from API")
            
        print(f"Job ID received: {job_id}")
        
        return {
            "job_id": job_id,
            "status": "pending",
            "video_path": None,
            "error": None
        }
        
    except Exception as e:
        print(f"Error generating video: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Video generation failed: {str(e)}")

def check_video_generation_status(job_id: str) -> dict:
    try:
        print(f"\nChecking status for job: {job_id}")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Generated videos directory: {GENERATED_VIDEOS_DIR}")
        
        # Ensure directory exists
        os.makedirs(GENERATED_VIDEOS_DIR, exist_ok=True)
        print(f"Directory permissions: {oct(os.stat(GENERATED_VIDEOS_DIR).st_mode)[-3:]}")
        
        # Make the API request to check status
        headers = {
            "api-key": AZURE_SORA_KEY
        }
        
        # Use the correct endpoint format for status check
        status_url = f"https://ai-anuragkambojmat219855ai956965945200.openai.azure.com/openai/v1/video/generations/jobs/{job_id}?api-version=preview"
        print(f"Checking status at: {status_url}")
        
        response = requests.get(status_url, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        print(f"API Response: {result}")  # Log full response
        status = result.get("status", "unknown")
        print(f"Current status from API: {status}")
        
        if status == "succeeded":
            # Get the video URL from the response
            video_url = result.get("output", {}).get("video_url")
            if not video_url:
                # Try alternative response structure
                generations = result.get("generations", [])
                if generations and len(generations) > 0:
                    generation_id = generations[0].get("id")
                    if generation_id:
                        # Use the correct endpoint format from Azure OpenAI documentation
                        video_endpoint = f"https://ai-anuragkambojmat219855ai956965945200.openai.azure.com/openai/v1/video/generations/{generation_id}/content/video?api-version=preview"
                        print(f"Getting video from: {video_endpoint}")
                        
                        video_response = requests.get(video_endpoint, headers=headers)
                        video_response.raise_for_status()
                        
                        # Check if this is a direct video download
                        content_type = video_response.headers.get('content-type', '')
                        if 'video' in content_type or 'application/octet-stream' in content_type:
                            print(f"Found direct video content")
                            # This is the video file itself, save it directly
                            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                            unique_id = str(uuid.uuid4())[:8]
                            video_filename = f"video_{timestamp}_{unique_id}.mp4"
                            video_path = os.path.join(GENERATED_VIDEOS_DIR, video_filename)
                            
                            print(f"Saving video to: {video_path}")
                            with open(video_path, "wb") as f:
                                f.write(video_response.content)
                            
                            file_size = os.path.getsize(video_path)
                            print(f"Video saved successfully: {file_size} bytes")
                            
                            return {
                                "job_id": job_id,
                                "status": "succeeded",
                                "video_path": f"/generated_videos/{video_filename}",
                                "error": None
                            }
                        else:
                            print(f"Unexpected content type: {content_type}")
                            raise HTTPException(status_code=500, detail=f"Unexpected content type: {content_type}")
            else:
                print("No video URL found in the response")
                print(f"Full response: {result}")
                raise HTTPException(status_code=500, detail="No video URL in response")
        else:
            print(f"Job still in progress. Status: {status}")
            return {
                "job_id": job_id,
                "status": status,
                "video_path": None,
                "error": None
            }
        
    except Exception as e:
        print(f"Error checking video status: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to check video status: {str(e)}")

# Add new endpoints for video generation
@app.post("/generate-video", response_model=VideoGenerationResponse, tags=["Videos"])
async def generate_video(request: VideoGenerationRequest):
    """Generate a video using Sora"""
    try:
        result = generate_video_from_prompt(
            prompt=request.prompt,
            height=request.height,
            width=request.width,
            n_seconds=request.n_seconds,
            n_variants=request.n_variants
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error generating video: {str(e)}"
        )

@app.get("/video-status/{job_id}", response_model=VideoGenerationStatus, tags=["Videos"])
async def get_video_status(job_id: str):
    """Check the status of a video generation job"""
    try:
        result = check_video_generation_status(job_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error checking video status: {str(e)}"
        )

@app.get("/debug-video-status/{job_id}", tags=["Videos"])
async def debug_video_status(job_id: str):
    """Debug endpoint to see raw API response"""
    try:
        headers = {
            "api-key": AZURE_SORA_KEY
        }
        
        status_url = f"https://ai-anuragkambojmat219855ai956965945200.openai.azure.com/openai/v1/video/generations/jobs/{job_id}?api-version=preview"
        print(f"Checking status at: {status_url}")
        
        response = requests.get(status_url, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error checking video status: {str(e)}"
        )

@app.get("/download-video/{generation_id}", tags=["Videos"])
async def download_video_direct(generation_id: str):
    """Debug endpoint to download video directly using generation ID"""
    try:
        headers = {
            "api-key": AZURE_SORA_KEY
        }
        
        # Try different endpoint formats to get the video
        video_endpoints = [
            f"https://ai-anuragkambojmat219855ai956965945200.openai.azure.com/openai/v1/video/generations/{generation_id}/content/video?api-version=preview",
            f"https://ai-anuragkambojmat219855ai956965945200.openai.azure.com/openai/v1/video/generations/{generation_id}?api-version=preview",
            f"https://ai-anuragkambojmat219855ai956965945200.openai.azure.com/openai/v1/video/generations/{generation_id}/url?api-version=preview",
            f"https://ai-anuragkambojmat219855ai956965945200.openai.azure.com/openai/v1/video/generations/{generation_id}/content?api-version=preview"
        ]
        
        for endpoint in video_endpoints:
            try:
                print(f"Trying video endpoint: {endpoint}")
                video_response = requests.get(endpoint, headers=headers)
                
                # Check if this is a direct video download
                content_type = video_response.headers.get('content-type', '')
                content_length = video_response.headers.get('content-length', '0')
                
                print(f"Response status: {video_response.status_code}")
                print(f"Content-Type: {content_type}")
                print(f"Content-Length: {content_length}")
                
                if video_response.status_code == 200:
                    if 'video' in content_type or 'application/octet-stream' in content_type or int(content_length) > 1000000:
                        print(f"Found direct video content at: {endpoint}")
                        # This is the video file itself, save it directly
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        unique_id = str(uuid.uuid4())[:8]
                        video_filename = f"video_{timestamp}_{unique_id}.mp4"
                        video_path = os.path.join(GENERATED_VIDEOS_DIR, video_filename)
                        
                        print(f"Saving video directly to: {video_path}")
                        with open(video_path, "wb") as f:
                            f.write(video_response.content)
                        
                        file_size = os.path.getsize(video_path)
                        print(f"Video saved successfully: {file_size} bytes")
                        
                        return {
                            "success": True,
                            "video_path": f"/generated_videos/{video_filename}",
                            "file_size": file_size,
                            "endpoint_used": endpoint
                        }
                    else:
                        # Try to parse as JSON
                        try:
                            json_response = video_response.json()
                            return {
                                "endpoint": endpoint,
                                "status_code": video_response.status_code,
                                "content_type": content_type,
                                "response": json_response
                            }
                        except:
                            return {
                                "endpoint": endpoint,
                                "status_code": video_response.status_code,
                                "content_type": content_type,
                                "response": video_response.text[:500]
                            }
                
            except Exception as e:
                print(f"Failed endpoint {endpoint}: {str(e)}")
                continue
        
        return {"error": "No working endpoint found"}
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error downloading video: {str(e)}"
        )

@app.get("/video-jobs", tags=["Videos"])
async def get_all_video_jobs(limit: int = 50, offset: int = 0):
    """Get all video generation jobs with their status and details"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get total count for pagination info
        cursor.execute("SELECT COUNT(*) FROM video_jobs")
        total_count = cursor.fetchone()[0]
        
        # Get the jobs with pagination
        cursor.execute("""
            SELECT job_id, prompt, status, video_path, error, created_at, completed_at, updated_at
            FROM video_jobs 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        jobs = cursor.fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        result = []
        for job in jobs:
            job_dict = dict(job)
            result.append(job_dict)
        
        return {
            "total_jobs": total_count,
            "limit": limit,
            "offset": offset,
            "jobs": result
        }
        
    except Exception as e:
        print(f"Error getting video jobs: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to get video jobs: {str(e)}"
        )

@app.get("/video-jobs/ids", tags=["Videos"])
async def get_all_video_job_ids():
    """Get all video job IDs in a simple list format"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT job_id, status, created_at FROM video_jobs ORDER BY created_at DESC")
        jobs = cursor.fetchall()
        conn.close()
        
        # Return simplified list of job IDs with basic info
        job_ids = []
        for job in jobs:
            job_ids.append({
                "job_id": job[0],
                "status": job[1],
                "created_at": job[2]
            })
        
        return {
            "total_jobs": len(job_ids),
            "job_ids": job_ids
        }
        
    except Exception as e:
        print(f"Error getting video job IDs: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to get video job IDs: {str(e)}"
        )

@app.post("/generate-and-download-video", tags=["Videos"])
async def generate_and_download_video(request: VideoGenerationRequest):
    """Generate a video and automatically download it once ready"""
    import asyncio
    import time
    
    try:
        print(f"\nStarting video generation and auto-download for prompt: {request.prompt}")
        
        # Step 1: Generate the video
        result = generate_video_from_prompt(
            prompt=request.prompt,
            height=request.height,
            width=request.width,
            n_seconds=request.n_seconds,
            n_variants=request.n_variants
        )
        
        job_id = result["job_id"]
        print(f"Video generation started with job ID: {job_id}")
        
        # Step 2: Poll for completion and auto-download
        max_wait_time = 300  # 5 minutes maximum wait time
        check_interval = 10  # Check every 10 seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            try:
                print(f"Checking status for job {job_id}...")
                
                # Check the status
                headers = {
                    "api-key": AZURE_SORA_KEY
                }
                
                status_url = f"https://ai-anuragkambojmat219855ai956965945200.openai.azure.com/openai/v1/video/generations/jobs/{job_id}?api-version=preview"
                response = requests.get(status_url, headers=headers)
                response.raise_for_status()
                
                status_result = response.json()
                status = status_result.get("status", "unknown")
                print(f"Current status: {status}")
                
                if status == "succeeded":
                    print("Video generation completed! Starting download...")
                    
                    # Try to download the video
                    generations = status_result.get("generations", [])
                    if generations and len(generations) > 0:
                        generation_id = generations[0].get("id")
                        if generation_id:
                            # Use the correct endpoint format from Azure OpenAI documentation
                            video_endpoint = f"https://ai-anuragkambojmat219855ai956965945200.openai.azure.com/openai/v1/video/generations/{generation_id}/content/video?api-version=preview"
                            print(f"Downloading video from: {video_endpoint}")
                            
                            video_response = requests.get(video_endpoint, headers=headers)
                            video_response.raise_for_status()
                            
                            # Check if this is a direct video download
                            content_type = video_response.headers.get('content-type', '')
                            if 'video' in content_type or 'application/octet-stream' in content_type:
                                print(f"Found direct video content")
                                # This is the video file itself, save it directly
                                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                                unique_id = str(uuid.uuid4())[:8]
                                video_filename = f"video_{timestamp}_{unique_id}.mp4"
                                video_path = os.path.join(GENERATED_VIDEOS_DIR, video_filename)
                                
                                print(f"Saving video to: {video_path}")
                                with open(video_path, "wb") as f:
                                    f.write(video_response.content)
                                
                                file_size = os.path.getsize(video_path)
                                print(f"Video saved successfully: {file_size} bytes")
                                
                                return {
                                    "job_id": job_id,
                                    "status": "completed",
                                    "video_path": f"/generated_videos/{video_filename}",
                                    "file_size": file_size,
                                    "download_time": time.time() - start_time,
                                    "generation_id": generation_id,
                                    "message": "Video generated and downloaded successfully"
                                }
                            else:
                                print(f"Unexpected content type: {content_type}")
                                return {
                                    "job_id": job_id,
                                    "status": "error",
                                    "error": f"Unexpected content type: {content_type}",
                                    "response_preview": video_response.text[:200]
                                }
                    
                    return {
                        "job_id": job_id,
                        "status": "error",
                        "error": "No video content found in successful response"
                    }
                
                elif status == "failed":
                    error_msg = status_result.get("error", "Unknown error")
                    print(f"Video generation failed: {error_msg}")
                    return {
                        "job_id": job_id,
                        "status": "failed",
                        "error": error_msg
                    }
                
                else:
                    # Still processing, wait and check again
                    print(f"Still processing... waiting {check_interval} seconds")
                    await asyncio.sleep(check_interval)
                    continue
                    
            except Exception as e:
                print(f"Error during status check: {str(e)}")
                await asyncio.sleep(check_interval)
                continue
        
        # If we get here, we've timed out
        return {
            "job_id": job_id,
            "status": "timeout",
            "error": f"Video generation took longer than {max_wait_time} seconds",
            "message": "You can check the status manually using /video-status/{job_id}"
        }
        
    except Exception as e:
        print(f"Error in generate and download video: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error generating and downloading video: {str(e)}"
        )

# Add new models for video ad prompt generation
class VideoAdPromptRequest(BaseModel):
    product_name: str
    product_category: str = Field(..., description="Category of the product (e.g., 'smartphone', 'skincare', 'fitness equipment')")
    target_audience: str = Field(..., description="Target audience description")
    key_benefits: List[str] = Field(..., description="Key product benefits to highlight")
    ad_style: Optional[str] = Field("cinematic", description="Style of the video ad (cinematic, lifestyle, product demo, testimonial)")
    tone: Optional[str] = Field("professional", description="Tone of the ad (professional, casual, energetic, luxurious)")
    duration_preference: Optional[str] = Field("5", description="Preferred video duration in seconds")
    setting: Optional[str] = Field(None, description="Preferred setting/environment for the video")
    brand_profile_id: Optional[str] = Field(None, description="Brand profile ID for brand-specific guidelines")

class VideoAdPromptResponse(BaseModel):
    optimized_prompt: str
    style_description: str
    technical_specs: dict
    alternative_prompts: List[str]
    estimated_duration: str

# TTS Configuration
AZURE_TTS_KEY = os.getenv("AZURE_TTS_KEY")
AZURE_TTS_ENDPOINT = os.getenv("AZURE_TTS_ENDPOINT")

# Create directories for audio files
GENERATED_AUDIO_DIR = os.path.join(os.getcwd(), "generated_audio")
os.makedirs(GENERATED_AUDIO_DIR, exist_ok=True)

# Add new models for TTS and ad script generation
class AdScriptRequest(BaseModel):
    product_name: str
    product_category: str = Field(..., description="Category of the product")
    target_audience: str = Field(..., description="Target audience description")
    key_benefits: List[str] = Field(..., description="Key product benefits to highlight")
    script_type: Optional[str] = Field("commercial", description="Type of script (commercial, explainer, testimonial, problem-solution)")
    tone: Optional[str] = Field("professional", description="Tone of the script (professional, casual, energetic, conversational)")
    duration_seconds: Optional[int] = Field(15, description="Target duration in seconds (determines script length)")
    call_to_action: Optional[str] = Field("Learn more", description="Specific call to action")
    brand_profile_id: Optional[str] = Field(None, description="Brand profile ID for brand-specific guidelines")

class AdScriptResponse(BaseModel):
    script_text: str
    word_count: int
    estimated_duration: str
    script_breakdown: dict
    alternative_scripts: List[str]

class TTSRequest(BaseModel):
    text: str = Field(..., description="Text to convert to speech")
    voice: Optional[str] = Field("alloy", description="Voice to use (alloy, echo, fable, onyx, nova, shimmer)")
    model: Optional[str] = Field("tts-1", description="TTS model to use (tts-1, tts-1-hd)")
    speed: Optional[float] = Field(1.0, description="Speech speed (0.25 to 4.0)", ge=0.25, le=4.0)
    response_format: Optional[str] = Field("mp3", description="Audio format (mp3, opus, aac, flac)")

class TTSResponse(BaseModel):
    audio_path: str
    file_size: int
    duration_estimate: str
    voice_used: str
    text_length: int

class AdScriptToSpeechRequest(BaseModel):
    product_name: str
    product_category: str = Field(..., description="Category of the product")
    target_audience: str = Field(..., description="Target audience description")
    key_benefits: List[str] = Field(..., description="Key product benefits to highlight")
    script_type: Optional[str] = Field("commercial", description="Type of script")
    tone: Optional[str] = Field("professional", description="Tone of the script")
    duration_seconds: Optional[int] = Field(15, description="Target duration in seconds")
    call_to_action: Optional[str] = Field("Learn more", description="Call to action")
    voice: Optional[str] = Field("alloy", description="Voice to use for TTS")
    speed: Optional[float] = Field(1.0, description="Speech speed", ge=0.25, le=4.0)
    brand_profile_id: Optional[str] = Field(None, description="Brand profile ID")

class AdScriptToSpeechResponse(BaseModel):
    script_details: AdScriptResponse
    audio_details: TTSResponse
    message: str

def generate_video_ad_prompt(request: VideoAdPromptRequest) -> VideoAdPromptResponse:
    """Generate an optimized video prompt for ad creation based on product information"""
    try:
        # Format benefits for the prompt
        benefits_text = "\n".join([f"- {benefit}" for benefit in request.key_benefits])
        
        # Add brand guidelines if provided
        brand_guidelines = ""
        if request.brand_profile_id:
            brand_guidelines = get_brand_guidelines_for_prompt(request.brand_profile_id)
        
        # Determine optimal duration for social media campaigns
        suggested_duration = "15"  # Default to 15 seconds for social media
        if request.duration_preference:
            user_duration = int(request.duration_preference)
            if user_duration < 6:
                suggested_duration = "15"  # Minimum for effective social media ads
            elif user_duration > 60:
                suggested_duration = "30"  # Maximum for attention span
            else:
                suggested_duration = str(max(15, user_duration))  # At least 15 seconds
        
        # Create the chat prompt for GPT-4
        chat_prompt = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": """You are an expert Facebook and Instagram video advertising creative director with 15+ years of experience creating viral, high-converting social media video ads for major brands. You specialize in crafting specific, detailed video prompts optimized for Facebook and Instagram campaigns.

Your video prompts should be:
1. SOCIAL MEDIA OPTIMIZED: Hook viewers in first 3 seconds with compelling visuals
2. PLATFORM SPECIFIC: Perfect for Facebook/Instagram feed, stories, and reels
3. CONVERSION FOCUSED: Clear call-to-action, benefit-driven messaging
4. TECHNICALLY PRECISE: Include camera angles, lighting, pacing for AI video generation
5. ENGAGEMENT DRIVEN: Designed to stop scrolling and drive action

Key Requirements:
- Hook within first 3 seconds (use movement, contrast, or surprising visuals)
- Standard video format (16:9 or 1:1 aspect ratio)
- Clear product demonstration and benefits
- Strong visual storytelling without relying on audio
- Include text overlay suggestions for key messages
- Design for 15-30 second optimal duration for social media attention spans
- Consider platform algorithms (engagement, watch time, shares)
- DO NOT frame the ad as being shown on a mobile device - create the actual ad content directly

Always provide multiple creative alternatives optimized for different campaign objectives (awareness, consideration, conversion)."""
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""Create an optimized Facebook/Instagram video ad prompt for AI video generation:

Product Information:
- Product Name: {request.product_name}
- Category: {request.product_category}
- Target Audience: {request.target_audience}
- Key Benefits:
{benefits_text}
- Preferred Ad Style: {request.ad_style}
- Tone: {request.tone}
- Campaign Duration: {suggested_duration} seconds (optimized for social media)
- Setting: {request.setting or 'Choose optimal setting for social media engagement'}
{brand_guidelines}

SPECIFIC REQUIREMENTS FOR FACEBOOK/INSTAGRAM:
1. Create ONE primary optimized video prompt (detailed, specific, ready for Sora)
2. MUST include a 3-second hook that stops scrolling
3. Use standard video format (16:9 or 1:1 aspect ratio)
4. Include visual storytelling that works without sound
5. Suggest text overlay placements for key messages
6. Optimize for {suggested_duration}-second duration
7. Include clear product demonstration and call-to-action
8. DO NOT frame the ad as being shown on a mobile device - create the actual ad content directly
9. Generate 3 alternative variations for different campaign objectives:
   - Version A: Brand Awareness (emotional connection)
   - Version B: Product Consideration (feature demonstration)  
   - Version C: Direct Response (urgency and conversion)

The primary prompt should be a detailed paragraph for AI video generation. Focus on:
- Opening hook that grabs attention immediately
- Product benefits shown visually
- Social media engagement elements
- Clear progression from hook → demonstration → call-to-action
- Professional visual composition with high production value

Make it specifically designed for Facebook/Instagram campaign success."""
                    }
                ]
            }
        ]
        
        # Generate completion using GPT-4
        completion = gpt_client.chat.completions.create(
            model=GPT_DEPLOYMENT,
            messages=chat_prompt,
            max_tokens=2000,  # Increased for more detailed social media optimization
            temperature=0.7,
            top_p=0.95
        )
        
        # Extract the response
        response_text = completion.choices[0].message.content
        
        # Parse the response with improved parsing for social media content
        lines = response_text.split('\n')
        
        optimized_prompt = ""
        style_description = ""
        technical_specs = {}
        alternative_prompts = []
        estimated_duration = suggested_duration
        
        current_section = ""
        temp_alternatives = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Identify sections
            if "primary prompt" in line.lower() or "main prompt" in line.lower() or "optimized prompt" in line.lower():
                current_section = "prompt"
                continue
            elif "style" in line.lower() and ("approach" in line.lower() or "description" in line.lower()):
                current_section = "style"
                continue
            elif "technical" in line.lower() or "specifications" in line.lower():
                current_section = "technical"
                continue
            elif ("alternative" in line.lower() and "variation" in line.lower()) or "version" in line.lower():
                current_section = "alternatives"
                continue
            elif "duration" in line.lower() or "timing" in line.lower():
                current_section = "duration"
                continue
            
            # Extract content based on current section
            if current_section == "prompt" and len(line) > 50 and not line.startswith(("1.", "2.", "3.", "-", "*")):
                if not optimized_prompt:  # Take the first substantial prompt
                    optimized_prompt = line
            elif current_section == "style":
                style_description += line + " "
            elif current_section == "technical":
                if ":" in line:
                    key, value = line.split(":", 1)
                    technical_specs[key.strip()] = value.strip()
                else:
                    technical_specs["social_media_optimization"] = technical_specs.get("social_media_optimization", "") + line + " "
            elif current_section == "alternatives" and len(line) > 30:
                # Look for version patterns and extract alternatives
                if "version a" in line.lower() or "brand awareness" in line.lower():
                    clean_line = re.sub(r'^[^\:]*:', '', line).strip()
                    if clean_line and len(clean_line) > 20:
                        temp_alternatives.append(clean_line)
                elif "version b" in line.lower() or "consideration" in line.lower():
                    clean_line = re.sub(r'^[^\:]*:', '', line).strip()
                    if clean_line and len(clean_line) > 20:
                        temp_alternatives.append(clean_line)
                elif "version c" in line.lower() or "direct response" in line.lower() or "conversion" in line.lower():
                    clean_line = re.sub(r'^[^\:]*:', '', line).strip()
                    if clean_line and len(clean_line) > 20:
                        temp_alternatives.append(clean_line)
                else:
                    # General alternative parsing
                    clean_line = re.sub(r'^[\d\.\-\*\s]+', '', line)
                    if clean_line and len(clean_line) > 30:
                        temp_alternatives.append(clean_line)
        
        # Set alternative prompts
        alternative_prompts = temp_alternatives[:3] if temp_alternatives else []
        
        # Fallback values optimized for Facebook/Instagram
        if not optimized_prompt:
            hook_element = "Quick zoom-in on product" if request.ad_style == "product demo" else "Split-screen transformation"
            optimized_prompt = f"HOOK (0-3s): {hook_element} with bold text overlay '{request.product_name}'. DEMONSTRATION (3-12s): {request.ad_style} showcase of {request.product_name} highlighting {', '.join(request.key_benefits[:2]) if request.key_benefits else 'key benefits'} with smooth transitions and professional framing. CALL-TO-ACTION (12-{suggested_duration}s): Product close-up with 'Shop Now' text overlay and brand logo, {request.tone} tone throughout."
        
        if not style_description:
            style_description = f"Facebook/Instagram optimized {request.ad_style} video with {request.tone} tone. Professional quality with strong 3-second hook, visual storytelling, and clear call-to-action. Optimized for {suggested_duration}-second social media attention span."
        
        if not technical_specs:
            technical_specs = {
                "aspect_ratio": "16:9 or 1:1 (standard video format)",
                "hook_timing": "0-3 seconds with high visual impact",
                "camera_movement": "Dynamic but smooth with professional quality",
                "lighting": "High contrast, bright and engaging",
                "pacing": "Fast-paced with clear visual progression",
                "text_overlays": "Bold, readable text for key messages",
                "platform": "Facebook/Instagram feed and stories optimized",
                "duration_breakdown": f"Hook (3s) + Demo ({int(suggested_duration)-5}s) + CTA (2s)"
            }
        
        if not alternative_prompts:
            alternative_prompts = [
                f"BRAND AWARENESS: Professional quality lifestyle montage showing {request.target_audience} using {request.product_name} in aspirational settings, {request.tone} music and smooth transitions",
                f"PRODUCT DEMO: High-quality step-by-step demonstration of {request.product_name} key features with before/after comparisons and benefit callouts",
                f"DIRECT RESPONSE: Professional urgent problem-solution format starting with pain point, quick product demo, customer testimonials, and strong 'Limited Time' call-to-action"
            ]
        
        return VideoAdPromptResponse(
            optimized_prompt=optimized_prompt.strip(),
            style_description=style_description.strip(),
            technical_specs=technical_specs,
            alternative_prompts=alternative_prompts[:3],
            estimated_duration=f"{suggested_duration} seconds (social media optimized)"
        )
        
    except Exception as e:
        print(f"Error generating video ad prompt: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to generate video ad prompt: {str(e)}"
        )

@app.post("/generate-video-ad-prompt", response_model=VideoAdPromptResponse, tags=["Videos"])
async def generate_video_ad_prompt_endpoint(request: VideoAdPromptRequest):
    """Generate an optimized video prompt for ad creation based on basic product information"""
    try:
        return generate_video_ad_prompt(request)
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error generating video ad prompt: {str(e)}"
        )

@app.post("/create-video-ad", tags=["Videos"])
async def create_complete_video_ad(
    product_name: str = Form(...),
    product_category: str = Form(...),
    target_audience: str = Form(...),
    key_benefits: str = Form(...),  # Comma-separated
    ad_style: str = Form("cinematic"),
    tone: str = Form("professional"),
    duration_preference: str = Form("5"),
    setting: str = Form(None),
    brand_profile_id: str = Form(None),
    auto_generate_video: bool = Form(True)
):
    """Create a complete video ad: generate optimized prompt, then create the video"""
    try:
        # Parse key benefits from comma-separated string
        benefits_list = [benefit.strip() for benefit in key_benefits.split(',')]
        
        # Step 1: Generate optimized prompt
        prompt_request = VideoAdPromptRequest(
            product_name=product_name,
            product_category=product_category,
            target_audience=target_audience,
            key_benefits=benefits_list,
            ad_style=ad_style,
            tone=tone,
            duration_preference=duration_preference,
            setting=setting,
            brand_profile_id=brand_profile_id
        )
        
        prompt_response = generate_video_ad_prompt(prompt_request)
        
        # Step 2: Generate video if requested
        video_result = None
        if auto_generate_video:
            video_request = VideoGenerationRequest(
                prompt=prompt_response.optimized_prompt,
                height="1080",
                width="1080",
                n_seconds=duration_preference,
                n_variants="1"
            )
            
            # Use the auto-download functionality
            video_result = await generate_and_download_video(video_request)
        
        return {
            "prompt_details": prompt_response.model_dump(),
            "video_result": video_result,
            "message": "Video ad created successfully" if auto_generate_video else "Video prompt generated successfully"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error creating video ad: {str(e)}"
        )

# TTS Functions
def generate_ad_script(request: AdScriptRequest) -> AdScriptResponse:
    """Generate an ad script based on product information"""
    try:
        # Format benefits for the prompt
        benefits_text = "\n".join([f"- {benefit}" for benefit in request.key_benefits])
        
        # Add brand guidelines if provided
        brand_guidelines = ""
        if request.brand_profile_id:
            brand_guidelines = get_brand_guidelines_for_prompt(request.brand_profile_id)
        
        # Calculate target word count based on duration (average 150-180 words per minute for ads)
        target_words = int(request.duration_seconds * 2.5)  # ~150 words per minute
        
        # Create the chat prompt for GPT-4
        chat_prompt = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": """You are an expert advertising copywriter and voice-over script specialist with 15+ years of experience creating compelling ad scripts for radio, TV, and digital campaigns. You specialize in writing scripts that are optimized for text-to-speech conversion and voice-over work.

Your ad scripts should be:
1. SPEECH OPTIMIZED: Written for natural voice delivery, easy pronunciation
2. EMOTIONALLY ENGAGING: Hook listeners immediately and maintain interest
3. CLEAR AND CONCISE: Every word counts, no filler content
4. ACTION-ORIENTED: Strong call-to-action that drives behavior
5. BRAND FOCUSED: Reinforces brand identity and key messages

Key Requirements for TTS Scripts:
- Use conversational, natural language that flows when spoken
- Avoid complex punctuation or formatting that doesn't translate to speech
- Include natural pauses and emphasis points
- Write numbers and abbreviations in speakable format
- Consider voice pacing and breathing points
- Optimize for the specified duration with precise word count
- Include alternative script variations for A/B testing

Always provide the main script plus 2-3 variations optimized for different approaches (emotional, logical, urgency-based)."""
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""Create an optimized ad script for text-to-speech conversion:

Product Information:
- Product Name: {request.product_name}
- Category: {request.product_category}
- Target Audience: {request.target_audience}
- Key Benefits:
{benefits_text}
- Script Type: {request.script_type}
- Tone: {request.tone}
- Target Duration: {request.duration_seconds} seconds
- Target Word Count: ~{target_words} words
- Call to Action: {request.call_to_action}
{brand_guidelines}

REQUIREMENTS:
1. Create ONE primary script optimized for TTS (exactly {target_words} ± 10 words)
2. Write in natural, conversational language that sounds great when spoken
3. Include clear emphasis points and natural pauses
4. Structure: Hook (2-3 seconds) → Benefits (main portion) → Call to Action (2-3 seconds)
5. Provide script breakdown with timing
6. Generate 3 alternative versions:
   - Emotional Appeal version
   - Logical/Feature-focused version  
   - Urgency/Scarcity version

Write numbers in word form (e.g., "twenty percent" not "20%")
Avoid complex punctuation or abbreviations
Make it sound natural and engaging when spoken aloud
Optimize specifically for the {request.tone} tone and {request.script_type} format."""
                    }
                ]
            }
        ]
        
        # Generate completion using GPT-4
        completion = gpt_client.chat.completions.create(
            model=GPT_DEPLOYMENT,
            messages=chat_prompt,
            max_tokens=1500,
            temperature=0.7,
            top_p=0.95
        )
        
        # Extract the response
        response_text = completion.choices[0].message.content
        
        # Parse the response
        lines = response_text.split('\n')
        
        script_text = ""
        script_breakdown = {}
        alternative_scripts = []
        
        current_section = ""
        temp_alternatives = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Identify sections
            if "primary script" in line.lower() or "main script" in line.lower():
                current_section = "script"
                continue
            elif "breakdown" in line.lower() or "timing" in line.lower():
                current_section = "breakdown"
                continue
            elif "alternative" in line.lower() or "version" in line.lower():
                current_section = "alternatives"
                continue
            
            # Extract content based on current section
            if current_section == "script" and len(line) > 20 and not line.startswith(("1.", "2.", "3.", "-", "*")):
                if not script_text:  # Take the first substantial script
                    script_text = line
            elif current_section == "breakdown":
                if ":" in line:
                    key, value = line.split(":", 1)
                    script_breakdown[key.strip()] = value.strip()
            elif current_section == "alternatives" and len(line) > 30:
                # Look for version patterns and extract alternatives
                if any(keyword in line.lower() for keyword in ["emotional", "logical", "urgency", "version"]):
                    clean_line = re.sub(r'^[^\:]*:', '', line).strip()
                    if clean_line and len(clean_line) > 20:
                        temp_alternatives.append(clean_line)
                else:
                    # General alternative parsing
                    clean_line = re.sub(r'^[\d\.\-\*\s]+', '', line)
                    if clean_line and len(clean_line) > 30:
                        temp_alternatives.append(clean_line)
        
        # Set alternative scripts
        alternative_scripts = temp_alternatives[:3] if temp_alternatives else []
        
        # Fallback values if parsing fails
        if not script_text:
            script_text = f"Discover {request.product_name}, the perfect {request.product_category} for {request.target_audience}. With {', '.join(request.key_benefits[:2]) if request.key_benefits else 'amazing benefits'}, it's exactly what you need. {request.call_to_action} today!"
        
        if not script_breakdown:
            script_breakdown = {
                "hook": "First 2-3 seconds to grab attention",
                "benefits": f"Main content highlighting {request.product_name}",
                "call_to_action": f"Final 2-3 seconds with {request.call_to_action}"
            }
        
        if not alternative_scripts:
            alternative_scripts = [
                f"Experience the difference with {request.product_name}. Our {request.target_audience} love the {request.key_benefits[0] if request.key_benefits else 'quality'}. {request.call_to_action} now!",
                f"Why choose {request.product_name}? Because it delivers {', '.join(request.key_benefits[:2]) if request.key_benefits else 'results'}. Don't wait - {request.call_to_action}!",
                f"Limited time: Get {request.product_name} and enjoy {request.key_benefits[0] if request.key_benefits else 'premium quality'}. {request.call_to_action} before it's too late!"
            ]
        
        # Calculate word count and estimated duration
        word_count = len(script_text.split())
        estimated_duration = f"{word_count / 2.5:.1f} seconds"  # ~150 words per minute
        
        return AdScriptResponse(
            script_text=script_text.strip(),
            word_count=word_count,
            estimated_duration=estimated_duration,
            script_breakdown=script_breakdown,
            alternative_scripts=alternative_scripts[:3]
        )
        
    except Exception as e:
        print(f"Error generating ad script: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to generate ad script: {str(e)}"
        )

def convert_text_to_speech(request: TTSRequest) -> TTSResponse:
    """Convert text to speech using Azure OpenAI TTS"""
    try:
        print(f"\nConverting text to speech:")
        print(f"Text length: {len(request.text)} characters")
        print(f"Voice: {request.voice}")
        print(f"Speed: {request.speed}")
        
        headers = {
            "api-key": AZURE_TTS_KEY,
            "Content-Type": "application/json"
        }
        
        data = {
            "model": request.model,
            "input": request.text,
            "voice": request.voice,
            "response_format": request.response_format,
            "speed": request.speed
        }
        
        print(f"Making TTS request to: {AZURE_TTS_ENDPOINT}")
        
        response = requests.post(AZURE_TTS_ENDPOINT, headers=headers, json=data)
        response.raise_for_status()
        
        # Generate unique filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        audio_filename = f"speech_{timestamp}_{unique_id}.{request.response_format}"
        audio_path = os.path.join(GENERATED_AUDIO_DIR, audio_filename)
        
        # Save the audio file
        with open(audio_path, "wb") as f:
            f.write(response.content)
        
        file_size = os.path.getsize(audio_path)
        
        # Estimate duration (rough calculation: ~150 words per minute)
        word_count = len(request.text.split())
        duration_estimate = f"{(word_count / 2.5) / request.speed:.1f} seconds"
        
        print(f"Audio saved successfully: {file_size} bytes")
        
        return TTSResponse(
            audio_path=f"/generated_audio/{audio_filename}",
            file_size=file_size,
            duration_estimate=duration_estimate,
            voice_used=request.voice,
            text_length=len(request.text)
        )
        
    except Exception as e:
        print(f"Error in TTS conversion: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"TTS conversion failed: {str(e)}"
        )

# TTS Endpoints
@app.post("/generate-ad-script", response_model=AdScriptResponse, tags=["TTS & Audio"])
async def generate_ad_script_endpoint(request: AdScriptRequest):
    """Generate an optimized ad script based on product information"""
    try:
        return generate_ad_script(request)
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error generating ad script: {str(e)}"
        )

@app.post("/text-to-speech", response_model=TTSResponse, tags=["TTS & Audio"])
async def text_to_speech_endpoint(request: TTSRequest):
    """Convert text to speech using Azure OpenAI TTS"""
    try:
        return convert_text_to_speech(request)
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error in text-to-speech conversion: {str(e)}"
        )

@app.post("/create-ad-script-with-speech", response_model=AdScriptToSpeechResponse, tags=["TTS & Audio"])
async def create_ad_script_with_speech(request: AdScriptToSpeechRequest):
    """Generate ad script and convert it to speech in one step"""
    try:
        # Step 1: Generate the script
        script_request = AdScriptRequest(
            product_name=request.product_name,
            product_category=request.product_category,
            target_audience=request.target_audience,
            key_benefits=request.key_benefits,
            script_type=request.script_type,
            tone=request.tone,
            duration_seconds=request.duration_seconds,
            call_to_action=request.call_to_action,
            brand_profile_id=request.brand_profile_id
        )
        
        script_response = generate_ad_script(script_request)
        
        # Step 2: Convert to speech
        tts_request = TTSRequest(
            text=script_response.script_text,
            voice=request.voice,
            speed=request.speed,
            model="tts-1",
            response_format="mp3"
        )
        
        audio_response = convert_text_to_speech(tts_request)
        
        return AdScriptToSpeechResponse(
            script_details=script_response,
            audio_details=audio_response,
            message="Ad script generated and converted to speech successfully"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error creating ad script with speech: {str(e)}"
        )

@app.post("/create-ad-script-form", tags=["TTS & Audio"])
async def create_ad_script_form(
    product_name: str = Form(...),
    product_category: str = Form(...),
    target_audience: str = Form(...),
    key_benefits: str = Form(...),  # Comma-separated
    script_type: str = Form("commercial"),
    tone: str = Form("professional"),
    duration_seconds: int = Form(15),
    call_to_action: str = Form("Learn more"),
    voice: str = Form("alloy"),
    speed: float = Form(1.0),
    brand_profile_id: str = Form(None),
    generate_audio: bool = Form(True)
):
    """Create ad script with speech using form data for easier submission"""
    try:
        # Parse key benefits from comma-separated string
        benefits_list = [benefit.strip() for benefit in key_benefits.split(',')]
        
        # Create request
        request = AdScriptToSpeechRequest(
            product_name=product_name,
            product_category=product_category,
            target_audience=target_audience,
            key_benefits=benefits_list,
            script_type=script_type,
            tone=tone,
            duration_seconds=duration_seconds,
            call_to_action=call_to_action,
            voice=voice,
            speed=speed,
            brand_profile_id=brand_profile_id
        )
        
        if generate_audio:
            # Generate script and audio
            return await create_ad_script_with_speech(request)
        else:
            # Generate script only
            script_request = AdScriptRequest(
                product_name=product_name,
                product_category=product_category,
                target_audience=target_audience,
                key_benefits=benefits_list,
                script_type=script_type,
                tone=tone,
                duration_seconds=duration_seconds,
                call_to_action=call_to_action,
                brand_profile_id=brand_profile_id
            )
            
            script_response = generate_ad_script(script_request)
            return {
                "script_details": script_response.model_dump(),
                "audio_details": None,
                "message": "Ad script generated successfully"
            }
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error creating ad script: {str(e)}"
        )

# Run the app using uvicorn when executing the script directly
if __name__ == "__main__":
    import uvicorn
    import sys
    
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port number: {sys.argv[1]}. Using default port 8000.")
    
    print(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
