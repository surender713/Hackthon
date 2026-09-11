import requests
import json

payload = {"text": "This is a test article about AI technology."}
try:
    response = requests.post("http://localhost:8000/analyze", json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
