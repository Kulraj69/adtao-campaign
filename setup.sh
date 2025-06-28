#!/bin/bash

# Create required directories
echo "Creating required directories..."
mkdir -p uploads static generated_images generated_videos generated_audio db

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp env.template .env
    echo "Please edit .env file and add your API keys"
else
    echo ".env file already exists"
fi

# Check if Python is installed
if command -v python3 &>/dev/null; then
    echo "Installing dependencies..."
    python3 -m pip install -r requirements.txt
    echo "Setup complete!"
    echo "Run the application with: python3 main.py"
else
    echo "Python 3 not found. Please install Python 3 and then run:"
    echo "pip install -r requirements.txt"
fi 