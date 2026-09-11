import requests
import json

url = "http://127.0.0.1:8000/analyze"
# Using the text from the screenshot
data = {"text": "A tree is a vital part of the natural environment that provides many benefits. Trees are tall, perennial plants with a single main stem or trunk. Trees have an essential role in maintaining ecological balance by producing oxygen, absorbing carbon dioxide, and reducing air pollution."}

response = requests.post(url, json=data, timeout=30)
print(f"Status: {response.status_code}")
print(f"Response:")
print(json.dumps(response.json(), indent=2))
