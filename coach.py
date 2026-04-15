import google.generativeai as genai
import os

# The standard library uses this configuration method
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Use the most basic, stable call possible
model = genai.GenerativeModel('gemini-1.5-flash')

response = model.generate_content(
    "Analyze my recent Strava data and give me 3 sentences of coaching advice."
)

print(response.text)
