import requests
import json

api_url = "https://datausa.io/api/data?drilldowns=Nation&measures=Population"

def fetch_api_task(url):
    res = requests.get(url)
    # print(res)
    response = json.loads(res.text)
    return response['data']

print(fetch_api_task(api_url))


