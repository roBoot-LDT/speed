import requests
import json

# Send data
url = "http://localhost:5000/api/data"
data = {"digits": [4, 5, 6]}
response = requests.post(url, json=data)
print(response.json())

# Check received data
response = requests.get("http://localhost:5000/api/data")
print(response.json())