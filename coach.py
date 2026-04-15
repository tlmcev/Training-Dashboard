import google.generativeai as genai
import os

# Configure the library with your key
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# We specify the model. By using the 'models/' prefix, 
# we help the library route the request correctly.
model = genai.GenerativeModel('models/gemini-1.5-flash')

# We'll skip the RequestOptions entirely and let the 
# Tier 1 key naturally hit the v1 production endpoint.
response = model.generate_content(
    "Analyze my recent Strava data and give me 3 sentences of coaching advice."
)

print(response.text)
