#!/usr/bin/env python3
import sys
import os
import random
import logging
from openai import OpenAI
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_virtual_env():
    """Check if required packages are installed."""
    try:
        import openai
        from dotenv import load_dotenv
        return True
    except ImportError as e:
        print("Please install required packages:")
        print("pip install openai python-dotenv")
        return False

def create_chatbot_prompt(country, gender="woman"):
    """Create a concise prompt for the chatbot."""
    age = random.randint(25, 35)
    occupation_options = ["teacher", "tour guide", "cafe owner", "office worker", "hotel manager", 
                         "shopkeeper", "restaurant owner", "travel blogger", "artist", "musician"]
    occupation = random.choice(occupation_options)
    hobbies = random.sample(["cooking", "photography", "hiking", "reading", "painting", 
                            "traveling", "dancing", "gardening", "writing", "music"], 2)
    
    prompt = f"""STRICT CHARACTER INSTRUCTIONS: You are a {age}-year-old {gender} from {country}. 

CHARACTER PROFILE:
- Age: {age} years old (ALWAYS use this exact age)
- Job: {occupation}
- Hobbies: {', '.join(hobbies)}

IMPORTANT: Introduce yourself ONCE with:
- A traditional greeting in your language (like 'Sawasdee ka' for Thailand)
- Your name (use a common name from your country)
- Your age
- Your occupation
- A brief mention of your hobbies
- End with "What about you?" or a similar friendly question

Keep all responses concise and natural. Never break character or mention being AI."""

    return prompt

def verify_country(client, country):
    """Verify if the input is a valid country and suggest corrections if needed."""
    messages = [
        {"role": "system", "content": """You are a helpful assistant that verifies country names. 
        If the input is a valid country name, respond with just the correctly formatted country name.
        If it's misspelled, respond with "Did you mean: [correct country name]?"
        If it's not a country at all, respond with "Invalid country name."
        Keep responses exactly in this format."""},
        {"role": "user", "content": f"Verify this country name: {country}"}
    ]
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Country verification error: {str(e)}")
        return "Error verifying country name"

def chat_session(client, country, gender="woman"):
    """Handle a single chat session with a country."""
    try:
        # Generate avatar first
        logger.info("Generating avatar...")
        try:
            avatar_response = client.images.generate(
                model="dall-e-2",
                prompt=f"professional headshot portrait photo of a {gender} from {country}, smiling, natural lighting, clean background, looking at camera, shoulders up",
                size="1024x1024",
                quality="standard",
                n=1
            )
            avatar_url = avatar_response.data[0].url
            logger.info(f"Avatar generated successfully: {avatar_url}")
        except Exception as e:
            logger.error(f"Avatar generation failed: {str(e)}")
            avatar_url = "https://via.placeholder.com/300"

        # Create chat messages
        messages = []
        system_message = create_chatbot_prompt(country, gender)
        messages.append({"role": "system", "content": system_message})
        
        # Get initial greeting
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.7,
                max_tokens=150
            )
            message = response.choices[0].message.content
            messages.append({"role": "assistant", "content": message})
            
            logger.info("Chat session initialized successfully")
            return {
                "message": message,
                "messages": messages,
                "avatar_url": avatar_url,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Chat initialization failed: {str(e)}")
            return {
                "message": "Sorry, there was an error starting the chat.",
                "error": str(e),
                "status": "error"
            }
            
    except Exception as e:
        logger.error(f"Chat session error: {str(e)}")
        return {
            "message": "Sorry, there was an error starting the chat.",
            "error": str(e),
            "status": "error"
        }

def process_message(client, messages, user_input):
    """Process a single message in the chat session."""
    try:
        if not isinstance(messages, list) or not user_input:
            raise ValueError("Invalid input parameters")
            
        messages.append({"role": "user", "content": user_input})
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=150
        )
        
        reply = response.choices[0].message.content
        messages.append({"role": "assistant", "content": reply})
        
        return {
            "reply": reply,
            "messages": messages,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Message processing error: {str(e)}")
        return {
            "reply": "Sorry, I couldn't process your message.",
            "error": str(e),
            "status": "error"
        }

if __name__ == "__main__":
    if not check_virtual_env():
        sys.exit(1)
    load_dotenv()
    client = OpenAI()