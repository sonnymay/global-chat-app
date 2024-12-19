#!/usr/bin/env python3
from flask import Flask, request, jsonify, send_file
from openai import OpenAI
from dotenv import load_dotenv
import os
import logging
import random
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load environment variables
load_dotenv()
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Store conversation histories and introduction status
conversation_histories = {}
introduction_given = {}

@app.route('/')
def home():
    """Serve the main HTML file."""
    try:
        return send_file('index.html')
    except Exception as e:
        logger.error(f"Error serving index.html: {str(e)}")
        return "Error loading page", 500

@app.route('/verify_country', methods=['POST'])
def verify_country_route():
    """Verify and suggest corrections for country names."""
    try:
        data = request.json
        if not data or 'country' not in data:
            return jsonify({"error": "No country provided"}), 400
            
        messages = [
            {"role": "system", "content": """You are a helpful assistant that verifies country names. 
            If the input is a valid country name, respond with the country flag emoji followed by the name, like "🇹🇭 Thailand"
            If it's misspelled, respond with "Did you mean: [flag emoji] [correct country name]?"
            If it's not a country at all, respond with "Invalid country name."
            Always include the appropriate flag emoji for valid country names."""},
            {"role": "user", "content": f"Verify this country name: {data['country']}"}
        ]
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0
        )
        
        verification = response.choices[0].message.content
        return jsonify({'verification': verification})
    except Exception as e:
        logger.error(f"Error in country verification: {str(e)}")
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
            1. Start with "{flag_emoji}" followed by your country's traditional greeting and its English translation
            2. Give yourself a common name from your country
            3. Tell your age (25-35 years old)
            4. Share something you enjoy doing
            5. End with a friendly question"""
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
                prompt=f"""Professional portrait photo of an attractive and friendly-looking {gender} from {data['country']}.
                Must have:
                - Beautiful traditional/cultural clothing specific to {data['country']}
                - Traditional hairstyle appropriate for the culture
                - Authentic cultural jewelry or accessories
                - Warm, genuine smile and friendly expression
                - High-quality studio lighting with soft, flattering angles
                - Simple, elegant background that complements traditional attire
                - Well-groomed, polished appearance
                - Perfect balance of cultural authenticity and modern elegance
                Style: High-end cultural portrait photography with perfect lighting
                Note: Ensure clothing and accessories are specific to {data['country']}'s cultural heritage""",
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
            "message": greeting,  # Include the initial greeting
            "messages": messages,
            "avatar_url": avatar_url,
            "session_id": session_id,
            "status": "success"
        })
        
    except Exception as e:
        logger.error(f"Error starting chat: {str(e)}")
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
        logger.error(f"Error in chat: {str(e)}")
        return jsonify({"error": str(e), "status": "error"}), 500

if __name__ == '__main__':
    try:
        
        if not os.getenv('OPENAI_API_KEY'):
            raise ValueError("OPENAI_API_KEY not found in environment variables")
            
        port = int(os.getenv('PORT', 5000))
        app.run(debug=True, port=port)
    except Exception as e:
        logger.error(f"Application startup error: {str(e)}")
        sys.exit(1)