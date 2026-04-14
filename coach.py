from google import genai
import os

# Initialize the modern client
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# Generate the coaching response
response = client.models.generate_content(
    model="gemini-1.5-flash",
    contents="Analyze my recent Strava data and give me 3 sentences of coaching advice."
)

print(response.text)
