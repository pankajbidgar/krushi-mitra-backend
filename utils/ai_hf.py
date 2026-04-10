import requests
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("HUGGINGFACE_API_KEY")
API_URL = "https://api-inference.huggingface.co/models/google/flan-t5-large"
headers = {"Authorization": f"Bearer {API_KEY}"}

def get_ai_response(prompt: str) -> str:
    try:
        response = requests.post(API_URL, headers=headers, json={"inputs": prompt})
        if response.status_code == 200:
            return response.json()[0]['generated_text']
        else:
            return fallback_response(prompt)
    except:
        return fallback_response(prompt)

def fallback_response(prompt):
    # तुमचा FAQ कोड इथे
    ...