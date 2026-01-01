import os
from google import genai
import sys

# Try to get API key from environment or common location
# Since I don't have it, I'll rely on the same logic as the app
# But for now, I'll just try to list models if I can.

def list_models():
    # We'll need the API key. Since I can't get it easily from QSettings here, 
    # I'll just check if there's an environment variable.
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not found in environment")
        return

    client = genai.Client(api_key=api_key)
    try:
        models = client.models.list()
        for m in models:
            print(f"Model: {m.name}, Display: {m.display_name}")
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    list_models()
