#!/usr/bin/env python3
import re
import os

# Read the current .env file
try:
    with open('.env.bak', 'r') as f:
        env_content = f.read()
except:
    print("No .env.bak file found")
    exit(1)

# Extract values using regex
dalle_key = re.search(r'AZURE_DALLE_KEY\s*=\s*"([^"]*)"', env_content)
dalle_endpoint = re.search(r'AZURE_DALLE_ENDPOINT\s*=\s*"([^"]*)"', env_content)
dalle_deployment = re.search(r'DALLE_DEPLOYMENT\s*=\s*"([^"]*)"', env_content)

gpt_key = re.search(r'AZURE_GPT_KEY\s*=\s*"([^"]*)"', env_content)
gpt_endpoint = re.search(r'AZURE_GPT_ENDPOINT\s*=\s*"([^"]*)"', env_content)
gpt_deployment = re.search(r'GPT_DEPLOYMENT\s*=\s*"([^"]*)"', env_content)

sora_key = re.search(r'AZURE_SORA_KEY\s*=\s*"([^"]*)"', env_content)
sora_endpoint = re.search(r'AZURE_SORA_ENDPOINT\s*=\s*"([^"]*)"', env_content)
sora_deployment = re.search(r'SORA_DEPLOYMENT\s*=\s*"([^"]*)"', env_content)

tts_key = re.search(r'AZURE_TTS_KEY\s*=\s*"([^"]*)"', env_content)
tts_endpoint = re.search(r'AZURE_TTS_ENDPOINT\s*=\s*"([^"]*)"', env_content)

# Create new .env file content
new_env = f"""# Azure DALL-E 3 credentials
AZURE_DALLE_KEY={dalle_key.group(1) if dalle_key else ''}
AZURE_DALLE_ENDPOINT={dalle_endpoint.group(1) if dalle_endpoint else ''}
DALLE_DEPLOYMENT={dalle_deployment.group(1) if dalle_deployment else 'dall-e-3'}

# Azure GPT-4o credentials
AZURE_GPT_KEY={gpt_key.group(1) if gpt_key else ''}
AZURE_GPT_ENDPOINT={gpt_endpoint.group(1) if gpt_endpoint else ''}
GPT_DEPLOYMENT={gpt_deployment.group(1) if gpt_deployment else 'gpt-4o'}

# Azure Sora credentials
AZURE_SORA_KEY={sora_key.group(1) if sora_key else ''}
AZURE_SORA_ENDPOINT={sora_endpoint.group(1) if sora_endpoint else ''}
SORA_DEPLOYMENT={sora_deployment.group(1) if sora_deployment else 'sora'}

# Azure TTS credentials
AZURE_TTS_KEY={tts_key.group(1) if tts_key else ''}
AZURE_TTS_ENDPOINT={tts_endpoint.group(1) if tts_endpoint else ''}
"""

# Write the new .env file
with open('.env', 'w') as f:
    f.write(new_env)

print("Fixed .env file created successfully!") 