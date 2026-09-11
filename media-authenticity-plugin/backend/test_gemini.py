from google import genai
import os
from dotenv import load_dotenv
from pathlib import Path
import json

ENV_PATH = Path('.env')
load_dotenv(dotenv_path=ENV_PATH)
key = os.getenv('GEMINI_API_KEY')

client = genai.Client(api_key=key)
text = 'This is a test.'
prompt = f"""Analyze if this text is AI-generated or human-written.
Return ONLY this JSON format:
{{"percentage": <0-100>, "label": "<number>% <AI-Generated|Human-Written>"}}

Text: {text}"""

response = client.models.generate_content(
    model='gemini-3.6-flash',
    contents=prompt,
)
print("Response:")
print(response.text)
