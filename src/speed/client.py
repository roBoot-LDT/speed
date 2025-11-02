import random
import requests
import json
import time
from random import randint
# Send data
url = "http://localhost:65500/api/data"
speed = 5
while True:
    data = {"digits": [1, speed]}
    response = requests.post(url, json=data)
    speed += random.randint(10, 15)

    # data = {"digits": [2, speed]}
    # response = requests.post(url, json=data)
    # speed += 5
    time.sleep(1)