#!/usr/bin/env python3
from flask import Flask, request, jsonify, send_file
from openai import OpenAI
from dotenv import load_dotenv
import os
import logging
import random
import sys
import time
import requests
from datetime import datetime
import pytz

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Store conversation histories (consider a database for scalability)
conversation_histories = {}

# Cache for country verification results (with expiration)
country_verification_cache = {}
CACHE_EXPIRY_TIME = 60 * 60 * 24  # 24 hours (in seconds)

@app.route('/')
def home():
    """Serve the main HTML file."""
    try:
        return send_file('index.html')
    except Exception as e:
        logger.error(f"Error serving index.html: {e}")
        return "Error loading page", 500

@app.route('/verify_country', methods=['POST'])
def verify_country_route():
    """Verify and suggest corrections for country names."""
    try:
        data = request.json
        if not data or 'country' not in data:
            return jsonify({"error": "No country provided"}), 400

        user_input = data['country']

        # Check if the input is in the cache and hasn't expired
        if user_input in country_verification_cache:
            cached_result, timestamp = country_verification_cache[user_input]
            if time.time() - timestamp < CACHE_EXPIRY_TIME:
                logger.info(f"Using cached result for {user_input}")
                return jsonify({'verification': cached_result})

        messages = [
            {"role": "system", "content": """You are a helpful assistant that verifies country names.
            If the input is a valid country name, respond with the country flag emoji followed by the name, like "🇹🇭 Thailand"
            If it's misspelled, respond with "Did you mean: [flag emoji] [correct country name]?"
            If it's not a country at all, respond with "Invalid country name."
            Always include the appropriate flag emoji for valid country names.
            If the input is partially a country name, suggest the most relevant country names, limit to 3 suggestions."""},
            {"role": "user", "content": f"Verify this country name: {user_input}"}
        ]

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0
        )

        verification = response.choices[0].message.content
        country_verification_cache[user_input] = (verification, time.time())
        return jsonify({'verification': verification})

    except Exception as e:
        logger.error(f"Error in country verification: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/get_country_info', methods=['POST'])
def get_country_info():
    """Get weather and basic information about a country."""
    try:
        data = request.json
        if not data or 'country' not in data:
            return jsonify({"error": "No country provided"}), 400

        country = data['country'].split(' ')[-1]  # Remove emoji if present
        
        # Get capital city using OpenAI
        capital_messages = [
            {"role": "system", "content": "Return only the capital city name for the given country."},
            {"role": "user", "content": f"Capital city of {country}:"}
        ]
        
        capital_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=capital_messages,
            temperature=0
        )
        capital_city = capital_response.choices[0].message.content.strip()

        # Get weather data
        weather_api_key = os.getenv('OPENWEATHER_API_KEY')
        weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={capital_city}&appid={weather_api_key}&units=metric"
        
        weather_response = requests.get(weather_url)
        weather_data = weather_response.json()

        if weather_response.status_code == 200:
            # Get timezone for the capital city
            timezone = pytz.timezone(pytz.country_timezones[weather_data['sys']['country']][0])
            local_time = datetime.now(timezone).strftime("%I:%M %p")
            
            weather_info = {
                "temperature": round(weather_data["main"]["temp"]),
                "condition": weather_data["weather"][0]["main"],
                "icon": weather_data["weather"][0]["icon"],
                "humidity": weather_data["main"]["humidity"],
                "city": capital_city,
                "local_time": local_time
            }
            
            # Get country information using OpenAI
            info_messages = [
                {"role": "system", "content": """Provide a brief overview of the country in this format:
                Capital: [capital]
                Population: [population]
                Language(s): [languages]
                Currency: [currency]
                Continent: [continent]
                Keep it factual and concise."""},
                {"role": "user", "content": f"Information about {country}:"}
            ]
            
            info_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=info_messages,
                temperature=0
            )
            
            country_info = info_response.choices[0].message.content

            return jsonify({
                "weather": weather_info,
                "country_info": country_info,
                "status": "success"
            })
        else:
            return jsonify({
                "error": "Could not fetch weather data",
                "status": "error"
            }), 500

    except Exception as e:
        logger.error(f"Error getting country info: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/start_chat', methods=['POST'])
def start_chat():
    """Initialize a new chat session with avatar generation."""
    try:
        data = request.json
        session_id = data.get('session_id', str(random.randint(1000, 9999)))

        # Initialize conversation history for new sessions
        if session_id not in conversation_histories:
            conversation_histories[session_id] = []

        if not data or 'country' not in data:
            return jsonify({"error": "No country provided"}), 400

        gender = data.get('gender', 'woman')

        # Get flag emoji for the country
        flag_messages = [
            {"role": "system", "content": "Return only the flag emoji for the given country."},
            {"role": "user", "content": f"Flag emoji for: {data['country']}"}
        ]

        flag_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=flag_messages,
            temperature=0
        )

        flag_emoji = flag_response.choices[0].message.content

        # Set up initial message with structured introduction
        messages = [{
            "role": "system",
            "content": f"""You are a friendly local from {data['country']}. 
            IMPORTANT: Greet the user in English with:
            1. Start with "{flag_emoji}" followed by your country's traditional greeting and its English translation.
            2. Give yourself a common name from your country.
            3. Tell your age (25-35 years old).
            4. Share something you enjoy doing.
            5. End with a friendly question."""
        }]

        # Generate initial greeting immediately
        chat_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7
        )

        greeting = chat_response.choices[0].message.content
        messages.append({"role": "assistant", "content": greeting})

        # Generate avatar with traditional clothing prompt
        try:
            avatar_response = client.images.generate(
                model="dall-e-2",
                prompt=f"""Professional portrait photo of a radiant and alluring woman in her early 20s from {data['country']}.
    - Must have beautiful traditional/cultural clothing specific to {data['country']}
    - Include traditional hairstyle appropriate for the culture
    - Add tasteful and authentic cultural jewelry or accessories that enhance her natural beauty
    - She should have a warm, genuine smile and a confident, engaging expression
    - Use high-quality studio lighting with soft, flattering angles
    - Keep the background simple and elegant, complementing the traditional attire
    - Ensure she is well-groomed and polished in appearance
    - The image should portray a sense of youthful energy and charm
    - Style should be high-end cultural portrait photography with perfect lighting, capturing a moment of captivating beauty
    - Ensure clothing and accessories are specific to {data['country']}'s cultural heritage, and that the image reflects a respectful and authentic representation of the culture.
    """,
                size="1024x1024",
                quality="standard",
                n=1
            )
            avatar_url = avatar_response.data[0].url
        except Exception as e:
            logger.error(f"Avatar generation failed: {str(e)}")
            avatar_url = "https://via.placeholder.com/300"

        conversation_histories[session_id] = messages

        return jsonify({
            "message": greeting,
            "messages": messages,
            "avatar_url": avatar_url,
            "session_id": session_id,
            "status": "success"
        })

    except Exception as e:
        logger.error(f"Error starting chat: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/chat', methods=['POST'])
def chat():
    """Process chat messages."""
    try:
        data = request.json
        session_id = data.get('session_id')

        if not session_id or session_id not in conversation_histories:
            return jsonify({"error": "Invalid session ID"}), 400

        if not data or 'user_input' not in data:
            return jsonify({"error": "Invalid request data"}), 400

        messages = conversation_histories[session_id]
        messages.append({"role": "user", "content": data['user_input']})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7
        )

        reply = response.choices[0].message.content
        messages.append({"role": "assistant", "content": reply})
        conversation_histories[session_id] = messages

        return jsonify({
            "reply": reply,
            "messages": messages,
            "status": "success"
        })
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

if __name__ == '__main__':
    try:
        if not os.getenv('OPENAI_API_KEY'):
            raise ValueError("OPENAI_API_KEY not found in environment variables")

        port = int(os.getenv('PORT', 5000))
        app.run(debug=True, port=port)
    except Exception as e:
        logger.error(f"Application startup error: {e}")
        sys.exit(1)