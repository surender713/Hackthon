import requests
import json

url = "http://127.0.0.1:8000/analyze"
data = {"text": "Trees are tall, perennial plants with a single main stem or trunk."}

response = requests.post(url, json=data, timeout=20)
print(f"Status: {response.status_code}")
print(f"Response:")
print(json.dumps(response.json(), indent=2))
