import os
from dotenv import load_dotenv
from google import genai


load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found in .env file.")
else:
    try:
       
        client = genai.Client(api_key=api_key)
        print("Fetching list of available models...\n")

        
        for model in client.models.list():
            print(f"Model Name: {model.name}")
        print("\n--- End of list ---")

    except Exception as e:
        print(f"An error occurred: {e}")