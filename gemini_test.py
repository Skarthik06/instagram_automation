import os
from dotenv import load_dotenv

import google.generativeai as genai

load_dotenv()

key = os.getenv("GEMINI_API_KEY")
print("API KEY FOUND:", bool(key))

genai.configure(api_key=key)

model = genai.GenerativeModel("gemini-2.5-flash")

response = model.generate_content(
    "Write one original motivational sentence about growth."
)

print("RAW RESPONSE:", response)
print("TEXT:", repr(response.text))
