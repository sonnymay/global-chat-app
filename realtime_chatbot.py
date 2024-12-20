#!/usr/bin/env python3
import sys
import os
import random
import logging
from openai import OpenAI
from dotenv import load_dotenv
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration (Move to a separate config file if needed) ---
OCCUPATION_OPTIONS = ["teacher", "tour guide", "cafe owner", "office worker", "hotel manager",
                     "shopkeeper", "restaurant owner", "travel blogger", "artist", "musician"]
HOBBIES = ["cooking", "photography", "hiking", "reading", "painting",
           "traveling", "dancing", "gardening", "writing", "music"]
CACHE_EXPIRY_TIME = 60 * 60 * 24  # 24 hours (in seconds)
# --------------------------------------------------------------------

# Cache for country verification results (with expiration)
country_verification_cache = {}

def create_chatbot_prompt(country, gender="woman"):
    """Create a concise prompt for the chatbot."""
    age = random.randint(25, 35)
    occupation = random.choice(OCCUPATION_OPTIONS)
    hobbies = random.sample(HOBBIES, 2)

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
    """Verify if the input is a valid country and suggest corrections if needed.
       Caches results for CACHE_EXPIRY_TIME seconds.
    """
    # Check if the input is in the cache and hasn't expired
    if country in country_verification_cache:
        cached_result, timestamp = country_verification_cache[country]
        if time.time() - timestamp < CACHE_EXPIRY_TIME:
            logger.info(f"Using cached result for {country}")
            return cached_result

    messages = [
        {"role": "system", "content": """You are a helpful assistant that verifies country names.
        If the input is a valid country name, respond with the country flag emoji followed by the name, like "🇹🇭 Thailand"
        If it's misspelled, respond with "Did you mean: [flag emoji] [correct country name]?"
        If it's not a country at all, respond with "Invalid country name."
        Always include the appropriate flag emoji for valid country names.
        If the input is partially a country name, suggest the most relevant country names, limit to 3 suggestions."""},
        {"role": "user", "content": f"Verify this country name: {country}"}
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0
        )

        verification = response.choices[0].message.content

        # Cache the result with a timestamp
        country_verification_cache[country] = (verification, time.time())

        return verification

    except Exception as e:
        logger.error(f"Country verification error: {e}")
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
            logger.error(f"Avatar generation failed: {e}")
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
            logger.error(f"Chat initialization failed: {e}")
            return {
                "message": "Sorry, there was an error starting the chat.",
                "error": str(e),
                "status": "error"
            }

    except Exception as e:
        logger.error(f"Chat session error: {e}")
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
        logger.error(f"Message processing error: {e}")
        return {
            "reply": "Sorry, I couldn't process your message.",
            "error": str(e),
            "status": "error"
        }

if __name__ == "__main__":
    load_dotenv()
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    # Example usage (if you want to run this script directly):
    country = input("Enter a country: ")
    gender = input("Enter a gender (optional, default is woman): ") or "woman"

    # Verify the country
    verification_result = verify_country(client, country)
    print(f"Country verification: {verification_result}")
    if not verification_result.startswith("Did you mean:") and not verification_result.startswith("Invalid"):
      # Start a chat session
      chat_result = chat_session(client, country, gender)
      if chat_result["status"] == "success":
          print(f"Avatar URL: {chat_result['avatar_url']}")
          print(f"Initial message: {chat_result['message']}")

          # Example of processing a user message
          while True:
              user_input = input("Your message: ")
              if user_input.lower() == "exit":
                break
              message_result = process_message(client, chat_result["messages"], user_input)
              if message_result["status"] == "success":
                  print(f"AI: {message_result['reply']}")
      else:
        print("Error starting chat session.")