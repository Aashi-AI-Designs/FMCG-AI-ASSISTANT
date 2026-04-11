import os
from dotenv import load_dotenv
load_dotenv()

from google import genai

key = os.getenv("GEMINI_API_KEY", "").strip()
if not key:
    print("ERROR: GEMINI_API_KEY not found in .env file")
    exit()

print(f"Key found: {key[:8]}...")
print("Fetching available models...\n")

client = genai.Client(api_key=key)
found = []
for m in client.models.list():
    if "generateContent" in (m.supported_actions or []):
        print(m.name)
        found.append(m.name)

print(f"\nTotal: {len(found)} models support generateContent")
