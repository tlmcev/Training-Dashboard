from google import genai
import os

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

response = client.models.generate_content(
    model="gemini-1.5-flash-002",  # This is the "Goldilocks" version for stability
    contents="Analyze my Strava data and give me 3 sentences of coaching advice."
)

print(response.text)
