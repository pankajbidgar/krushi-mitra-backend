import os
from dotenv import load_dotenv
from google import genai

# .env फाइलमधून API key लोड करा
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found in .env file.")
else:
    try:
        # Gemini क्लायंट इनिशियलाइझ करा
        client = genai.Client(api_key=api_key)
        print("Fetching list of available models...\n")

        # सर्व मॉडेल्स लिस्ट करा
        for model in client.models.list():
            print(f"Model Name: {model.name}")
        print("\n--- End of list ---")

    except Exception as e:
        print(f"An error occurred: {e}")