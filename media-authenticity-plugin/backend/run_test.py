import requests
import json
import sys

try:
    response = requests.post(
        "http://localhost:8000/analyze",
        json={"text": "This is a test article about AI technology."},
        timeout=30
    )
    
    with open('c:/Users/slord/Hackthon/media-authenticity-plugin/backend/test_result.txt', 'w') as f:
        f.write(f"Status Code: {response.status_code}\n")
        f.write(f"Response:\n{response.text}\n")
        
except Exception as e:
    with open('c:/Users/slord/Hackthon/media-authenticity-plugin/backend/test_result.txt', 'w') as f:
        f.write(f"Error: {e}\n")
