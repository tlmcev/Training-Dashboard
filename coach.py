import google.generativeai as genai
import os

# This is the secret sauce for Tier 1 users on the legacy library
from google.generativeai.types import RequestOptions

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

model = genai.GenerativeModel('gemini-1.5-flash')

# We explicitly tell it to use 'v1' to match your Tier 1 quota
response = model.generate_content(
    "Analyze my Strava data and give me 3 sentences of coaching advice.",
    request_options=RequestOptions(api_version='v1')
)

print(response.text)
