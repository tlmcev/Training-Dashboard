from google import genai
import os

# Initialize the client without the 'v1beta' restriction
client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"],
    http_options={'api_version': 'v1'}
)

response = client.models.generate_content(
    model="gemini-1.5-flash",
    contents="Analyze my Strava data and give me 3 sentences of coaching advice."
)

print(response.text)
