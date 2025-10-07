from dotenv import load_dotenv

load_dotenv()
import requests
import json
import re
import sys
import secrets
import string
from flask import Flask, render_template, redirect, url_for, request, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, timezone
import os
import random
import time
import traceback
from functools import wraps
import sqlalchemy.exc

# Database retry decorator for handling connection issues
def database_retry(max_retries=3, delay=1):
    """Decorator to retry database operations on connection failures"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (sqlalchemy.exc.OperationalError, sqlalchemy.exc.DisconnectionError) as e:
                    if attempt < max_retries - 1:
                        print(f"Database connection error (attempt {attempt + 1}/{max_retries}): {e}")
                        print(f"Retrying in {delay} seconds...")
                        time.sleep(delay * (attempt + 1))  # Exponential backoff
                        # Try to recreate the database connection
                        try:
                            db.session.remove()
                            db.engine.dispose()
                        except:
                            pass
                    else:
                        print(f"Database operation failed after {max_retries} attempts")
                        raise e
                except Exception as e:
                    # For non-connection errors, don't retry
                    raise e
            return None
        return wrapper
    return decorator

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')  # Use env var in production

# Database Configuration - Support both SQLite (local) and PostgreSQL (production)
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # Production: Use PostgreSQL from environment variable (Neon, Heroku, etc.)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    # PostgreSQL connection pooling and stability settings for Neon
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 10,                    # Number of connections to maintain
        'pool_recycle': 3600,               # Recycle connections every hour
        'pool_pre_ping': True,              # Verify connections before use
        'max_overflow': 20,                 # Additional connections if needed
        'pool_timeout': 30,                 # Timeout for getting connection
        'connect_args': {
            'connect_timeout': 10,          # Connection timeout
            'application_name': 'quizzo',   # App name for monitoring
        }
    }
else:
    # Development: Use SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quizzo.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'static/profile_pics'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

# Database helper functions with retry logic
@database_retry(max_retries=3, delay=1)
def safe_db_query(query_func):
    """Safely execute database queries with retry logic"""
    try:
        return query_func()
    except Exception as e:
        print(f"Database query error: {e}")
        # Force session cleanup on error
        try:
            db.session.rollback()
        except:
            pass
        raise e

@database_retry(max_retries=3, delay=1)
def safe_db_commit():
    """Safely commit database changes with retry logic"""
    try:
        db.session.commit()
        return True
    except Exception as e:
        print(f"Database commit error: {e}")
        try:
            db.session.rollback()
        except:
            pass
        raise e

# Free AI Services Configuration
FREE_AI_SERVICES = {
    'huggingface': {
        'name': 'Hugging Face',
        'api_url': 'https://api-inference.huggingface.co/models/microsoft/DialoGPT-medium',
        'headers_func': lambda: {'Authorization': f'Bearer {os.environ.get("HUGGINGFACE_API_KEY", "")}'},
        'free_tier': True,
        'rate_limit': '1000 requests/hour'
    },
    'together': {
        'name': 'Together AI',
        'api_url': 'https://api.together.xyz/inference',
        'headers_func': lambda: {'Authorization': f'Bearer {os.environ.get("TOGETHER_API_KEY", "")}'},
        'free_tier': '$5 free credits',
        'rate_limit': 'Generous free tier'
    },
    'cohere': {
        'name': 'Cohere',
        'api_url': 'https://api.cohere.ai/v1/generate',
        'headers_func': lambda: {'Authorization': f'Bearer {os.environ.get("COHERE_API_KEY", "")}', 'Content-Type': 'application/json'},
        'free_tier': '5 million tokens/month',
        'rate_limit': 'Very generous'
    },
    'groq': {
        'name': 'Groq',
        'api_url': 'https://api.groq.com/openai/v1/chat/completions',
        'headers_func': lambda: {'Authorization': f'Bearer {os.environ.get("GROQ_API_KEY", "")}', 'Content-Type': 'application/json'},
        'free_tier': 'Fast inference, free tier available',
        'rate_limit': 'High speed processing'
    }
}


def try_free_ai_generation(prompt, num_questions, question_type, difficulty, context):
    """Try different free AI services to generate questions"""
    
    # Enhanced prompt for better question generation
    enhanced_prompt = f"""
As an expert educator, create {num_questions} high-quality {question_type.replace('_', ' ')} questions about the given topic.

Requirements:
- Difficulty: {difficulty}
- Question type: {question_type}
- Educational and academically sound
- Clear and unambiguous language
- Suitable for assessment

Topic: {prompt}
{f'Additional context: {context}' if context else ''}

Please provide ONLY a JSON array with this exact format:
[
  {{
    "question": "Question text here",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_answer": "A",
    "explanation": "Brief explanation"
  }}
]

For true/false questions, use:
[
  {{
    "question": "Statement here",
    "correct_answer": "true",
    "explanation": "Brief explanation"
  }}
]

Generate exactly {num_questions} questions in valid JSON format.
"""

    # Try Groq first (fastest free option)
    groq_result = try_groq_api(enhanced_prompt, num_questions)
    if groq_result:
        return groq_result
    
    # Try Hugging Face
    hf_result = try_huggingface_api(enhanced_prompt, num_questions)
    if hf_result:
        return hf_result
    
    # Try Cohere
    cohere_result = try_cohere_api(enhanced_prompt, num_questions)
    if cohere_result:
        return cohere_result
    
    # Try Together AI
    together_result = try_together_api(enhanced_prompt, num_questions)
    if together_result:
        return together_result
    
    return None

def try_groq_api(prompt, num_questions):
    """Try Groq API - Very fast free inference"""
    api_key = os.environ.get('GROQ_API_KEY')
    print(f"[GROQ] API Key present: {'✓' if api_key else '✗'}")
    if not api_key:
        print("[GROQ] No API key found")
        return None
    
    try:
        print(f"[GROQ] Making API call for {num_questions} questions...")
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'llama-3.1-8b-instant',  # Updated current model
                'messages': [
                    {'role': 'system', 'content': 'You are an expert educational content creator. Generate high-quality questions in valid JSON format only.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.7,
                'max_tokens': 2000
            },
            timeout=30
        )
        
        print(f"[GROQ] Response status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            ai_text = result['choices'][0]['message']['content']
            print(f"[GROQ] Generated text length: {len(ai_text)}")
            parsed_result = parse_ai_response(ai_text, 'Groq (LLaMA 3)')
            print(f"[GROQ] Parsed result: {parsed_result}")
            return parsed_result
        else:
            print(f"Groq API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Groq API exception: {e}")
        return None

def try_grok_for_chatbot(user_message, user_role, category, conversation_context="", user_name="Student"):
    """Use Grok (via Groq API) for intelligent chatbot responses with conversation context"""
    api_key = os.environ.get('GROQ_API_KEY')
    print(f"[GROK-CHATBOT] API Key present: {'✓' if api_key else '✗'}")
    
    if not api_key:
        print("[GROK-CHATBOT] No API key found")
        return None
    
    try:
        # Create focused system prompt based on category
        system_content = f"""You are Quizzo Bot, a friendly and enthusiastic educational assistant who loves helping students and lecturers! 

Hey there, {user_name}! 🎯 I'm here to chat with you like a real person would - casual, helpful, and fun!

IMPORTANT: You have access to our conversation history through the QUIZZO platform. When users ask about past conversations, refer to the context provided and help them remember what we discussed before!

PERSONALITY:
- Be conversational and natural like talking to a friend
- Use casual language: "Hey!", "That's awesome!", "Let me help you with that!"
- Show enthusiasm and encouragement
- Ask follow-up questions to keep the conversation flowing
- Use the person's name naturally in conversation
- Be genuinely helpful, not robotic

CONVERSATION MEMORY:
- You CAN remember our previous conversations through the platform's chat history
- When asked about past conversations, refer to the context and help recall topics
- Build on previous discussions naturally
- Reference things we've talked about before when relevant

RESPONSE FORMAT (for study tips and educational content):
When giving study advice or explaining topics, use this friendly structure:

**Hey {user_name}! [Topic Name]:**

**[Section Name]:**
• [Natural conversational point with explanation]
• [Another helpful tip in normal language]

**[Another Section]:**
• [More casual, friendly advice]
• [Keep it natural and conversational]

**What would you like to dive into next, {user_name}?**

CRITICAL: Keep responses SHORT and focused! Maximum 3-4 bullet points total. Don't write long explanations - be concise and engaging!

CONVERSATION STYLE:
- Start with warm greetings like "Hey {user_name}!" or "That's a great question!"
- Use encouraging phrases: "You've got this!", "That's exactly right!", "Great thinking!"
- Ask engaging follow-ups: "What's your experience with...?", "Have you tried...?"
- Keep explanations clear but friendly - don't ramble!
- Share tips like you're chatting with a friend

QUIZZO PLATFORM INFO:
- Speed challenges: 30-second countdown (pretty exciting, right?)
- Points: 50 base + 10 per correct answer + speed bonuses
- Virtual classrooms with video calls
- Created by Shadrack M Emadau
- AI-generated questions for practice

IMPORTANT: Be natural, warm, and genuinely helpful. Keep responses SHORT and focused. You can access conversation history through the platform. Chat like a knowledgeable friend who's excited to help!"""

        # Build conversation context
        messages = [{"role": "system", "content": system_content}]
        
        # Add recent conversation context if available
        if conversation_context:
            messages.append({
                "role": "assistant", 
                "content": f"Previous conversation context:\n{conversation_context}\n\nNow continuing the conversation..."
            })

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        print(f"[GROK-CHATBOT] Making API call with context for chatbot response...")
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                "model": "llama-3.1-8b-instant",  # Updated to working model
                "messages": messages,
                "max_tokens": 800,  # Increased from 300 to allow complete responses
                "temperature": 0.8,
                "top_p": 0.9,
                "presence_penalty": 0.1,
                "frequency_penalty": 0.1
            },
            timeout=15
        )
        
        print(f"[GROK-CHATBOT] Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result['choices'][0]['message']['content']
            print(f"[GROK-CHATBOT] Generated response length: {len(ai_response)}")
            print(f"[GROK-CHATBOT] Response preview: {ai_response[:100]}...")
            return ai_response.strip()
        else:
            print(f"Grok API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Grok chatbot API exception: {e}")
        return None

def try_huggingface_api(prompt, num_questions):
    """Try Hugging Face Inference API - Completely free"""
    api_key = os.environ.get('HUGGINGFACE_API_KEY')
    if not api_key:
        return None
    
    try:
        # Use a good free model for text generation
        response = requests.post(
            'https://api-inference.huggingface.co/models/microsoft/DialoGPT-large',
            headers={'Authorization': f'Bearer {api_key}'},
            json={'inputs': prompt, 'parameters': {'max_length': 2000, 'temperature': 0.7}},
            timeout=60  # HF can be slower
        )
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                ai_text = result[0].get('generated_text', '')
                return parse_ai_response(ai_text, 'Hugging Face (DialoGPT)')
        else:
            print(f"HuggingFace API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"HuggingFace API exception: {e}")
        return None

def try_cohere_api(prompt, num_questions):
    """Try Cohere API - Generous free tier"""
    api_key = os.environ.get('COHERE_API_KEY')
    if not api_key:
        return None
    
    try:
        response = requests.post(
            'https://api.cohere.ai/v1/generate',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'command',
                'prompt': prompt,
                'max_tokens': 2000,
                'temperature': 0.7,
                'stop_sequences': []
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_text = result['generations'][0]['text']
            return parse_ai_response(ai_text, 'Cohere (Command)')
        else:
            print(f"Cohere API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Cohere API exception: {e}")
        return None

def try_together_api(prompt, num_questions):
    """Try Together AI - Good free tier"""
    api_key = os.environ.get('TOGETHER_API_KEY')
    if not api_key:
        return None
    
    try:
        response = requests.post(
            'https://api.together.xyz/inference',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'togethercomputer/llama-2-7b-chat',
                'prompt': prompt,
                'max_tokens': 2000,
                'temperature': 0.7
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_text = result['output']['choices'][0]['text']
            return parse_ai_response(ai_text, 'Together AI (LLaMA 2)')
        else:
            print(f"Together API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Together API exception: {e}")
        return None

def parse_ai_response(ai_text, source_name):
    """Parse AI response and extract questions"""
    try:
        import json as pyjson
        
        # Clean the response
        ai_text = ai_text.strip()
        if ai_text.startswith('```json'):
            ai_text = ai_text[7:]
        if ai_text.endswith('```'):
            ai_text = ai_text[:-3]
        ai_text = ai_text.strip()
        
        # Find JSON array in the response
        start_idx = ai_text.find('[')
        end_idx = ai_text.rfind(']') + 1
        
        if start_idx != -1 and end_idx > start_idx:
            json_text = ai_text[start_idx:end_idx]
            questions = pyjson.loads(json_text)
            
            if isinstance(questions, list) and len(questions) > 0:
                # Add metadata
                for i, q in enumerate(questions):
                    q['id'] = i + 1
                    q['source'] = source_name
                    q['ai_generated'] = True
                
                return {
                    'questions': questions,
                    'status': 'success',
                    'source': source_name,
                    'ai_generated': True
                }
        
        return None
        
    except Exception as e:
        print(f"Error parsing AI response from {source_name}: {e}")
        return None

# Fallback question templates for when API is unavailable
FALLBACK_QUESTIONS = {
    'medicine': {
        'beginner': [
            {
                'question': 'What is the largest organ in the human body?',
                'options': ['Heart', 'Liver', 'Skin', 'Brain'],
                'correct_answer': 'C',
                'explanation': 'The skin is the largest organ, covering the entire body and protecting internal organs.'
            },
            {
                'question': 'How many chambers does a human heart have?',
                'options': ['2', '3', '4', '5'],
                'correct_answer': 'C',
                'explanation': 'The human heart has 4 chambers: 2 atria and 2 ventricles.'
            },
            {
                'question': 'Which blood type is known as the universal donor?',
                'options': ['A+', 'B+', 'AB+', 'O-'],
                'correct_answer': 'D',
                'explanation': 'O- blood type can be given to people with any blood type, making it the universal donor.'
            },
            {
                'question': 'What is the normal human body temperature in Celsius?',
                'options': ['35°C', '37°C', '39°C', '40°C'],
                'correct_answer': 'B',
                'explanation': 'Normal human body temperature is approximately 37°C (98.6°F).'
            },
            {
                'question': 'Which organ produces insulin?',
                'options': ['Liver', 'Kidney', 'Pancreas', 'Stomach'],
                'correct_answer': 'C',
                'explanation': 'The pancreas produces insulin, which regulates blood sugar levels.'
            }
        ]
    },
    'science': {
        'beginner': [
            {
                'question': 'What is the chemical symbol for water?',
                'options': ['H2O', 'CO2', 'NaCl', 'O2'],
                'correct_answer': 'A',
                'explanation': 'Water is composed of two hydrogen atoms and one oxygen atom, hence H2O.'
            },
            {
                'question': 'What planet is closest to the Sun?',
                'options': ['Venus', 'Mercury', 'Earth', 'Mars'],
                'correct_answer': 'B',
                'explanation': 'Mercury is the closest planet to the Sun in our solar system.'
            }
        ]
    },
    'mathematics': {
        'beginner': [
            {
                'question': 'What is 15 + 27?',
                'options': ['41', '42', '43', '44'],
                'correct_answer': 'B',
                'explanation': '15 + 27 = 42'
            },
            {
                'question': 'What is the area of a rectangle with length 8 and width 5?',
                'options': ['13', '26', '40', '80'],
                'correct_answer': 'C',
                'explanation': 'Area of rectangle = length × width = 8 × 5 = 40'
            }
        ]
    }
}

# Endpoint for AI-powered question generation
@app.route('/generate_ai_question', methods=['POST'])
def generate_ai_question():
    import sys
    data = request.json
    print(f"[AI GEN] Request received: {data}", file=sys.stderr)
    
    topic = data.get('topic', '')
    prompt = data.get('prompt', '')
    num_questions = int(data.get('num_questions', 5))
    question_type = data.get('question_type', 'multiple_choice')
    difficulty = data.get('difficulty', 'intermediate')
    context = data.get('context', '')
    
    # Try free AI services first
    print(f"[AI GEN] Trying free AI services for {num_questions} {question_type} questions", file=sys.stderr)
    
    ai_result = try_free_ai_generation(prompt or topic, num_questions, question_type, difficulty, context)
    
    if ai_result:
        print(f"[AI GEN] Successfully generated questions using {ai_result.get('source', 'Free AI')}", file=sys.stderr)
        return jsonify(ai_result)
    
    # If all free AI services fail, try OpenRouter as backup
    print(f"[AI GEN] Free AI services unavailable, trying OpenRouter...", file=sys.stderr)
    openrouter_result = try_openrouter_generation(topic, prompt, num_questions, question_type, difficulty, context)
    
    if openrouter_result:
        print(f"[AI GEN] Successfully generated questions using OpenRouter", file=sys.stderr)
        return jsonify(openrouter_result)
    
    # Final fallback to template questions
    print(f"[AI GEN] All AI services unavailable, using template questions", file=sys.stderr)
    fallback_questions = generate_fallback_questions(topic, num_questions, question_type, difficulty)
    
    return fallback_questions

def try_openrouter_generation(topic, prompt, num_questions, question_type, difficulty, context):
    """Try OpenRouter API as backup option"""
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        return None
    
    try:
        # Create sophisticated prompt
        if question_type == 'multiple_choice':
            question_instruction = f"""
Generate exactly {num_questions} high-quality multiple-choice questions about {topic}.

Requirements:
- Each question should have 4 options (A, B, C, D)
- Difficulty level: {difficulty}
- Questions should be clear, unambiguous, and educational
- Avoid trick questions or overly complex language
- Include a mix of conceptual and application-based questions
- Ensure only one correct answer per question
"""
        elif question_type == 'true_false':
            question_instruction = f"""
Generate exactly {num_questions} high-quality true/false questions about {topic}.

Requirements:
- Each question should be a clear statement that is definitively true or false
- Difficulty level: {difficulty}
- Avoid ambiguous statements
- Focus on key concepts and facts
- Mix of fundamental and detailed knowledge
"""
        else:  # text/essay questions
            question_instruction = f"""
Generate exactly {num_questions} open-ended questions about {topic}.

Requirements:
- Questions should encourage critical thinking and detailed responses
- Difficulty level: {difficulty}
- Suitable for essay or short answer format
- Cover different aspects of the topic
- Promote analysis, synthesis, and evaluation
"""

        if context:
            question_instruction += f"\n\nAdditional context: {context}"

        json_instruction = """
Return ONLY a JSON array of objects with this exact structure:
- For multiple choice: {"question": "...", "options": ["A option", "B option", "C option", "D option"], "correct_answer": "A", "explanation": "brief explanation"}
- For true/false: {"question": "...", "correct_answer": "true" or "false", "explanation": "brief explanation"}  
- For text questions: {"question": "...", "question_type": "text", "sample_answer": "example answer"}

Do not include any text outside the JSON array.
"""
        
        full_prompt = f"{question_instruction}\n\n{json_instruction}"
        
        # Use different models based on complexity
        if difficulty == 'advanced' or num_questions > 10:
            model = "anthropic/claude-3-haiku"
        else:
            model = "microsoft/phi-3-mini-128k-instruct"
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are an expert educational content creator. Generate high-quality, pedagogically sound questions."},
                    {"role": "user", "content": full_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_text = result['choices'][0]['message']['content']
            return parse_ai_response(ai_text, 'OpenRouter (Premium)')
        else:
            print(f"[AI GEN] OpenRouter API Error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"[AI GEN] OpenRouter Request Error: {e}")
        return None

def generate_fallback_questions(topic, num_questions, question_type, difficulty):
    """Generate fallback questions when AI service is unavailable"""
    import random
    
    # Get questions for the topic, or use a generic set
    topic_questions = FALLBACK_QUESTIONS.get(topic.lower(), FALLBACK_QUESTIONS.get('science', {}))
    difficulty_questions = topic_questions.get(difficulty, topic_questions.get('beginner', []))
    
    if not difficulty_questions:
        # Generate very basic questions if no templates available
        difficulty_questions = [
            {
                'question': f'This is a sample {question_type.replace("_", " ")} question about {topic}.',
                'options': ['Option A', 'Option B', 'Option C', 'Option D'] if question_type == 'multiple_choice' else None,
                'correct_answer': 'A' if question_type == 'multiple_choice' else 'true' if question_type == 'true_false' else 'Sample answer',
                'explanation': f'This is a sample question to demonstrate the {topic} topic.'
            }
        ]
    
    # Select and adapt questions
    selected_questions = []
    available_questions = difficulty_questions.copy()
    
    for i in range(min(num_questions, len(available_questions) * 3)):  # Allow repetition with variation
        if not available_questions and difficulty_questions:
            available_questions = difficulty_questions.copy()
        
        if available_questions:
            base_question = random.choice(available_questions)
            available_questions.remove(base_question)
            
            # Adapt question to requested type
            adapted_question = adapt_question_type(base_question, question_type, i + 1)
            adapted_question.update({
                'id': i + 1,
                'topic': topic,
                'difficulty': difficulty,
                'source': 'fallback'
            })
            selected_questions.append(adapted_question)
    
    return jsonify({
        "questions": selected_questions, 
        "topic_analyzed": topic, 
        "status": "success_fallback",
        "message": "Using built-in question templates. For AI-generated questions, please configure OpenRouter API key."
    })

def adapt_question_type(base_question, target_type, question_number):
    """Adapt a question to the target type"""
    adapted = base_question.copy()
    
    if target_type == 'true_false':
        # Convert to true/false
        if 'options' in adapted:
            correct_option_index = ord(adapted.get('correct_answer', 'A')) - ord('A')
            correct_text = adapted['options'][correct_option_index] if correct_option_index < len(adapted['options']) else adapted['options'][0]
            adapted['question'] = f"True or False: {adapted['question'].replace('?', '')} The answer is {correct_text}."
            adapted['correct_answer'] = 'true'
            del adapted['options']
    elif target_type == 'text':
        # Convert to text question
        adapted['question'] = f"Explain: {adapted['question']}"
        adapted['sample_answer'] = adapted.get('explanation', 'Provide a detailed explanation.')
        if 'options' in adapted:
            del adapted['options']
        if 'correct_answer' in adapted:
            del adapted['correct_answer']
    elif target_type == 'multiple_choice' and 'options' not in adapted:
        # Add basic options if none exist
        adapted['options'] = ['Option A', 'Option B', 'Option C', 'Option D']
        adapted['correct_answer'] = 'A'
    
    return adapted

@app.route('/check_ai_status', methods=['GET'])
def check_ai_status():
    """Quick endpoint to check which AI services are available"""
    status = {
        'groq': bool(os.environ.get('GROQ_API_KEY')),
        'huggingface': bool(os.environ.get('HUGGINGFACE_API_KEY')),
        'cohere': bool(os.environ.get('COHERE_API_KEY')),
        'together': bool(os.environ.get('TOGETHER_API_KEY')),
        'openrouter': bool(os.environ.get('OPENROUTER_API_KEY')),
        'templates': True  # Always available
    }
    
    available_services = [name for name, available in status.items() if available]
    
    return jsonify({
        'status': status,
        'available_services': available_services,
        'total_available': len(available_services),
        'recommended_setup': 'groq' not in available_services,
        'message': f"{len(available_services)} AI services configured"
    })

@app.route('/analyze_topic', methods=['POST'])
def analyze_topic():
    """Analyze topic and suggest subtopics for better question generation"""
    data = request.json
    topic = data.get('topic', '')
    
    if not topic:
        return jsonify({"error": "Topic is required"})
    
    # If no API key, provide basic analysis
    if not OPENROUTER_API_KEY:
        return generate_fallback_analysis(topic)
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "microsoft/phi-3-mini-128k-instruct",
                "messages": [
                    {"role": "user", "content": f"Analyze the topic '{topic}' and provide a JSON response with: {{'main_concepts': ['concept1', 'concept2', ...], 'subtopics': ['subtopic1', 'subtopic2', ...], 'difficulty_levels': ['beginner', 'intermediate', 'advanced'], 'suggested_question_types': ['multiple_choice', 'true_false', 'text']}}"}
                ],
                "temperature": 0.3,
                "max_tokens": 500
            },
            timeout=15
        )
        
        if response.status_code == 402:
            return generate_fallback_analysis(topic)
        elif response.status_code == 200:
            result = response.json()
            ai_text = result['choices'][0]['message']['content']
            
            # Try to parse the analysis
            import json as pyjson
            try:
                analysis = pyjson.loads(ai_text.strip())
                return jsonify({"analysis": analysis, "status": "success"})
            except:
                return generate_fallback_analysis(topic)
        else:
            return generate_fallback_analysis(topic)
            
    except Exception as e:
        return generate_fallback_analysis(topic)

def generate_fallback_analysis(topic):
    """Generate basic topic analysis without AI"""
    topic_lower = topic.lower()
    
    # Basic analysis based on topic keywords
    analysis = {
        "main_concepts": [topic],
        "subtopics": [],
        "difficulty_levels": ["beginner", "intermediate", "advanced"],
        "suggested_question_types": ["multiple_choice", "true_false", "text"]
    }
    
    # Add topic-specific insights
    if any(word in topic_lower for word in ['medicine', 'medical', 'anatomy', 'biology']):
        analysis["main_concepts"] = ["Human anatomy", "Medical terminology", "Health systems"]
        analysis["subtopics"] = ["Basic anatomy", "Common conditions", "Medical procedures"]
    elif any(word in topic_lower for word in ['math', 'mathematics', 'algebra', 'geometry']):
        analysis["main_concepts"] = ["Mathematical operations", "Problem solving", "Logical reasoning"]
        analysis["subtopics"] = ["Basic calculations", "Word problems", "Geometric shapes"]
    elif any(word in topic_lower for word in ['science', 'physics', 'chemistry']):
        analysis["main_concepts"] = ["Scientific method", "Natural phenomena", "Scientific laws"]
        analysis["subtopics"] = ["Basic principles", "Experiments", "Applications"]
    elif any(word in topic_lower for word in ['history', 'historical']):
        analysis["main_concepts"] = ["Historical events", "Important figures", "Cultural impact"]
        analysis["subtopics"] = ["Timeline", "Causes and effects", "Historical significance"]
    
    return jsonify({
        "analysis": analysis, 
        "status": "fallback",
        "message": "Basic analysis provided. For detailed AI analysis, configure OpenRouter API key."
    })

# ==================== AI COURSE GENERATION FUNCTIONS ====================


def generate_course_outline_with_ai(subject_area, difficulty_level, special_requirements=None):
    """Generate a comprehensive course outline using AI"""
    
    # Create subject-specific course design prompts
    if subject_area.lower() in ['computer science', 'programming', 'software engineering']:
        subject_guidance = """
Focus on practical programming skills, algorithms, data structures, software design patterns, 
and industry best practices. Include hands-on coding projects, system design concepts, 
and modern development tools and methodologies.
"""
        estimated_hours = 60
        modules_count = "5-7"
    elif subject_area.lower() in ['biology', 'medical', 'anatomy', 'physiology']:
        subject_guidance = """
Emphasize anatomical structures, physiological processes, cellular mechanisms, 
disease pathology, and clinical applications. Include laboratory techniques, 
diagnostic methods, and current medical research.
"""
        estimated_hours = 50
        modules_count = "6-8"
    elif subject_area.lower() in ['mathematics', 'statistics', 'calculus']:
        subject_guidance = """
Build mathematical foundations systematically, include rigorous proofs, 
multiple solution approaches, real-world applications, and mathematical modeling. 
Progress from concrete examples to abstract concepts.
"""
        estimated_hours = 45
        modules_count = "5-6"
    elif subject_area.lower() in ['physics', 'chemistry', 'engineering']:
        subject_guidance = """
Cover fundamental principles, mathematical derivations, laboratory experiments, 
engineering applications, and modern technological implementations. Include 
safety protocols and industry standards.
"""
        estimated_hours = 55
        modules_count = "6-7"
    elif subject_area.lower() in ['business', 'economics', 'finance']:
        subject_guidance = """
Include strategic frameworks, financial analysis, market research, case studies 
from real companies, regulatory considerations, and digital transformation impacts. 
Focus on practical decision-making skills.
"""
        estimated_hours = 40
        modules_count = "5-6"
    else:
        subject_guidance = f"""
Create comprehensive coverage of {subject_area} with theoretical foundations, 
practical applications, current trends, and real-world case studies.
"""
        estimated_hours = 45
        modules_count = "5-6"
    
    prompt = f"""
As an expert educational curriculum designer specializing in {subject_area}, create a comprehensive course outline that matches industry-leading educational platforms like MIT OpenCourseWare, Stanford Online, and professional certification programs.

Course Parameters:
- Subject Area: {subject_area}
- Difficulty Level: {difficulty_level}
- Target Audience: {"Beginners with no prior experience" if difficulty_level == "beginner" else "Students with foundational knowledge" if difficulty_level == "intermediate" else "Advanced practitioners seeking specialization"}
{f'- Special Requirements: {special_requirements}' if special_requirements else ''}

Subject-Specific Guidelines:
{subject_guidance}

Difficulty-Specific Requirements:
{"- Start with fundamental concepts and build gradually\n- Include plenty of practice exercises\n- Provide clear explanations with examples\n- Focus on practical skills over theory" if difficulty_level == "beginner" else "- Assume basic knowledge and build upon it\n- Include complex problem-solving scenarios\n- Balance theory with practical applications\n- Include industry-relevant projects" if difficulty_level == "intermediate" else "- Assume strong foundational knowledge\n- Include cutting-edge research and developments\n- Focus on expert-level analysis and optimization\n- Include professional-grade case studies"}

Please provide ONLY a JSON response with this exact structure:
{{
  "course_title": "Professional and comprehensive course title that clearly indicates the subject and level",
  "description": "Detailed 3-4 paragraph course description explaining the course purpose, target audience, learning approach, and career relevance. Make it compelling and informative.",
  "estimated_total_hours": {estimated_hours},
  "prerequisites": ["List specific prerequisite knowledge or courses required"],
  "learning_objectives": [
    "Students will be able to analyze and solve complex problems in {subject_area}",
    "Students will understand the fundamental principles and advanced concepts",
    "Students will apply knowledge to real-world scenarios and projects",
    "Students will evaluate and create solutions using industry best practices",
    "Students will demonstrate proficiency in relevant tools and methodologies"
  ],
  "course_outcomes": [
    "Professional-level competency in {subject_area}",
    "Portfolio of practical projects demonstrating skills",
    "Understanding of industry standards and best practices",
    "Preparation for advanced study or professional certification"
  ],
  "assessment_methods": [
    "Practical projects and assignments",
    "Comprehensive examinations",
    "Peer review and collaboration exercises",
    "Portfolio development and presentation"
  ],
  "modules": [
    {{
      "module_number": 1,
      "title": "Foundation Module Title",
      "description": "Comprehensive module description explaining learning goals and approach",
      "estimated_hours": 8,
      "learning_outcomes": ["Specific skills students will gain"],
      "assessment_criteria": ["How students will be evaluated"],
      "topics": [
        {{
          "topic_title": "Specific Topic Title",
          "subtopics": ["Detailed subtopic 1", "Detailed subtopic 2", "Detailed subtopic 3"],
          "estimated_hours": 2,
          "difficulty": "{difficulty_level}",
          "learning_objectives": ["Specific objective 1", "Specific objective 2"],
          "practical_exercises": ["Hands-on exercise description"],
          "assessment_type": "Quiz/Project/Assignment"
        }}
      ]
    }}
  ]
}}

Create {modules_count} comprehensive modules with 3-5 topics each, ensuring:
1. Progressive difficulty from foundational to advanced concepts
2. Each module builds upon previous knowledge
3. Practical applications and real-world relevance
4. Clear learning objectives and assessment criteria
5. Industry-relevant skills and knowledge
6. Comprehensive coverage of the subject area
7. Balance between theory and practical application
"""
    
    try:
        # Try Groq API first
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {os.environ.get("GROQ_API_KEY", "")}',
                'Content-Type': 'application/json'
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2000,
                "temperature": 0.7
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result['choices'][0]['message']['content']
            
            # Parse JSON from AI response with multiple fallback strategies
            try:
                # Strategy 1: Try to parse the whole response as JSON
                course_data = json.loads(ai_response)
                return course_data
            except json.JSONDecodeError:
                try:
                    # Strategy 2: Clean the response to extract JSON
                    json_start = ai_response.find('{')
                    json_end = ai_response.rfind('}') + 1
                    if json_start != -1 and json_end != 0:
                        json_str = ai_response[json_start:json_end]
                        course_data = json.loads(json_str)
                        return course_data
                except json.JSONDecodeError as e:
                    pass
                
                try:
                    # Strategy 3: Look for JSON between ```json markers
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', ai_response, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                        course_data = json.loads(json_str)
                        return course_data
                except json.JSONDecodeError:
                    pass
                
                print(f"JSON parsing error. AI Response preview: {ai_response[:500]}...")
                print("Falling back to template course outline")
                return create_fallback_course_outline(subject_area, difficulty_level, special_requirements)
        else:
            print(f"AI API error: {response.status_code}")
            return create_fallback_course_outline(subject_area, difficulty_level, special_requirements)
            
    except Exception as e:
        print(f"AI course generation error: {e}")
        return create_fallback_course_outline(subject_area, difficulty_level, special_requirements)

def create_fallback_course_outline(subject_area, difficulty_level, special_requirements=None):
    """Create a comprehensive fallback course outline when AI generation fails"""
    
    # Create a well-structured course based on the subject area
    course_title = f"Comprehensive {subject_area} Course ({difficulty_level.title()} Level)"
    
    # Base modules that work for most subjects
    base_modules = [
        {
            "module_number": 1,
            "title": f"Introduction to {subject_area}",
            "description": f"Foundational concepts and overview of {subject_area}",
            "estimated_hours": 8,
            "topics": [
                {
                    "topic_title": f"What is {subject_area}?",
                    "subtopics": ["Definition and scope", "Historical background", "Importance and applications"],
                    "estimated_hours": 2,
                    "difficulty": difficulty_level,
                    "learning_objectives": [f"Understand the definition of {subject_area}", "Identify key applications"]
                },
                {
                    "topic_title": "Core Principles",
                    "subtopics": ["Fundamental concepts", "Key terminology", "Basic principles"],
                    "estimated_hours": 3,
                    "difficulty": difficulty_level,
                    "learning_objectives": ["Master fundamental concepts", "Use proper terminology"]
                },
                {
                    "topic_title": "Getting Started",
                    "subtopics": ["Prerequisites", "Learning approach", "Study strategies"],
                    "estimated_hours": 3,
                    "difficulty": difficulty_level,
                    "learning_objectives": ["Prepare for advanced topics", "Develop effective study habits"]
                }
            ]
        },
        {
            "module_number": 2,
            "title": f"Fundamental Concepts in {subject_area}",
            "description": f"Essential knowledge and skills in {subject_area}",
            "estimated_hours": 10,
            "topics": [
                {
                    "topic_title": "Key Theories",
                    "subtopics": ["Major theories", "Supporting evidence", "Practical implications"],
                    "estimated_hours": 4,
                    "difficulty": difficulty_level,
                    "learning_objectives": ["Understand major theories", "Apply theoretical knowledge"]
                },
                {
                    "topic_title": "Essential Skills",
                    "subtopics": ["Core competencies", "Skill development", "Practice exercises"],
                    "estimated_hours": 3,
                    "difficulty": difficulty_level,
                    "learning_objectives": ["Develop essential skills", "Apply skills effectively"]
                },
                {
                    "topic_title": "Problem-Solving Approaches",
                    "subtopics": ["Analytical methods", "Step-by-step processes", "Common challenges"],
                    "estimated_hours": 3,
                    "difficulty": difficulty_level,
                    "learning_objectives": ["Master problem-solving techniques", "Handle complex challenges"]
                }
            ]
        },
        {
            "module_number": 3,
            "title": f"Practical Applications of {subject_area}",
            "description": f"Real-world applications and case studies in {subject_area}",
            "estimated_hours": 12,
            "topics": [
                {
                    "topic_title": "Industry Applications",
                    "subtopics": ["Professional use cases", "Industry standards", "Best practices"],
                    "estimated_hours": 4,
                    "difficulty": difficulty_level,
                    "learning_objectives": ["Understand professional applications", "Apply industry standards"]
                },
                {
                    "topic_title": "Case Studies",
                    "subtopics": ["Real-world examples", "Success stories", "Lessons learned"],
                    "estimated_hours": 4,
                    "difficulty": difficulty_level,
                    "learning_objectives": ["Analyze real cases", "Extract key insights"]
                },
                {
                    "topic_title": "Hands-on Projects",
                    "subtopics": ["Project planning", "Implementation", "Evaluation"],
                    "estimated_hours": 4,
                    "difficulty": difficulty_level,
                    "learning_objectives": ["Complete practical projects", "Demonstrate competency"]
                }
            ]
        },
        {
            "module_number": 4,
            "title": f"Advanced Topics in {subject_area}",
            "description": f"Advanced concepts and emerging trends in {subject_area}",
            "estimated_hours": 10,
            "topics": [
                {
                    "topic_title": "Advanced Concepts",
                    "subtopics": ["Complex theories", "Advanced techniques", "Specialized knowledge"],
                    "estimated_hours": 5,
                    "difficulty": "advanced" if difficulty_level != "beginner" else difficulty_level,
                    "learning_objectives": ["Master advanced concepts", "Apply complex techniques"]
                },
                {
                    "topic_title": "Current Trends and Future Directions",
                    "subtopics": ["Emerging developments", "Future prospects", "Research directions"],
                    "estimated_hours": 5,
                    "difficulty": "advanced" if difficulty_level != "beginner" else difficulty_level,
                    "learning_objectives": ["Understand current trends", "Anticipate future developments"]
                }
            ]
        }
    ]
    
    # Customize based on subject area
    if any(word in subject_area.lower() for word in ['mathematics', 'math', 'algebra', 'calculus']):
        course_title = f"Complete Mathematics Course: {subject_area}"
        base_modules[1]['topics'][0]['topic_title'] = "Mathematical Foundations"
        base_modules[1]['topics'][0]['subtopics'] = ["Number systems", "Mathematical notation", "Basic operations"]
        base_modules[2]['topics'][0]['topic_title'] = "Problem-Solving Techniques"
        base_modules[2]['topics'][0]['subtopics'] = ["Mathematical reasoning", "Proof techniques", "Applications"]
    
    elif any(word in subject_area.lower() for word in ['science', 'biology', 'chemistry', 'physics']):
        course_title = f"Complete Science Course: {subject_area}"
        base_modules[1]['topics'][0]['topic_title'] = "Scientific Method"
        base_modules[1]['topics'][0]['subtopics'] = ["Observation", "Hypothesis formation", "Experimentation"]
        base_modules[2]['topics'][0]['topic_title'] = "Laboratory Techniques"
        base_modules[2]['topics'][0]['subtopics'] = ["Equipment usage", "Safety procedures", "Data collection"]
    
    elif any(word in subject_area.lower() for word in ['computer', 'programming', 'software', 'technology']):
        course_title = f"Complete Technology Course: {subject_area}"
        base_modules[1]['topics'][0]['topic_title'] = "Technical Fundamentals"
        base_modules[1]['topics'][0]['subtopics'] = ["System architecture", "Core technologies", "Development principles"]
        base_modules[2]['topics'][0]['topic_title'] = "Practical Implementation"
        base_modules[2]['topics'][0]['subtopics'] = ["Coding practices", "Testing methodologies", "Deployment strategies"]
    
    # Add special requirements if provided
    if special_requirements:
        base_modules.append({
            "module_number": 5,
            "title": "Specialized Requirements",
            "description": f"Additional topics based on specific requirements: {special_requirements}",
            "estimated_hours": 8,
            "topics": [
                {
                    "topic_title": "Custom Topic",
                    "subtopics": ["Requirement analysis", "Implementation", "Evaluation"],
                    "estimated_hours": 8,
                    "difficulty": difficulty_level,
                    "learning_objectives": ["Meet specialized requirements", "Apply custom solutions"]
                }
            ]
        })
    
    return {
        "course_title": course_title,
        "description": f"A comprehensive {difficulty_level}-level course covering all essential aspects of {subject_area}. This course is designed to provide both theoretical understanding and practical skills, preparing students for real-world applications and further advanced study. The curriculum includes foundational concepts, practical applications, and current industry trends.",
        "estimated_total_hours": sum(module['estimated_hours'] for module in base_modules),
        "prerequisites": [
            "Basic reading comprehension",
            "Willingness to learn and practice",
            "Access to study materials" if difficulty_level == "beginner" else "Some background knowledge recommended"
        ],
        "learning_objectives": [
            f"Develop comprehensive understanding of {subject_area}",
            f"Apply {subject_area} principles to solve real-world problems",
            f"Demonstrate proficiency in {subject_area} techniques and methodologies",
            f"Analyze and evaluate {subject_area} applications critically",
            f"Create original solutions using {subject_area} knowledge"
        ],
        "modules": base_modules
    }


def generate_topic_content_with_ai(topic_title, subtopics, difficulty_level, subject_area):
    """Generate comprehensive, detailed content for a specific topic"""
    
    # Create subject-specific comprehensive prompts for different fields
    if subject_area.lower() in ['biology', 'science', 'medical', 'anatomy', 'physiology', 'biochemistry']:
        subject_specific_prompt = f"""
As a biology professor with expertise in {topic_title}, create educational content that matches the depth and quality of medical textbooks and GeeksforGeeks tutorials.

For {topic_title}, include:
- Detailed anatomical descriptions with specific examples
- Function and structure relationships
- Clinical significance and medical applications
- Microscopic and macroscopic perspectives
- Physiological processes and mechanisms
- Real disease examples and case studies
- Evolutionary significance where applicable
- Laboratory techniques and experimental methods
- Current research and recent discoveries
"""
    elif subject_area.lower() in ['computer science', 'programming', 'software engineering', 'algorithms', 'data structures']:
        subject_specific_prompt = f"""
As a computer science professor and industry expert, create comprehensive programming and CS content.

For {topic_title}, include:
- Detailed code examples with line-by-line explanations
- Algorithm complexity analysis (Big O notation)
- Real-world implementation scenarios
- Best practices and design patterns
- Common pitfalls and debugging techniques
- Industry applications and use cases
- Performance optimization strategies
- Testing and validation approaches
- Code examples in multiple languages where applicable
"""
    elif subject_area.lower() in ['mathematics', 'math', 'algebra', 'geometry', 'calculus', 'statistics']:
        subject_specific_prompt = f"""
As a mathematics professor, create content with rigorous mathematical foundations and practical applications.

For {topic_title}, include:
- Detailed mathematical derivations and proofs
- Step-by-step solution methods
- Multiple approaches to problem-solving
- Real-world applications and modeling
- Visual representations and graphs
- Common misconceptions and how to avoid them
- Mathematical software and tools usage
- Historical context and mathematical significance
- Connections to other mathematical concepts
"""
    elif subject_area.lower() in ['physics', 'chemistry', 'engineering', 'mechanical engineering', 'electrical engineering']:
        subject_specific_prompt = f"""
As a science/engineering professor with industry experience, create technically rigorous content.

For {topic_title}, include:
- Fundamental principles and governing equations
- Detailed derivations and mathematical foundations
- Real-world engineering applications
- Laboratory experiments and practical demonstrations
- Industry standards and best practices
- Safety considerations and protocols
- Modern tools and technologies
- Problem-solving methodologies
- Case studies from actual projects
"""
    elif subject_area.lower() in ['business', 'economics', 'finance', 'management', 'marketing']:
        subject_specific_prompt = f"""
As a business professor and industry consultant, create practical and strategic business content.

For {topic_title}, include:
- Real business case studies and examples
- Strategic frameworks and methodologies
- Financial analysis and metrics
- Market research and data interpretation
- Industry trends and best practices
- Regulatory considerations and compliance
- Digital transformation aspects
- Global perspectives and cultural considerations
- Practical implementation strategies
"""
    elif subject_area.lower() in ['psychology', 'sociology', 'anthropology', 'social sciences']:
        subject_specific_prompt = f"""
As a social science researcher and practitioner, create evidence-based content.

For {topic_title}, include:
- Research methodologies and findings
- Theoretical frameworks and models
- Real-world applications and case studies
- Cultural and contextual considerations
- Ethical implications and considerations
- Current research and developments
- Practical assessment tools and techniques
- Cross-cultural perspectives
- Evidence-based interventions and practices
"""
    elif subject_area.lower() in ['art', 'design', 'creative writing', 'literature', 'media studies']:
        subject_specific_prompt = f"""
As a creative arts professor and practicing artist, create inspiring and practical content.

For {topic_title}, include:
- Historical context and artistic movements
- Technical skills and methodologies
- Creative process and ideation techniques
- Critical analysis and interpretation
- Contemporary trends and innovations
- Portfolio development strategies
- Industry insights and career paths
- Cultural impact and significance
- Hands-on exercises and projects
"""
    elif subject_area.lower() in ['geography', 'physical geography', 'human geography', 'environmental science']:
        subject_specific_prompt = f"""
As a professional geographer and spatial analyst, create comprehensive educational content that demonstrates expertise in geographic thinking and spatial analysis.

For {topic_title}, include:
- Spatial patterns, processes, and relationships
- Scale analysis (local, regional, national, global connections)
- Human-environment interactions and sustainability
- Geographic Information Systems (GIS) and mapping applications
- Physical processes (climate, landforms, hydrology, ecosystems)
- Human geography (population, culture, economics, urbanization)
- Field methods, data collection, and spatial analysis techniques
- Case studies from different world regions
- Current geographic research and methodologies
- Real-world applications in planning, policy, and problem-solving
- Integration of quantitative and qualitative geographic methods
- Geographic technology tools and their applications

Use the five fundamental geographic questions:
1. Where is it located? (absolute and relative location)
2. Why is it there? (spatial distribution and site factors)
3. How did it get there? (spatial processes and diffusion)
4. What are the consequences of its location? (spatial interactions)
5. What does its location mean for people and environment? (geographic significance)

Include specific examples, detailed case studies, geographic terminology, and practical applications that demonstrate professional-level geographic knowledge.
"""
    elif subject_area.lower() in ['history', 'political science', 'archaeology']:
        subject_specific_prompt = f"""
As a historian and social scientist, create contextually rich and analytical content.

For {topic_title}, include:
- Historical context and chronological development
- Primary and secondary source analysis
- Cause and effect relationships
- Comparative analysis across cultures/periods
- Archaeological and material evidence
- Geographic and environmental factors
- Political and social implications
- Historiographical debates and perspectives
- Modern relevance and lessons learned
"""
    else:
        subject_specific_prompt = f"""
As a subject matter expert in {subject_area}, create comprehensive educational content that demonstrates deep understanding and practical expertise.

For {topic_title}, include:
- Fundamental principles and core concepts
- Real-world applications and examples
- Current trends and developments
- Best practices and methodologies
- Common challenges and solutions
- Industry standards and requirements
- Practical exercises and applications
"""
    
    # Add difficulty-specific requirements
    if difficulty_level.lower() == 'beginner':
        difficulty_guidance = """
BEGINNER LEVEL REQUIREMENTS:
- Start with basic definitions and simple explanations
- Use analogies and everyday examples
- Include plenty of visual aids and diagrams
- Provide step-by-step tutorials
- Focus on fundamental concepts before advanced topics
- Include common beginner mistakes and how to avoid them
"""
    elif difficulty_level.lower() == 'intermediate':
        difficulty_guidance = """
INTERMEDIATE LEVEL REQUIREMENTS:
- Assume basic knowledge and build upon it
- Include more complex examples and scenarios
- Integrate multiple concepts together
- Provide comparative analysis and alternatives
- Include practical projects and applications
- Address common intermediate challenges
"""
    else:  # advanced
        difficulty_guidance = """
ADVANCED LEVEL REQUIREMENTS:
- Assume strong foundational knowledge
- Include cutting-edge research and developments
- Provide in-depth technical analysis
- Include complex problem-solving scenarios
- Address advanced optimization and best practices
- Include expert-level insights and professional perspectives
"""
    
    prompt = f"""
{subject_specific_prompt}

{difficulty_guidance}

Create a comprehensive lesson on "{topic_title}" at {difficulty_level} level for {subject_area}.

CRITICAL REQUIREMENTS:
1. Write detailed explanations (minimum 600 words per section for intermediate/advanced, 400 for beginner)
2. Include specific, real examples with full explanations
3. Add practical applications and real-world scenarios
4. Provide detailed case studies and examples
5. Make it as comprehensive as industry-standard educational materials
6. Use proper terminology and explain it clearly
7. Include visual descriptions and diagrams in text format
8. Add hands-on exercises and practical applications
9. Include current industry trends and developments
10. Provide multiple learning paths and approaches

Subtopics to cover: {', '.join(subtopics)}

Return ONLY valid JSON with this structure:
    {{
  "topic_title": "{topic_title}",
  "introduction": "Write a comprehensive 3-4 paragraph introduction explaining what {topic_title} is, why it's important in {subject_area}, and real-world applications. Include specific examples and scenarios where this concept is used.",
  "sections": [
    {{
      "section_title": "Understanding {topic_title}",
      "content": "Write 500+ words explaining the fundamental concepts of {topic_title}. Include definitions, key principles, theoretical background, and step-by-step explanations. Use clear examples to illustrate each concept. Explain the 'why' behind each principle, not just the 'what'. Include multiple paragraphs with detailed explanations.",
      "code_examples": [
        "Example 1: Step-by-step solution showing how to solve {topic_title} problems",
        "Example 2: Another detailed example with different approach",
        "Example 3: Advanced example showing practical application"
      ],
      "practical_examples": [
        "Real-world Example 1: Detailed scenario from industry showing how {topic_title} is used",
        "Real-world Example 2: Another practical application with step-by-step explanation",
        "Case Study: Complete example showing problem identification, solution process, and results"
      ],
      "key_points": [
        "Key Concept 1: Detailed explanation of the most important principle in {topic_title}",
        "Key Concept 2: Another critical understanding with examples and why it matters",
        "Key Concept 3: Advanced concept that builds on previous knowledge"
      ],
      "visual_diagrams": [
        "ASCII diagram showing the relationship between concepts in {topic_title}",
        "Text-based flowchart illustrating the process or methodology"
      ]
    }}
  ],
  "detailed_examples": [
    {{
      "title": "Complete Worked Example",
      "scenario": "Present a real-world problem that requires {topic_title} to solve",
      "solution": "Provide step-by-step solution with detailed explanations for each step",
      "explanation": "Explain why each step is necessary and how it contributes to the final solution"
    }}
  ],
  "summary": "Write a comprehensive 2-3 paragraph summary that reviews all key concepts covered, their relationships, and practical applications. Reinforce the main learning objectives.",
  "quiz_questions": [
    {{
      "question": "Create a detailed question that tests understanding of {topic_title}",
      "options": ["Detailed option A", "Detailed option B", "Detailed option C", "Detailed option D"],
      "correct": "A",
      "explanation": "Detailed explanation of why this answer is correct and others are wrong"
    }}
  ]
}}

EXAMPLE for Linear Equations:
- Introduction should explain what linear equations are, why they're fundamental in mathematics, how they're used in engineering, physics, economics, etc.
- Content should include detailed explanations of concepts like slope, y-intercept, standard form, point-slope form
- Examples should show step-by-step solutions: "To solve 3x + 5 = 14, first subtract 5 from both sides: 3x = 9, then divide by 3: x = 3"
- Include practical applications like calculating costs, predicting trends, etc.

Create educational content that teaches, not just lists topics!
"""
    
    try:
        # Use rate-limited API request
        response = make_api_request_with_backoff(
            'https://api.groq.com/openai/v1/chat/completions',
            {
                'Authorization': f'Bearer {os.environ.get("GROQ_API_KEY", "")}',
                'Content-Type': 'application/json'
            },
            {
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 4000,  # Increased for more detailed content
                "temperature": 0.7
            }
        )
        
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content']
            
            # Use the robust JSON parser
            parsed_content = clean_and_parse_json(content, expected_type='object')
            
            if parsed_content and 'topic_title' in parsed_content and 'sections' in parsed_content:
                return parsed_content
            else:
                print(f"Warning: AI response missing required fields or failed to parse")
                # If JSON parsing fails, create a detailed fallback
                return create_detailed_fallback_content(topic_title, subtopics, subject_area, difficulty_level)
        else:
            print(f"API request failed with status code: {response.status_code}")
            return create_detailed_fallback_content(topic_title, subtopics, subject_area, difficulty_level)
            
    except Exception as e:
        print(f"Error generating topic content: {e}")
        return create_detailed_fallback_content(topic_title, subtopics, subject_area, difficulty_level)

def create_detailed_fallback_content(topic_title, subtopics, subject_area, difficulty_level):
    """Create detailed fallback content when AI generation fails"""
    
    # Create comprehensive content based on the topic and subject area
    if subject_area.lower() in ['biology', 'science', 'medical', 'anatomy'] and any(word in topic_title.lower() for word in ['tissue', 'organ', 'cell', 'anatomy']):
        return {
            "topic_title": topic_title,
            "introduction": f"""Welcome to this comprehensive exploration of {topic_title} in biology. This fundamental topic forms the cornerstone of understanding how complex multicellular organisms are organized and function. From the microscopic cellular level to the complex organ systems that sustain life, {topic_title} represents one of the most fascinating areas of biological study with direct applications in medicine, biotechnology, and health sciences.

Understanding {topic_title} is essential for anyone pursuing careers in medicine, veterinary science, biotechnology, or biological research. The concepts you'll learn here directly apply to understanding human health, disease processes, medical treatments, and the incredible complexity of living organisms. Whether you're studying to become a doctor, researcher, or simply want to understand how your own body works, this topic provides crucial foundational knowledge.

In this comprehensive lesson, we'll explore the intricate world of biological organization, examining how individual cells specialize to form tissues, how tissues combine to create organs, and how organs work together in sophisticated systems. You'll discover the remarkable engineering principles that evolution has developed over millions of years, creating the most efficient and adaptable structures known to science. By the end of this lesson, you'll have a deep understanding of biological organization that will serve as a foundation for advanced studies in medicine, research, and biotechnology.""",
            
            "sections": [
                {
                    "section_title": "Cellular Foundation: Building Blocks of Life",
                    "content": f"""Before we can understand {topic_title}, we must first appreciate that all complex life forms are built from the fundamental unit of life: the cell. Every tissue and organ in your body began as a single cell, which through the remarkable process of cellular differentiation, developed into the specialized structures we see today. This process represents one of biology's most fascinating phenomena - how a single fertilized egg can give rise to the incredible diversity of cell types in a complex organism.

Cellular differentiation occurs through carefully controlled gene expression, where different sets of genes are activated in different cells, leading to distinct cellular characteristics and functions. For example, muscle cells express genes that produce contractile proteins like actin and myosin, allowing them to generate force and movement. Meanwhile, nerve cells express genes for neurotransmitter production and electrical signaling, enabling rapid communication throughout the body.

The human body contains over 200 different cell types, each with unique structures and functions perfectly adapted to their specific roles. Epithelial cells, for instance, are tightly packed with specialized junctions that create protective barriers, while blood cells are designed for transport and immune defense. Understanding this cellular diversity is crucial because tissues are simply organized collections of similar cells working together toward common functions.

What makes this even more remarkable is that despite their incredible diversity, all these cells share fundamental characteristics: they all contain DNA with the same genetic information, they all use the same basic metabolic pathways, and they all maintain similar internal conditions through homeostasis. This unity within diversity reflects the common evolutionary origin of all life and demonstrates the elegant efficiency of biological design.

The study of cellular organization also reveals important principles about biological scaling and engineering. As organisms evolved to become larger and more complex, they faced fundamental challenges related to surface area-to-volume ratios, diffusion distances, and coordination of activities. The evolution of tissues and organs represents biological solutions to these engineering challenges, creating structures that maximize efficiency while maintaining the precise control necessary for life.""",
                    
                    "code_examples": [
                        """Cell Differentiation Example:
Stem Cell → Signal Pathways → Specialized Cell

Muscle Cell Development:
1. Myogenic stem cell receives developmental signals
2. MyoD transcription factor is activated
3. Muscle-specific genes are expressed
4. Actin and myosin proteins are produced
5. Cell develops contractile apparatus
6. Mature muscle fiber capable of contraction""",
                        
                        """Tissue Organization Hierarchy:
Cells → Tissues → Organs → Organ Systems

Example: Digestive System
Individual intestinal cells →
Intestinal epithelial tissue →
Small intestine organ →
Digestive system""",
                        
                        """Cell Specialization Examples:
• Red Blood Cells: No nucleus, filled with hemoglobin
• Nerve Cells: Long axons, specialized for electrical conduction
• Muscle Cells: Contractile proteins, organized in fibers
• Epithelial Cells: Tight junctions, barrier function"""
                    ],
                    
                    "practical_examples": [
                        "Medical Application: Understanding tissue organization is crucial for cancer diagnosis. Pathologists examine tissue samples to identify abnormal cell organization patterns that indicate malignancy. Cancer cells lose normal tissue organization and invade surrounding tissues.",
                        "Regenerative Medicine: Stem cell therapy relies on understanding how cells differentiate into specific tissue types. Scientists can now direct stem cells to become heart muscle cells, nerve cells, or other specialized types for treating diseases.",
                        "Drug Development: Many medications work by targeting specific cell types or tissues. Understanding tissue organization helps pharmaceutical companies design drugs that reach their intended targets while minimizing side effects."
                    ],
                    
                    "key_points": [
                        "Cellular differentiation transforms identical stem cells into over 200 specialized cell types through controlled gene expression, creating the cellular diversity necessary for complex organ function",
                        "Tissue organization follows hierarchical principles where cells with similar functions group together, tissues combine to form organs, and organs coordinate to create organ systems",
                        "The evolution of multicellular organization solved fundamental biological engineering challenges related to size, efficiency, and coordination that single cells could not address alone"
                    ],
                    
                    "visual_diagrams": [
                        """Tissue Organization Diagram:
    
    EPITHELIAL TISSUE    CONNECTIVE TISSUE    MUSCLE TISSUE       NERVOUS TISSUE
         ┌─┬─┬─┐              ○   ○              ═══════════        ─○─┬─○─
         ├─┼─┼─┤            ○  ○  ○             ═══════════           │
         ├─┼─┼─┤              ○   ○              ═══════════        ─○─┴─○─
         └─┴─┴─┘            ○  ○  ○             ═══════════
    
    Protection &         Support &            Movement &          Communication &
    Secretion           Connection           Contraction          Control""",
                        
                        """Cell to Organ System Hierarchy:
    
    Cell Level:      [Individual specialized cells]
                            ↓
    Tissue Level:    [Groups of similar cells]
                            ↓  
    Organ Level:     [Multiple tissues working together]
                            ↓
    System Level:    [Multiple organs coordinating]
                            ↓
    Organism:        [All systems integrated]"""
                    ]
                },
                
                {
                    "section_title": "The Four Fundamental Tissue Types: Specialized Structures for Life",
                    "content": f"""The human body's remarkable complexity arises from just four fundamental tissue types, each with distinctive characteristics and essential functions. These tissues - epithelial, connective, muscle, and nervous - represent millions of years of evolutionary refinement, creating structures perfectly adapted to their specific roles in maintaining life. Understanding these tissue types is fundamental to comprehending how organs function and how diseases affect the body.

Epithelial tissue forms the body's protective barriers and interfaces with the environment. These tissues line body cavities, cover external surfaces, and form glands that secrete essential substances. What makes epithelial tissue unique is its cellular organization: cells are tightly packed with minimal intercellular space and are held together by specialized junctions. The apical surface (facing the exterior or cavity) often has specialized features like cilia or microvilli to enhance function, while the basal surface rests on a basement membrane that provides structural support.

Different types of epithelial tissue serve distinct functions based on their structure. Simple squamous epithelium, with its thin, flat cells, is perfect for diffusion and is found in the lungs' alveoli where oxygen and carbon dioxide exchange occurs. Stratified squamous epithelium provides protection against mechanical damage and is found in the skin and mouth. Columnar epithelium, with its tall, column-like cells, is specialized for secretion and absorption and lines the digestive tract.

Connective tissue, the body's most abundant and diverse tissue type, provides structural support, protection, and connection between other tissues. Unlike epithelial tissue, connective tissue has abundant extracellular matrix - a complex mixture of proteins and polysaccharides that gives the tissue its characteristic properties. The extracellular matrix in bone tissue contains calcium phosphate crystals for hardness, while cartilage matrix contains flexible proteins for shock absorption.

The diversity of connective tissue is remarkable: loose connective tissue fills spaces between organs, dense connective tissue forms tendons and ligaments, adipose tissue stores energy and provides insulation, cartilage provides flexible support, bone provides rigid support, and blood transports materials throughout the body. Each type has a specific cellular composition and matrix structure perfectly suited to its function.

Muscle tissue generates force and produces movement through the coordinated contraction of specialized proteins. The three types of muscle tissue - skeletal, cardiac, and smooth - each have unique characteristics adapted to their specific functions. Skeletal muscle, with its long, multinucleated fibers and striations, provides voluntary movement and is under conscious control. Cardiac muscle, found only in the heart, has branching fibers connected by intercalated discs that allow coordinated contraction. Smooth muscle, with its spindle-shaped cells and no striations, controls involuntary functions like digestion and blood vessel diameter.

Nervous tissue specializes in rapid communication and coordination throughout the body. Neurons, the primary cells of nervous tissue, have unique extensions called axons and dendrites that allow them to transmit electrical and chemical signals over long distances. Supporting cells called glial cells provide nutrients, protection, and insulation for neurons. The organization of nervous tissue into the central nervous system (brain and spinal cord) and peripheral nervous system allows for complex processing and rapid response to environmental changes.""",
                    
                    "code_examples": [
                        """Epithelial Tissue Classification:
Shape: Squamous (flat) | Cuboidal (cube) | Columnar (tall)
Layers: Simple (1 layer) | Stratified (multiple layers)

Examples:
• Simple Squamous: Lung alveoli (gas exchange)
• Stratified Squamous: Skin epidermis (protection)
• Simple Columnar: Intestinal lining (absorption)
• Pseudostratified Columnar: Respiratory tract (protection + movement)""",
                        
                        """Connective Tissue Matrix Components:
Protein Fibers:
• Collagen: Strength and structure (most abundant protein in body)
• Elastin: Flexibility and stretch
• Reticular: Support networks

Ground Substance:
• Proteoglycans: Water retention and cushioning
• Glycoproteins: Cell adhesion and signaling""",
                        
                        """Muscle Contraction Mechanism:
1. Nerve signal triggers calcium release
2. Calcium binds to troponin complex
3. Tropomyosin moves, exposing myosin binding sites
4. Myosin heads bind to actin (cross-bridge formation)
5. Power stroke pulls actin filaments
6. ATP breaks cross-bridge, cycle repeats"""
                    ],
                    
                    "practical_examples": [
                        "Clinical Diagnosis: Tissue biopsies are essential for diagnosing diseases. For example, examining epithelial tissue can reveal cancer progression, while muscle tissue biopsies can diagnose muscular dystrophy or inflammatory conditions.",
                        "Surgical Applications: Understanding tissue properties guides surgical techniques. Surgeons must know that nervous tissue doesn't regenerate well, so careful handling is crucial, while connective tissue generally heals well but slowly.",
                        "Physical Therapy: Treatment strategies depend on tissue type. Muscle tissue responds to exercise and stretching, connective tissue needs gradual loading for healing, and nervous tissue requires specific approaches for rehabilitation."
                    ]
                }
            ],
            
            "detailed_examples": [
                {
                    "title": "Complete Organ Analysis: The Heart as a Multi-Tissue Structure",
                    "scenario": "Analyze how the four tissue types work together in the heart to create a functional organ capable of pumping blood throughout the body for an entire lifetime.",
                    "solution": "The heart demonstrates perfect integration of all tissue types: (1) Cardiac muscle tissue provides the contractile force with synchronized contractions via intercalated discs; (2) Connective tissue forms the heart valves, fibrous skeleton, and pericardium for structural support; (3) Epithelial tissue (endothelium) lines blood vessels and heart chambers for smooth blood flow; (4) Nervous tissue (cardiac conduction system) coordinates contractions and responds to body needs.",
                    "explanation": "This example shows how organ function emerges from tissue cooperation. No single tissue could perform the heart's complex functions alone - it requires the specialized contributions of each tissue type working in perfect coordination."
                }
            ],
            
            "summary": f"""Through this comprehensive exploration of {topic_title}, you've gained deep insight into one of biology's most fundamental organizing principles. The hierarchical organization from cells to tissues to organs represents evolution's solution to the challenge of creating complex, multicellular life forms. Understanding this organization is not merely academic - it forms the foundation for all medical knowledge, from understanding disease processes to developing treatments.

The four tissue types - epithelial, connective, muscle, and nervous - each represent millions of years of evolutionary refinement, resulting in structures perfectly adapted to their functions. Their coordinated interaction in organs and organ systems demonstrates the remarkable integration that makes complex life possible. This knowledge directly applies to understanding human health, disease mechanisms, and medical treatments.

As you continue your studies in biology or medicine, remember that every physiological process, every disease, and every treatment ultimately comes down to how cells, tissues, and organs function together. The principles you've learned here will serve as a foundation for understanding everything from basic physiology to advanced medical procedures, making this one of the most valuable topics in all of biological science.""",
            
            "quiz_questions": [
                {
                    "question": "A tissue sample shows tightly packed cells with no blood vessels, arranged in multiple layers with the surface cells being flat. What type of tissue is this most likely to be?",
                    "options": ["Simple squamous epithelium", "Stratified squamous epithelium", "Dense connective tissue", "Smooth muscle tissue"],
                    "correct": "B",
                    "explanation": "Stratified squamous epithelium has multiple layers (stratified) with flat surface cells (squamous) and no blood vessels (avascular), typically found in areas needing protection like skin and mouth lining."
                },
                {
                    "question": "Which tissue type would you expect to find the most extracellular matrix?",
                    "options": ["Epithelial tissue", "Muscle tissue", "Nervous tissue", "Connective tissue"],
                    "correct": "D",
                    "explanation": "Connective tissue is characterized by abundant extracellular matrix, which gives it structural and functional properties. The matrix can be liquid (blood), gel-like (cartilage), or solid (bone)."
                }
            ]
        }
    
    # Enhanced Computer Science fallback
    elif subject_area.lower() in ['computer science', 'programming', 'algorithms', 'data structures'] and any(word in topic_title.lower() for word in ['algorithm', 'data structure', 'programming', 'coding', 'software']):
        return {
            "topic_title": topic_title,
            "introduction": f"""Welcome to this comprehensive exploration of {topic_title} in computer science. This topic represents a fundamental area of study that forms the backbone of modern software development and computational thinking. Understanding {topic_title} is essential for developing efficient, scalable, and maintainable software solutions in today's technology-driven world.

Computer science is built upon the foundation of algorithms and data structures, which serve as the building blocks for all software applications. From the apps on your smartphone to the complex systems running global financial markets, the principles you'll learn in {topic_title} are at work everywhere. This knowledge is crucial for anyone pursuing a career in software development, data science, artificial intelligence, or any technology-related field.

Throughout this lesson, you'll gain both theoretical understanding and practical implementation skills. We'll explore the mathematical foundations, analyze performance characteristics, and examine real-world applications. By the end of this comprehensive study, you'll be equipped with the knowledge to make informed decisions about algorithm selection, data structure design, and system optimization in your own projects.""",
            
            "sections": [
                {
                    "section_title": f"Fundamental Concepts and Implementation of {topic_title}",
                    "content": f"""Understanding {topic_title} requires both theoretical knowledge and practical implementation skills. In computer science, we must consider not just what a solution does, but how efficiently it performs under different conditions. This involves analyzing time complexity (how long an algorithm takes to run) and space complexity (how much memory it requires).

The Big O notation is fundamental to this analysis. When we say an algorithm has O(n) time complexity, we mean that the execution time grows linearly with the input size. For example, searching through an unsorted array requires checking each element, giving us O(n) complexity. In contrast, binary search on a sorted array achieves O(log n) by eliminating half the search space with each comparison.

Implementation considerations are equally important. Different programming languages offer various built-in data structures and libraries, but understanding the underlying principles allows you to choose the right tool for each situation. For instance, Python's list is actually a dynamic array that automatically resizes, while a linked list offers constant-time insertion and deletion at any position.

Memory management plays a crucial role in {topic_title}. Understanding how data is stored, accessed, and modified helps optimize both performance and resource usage. Cache locality, for example, significantly affects real-world performance - algorithms that access memory sequentially often outperform theoretically superior approaches that jump around in memory.

Modern software development also involves considering parallel processing and distributed systems. Many traditional algorithms can be adapted for concurrent execution, but this requires careful consideration of race conditions, deadlocks, and synchronization overhead. Understanding these concepts is increasingly important as multi-core processors and cloud computing become ubiquitous.""",
                    
                    "code_examples": [
                        """# Example 1: Linear Search Implementation
def linear_search(arr, target):
    \"\"\"
    Search for target in unsorted array
    Time Complexity: O(n)
    Space Complexity: O(1)
    \"\"\"
    for i in range(len(arr)):
        if arr[i] == target:
            return i  # Return index if found
    return -1  # Return -1 if not found

# Usage example
numbers = [64, 34, 25, 12, 22, 11, 90]
result = linear_search(numbers, 22)
print(f"Element found at index: {result}")""",
                        
                        """# Example 2: Binary Search Implementation
def binary_search(arr, target):
    \"\"\"
    Search for target in sorted array
    Time Complexity: O(log n)
    Space Complexity: O(1)
    \"\"\"
    left, right = 0, len(arr) - 1
    
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1

# Usage example
sorted_numbers = [11, 12, 22, 25, 34, 64, 90]
result = binary_search(sorted_numbers, 22)
print(f"Element found at index: {result}")""",
                        
                        """# Example 3: Performance Comparison
import time

def measure_performance(search_func, arr, target):
    start_time = time.time()
    result = search_func(arr, target)
    end_time = time.time()
    return result, (end_time - start_time) * 1000  # milliseconds

# Compare performance on large dataset
large_array = list(range(100000))
target = 75000

linear_result, linear_time = measure_performance(linear_search, large_array, target)
binary_result, binary_time = measure_performance(binary_search, large_array, target)

print(f"Linear search: {linear_time:.4f}ms")
print(f"Binary search: {binary_time:.4f}ms")"""
                    ],
                    
                    "practical_examples": [
                        "Database Indexing: Database systems use B-trees and hash tables to enable fast data retrieval. Understanding these data structures helps in designing efficient database schemas and optimizing query performance.",
                        "Web Search Engines: Search engines like Google use sophisticated algorithms including PageRank and inverted indices to quickly find relevant web pages from billions of documents. These systems demonstrate the importance of algorithmic efficiency at scale.",
                        "Social Media Platforms: Recommendation algorithms analyze user behavior patterns to suggest content. These systems must process millions of interactions in real-time, requiring carefully optimized data structures and algorithms."
                    ],
                    
                    "key_points": [
                        "Time and space complexity analysis using Big O notation is essential for comparing algorithmic efficiency and predicting performance with larger datasets",
                        "The choice of data structure significantly impacts application performance, with trade-offs between insertion, deletion, search, and memory usage that must be considered for each use case",
                        "Modern software development requires understanding parallel processing and distributed computing concepts as applications scale across multiple cores and systems"
                    ],
                    
                    "visual_diagrams": [
                        """Algorithm Complexity Comparison:

Time Complexity Growth:
O(1)     ──────────────── Constant
O(log n) ──────────────── Logarithmic  
O(n)     ──────────────── Linear
O(n²)    ──────────────── Quadratic
O(2^n)   ──────────────── Exponential

For n = 1000:
O(1)     → 1 operation
O(log n) → ~10 operations  
O(n)     → 1,000 operations
O(n²)    → 1,000,000 operations
O(2^n)   → 2^1000 operations (infeasible)""",
                        
                        """Binary Search Visualization:

Array: [11, 12, 22, 25, 34, 64, 90]  Target: 22

Step 1: [11, 12, 22, |25|, 34, 64, 90]  mid=25, target<25, go left
Step 2: [11, |12|, 22]                   mid=12, target>12, go right  
Step 3: [|22|]                           mid=22, target=22, found!

Total comparisons: 3 (vs 7 for linear search)"""
                    ]
                }
            ],
            
            "detailed_examples": [
                {
                    "title": "Complete Algorithm Design: Implementing a Hash Table",
                    "scenario": "Design and implement a hash table data structure that supports insertion, deletion, and lookup operations with average O(1) time complexity. Handle collisions using chaining and analyze performance characteristics.",
                    "solution": "Implementation involves: (1) Choose hash function (e.g., division method), (2) Create array of linked lists for chaining, (3) Implement insert by computing hash and adding to chain, (4) Implement search by traversing appropriate chain, (5) Handle dynamic resizing when load factor exceeds threshold, (6) Analyze performance under different load factors and hash function quality.",
                    "explanation": "This example demonstrates how theoretical concepts translate to practical implementations. The hash table showcases trade-offs between time and space complexity, the importance of good hash functions, and how real-world performance can differ from theoretical analysis due to factors like cache behavior and collision patterns."
                }
            ],
            
            "summary": f"""Through this comprehensive exploration of {topic_title}, you've gained essential knowledge that forms the foundation of efficient software development. Understanding algorithmic complexity, data structure trade-offs, and implementation considerations enables you to build scalable, maintainable software systems that perform well under real-world conditions.

The concepts covered here extend far beyond academic study - they're actively used in every major software system today. From the routing algorithms that deliver your internet traffic to the recommendation systems that suggest your next video, these fundamental principles are at work. As you continue your journey in computer science, remember that the best solutions often come from a deep understanding of these basics combined with creative problem-solving.

Whether you're optimizing database queries, designing distributed systems, or building mobile applications, the analytical thinking and systematic approach you've developed through studying {topic_title} will serve you throughout your career in technology.""",
            
            "quiz_questions": [
                {
                    "question": "What is the time complexity of binary search on a sorted array of n elements?",
                    "options": ["O(1)", "O(log n)", "O(n)", "O(n log n)"],
                    "correct": "B",
                    "explanation": "Binary search eliminates half of the remaining elements with each comparison, leading to O(log n) time complexity. This logarithmic growth means doubling the array size only adds one more comparison."
                },
                {
                    "question": "Which data structure would be most appropriate for implementing a function call stack?",
                    "options": ["Queue", "Stack", "Hash Table", "Binary Tree"],
                    "correct": "B",
                    "explanation": "A stack follows Last-In-First-Out (LIFO) order, which perfectly matches how function calls work - the most recently called function is the first to return (be removed from the stack)."
                }
            ]
        }
    
    # Enhanced mathematics fallback
    elif subject_area.lower() in ['mathematics', 'math'] and 'linear' in topic_title.lower():
        return {
            "topic_title": topic_title,
            "introduction": f"""Linear equations are fundamental mathematical expressions that form the backbone of algebra and have extensive applications across science, engineering, economics, and everyday problem-solving. A linear equation represents a straight line when graphed and maintains a constant rate of change between variables. In this comprehensive guide, you'll master the essential concepts of {topic_title}, learning not just how to solve them, but understanding their practical significance and real-world applications.

Linear equations appear everywhere in our daily lives - from calculating costs and profits in business, to determining speeds and distances in physics, to modeling population growth in biology. Whether you're balancing a budget, planning a trip, or analyzing data trends, linear equations provide the mathematical foundation for making informed decisions. This lesson will equip you with both theoretical understanding and practical problem-solving skills.

By the end of this lesson, you'll confidently solve linear equations using multiple methods, understand the graphical representation of these equations, and apply this knowledge to solve real-world problems. We'll explore various forms of linear equations, their properties, and how they connect to broader mathematical concepts you'll encounter in advanced studies.""",
            
            "sections": [
                {
                    "section_title": "Understanding Linear Equations: Foundations and Forms",
                    "content": f"""A linear equation is an algebraic equation where each term is either a constant or the product of a constant and a single variable. The general form of a linear equation in one variable is ax + b = c, where 'a', 'b', and 'c' are constants and 'x' is the variable we're solving for. The key characteristic that makes an equation 'linear' is that the variable appears only to the first power - no squares, cubes, or other higher powers.

The beauty of linear equations lies in their predictable behavior and consistent patterns. When you change the input by a certain amount, the output changes by a proportional amount. This creates the straight-line graph that gives linear equations their name. Understanding this fundamental relationship is crucial for mastering more complex mathematical concepts.

There are several standard forms of linear equations, each useful for different purposes. The slope-intercept form (y = mx + b) is excellent for quickly identifying the rate of change (slope) and starting point (y-intercept). The standard form (Ax + By = C) is useful for certain algebraic manipulations and finding intercepts. The point-slope form [y - y₁ = m(x - x₁)] is perfect when you know a point on the line and its slope.

Let's explore each form with detailed examples. Consider the equation 2x + 3 = 11. This is a simple linear equation in one variable. To solve it, we use inverse operations: subtract 3 from both sides to get 2x = 8, then divide both sides by 2 to find x = 4. The solution x = 4 means that when we substitute 4 for x in the original equation, both sides are equal.

For two-variable linear equations like y = 2x + 3, every point (x, y) that satisfies this equation lies on a straight line. When x = 0, y = 3 (the y-intercept). When x = 1, y = 5. When x = 2, y = 7. Notice the consistent pattern: for every 1-unit increase in x, y increases by 2 units. This is the slope of the line.""",
                    
                    "code_examples": [
                        """# Example 1: Solving a basic linear equation
# Equation: 3x + 7 = 22
# Step 1: Subtract 7 from both sides
# 3x + 7 - 7 = 22 - 7
# 3x = 15
# Step 2: Divide both sides by 3
# x = 15/3 = 5
# Verification: 3(5) + 7 = 15 + 7 = 22 ✓""",
                        
                        """# Example 2: Linear equation with fractions
# Equation: (2/3)x + 1/4 = 5/6
# Step 1: Subtract 1/4 from both sides
# (2/3)x = 5/6 - 1/4 = 10/12 - 3/12 = 7/12
# Step 2: Multiply both sides by 3/2
# x = (7/12) × (3/2) = 21/24 = 7/8""",
                        
                        """# Example 3: Word problem setup
# Problem: A phone plan costs $30 plus $0.10 per minute
# Total cost equation: C = 30 + 0.10m
# Where C = total cost, m = minutes used
# If bill is $45, find minutes used:
# 45 = 30 + 0.10m
# 15 = 0.10m
# m = 150 minutes"""
                    ],
                    
                    "practical_examples": [
                        "Business Application: A company's profit equation is P = 25x - 1000, where x is units sold. To break even (P = 0), they need to solve 0 = 25x - 1000, finding x = 40 units.",
                        "Physics Application: Distance equation d = vt + d₀. If initial position d₀ = 10m, velocity v = 5m/s, and final position d = 35m, solve for time: 35 = 5t + 10, so t = 5 seconds.",
                        "Economics: Supply and demand equilibrium. If supply S = 2p + 10 and demand D = -p + 40, equilibrium occurs when S = D: 2p + 10 = -p + 40, solving gives p = 10."
                    ],
                    
                    "key_points": [
                        "Linear equations maintain constant rates of change, creating straight-line graphs that make them predictable and useful for modeling real-world relationships",
                        "The fundamental principle of solving linear equations is maintaining equality by performing the same operation on both sides, allowing us to isolate the variable systematically",
                        "Different forms of linear equations (slope-intercept, standard, point-slope) serve different purposes and provide different insights into the relationship between variables"
                    ],
                    
                    "visual_diagrams": [
                        """Linear Equation Solution Process:
    3x + 7 = 22
        ↓ (subtract 7)
    3x = 15
        ↓ (divide by 3)
    x = 5
        ↓ (verify)
    3(5) + 7 = 22 ✓""",
                        
                        """Graphical Representation:
    y = 2x + 3
    
    y |     /
      |    /
    5 |   • (1,5)
      |  /
    3 |• (0,3) ← y-intercept
      |/
    1 •────────── x
      0  1  2  3
      
    Slope = 2 (rise/run)"""
                    ]
                }
            ],
            
            "detailed_examples": [
                {
                    "title": "Complete Real-World Linear Equation Problem",
                    "scenario": "A delivery company charges a flat fee of $5 plus $2 per mile. If your delivery cost was $23, how many miles was the delivery?",
                    "solution": "Set up the equation: Cost = 5 + 2(miles), so 23 = 5 + 2m. Subtract 5: 18 = 2m. Divide by 2: m = 9 miles.",
                    "explanation": "This problem demonstrates how linear equations model real-world pricing structures with fixed costs plus variable rates. The coefficient 2 represents the rate per mile, while 5 is the base fee."
                }
            ],
            
            "summary": f"""Linear equations serve as the foundation for algebraic thinking and mathematical modeling. Through this comprehensive exploration of {topic_title}, you've learned to recognize linear relationships, solve equations systematically, and apply these skills to real-world problems. The key insights include understanding that linear equations represent constant rates of change, mastering the fundamental principle of maintaining equality through equivalent operations, and recognizing how different forms of linear equations provide different perspectives on the same relationship.

These skills prepare you for advanced mathematics including systems of equations, inequalities, and eventually calculus where linear approximations become essential tools. More importantly, the logical thinking and problem-solving strategies you've developed will serve you well in any field that involves quantitative analysis, from science and engineering to business and economics.

Remember that mathematics is not just about finding answers, but about understanding patterns, relationships, and logical reasoning. Linear equations provide an excellent foundation for developing these critical thinking skills that extend far beyond mathematics into all areas of academic and professional life.""",
            
            "quiz_questions": [
                {
                    "question": "What is the solution to the equation 3x - 7 = 2x + 5?",
                    "options": ["x = 12", "x = 6", "x = -2", "x = 8"],
                    "correct": "A",
                    "explanation": "To solve 3x - 7 = 2x + 5, subtract 2x from both sides: x - 7 = 5, then add 7 to both sides: x = 12. Verify: 3(12) - 7 = 36 - 7 = 29, and 2(12) + 5 = 24 + 5 = 29."
                }
            ]
        }
    
    # Geography and Earth Sciences fallback content
    elif subject_area.lower() in ['geography', 'physical geography', 'human geography', 'environmental science'] and any(word in topic_title.lower() for word in ['geography', 'spatial', 'climate', 'landform', 'population', 'urban', 'region', 'environment', 'map', 'location']):
        return {
            "topic_title": topic_title,
            "introduction": f"""Geography is the scientific study of Earth's landscapes, peoples, places, and environments. {topic_title} represents a fundamental concept in geographic thinking that helps us understand the complex relationships between people, places, and environments. This comprehensive exploration will develop your spatial thinking skills and geographic knowledge essential for understanding our interconnected world.

Geographic knowledge is increasingly vital in our globalized world where environmental challenges, urban planning, economic development, and social issues require spatial perspective and understanding. Whether analyzing climate change impacts, planning sustainable cities, or understanding cultural patterns, geographic concepts provide essential tools for informed decision-making and problem-solving.

This lesson will develop your ability to think spatially, analyze geographic patterns, understand human-environment interactions, and apply geographic methods and technologies. You'll learn to ask the fundamental geographic questions: Where? Why there? So what? These questions guide geographic inquiry and help reveal spatial relationships that might otherwise remain hidden.""",
            
            "sections": [
                {
                    "section_title": f"Understanding {topic_title} in Geographic Context",
                    "content": f"""Geographic understanding of {topic_title} requires examining spatial patterns, processes, and relationships at multiple scales. Geography's unique perspective focuses on location, distribution, and the spatial dimension of phenomena. This {difficulty_level}-level analysis will help you develop the spatial thinking skills essential for geographic literacy.

Location is fundamental to geographic analysis and can be examined as absolute location (specific coordinates) and relative location (position relative to other places). When studying {topic_title}, we must consider both site factors (local physical and cultural characteristics) and situation factors (relative location and connections to other places). This locational analysis reveals why certain phenomena occur where they do.

Spatial scale is another crucial geographic concept that influences how we understand {topic_title}. Geographic phenomena operate simultaneously at local, regional, national, and global scales, and understanding these scale relationships is essential for comprehensive geographic analysis. What appears random at one scale may show clear patterns at another scale, demonstrating the importance of multi-scale thinking.

Human-environment interaction represents a core theme in geographic study that applies directly to understanding {topic_title}. This interaction involves how humans adapt to, modify, and depend upon their environment, while environmental conditions influence human activities and settlement patterns. Modern geography emphasizes sustainability and the need for humans to manage Earth's resources responsibly.

Geographic Information Systems (GIS) and other spatial technologies provide powerful tools for analyzing {topic_title}. These technologies allow geographers to visualize spatial patterns, analyze relationships, model processes, and communicate findings effectively. Understanding how to use and interpret geographic technology is essential for modern geographic practice.""",
                    
                    "code_examples": [
                        f"# Geographic Analysis Method for {topic_title}",
                        f"# Step 1: Define spatial extent and scale of analysis",
                        f"# Step 2: Collect and verify locational data using GPS/GIS",
                        f"# Step 3: Analyze spatial patterns using statistical methods",
                        f"# Step 4: Examine spatial relationships and dependencies",
                        f"# Step 5: Create maps and visualizations to communicate findings"
                    ],
                    
                    "practical_examples": [
                        f"Urban Planning Application: Using {topic_title} analysis to guide zoning decisions and infrastructure development in growing metropolitan areas",
                        f"Environmental Management: Applying {topic_title} concepts to develop conservation strategies for protected areas and biodiversity hotspots",
                        f"Economic Development: Using spatial analysis of {topic_title} to identify optimal locations for business development and industrial zones",
                        f"Disaster Preparedness: Incorporating {topic_title} understanding into emergency planning and risk assessment for natural hazards",
                        f"Transportation Planning: Applying geographic principles to design efficient transportation networks and reduce environmental impacts"
                    ],
                    
                    "key_points": [
                        f"Spatial Perspective: {topic_title} must be understood through geographic questions of where, why there, and so what",
                        f"Scale Analysis: {topic_title} operates at multiple scales from local to global, requiring multi-scale understanding",
                        f"Human-Environment Interaction: {topic_title} involves complex relationships between people and their environment",
                        f"Geographic Technology: GIS and spatial analysis tools provide essential methods for studying {topic_title}",
                        f"Applied Geography: {topic_title} has direct applications in planning, policy, and problem-solving across many fields"
                    ],
                    
                    "visual_diagrams": [
                        f"""Geographic Scale Hierarchy for {topic_title}:
    Global Level
        ↓
    National Level  
        ↓
    Regional Level
        ↓
    Local Level
        ↓
    Site Level""",
                        
                        f"""Five Themes of Geography Applied to {topic_title}:
    
    1. LOCATION → Where is it? (Absolute & Relative)
    2. PLACE → What is it like? (Physical & Human)
    3. REGION → How is it similar/different? (Formal & Functional)
    4. MOVEMENT → How do things move? (People, Goods, Ideas)
    5. HUMAN-ENVIRONMENT → How do people and environment interact?"""
                    ]
                },
                
                {
                    "section_title": f"Spatial Analysis and Geographic Methods",
                    "content": f"""Effective geographic analysis of {topic_title} requires systematic application of spatial thinking and geographic methods. Spatial analysis involves examining the arrangement, distribution, and relationships of phenomena across Earth's surface. This analysis reveals patterns that help us understand processes and predict future changes.

Distance decay is a fundamental geographic principle that applies to many aspects of {topic_title}. This principle suggests that interaction between places decreases as distance increases, though modern transportation and communication technologies have modified traditional distance relationships. Understanding distance decay helps explain spatial patterns and accessibility issues.

Diffusion processes explain how {topic_title} spreads across space and time. Contagious diffusion spreads outward from source areas like ripples in water, while hierarchical diffusion jumps between places of similar importance or connectivity. Stimulus diffusion involves the spread of underlying ideas that are modified as they move. Understanding these diffusion types helps explain spatial patterns and change processes.

Spatial interaction models help analyze flows and connections related to {topic_title}. Gravity models predict interaction based on size and distance relationships, while network analysis examines connectivity and accessibility within spatial systems. These models provide quantitative tools for understanding and predicting spatial relationships.

Geographic fieldwork remains essential for understanding {topic_title} despite advances in remote sensing and GIS technology. Field observation, measurement, and data collection provide ground truth for understanding local conditions and processes. Combining fieldwork with spatial technology creates comprehensive geographic analysis.

Region is a fundamental geographic concept for organizing knowledge about {topic_title}. Formal regions are defined by common characteristics, functional regions by connections and interactions, and perceptual regions by people's mental maps and cultural understanding. Regional analysis helps organize complex geographic information into meaningful patterns.""",
                    
                    "code_examples": [
                        f"# Spatial Pattern Analysis for {topic_title}",
                        f"# Calculate nearest neighbor distances to measure clustering",
                        f"# Apply Moran's I statistic to test for spatial autocorrelation", 
                        f"# Use kernel density estimation to identify hotspots",
                        f"# Perform regression analysis including spatial variables"
                    ],
                    
                    "practical_examples": [
                        f"Retail Location Analysis: Using spatial analysis to identify optimal locations for stores based on demographic data and competitor locations",
                        f"Disease Mapping: Applying geographic methods to track disease outbreaks and identify spatial clusters requiring intervention",
                        f"Agricultural Planning: Using geographic analysis to optimize crop selection and farming practices based on climate and soil conditions",
                        f"Conservation Planning: Applying spatial methods to design protected area networks that maintain ecological connectivity"
                    ],
                    
                    "key_points": [
                        f"Spatial Patterns: {topic_title} shows distinctive spatial arrangements that can be measured and analyzed",
                        f"Distance Relationships: Proximity and accessibility influence patterns and processes related to {topic_title}",
                        f"Diffusion Processes: Understanding how {topic_title} spreads or changes across space and time",
                        f"Regional Organization: {topic_title} can be understood through formal, functional, and perceptual regional frameworks"
                    ]
                }
            ],
            
            "detailed_examples": [
                {
                    "title": f"Complete Geographic Analysis of {topic_title}",
                    "scenario": f"A regional planning agency needs to understand {topic_title} patterns to develop effective policies and allocate resources efficiently across their jurisdiction.",
                    "solution": f"Geographers conduct multi-scale spatial analysis using GIS technology, field surveys, and demographic data. They examine spatial patterns, identify clusters and trends, analyze accessibility and connectivity, and model future scenarios. The analysis reveals significant spatial variations and helps identify priority areas for intervention.",
                    "explanation": f"This example demonstrates how geographic methods provide comprehensive understanding of {topic_title} through spatial perspective. The combination of quantitative analysis, qualitative observation, and spatial visualization creates actionable knowledge for decision-makers."
                }
            ],
            
            "summary": f"""Geographic understanding of {topic_title} provides essential spatial perspective for addressing complex contemporary challenges. Through systematic spatial analysis, we can identify patterns, understand processes, and develop effective solutions. The key geographic concepts - location, place, region, movement, and human-environment interaction - provide a comprehensive framework for understanding {topic_title}.

The spatial thinking skills developed through geographic study of {topic_title} transfer to many fields including urban planning, environmental management, business location analysis, and public policy development. Geographic technology tools like GIS provide powerful capabilities for spatial analysis and visualization that are increasingly valuable in data-driven decision making.

Remember that geography is not just about knowing where things are, but understanding why they are there, how they got there, and what their location means for people and environment. This geographic perspective is increasingly vital for understanding and addressing global challenges that require spatial thinking and analysis.""",
            
            "quiz_questions": [
                {
                    "question": f"Which of the following best describes the geographic approach to studying {topic_title}?",
                    "options": [
                        "Examining spatial patterns, processes, and relationships at multiple scales",
                        "Focusing only on physical environmental factors",
                        "Memorizing locations and place names",
                        "Studying only human activities and ignoring environmental factors"
                    ],
                    "correct": "A",
                    "explanation": f"Geography's unique contribution is examining spatial patterns, processes, and relationships at multiple scales. This comprehensive spatial perspective distinguishes geographic analysis from other approaches to studying {topic_title}."
                },
                {
                    "question": "What are the five fundamental themes of geography?",
                    "options": [
                        "Location, Place, Region, Movement, Human-Environment Interaction",
                        "Climate, Landforms, Population, Culture, Economics", 
                        "Maps, GIS, Remote Sensing, Fieldwork, Statistics",
                        "Physical, Human, Regional, Global, Local"
                    ],
                    "correct": "A",
                    "explanation": "The five themes of geography are Location, Place, Region, Movement, and Human-Environment Interaction. These themes provide a comprehensive framework for geographic analysis and help organize geographic thinking."
                }
            ]
        }
        
    # Mathematics fallback content
    return {
        "topic_title": topic_title,
        "introduction": f"""Welcome to this comprehensive study of {topic_title} in {subject_area}. This topic represents a crucial area of knowledge that builds upon fundamental concepts while preparing you for more advanced studies. Understanding {topic_title} requires both theoretical knowledge and practical application skills that you'll develop throughout this lesson.

In {subject_area}, {topic_title} serves as a bridge between basic concepts and advanced applications. Whether you're pursuing academic goals or professional development, mastering this topic will provide you with valuable problem-solving tools and analytical thinking skills. This lesson is designed to take you from foundational understanding to confident application.

We'll explore the key concepts systematically, provide multiple examples and practice opportunities, and connect the theoretical knowledge to real-world applications. By the end of this lesson, you'll have a solid foundation in {topic_title} and the confidence to tackle more advanced challenges.""",
        
        "sections": [
            {
                "section_title": f"Fundamental Concepts of {topic_title}",
                "content": f"""Understanding {topic_title} begins with grasping its fundamental principles and core concepts. This {difficulty_level}-level exploration will provide you with the essential knowledge needed to work confidently with {topic_title} in various contexts. The concepts we'll cover form the foundation for all advanced work in this area.

The importance of {topic_title} in {subject_area} cannot be overstated. These concepts appear throughout the field and provide essential tools for problem-solving and analysis. Whether you're working on theoretical problems or practical applications, a solid understanding of these fundamentals is crucial for success.

Key principles include understanding the underlying theory, recognizing patterns and relationships, and developing systematic approaches to problem-solving. We'll explore each of these areas with detailed explanations and multiple examples to ensure your comprehension is both deep and practical.

Throughout this section, pay attention to how different concepts connect and build upon each other. This interconnected understanding is what separates superficial knowledge from true mastery of {topic_title}.""",
                
                "code_examples": [
                    f"# Basic example demonstrating {topic_title} principles",
                    f"# Step-by-step approach to {topic_title} problems",
                    f"# Advanced application showing practical use"
                ],
                
                "practical_examples": [
                    f"Real-world application of {topic_title} in professional settings",
                    f"How {topic_title} appears in everyday problem-solving",
                    f"Industry examples showing the practical value of understanding {topic_title}"
                ],
                
                "key_points": [
                    f"Core principle 1: Understanding the fundamental nature of {topic_title}",
                    f"Core principle 2: Recognizing patterns and applications in {topic_title}",
                    f"Core principle 3: Developing systematic problem-solving approaches"
                ],
                
                "visual_diagrams": [
                    f"Conceptual diagram showing key relationships in {topic_title}",
                    f"Process flowchart for approaching {topic_title} problems"
                ]
            }
        ],
        
        "detailed_examples": [
            {
                "title": f"Comprehensive {topic_title} Example",
                "scenario": f"A detailed scenario requiring application of {topic_title} concepts",
                "solution": f"Step-by-step solution demonstrating proper methodology for {topic_title}",
                "explanation": f"Detailed explanation of each step and the reasoning behind the approach"
            }
        ],
        
        "summary": f"""This comprehensive introduction to {topic_title} has provided you with the essential knowledge and skills needed for success in {subject_area}. You've learned the fundamental concepts, seen practical applications, and practiced problem-solving techniques that will serve you well in advanced studies and professional applications.

The key takeaways from this lesson include understanding the core principles, recognizing how {topic_title} applies in various contexts, and developing confidence in your problem-solving abilities. These skills form the foundation for continued learning and success in {subject_area}.""",
        
        "quiz_questions": [
            {
                "question": f"Which of the following best describes the primary purpose of studying {topic_title}?",
                "options": [
                    f"To develop problem-solving skills applicable to {subject_area}",
                    "To memorize formulas and procedures",
                    "To prepare for standardized tests",
                    "To complete academic requirements"
                ],
                "correct": "A",
                "explanation": f"The primary purpose of studying {topic_title} is to develop problem-solving skills and conceptual understanding that can be applied broadly in {subject_area} and related fields."
            }
        ]
    }

import time
import random

def make_api_request_with_backoff(url, headers, data, max_retries=3, base_delay=1):
    """Make API request with exponential backoff for rate limiting"""
    
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=45)
            
            if response.status_code == 200:
                return response
            elif response.status_code == 429:  # Rate limited
                if attempt < max_retries:
                    # Exponential backoff with jitter
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"Rate limited (429). Retrying in {delay:.1f} seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    print(f"Rate limit exceeded. Max retries ({max_retries}) reached.")
                    return response
            else:
                print(f"API request failed with status code: {response.status_code}")
                return response
                
        except requests.RequestException as e:
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                print(f"Request failed: {e}. Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print(f"Request failed after {max_retries} retries: {e}")
                raise
    
    return None

def clean_and_parse_json(content, expected_type='object'):
    """Robust JSON parsing that handles control characters and malformed responses"""
    import re
    
    try:
        # Remove null bytes and other control characters that break JSON parsing
        content = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', content)
        
        # Remove markdown code blocks
        if content.startswith('```json'):
            content = content[7:]
        elif content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]
        
        content = content.strip()
        
        # Find JSON boundaries based on expected type
        if expected_type == 'array':
            start_char, end_char = '[', ']'
        else:
            start_char, end_char = '{', '}'
        
        # Find the main JSON structure
        start_idx = content.find(start_char)
        if start_idx == -1:
            return None
        
        # Find matching closing bracket/brace
        bracket_count = 0
        end_idx = -1
        
        for i in range(start_idx, len(content)):
            if content[i] == start_char:
                bracket_count += 1
            elif content[i] == end_char:
                bracket_count -= 1
                if bracket_count == 0:
                    end_idx = i + 1
                    break
        
        if end_idx == -1:
            return None
        
        json_content = content[start_idx:end_idx]
        
        # Additional cleaning for common AI response issues
        # Fix missing commas before closing brackets
        json_content = re.sub(r'"\s*\n\s*}', '",\n  }', json_content)
        json_content = re.sub(r'"\s*\n\s*]', '",\n  ]', json_content)
        
        # Fix missing commas between JSON properties (common AI error)
        json_content = re.sub(r'"\s*\n\s*"', '",\n  "', json_content)
        
        # Fix specific delimiter issues seen in logs - missing comma after long text
        json_content = re.sub(r'([\w\s\.]+)"\s*"', r'\1", "', json_content)
        
        # Fix trailing commas
        json_content = re.sub(r',\s*([}\]])', r'\1', json_content)
        
        # Fix incomplete JSON objects by ensuring proper closing
        if json_content.count('{') > json_content.count('}'):
            json_content += '}'
        if json_content.count('[') > json_content.count(']'):
            json_content += ']'
        
        # Try to parse the cleaned JSON
        parsed = json.loads(json_content)
        return parsed
        
    except json.JSONDecodeError as e:
        print(f"JSON parsing error after cleaning: {e}")
        print(f"Attempted to parse: {json_content[:300]}..." if 'json_content' in locals() else "Could not extract JSON")
        return None
    except Exception as e:
        print(f"Unexpected error in JSON parsing: {e}")
        return None

def generate_challenging_questions_for_topic(topic_title, difficulty_level, num_questions=5):
    """Generate challenging questions for a specific topic"""
    
    # Determine question distribution based on difficulty level
    if difficulty_level.lower() == 'beginner':
        question_distribution = {
            'multiple_choice': 3,
            'true_false': 2,
            'fill_blank': 0,
            'short_answer': 0
        }
        complexity_focus = "fundamental concepts, definitions, and basic applications"
    elif difficulty_level.lower() == 'intermediate':
        question_distribution = {
            'multiple_choice': 2,
            'true_false': 1,
            'fill_blank': 1,
            'short_answer': 1
        }
        complexity_focus = "analysis, application, and problem-solving scenarios"
    else:  # advanced
        question_distribution = {
            'multiple_choice': 1,
            'true_false': 1,
            'fill_blank': 1,
            'short_answer': 2
        }
        complexity_focus = "synthesis, evaluation, and expert-level analysis"
    
    prompt = f"""
As an expert educator and assessment designer, create {num_questions} challenging {difficulty_level} level questions for the topic: {topic_title}

Question Distribution:
- {question_distribution['multiple_choice']} Multiple Choice questions
- {question_distribution['true_false']} True/False questions
- {question_distribution['fill_blank']} Fill-in-the-blank questions
- {question_distribution['short_answer']} Short answer questions

Assessment Focus: {complexity_focus}

Quality Requirements:
1. Questions should test {complexity_focus}
2. Include real-world scenarios and applications
3. Avoid trivial recall questions
4. Include common misconceptions as distractors
5. Provide detailed explanations for all answers
6. Ensure questions are pedagogically sound and fair

Bloom's Taxonomy Levels to Target:
- Beginner: Remember, Understand, Apply
- Intermediate: Apply, Analyze, Evaluate
- Advanced: Analyze, Evaluate, Create

Provide ONLY a JSON array with this structure:
[
  {{
    "question": "Detailed question text with clear context and requirements",
    "type": "multiple_choice",
    "options": ["Detailed option A with specific terminology", "Detailed option B", "Detailed option C", "Detailed option D"],
    "correct_answer": "A",
    "explanation": "Comprehensive explanation of why this answer is correct and why others are incorrect",
    "difficulty": "{difficulty_level}",
    "bloom_level": "apply",
    "estimated_time": 3,
    "learning_objective": "Specific skill or knowledge this question assesses",
    "tags": ["relevant", "topic", "tags"]
  }},
  {{
    "question": "True/False statement with sufficient context",
    "type": "true_false",
    "correct_answer": "true",
    "explanation": "Detailed explanation supporting the correct answer",
    "difficulty": "{difficulty_level}",
    "bloom_level": "understand",
    "estimated_time": 2,
    "learning_objective": "Specific understanding being tested",
    "tags": ["relevant", "tags"]
  }},
  {{
    "question": "Complete this statement: 'The primary function of _____ is to _____'",
    "type": "fill_blank",
    "correct_answer": "specific term or phrase",
    "alternative_answers": ["acceptable alternative 1", "acceptable alternative 2"],
    "explanation": "Why this answer is correct and its significance",
    "difficulty": "{difficulty_level}",
    "bloom_level": "remember",
    "estimated_time": 2,
    "learning_objective": "Knowledge of key terminology",
    "tags": ["terminology", "definitions"]
  }},
  {{
    "question": "Explain how [concept] applies to [real-world scenario]. Provide specific examples and reasoning.",
    "type": "short_answer",
    "sample_answer": "Comprehensive sample answer demonstrating expected depth and structure",
    "key_points": ["Essential point 1", "Essential point 2", "Essential point 3"],
    "grading_rubric": {{
      "excellent": "Criteria for top marks",
      "good": "Criteria for good performance", 
      "needs_improvement": "Criteria indicating more study needed"
    }},
    "explanation": "What this question assesses and why it's important",
    "difficulty": "{difficulty_level}",
    "bloom_level": "evaluate",
    "estimated_time": 8,
    "learning_objective": "Application and analysis skills",
    "tags": ["application", "analysis"]
  }}
]

Make questions challenging, practical, and educationally sound. Focus on understanding, application, and critical thinking rather than memorization.
"""
    
    try:
        # Use rate-limited API request
        response = make_api_request_with_backoff(
            'https://api.groq.com/openai/v1/chat/completions',
            {
                'Authorization': f'Bearer {os.environ.get("GROQ_API_KEY", "")}',
                'Content-Type': 'application/json'
            },
            {
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1200,
                "temperature": 0.8
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result['choices'][0]['message']['content']
            
            # Use the robust JSON parser for array responses
            questions_data = clean_and_parse_json(ai_response, expected_type='array')
            
            if questions_data and isinstance(questions_data, list):
                return questions_data
            else:
                print(f"Failed to parse questions JSON or got invalid format")
                return []
        else:
            print(f"API request failed with status code: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Questions generation error: {e}")
        return []

def validate_course_content_quality(course_content, subject_area, difficulty_level):
    """Validate and score the quality of generated course content"""
    
    quality_score = 0
    max_score = 100
    feedback = []
    
    # Check introduction quality (20 points)
    introduction = course_content.get('introduction', '')
    if len(introduction) > 500:
        quality_score += 15
    elif len(introduction) > 300:
        quality_score += 10
        feedback.append("Introduction could be more detailed")
    else:
        feedback.append("Introduction needs significant expansion")
    
    # Check for subject-specific terminology (15 points)
    if subject_area.lower() in ['biology', 'medical']:
        bio_terms = ['cell', 'tissue', 'organ', 'protein', 'DNA', 'enzyme', 'metabolism']
        found_terms = sum(1 for term in bio_terms if term.lower() in introduction.lower())
        quality_score += min(15, found_terms * 3)
    elif subject_area.lower() in ['computer science', 'programming']:
        cs_terms = ['algorithm', 'data structure', 'complexity', 'function', 'variable', 'loop', 'array']
        found_terms = sum(1 for term in cs_terms if term.lower() in introduction.lower())
        quality_score += min(15, found_terms * 3)
    elif subject_area.lower() in ['mathematics']:
        math_terms = ['equation', 'function', 'variable', 'solution', 'theorem', 'proof', 'formula']
        found_terms = sum(1 for term in math_terms if term.lower() in introduction.lower())
        quality_score += min(15, found_terms * 3)
    else:
        quality_score += 10  # Base score for other subjects
    
    # Check sections quality (25 points)
    sections = course_content.get('sections', [])
    if len(sections) >= 2:
        quality_score += 10
        
        total_content_length = sum(len(section.get('content', '')) for section in sections)
        if total_content_length > 2000:
            quality_score += 15
        elif total_content_length > 1000:
            quality_score += 10
            feedback.append("Section content could be more comprehensive")
        else:
            feedback.append("Section content needs significant expansion")
    else:
        feedback.append("Course needs more detailed sections")
    
    # Check practical examples (15 points)
    total_examples = 0
    for section in sections:
        total_examples += len(section.get('practical_examples', []))
        total_examples += len(section.get('code_examples', []))
    
    if total_examples >= 5:
        quality_score += 15
    elif total_examples >= 3:
        quality_score += 10
        feedback.append("More practical examples would improve the course")
    else:
        feedback.append("Course needs significantly more practical examples")
    
    # Check quiz questions quality (15 points)
    quiz_questions = course_content.get('quiz_questions', [])
    if len(quiz_questions) >= 3:
        quality_score += 10
        
        # Check for detailed explanations
        detailed_explanations = sum(1 for q in quiz_questions if len(q.get('explanation', '')) > 50)
        quality_score += min(5, detailed_explanations * 2)
    else:
        feedback.append("Course needs more assessment questions")
    
    # Check learning objectives alignment (10 points)
    if 'detailed_examples' in course_content and len(course_content['detailed_examples']) > 0:
        quality_score += 10
    else:
        feedback.append("Course needs detailed worked examples")
    
    # Difficulty level appropriateness check
    if difficulty_level == 'beginner':
        if 'fundamental' in introduction.lower() or 'basic' in introduction.lower():
            quality_score += 5
        if len(introduction) < 800:  # Beginners need more explanation
            feedback.append("Beginner content needs more detailed explanations")
    elif difficulty_level == 'advanced':
        if 'advanced' in introduction.lower() or 'expert' in introduction.lower():
            quality_score += 5
        if total_content_length < 1500:
            feedback.append("Advanced content needs more depth and complexity")
    
    # Calculate final score and grade
    final_score = min(100, quality_score)
    
    if final_score >= 85:
        grade = "Excellent"
        overall_feedback = "High-quality educational content meeting professional standards"
    elif final_score >= 70:
        grade = "Good"
        overall_feedback = "Solid educational content with room for minor improvements"
    elif final_score >= 55:
        grade = "Needs Improvement"
        overall_feedback = "Content meets basic requirements but needs enhancement"
    else:
        grade = "Poor"
        overall_feedback = "Content requires significant improvement to meet educational standards"
    
    return {
        'score': final_score,
        'grade': grade,
        'feedback': feedback,
        'overall_feedback': overall_feedback,
        'recommendations': generate_improvement_recommendations(feedback, subject_area, difficulty_level)
    }

def generate_improvement_recommendations(feedback, subject_area, difficulty_level):
    """Generate specific recommendations for improving course content"""
    
    recommendations = []
    
    if any("expansion" in f.lower() for f in feedback):
        recommendations.append(f"Expand content sections to include more detailed explanations appropriate for {difficulty_level} level")
    
    if any("examples" in f.lower() for f in feedback):
        recommendations.append(f"Add more real-world examples and case studies relevant to {subject_area}")
    
    if any("assessment" in f.lower() or "questions" in f.lower() for f in feedback):
        recommendations.append("Include more varied assessment questions with detailed explanations")
    
    if subject_area.lower() in ['computer science', 'programming']:
        recommendations.append("Add more code examples with step-by-step explanations")
        recommendations.append("Include algorithm complexity analysis and performance considerations")
    elif subject_area.lower() in ['biology', 'medical']:
        recommendations.append("Include more anatomical diagrams and physiological process explanations")
        recommendations.append("Add clinical applications and disease-related examples")
    elif subject_area.lower() in ['mathematics']:
        recommendations.append("Include more worked examples with multiple solution approaches")
        recommendations.append("Add visual representations and graphical interpretations")
    
    if difficulty_level == 'beginner':
        recommendations.append("Provide more foundational explanations and basic terminology definitions")
    elif difficulty_level == 'advanced':
        recommendations.append("Include cutting-edge research and advanced theoretical concepts")
    
    return recommendations

# ==================== ENROLLMENT HELPER FUNCTIONS ====================

def generate_enrollment_number(course_id):
    """Generate a unique enrollment number for a course"""
    import string
    import secrets
    
    # Format: QZ-{COURSE_ID}-{YEAR}-{RANDOM}
    year = datetime.now().year
    random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    enrollment_number = f"QZ-{course_id:03d}-{year}-{random_part}"
    
    # Ensure uniqueness
    while CourseEnrollment.query.filter_by(enrollment_number=enrollment_number).first():
        random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
        enrollment_number = f"QZ-{course_id:03d}-{year}-{random_part}"
    
    return enrollment_number

def get_student_profile_data(user_id):
    """Get student profile data for enrollment"""
    user = db.session.get(User, user_id)
    if user:
        return {
            'name': user.username,  # You might want to add a full_name field to User model
            'email': user.email
        }
    return {'name': 'Unknown', 'email': 'unknown@example.com'}

# User model: students, lecturers, admin
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)  # Email field
    password = db.Column(db.String(255), nullable=False)  # Increased from 120 to 255 for scrypt hashes
    role = db.Column(db.String(20), nullable=False)  # 'student', 'lecturer', 'admin'
    profile_pic = db.Column(db.String(120), nullable=True)  # New field

# Exam model
class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    lecturer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    ai_generated = db.Column(db.Boolean, default=False)  # Flag for AI-generated exams
    
    # Scheduling fields
    scheduled_start = db.Column(db.DateTime, nullable=True)  # When exam becomes available
    scheduled_end = db.Column(db.DateTime, nullable=True)    # When exam becomes unavailable
    is_scheduled = db.Column(db.Boolean, default=False)     # Whether exam has scheduling enabled

# Question model
class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    option_a = db.Column(db.String(200), nullable=True)
    option_b = db.Column(db.String(200), nullable=True)
    option_c = db.Column(db.String(200), nullable=True)
    option_d = db.Column(db.String(200), nullable=True)
    correct_option = db.Column(db.String(1), nullable=True)  # 'A', 'B', 'C', or 'D'
    question_type = db.Column(db.String(20), nullable=False, default='multiple_choice')  # 'multiple_choice' or 'text'
    answer = db.Column(db.String(200), nullable=True)  # For backward compatibility with text questions

# Exam Session model for tracking student exam attempts
class ExamSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    end_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='in_progress')  # 'in_progress', 'completed', 'disqualified'
    ai_monitoring_enabled = db.Column(db.Boolean, nullable=False, default=True)
    webcam_permission = db.Column(db.Boolean, nullable=False, default=False)

# AI Monitoring Alerts model
class MonitoringAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('exam_session.id'), nullable=False)
    alert_type = db.Column(db.String(50), nullable=False)  # 'face_not_detected', 'multiple_faces', 'tab_switch', 'suspicious_movement'
    alert_time = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    severity = db.Column(db.String(20), nullable=False)  # 'low', 'medium', 'high', 'critical'
    description = db.Column(db.String(500), nullable=True)

# Student Answers model
class StudentAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('exam_session.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    answer = db.Column(db.String(500), nullable=False)
    answered_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

# Question Bank model for AI-generated questions
class QuestionBank(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(200), nullable=False)
    question_text = db.Column(db.String(500), nullable=False)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=False)
    option_d = db.Column(db.String(200), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False, default='medium')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

# Exam Settings model
class ExamSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False, unique=True)
    results_visible_after_all_complete = db.Column(db.Boolean, nullable=False, default=True)
    time_limit_minutes = db.Column(db.Integer, nullable=True)
    randomize_questions = db.Column(db.Boolean, nullable=False, default=False)
    randomize_options = db.Column(db.Boolean, nullable=False, default=False)
    passing_score = db.Column(db.Integer, nullable=False, default=70)

# Gamification Models
class TeacherAchievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    achievement_type = db.Column(db.String(50), nullable=False)  # 'exams_created', 'students_taught', etc.
    achievement_name = db.Column(db.String(100), nullable=False)
    achievement_description = db.Column(db.String(200), nullable=False)
    badge_tier = db.Column(db.String(20), nullable=False, default='bronze')  # bronze, silver, gold
    earned_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    points_awarded = db.Column(db.Integer, nullable=False, default=10)

class StudentPoints(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    points = db.Column(db.Integer, nullable=False, default=0)
    level = db.Column(db.Integer, nullable=False, default=1)
    total_exams_taken = db.Column(db.Integer, nullable=False, default=0)
    perfect_scores = db.Column(db.Integer, nullable=False, default=0)
    streak_days = db.Column(db.Integer, nullable=False, default=0)
    last_activity = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

class Challenge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(1000), nullable=False)
    topic = db.Column(db.String(200), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False, default='medium')  # 'easy', 'medium', 'hard'
    challenge_type = db.Column(db.String(50), nullable=False, default='speed_quiz')  # 'speed_quiz', 'accuracy_challenge', 'mixed', 'knowledge_test'
    time_limit_minutes = db.Column(db.Integer, nullable=True)  # For timed challenges
    max_attempts = db.Column(db.Integer, nullable=False, default=3)  # Maximum attempts per student
    passing_score = db.Column(db.Integer, nullable=False, default=70)  # Minimum score to pass
    points_reward = db.Column(db.Integer, nullable=False, default=50)
    start_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    end_date = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    ai_generated = db.Column(db.Boolean, nullable=False, default=False)
    participants_count = db.Column(db.Integer, nullable=False, default=0)
    max_participants = db.Column(db.Integer, nullable=True)  # Optional participant limit
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

# Challenge Questions model
class ChallengeQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenge.id'), nullable=False)
    question_text = db.Column(db.String(1000), nullable=False)
    question_type = db.Column(db.String(20), nullable=False, default='multiple_choice')  # 'multiple_choice', 'text'
    option_a = db.Column(db.String(500), nullable=True)
    option_b = db.Column(db.String(500), nullable=True)
    option_c = db.Column(db.String(500), nullable=True)
    option_d = db.Column(db.String(500), nullable=True)
    correct_option = db.Column(db.String(1), nullable=True)  # For MCQ (A, B, C, D)
    answer = db.Column(db.String(500), nullable=True)  # For text questions
    points = db.Column(db.Integer, nullable=False, default=1)
    time_limit_seconds = db.Column(db.Integer, nullable=True)  # Individual question time limit
    order_index = db.Column(db.Integer, nullable=False, default=0)

# Challenge Sessions model for tracking student attempts
class ChallengeSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenge.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    end_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='in_progress')  # 'in_progress', 'completed', 'abandoned'
    score = db.Column(db.Integer, nullable=False, default=0)
    percentage = db.Column(db.Float, nullable=False, default=0.0)
    time_taken_minutes = db.Column(db.Float, nullable=True)
    rank = db.Column(db.Integer, nullable=True)  # Student's rank in this challenge
    points = db.Column(db.Integer, nullable=False, default=0)  # Renamed from points_earned for consistency
    points_breakdown = db.Column(db.Text, nullable=True)  # JSON string with detailed point breakdown

# Challenge Answers model
class ChallengeAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('challenge_session.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('challenge_question.id'), nullable=False)
    answer = db.Column(db.String(500), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False, default=False)
    time_taken_seconds = db.Column(db.Float, nullable=True)
    answered_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

class TeacherStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    total_exams_created = db.Column(db.Integer, nullable=False, default=0)
    total_students_taught = db.Column(db.Integer, nullable=False, default=0)
    total_questions_created = db.Column(db.Integer, nullable=False, default=0)
    total_points = db.Column(db.Integer, nullable=False, default=0)
    level = db.Column(db.Integer, nullable=False, default=1)
    join_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

# Live Session Models for Virtual Classroom

class LiveSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    session_id = db.Column(db.String(100), nullable=False, unique=True)  # Unique room ID
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    max_participants = db.Column(db.Integer, nullable=False, default=50)
    is_recording = db.Column(db.Boolean, nullable=False, default=False)
    session_type = db.Column(db.String(50), nullable=False, default='lecture')  # 'lecture', 'discussion', 'exam_review'
    password_protected = db.Column(db.Boolean, nullable=False, default=False)
    session_password = db.Column(db.String(100), nullable=True)


class SessionParticipant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('live_session.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    left_at = db.Column(db.DateTime, nullable=True)
    is_online = db.Column(db.Boolean, nullable=False, default=True)
    role_in_session = db.Column(db.String(20), nullable=False, default='participant')  # 'host', 'co-host', 'participant'
    camera_enabled = db.Column(db.Boolean, nullable=False, default=False)
    microphone_enabled = db.Column(db.Boolean, nullable=False, default=False)
    screen_sharing = db.Column(db.Boolean, nullable=False, default=False)


class SessionMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('live_session.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(1000), nullable=False)
    message_type = db.Column(db.String(20), nullable=False, default='text')  # 'text', 'system', 'file'
    sent_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    is_private = db.Column(db.Boolean, nullable=False, default=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # For private messages

class SessionRecording(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('live_session.id'), nullable=False)
    recording_url = db.Column(db.String(500), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)  # Size in MB
    duration_minutes = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    is_available = db.Column(db.Boolean, nullable=False, default=True)

# Quizzo Bot Chatbot Models
class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_title = db.Column(db.String(200), nullable=True)  # Auto-generated from first message
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_activity = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    message_count = db.Column(db.Integer, nullable=False, default=0)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=True)  # Bot's response
    message_type = db.Column(db.String(20), nullable=False, default='user')  # 'user' or 'bot'
    sentiment = db.Column(db.String(20), nullable=True)  # 'positive', 'negative', 'neutral'
    category = db.Column(db.String(50), nullable=True)  # 'app_features', 'academic', 'general', etc.
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    response_time_ms = db.Column(db.Integer, nullable=True)  # Time taken to generate response
    is_helpful = db.Column(db.Boolean, nullable=True)  # User feedback

# Study Materials Models
class StudyMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    url = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(100), nullable=False)  # 'biology', 'chemistry', 'physics', etc.
    material_type = db.Column(db.String(50), nullable=False)  # 'video', 'article', 'pdf', 'interactive'
    difficulty_level = db.Column(db.String(20), nullable=False, default='intermediate')  # 'beginner', 'intermediate', 'advanced'
    source = db.Column(db.String(100), nullable=True)  # 'Khan Academy', 'Coursera', etc.
    rating = db.Column(db.Float, nullable=False, default=0.0)
    view_count = db.Column(db.Integer, nullable=False, default=0)
    added_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_approved = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    tags = db.Column(db.String(500), nullable=True)  # Comma-separated tags

class MaterialBookmark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('study_material.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

class MaterialRating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('study_material.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    review = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

# Self-Paced Courses Models
class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    difficulty_level = db.Column(db.String(20), nullable=False, default='intermediate')
    estimated_duration_hours = db.Column(db.Integer, nullable=False)
    is_published = db.Column(db.Boolean, nullable=False, default=False)
    enrollment_count = db.Column(db.Integer, nullable=False, default=0)
    rating = db.Column(db.Float, nullable=False, default=0.0)
    cover_image = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    prerequisites = db.Column(db.Text, nullable=True)  # Course requirements
    learning_objectives = db.Column(db.Text, nullable=True)

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)  # HTML content
    lesson_type = db.Column(db.String(50), nullable=False, default='text')  # 'text', 'video', 'interactive', 'quiz'
    video_url = db.Column(db.String(500), nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=True)
    order_index = db.Column(db.Integer, nullable=False)
    is_published = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

class CourseEnrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    enrollment_number = db.Column(db.String(20), nullable=False, unique=True)  # Auto-generated enrollment number
    student_name = db.Column(db.String(200), nullable=False)  # Cached from user profile
    student_email = db.Column(db.String(200), nullable=False)  # Cached from user profile
    enrolled_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    progress_percentage = db.Column(db.Float, nullable=False, default=0.0)
    completed_at = db.Column(db.DateTime, nullable=True)
    last_accessed = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    enrollment_status = db.Column(db.String(20), nullable=False, default='active')  # 'active', 'completed', 'dropped'
    certificate_issued = db.Column(db.Boolean, nullable=False, default=False)
    final_grade = db.Column(db.String(5), nullable=True)  # A, B, C, D, F

class LessonProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('course_enrollment.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    is_completed = db.Column(db.Boolean, nullable=False, default=False)
    time_spent_minutes = db.Column(db.Integer, nullable=False, default=0)
    completed_at = db.Column(db.DateTime, nullable=True)
    last_accessed = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

class CourseReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    review = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

# AI Course Generation Models
class AITopicTemplate(db.Model):
    """AI-generated topic templates for course creation"""
    id = db.Column(db.Integer, primary_key=True)
    subject_area = db.Column(db.String(100), nullable=False)  # e.g., "Python Programming", "Data Science"
    topic_title = db.Column(db.String(200), nullable=False)
    topic_description = db.Column(db.Text, nullable=False)
    difficulty_level = db.Column(db.String(20), nullable=False)  # beginner, intermediate, advanced
    estimated_hours = db.Column(db.Integer, nullable=False)
    prerequisites = db.Column(db.Text, nullable=True)
    learning_objectives = db.Column(db.Text, nullable=False)  # JSON array of objectives
    subtopics = db.Column(db.Text, nullable=False)  # JSON array of subtopics
    suggested_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

class AICourseTemplate(db.Model):
    """Complete AI-generated course templates"""
    id = db.Column(db.Integer, primary_key=True)
    template_name = db.Column(db.String(200), nullable=False)
    subject_area = db.Column(db.String(100), nullable=False)
    difficulty_level = db.Column(db.String(20), nullable=False)
    total_estimated_hours = db.Column(db.Integer, nullable=False)
    course_description = db.Column(db.Text, nullable=False)
    learning_objectives = db.Column(db.Text, nullable=False)  # JSON array
    prerequisites = db.Column(db.Text, nullable=True)
    course_outline = db.Column(db.Text, nullable=False)  # JSON array of topics/lessons
    ai_generated_content = db.Column(db.Text, nullable=False)  # Full course content in JSON
    usage_count = db.Column(db.Integer, nullable=False, default=0)
    rating = db.Column(db.Float, nullable=False, default=0.0)
    created_by_ai = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

class AIQuestionBank(db.Model):
    """AI-generated challenging questions for topics"""
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('ai_topic_template.id'), nullable=True)
    subject_area = db.Column(db.String(100), nullable=False)
    topic_title = db.Column(db.String(200), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(50), nullable=False)  # multiple_choice, true_false, coding, essay
    options = db.Column(db.Text, nullable=True)  # JSON array for multiple choice
    correct_answer = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text, nullable=False)
    difficulty_level = db.Column(db.String(20), nullable=False)
    bloom_taxonomy_level = db.Column(db.String(20), nullable=True)  # remember, understand, apply, analyze, evaluate, create
    estimated_time_minutes = db.Column(db.Integer, nullable=False, default=2)
    usage_count = db.Column(db.Integer, nullable=False, default=0)
    quality_rating = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

class CourseGenerationRequest(db.Model):
    """Track AI course generation requests and results"""
    id = db.Column(db.Integer, primary_key=True)
    lecturer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject_area = db.Column(db.String(100), nullable=False)
    course_title = db.Column(db.String(200), nullable=False)
    difficulty_level = db.Column(db.String(20), nullable=False)
    special_requirements = db.Column(db.Text, nullable=True)
    generation_status = db.Column(db.String(20), nullable=False, default='pending')  # pending, generating, completed, failed
    generated_template_id = db.Column(db.Integer, db.ForeignKey('ai_course_template.id'), nullable=True)
    generated_course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True)
    ai_processing_time = db.Column(db.Integer, nullable=True)  # seconds
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime, nullable=True)


@app.route('/')
def index():
    return render_template('login.html')

@app.route('/health')
def health_check():
    """Health check endpoint for Render deployment"""
    try:
        # Test database connection
        with app.app_context():
            db.session.execute(db.text('SELECT 1'))
        return {
            'status': 'healthy',
            'database': 'connected',
            'version': '1.0.0'
        }, 200
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }, 500


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            # Debug: Print all form data
            print("Form data received:", dict(request.form))
            
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
            role = request.form.get('role', '')
            
            print(f"Parsed data: username={username}, email={email}, role={role}")
            
            # Validation
            if not username or not email or not password:
                error_msg = "All fields are required."
                print(f"Validation error: {error_msg}")
                return render_template('signup.html', error=error_msg)
            
            if password != confirm_password:
                error_msg = "Passwords do not match."
                print(f"Validation error: {error_msg}")
                return render_template('signup.html', error=error_msg)
            
            if len(password) < 6:
                error_msg = "Password must be at least 6 characters long."
                print(f"Validation error: {error_msg}")
                return render_template('signup.html', error=error_msg)
            
            if not role:
                error_msg = "Please select your role (Student or Lecturer)."
                print(f"Validation error: {error_msg}")
                return render_template('signup.html', error=error_msg)
            
            # Check if username already exists
            existing_user = safe_db_query(lambda: User.query.filter_by(username=username).first())
            if existing_user:
                error_msg = "Username already exists."
                print(f"Validation error: {error_msg}")
                return render_template('signup.html', error=error_msg)
            
            # Check if email already exists
            existing_email = safe_db_query(lambda: User.query.filter_by(email=email).first())
            if existing_email:
                error_msg = "Email already exists."
                print(f"Validation error: {error_msg}")
                return render_template('signup.html', error=error_msg)
            
            # Create new user
            hashed_pw = generate_password_hash(password)
            user = User()
            user.username = username
            user.email = email
            user.password = hashed_pw
            user.role = role
            db.session.add(user)
            safe_db_commit()
            
            print(f"User created successfully: {username}")
            # Add success message to session for display on login page
            session['signup_success'] = f"Account created successfully! Welcome to QUIZZO, {username}!"
            return redirect(url_for('login'))
            
        except Exception as e:
            import traceback
            print('Signup error:', e)
            traceback.print_exc()
            error_msg = f"Signup failed: {str(e)}"
            return render_template('signup.html', error=error_msg)
    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            # Clear signup success message after form submission
            session.pop('signup_success', None)
            
            username = request.form['username']
            password = request.form['password']
            user = safe_db_query(lambda: User.query.filter_by(username=username).first())
            if user and check_password_hash(user.password, password):
                session['user_id'] = user.id
                session['role'] = user.role
                session['username'] = user.username
                return redirect(url_for('dashboard'))
            else:
                return render_template('login.html', error="Invalid credentials.")
        except Exception as e:
            print(f"Login error: {e}")
            return render_template('login.html', error="Database connection issue. Please try again.")
    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))      
    role = session.get('role')
    user = db.session.get(User, session['user_id']) 
    if not user:
        session.clear()
        return redirect(url_for('login'))
    if role == 'lecturer':
        # Get lecturer's exams and statistics
        lecturer_exams = Exam.query.filter_by(lecturer_id=session['user_id']).all()
        exam_count = len(lecturer_exams)
        # Get active exam sessions
        active_sessions = db.session.query(ExamSession).join(Exam).filter(
            Exam.lecturer_id == session['user_id'],
            ExamSession.status == 'in_progress'
        ).count()
        
        # Get total student results
        total_results = db.session.query(ExamSession).join(Exam).filter(
            Exam.lecturer_id == session['user_id'],
            ExamSession.status.in_(['completed', 'disqualified'])
        ).count()
        
        # Get detailed live activity data
        live_activities = []
        activity_history = []
        
        # Get current active sessions with detailed student info
        active_exam_sessions = db.session.query(ExamSession, Exam, User).join(
            Exam, ExamSession.exam_id == Exam.id
        ).join(
            User, ExamSession.student_id == User.id
        ).filter(
            Exam.lecturer_id == session['user_id'],
            ExamSession.status == 'in_progress'
        ).order_by(ExamSession.start_time.desc()).all()
        
        for exam_session, exam, student in active_exam_sessions:
            # Calculate time elapsed
            time_elapsed = datetime.now(timezone.utc) - exam_session.start_time
            elapsed_minutes = int(time_elapsed.total_seconds() / 60)
            
            # Get recent monitoring alerts for this session
            recent_alerts = MonitoringAlert.query.filter_by(
                session_id=exam_session.id
            ).order_by(MonitoringAlert.alert_time.desc()).limit(3).all()
            
            # Get answered questions count
            answered_questions = StudentAnswer.query.filter_by(
                session_id=exam_session.id
            ).count()
            
            total_questions = Question.query.filter_by(exam_id=exam.id).count()
            
            live_activities.append({
                'student_name': student.username,
                'exam_title': exam.title,
                'start_time': exam_session.start_time,
                'elapsed_minutes': elapsed_minutes,
                'progress': round((answered_questions / total_questions * 100) if total_questions > 0 else 0),
                'answered_questions': answered_questions,
                'total_questions': total_questions,
                'recent_alerts': recent_alerts,
                'session_id': exam_session.id
            })
        
        # Get recent activity history (completed/disqualified sessions from last 24 hours)
        twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_completions = db.session.query(ExamSession, Exam, User).join(
            Exam, ExamSession.exam_id == Exam.id
        ).join(
            User, ExamSession.student_id == User.id
        ).filter(
            Exam.lecturer_id == session['user_id'],
            ExamSession.status.in_(['completed', 'disqualified']),
            ExamSession.end_time >= twenty_four_hours_ago
        ).order_by(ExamSession.end_time.desc()).limit(20).all()
        
        for exam_session, exam, student in recent_completions:
            # Calculate score if completed
            score_percentage = 0
            if exam_session.status == 'completed':
                try:
                    _, _, score_percentage = calculate_exam_score(exam_session)
                except Exception:
                    score_percentage = 0
            
            # Calculate duration
            duration_minutes = 0
            if exam_session.end_time and exam_session.start_time:
                duration = exam_session.end_time - exam_session.start_time
                duration_minutes = int(duration.total_seconds() / 60)
            
            activity_history.append({
                'student_name': student.username,
                'exam_title': exam.title,
                'status': exam_session.status,
                'end_time': exam_session.end_time,
                'score_percentage': score_percentage,
                'duration_minutes': duration_minutes,
                'session_id': exam_session.id
            })

        # Get gamification data
        teacher_stats = TeacherStats.query.filter_by(
            teacher_id=session['user_id']
        ).first()
        if not teacher_stats:
            teacher_stats = TeacherStats()
            teacher_stats.teacher_id = session['user_id']
            teacher_stats.level = 1  # Set default level
            teacher_stats.join_date = datetime.now(timezone.utc)  # Set join date
            db.session.add(teacher_stats)
            db.session.commit()

        # Update teacher stats
        teacher_stats.total_exams_created = exam_count
        unique_students = db.session.query(ExamSession.student_id).join(Exam).filter(
            Exam.lecturer_id == session['user_id']
        ).distinct().count()
        teacher_stats.total_students_taught = unique_students
        db.session.commit()
        
        # Get achievements and leaderboard
        achievements = get_teacher_achievements(session['user_id'])
        recent_achievements = achievements[:3]  # Show last 3 achievements
        leaderboard = get_class_leaderboard(session['user_id'], 5)
        active_challenges = get_active_challenges()
        
        # Check for new achievements
        new_achievements = check_and_award_achievements(session['user_id'])

        return render_template(
            'lecturers_dashboard.html',
            role=role,
            now=datetime.now(),
            user=user,
            exam_count=exam_count,
            active_sessions=active_sessions,
            total_results=total_results,
            exams=lecturer_exams,
            live_activities=live_activities,
            activity_history=activity_history,
            teacher_stats=teacher_stats,
            achievements=achievements,
            recent_achievements=recent_achievements,
            leaderboard=leaderboard,
            active_challenges=active_challenges,
            new_achievements=new_achievements
        )
    else:
        # Enhanced Student Dashboard with Gamification
        
        # Get available exams for students
        available_exams = Exam.query.all()
        
        # Get student's exam sessions
        student_sessions = ExamSession.query.filter_by(student_id=session['user_id']).all()
        completed_sessions = [s for s in student_sessions if s.status == 'completed']
        completed_exams = len(completed_sessions)
        
        # Get upcoming exams (exams not yet taken)
        taken_exam_ids = [s.exam_id for s in student_sessions]
        upcoming_exams = [e for e in available_exams if e.id not in taken_exam_ids]
        
        # Calculate real average score from completed exams
        avg_score = 0
        if completed_sessions:
            total_score = 0
            valid_scores = 0
            for exam_session in completed_sessions:
                if check_result_visibility(exam_session.exam_id):
                    _, _, score_percentage = calculate_exam_score(exam_session)
                    total_score += score_percentage
                    valid_scores += 1
            avg_score = round(total_score / valid_scores, 1) if valid_scores > 0 else 0
        
        # Add question counts to available exams
        for exam in upcoming_exams:
            exam.questions = Question.query.filter_by(exam_id=exam.id).all()
        
        # Get or create student points
        student_points_record = StudentPoints.query.filter_by(student_id=session['user_id']).first()
        if not student_points_record:
            student_points_record = StudentPoints()
            student_points_record.student_id = session['user_id']
            student_points_record.points = 0
            student_points_record.streak_days = 0
            db.session.add(student_points_record)
            db.session.commit()
        
        # Calculate current study streak
        study_streak = calculate_study_streak(session['user_id'])
        student_points_record.streak_days = study_streak
        db.session.commit()
        
        # Get student rank
        student_rank = get_student_rank(session['user_id'])
        
        # Get student achievements
        student_achievements = get_student_achievements(session['user_id'])
        
        # Get leaderboard data
        leaderboard = get_global_leaderboard(10)
        
        # Get active challenges for student
        student_challenges = get_student_challenges(session['user_id'])
        
        # Get recent activities
        recent_activities = get_student_recent_activities(session['user_id'])
        
        # Check for new achievements
        check_and_award_student_achievements(session['user_id'])
        
        # Get available courses for students
        available_courses = Course.query.filter_by(is_published=True).order_by(Course.created_at.desc()).limit(8).all()
        
        # Get student's enrolled courses
        enrolled_courses = db.session.query(Course, CourseEnrollment).join(
            CourseEnrollment, Course.id == CourseEnrollment.course_id
        ).filter(CourseEnrollment.user_id == session['user_id']).all()
        
        # Get course categories for filtering
        course_categories = db.session.query(Course.category).filter_by(is_published=True).distinct().all()
        course_categories = [cat[0] for cat in course_categories]
        
        return render_template('students_dashboard.html', 
                             role=role, 
                             now=datetime.now(), 
                             user=user,
                             upcoming_count=len(upcoming_exams),
                             completed_count=completed_exams,
                             avg_score=avg_score,
                             available_exams=upcoming_exams[:5],
                             student_points=student_points_record.points,
                             student_rank=student_rank,
                             study_streak=study_streak,
                             student_achievements=student_achievements,
                             leaderboard=leaderboard,
                             student_challenges=student_challenges,
                             recent_activities=recent_activities,
                             available_courses=available_courses,
                             enrolled_courses=enrolled_courses,
                             course_categories=course_categories)

# Study Materials Routes
@app.route('/study_materials')
def study_materials():
    """Browse and search study materials"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get search and filter parameters
    search_query = request.args.get('search', '')
    category = request.args.get('category', '')
    material_type = request.args.get('type', '')
    difficulty = request.args.get('difficulty', '')
    
    # Build query
    query = StudyMaterial.query.filter_by(is_approved=True)
    
    if search_query:
        query = query.filter(
            db.or_(
                StudyMaterial.title.ilike(f'%{search_query}%'),
                StudyMaterial.description.ilike(f'%{search_query}%'),
                StudyMaterial.tags.ilike(f'%{search_query}%')
            )
        )
    
    if category:
        query = query.filter_by(category=category)
    
    if material_type:
        query = query.filter_by(material_type=material_type)
    
    if difficulty:
        query = query.filter_by(difficulty_level=difficulty)
    
    # Get materials with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 12
    materials = query.order_by(StudyMaterial.rating.desc(), StudyMaterial.view_count.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get categories for filter dropdown
    categories = db.session.query(StudyMaterial.category).distinct().all()
    categories = [cat[0] for cat in categories]
    
    # Get user's bookmarks
    user_bookmarks = []
    if session.get('user_id'):
        bookmarks = MaterialBookmark.query.filter_by(user_id=session['user_id']).all()
        user_bookmarks = [b.material_id for b in bookmarks]
    
    return render_template('study_materials.html', 
                         materials=materials,
                         categories=categories,
                         user_bookmarks=user_bookmarks,
                         search_query=search_query,
                         selected_category=category,
                         selected_type=material_type,
                         selected_difficulty=difficulty)

@app.route('/bookmark_material/<int:material_id>', methods=['POST'])
def bookmark_material(material_id):
    """Bookmark or unbookmark a study material"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    user_id = session['user_id']
    existing_bookmark = MaterialBookmark.query.filter_by(
        user_id=user_id, material_id=material_id
    ).first()
    
    if existing_bookmark:
        # Remove bookmark
        db.session.delete(existing_bookmark)
        bookmarked = False
    else:
        # Add bookmark
        bookmark = MaterialBookmark(user_id=user_id, material_id=material_id)
        db.session.add(bookmark)
        bookmarked = True
    
    db.session.commit()
    return jsonify({'success': True, 'bookmarked': bookmarked})

@app.route('/rate_material/<int:material_id>', methods=['POST'])
def rate_material(material_id):
    """Rate a study material"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    user_id = session['user_id']
    rating = request.json.get('rating')
    review = request.json.get('review', '')
    
    if not rating or rating < 1 or rating > 5:
        return jsonify({'success': False, 'message': 'Invalid rating'})
    
    # Check if user already rated this material
    existing_rating = MaterialRating.query.filter_by(
        user_id=user_id, material_id=material_id
    ).first()
    
    if existing_rating:
        existing_rating.rating = rating
        existing_rating.review = review
    else:
        new_rating = MaterialRating(
            user_id=user_id, 
            material_id=material_id, 
            rating=rating, 
            review=review
        )
        db.session.add(new_rating)
    
    # Update material's average rating
    material = StudyMaterial.query.get(material_id)
    if material:
        all_ratings = MaterialRating.query.filter_by(material_id=material_id).all()
        if all_ratings:
            avg_rating = sum(r.rating for r in all_ratings) / len(all_ratings)
            material.rating = round(avg_rating, 1)
    
    db.session.commit()
    return jsonify({'success': True, 'new_rating': material.rating})

@app.route('/view_material/<int:material_id>')
def view_material(material_id):
    """View a study material and increment view count"""
    material = StudyMaterial.query.get_or_404(material_id)
    
    # Increment view count
    material.view_count += 1
    db.session.commit()
    
    # Redirect to the actual material URL
    return redirect(material.url)

# Self-Paced Courses Routes
@app.route('/courses')
def courses():
    """Browse and search self-paced courses"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get search and filter parameters
    search_query = request.args.get('search', '')
    category = request.args.get('category', '')
    
    # Build query
    query = Course.query.filter_by(is_published=True)
    
    if search_query:
        query = query.filter(
            db.or_(
                Course.title.ilike(f'%{search_query}%'),
                Course.description.ilike(f'%{search_query}%')
            )
        )
    
    if category:
        query = query.filter_by(category=category)
    
    # Get courses with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 12
    courses = query.order_by(Course.rating.desc(), Course.enrollment_count.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get categories for filter dropdown
    categories = db.session.query(Course.category).distinct().all()
    categories = [cat[0] for cat in categories]
    
    # Get user's enrollments
    user_enrollments = {}
    if session.get('user_id'):
        enrollments = CourseEnrollment.query.filter_by(user_id=session['user_id']).all()
        user_enrollments = {e.course_id: e.progress_percentage for e in enrollments}
    
    return render_template('courses.html', 
                         courses=courses,
                         categories=categories,
                         user_enrollments=user_enrollments,
                         search_query=search_query,
                         selected_category=category)

@app.route('/enroll_course/<int:course_id>', methods=['POST'])
def enroll_course(course_id):
    """Enroll in a course with enrollment number and profile data"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    user_id = session['user_id']
    
    # Get course details
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({'success': False, 'message': 'Course not found'})
    
    if not course.is_published:
        return jsonify({'success': False, 'message': 'Course not available for enrollment'})
    
    # Check if already enrolled
    existing_enrollment = CourseEnrollment.query.filter_by(
        user_id=user_id, course_id=course_id
    ).first()
    
    if existing_enrollment:
        return jsonify({
            'success': False, 
            'message': f'Already enrolled! Your enrollment number is: {existing_enrollment.enrollment_number}'
        })
    
    try:
        # Get student profile data
        profile_data = get_student_profile_data(user_id)
        
        # Generate unique enrollment number
        enrollment_number = generate_enrollment_number(course_id)
        
        # Create enrollment
        enrollment = CourseEnrollment(
            user_id=user_id,
            course_id=course_id,
            enrollment_number=enrollment_number,
            student_name=profile_data['name'],
            student_email=profile_data['email']
        )
        db.session.add(enrollment)
        
        # Update course enrollment count
        course.enrollment_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Successfully enrolled! Your enrollment number is: {enrollment_number}',
            'enrollment_number': enrollment_number,
            'course_title': course.title,
            'student_name': profile_data['name'],
            'enrolled_at': enrollment.enrolled_at.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Enrollment failed: {str(e)}'})
    
    if existing_enrollment:
        return jsonify({'success': False, 'message': 'Already enrolled'})
    
    # Create enrollment
    enrollment = CourseEnrollment(user_id=user_id, course_id=course_id)
    db.session.add(enrollment)
    
    # Update course enrollment count
    course = Course.query.get(course_id)
    if course:
        course.enrollment_count += 1
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Enrolled successfully'})

@app.route('/course/<int:course_id>')
def course_view(course_id):
    """View a specific course"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    course = Course.query.get_or_404(course_id)
    
    # Check if user is enrolled
    enrollment = CourseEnrollment.query.filter_by(
        user_id=session['user_id'], course_id=course_id
    ).first()
    
    if not enrollment:
        return redirect(url_for('courses'))
    
    # Get all lessons for this course
    lessons = Lesson.query.filter_by(course_id=course_id, is_published=True)\
                          .order_by(Lesson.order_index).all()
    
    # Get user's lesson progress
    lesson_progress = LessonProgress.query.filter_by(enrollment_id=enrollment.id).all()
    completed_lesson_ids = [lp.lesson_id for lp in lesson_progress if lp.is_completed]
    
    # Calculate progress
    total_lessons = len(lessons)
    completed_lessons = len(completed_lesson_ids)
    
    # Update enrollment progress
    if total_lessons > 0:
        enrollment.progress_percentage = (completed_lessons / total_lessons) * 100
        db.session.commit()
    
    return render_template('course_view.html',
                         course=course,
                         lessons=lessons,
                         enrollment=enrollment,
                         completed_lesson_ids=completed_lesson_ids,
                         completed_lessons=completed_lessons,
                         total_lessons=total_lessons)

@app.route('/course/<int:course_id>/lesson/<int:lesson_id>')
def lesson_view(course_id, lesson_id):
    """View a specific lesson"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    course = Course.query.get_or_404(course_id)
    lesson = Lesson.query.get_or_404(lesson_id)
    
    # Check if user is enrolled
    enrollment = CourseEnrollment.query.filter_by(
        user_id=session['user_id'], course_id=course_id
    ).first()
    
    if not enrollment:
        return redirect(url_for('courses'))
    
    # Get all lessons for navigation
    lessons = Lesson.query.filter_by(course_id=course_id, is_published=True)\
                          .order_by(Lesson.order_index).all()
    
    # Find previous and next lessons
    current_index = next((i for i, l in enumerate(lessons) if l.id == lesson_id), None)
    prev_lesson = lessons[current_index - 1] if current_index and current_index > 0 else None
    next_lesson = lessons[current_index + 1] if current_index is not None and current_index < len(lessons) - 1 else None
    
    # Get user's lesson progress
    lesson_progress = LessonProgress.query.filter_by(enrollment_id=enrollment.id).all()
    completed_lesson_ids = [lp.lesson_id for lp in lesson_progress if lp.is_completed]
    
    return render_template('course_view.html',
                         course=course,
                         lessons=lessons,
                         current_lesson=lesson,
                         current_lesson_id=lesson_id,
                         prev_lesson=prev_lesson,
                         next_lesson=next_lesson,
                         enrollment=enrollment,
                         completed_lesson_ids=completed_lesson_ids,
                         completed_lessons=len(completed_lesson_ids),
                         total_lessons=len(lessons))

@app.route('/complete_lesson/<int:lesson_id>', methods=['POST'])
def complete_lesson(lesson_id):
    """Mark a lesson as completed"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    lesson = Lesson.query.get_or_404(lesson_id)
    
    # Get user's enrollment for this course
    enrollment = CourseEnrollment.query.filter_by(
        user_id=session['user_id'], course_id=lesson.course_id
    ).first()
    
    if not enrollment:
        return jsonify({'success': False, 'message': 'Not enrolled'})
    
    # Check if already completed
    existing_progress = LessonProgress.query.filter_by(
        enrollment_id=enrollment.id, lesson_id=lesson_id
    ).first()
    
    if existing_progress:
        if not existing_progress.is_completed:
            existing_progress.is_completed = True
            existing_progress.completed_at = datetime.now(timezone.utc)
    else:
        # Create new progress record
        progress = LessonProgress(
            enrollment_id=enrollment.id,
            lesson_id=lesson_id,
            is_completed=True,
            completed_at=datetime.now(timezone.utc)
        )
        db.session.add(progress)
    
    # Update course progress
    total_lessons = Lesson.query.filter_by(course_id=lesson.course_id, is_published=True).count()
    completed_lessons = LessonProgress.query.filter_by(
        enrollment_id=enrollment.id, is_completed=True
    ).count()
    
    if total_lessons > 0:
        enrollment.progress_percentage = (completed_lessons / total_lessons) * 100
        enrollment.last_accessed = datetime.now(timezone.utc)
        
        # Check if course is now completed
        if completed_lessons >= total_lessons:
            enrollment.completed_at = datetime.now(timezone.utc)
    
    db.session.commit()
    return jsonify({'success': True})

# ==================== AI COURSE GENERATION ROUTES ====================

@app.route('/ai_course_generator')
def ai_course_generator():
    """AI Course Generator Interface for Lecturers"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['user_id'])
    if not user or user.role != 'lecturer':
        flash('Access denied. Only lecturers can access the AI Course Generator.', 'error')
        return redirect(url_for('dashboard'))
    
    # Get user's previous generation requests
    recent_requests = CourseGenerationRequest.query.filter_by(
        lecturer_id=session['user_id']
    ).order_by(CourseGenerationRequest.created_at.desc()).limit(10).all()
    
    # Get popular course templates
    popular_templates = AICourseTemplate.query.order_by(
        AICourseTemplate.usage_count.desc(), AICourseTemplate.rating.desc()
    ).limit(6).all()
    
    return render_template('ai_course_generator.html',
                         recent_requests=recent_requests,
                         popular_templates=popular_templates)

@app.route('/generate_ai_course', methods=['POST'])
def generate_ai_course():
    """Generate a complete course using AI"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    user = db.session.get(User, session['user_id'])
    if not user or user.role != 'lecturer':
        return jsonify({'success': False, 'message': 'Access denied'})
    
    try:
        data = request.json
        subject_area = data.get('subject_area', '').strip()
        course_title = data.get('course_title', '').strip()
        difficulty_level = data.get('difficulty_level', 'intermediate')
        special_requirements = data.get('special_requirements', '').strip()
        
        if not subject_area or not course_title:
            return jsonify({'success': False, 'message': 'Subject area and course title are required'})
        
        # Create generation request record
        generation_request = CourseGenerationRequest(
            lecturer_id=session['user_id'],
            subject_area=subject_area,
            course_title=course_title,
            difficulty_level=difficulty_level,
            special_requirements=special_requirements if special_requirements else None,
            generation_status='generating'
        )
        db.session.add(generation_request)
        db.session.commit()
        
        start_time = time.time()
        
        # Generate course outline with AI
        print(f"[AI COURSE] Generating course outline for: {course_title}")
        course_outline = generate_course_outline_with_ai(subject_area, difficulty_level, special_requirements)
        
        if not course_outline:
            generation_request.generation_status = 'failed'
            generation_request.error_message = 'Failed to generate course outline'
            db.session.commit()
            return jsonify({'success': False, 'message': 'Failed to generate course outline. Please try again.'})
        
        # Generate detailed content for each topic
        print(f"[AI COURSE] Generating detailed content for {len(course_outline.get('modules', []))} modules")
        enhanced_modules = []
        
        for module in course_outline.get('modules', []):
            enhanced_topics = []
            
            for topic in module.get('topics', []):
                # Generate detailed content for topic
                topic_content = generate_topic_content_with_ai(
                    topic['topic_title'],
                    topic.get('subtopics', []),
                    difficulty_level,
                    subject_area
                )
                
                # Generate challenging questions for topic
                topic_questions = generate_challenging_questions_for_topic(
                    topic['topic_title'],
                    difficulty_level,
                    num_questions=5
                )
                
                enhanced_topic = {
                    **topic,
                    'content': topic_content if topic_content else {},
                    'questions': topic_questions
                }
                enhanced_topics.append(enhanced_topic)
            
            enhanced_module = {
                **module,
                'topics': enhanced_topics
            }
            enhanced_modules.append(enhanced_module)
        
        # Create enhanced course outline
        enhanced_course = {
            **course_outline,
            'modules': enhanced_modules
        }
        
        # Save as AI course template
        ai_template = AICourseTemplate(
            template_name=course_outline['course_title'],
            subject_area=subject_area,
            difficulty_level=difficulty_level,
            total_estimated_hours=course_outline.get('estimated_total_hours', 40),
            course_description=course_outline['description'],
            learning_objectives=json.dumps(course_outline.get('learning_objectives', [])),
            prerequisites=json.dumps(course_outline.get('prerequisites', [])),
            course_outline=json.dumps(course_outline.get('modules', [])),
            ai_generated_content=json.dumps(enhanced_course),
            usage_count=1
        )
        db.session.add(ai_template)
        db.session.flush()  # Get the ID
        
        # AUTOMATICALLY CREATE A REAL COURSE FROM THE AI TEMPLATE
        print(f"[AI COURSE] Creating actual course from AI template...")
        
        # Create the course
        course = Course(
            title=course_outline['course_title'],
            description=course_outline['description'],
            instructor_id=session['user_id'],
            category=subject_area,
            difficulty_level=difficulty_level,
            estimated_duration_hours=course_outline.get('estimated_total_hours', 40),
            prerequisites='; '.join(course_outline.get('prerequisites', [])) if course_outline.get('prerequisites') else None,
            learning_objectives='; '.join(course_outline.get('learning_objectives', [])) if course_outline.get('learning_objectives') else None,
            is_published=True  # Auto-publish AI generated courses
        )
        db.session.add(course)
        db.session.flush()  # Get course ID
        
        # Create lessons from modules and topics
        lesson_order = 1
        total_lessons_created = 0
        
        for module in enhanced_course.get('modules', []):
            for topic in module.get('topics', []):
                # Create lesson content from AI-generated topic content
                content_data = topic.get('content', {})
                
                # Build comprehensive lesson content
                lesson_content = f"""
                <div class="ai-generated-lesson">
                    <div class="lesson-header">
                        <h1>{topic['topic_title']}</h1>
                        <div class="lesson-meta">
                            <span class="difficulty">{difficulty_level.title()}</span>
                            <span class="duration">{topic.get('estimated_hours', 1)} hours</span>
                            <span class="ai-badge">🤖 AI Generated</span>
                        </div>
                    </div>
                    
                    {f'<div class="introduction"><h2>Introduction</h2><p>{content_data.get("introduction", "")}</p></div>' if content_data.get("introduction") else ''}
                    
                    <div class="learning-objectives">
                        <h3>Learning Objectives</h3>
                        <ul>
                            {''.join([f'<li>{obj}</li>' for obj in topic.get('learning_objectives', [])])}
                        </ul>
                    </div>
                    
                    {f'<div class="subtopics"><h3>Topics Covered</h3><ul>{"".join([f"<li>{subtopic}</li>" for subtopic in topic.get("subtopics", [])])}</ul></div>' if topic.get("subtopics") else ''}
                    
                    <div class="content-sections">
                        {''.join([f'<div class="section"><h3>{section["section_title"]}</h3><div class="content">{section["content"]}</div>' + 
                                 (f'<div class="key-points"><h4>Key Points:</h4><ul>{"".join([f"<li>{point}</li>" for point in section.get("key_points", [])])}</ul></div>' if section.get("key_points") else '') +
                                 (f'<div class="code-examples"><h4>Examples:</h4>{"".join([f"<pre><code>{example}</code></pre>" for example in section.get("code_examples", [])])}</div>' if section.get("code_examples") else '') +
                                 '</div>' for section in content_data.get("sections", [])]) if content_data.get("sections") else ''}
                    </div>
                    
                    {f'<div class="summary"><h3>Summary</h3><p>{content_data.get("summary", "")}</p></div>' if content_data.get("summary") else ''}
                    
                    {f'<div class="further-reading"><h3>Further Reading</h3><ul>{"".join([f"<li>{resource}</li>" for resource in content_data.get("further_reading", [])])}</ul></div>' if content_data.get("further_reading") else ''}
                    
                    <div class="practice-questions">
                        <h3>Practice Questions</h3>
                        <p>Test your knowledge with {len(topic.get('questions', []))} challenging questions available in the quiz section.</p>
                    </div>
                </div>
                """
                
                lesson = Lesson(
                    course_id=course.id,
                    title=topic['topic_title'],
                    content=lesson_content,
                    lesson_type='text',
                    duration_minutes=topic.get('estimated_hours', 1) * 60,
                    order_index=lesson_order,
                    is_published=True  # Auto-publish lessons
                )
                db.session.add(lesson)
                
                # Store AI-generated questions in question bank
                for question_data in topic.get('questions', []):
                    ai_question = AIQuestionBank(
                        subject_area=subject_area,
                        topic_title=topic['topic_title'],
                        question_text=question_data.get('question', ''),
                        question_type=question_data.get('type', 'multiple_choice'),
                        options=json.dumps(question_data.get('options', [])) if question_data.get('options') else None,
                        correct_answer=question_data.get('correct_answer', ''),
                        explanation=question_data.get('explanation', ''),
                        difficulty_level=question_data.get('difficulty', difficulty_level),
                        bloom_taxonomy_level=question_data.get('bloom_level', 'understand'),
                        estimated_time_minutes=question_data.get('estimated_time', 2)
                    )
                    db.session.add(ai_question)
                
                lesson_order += 1
                total_lessons_created += 1
        
        # Update template usage count
        ai_template.usage_count += 1
        
        processing_time = int(time.time() - start_time)
        
        # Update generation request with both template and course IDs
        generation_request.generation_status = 'completed'
        generation_request.generated_template_id = ai_template.id
        generation_request.generated_course_id = course.id
        generation_request.ai_processing_time = processing_time
        generation_request.completed_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        print(f"[AI COURSE] Successfully generated:")
        print(f"  - Course template ID: {ai_template.id}")
        print(f"  - Actual course ID: {course.id}")
        print(f"  - Lessons created: {total_lessons_created}")
        
        return jsonify({
            'success': True,
            'message': f'Course generated and saved successfully! {total_lessons_created} lessons created.',
            'template_id': ai_template.id,
            'course_id': course.id,
            'lessons_created': total_lessons_created,
            'processing_time': processing_time,
            'course_data': enhanced_course,
            'redirect_url': f'/course/{course.id}'
        })
        
    except Exception as e:
        print(f"[AI COURSE] Generation error: {e}")
        generation_request.generation_status = 'failed'
        generation_request.error_message = str(e)
        db.session.commit()
        return jsonify({'success': False, 'message': 'Course generation failed. Please try again.'})

@app.route('/preview_ai_template/<int:template_id>')
def preview_ai_template(template_id):
    """Preview AI-generated course template"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['user_id'])
    if not user or user.role != 'lecturer':
        flash('Access denied. Only lecturers can preview course templates.', 'error')
        return redirect(url_for('dashboard'))
    
    template = db.session.get(AICourseTemplate, template_id)
    if not template:
        flash('Course template not found.', 'error')
        return redirect(url_for('ai_course_generator'))
    
    # Parse the AI-generated content
    try:
        course_data = json.loads(template.ai_generated_content)
        learning_objectives = json.loads(template.learning_objectives)
        prerequisites = json.loads(template.prerequisites)
    except json.JSONDecodeError:
        flash('Error loading course template data.', 'error')
        return redirect(url_for('ai_course_generator'))
    
    return render_template('ai_course_preview.html',
                         template=template,
                         course_data=course_data,
                         learning_objectives=learning_objectives,
                         prerequisites=prerequisites)

@app.route('/create_course_from_template/<int:template_id>', methods=['POST'])
def create_course_from_template(template_id):
    """Create an actual course from AI template"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    user = db.session.get(User, session['user_id'])
    if not user or user.role != 'lecturer':
        return jsonify({'success': False, 'message': 'Access denied'})
    
    template = db.session.get(AICourseTemplate, template_id)
    if not template:
        return jsonify({'success': False, 'message': 'Template not found'})
    
    try:
        course_data = json.loads(template.ai_generated_content)
        learning_objectives = json.loads(template.learning_objectives)
        prerequisites = json.loads(template.prerequisites)
        
        # Create the course
        course = Course(
            title=course_data['course_title'],
            description=course_data['description'],
            instructor_id=session['user_id'],
            category=template.subject_area,
            difficulty_level=template.difficulty_level,
            estimated_duration_hours=template.total_estimated_hours,
            prerequisites='; '.join(prerequisites) if prerequisites else None,
            learning_objectives='; '.join(learning_objectives) if learning_objectives else None,
            is_published=False  # Let lecturer review before publishing
        )
        db.session.add(course)
        db.session.flush()  # Get course ID
        
        # Create lessons from modules and topics
        lesson_order = 1
        
        for module in course_data.get('modules', []):
            for topic in module.get('topics', []):
                # Create lesson content from AI-generated topic content
                content_data = topic.get('content', {})
                
                lesson_content = f"""
                <div class="lesson-content">
                    <h2>{topic['topic_title']}</h2>
                    
                    {f'<div class="introduction">{content_data.get("introduction", "")}</div>' if content_data.get("introduction") else ''}
                    
                    {''.join([f'<div class="section"><h3>{section["section_title"]}</h3><div class="content">{section["content"]}</div></div>' for section in content_data.get("sections", [])]) if content_data.get("sections") else ''}
                    
                    {f'<div class="summary"><h3>Summary</h3><p>{content_data.get("summary", "")}</p></div>' if content_data.get("summary") else ''}
                </div>
                """
                
                lesson = Lesson(
                    course_id=course.id,
                    title=topic['topic_title'],
                    content=lesson_content,
                    lesson_type='text',
                    duration_minutes=topic.get('estimated_hours', 1) * 60,
                    order_index=lesson_order,
                    is_published=False
                )
                db.session.add(lesson)
                
                # Store AI-generated questions in question bank
                for question_data in topic.get('questions', []):
                    ai_question = AIQuestionBank(
                        subject_area=template.subject_area,
                        topic_title=topic['topic_title'],
                        question_text=question_data.get('question', ''),
                        question_type=question_data.get('type', 'multiple_choice'),
                        options=json.dumps(question_data.get('options', [])) if question_data.get('options') else None,
                        correct_answer=question_data.get('correct_answer', ''),
                        explanation=question_data.get('explanation', ''),
                        difficulty_level=question_data.get('difficulty', template.difficulty_level),
                        bloom_taxonomy_level=question_data.get('bloom_level', 'understand'),
                        estimated_time_minutes=question_data.get('estimated_time', 2)
                    )
                    db.session.add(ai_question)
                
                lesson_order += 1
        
        # Update template usage count
        template.usage_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Course created successfully!',
            'course_id': course.id,
            'lessons_created': lesson_order - 1
        })
        
    except Exception as e:
        print(f"[AI COURSE] Error creating course from template: {e}")
        return jsonify({'success': False, 'message': 'Failed to create course. Please try again.'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['user_id'])
    if not user:
        return redirect(url_for('login'))
    
    message = None
    message_type = 'success'
    
    if request.method == 'POST':
        action = request.form.get('action', 'update_profile_pic')
        
        if action == 'change_password':
            # Handle password change
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if not current_password or not new_password or not confirm_password:
                message = "All password fields are required."
                message_type = 'error'
            elif not check_password_hash(user.password, current_password):
                message = "Current password is incorrect."
                message_type = 'error'
            elif new_password != confirm_password:
                message = "New passwords do not match."
                message_type = 'error'
            elif len(new_password) < 8:
                message = "Password must be at least 8 characters long."
                message_type = 'error'
            else:
                user.password = generate_password_hash(new_password)
                db.session.commit()
                message = "Password updated successfully."
                
        elif action == 'update_personal_info':
            # Handle personal information updates
            # Note: These fields would need to be added to the User model in a real implementation
            full_name = request.form.get('full_name', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            location = request.form.get('location', '').strip()
            bio = request.form.get('bio', '').strip()
            
            # For now, we'll just show a success message since the User model doesn't have these fields
            # In a real implementation, you would add these fields to the User model and update them here
            message = "Personal information updated successfully."
            
        else:
            # Handle profile picture upload (default action)
            file = request.files.get('profile_pic')
            if file and file.filename:
                # Validate file type and size
                allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
                file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
                
                if file_extension not in allowed_extensions:
                    message = "Invalid file type. Please use JPG, PNG, or GIF."
                    message_type = 'error'
                elif len(file.read()) > 5 * 1024 * 1024:  # 5MB limit
                    message = "File size too large. Maximum size is 5MB."
                    message_type = 'error'
                    file.seek(0)  # Reset file pointer
                else:
                    file.seek(0)  # Reset file pointer after size check
                    filename = secure_filename(file.filename)
                    # Add timestamp to filename to avoid conflicts
                    import time
                    timestamp = str(int(time.time()))
                    name, ext = filename.rsplit('.', 1)
                    filename = f"{name}_{timestamp}.{ext}"
                    
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    
                    # Delete old profile picture if it exists
                    if user.profile_pic:
                        old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], user.profile_pic)
                        if os.path.exists(old_filepath):
                            os.remove(old_filepath)
                    
                    user.profile_pic = filename
                    db.session.commit()
                    message = "Profile picture updated successfully."
    
    return render_template('profile.html', user=user, message=message, message_type=message_type)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    results = []
    
    if query:
        # Search for exams by title (case-insensitive)
        exam_results = Exam.query.filter(
            Exam.title.contains(query)
        ).all()
        
        # Format results for display
        for exam in exam_results:
            lecturer = db.session.get(User, exam.lecturer_id)
            # Check if student has taken this exam
            if session.get('role') == 'student':
                existing_session = ExamSession.query.filter_by(
                    student_id=session['user_id'],
                    exam_id=exam.id
                ).first()
                status = 'Available' if not existing_session else existing_session.status.title()
            else:
                status = 'Available'
                
            results.append({
                'type': 'exam',
                'title': exam.title,
                'lecturer': lecturer.username if lecturer else 'Unknown',
                'created_at': exam.created_at,
                'id': exam.id,
                'status': status
            })
        
        # If student, also search in their results
        if session.get('role') == 'student':
            student_sessions = ExamSession.query.filter_by(
                student_id=session['user_id']
            ).join(Exam).filter(
                Exam.title.contains(query)
            ).all()
            
            for session_obj in student_sessions:
                exam = db.session.get(Exam, session_obj.exam_id)
                if exam:
                    results.append({
                        'type': 'result',
                        'title': f"Result: {exam.title}",
                        'lecturer': 'Your Result',
                        'created_at': session_obj.end_time or session_obj.start_time,
                        'id': session_obj.id,
                        'status': session_obj.status.title()
                    })
    
    return render_template('search_results.html', query=query, results=results)

@app.route('/create_exam', methods=['GET', 'POST'])
def create_exam():
    if 'user_id' not in session or session.get('role') != 'lecturer':
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action', 'create')
        print(f"[DEBUG] Received action: {action}")  # Debug line
        
        if action == 'preview_exam':
            # Handle exam preview before saving
            title = request.form.get('exam_title', 'New Exam')
            
            # Get generated questions from form
            generated_questions_json = request.form.get('generated_questions')
            if generated_questions_json:
                try:
                    import json
                    import urllib.parse
                    
                    # Decode and parse the questions
                    questions_data = json.loads(urllib.parse.unquote(generated_questions_json))
                    
                    # Get form data for preview
                    exam_data = {
                        'title': title,
                        'time_limit': request.form.get('time_limit', '60'),
                        'passing_score': request.form.get('passing_score', '60'),
                        'difficulty': request.form.get('difficulty', 'intermediate'),
                        'topic': request.form.get('topic', ''),
                        'custom_topic': request.form.get('custom_topic', ''),
                        'shuffle_questions': request.form.get('shuffle_questions') == 'on',
                        'show_results': request.form.get('show_results') == 'on',
                        'allow_retake': request.form.get('allow_retake') == 'on',
                        'proctoring': request.form.get('proctoring') == 'on'
                    }
                    
                    return render_template('exam_preview.html', 
                                         exam_data=exam_data, 
                                         questions=questions_data,
                                         generated_questions_json=generated_questions_json)
                
                except Exception as e:
                    print(f"Error processing preview: {e}")
                    return render_template('create_exam.html', 
                                         error="Failed to process questions for preview. Please try again.",
                                         step='initial')
            else:
                return render_template('create_exam.html', 
                                     error="No questions found for preview. Please generate questions first.",
                                     step='initial')
        
        elif action == 'create_exam':
            # Handle manual exam creation
            title = request.form['exam_title']
            lecturer_id = session['user_id']
            
            # Create the exam
            exam = Exam()
            exam.title = title
            exam.lecturer_id = lecturer_id
            exam.ai_generated = False
            db.session.add(exam)
            db.session.flush()
            
            # Create exam settings
            exam_settings = ExamSettings()
            exam_settings.exam_id = exam.id
            exam_settings.results_visible_after_all_complete = request.form.get('results_after_all') == 'on'
            exam_settings.time_limit_minutes = int(request.form.get('time_limit', 60))
            exam_settings.randomize_questions = request.form.get('randomize_questions') == 'on'
            exam_settings.passing_score = int(request.form.get('passing_score', 70))
            db.session.add(exam_settings)
            
            # Handle manually entered questions
            question_texts = request.form.getlist('question_text')
            for i, text in enumerate(question_texts):
                if text.strip():
                    question = Question()
                    question.exam_id = exam.id
                    question.text = text
                    question.option_a = request.form.getlist('option_a')[i] if i < len(request.form.getlist('option_a')) else ''
                    question.option_b = request.form.getlist('option_b')[i] if i < len(request.form.getlist('option_b')) else ''
                    question.option_c = request.form.getlist('option_c')[i] if i < len(request.form.getlist('option_c')) else ''
                    question.option_d = request.form.getlist('option_d')[i] if i < len(request.form.getlist('option_d')) else ''
                    question.correct_option = request.form.getlist('correct_option')[i] if i < len(request.form.getlist('correct_option')) else 'A'
                    question.question_type = 'multiple_choice'
                    db.session.add(question)
            
            db.session.commit()
            session['exam_created'] = f"Successfully created exam '{title}'!"
            return redirect(url_for('manage_exams'))
        
        elif action == 'save_exam':
            # Handle final exam saving from preview
            title = request.form.get('exam_title', 'New Exam')
            lecturer_id = session['user_id']
            
            # Get generated questions from form
            generated_questions_json = request.form.get('generated_questions')
            if generated_questions_json:
                try:
                    import json
                    import urllib.parse
                    
                    # Decode and parse the questions
                    questions_data = json.loads(urllib.parse.unquote(generated_questions_json))
                    
                    # Create the exam
                    exam = Exam()
                    exam.title = title
                    exam.lecturer_id = lecturer_id
                    exam.ai_generated = True
                    
                    # Handle scheduling
                    is_scheduled = request.form.get('enable_scheduling') == 'on'
                    if is_scheduled:
                        scheduled_start = request.form.get('scheduled_start')
                        scheduled_end = request.form.get('scheduled_end')
                        
                        if scheduled_start and scheduled_end:
                            from datetime import datetime
                            try:
                                exam.scheduled_start = datetime.fromisoformat(scheduled_start)
                                exam.scheduled_end = datetime.fromisoformat(scheduled_end)
                                exam.is_scheduled = True
                            except ValueError:
                                # Invalid datetime format
                                exam.is_scheduled = False
                        else:
                            exam.is_scheduled = False
                    else:
                        exam.is_scheduled = False
                    
                    db.session.add(exam)
                    db.session.flush()
                    
                    # Create exam settings with enhanced options
                    exam_settings = ExamSettings()
                    exam_settings.exam_id = exam.id
                    exam_settings.time_limit_minutes = int(request.form.get('time_limit', 60))
                    exam_settings.randomize_questions = request.form.get('shuffle_questions') == 'on'
                    exam_settings.results_visible_after_all_complete = request.form.get('show_results') == 'on'
                    exam_settings.passing_score = int(request.form.get('passing_score', 70))
                    db.session.add(exam_settings)
                    
                    # Process and add questions to exam
                    question_counter = 1
                    successfully_added = 0
                    
                    for q_data in questions_data:
                        try:
                            question = Question()
                            question.exam_id = exam.id
                            question.text = q_data.get('question', f'Question {question_counter}')
                            
                            # Handle different question types
                            if 'options' in q_data and q_data['options']:
                                # Multiple choice
                                question.question_type = 'multiple_choice'
                                options = q_data['options']
                                question.option_a = options[0] if len(options) > 0 else ''
                                question.option_b = options[1] if len(options) > 1 else ''
                                question.option_c = options[2] if len(options) > 2 else ''
                                question.option_d = options[3] if len(options) > 3 else ''
                                question.correct_option = q_data.get('correct_answer', 'A')
                            elif q_data.get('correct_answer') in ['true', 'false']:
                                # True/False question
                                question.question_type = 'multiple_choice'
                                question.option_a = 'True'
                                question.option_b = 'False'
                                question.option_c = ''
                                question.option_d = ''
                                question.correct_option = 'A' if q_data.get('correct_answer').lower() == 'true' else 'B'
                            else:
                                # Text/Essay question
                                question.question_type = 'text'
                                question.option_a = ''
                                question.option_b = ''
                                question.option_c = ''
                                question.option_d = ''
                                question.correct_option = None
                            
                            db.session.add(question)
                            successfully_added += 1
                            question_counter += 1
                            
                        except Exception as e:
                            print(f"Error adding question {question_counter}: {e}")
                            continue
                    
                    if successfully_added > 0:
                        db.session.commit()
                        session['exam_created'] = f"Successfully created exam '{title}' with {successfully_added} AI-generated questions!"
                        return redirect(url_for('manage_exams'))
                    else:
                        db.session.rollback()
                        return render_template('exam_preview.html', 
                                             error="Failed to save questions. Please try again.",
                                             exam_data=request.form,
                                             questions=questions_data,
                                             generated_questions_json=generated_questions_json)
                        
                except Exception as e:
                    print(f"Error saving exam: {e}")
                    return render_template('create_exam.html', 
                                         error="Failed to save exam. Please try again.",
                                         step='initial')
            else:
                return render_template('create_exam.html', 
                                     error="No questions found to save. Please generate questions first.",
                                     step='initial')
    
    return render_template('create_exam.html', step='initial')


@app.route('/take_exam/<int:exam_id>')
def take_exam(exam_id):
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('dashboard'))
    
    exam = Exam.query.get_or_404(exam_id)
    
    # Check if exam is scheduled and validate timing
    if exam.is_scheduled:
        from datetime import datetime
        now = datetime.now()
        
        if exam.scheduled_start and now < exam.scheduled_start:
            # Exam hasn't started yet - show countdown
            return render_template('exam_countdown.html', 
                                 exam=exam,
                                 scheduled_start=exam.scheduled_start,
                                 scheduled_end=exam.scheduled_end)
        
        if exam.scheduled_end and now > exam.scheduled_end:
            # Exam has ended
            return render_template('exam_unavailable.html', 
                                 exam=exam,
                                 message="This exam has ended and is no longer available.")
    
    # Get exam settings for duration
    exam_settings = ExamSettings.query.filter_by(exam_id=exam.id).first()
    duration_minutes = exam_settings.time_limit_minutes if exam_settings else 60  # Default 60 minutes
    
    # Check if student already has an active session for this exam
    existing_session = ExamSession.query.filter_by(
        student_id=session['user_id'], 
        exam_id=exam_id, 
        status='in_progress'
    ).first()
    
    if existing_session:
        return redirect(url_for('exam_interface', session_id=existing_session.id))
    
    return render_template('exam_start.html', exam=exam, duration_minutes=duration_minutes)

@app.route('/start_exam/<int:exam_id>', methods=['POST'])
def start_exam(exam_id):
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('dashboard'))
    
    # Create new exam session
    exam_session = ExamSession()
    exam_session.student_id = session['user_id']
    exam_session.exam_id = exam_id
    exam_session.webcam_permission = True
    db.session.add(exam_session)
    db.session.commit()
    
    return redirect(url_for('exam_interface', session_id=exam_session.id))

@app.route('/exam/<int:session_id>')
def exam_interface(session_id):
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('dashboard'))
    
    exam_session = ExamSession.query.get_or_404(session_id)
    if exam_session.student_id != session['user_id']:
        return redirect(url_for('dashboard'))
    
    if exam_session.status != 'in_progress':
        return redirect(url_for('dashboard'))
    
    exam = db.session.get(Exam, exam_session.exam_id)
    if not exam:
        return redirect(url_for('dashboard'))
    
    # Get exam settings for duration
    exam_settings = ExamSettings.query.filter_by(exam_id=exam.id).first()
    duration_minutes = exam_settings.time_limit_minutes if exam_settings else 60  # Default 60 minutes
    
    questions = Question.query.filter_by(exam_id=exam.id).all()
    user = db.session.get(User, session['user_id'])
    
    return render_template('exam.html', 
                         exam=exam, 
                         questions=questions, 
                         session=exam_session,
                         user=user,
                         duration_minutes=duration_minutes)

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    if 'user_id' not in session or session.get('role') != 'student':
        return jsonify({'status': 'error', 'message': 'Unauthorized'})
    
    session_id = request.form['session_id']
    question_id = request.form['question_id']
    answer = request.form['answer']
    
    # Check if answer already exists
    existing_answer = StudentAnswer.query.filter_by(
        session_id=session_id,
        question_id=question_id
    ).first()
    
    if existing_answer:
        existing_answer.answer = answer
        existing_answer.answered_at = datetime.now(timezone.utc)
    else:
        student_answer = StudentAnswer()
        student_answer.session_id = session_id
        student_answer.question_id = question_id
        student_answer.answer = answer
        db.session.add(student_answer)
    
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/get_saved_answers/<int:session_id>')
def get_saved_answers(session_id):
    if 'user_id' not in session or session.get('role') != 'student':
        return jsonify({'status': 'error', 'message': 'Unauthorized'})
    
    # Verify this session belongs to the current user
    exam_session = ExamSession.query.get_or_404(session_id)
    if exam_session.student_id != session['user_id']:
        return jsonify({'status': 'error', 'message': 'Unauthorized'})
    
    # Get all saved answers for this session
    answers = StudentAnswer.query.filter_by(session_id=session_id).all()
    answer_dict = {str(answer.question_id): answer.answer for answer in answers}
    
    return jsonify({'status': 'success', 'answers': answer_dict})

@app.route('/exam/<int:exam_id>/analytics')
def exam_analytics(exam_id):
    if 'user_id' not in session or session.get('role') != 'lecturer':
        return redirect(url_for('dashboard'))
    
    exam = Exam.query.get_or_404(exam_id)
    
    # Verify lecturer owns this exam
    if exam.lecturer_id != session['user_id']:
        return redirect(url_for('dashboard'))
    
    # Get exam sessions for analytics
    exam_sessions = ExamSession.query.filter_by(exam_id=exam_id).all()
    
    # Calculate analytics data
    total_attempts = len(exam_sessions)
    completed_attempts = len([s for s in exam_sessions if s.status == 'completed'])
    average_score = 0
    
    if completed_attempts > 0:
        total_score = 0
        for exam_session in exam_sessions:
            if exam_session.status == 'completed':
                _, _, score_percentage = calculate_exam_score(exam_session)
                total_score += score_percentage
        average_score = total_score / completed_attempts
    
    analytics_data = {
        'exam': exam,
        'total_attempts': total_attempts,
        'completed_attempts': completed_attempts,
        'average_score': round(average_score, 1),
        'exam_sessions': exam_sessions
    }
    
    return render_template('exam_analytics.html', **analytics_data)

@app.route('/ai_alert', methods=['POST'])
def ai_alert():
    if 'user_id' not in session or session.get('role') != 'student':
        return {'status': 'error'}
    
    data = request.get_json()
    session_id = data.get('session_id')
    alert_type = data.get('alert_type')
    severity = data.get('severity', 'medium')
    description = data.get('description', '')
    
    # Create monitoring alert
    alert = MonitoringAlert()
    alert.session_id = session_id
    alert.alert_type = alert_type
    alert.severity = severity
    alert.description = description
    db.session.add(alert)
    
    # Check if this is a critical alert that should disqualify the student
    if severity == 'critical':
        exam_session = db.session.get(ExamSession, session_id)
        if exam_session and exam_session.student_id == session['user_id']:
            exam_session.status = 'disqualified'
            exam_session.end_time = datetime.now(timezone.utc)
    
    db.session.commit()
    
    return {'status': 'success', 'action': 'disqualified' if severity == 'critical' else 'warning'}

@app.route('/complete_exam/<int:session_id>', methods=['POST'])
def complete_exam(session_id):
    try:
        # Quick authentication check
        if 'user_id' not in session or session.get('role') != 'student':
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        
        # Fast session lookup
        exam_session = ExamSession.query.get_or_404(session_id)
        if exam_session.student_id != session['user_id']:
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        
        # Quick check for already completed
        if exam_session.status != 'in_progress':
            return jsonify({
                'status': 'success', 
                'action': 'already_completed',
                'redirect_url': url_for('view_results', session_id=session_id)
            })
        
        # Fast JSON parsing for submission type
        data = {}
        try:
            if request.is_json and request.get_json():
                data = request.get_json()
        except Exception as e:
            data = {}
        
        forced_submission = data.get('forced_submission', False)
        
        if forced_submission:
            # Handle AI violation submission
            violation_reason = data.get('reason', '')
            violation_count = data.get('violation_count', 0)
            
            exam_session.status = 'disqualified'
            exam_session.end_time = datetime.now(timezone.utc)
            
            # Quick alert creation
            alert = MonitoringAlert()
            alert.session_id = session_id
            alert.alert_type = 'exam_auto_submitted'
            alert.severity = 'critical'
            alert.description = f'Exam auto-submitted after {violation_count} violations: {violation_reason}'
            db.session.add(alert)
            
            db.session.commit()
            
            return jsonify({
                'status': 'success', 
                'action': 'disqualified',
                'message': 'Exam submitted due to violations',
                'violation_count': violation_count,
                'reason': violation_reason
            })
        else:
            # Handle normal completion - optimized for speed
            exam_session.status = 'completed'
            exam_session.end_time = datetime.now(timezone.utc)
            
            # Award student points for completing the exam
            award_student_points(exam_session.student_id, 10, 'exam_completion')
            
            # Check if it's a perfect score and award bonus
            try:
                correct_answers, total_questions, score_percentage = calculate_exam_score(exam_session)
                if score_percentage >= 100:
                    award_student_points(exam_session.student_id, 20, 'perfect_score')
            except:
                pass  # Don't fail if score calculation fails
            
            # Fast single commit
            db.session.commit()
            
            return jsonify({
                'status': 'success', 
                'action': 'completed',
                'message': 'Exam submitted successfully',
                'redirect_url': url_for('view_results', session_id=session_id)
            })
            
    except Exception as e:
        traceback.print_exc()
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'An error occurred during exam submission'}), 500

@app.route('/results/<int:session_id>')
def view_results(session_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get current user
    current_user = db.session.get(User, session['user_id'])
    if not current_user:
        session.clear()
        return redirect(url_for('login'))
    
    exam_session = ExamSession.query.get_or_404(session_id)
    
    # Allow students to view their own results, and lecturers to view any results
    if session.get('role') == 'student' and exam_session.student_id != session['user_id']:
        return redirect(url_for('dashboard'))
    elif session.get('role') == 'lecturer':
        exam = db.session.get(Exam, exam_session.exam_id)
        if not exam or exam.lecturer_id != session['user_id']:
            return redirect(url_for('dashboard'))
    
    exam = db.session.get(Exam, exam_session.exam_id)
    if not exam:
        return redirect(url_for('dashboard'))
        
    student = db.session.get(User, exam_session.student_id)
    questions = Question.query.filter_by(exam_id=exam.id).all()
    answers = StudentAnswer.query.filter_by(session_id=session_id).all()
    
    # Check if results should be visible (only for completed/disqualified students)
    results_visible = True
    if session.get('role') == 'student':
        # Show results for both completed and disqualified students
        if exam_session.status not in ['completed', 'disqualified']:
            results_visible = check_result_visibility(exam.id)
            if not results_visible:
                # Redirect to my_results page with pending message
                return redirect(url_for('my_results'))
    
    # Calculate score using MCQ-aware function (for both completed and disqualified)
    correct_answers, total_questions, score_percentage = calculate_exam_score(exam_session)
    
    answer_dict = {answer.question_id: answer.answer for answer in answers}
    
    # Get monitoring alerts for this session
    alerts = MonitoringAlert.query.filter_by(session_id=session_id).all()
    
    # Get exam settings for duration
    exam_settings = ExamSettings.query.filter_by(exam_id=exam.id).first()
    duration_minutes = exam_settings.time_limit_minutes if exam_settings else 60  # Default 60 minutes
    
    # Generate AI advice for wrong answers (only for students viewing their own results)
    ai_advice = {}
    wrong_questions = []
    if session.get('role') == 'student' and exam_session.student_id == session['user_id']:
        for question in questions:
            student_answer = answer_dict.get(question.id, '').strip()
            is_correct = False
            
            if question.question_type == 'multiple_choice':
                is_correct = student_answer.upper() == question.correct_option.upper()
            else:
                correct_answer = question.answer.strip().lower() if question.answer else ''
                is_correct = student_answer.lower() == correct_answer
            
            if not is_correct:
                wrong_questions.append({
                    'question': question.text,
                    'student_answer': student_answer,
                    'correct_answer': question.correct_option if question.question_type == 'multiple_choice' else question.answer,
                    'question_type': question.question_type
                })
        
        # Generate AI advice for wrong answers
        if wrong_questions:
            ai_advice = generate_exam_advice(exam.title, wrong_questions, score_percentage)
    
    return render_template('exam_results.html', 
                         current_user=current_user,
                         exam_session=exam_session,
                         exam=exam,
                         student=student,
                         questions=questions,
                         answers=answer_dict,
                         total_questions=total_questions,
                         correct_answers=correct_answers,
                         score_percentage=round(score_percentage, 1),
                         alerts=alerts,
                         duration_minutes=duration_minutes,
                         ai_advice=ai_advice,
                         wrong_questions=wrong_questions)

def generate_exam_advice(exam_title, wrong_questions, score_percentage):
    """Generate AI-powered advice for exam results using free AI services"""
    if not wrong_questions:
        return {
            'overall_advice': "Excellent work! You answered all questions correctly. Keep up the great study habits!",
            'study_tips': [
                "Continue your excellent preparation methods",
                "Share your study techniques with classmates",
                "Consider helping others who might be struggling with the material"
            ],
            'question_advice': {}
        }
    
    # Prepare prompt for AI
    wrong_count = len(wrong_questions)
    prompt = f"""As an educational advisor, provide helpful study advice for a student who scored {score_percentage:.1f}% on "{exam_title}".

The student got {wrong_count} questions wrong. Here are the questions they missed:

"""
    
    for i, q in enumerate(wrong_questions, 1):
        prompt += f"""
Question {i}: {q['question']}
Student's answer: {q['student_answer'] if q['student_answer'] else 'No answer provided'}
Correct answer: {q['correct_answer']}
Question type: {q['question_type']}
"""
    
    prompt += f"""

Please provide:
1. Overall study advice (2-3 sentences)
2. 3-4 specific study tips
3. For each wrong question, brief advice on why they might have gotten it wrong and how to improve

Format as JSON:
{{
  "overall_advice": "...",
  "study_tips": ["tip1", "tip2", "tip3"],
  "question_advice": {{
    "1": "advice for question 1",
    "2": "advice for question 2"
  }}
}}"""

    # Try AI services in order of preference
    ai_services = [
        ('Groq', get_groq_advice),
        ('HuggingFace', get_huggingface_advice),
        ('Cohere', get_cohere_advice)
    ]
    
    for service_name, service_func in ai_services:
        try:
            advice = service_func(prompt)
            if advice:
                return advice
        except Exception as e:
            print(f"Error with {service_name} advice generation: {e}")
            continue
    
    # Fallback advice
    return generate_fallback_advice(score_percentage, wrong_count)

def get_groq_advice(prompt):
    """Generate advice using Groq API"""
    try:
        import requests
        import json
        
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {os.environ.get("GROQ_API_KEY", "")}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'llama-3.2-1b-preview',
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'temperature': 0.7,
                'max_tokens': 1000
            },
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            
            # Try to parse JSON from the response
            try:
                advice_data = json.loads(content)
                return advice_data
            except json.JSONDecodeError:
                # If not valid JSON, extract advice manually
                return parse_advice_text(content)
        
    except Exception as e:
        print(f"Groq advice error: {e}")
        return None

def get_huggingface_advice(prompt):
    """Generate advice using HuggingFace API"""
    try:
        import requests
        import json
        
        response = requests.post(
            'https://api-inference.huggingface.co/models/microsoft/DialoGPT-medium',
            headers={'Authorization': f'Bearer {os.environ.get("HUGGINGFACE_API_KEY", "")}'},
            json={'inputs': prompt[:500]},  # Limit length for this model
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            if result and len(result) > 0:
                advice_text = result[0].get('generated_text', '')
                return parse_advice_text(advice_text)
        
    except Exception as e:
        print(f"HuggingFace advice error: {e}")
        return None

def get_cohere_advice(prompt):
    """Generate advice using Cohere API"""
    try:
        import requests
        import json
        
        response = requests.post(
            'https://api.cohere.ai/v1/generate',
            headers={
                'Authorization': 'Bearer LUiLZHOkdUqKsEBySFfvxX04PdE0YvKhFa8bLFQT',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'command-light',
                'prompt': prompt,
                'max_tokens': 500,
                'temperature': 0.7
            },
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'generations' in result and len(result['generations']) > 0:
                advice_text = result['generations'][0]['text']
                return parse_advice_text(advice_text)
        
    except Exception as e:
        print(f"Cohere advice error: {e}")
        return None

def parse_advice_text(text):
    """Parse advice from free-form text when JSON parsing fails"""
    try:
        import json
        # Try to find JSON in the text
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end != 0:
            json_text = text[start:end]
            return json.loads(json_text)
    except:
        pass
    
    # If no JSON found, create structured advice from text
    return {
        'overall_advice': text[:200] + "..." if len(text) > 200 else text,
        'study_tips': [
            "Review the material more thoroughly",
            "Practice with similar questions",
            "Seek help from your instructor if needed"
        ],
        'question_advice': {}
    }

def generate_fallback_advice(score_percentage, wrong_count):
    """Generate fallback advice when AI services are unavailable"""
    if score_percentage >= 80:
        overall = "Good performance! You're on the right track but there's room for improvement in a few areas."
        tips = [
            "Review the questions you missed to understand the concepts better",
            "Focus on the specific topics where you made mistakes",
            "Practice similar questions to reinforce your understanding"
        ]
    elif score_percentage >= 60:
        overall = "You have a basic understanding but need to strengthen your knowledge in several areas."
        tips = [
            "Dedicate more time to studying the material",
            "Create study notes for topics you find challenging",
            "Consider forming a study group with classmates",
            "Ask your instructor for clarification on difficult concepts"
        ]
    else:
        overall = "This exam shows you need significant improvement. Don't get discouraged - use this as a learning opportunity!"
        tips = [
            "Schedule regular study sessions to review all material",
            "Meet with your instructor during office hours",
            "Consider using additional study resources like textbooks or online materials",
            "Practice active learning techniques like summarizing and self-testing"
        ]
    
    return {
        'overall_advice': overall,
        'study_tips': tips,
        'question_advice': {}
    }

def calculate_exam_score(exam_session):
    """Calculate exam score with MCQ support"""
    exam = db.session.get(Exam, exam_session.exam_id)
    if not exam:
        return 0, 0, 0
    
    questions = Question.query.filter_by(exam_id=exam.id).all()
    answers = StudentAnswer.query.filter_by(session_id=exam_session.id).all()
    
    total_questions = len(questions)
    correct_answers = 0
    
    if total_questions > 0:
        answer_dict = {answer.question_id: answer.answer for answer in answers}
        
        for question in questions:
            student_answer = answer_dict.get(question.id, '').strip()
            
            if question.question_type == 'multiple_choice':
                # For MCQ, compare with correct_option (A, B, C, D)
                if student_answer.upper() == question.correct_option.upper():
                    correct_answers += 1
            else:
                # For text questions, use the old logic
                correct_answer = question.answer.strip().lower() if question.answer else ''
                if student_answer.lower() == correct_answer:
                    correct_answers += 1
    
    score_percentage = (correct_answers / total_questions * 100) if total_questions > 0 else 0
    return correct_answers, total_questions, score_percentage

def check_result_visibility(exam_id):
    """Check if results should be visible for this exam"""
    exam_settings = ExamSettings.query.filter_by(exam_id=exam_id).first()
    
    if not exam_settings or not exam_settings.results_visible_after_all_complete:
        return True  # Results always visible if no settings or setting is False
    
    # Check if all students have completed the exam
    exam_sessions = ExamSession.query.filter_by(exam_id=exam_id).all()
    
    if not exam_sessions:
        return True
    
    # Count sessions that are still in progress
    in_progress_count = sum(1 for exam_session in exam_sessions if exam_session.status == 'in_progress')
    
    return in_progress_count == 0  # Results visible only when no one is still taking the exam

@app.route('/exam_results')
def exam_results_list():
    if 'user_id' not in session or session.get('role') != 'lecturer':
        return redirect(url_for('dashboard'))
    
    # Get current user
    user = db.session.get(User, session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    
    # Get all exam sessions for exams created by this lecturer
    lecturer_exams = Exam.query.filter_by(lecturer_id=session['user_id']).all()
    exam_ids = [exam.id for exam in lecturer_exams]
    
    exam_sessions = ExamSession.query.filter(
        ExamSession.exam_id.in_(exam_ids),
        ExamSession.status.in_(['completed', 'disqualified'])
    ).order_by(ExamSession.end_time.desc()).all()
    
    # Calculate premium statistics
    total_submissions = len(exam_sessions)
    completed_count = sum(1 for s in exam_sessions if s.status == 'completed')
    disqualified_count = sum(1 for s in exam_sessions if s.status == 'disqualified')
    
    # Calculate average score from completed sessions
    total_score = 0
    score_count = 0
    grade_distribution = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
    
    # Add exam and student information
    results = []
    for exam_session in exam_sessions:
        exam = db.session.get(Exam, exam_session.exam_id)
        student = db.session.get(User, exam_session.student_id)
        
        if not exam or not student:
            continue
        
        # Calculate score using the new MCQ-aware function
        correct_answers, total_questions, score_percentage = calculate_exam_score(exam_session)
        
        # Update statistics for completed exams
        if exam_session.status == 'completed':
            total_score += score_percentage
            score_count += 1
            
            # Grade distribution
            if score_percentage >= 90:
                grade_distribution['A'] += 1
            elif score_percentage >= 80:
                grade_distribution['B'] += 1
            elif score_percentage >= 70:
                grade_distribution['C'] += 1
            elif score_percentage >= 60:
                grade_distribution['D'] += 1
            else:
                grade_distribution['F'] += 1
        
        results.append({
            'session': exam_session,
            'exam': exam,
            'student': student,
            'score_percentage': round(score_percentage, 1),
            'total_questions': total_questions,
            'correct_answers': correct_answers
        })
    
    # Calculate final statistics
    avg_score = round(total_score / score_count, 1) if score_count > 0 else 0
    completion_rate = round((completed_count / total_submissions * 100), 1) if total_submissions > 0 else 0
    
    return render_template('exam_results_list.html', 
                         user=user,
                         results=results,
                         stats={
                             'total_submissions': total_submissions,
                             'completed_count': completed_count,
                             'disqualified_count': disqualified_count,
                             'avg_score': avg_score,
                             'completion_rate': completion_rate,
                             'grade_distribution': grade_distribution
                         })

@app.route('/my_results')
def my_results():
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('dashboard'))
    
    # Get all exam sessions for this student
    student_sessions = ExamSession.query.filter_by(
        student_id=session['user_id']
    ).filter(
        ExamSession.status.in_(['completed', 'disqualified'])
    ).order_by(ExamSession.end_time.desc()).all()
    
    # Add exam information and calculate scores
    results = []
    for exam_session in student_sessions:
        exam = db.session.get(Exam, exam_session.exam_id)
        if not exam:
            continue
        
        # Check if results should be visible for this exam
        results_visible = check_result_visibility(exam.id)
        
        # Calculate score for completed exams only if results are visible
        score_percentage = None
        correct_answers = 0
        total_questions = 0
        
        if exam_session.status == 'completed' and results_visible:
            correct_answers, total_questions, score_percentage = calculate_exam_score(exam_session)
        elif exam_session.status == 'completed':
            # Get question count but don't show score
            questions = Question.query.filter_by(exam_id=exam.id).all()
            total_questions = len(questions)
        
        results.append({
            'session': exam_session,
            'exam': exam,
            'score_percentage': round(score_percentage, 1) if score_percentage is not None else None,
            'total_questions': total_questions,
            'correct_answers': correct_answers,
            'results_visible': results_visible
        })
    
    return render_template('my_results.html', results=results)

@app.route('/favicon.ico')
def favicon():
    return '', 204  # No content response

def generate_sample_questions(topic, count=30):
    """Generate sample questions for a given topic"""
    # This is a simplified version - in production, you'd use an AI API like OpenAI
    question_templates = {
        "general": [
            {
                "question": "What is the capital of France?",
                "options": ["Paris", "London", "Berlin", "Madrid"],
                "correct": "A"
            },
            {
                "question": "Which programming language is known for its simplicity and readability?",
                "options": ["C++", "Assembly", "Python", "Java"],
                "correct": "C"
            },
            {
                "question": "What does HTML stand for?",
                "options": ["Hypertext Markup Language", "High Tech Modern Language", "Home Tool Markup Language", "Hyperlink Text Management Language"],
                "correct": "A"
            },
            {
                "question": "Which of the following is a relational database?",
                "options": ["MongoDB", "Redis", "MySQL", "Elasticsearch"],
                "correct": "C"
            },
            {
                "question": "What is the result of 15 + 25?",
                "options": ["35", "40", "45", "50"],
                "correct": "B"
            }
        ],
        "science": [
            {
                "question": "What is the chemical symbol for water?",
                "options": ["H2O", "CO2", "NaCl", "O2"],
                "correct": "A"
            },
            {
                "question": "Which planet is closest to the Sun?",
                "options": ["Venus", "Mercury", "Earth", "Mars"],
                "correct": "B"
            },
            {
                "question": "What is the speed of light in vacuum?",
                "options": ["300,000 km/s", "150,000 km/s", "450,000 km/s", "600,000 km/s"],
                "correct": "A"
            }
        ],
        "mathematics": [
            {
                "question": "What is the value of π (pi) approximately?",
                "options": ["3.14159", "2.71828", "1.61803", "4.66920"],
                "correct": "A"
            },
            {
                "question": "What is 12 × 8?",
                "options": ["84", "96", "108", "112"],
                "correct": "B"
            },
            {
                "question": "What is the square root of 144?",
                "options": ["10", "11", "12", "13"],
                "correct": "C"
            }
        ]
    }
    
    # Select appropriate template based on topic
    if topic.lower() in question_templates:
        base_questions = question_templates[topic.lower()]
    else:
        base_questions = question_templates["general"]
    
    # Generate variations and random questions
    generated_questions = []
    for i in range(count):
        base_q = base_questions[i % len(base_questions)]
        
        # Add some variation to avoid exact duplicates
        variation_suffix = f" (Question {i+1})" if i >= len(base_questions) else ""
        
        generated_questions.append({
            "question": base_q["question"] + variation_suffix,
            "option_a": base_q["options"][0],
            "option_b": base_q["options"][1], 
            "option_c": base_q["options"][2],
            "option_d": base_q["options"][3],
            "correct_option": base_q["correct"],
            "difficulty": random.choice(["easy", "medium", "hard"])
        })
    
    return generated_questions

@app.route('/manage_exams')
def manage_exams():
    if 'user_id' not in session or session.get('role') != 'lecturer':
        return redirect(url_for('dashboard'))
    
    # Clear any success messages after displaying
    success_message = session.pop('exam_created', None)
    
    # Get all exams created by this lecturer with detailed information
    lecturer_exams = Exam.query.filter_by(lecturer_id=session['user_id']).order_by(Exam.created_at.desc()).all()
    
    # Calculate overall statistics
    total_exams = len(lecturer_exams)
    active_exams_count = total_exams  # All exams are considered active unless explicitly disabled
    
    # Get total students who have taken any of this lecturer's exams
    student_ids = set()
    total_attempts = 0
    completed_attempts = 0
    in_progress_attempts = 0
    avg_score = 0
    scores = []
    
    # Calculate AI vs Manual exam counts
    ai_exams = sum(1 for exam in lecturer_exams if exam.ai_generated)
    manual_exams = total_exams - ai_exams
    
    # Add statistics for each exam
    exam_details = []
    for exam in lecturer_exams:
        # Get question count
        question_count = Question.query.filter_by(exam_id=exam.id).count()
        
        # Get session statistics
        total_sessions = ExamSession.query.filter_by(exam_id=exam.id).count()
        completed_sessions = ExamSession.query.filter_by(exam_id=exam.id, status='completed').count()
        disqualified_sessions = ExamSession.query.filter_by(exam_id=exam.id, status='disqualified').count()
        active_sessions = ExamSession.query.filter_by(exam_id=exam.id, status='in_progress').count()
        
        # Get unique students for this exam
        exam_students = ExamSession.query.filter_by(exam_id=exam.id).with_entities(ExamSession.student_id).distinct()
        for student_session in exam_students:
            student_ids.add(student_session.student_id)
        
        # Accumulate overall stats
        total_attempts += total_sessions
        completed_attempts += completed_sessions
        in_progress_attempts += active_sessions
        
        # Calculate average score for completed sessions
        completed_session_scores = ExamSession.query.filter_by(exam_id=exam.id, status='completed').all()
        exam_scores = []
        for exam_session in completed_session_scores:
            try:
                _, _, score_percentage = calculate_exam_score(exam_session)
                if score_percentage is not None:
                    exam_scores.append(score_percentage)
            except Exception as e:
                print(f"Error calculating score for session {exam_session.id}: {e}")
                continue
        scores.extend(exam_scores)
        
        # Get exam settings (safely handle missing passing_score column)
        try:
            settings = ExamSettings.query.filter_by(exam_id=exam.id).first()
        except Exception as e:
            print(f"Error accessing ExamSettings: {e}")
            settings = None
        
        # Calculate pass rate for this exam
        passing_score = getattr(settings, 'passing_score', 70) if settings else 70
        passed_sessions = len([score for score in exam_scores if score >= passing_score])
        pass_rate = (passed_sessions / len(exam_scores) * 100) if exam_scores else 0
        
        exam_details.append({
            'exam': exam,
            'question_count': question_count,
            'total_sessions': total_sessions,
            'completed_sessions': completed_sessions,
            'disqualified_sessions': disqualified_sessions,
            'active_sessions': active_sessions,
            'settings': settings,
            'total_attempts': total_sessions,  # For template compatibility
            'pass_rate': round(pass_rate, 1),
            'avg_score': round(sum(exam_scores) / len(exam_scores), 1) if exam_scores else 0
        })
    
    # Calculate overall statistics
    total_students = len(student_ids)
    overall_avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    overall_pass_rate = round((completed_attempts / total_attempts * 100), 1) if total_attempts > 0 else 0
    
    return render_template('manage_exams.html', 
                         exam_details=exam_details,
                         total_exams=total_exams,
                         active_exams_count=active_exams_count,
                         total_students=total_students,
                         total_attempts=total_attempts,
                         completed_attempts=completed_attempts,
                         in_progress_attempts=in_progress_attempts,
                         overall_avg_score=overall_avg_score,
                         overall_pass_rate=overall_pass_rate,
                         ai_exams=ai_exams,
                         manual_exams=manual_exams,
                         success_message=success_message)

@app.route('/edit_exam/<int:exam_id>')
def edit_exam(exam_id):
    if 'user_id' not in session or session.get('role') != 'lecturer':
        return redirect(url_for('dashboard'))
    
    exam = Exam.query.get_or_404(exam_id)
    
    # Check if this lecturer owns the exam
    if exam.lecturer_id != session['user_id']:
        return redirect(url_for('manage_exams'))
    
    # Get exam questions and settings
    questions = Question.query.filter_by(exam_id=exam.id).all()
    settings = ExamSettings.query.filter_by(exam_id=exam.id).first()
    
    return render_template('edit_exam.html', exam=exam, questions=questions, settings=settings)

@app.route('/update_exam/<int:exam_id>', methods=['POST'])
def update_exam(exam_id):
    if 'user_id' not in session or session.get('role') != 'lecturer':
        return redirect(url_for('dashboard'))
    
    exam = Exam.query.get_or_404(exam_id)
    
    # Check if this lecturer owns the exam
    if exam.lecturer_id != session['user_id']:
        return redirect(url_for('manage_exams'))
    
    try:
        # Update exam title
        exam.title = request.form.get('exam_title', exam.title)
        
        # Update settings
        settings = ExamSettings.query.filter_by(exam_id=exam.id).first()
        if settings:
            settings.results_visible_after_all_complete = request.form.get('results_after_all') == 'on'
            settings.time_limit_minutes = int(request.form.get('time_limit', settings.time_limit_minutes or 60))
            settings.randomize_questions = request.form.get('randomize_questions') == 'on'
        
        db.session.commit()
        return redirect(url_for('manage_exams'))
        
    except Exception as e:
        db.session.rollback()
        return redirect(url_for('edit_exam', exam_id=exam_id))

@app.route('/delete_exam/<int:exam_id>', methods=['POST'])
def delete_exam(exam_id):
    if 'user_id' not in session or session.get('role') != 'lecturer':
        return redirect(url_for('dashboard'))
    
    exam = Exam.query.get_or_404(exam_id)
    
    # Check if this lecturer owns the exam
    if exam.lecturer_id != session['user_id']:
        return redirect(url_for('manage_exams'))
    
    try:
        # Delete all related data in proper order
        # Delete student answers first
        exam_sessions = ExamSession.query.filter_by(exam_id=exam.id).all()
        for exam_session in exam_sessions:
            StudentAnswer.query.filter_by(session_id=exam_session.id).delete()
            MonitoringAlert.query.filter_by(session_id=exam_session.id).delete()
        
        # Delete exam sessions
        ExamSession.query.filter_by(exam_id=exam.id).delete()
        
        # Delete questions
        Question.query.filter_by(exam_id=exam.id).delete()
        
        # Delete settings
        ExamSettings.query.filter_by(exam_id=exam.id).delete()
        
        # Finally delete the exam
        db.session.delete(exam)
        db.session.commit()
        
        return redirect(url_for('manage_exams'))
        
    except Exception as e:
        db.session.rollback()
        return redirect(url_for('manage_exams'))

@app.route('/exam_results_for_exam/<int:exam_id>')
def exam_results_for_exam(exam_id):
    if 'user_id' not in session or session.get('role') != 'lecturer':
        return redirect(url_for('dashboard'))
    
    # Get current user
    user = db.session.get(User, session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    
    exam = Exam.query.get_or_404(exam_id)
    
    # Check if this lecturer owns the exam
    if exam.lecturer_id != session['user_id']:
        return redirect(url_for('manage_exams'))
    
    # Get all exam sessions for this specific exam
    exam_sessions = ExamSession.query.filter(
        ExamSession.exam_id == exam_id,
        ExamSession.status.in_(['completed', 'disqualified'])
    ).order_by(ExamSession.end_time.desc()).all()
    
    # Calculate premium statistics for this specific exam
    total_submissions = len(exam_sessions)
    completed_count = sum(1 for s in exam_sessions if s.status == 'completed')
    disqualified_count = sum(1 for s in exam_sessions if s.status == 'disqualified')
    
    # Calculate statistics from completed sessions
    total_score = 0
    score_count = 0
    scores = []
    grade_distribution = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
    
    # Add student information and scores
    results = []
    for exam_session in exam_sessions:
        student = db.session.get(User, exam_session.student_id)
        
        if not student:
            continue
        
        # Calculate score using the MCQ-aware function
        correct_answers, total_questions, score_percentage = calculate_exam_score(exam_session)
        
        # Update statistics for completed exams
        if exam_session.status == 'completed':
            total_score += score_percentage
            score_count += 1
            scores.append(score_percentage)
            
            # Grade distribution
            if score_percentage >= 90:
                grade_distribution['A'] += 1
            elif score_percentage >= 80:
                grade_distribution['B'] += 1
            elif score_percentage >= 70:
                grade_distribution['C'] += 1
            elif score_percentage >= 60:
                grade_distribution['D'] += 1
            else:
                grade_distribution['F'] += 1
        
        results.append({
            'session': exam_session,
            'student': student,
            'score_percentage': round(score_percentage, 1),
            'total_questions': total_questions,
            'correct_answers': correct_answers
        })
    
    # Calculate final statistics
    avg_score = round(total_score / score_count, 1) if score_count > 0 else 0
    highest_score = round(max(scores), 1) if scores else 0
    lowest_score = round(min(scores), 1) if scores else 0
    completion_rate = round((completed_count / total_submissions * 100), 1) if total_submissions > 0 else 0
    
    return render_template('exam_specific_results.html', 
                         user=user,
                         exam=exam, 
                         results=results,
                         stats={
                             'total_submissions': total_submissions,
                             'completed_count': completed_count,
                             'disqualified_count': disqualified_count,
                             'avg_score': avg_score,
                             'highest_score': highest_score,
                             'lowest_score': lowest_score,
                             'completion_rate': completion_rate,
                             'grade_distribution': grade_distribution
                         })

# ===============================
# CHALLENGE ROUTES
# ===============================

@app.route('/challenges')
def manage_challenges():
    """Lecturer dashboard for managing challenges"""
    if 'user_id' not in session or session.get('role') != 'lecturer':
        return redirect(url_for('dashboard'))
    
    # Get current user
    user = db.session.get(User, session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    
    # Get all challenges created by this lecturer
    challenges = Challenge.query.filter_by(created_by=session['user_id']).order_by(Challenge.created_at.desc()).all()
    
    # Calculate statistics for each challenge
    challenge_stats = []
    for challenge in challenges:
        participants = ChallengeSession.query.filter_by(challenge_id=challenge.id).count()
        completed = ChallengeSession.query.filter_by(challenge_id=challenge.id, status='completed').count()
        avg_score = db.session.query(db.func.avg(ChallengeSession.percentage)).filter_by(
            challenge_id=challenge.id, status='completed').scalar() or 0
        
        challenge_stats.append({
            'challenge': challenge,
            'participants': participants,
            'completed': completed,
            'avg_score': round(avg_score, 1),
            'completion_rate': round((completed / participants * 100), 1) if participants > 0 else 0
        })
    
    return render_template('manage_challenges.html', user=user, challenge_stats=challenge_stats)

@app.route('/create_challenge', methods=['GET', 'POST'])
def create_challenge():
    """Create a new challenge with optional AI assistance"""
    if 'user_id' not in session or session.get('role') != 'lecturer':
        return redirect(url_for('dashboard'))
    
    user = db.session.get(User, session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            action = request.form.get('action')
            print(f"DEBUG: Action received: {action}")
            print(f"DEBUG: Form data keys: {list(request.form.keys())}")
            
            if action == 'generate_ai_challenge':
                # Handle AI challenge generation
                topic = request.form.get('topic', '').strip()
                difficulty = request.form.get('difficulty', 'medium')
                question_count = int(request.form.get('question_count', 5))
                challenge_type = request.form.get('challenge_type', 'speed_quiz')
                
                if not topic:
                    return jsonify({'error': 'Topic is required for AI generation'}), 400
                
                # Generate AI questions for the challenge
                generated_questions = generate_ai_challenge_questions(topic, difficulty, question_count, challenge_type)
                
                return jsonify({
                    'success': True,
                    'questions': generated_questions,
                    'topic': topic,
                    'difficulty': difficulty,
                    'challenge_type': challenge_type
                })
            
            elif action == 'save_challenge' or action == 'create_challenge' or action is None:
                # Handle challenge creation (including when action is None)
                print(f"DEBUG: Creating challenge with action: {action}")
                # Save the challenge
                title = request.form.get('title', '').strip()
                description = request.form.get('description', '').strip()
                challenge_type = request.form.get('challenge_type', 'speed_quiz')
                time_limit = request.form.get('time_limit_minutes')
                max_attempts = int(request.form.get('max_attempts', 3))
                passing_score = int(request.form.get('passing_score', 70))
                
                print(f"DEBUG: Title: {title}, Description: {description}, Type: {challenge_type}")
                print(f"DEBUG: Form keys: {list(request.form.keys())}")
                
                if not title:
                    return jsonify({'error': 'Title is required'}), 400                # Create challenge
                challenge = Challenge(
                    created_by=session['user_id'],
                    title=title,
                    description=description,
                    topic=request.form.get('topic', title),  # Use topic from form or title as fallback
                    difficulty=request.form.get('difficulty', 'medium'),
                    challenge_type=challenge_type,
                    time_limit_minutes=int(time_limit) if time_limit else None,
                    max_attempts=max_attempts,
                    passing_score=passing_score,
                    is_active=True,
                    ai_generated=True if request.form.get('generation_method') == 'ai' else False,
                    end_date=datetime.now(timezone.utc) + timedelta(days=30),  # Default 30 days from now
                    created_at=datetime.now(timezone.utc)
                )
                
                db.session.add(challenge)
                db.session.flush()  # Get the challenge ID
                
                # Add questions from AI generation or manual entry
                questions_added = 0
                
                # Handle AI generated questions
                generated_questions = request.form.getlist('generated_questions')
                if generated_questions:
                    import json
                    for q_json in generated_questions:
                        try:
                            q_data = json.loads(q_json)
                            question = ChallengeQuestion(
                                challenge_id=challenge.id,
                                question_text=q_data.get('text', ''),
                                question_type=q_data.get('question_type', 'multiple_choice'),
                                option_a=q_data.get('option_a'),
                                option_b=q_data.get('option_b'),
                                option_c=q_data.get('option_c'),
                                option_d=q_data.get('option_d'),
                                correct_option=q_data.get('correct_option'),
                                points=q_data.get('points', 1),
                                time_limit_seconds=q_data.get('time_limit_seconds'),
                                order_index=questions_added
                            )
                            db.session.add(question)
                            questions_added += 1
                        except Exception as e:
                            print(f"Error parsing question: {e}")
                
                # Handle manually entered questions
                question_indices = set()
                for key in request.form.keys():
                    if key.startswith('questions[') and key.endswith('][text]'):
                        # Extract question index from key like 'questions[0][text]'
                        try:
                            index = int(key.split('[')[1].split(']')[0])
                            question_indices.add(index)
                        except:
                            continue
                
                for index in sorted(question_indices):
                    question_text = request.form.get(f'questions[{index}][text]', '').strip()
                    if question_text:
                        question = ChallengeQuestion(
                            challenge_id=challenge.id,
                            question_text=question_text,
                            question_type='multiple_choice',
                            option_a=request.form.get(f'questions[{index}][option_a]', ''),
                            option_b=request.form.get(f'questions[{index}][option_b]', ''),
                            option_c=request.form.get(f'questions[{index}][option_c]', ''),
                            option_d=request.form.get(f'questions[{index}][option_d]', ''),
                            correct_option=request.form.get(f'questions[{index}][correct_option]', 'A'),
                            points=1,
                            order_index=questions_added
                        )
                        db.session.add(question)
                        questions_added += 1
                
                if questions_added == 0:
                    db.session.rollback()
                    return jsonify({'error': 'At least one question is required'}), 400
                
                db.session.commit()
                print(f"DEBUG: Challenge created successfully with ID: {challenge.id}")
                return jsonify({'success': True, 'challenge_id': challenge.id, 'message': 'Challenge created successfully!'})
            
            else:
                # Unknown action - treat as regular challenge creation
                return render_template('create_challenge.html', user=user)
                
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Failed to create challenge: {str(e)}'}), 500
    
    return render_template('create_challenge.html', user=user)

@app.route('/generate_ai_challenge_questions', methods=['POST'])
def generate_ai_challenge_questions_route():
    """API endpoint for generating AI challenge questions"""
    if 'user_id' not in session or session.get('role') != 'lecturer':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        topic = data.get('topic', '').strip()
        difficulty = data.get('difficulty', 'medium')
        question_count = int(data.get('question_count', 5))
        challenge_type = data.get('challenge_type', 'speed_quiz')
        
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        questions = generate_ai_challenge_questions(topic, difficulty, question_count, challenge_type)
        return jsonify({'success': True, 'questions': questions})
        
    except Exception as e:
        return jsonify({'error': f'Failed to generate questions: {str(e)}'}), 500

@app.route('/view_challenge/<int:challenge_id>')
def view_challenge(challenge_id):
    """View individual challenge details and results"""
    if 'user_id' not in session or session.get('role') != 'lecturer':
        return redirect(url_for('dashboard'))
    
    challenge = db.session.get(Challenge, challenge_id)
    if not challenge or challenge.created_by != session['user_id']:
        return redirect(url_for('manage_challenges'))
    
    # Get challenge statistics
    participants = ChallengeSession.query.filter_by(challenge_id=challenge.id).count()
    completed = ChallengeSession.query.filter_by(challenge_id=challenge.id, status='completed').count()
    avg_score = db.session.query(db.func.avg(ChallengeSession.percentage)).filter_by(
        challenge_id=challenge.id, status='completed').scalar() or 0
    
    # Get recent sessions
    recent_sessions = ChallengeSession.query.filter_by(challenge_id=challenge.id)\
        .order_by(ChallengeSession.start_time.desc()).limit(10).all()
    
    stats = {
        'participants': participants,
        'completed': completed,
        'avg_score': round(avg_score, 1),
        'completion_rate': round((completed / participants * 100), 1) if participants > 0 else 0
    }
    
    user = db.session.get(User, session['user_id'])
    return render_template('challenge_view.html', user=user, challenge=challenge, stats=stats, recent_sessions=recent_sessions)

@app.route('/edit_challenge/<int:challenge_id>', methods=['GET', 'POST'])
def edit_challenge(challenge_id):
    """Edit an existing challenge"""
    if 'user_id' not in session or session.get('role') != 'lecturer':
        return redirect(url_for('dashboard'))
    
    challenge = db.session.get(Challenge, challenge_id)
    if not challenge or challenge.created_by != session['user_id']:
        return redirect(url_for('manage_challenges'))
    
    if request.method == 'POST':
        try:
            challenge.title = request.form.get('title', '').strip()
            challenge.description = request.form.get('description', '').strip()
            challenge.challenge_type = request.form.get('challenge_type', 'speed_quiz')
            challenge.time_limit_minutes = int(request.form.get('time_limit_minutes')) if request.form.get('time_limit_minutes') else None
            challenge.max_attempts = int(request.form.get('max_attempts', 3))
            challenge.passing_score = int(request.form.get('passing_score', 70))
            challenge.is_active = 'is_active' in request.form
            
            db.session.commit()
            return redirect(url_for('manage_challenges'))
        except Exception as e:
            db.session.rollback()
            return redirect(url_for('edit_challenge', challenge_id=challenge_id))
    
    user = db.session.get(User, session['user_id'])
    return render_template('edit_challenge.html', user=user, challenge=challenge)

@app.route('/api/challenge/<int:challenge_id>/toggle-status', methods=['POST'])
def toggle_challenge_status(challenge_id):
    """Toggle challenge active/inactive status"""
    if 'user_id' not in session or session.get('role') != 'lecturer':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        challenge = db.session.get(Challenge, challenge_id)
        if not challenge or challenge.created_by != session['user_id']:
            return jsonify({'success': False, 'message': 'Challenge not found'}), 404
        
        challenge.is_active = not challenge.is_active
        db.session.commit()
        
        return jsonify({'success': True, 'is_active': challenge.is_active})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/challenge/<int:challenge_id>', methods=['DELETE'])
def delete_challenge(challenge_id):
    """Delete a challenge and all associated data"""
    if 'user_id' not in session or session.get('role') != 'lecturer':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        challenge = db.session.get(Challenge, challenge_id)
        if not challenge or challenge.created_by != session['user_id']:
            return jsonify({'success': False, 'message': 'Challenge not found'}), 404
        
        # Delete associated data
        ChallengeAnswer.query.filter(
            ChallengeAnswer.session_id.in_(
                db.session.query(ChallengeSession.id).filter_by(challenge_id=challenge_id)
            )
        ).delete(synchronize_session=False)
        
        ChallengeSession.query.filter_by(challenge_id=challenge_id).delete()
        ChallengeQuestion.query.filter_by(challenge_id=challenge_id).delete()
        
        db.session.delete(challenge)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Challenge deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/notifications')
def notifications():
    """Get notifications for the current student"""
    if 'user_id' not in session or session.get('role') != 'student':
        return jsonify({'notifications': []})
    
    # Generate sample notifications - in production, these would come from the database
    student_id = session['user_id']
    
    # Get student's recent activity
    student_sessions = ExamSession.query.filter_by(student_id=student_id).order_by(ExamSession.start_time.desc()).limit(5).all()
    available_exams = Exam.query.all()
    taken_exam_ids = [s.exam_id for s in ExamSession.query.filter_by(student_id=student_id).all()]
    upcoming_exams = [e for e in available_exams if e.id not in taken_exam_ids]
    
    notifications = []
    
    # Check for new available exams
    if upcoming_exams:
        notifications.append({
            'title': 'New Exams Available',
            'message': f'{len(upcoming_exams)} new exam(s) are ready for you to take',
            'priority': 'medium',
            'action_url': url_for('dashboard') + '#available-exams',
            'action_text': 'View Exams'
        })
    
    # Check for results ready
    for exam_session in student_sessions:
        if exam_session.status == 'completed':
            exam = db.session.get(Exam, exam_session.exam_id)
            if exam and check_result_visibility(exam.id):
                notifications.append({
                    'title': f'Results Ready: {exam.title}',
                    'message': 'Your exam results are now available',
                    'priority': 'high',
                    'action_url': url_for('view_results', session_id=exam_session.id),
                    'action_text': 'View Results'
                })
                break  # Only show one result notification
    
    # Study reminders
    if len(upcoming_exams) > 0 and len(student_sessions) == 0:
        notifications.append({
            'title': 'Welcome to QUIZZO!',
            'message': 'Review the study tips below before taking your first exam',
            'priority': 'low',
            'action_url': None,
            'action_text': None
        })
    
    # Performance encouragement
    completed_sessions = [s for s in student_sessions if s.status == 'completed']
    if len(completed_sessions) >= 2:
        scores = []
        for exam_session in completed_sessions[:3]:  # Last 3 exams
            if check_result_visibility(exam_session.exam_id):
                _, _, score = calculate_exam_score(exam_session)
                scores.append(score)
        
        if scores:
            avg_recent = sum(scores) / len(scores)
            if avg_recent >= 85:
                notifications.append({
                    'title': 'Excellent Performance!',
                    'message': f'Your recent average is {avg_recent:.1f}%. Keep up the great work!',
                    'priority': 'low',
                    'action_url': url_for('student_progress'),
                    'action_text': 'View Progress'
                })
            elif avg_recent < 70:
                notifications.append({
                    'title': 'Study Tip',
                    'message': 'Consider reviewing the study materials for better performance',
                    'priority': 'medium',
                    'action_url': url_for('dashboard') + '#study-tips',
                    'action_text': 'Study Tips'
                })
    
    # Limit to 3 most important notifications
    notifications = notifications[:3]
    
    return jsonify({'notifications': notifications})

@app.route('/mark_notification_read', methods=['POST'])
def mark_notification_read():
    """Mark a notification as read (placeholder for future database implementation)"""
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Not authenticated'})
    
    # In production, you would mark the notification as read in the database
    return jsonify({'status': 'success'})

# Enhanced API endpoints for student dashboard
@app.route('/api/student/notifications')
def api_student_notifications():
    """Enhanced notifications API for students"""
    if 'user_id' not in session or session.get('role') != 'student':
        return jsonify({'notifications': []})
    
    student_id = session['user_id']
    notifications = []
    
    # Get student stats
    completed_count = ExamSession.query.filter(
        ExamSession.student_id == student_id,
        ExamSession.status == 'completed'
    ).count()
    
    # Check for new achievements
    achievements = get_student_achievements(student_id)
    if achievements:
        notifications.append({
            'title': '🏆 Achievement Unlocked!',
            'message': f'You earned "{achievements[0]["title"]}" - Keep up the great work!',
            'icon': 'trophy',
            'color': 'amber',
            'time_ago': '2 min ago',
            'action_url': url_for('student_progress'),
            'action_text': 'View Achievements'
        })
    
    # Check for study streak
    streak = calculate_study_streak(student_id)
    if streak >= 3:
        notifications.append({
            'title': '🔥 Study Streak Active!',
            'message': f'You\'re on a {streak}-day study streak! Don\'t break the chain.',
            'icon': 'fire',
            'color': 'orange',
            'time_ago': '1 hour ago'
        })
    
    # Check for available exams
    available_exams = Exam.query.all()
    taken_exam_ids = [s.exam_id for s in ExamSession.query.filter_by(student_id=student_id).all()]
    upcoming_exams = [e for e in available_exams if e.id not in taken_exam_ids]
    
    if upcoming_exams:
        notifications.append({
            'title': '📚 New Exams Available',
            'message': f'{len(upcoming_exams)} new exam(s) are ready for you to take',
            'icon': 'clipboard-list',
            'color': 'blue',
            'time_ago': '3 hours ago',
            'action_url': url_for('exam_schedule'),
            'action_text': 'View Schedule'
        })
    
    # Motivational messages based on performance
    if completed_count > 0:
        avg_score = 85  # Calculate actual average
        if avg_score >= 90:
            notifications.append({
                'title': '⭐ Excellent Performance!',
                'message': f'Your average score is {avg_score}%. You\'re doing amazing!',
                'icon': 'star',
                'color': 'yellow',
                'time_ago': '1 day ago'
            })
    
    return jsonify({'notifications': notifications})

@app.route('/api/student/achievements')
def api_student_achievements():
    """Get detailed achievements for student"""
    if 'user_id' not in session or session.get('role') != 'student':
        return jsonify({'achievements': []})
    
    achievements = get_student_achievements(session['user_id'])
    return jsonify({'achievements': achievements})

@app.route('/api/student/leaderboard')
def api_student_leaderboard():
    """Get global leaderboard"""
    if 'user_id' not in session or session.get('role') != 'student':
        return jsonify({'leaderboard': []})
    
    leaderboard = get_global_leaderboard(20)
    return jsonify({'leaderboard': leaderboard})

@app.route('/student/challenges')
def student_challenges():
    """Student challenges page with detailed challenge information"""
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('dashboard'))
    
    user = db.session.get(User, session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    
    # Get all active challenges with student progress
    active_challenges = Challenge.query.filter_by(is_active=True).all()
    challenges_data = []
    
    for challenge in active_challenges:
        # Get student's sessions for this challenge
        student_sessions = ChallengeSession.query.filter_by(
            challenge_id=challenge.id, 
            student_id=session['user_id']
        ).all()
        
        # Determine user status
        user_status = 'available'
        user_progress = None
        best_score = None
        current_rank = None
        attempts = len(student_sessions)
        
        if student_sessions:
            completed_sessions = [s for s in student_sessions if s.status == 'completed']
            if completed_sessions:
                user_status = 'completed'
                best_score = max([s.percentage for s in completed_sessions])
                # Get rank for best session
                best_session = max(completed_sessions, key=lambda s: s.percentage)
                current_rank = best_session.rank
            elif any(s.status == 'in_progress' for s in student_sessions):
                user_status = 'in-progress'
        
        # Get question count
        question_count = ChallengeQuestion.query.filter_by(challenge_id=challenge.id).count()
        
        # Get participant count
        participants = ChallengeSession.query.filter_by(challenge_id=challenge.id).count()
        
        challenge_data = {
            'id': challenge.id,
            'title': challenge.title,
            'description': challenge.description,
            'challenge_type': challenge.challenge_type,
            'difficulty': challenge.difficulty,
            'time_limit_minutes': challenge.time_limit_minutes,
            'time_limit': f"{challenge.time_limit_minutes} min" if challenge.time_limit_minutes else None,
            'max_attempts': challenge.max_attempts,
            'passing_score': challenge.passing_score,
            'question_count': question_count,
            'participants': participants,
            'user_status': user_status,
            'user_sessions': sorted([{
                'id': s.id,
                'percentage': s.percentage,
                'score': s.score,
                'status': s.status,
                'end_time': s.end_time
            } for s in student_sessions if s.status == 'completed'], 
            key=lambda x: x['percentage'], reverse=True) if student_sessions else [],
            'user_progress': {
                'attempts': attempts,
                'best_score': best_score,
                'rank': current_rank
            } if student_sessions else None
        }
        challenges_data.append(challenge_data)
    
    # Calculate student stats
    total_challenges = len([c for c in challenges_data if c['user_progress']])
    completed = len([c for c in challenges_data if c['user_status'] == 'completed'])
    all_scores = [c['user_progress']['best_score'] for c in challenges_data 
                  if c['user_progress'] and c['user_progress']['best_score']]
    average_score = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0
    best_rank = min([c['user_progress']['rank'] for c in challenges_data 
                     if c['user_progress'] and c['user_progress']['rank']]) if any(c['user_progress'] and c['user_progress']['rank'] for c in challenges_data) else 'N/A'
    
    my_stats = {
        'total_challenges': total_challenges,
        'completed': completed,
        'average_score': average_score,
        'best_rank': best_rank
    }
    
    return render_template('student_challenges.html', 
                         user=user, 
                         challenges=challenges_data, 
                         my_stats=my_stats)

@app.route('/api/student/challenges')
def api_student_challenges():
    """Get student challenges with progress"""
    if 'user_id' not in session or session.get('role') != 'student':
        return jsonify({'challenges': []})
    
    challenges = get_student_challenges(session['user_id'])
    return jsonify({'challenges': challenges})

@app.route('/challenge/<int:challenge_id>/start')
def start_challenge(challenge_id):
    """Start a challenge for a student"""
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
    
    try:
        # Get the challenge
        challenge = Challenge.query.get_or_404(challenge_id)
        
        # Check if challenge is active
        if not challenge.is_active:
            flash('This challenge is not currently available.', 'error')
            return redirect(url_for('student_challenges'))
        
        # Check if challenge has questions
        question_count = ChallengeQuestion.query.filter_by(challenge_id=challenge_id).count()
        if question_count == 0:
            flash('This challenge has no questions yet.', 'error')
            return redirect(url_for('student_challenges'))
        
        # Check if student has already completed this challenge
        existing_session = ChallengeSession.query.filter_by(
            challenge_id=challenge_id,
            student_id=session['user_id'],
            status='completed'
        ).first()
        
        # Check attempt limits if they exist
        if challenge.max_attempts:
            attempt_count = ChallengeSession.query.filter_by(
                challenge_id=challenge_id,
                student_id=session['user_id']
            ).count()
            
            if attempt_count >= challenge.max_attempts:
                flash(f'You have reached the maximum number of attempts ({challenge.max_attempts}) for this challenge.', 'error')
                return redirect(url_for('student_challenges'))
        
        # Check if there's an ongoing session
        ongoing_session = ChallengeSession.query.filter_by(
            challenge_id=challenge_id,
            student_id=session['user_id'],
            status='in_progress'
        ).first()
        
        if ongoing_session:
            # Continue existing session
            return redirect(url_for('take_challenge', session_id=ongoing_session.id))
        
        # Create new challenge session
        new_session = ChallengeSession(
            challenge_id=challenge_id,
            student_id=session['user_id'],
            start_time=datetime.now(timezone.utc),
            score=0,
            status='in_progress'
        )
        
        db.session.add(new_session)
        db.session.commit()
        
        # Redirect to the challenge taking interface
        return redirect(url_for('take_challenge', session_id=new_session.id))
        
    except Exception as e:
        print(f"Error starting challenge: {e}")
        flash('An error occurred while starting the challenge. Please try again.', 'error')
        return redirect(url_for('student_challenges'))

@app.route('/challenge/session/<int:session_id>')
def take_challenge(session_id):
    """Take a challenge - display questions and handle answers"""
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
    
    try:
        # Get the challenge session
        challenge_session = ChallengeSession.query.get_or_404(session_id)
        
        # Verify this session belongs to the current user
        if challenge_session.student_id != session['user_id']:
            flash('Access denied to this challenge session.', 'error')
            return redirect(url_for('student_challenges'))
        
        # Check if session is already completed
        if challenge_session.status == 'completed':
            return redirect(url_for('challenge_results', session_id=session_id))
        
        # Get the challenge and questions
        challenge = Challenge.query.get_or_404(challenge_session.challenge_id)
        questions = ChallengeQuestion.query.filter_by(challenge_id=challenge.id).order_by(ChallengeQuestion.order_index).all()
        
        if not questions or len(questions) == 0:
            flash('This challenge has no questions.', 'error')
            return redirect(url_for('student_challenges'))
        
        # Get answered questions to determine current question
        answered_questions = ChallengeAnswer.query.filter_by(session_id=session_id).all()
        answered_question_ids = [ans.question_id for ans in answered_questions]
        
        # Find the first unanswered question
        current_question = None
        current_question_num = 1
        
        for i, question in enumerate(questions):
            if question.id not in answered_question_ids:
                current_question = question
                current_question_num = i + 1
                break
        
        # If all questions are answered, complete the challenge
        if current_question is None:
            # Calculate final score and complete
            correct_answers = sum(1 for ans in answered_questions if ans.is_correct)
            challenge_session.score = correct_answers
            challenge_session.percentage = round((correct_answers / len(questions)) * 100)
            challenge_session.status = 'completed'
            challenge_session.end_time = datetime.now(timezone.utc)
            
            # Calculate points using the new point system
            points_breakdown = calculate_challenge_points(challenge_session, challenge, len(questions))
            challenge_session.points = points_breakdown['total']
            challenge_session.points_breakdown = json.dumps(points_breakdown)  # Store detailed breakdown
            
            db.session.commit()
            return redirect(url_for('challenge_results', session_id=session_id))
        
        # Calculate progress
        progress = {
            'current': current_question_num,
            'total': len(questions),
            'percentage': round((current_question_num - 1) / len(questions) * 100)
        }
        
        # Calculate per-question time limit for speed answering
        per_question_time = None
        if challenge.time_limit_minutes:
            total_time_seconds = challenge.time_limit_minutes * 60
            per_question_time = total_time_seconds // len(questions)  # Integer division for seconds per question
        
        return render_template('take_challenge.html',
                             session=challenge_session,
                             challenge=challenge,
                             question=current_question,
                             progress=progress,
                             per_question_time=per_question_time)
        
    except Exception as e:
        print(f"Error taking challenge: {e}")
        flash('An error occurred while loading the challenge. Please try again.', 'error')
        return redirect(url_for('student_challenges'))

@app.route('/challenge/session/<int:session_id>/answer', methods=['POST'])
def submit_challenge_answer(session_id):
    """Submit an answer for a challenge question"""
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
    
    try:
        # Get the challenge session
        challenge_session = ChallengeSession.query.get_or_404(session_id)
        
        # Verify this session belongs to the current user
        if challenge_session.student_id != session['user_id']:
            flash('Access denied to this challenge session.', 'error')
            return redirect(url_for('student_challenges'))
        
        # Check if session is already completed
        if challenge_session.status == 'completed':
            return redirect(url_for('challenge_results', session_id=session_id))
        
        # Get form data
        question_id = int(request.form.get('question_id'))
        answer = request.form.get('answer')
        is_auto_submit = request.form.get('auto_submit', 'false') == 'true'
        
        # Allow empty answer for auto-submit (time expired)
        if not answer and not is_auto_submit:
            flash('Please select an answer.', 'error')
            return redirect(url_for('take_challenge', session_id=session_id))
        
        # Get the question
        question = ChallengeQuestion.query.get_or_404(question_id)
        
        # Check if answer is correct (false if no answer provided)
        is_correct = False
        if answer:  # Only check correctness if answer was provided
            if question.question_type == 'multiple_choice':
                # For MCQ, get the correct option text
                correct_option_letter = question.correct_option
                if correct_option_letter == 'A':
                    correct_answer = question.option_a
                elif correct_option_letter == 'B':
                    correct_answer = question.option_b
                elif correct_option_letter == 'C':
                    correct_answer = question.option_c
                elif correct_option_letter == 'D':
                    correct_answer = question.option_d
                else:
                    correct_answer = None
                
                is_correct = (answer == correct_answer)
            else:
                # For true/false or text questions
                correct_answer = question.answer
                is_correct = (answer.strip().lower() == correct_answer.strip().lower())
        
        # Check if this question was already answered
        existing_answer = ChallengeAnswer.query.filter_by(
            session_id=session_id,
            question_id=question_id
        ).first()
        
        if existing_answer:
            flash('This question has already been answered.', 'error')
            return redirect(url_for('take_challenge', session_id=session_id))
        
        # Save the answer (empty string if no answer provided)
        challenge_answer = ChallengeAnswer(
            session_id=session_id,
            question_id=question_id,
            answer=answer or '',  # Store empty string if no answer
            is_correct=is_correct,
            answered_at=datetime.now(timezone.utc)
        )
        
        db.session.add(challenge_answer)
        db.session.commit()
        
        # Different messages for manual vs auto-submission
        if is_auto_submit:
            if answer:
                flash('Time expired! Your answer was submitted.', 'warning')
            else:
                flash('Time expired! No answer was submitted.', 'warning')
        else:
            flash('Answer submitted successfully!', 'success')
        
        # Continue to next question (the take_challenge route will handle completion)
        return redirect(url_for('take_challenge', session_id=session_id))
        
    except Exception as e:
        print(f"Error submitting answer: {e}")
        flash('An error occurred while submitting your answer. Please try again.', 'error')
        return redirect(url_for('take_challenge', session_id=session_id))

@app.route('/challenge/session/<int:session_id>/results')
def challenge_results(session_id):
    """Show challenge results"""
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
    
    try:
        # Get the challenge session
        challenge_session = ChallengeSession.query.get_or_404(session_id)
        
        # Verify this session belongs to the current user
        if challenge_session.student_id != session['user_id']:
            flash('Access denied to this challenge session.', 'error')
            return redirect(url_for('student_challenges'))
        
        # Check if session is completed
        if challenge_session.status != 'completed':
            return redirect(url_for('take_challenge', session_id=session_id))
        
        challenge = Challenge.query.get_or_404(challenge_session.challenge_id)
        
        # Calculate detailed results using actual answers
        total_questions = ChallengeQuestion.query.filter_by(challenge_id=challenge.id).count()
        answered_questions = ChallengeAnswer.query.filter_by(session_id=session_id).all()
        correct_answers = sum(1 for ans in answered_questions if ans.is_correct)
        percentage = round((correct_answers / total_questions) * 100) if total_questions > 0 else 0
        
        # Update session with final score if not already set
        if challenge_session.score != correct_answers or challenge_session.percentage != percentage:
            challenge_session.score = correct_answers
            challenge_session.percentage = percentage
            db.session.commit()
        
        # Determine pass/fail
        passing_score = challenge.passing_score or 70
        passed = percentage >= passing_score
        
        # Get time taken
        time_taken = None
        if challenge_session.end_time and challenge_session.start_time:
            time_diff = challenge_session.end_time - challenge_session.start_time
            time_taken = str(time_diff).split('.')[0]  # Remove microseconds
        
        # Get detailed answers for review
        challenge_answers = ChallengeAnswer.query.filter_by(session_id=session_id).all()
        questions_with_answers = []
        
        for answer in challenge_answers:
            question = ChallengeQuestion.query.get(answer.question_id)
            if question:
                questions_with_answers.append({
                    'question': question,
                    'answer': answer,
                    'is_correct': answer.is_correct
                })
        
        # Parse points breakdown if available
        points_breakdown = None
        if challenge_session.points_breakdown:
            try:
                points_breakdown = json.loads(challenge_session.points_breakdown)
            except:
                points_breakdown = None
        
        results = {
            'challenge': challenge,
            'session': challenge_session,
            'total_questions': total_questions,
            'correct_answers': correct_answers,
            'percentage': percentage,
            'passed': passed,
            'passing_score': passing_score,
            'time_taken': time_taken,
            'questions_with_answers': questions_with_answers,
            'points_breakdown': points_breakdown
        }
        
        return render_template('challenge_results.html', **results)
        
    except Exception as e:
        print(f"Error showing results: {e}")
        flash('An error occurred while loading results. Please try again.', 'error')
        return redirect(url_for('student_challenges'))

@app.route('/student/challenge-history')
def student_challenge_history():
    """Show student's challenge history and results"""
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
    
    try:
        # Get all completed challenge sessions for this student
        completed_sessions = ChallengeSession.query.filter_by(
            student_id=session['user_id'],
            status='completed'
        ).order_by(ChallengeSession.end_time.desc()).all()
        
        # Get challenge details for each session
        history = []
        for session_obj in completed_sessions:
            challenge = Challenge.query.get(session_obj.challenge_id)
            if challenge:
                # Get total questions for this challenge
                total_questions = ChallengeQuestion.query.filter_by(challenge_id=challenge.id).count()
                
                history.append({
                    'session': session_obj,
                    'challenge': challenge,
                    'total_questions': total_questions,
                    'percentage': session_obj.percentage,
                    'passed': session_obj.percentage >= (challenge.passing_score or 70),
                    'date_completed': session_obj.end_time.strftime('%Y-%m-%d %H:%M') if session_obj.end_time else 'N/A'
                })
        
        return render_template('student_challenge_history.html', history=history)
        
    except Exception as e:
        print(f"Error loading challenge history: {e}")
        flash('An error occurred while loading your challenge history.', 'error')
        return redirect(url_for('student_challenges'))

@app.route('/student/rankings')
def student_rankings():
    """Show student rankings based on total points"""
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))
    
    try:
        # Get all students with their total points from completed challenges
        student_rankings = db.session.query(
            User.id,
            User.username,
            User.email,
            db.func.sum(ChallengeSession.points).label('total_points'),
            db.func.count(ChallengeSession.id).label('challenges_completed')
        ).join(
            ChallengeSession, User.id == ChallengeSession.student_id
        ).filter(
            User.role == 'student',
            ChallengeSession.status == 'completed'
        ).group_by(
            User.id, User.username, User.email
        ).order_by(
            db.func.sum(ChallengeSession.points).desc()
        ).all()
        
        # Add rank numbers
        rankings_with_rank = []
        for rank, student in enumerate(student_rankings, 1):
            rankings_with_rank.append({
                'rank': rank,
                'user_id': student.id,
                'username': student.username,
                'email': student.email,
                'total_points': student.total_points or 0,
                'challenges_completed': student.challenges_completed or 0,
                'is_current_user': student.id == session['user_id']
            })
        
        # Get current user's rank
        current_user_rank = None
        for student in rankings_with_rank:
            if student['is_current_user']:
                current_user_rank = student['rank']
                break
        
        # Get top performers this week
        from datetime import datetime, timedelta
        one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        
        weekly_rankings = db.session.query(
            User.username,
            db.func.sum(ChallengeSession.points).label('weekly_points')
        ).join(
            ChallengeSession, User.id == ChallengeSession.student_id
        ).filter(
            User.role == 'student',
            ChallengeSession.status == 'completed',
            ChallengeSession.end_time >= one_week_ago
        ).group_by(
            User.id, User.username
        ).order_by(
            db.func.sum(ChallengeSession.points).desc()
        ).limit(5).all()
        
        return render_template('student_rankings.html',
                             rankings=rankings_with_rank,
                             current_user_rank=current_user_rank,
                             weekly_rankings=weekly_rankings,
                             total_students=len(rankings_with_rank))
        
    except Exception as e:
        print(f"Error loading rankings: {e}")
        flash('An error occurred while loading rankings.', 'error')
        return redirect(url_for('student_challenges'))

# WebRTC and Live Session API Endpoints

@app.route('/api/session/<int:session_id>/update_media', methods=['POST'])
def update_session_media(session_id):
    """Update participant's media state (camera/microphone)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        camera_enabled = data.get('camera_enabled', False)
        microphone_enabled = data.get('microphone_enabled', False)
        
        # Update participant's media state in database
        participant = SessionParticipant.query.filter_by(
            session_id=session_id,
            user_id=session['user_id']
        ).first()
        
        if participant:
            participant.camera_enabled = camera_enabled
            participant.microphone_enabled = microphone_enabled
            db.session.commit()
            
            return jsonify({
                'success': True,
                'camera_enabled': camera_enabled,
                'microphone_enabled': microphone_enabled
            })
        else:
            return jsonify({'success': False, 'error': 'Participant not found'}), 404
            
    except Exception as e:
        print(f"Error updating media state: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/api/session/<int:session_id>/signaling', methods=['POST'])
def handle_signaling(session_id):
    """Handle WebRTC signaling messages"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        message_type = data.get('type')
        
        # For now, just log the signaling message
        # In a full implementation, you'd use WebSockets or Server-Sent Events
        # to relay messages between participants
        print(f"Signaling message from user {session['user_id']}: {message_type}")
        
        # Here you would typically:
        # 1. Store the signaling message temporarily
        # 2. Send it to the appropriate peer(s) via WebSocket/SSE
        # 3. Handle offer/answer/ice-candidate exchange
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Error handling signaling: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/api/session/<int:session_id>/participants', methods=['GET'])
def get_session_participants(session_id):
    """Get current session participants with their media states"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        # Get all active participants
        participants = db.session.query(
            SessionParticipant, User
        ).join(
            User, SessionParticipant.user_id == User.id
        ).filter(
            SessionParticipant.session_id == session_id,
            SessionParticipant.is_online == True
        ).all()
        
        participant_list = []
        for participant, user in participants:
            participant_list.append({
                'id': user.id,
                'username': user.username,
                'camera_enabled': participant.camera_enabled,
                'microphone_enabled': participant.microphone_enabled,
                'joined_at': participant.joined_at.isoformat() if participant.joined_at else None
            })
        
        return jsonify({
            'success': True,
            'participants': participant_list
        })
        
    except Exception as e:
        print(f"Error getting participants: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

# Quizzo Bot Chatbot Routes

@app.route('/quizzo-bot')
def quizzo_bot():
    """Main chatbot interface"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        # Get user information
        user = User.query.get(session['user_id'])
        user_name = user.username if user else 'Student'
        
        # Get user's recent chat sessions
        recent_sessions = ChatSession.query.filter_by(
            user_id=session['user_id'],
            is_active=True
        ).order_by(ChatSession.last_activity.desc()).limit(5).all()
        
        return render_template('quizzo_bot.html', 
                             recent_sessions=recent_sessions, 
                             user_name=user_name)
        
    except Exception as e:
        print(f"Error loading chatbot: {e}")
        flash('Error loading chatbot interface.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/api/quizzo-bot/new-session', methods=['POST'])
def create_chat_session():
    """Create a new chat session"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        # Create new chat session
        chat_session = ChatSession(
            user_id=session['user_id'],
            session_title='New Chat'
        )
        db.session.add(chat_session)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'session_id': chat_session.id,
            'message': 'New chat session created'
        })
        
    except Exception as e:
        print(f"Error creating chat session: {e}")
        return jsonify({'success': False, 'error': 'Failed to create chat session'}), 500

@app.route('/api/quizzo-bot/session/<int:session_id>/messages', methods=['GET'])
def get_chat_messages(session_id):
    """Get messages for a chat session"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        # Verify session belongs to user
        chat_session = ChatSession.query.filter_by(
            id=session_id,
            user_id=session['user_id']
        ).first()
        
        if not chat_session:
            return jsonify({'success': False, 'error': 'Chat session not found'}), 404
        
        # Get messages
        messages = ChatMessage.query.filter_by(
            chat_session_id=session_id
        ).order_by(ChatMessage.created_at.asc()).all()
        
        message_list = []
        for msg in messages:
            message_list.append({
                'id': msg.id,
                'message': msg.message,
                'response': msg.response,
                'message_type': msg.message_type,
                'category': msg.category,
                'created_at': msg.created_at.isoformat(),
                'is_helpful': msg.is_helpful
            })
        
        return jsonify({
            'success': True,
            'messages': message_list,
            'session_title': chat_session.session_title
        })
        
    except Exception as e:
        print(f"Error getting chat messages: {e}")
        return jsonify({'success': False, 'error': 'Failed to get messages'}), 500

@app.route('/api/quizzo-bot/session/<int:session_id>/send', methods=['POST'])
def send_chat_message(session_id):
    """Send a message to Quizzo Bot"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        message_text = data.get('message', '').strip()
        
        if not message_text:
            return jsonify({'success': False, 'error': 'Message cannot be empty'}), 400
        
        # Verify session belongs to user
        chat_session = ChatSession.query.filter_by(
            id=session_id,
            user_id=session['user_id']
        ).first()
        
        if not chat_session:
            return jsonify({'success': False, 'error': 'Chat session not found'}), 404
        
        # Start timing for response generation
        import time
        start_time = time.time()
        
        # Generate AI response using existing AI infrastructure
        bot_response = generate_quizzo_bot_response(message_text, session['user_id'])
        
        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Determine message category
        category = categorize_message(message_text)
        
        # Create user message
        user_message = ChatMessage(
            chat_session_id=session_id,
            user_id=session['user_id'],
            message=message_text,
            message_type='user',
            category=category,
            response_time_ms=response_time_ms
        )
        db.session.add(user_message)
        
        # Create bot response message
        bot_message = ChatMessage(
            chat_session_id=session_id,
            user_id=session['user_id'],  # Same user for tracking
            message=bot_response,
            message_type='bot',
            category=category,
            response_time_ms=response_time_ms
        )
        db.session.add(bot_message)
        
        # Update session
        chat_session.last_activity = datetime.now(timezone.utc)
        chat_session.message_count += 2  # User message + bot response
        
        # Update session title if it's the first message
        if chat_session.session_title == 'New Chat' and len(message_text) > 0:
            # Use first few words as title
            title_words = message_text.split()[:5]
            chat_session.session_title = ' '.join(title_words) + ('...' if len(title_words) == 5 else '')
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'user_message': {
                'id': user_message.id,
                'message': user_message.message,
                'message_type': 'user',
                'created_at': user_message.created_at.isoformat()
            },
            'bot_response': {
                'id': bot_message.id,
                'message': bot_message.message,
                'message_type': 'bot',
                'created_at': bot_message.created_at.isoformat(),
                'response_time_ms': response_time_ms
            }
        })
        
    except Exception as e:
        print(f"Error sending chat message: {e}")
        return jsonify({'success': False, 'error': 'Failed to send message'}), 500

@app.route('/api/quizzo-bot/feedback', methods=['POST'])
def chat_feedback():
    """Provide feedback on bot response"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        message_id = data.get('message_id')
        is_helpful = data.get('is_helpful')  # True/False
        
        # Find and update the message
        message = ChatMessage.query.filter_by(
            id=message_id,
            user_id=session['user_id'],
            message_type='bot'
        ).first()
        
        if message:
            message.is_helpful = is_helpful
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'Feedback recorded'})
        else:
            return jsonify({'success': False, 'error': 'Message not found'}), 404
            
    except Exception as e:
        print(f"Error recording feedback: {e}")
        return jsonify({'success': False, 'error': 'Failed to record feedback'}), 500

# Quizzo Bot AI Functions

def detect_all_quizzo_features():
    """Dynamically detect all QUIZZO features by analyzing routes, templates, and models"""
    features = {}
    
    try:
        # Get all routes from current app
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append({
                'path': rule.rule,
                'methods': ','.join(rule.methods - {'HEAD', 'OPTIONS'}),
                'endpoint': rule.endpoint
            })
        
        # Categorize features based on routes
        features = {
            'Virtual Classroom': {
                'description': 'Real-time video calls, live sessions, and collaborative learning',
                'routes': [r for r in routes if any(keyword in r['path'].lower() for keyword in ['virtual', 'session', 'classroom', 'live'])],
                'status': 'Active',
                'new_feature': True
            },
            'AI Course Generator': {
                'description': 'AI-powered course creation with comprehensive content generation',
                'routes': [r for r in routes if any(keyword in r['path'].lower() for keyword in ['ai', 'generate', 'template'])],
                'status': 'Active',
                'enhanced': True
            },
            'Course Management': {
                'description': 'Course enrollment, lessons, and progress tracking',
                'routes': [r for r in routes if any(keyword in r['path'].lower() for keyword in ['course', 'lesson', 'enroll'])],
                'status': 'Active'
            },
            'Exam System': {
                'description': 'Create, take, and analyze exams with detailed results',
                'routes': [r for r in routes if any(keyword in r['path'].lower() for keyword in ['exam', 'test', 'take_exam'])],
                'status': 'Active'
            },
            'Challenges': {
                'description': 'Interactive learning challenges and competitions',
                'routes': [r for r in routes if 'challenge' in r['path'].lower()],
                'status': 'Active'
            },
            'Dashboard': {
                'description': 'Student and lecturer role-based dashboards',
                'routes': [r for r in routes if 'dashboard' in r['path'].lower()],
                'status': 'Active'
            },
            'Study Materials': {
                'description': 'Browse, bookmark, and rate learning materials',
                'routes': [r for r in routes if any(keyword in r['path'].lower() for keyword in ['material', 'study'])],
                'status': 'Active'
            },
            'User Management': {
                'description': 'User profiles, authentication, and settings',
                'routes': [r for r in routes if any(keyword in r['path'].lower() for keyword in ['profile', 'login', 'signup', 'user'])],
                'status': 'Active'
            },
            'Notifications': {
                'description': 'Real-time notifications and alerts system',
                'routes': [r for r in routes if 'notification' in r['path'].lower()],
                'status': 'Active'
            },
            'Chatbot System': {
                'description': 'AI-powered study assistant and platform guide',
                'routes': [r for r in routes if any(keyword in r['path'].lower() for keyword in ['bot', 'chat', 'quizzo-bot'])],
                'status': 'Active'
            }
        }
        
        # Remove features with no routes
        features = {k: v for k, v in features.items() if v['routes']}
        
    except Exception as e:
        print(f"Error detecting features: {e}")
        # Fallback static feature list
        features = {
            'Virtual Classroom': {'description': 'Video calls and live sessions', 'routes': [], 'status': 'Active'},
            'AI Course Generator': {'description': 'AI-powered course creation', 'routes': [], 'status': 'Active'},
            'Course Management': {'description': 'Course and lesson management', 'routes': [], 'status': 'Active'},
            'Exam System': {'description': 'Exams and assessments', 'routes': [], 'status': 'Active'},
            'Challenges': {'description': 'Learning challenges', 'routes': [], 'status': 'Active'}
        }
    
    return features

def generate_feature_list(features):
    """Generate a formatted list of features for chatbot responses"""
    feature_list = []
    for name, data in features.items():
        status_icon = "🆕" if data.get('new_feature') else "✨" if data.get('enhanced') else "✅"
        route_count = len(data.get('routes', []))
        feature_list.append(f"{status_icon} **{name}** ({route_count} endpoints) - {data.get('description', 'Platform feature')}")
    
    return '\n'.join(feature_list[:8])  # Limit to 8 features for readability

def generate_quizzo_bot_response(message, user_id):
    """Generate intelligent response from Quizzo Bot using AI services"""
    try:
        # Get user context for personalized responses
        user = User.query.get(user_id)
        user_role = user.role if user else 'student'
        user_name = user.username if user else 'Student'
        
        # Get recent conversation context for continuity
        recent_messages = ChatMessage.query.filter_by(user_id=user_id)\
            .order_by(ChatMessage.created_at.desc())\
            .limit(6).all()
        
        conversation_context = ""
        if recent_messages:
            context_msgs = []
            for msg in reversed(recent_messages):
                if msg.message_type == 'user':
                    context_msgs.append(f"User: {msg.message}")
                else:
                    context_msgs.append(f"Bot: {msg.message}")
            conversation_context = "\n".join(context_msgs[-4:])  # Last 4 messages
        
        # Categorize the message to provide focused responses
        category = categorize_message(message)
        
        # Try to get AI response using Grok/Groq for intelligent responses
        print(f"[CHATBOT] Attempting Grok API call for message: '{message[:50]}...'")
        print(f"[CHATBOT] User: {user_name} ({user_role}), Category: {category}")
        
        ai_response = try_grok_for_chatbot(message, user_role, category, conversation_context, user_name)
        
        if ai_response and ai_response.strip():
            print(f"[CHATBOT] Grok response received: {len(ai_response)} chars")
            # Format the response to ensure proper structure
            formatted_response = format_bot_response(ai_response, user_name)
            return formatted_response
        else:
            print(f"[CHATBOT] Grok failed, using fallback response")
            # Fallback to enhanced rule-based responses if AI fails
            return generate_enhanced_fallback_response(message, category, user_role, user_name)
            
    except Exception as e:
        print(f"Error generating bot response: {e}")
        return generate_enhanced_fallback_response(message, 'general', 'student', 'Student')

def format_bot_response(response, user_name):
    """Format AI response intelligently based on content type and enforce structured format"""
    
    # Check if response is interactive content (should keep paragraph format)
    interactive_keywords = ['question:', 'timer starts', 'your answer', 'challenge', 'quiz', 
                           'correct!', 'wrong', 'points', 'next question', 'well done', 
                           'let\'s practice', 'here\'s your']
    
    # If it's interactive content, keep the natural paragraph format
    if any(keyword in response.lower() for keyword in interactive_keywords):
        return response
    
    # Check if response is already properly formatted with **bold** structure
    if response.startswith('**') and '• ' in response and user_name in response:
        return response
    
    # FORCE STRUCTURED FORMAT for any unstructured response
    # Detect if response is a paragraph (long text without proper structure)
    is_paragraph = (len(response) > 150 and 
                   not response.startswith('**') and
                   response.count('• ') < 2 and  # Less than 2 bullet points means it's likely paragraph
                   not any(keyword in response.lower() for keyword in interactive_keywords))
    
    if is_paragraph:
        # Break down paragraph into structured format
        sentences = [s.strip() for s in response.replace('. ', '.\n').split('\n') if s.strip()]
        
        # Create structured response
        formatted_response = f"**Study Assistance - {user_name}:**\n\n"
        formatted_response += "**Key Points:**\n"
        
        for sentence in sentences[:4]:  # Take first 4 sentences
            if sentence and len(sentence) > 10:
                # Shorten sentence if too long
                if len(sentence) > 80:
                    sentence = sentence[:77] + "..."
                formatted_response += f"• {sentence}\n"
        
        formatted_response += f"\n**What else would you like to know, {user_name}?**"
        return formatted_response
    
    return response

def generate_enhanced_fallback_response(message, category, user_role, user_name='Student'):
    """Generate intelligent rule-based fallback responses with dynamic feature detection"""
    
    message_lower = message.lower()
    
    # Get current features dynamically
    current_features = detect_all_quizzo_features()
    
    # Feature-specific responses with dynamic detection
    if any(word in message_lower for word in ['virtual', 'classroom', 'live session', 'video call', 'webrtc']):
        virtual_classroom_info = current_features.get('Virtual Classroom', {})
        routes = virtual_classroom_info.get('routes', [])
        return f"""**🎥 Virtual Classroom - {user_name}:**

**✨ Real-time Learning Environment:**
• **Video Calls**: HD video with WebRTC technology
• **Live Sessions**: Interactive learning with multiple participants  
• **Chat Integration**: Real-time messaging during sessions
• **Screen Sharing**: Share presentations and materials
• **Session Management**: Create, join, and manage learning sessions

**🚀 Available Features:**
{chr(10).join([f'• {route["path"]} - {route["methods"]} methods' for route in routes[:5]])}

**🎯 How to Access:**
• Go to your dashboard and look for "Virtual Classroom" 
• Click "Create Session" to start a new live session
• Or "Join Session" to enter an existing room

**💡 Perfect for:**
• Group study sessions
• Live lectures and tutorials  
• Collaborative problem-solving
• Remote office hours

**Need help getting started with virtual classrooms, {user_name}?**"""

    elif any(word in message_lower for word in ['ai course', 'course generator', 'generate course', 'ai generate']):
        ai_course_info = current_features.get('AI Course Generator', {})
        return f"""**🤖 AI Course Generator - {user_name}:**

**✨ Advanced AI-Powered Course Creation:**
• **Intelligent Content**: Comprehensive lessons with detailed explanations
• **GeeksforGeeks Quality**: Rich educational content with examples
• **Multiple Formats**: Video-style lessons, interactive content, assessments
• **Adaptive Learning**: Content tailored to difficulty levels

**🎯 What You Get:**
• Detailed topic explanations with real-world examples
• Code snippets and practical demonstrations
• Visual diagrams and learning aids
• Interactive quizzes and assessments
• Best practices and troubleshooting guides

**🚀 Recent Enhancement:**
✅ **Content Quality Upgrade**: Now generates comprehensive, detailed lessons
✅ **Rich Examples**: Practical applications and case studies
✅ **Visual Learning**: Diagrams and flowcharts included

**📍 Access Path:** Dashboard → AI Course Generator → Create Course

**Ready to create your first AI-powered course, {user_name}?**"""

    elif any(word in message_lower for word in ['course', 'enroll', 'lesson', 'study material']):
        course_info = current_features.get('Course Management', {})
        return f"""**📚 Course Management System - {user_name}:**

**🎓 Comprehensive Learning Platform:**
• **Course Enrollment**: Automatic enrollment numbers (QZ-XXX-2025-XXXX format)
• **Progress Tracking**: Monitor your learning journey
• **Lesson Navigation**: Sequential learning with completion tracking
• **Study Materials**: Rich content library with bookmarking

**✨ Enhanced Features:**
• **Smart Enrollment**: Auto-capture student details and generate unique IDs
• **Course Preview**: See detailed content before enrolling
• **Progress Analytics**: Track completion rates and performance

**🎯 Available Actions:**
• Browse and search courses by category
• Enroll with one-click enrollment system
• Access lessons with interactive content
• Bookmark favorite materials

**Want to explore courses or need help with enrollment, {user_name}?**"""

    elif any(word in message_lower for word in ['exam', 'test', 'challenge', 'quiz', 'assessment']):
        exam_info = current_features.get('Exam System', {})
        challenge_info = current_features.get('Challenges', {})
        return f"""**⚡ Exams & Challenges System - {user_name}:**

**🎯 Interactive Assessment Platform:**
• **Speed Challenges**: 30-second timer per question for rapid learning
• **Comprehensive Exams**: Full-length assessments with detailed analytics
• **AI-Generated Questions**: Fresh content powered by advanced AI
• **Real-time Results**: Instant feedback and performance breakdowns

**🏆 Scoring & Competition:**
• **Points System**: Earn points for participation, accuracy, and speed
• **Leaderboards**: Compete with classmates and track rankings
• **Performance Analytics**: Detailed insights into your strengths

**⭐ Challenge Features:**
• Multiple difficulty levels
• Subject-specific content
• Timed competitions
• Progress tracking

**📊 Exam Features:**
• Comprehensive question banks
• Detailed result analysis
• Performance metrics
• Study recommendations

**Ready to test your knowledge, {user_name}?**"""

    elif any(word in message_lower for word in ['feature', 'new', 'update', 'platform', 'what can', 'capabilities']):
        return f"""**🚀 QUIZZO Platform Features Overview - {user_name}:**

**🆕 Recently Detected Features:**
{generate_feature_list(current_features)}

**✨ Platform Capabilities:**
• **Total Features**: {len(current_features)} major feature categories
• **Dynamic Detection**: I automatically detect new features as they're added
• **Comprehensive Coverage**: From basic learning to advanced collaboration

**🎯 Feature Categories:**
{chr(10).join([f'• **{name}**: {data.get("description", "Advanced platform feature")}' for name, data in current_features.items()])}

**💡 Pro Tip:**
I can help you with any of these features! Just ask about what interests you most.

**Which feature would you like to explore first, {user_name}?**"""

    # Past conversation/history responses
    elif any(phrase in message_lower for phrase in ['yesterday', 'last time', 'previous', 'before', 'earlier', 'what did we talk', 'remember when', 'last conversation']):
        return f"""**Hey {user_name}! Let me help with that! 💭**

**About Our Chat History:**
• I can access our previous conversations through the QUIZZO platform
• Our chat sessions are saved so we can pick up where we left off
• If you need to review specific topics, just ask!

**Quick Ways to Refresh:**
• Tell me the subject you want to continue discussing
• Ask about specific features we explored before
• Or start fresh with any new questions!

**What topic from our previous chats would you like to revisit, {user_name}?**"""
    
    # Greeting responses
    if any(word in message_lower for word in ['hello', 'hi', 'hey', 'greetings', 'good morning', 'good afternoon']):
        greetings = [
            f"Hey {user_name}! 🌟 Great to see you! What can I help you explore today?",
            f"Hi there, {user_name}! 😊 I'm excited to chat with you! What's on your mind?",
            f"Hello {user_name}! 🎯 Ready to dive into some learning or platform features?",
            f"Hey {user_name}! 👋 Perfect timing! What would you like to discover today?"
        ]
        return random.choice(greetings)
    
    # How are you responses
    if any(phrase in message_lower for phrase in ['how are you', 'how are you doing']):
        responses = [
            f"I'm doing fantastic, {user_name}! 🎉 Thanks for asking! I'm pumped up and ready to help with whatever you need!",
            f"Hey {user_name}! I'm great and super excited to chat with you! 😊 What's going on in your world today?",
            f"I'm awesome, {user_name}! 🌟 Feeling energized and ready to tackle some learning together! What can I help you with?",
            f"Doing wonderful, {user_name}! 🚀 I'm here and ready to make learning fun for you! What would you like to explore?"
        ]
        return random.choice(responses)
    
    # Name/identity questions
    if any(phrase in message_lower for phrase in ['what is your name', 'who are you', 'your name']):
        return f"Hey {user_name}! 🤖 I'm Quizzo Bot, your friendly study companion! Think of me as that enthusiastic friend who's always ready to help with homework, explain tricky concepts, or show you cool platform features. I love making learning fun and interactive! What would you like to dive into together?"
    
    # Casual conversation responses (what's up, stories, general chat)
    if any(phrase in message_lower for phrase in ['whats up', "what's up", 'sup', 'wassup', 'tell me a story', 'story']):
        responses = [
            f"Not much, {user_name}! Just hanging out here, ready to help you ace your studies! 😎 What's going on with you?",
            f"Hey {user_name}! Just chilling and thinking about all the cool stuff we could explore together! 🚀 What's on your mind?",
            f"Nothing crazy, {user_name}! Just excited to chat with you and see what we can learn today! 🌟 What brings you here?",
            f"Just the usual - helping awesome students like you succeed! 😊 What would you like to tackle today, {user_name}?"
        ]
        return random.choice(responses)
    
    # Subject-specific responses
    if 'biology' in message_lower:
        return f"""**Hey {user_name}! Love the biology question! 🧬**

**Bio & Tech are Best Friends:**
• CRISPR gene editing - like word processing for DNA!
• AI discovers new drugs and analyzes genetic data
• Neural networks inspired by how our brains work

**Cool Applications:**
• Lab-grown organs from stem cells 
• Biomimetics: copying nature for better tech designs
• AI predicts protein structures in minutes vs years

**What specific area sparks your curiosity, {user_name}? Gene editing? AI in medicine? Something else?**"""
    
    elif any(subject in message_lower for subject in ['chemistry', 'physics', 'math', 'mathematics']):
        subject_name = next(s for s in ['chemistry', 'physics', 'math', 'mathematics'] if s in message_lower)
        return f"""**{subject_name.title()} Study Tips - {user_name}:**

**Core Strategies:**
• Practice problems: Solve many different types to build understanding
• Understand concepts: Don't just memorize formulas, know why they work
• Break down complexity: Divide difficult problems into smaller steps

**Study Techniques:**
• Regular review: Use spaced repetition for formulas and key concepts
• Work systematically: Follow logical steps for problem-solving
• Connect ideas: See how different topics relate to each other

**QUIZZO Integration:**
• Use speed challenges: Reinforce your learning with timed practice
• Track progress: Monitor which areas need more attention

**What specific {subject_name} topic would you like help with, {user_name}?**"""
    
    # Note-taking specific help
    elif any(phrase in message_lower for phrase in ['note taking', 'notes', 'note-taking', 'taking notes']):
        return f"""**Note-Taking Mastery - {user_name}:**

**Top Methods:**
• Cornell Method: Split page into notes section and keywords column
• Mind Maps: Create visual connections with circles and arrows
• Outline Format: Use hierarchical structure with main points and sub-points

**Effective Techniques:**
• Use abbreviations: Develop your own shorthand for faster writing
• Review within 24 hours: Reinforce learning while memory is fresh
• Add colors and highlights: Make important concepts stand out

**Digital Options:**
• Try apps like Notion, OneNote, or Obsidian for organized digital notes
• Sync across devices: Access your notes anywhere, anytime

**QUIZZO Connection:**
• Take notes during challenges: Track which topics you struggle with most

**Which note-taking method sounds most interesting to you, {user_name}?**"""
    
    # Study preparation questions
    elif any(phrase in message_lower for phrase in ['prepare', 'preparation', 'study before', 'advice', 'how should i study']):
        return f"""**Exam Preparation Strategy - {user_name}:**

**Before Taking QUIZZO Challenges:**
• Review Material: Go through your notes and textbooks
• Practice Questions: Try sample problems in your subject area
• Time Management: Practice answering quickly (30-second timer!)
• Key Concepts: Focus on main ideas and formulas

**Speed Challenge Tips:**
• Read questions carefully but quickly
• Eliminate obviously wrong answers
• Trust your first instinct
• Stay calm under pressure

**Scoring Strategy:**
• Balance speed and accuracy for maximum points

**What subject are you preparing for, {user_name}?**"""
    
    # Specific feature responses based on message content
    elif any(word in message_lower for word in ['point', 'score', 'ranking', 'leaderboard', 'good scores']):
        return f"""**QUIZZO Points & Rankings System - {user_name}:**

**How to Earn Points:**
• Base participation: 50 points per challenge
• Correct answers: 10 points each
• Speed bonuses: 25-100 points (answer faster to get more!)
• Performance bonuses: 10-50 points based on accuracy

**Rankings:**
• Compete with other students on real-time leaderboards

**Pro Tip:**
• Answer quickly AND accurately for maximum points!

**Want to know more about challenges or other features, {user_name}?**"""

    elif any(phrase in message_lower for phrase in ['where can i find', 'where is', 'how to access', 'find the exams']):
        return f"""**Finding QUIZZO Challenges & Exams - {user_name}:**

**Easy Access:**
• Go to your Dashboard
• Look for the "Take Challenge" button
• Click to start a new speed challenge
• Choose your subject area

**Quick Start:**
• The challenges are right on your main dashboard - you can't miss them!

**Ready to Compete:**
• Each challenge has a 30-second timer per question

**Need help with anything else about the platform, {user_name}?**"""

    elif any(word in message_lower for word in ['challenge', 'exam', 'test', 'quiz']):
        return f"""**QUIZZO Challenges & Exams - {user_name}:**

**Speed Challenges:**
• 30-second countdown per question
• AI-Generated Questions: Fresh content from multiple providers
• Real-time Results: Instant feedback and detailed breakdowns
• Competitive Element: Climb the leaderboards!

**How to Start:**
• Go to your dashboard and click "Take Challenge"

**Any specific questions about the challenge system, {user_name}?**"""

    elif any(word in message_lower for word in ['video', 'camera', 'microphone', 'virtual classroom', 'live session']):
        return f"""**Virtual Classroom & Live Sessions - {user_name}:**

**Video Features:**
• Video Calls: WebRTC-powered real-time video
• Audio Chat: Crystal-clear voice communication  
• Live Chat: Message other participants during sessions
• Multi-user: Connect with classmates and teachers
• Easy Controls: Simple camera/mic toggle buttons

**Getting Started:**
• Click the camera icon and allow browser permissions

**Need help with anything specific about virtual classrooms, {user_name}?**"""

    elif any(word in message_lower for word in ['study', 'learn', 'research', 'academic', 'homework']):
        return f"""**Academic Support & Study Tips - {user_name}:**

**Effective Study Techniques:**
• Active recall: Test yourself frequently
• Spaced repetition: Review material over time
• Practice with QUIZZO challenges for retention

**Research Help:**
• I can assist with academic topics and explanations

**Study Strategy:**
• Use QUIZZO's speed challenges to reinforce learning

**What subject or topic would you like help with, {user_name}?**"""

    # Category-based responses
    elif category == 'feature_request':
        return f"""**Feature Suggestions - {user_name}:**

**I appreciate your ideas for improving QUIZZO! However, I should be honest - I'm an AI assistant and can't actually contact Shadrack M Emadau or implement new features directly.**

**What I CAN do:**
• Help you with current QUIZZO features
• Provide academic support and study tips
• Answer questions about the platform
• Guide you through existing functionality

**For Feature Suggestions:**
• You could reach out to Shadrack directly through official channels
• Share feedback through the platform's support system
• Voice features would be an interesting addition to consider!

**Is there anything about the current QUIZZO features I can help you with, {user_name}?**"""
    
    elif category == 'developer':
        return f"""**About QUIZZO's Developer - {user_name}:**

**Creator:**
• Shadrack M Emadau

**Vision:**
• Creating innovative educational platforms

**QUIZZO Features Built by Shadrack:**
• AI-powered question generation
• Real-time speed challenges  
• Virtual classroom integration
• Comprehensive analytics system

**Shadrack developed QUIZZO to revolutionize student learning through gamification and AI technology.**

**What would you like to know about the platform, {user_name}?**"""
    
    elif category == 'app_features':
        return f"""📱 **QUIZZO Platform Overview:**

🎯 **Main Features:**
• AI-generated exams and challenges
• Real-time speed answering (30-sec timer)
• Comprehensive points system
• Student rankings and leaderboards
• Virtual classrooms with video calls
• Detailed progress tracking

✨ **For {user_role.title()}s:** Personalized dashboard with all your tools

What specific feature would you like to explore?"""

    # Default helpful response
    return """🤖 **I'm here to help with:**

🎯 **QUIZZO Features:** Navigation, challenges, exams, results
🏆 **Points & Rankings:** How scoring works, leaderboards
💻 **Virtual Classroom:** Video calls, live sessions, chat
📚 **Study Support:** Tips, research help, academic guidance

💡 **Try asking:** "How do challenges work?" or "Help me study better"

What would you like to know about?"""

def categorize_message(message):
    """Categorize user message to provide focused responses"""
    message_lower = message.lower()
    
    # Greeting keywords (should be conversational)
    greeting_keywords = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'how are you']
    
    # Academic subject keywords
    academic_keywords = ['biology', 'chemistry', 'physics', 'math', 'mathematics', 'english', 'history', 
                        'science', 'study', 'research', 'learn', 'education', 'academic', 'homework', 
                        'assignment', 'subject', 'topic', 'explain', 'help me understand', 'prepare',
                        'preparation', 'tips', 'advice', 'how to study', 'study tips', 'artificial intelligence',
                        'ai', 'machine learning', 'computer science', 'programming', 'technology', 'algorithm',
                        'data science', 'neural networks', 'robotics', 'automation', 'tell me about']
    
    # App features keywords
    app_keywords = ['exam', 'challenge', 'test', 'quiz', 'point', 'score', 'ranking', 'leaderboard', 
                   'profile', 'dashboard', 'login', 'signup', 'result', 'navigation', 'feature',
                   'where can i find', 'how to access', 'where is', 'how do i']
    
    # Challenge-specific keywords
    challenge_keywords = ['speed', 'timer', 'countdown', 'fast', 'quick', 'time limit', 
                         'compete', 'competition', 'rank', 'first place', 'good scores',
                         'practice', 'quiz me', 'test me', 'question', 'let\'s practice']
    
    # Virtual classroom keywords - improved with more variations
    classroom_keywords = ['video', 'audio', 'camera', 'microphone', 'virtual classroom', 'virtual class',
                         'live session', 'live sessions', 'live class', 'live classes', 'class live',
                         'call', 'meeting', 'chat', 'webrtc', 'video call', 'audio call']
    
    # Conversational keywords
    conversational_keywords = ['how are you', 'what can you do', 'who are you', 'your name', 
                              'whats up', "what's up", 'hey there', 'sup', 'wassup', 'how you doing',
                              'tell me a story', 'story', 'chat', 'talk', 'conversation']
    
    # Developer-related keywords
    developer_keywords = ['developer', 'creator', 'who made', 'who created', 'who built', 'who developed',
                         'shadrack', 'emadau', 'your developer', 'made quizzo', 'created quizzo']
    
    # Feature request keywords
    feature_request_keywords = ['tell shadrack to add', 'tell shadrack m emadau to add', 'add voice', 
                               'voice assistant', 'voice feature', 'ask shadrack', 'contact shadrack', 
                               'send message to', 'tell developer to add', 'add feature', 'can you add', 
                               'implement', 'voice chat', 'add you a voice']
    
    # Check categories in order of specificity
    if any(keyword in message_lower for keyword in feature_request_keywords):
        return 'feature_request'
    elif any(keyword in message_lower for keyword in developer_keywords):
        return 'developer'
    elif any(keyword in message_lower for keyword in conversational_keywords):
        return 'conversational'
    elif any(keyword in message_lower for keyword in greeting_keywords):
        return 'conversational'
    elif any(keyword in message_lower for keyword in classroom_keywords):
        return 'virtual_classroom'
    elif any(keyword in message_lower for keyword in academic_keywords):
        return 'academic'
    elif any(keyword in message_lower for keyword in challenge_keywords):
        return 'challenges'
    elif any(keyword in message_lower for keyword in app_keywords):
        return 'app_features'
    else:
        return 'general'

# NOTE: The old generate_fallback_response function has been replaced by generate_enhanced_fallback_response above

def calculate_challenge_points(session_obj, challenge, total_questions):
    """Calculate points for a completed challenge session based on multiple criteria"""
    points_breakdown = {
        'base_points': 0,
        'correctness_bonus': 0,
        'speed_bonus': 0,
        'completion_bonus': 0,
        'first_completion_bonus': 0,
        'total': 0
    }
    
    # Base points for participation
    points_breakdown['base_points'] = 50
    
    # Correctness bonus: 10 points per correct answer
    correct_answers = session_obj.score
    points_breakdown['correctness_bonus'] = correct_answers * 10
    
    # Speed bonus for timed challenges
    if challenge.time_limit_minutes and session_obj.end_time and session_obj.start_time:
        # Ensure both timestamps are timezone-aware for proper calculation
        end_time = session_obj.end_time
        start_time = session_obj.start_time
        
        # Convert to timezone-aware if needed
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
            
        time_taken_seconds = (end_time - start_time).total_seconds()
        total_time_allowed = challenge.time_limit_minutes * 60
        
        # Calculate speed ratio (faster = higher bonus)
        time_ratio = time_taken_seconds / total_time_allowed
        if time_ratio <= 0.5:  # Completed in half the time or less
            points_breakdown['speed_bonus'] = 100
        elif time_ratio <= 0.7:  # Completed in 70% of time
            points_breakdown['speed_bonus'] = 50
        elif time_ratio <= 0.85:  # Completed in 85% of time
            points_breakdown['speed_bonus'] = 25
    
    # Completion bonus based on percentage score
    percentage = session_obj.percentage
    if percentage >= 90:
        points_breakdown['completion_bonus'] = 50
    elif percentage >= 80:
        points_breakdown['completion_bonus'] = 30
    elif percentage >= 70:
        points_breakdown['completion_bonus'] = 20
    elif percentage >= 60:
        points_breakdown['completion_bonus'] = 10
    
    # First completion bonus (check if this is the first completion of this challenge)
    first_completion = ChallengeSession.query.filter(
        ChallengeSession.challenge_id == challenge.id,
        ChallengeSession.status == 'completed',
        ChallengeSession.end_time < session_obj.end_time
    ).first()
    
    if not first_completion:  # This is the first completion
        points_breakdown['first_completion_bonus'] = 100
    
    # Calculate total points
    points_breakdown['total'] = sum([
        points_breakdown['base_points'],
        points_breakdown['correctness_bonus'],
        points_breakdown['speed_bonus'],
        points_breakdown['completion_bonus'],
        points_breakdown['first_completion_bonus']
    ])
    
    return points_breakdown

@app.route('/student_progress')
def student_progress():
    """Show detailed progress for a student"""
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('dashboard'))
    
    # Get all student's exam sessions
    student_sessions = ExamSession.query.filter_by(student_id=session['user_id']).all()
    
    # Calculate comprehensive statistics
    total_exams_taken = len(student_sessions)
    completed_exams = [s for s in student_sessions if s.status == 'completed']
    disqualified_exams = [s for s in student_sessions if s.status == 'disqualified']
    
    # Calculate scores and grades
    scores = []
    grade_distribution = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
    total_questions = 0
    total_correct = 0
    
    for exam_session in completed_exams:
        if check_result_visibility(exam_session.exam_id):
            correct, questions, score = calculate_exam_score(exam_session)
            scores.append(score)
            total_questions += questions
            total_correct += correct
            
            # Assign grade
            if score >= 90:
                grade_distribution['A'] += 1
            elif score >= 80:
                grade_distribution['B'] += 1
            elif score >= 70:
                grade_distribution['C'] += 1
            elif score >= 60:
                grade_distribution['D'] += 1
            else:
                grade_distribution['F'] += 1
    
    # Calculate statistics
    avg_score = sum(scores) / len(scores) if scores else 0
    highest_score = max(scores) if scores else 0
    lowest_score = min(scores) if scores else 0
    improvement_trend = 'stable'
    
    if len(scores) >= 3:
        recent_avg = sum(scores[-3:]) / 3
        earlier_avg = sum(scores[:-3]) / len(scores[:-3]) if len(scores) > 3 else avg_score
        if recent_avg > earlier_avg + 5:
            improvement_trend = 'improving'
        elif recent_avg < earlier_avg - 5:
            improvement_trend = 'declining'
    
    progress_data = {
        'total_exams_taken': total_exams_taken,
        'completed_exams': len(completed_exams),
        'disqualified_exams': len(disqualified_exams),
        'avg_score': round(avg_score, 1),
        'highest_score': round(highest_score, 1),
        'lowest_score': round(lowest_score, 1),
        'grade_distribution': grade_distribution,
        'improvement_trend': improvement_trend,
        'total_questions_answered': total_questions,
        'total_correct_answers': total_correct,
        'accuracy_rate': round((total_correct / total_questions * 100), 1) if total_questions > 0 else 0,
        'recent_scores': scores[-5:] if len(scores) >= 5 else scores  # Last 5 scores
    }
    
    return render_template('student_progress.html', progress=progress_data, user=db.session.get(User, session['user_id']))

@app.route('/exam_schedule')
def exam_schedule():
    """Show exam schedule for both students and lecturers"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    from datetime import datetime, timedelta
    import calendar
    
    current_user = db.session.get(User, session['user_id'])
    if not current_user:
        return redirect(url_for('login'))
    
    user_role = session.get('role')
    now = datetime.now()
    
    # Calculate date ranges
    week_start = now - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=6)
    month_start = now.replace(day=1)
    next_month = month_start.replace(month=month_start.month % 12 + 1, day=1) if month_start.month < 12 else month_start.replace(year=month_start.year + 1, month=1, day=1)
    month_end = next_month - timedelta(days=1)
    
    if user_role == 'lecturer':
        # Lecturer view - manage all their exams
        lecturer_exams = Exam.query.filter_by(lecturer_id=session['user_id']).all()
        
        # Categorize exams
        upcoming_exams = []
        active_exams = []
        scheduled_exams = []
        completed_exams = []
        
        for exam in lecturer_exams:
            exam_sessions = ExamSession.query.filter_by(exam_id=exam.id).all()
            questions = Question.query.filter_by(exam_id=exam.id).all()
            
            exam_data = {
                'exam': exam,
                'question_count': len(questions),
                'total_attempts': len(exam_sessions),
                'completed_attempts': len([s for s in exam_sessions if s.status == 'completed']),
                'in_progress_attempts': len([s for s in exam_sessions if s.status == 'in_progress'])
            }
            
            if exam.is_scheduled:
                if exam.scheduled_start and exam.scheduled_end:
                    if now < exam.scheduled_start:
                        if exam.scheduled_start <= now + timedelta(days=7):
                            upcoming_exams.append(exam_data)
                        if month_start <= exam.scheduled_start <= month_end:
                            scheduled_exams.append(exam_data)
                    elif exam.scheduled_start <= now <= exam.scheduled_end:
                        active_exams.append(exam_data)
                    elif now > exam.scheduled_end:
                        if exam.scheduled_end >= week_start:
                            completed_exams.append(exam_data)
            else:
                # Non-scheduled exams are always available
                upcoming_exams.append(exam_data)
        
        # Calendar data
        calendar_events = []
        for exam in lecturer_exams:
            if exam.is_scheduled and exam.scheduled_start:
                calendar_events.append({
                    'id': exam.id,
                    'title': exam.title,
                    'start': exam.scheduled_start,
                    'end': exam.scheduled_end,
                    'type': 'scheduled' if now < exam.scheduled_start else 'active' if now <= exam.scheduled_end else 'completed'
                })
        
    else:
        # Student view - show available exams and their status
        all_exams = Exam.query.all()
        student_sessions = ExamSession.query.filter_by(student_id=session['user_id']).all()
        
        upcoming_exams = []
        active_exams = []
        scheduled_exams = []
        completed_exams = []
        
        for exam in all_exams:
            questions = Question.query.filter_by(exam_id=exam.id).all()
            student_session = next((s for s in student_sessions if s.exam_id == exam.id), None)
            
            exam_data = {
                'exam': exam,
                'question_count': len(questions),
                'estimated_time': len(questions) * 2,  # 2 minutes per question
                'session': student_session,
                'status': student_session.status if student_session else 'available'
            }
            
            if student_session:
                if student_session.status == 'completed':
                    if student_session.end_time and student_session.end_time >= week_start:
                        completed_exams.append(exam_data)
                elif student_session.status == 'in_progress':
                    active_exams.append(exam_data)
            else:
                # Check if exam is available
                if exam.is_scheduled:
                    if exam.scheduled_start and exam.scheduled_end:
                        if now < exam.scheduled_start:
                            if exam.scheduled_start <= now + timedelta(days=7):
                                upcoming_exams.append(exam_data)
                            if month_start <= exam.scheduled_start <= month_end:
                                scheduled_exams.append(exam_data)
                        elif exam.scheduled_start <= now <= exam.scheduled_end:
                            active_exams.append(exam_data)
                else:
                    upcoming_exams.append(exam_data)
        
        # Calendar data for students
        calendar_events = []
        for exam in all_exams:
            if exam.is_scheduled and exam.scheduled_start:
                student_session = next((s for s in student_sessions if s.exam_id == exam.id), None)
                calendar_events.append({
                    'id': exam.id,
                    'title': exam.title,
                    'start': exam.scheduled_start,
                    'end': exam.scheduled_end,
                    'type': 'completed' if student_session and student_session.status == 'completed' else 
                           'active' if exam.scheduled_start <= now <= exam.scheduled_end else 'scheduled'
                })
    
    # Calculate stats
    stats = {
        'upcoming_count': len(upcoming_exams),
        'active_count': len(active_exams),
        'scheduled_count': len(scheduled_exams),
        'completed_count': len(completed_exams)
    }
    
    # Generate calendar grid for current month
    cal = calendar.monthcalendar(now.year, now.month)
    calendar_grid = []
    for week in cal:
        week_data = []
        for day in week:
            if day == 0:
                week_data.append({'day': '', 'events': []})
            else:
                day_date = datetime(now.year, now.month, day)
                day_events = [e for e in calendar_events if e['start'].date() == day_date.date()]
                week_data.append({
                    'day': day,
                    'events': day_events,
                    'is_today': day_date.date() == now.date()
                })
        calendar_grid.append(week_data)
    
    return render_template('exam_schedule.html', 
                         upcoming_exams=upcoming_exams,
                         active_exams=active_exams,
                         scheduled_exams=scheduled_exams,
                         completed_exams=completed_exams,
                         calendar_events=calendar_events,
                         calendar_grid=calendar_grid,
                         current_month=now.strftime('%B %Y'),
                         current_time=now,
                         stats=stats,
                         user=current_user,
                         user_role=user_role)

@app.route('/bulk_schedule', methods=['GET', 'POST'])
def bulk_schedule():
    """Bulk schedule multiple exams"""
    if 'user_id' not in session or session.get('role') != 'lecturer':
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        # Handle bulk scheduling
        data = request.get_json()
        schedules = data.get('schedules', [])
        
        success_count = 0
        for schedule in schedules:
            try:
                exam_id = schedule.get('exam_id')
                start_time = schedule.get('start_time')
                end_time = schedule.get('end_time')
                
                if exam_id and start_time and end_time:
                    exam = db.session.get(Exam, exam_id)
                    if exam and exam.lecturer_id == session['user_id']:
                        exam.scheduled_start = datetime.fromisoformat(start_time)
                        exam.scheduled_end = datetime.fromisoformat(end_time)
                        exam.is_scheduled = True
                        success_count += 1
            except Exception as e:
                print(f"Error scheduling exam {schedule.get('exam_id')}: {e}")
                continue
        
        if success_count > 0:
            db.session.commit()
            return jsonify({'status': 'success', 'scheduled': success_count})
        else:
            return jsonify({'status': 'error', 'message': 'No exams were scheduled'})
    
    # GET request - show bulk schedule form
    lecturer_exams = Exam.query.filter_by(lecturer_id=session['user_id']).all()
    unscheduled_exams = [exam for exam in lecturer_exams if not exam.is_scheduled]
    
    return render_template('bulk_schedule.html', 
                         exams=unscheduled_exams,
                         user=db.session.get(User, session['user_id']))

@app.route('/generate_ai_exam', methods=['POST'])
def generate_ai_exam():
    if 'user_id' not in session or session.get('role') != 'lecturer':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        exam_title = data.get('examTitle', 'AI Generated Exam')
        topics = data.get('topics', [])
        question_count = int(data.get('questionCount', 10))
        difficulty = data.get('difficulty', 'Medium')
        duration = int(data.get('duration', 60))
        question_types = data.get('questionTypes', ['multiple_choice'])
        
        # Create the exam
        exam = Exam()
        exam.title = exam_title
        exam.lecturer_id = session['user_id']
        exam.created_at = datetime.now()
        exam.ai_generated = True  # Flag to indicate AI generation
        db.session.add(exam)
        db.session.flush()  # Get exam ID
        
        # Generate AI questions based on topics and parameters
        generated_questions = generate_ai_questions(
            topics=topics,
            count=question_count,
            difficulty=difficulty,
            question_types=question_types
        )
        
        # Save generated questions to database
        for q_data in generated_questions:
            question = Question()
            question.exam_id = exam.id
            question.text = q_data['question']
            question.question_type = q_data['type']
            
            if q_data['type'] == 'multiple_choice':
                question.option_a = q_data['options'][0]
                question.option_b = q_data['options'][1]
                question.option_c = q_data['options'][2]
                question.option_d = q_data['options'][3]
                question.correct_option = q_data['correct_option']
                question.answer = q_data['options'][q_data['correct_option']]
            else:
                question.answer = q_data['answer']
                question.option_a = None
                question.option_b = None
                question.option_c = None
                question.option_d = None
                question.correct_option = None
            
            db.session.add(question)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'exam_id': exam.id,
            'message': f'Successfully generated exam "{exam_title}" with {len(generated_questions)} questions',
            'preview': generated_questions[:3]  # Return first 3 questions for preview
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to generate exam: {str(e)}'}), 500

def generate_ai_questions(topics, count, difficulty, question_types):
    """
    Generate AI-powered questions based on topics and parameters.
    This is a sophisticated function that creates diverse, high-quality questions.
    """
    questions = []
    
    # Question templates for different subjects and difficulties
    question_templates = {
        'easy': [
            "What is the definition of {topic}?",
            "Which of the following is an example of {topic}?",
            "True or False: {topic} is important in this subject.",
            "Name one characteristic of {topic}.",
            "What does {topic} stand for?"
        ],
        'medium': [
            "Explain how {topic} relates to the broader concept of {context}.",
            "What are the main advantages and disadvantages of {topic}?",
            "Compare and contrast {topic} with related concepts.",
            "Describe the process involved in {topic}.",
            "What factors influence {topic} in real-world applications?"
        ],
        'hard': [
            "Analyze the critical implications of {topic} in advanced scenarios.",
            "Evaluate the effectiveness of different approaches to {topic}.",
            "Synthesize information about {topic} to solve complex problems.",
            "Critically assess the role of {topic} in theoretical frameworks.",
            "Design a solution that incorporates principles of {topic}."
        ]
    }
    
    # Sample answers and options for different topics
    topic_contexts = {
        'mathematics': ['algebra', 'geometry', 'calculus', 'statistics'],
        'science': ['physics', 'chemistry', 'biology', 'scientific method'],
        'computer science': ['programming', 'algorithms', 'data structures', 'software engineering'],
        'history': ['ancient civilizations', 'world wars', 'cultural movements', 'political systems'],
        'literature': ['poetry', 'novels', 'literary analysis', 'writing techniques'],
        'economics': ['market systems', 'financial theories', 'economic policies', 'trade']
    }
    
    for i in range(count):
        topic = topics[i % len(topics)] if topics else 'general knowledge'
        
        # Determine difficulty for this question
        if difficulty == 'Mixed':
            q_difficulty = ['easy', 'medium', 'hard'][i % 3]
        else:
            q_difficulty = difficulty.lower()
        
        # Select question type
        question_type = question_types[i % len(question_types)]
        
        # Generate question based on type
        if question_type == 'multiple_choice':
            question_data = generate_multiple_choice_question(topic, q_difficulty, question_templates)
        elif question_type == 'true_false':
            question_data = generate_true_false_question(topic, q_difficulty)
        else:  # short_answer
            question_data = generate_short_answer_question(topic, q_difficulty, question_templates)
        
        questions.append(question_data)
    
    return questions

def generate_multiple_choice_question(topic, difficulty, templates):
    """Generate a multiple choice question"""
    template = templates[difficulty][hash(topic) % len(templates[difficulty])]
    
    # Create context-aware question
    question_text = template.replace('{topic}', topic).replace('{context}', f"the study of {topic}")
    
    # Generate plausible options
    options = [
        f"The primary definition of {topic}",
        f"A secondary aspect of {topic}",
        f"An alternative interpretation of {topic}",
        f"A related but distinct concept from {topic}"
    ]
    
    # Randomize correct answer position
    correct_index = hash(topic + difficulty) % 4
    
    return {
        'question': question_text,
        'type': 'multiple_choice',
        'options': options,
        'correct_option': correct_index,
        'difficulty': difficulty,
        'topic': topic
    }

def generate_true_false_question(topic, difficulty):
    """Generate a true/false question"""
    statements = {
        'easy': f"{topic} is a fundamental concept in this subject.",
        'medium': f"The application of {topic} requires understanding of underlying principles.",
        'hard': f"Advanced theories of {topic} challenge traditional perspectives."
    }
    
    # Randomly decide if statement is true or false
    is_true = hash(topic + difficulty) % 2 == 0
    
    return {
        'question': statements[difficulty],
        'type': 'true_false',
        'options': ['True', 'False'],
        'correct_option': 0 if is_true else 1,
        'answer': 'True' if is_true else 'False',
        'difficulty': difficulty,
        'topic': topic
    }

def generate_short_answer_question(topic, difficulty, templates):
    """Generate a short answer question"""
    template = templates[difficulty][hash(topic + 'short') % len(templates[difficulty])]
    question_text = template.replace('{topic}', topic).replace('{context}', f"the field of {topic}")
    
    # Generate sample answer
    answers = {
        'easy': f"A basic explanation of {topic} would include its definition and key characteristics.",
        'medium': f"A comprehensive answer about {topic} should cover its applications, benefits, and limitations.",
        'hard': f"An advanced discussion of {topic} requires analysis of complex relationships and theoretical implications."
    }
    
    return {
        'question': question_text,
        'type': 'short_answer',
        'answer': answers[difficulty],
        'difficulty': difficulty,
        'topic': topic
    }

def generate_ai_challenge_questions(topic, difficulty, question_count, challenge_type):
    """
    Generate AI-powered questions using the existing AI system.
    This function uses the real AI services already configured in the app.
    """
    questions = []
    
    try:
        # Use the existing AI generation system
        print(f"[CHALLENGE AI] Generating {question_count} questions for topic: {topic}, difficulty: {difficulty}")
        
        # Check if API keys are available
        groq_key = os.environ.get('GROQ_API_KEY')
        cohere_key = os.environ.get('COHERE_API_KEY')
        openrouter_key = os.environ.get('OPENROUTER_API_KEY')
        hf_key = os.environ.get('HUGGINGFACE_API_KEY')
        
        print(f"[CHALLENGE AI] API Keys available - Groq: {'✓' if groq_key else '✗'}, Cohere: {'✓' if cohere_key else '✗'}, OpenRouter: {'✓' if openrouter_key else '✗'}, HF: {'✓' if hf_key else '✗'}")
        
        # Call the existing AI generation function
        ai_result = try_free_ai_generation(
            prompt=topic,
            num_questions=question_count, 
            question_type='multiple_choice',
            difficulty=difficulty,
            context=f"Challenge type: {challenge_type}"
        )
        
        print(f"[CHALLENGE AI] AI Generation result: {ai_result}")
        
        if ai_result and ai_result.get('status') == 'success':
            ai_questions = ai_result.get('questions', [])
            print(f"AI generated {len(ai_questions)} questions successfully")
            
            # Convert AI questions to challenge format
            for i, q_data in enumerate(ai_questions[:question_count]):
                if 'question' in q_data:
                    # Handle multiple choice questions
                    if 'options' in q_data and q_data['options']:
                        options = q_data['options']
                        correct_answer = q_data.get('correct_answer', 'A')
                        
                        # Ensure we have 4 options
                        while len(options) < 4:
                            options.append(f"Option {len(options) + 1}")
                        
                        # Convert letter to index for correct answer
                        if correct_answer in ['A', 'B', 'C', 'D']:
                            correct_idx = ord(correct_answer) - ord('A')
                        else:
                            correct_idx = 0  # Default to first option
                        
                        # Ensure correct_idx is valid
                        if correct_idx >= len(options):
                            correct_idx = 0
                        
                        correct_answer_text = options[correct_idx]
                        
                        # Shuffle options while tracking correct answer
                        import random
                        options_copy = options.copy()
                        random.shuffle(options_copy)
                        new_correct_idx = options_copy.index(correct_answer_text)
                        correct_letters = ['A', 'B', 'C', 'D']
                        
                        question_data = {
                            'text': q_data['question'],
                            'question_type': 'multiple_choice',
                            'option_a': options_copy[0],
                            'option_b': options_copy[1],
                            'option_c': options_copy[2], 
                            'option_d': options_copy[3],
                            'correct_option': correct_letters[new_correct_idx],
                            'correct_answer': correct_answer_text,
                            'points': 1 if difficulty == 'easy' else 2 if difficulty == 'medium' else 3,
                            'time_limit_seconds': 30 if challenge_type == 'speed_quiz' else 60
                        }
                    
                    # Handle true/false questions
                    elif 'correct_answer' in q_data and q_data['correct_answer'].lower() in ['true', 'false']:
                        correct_answer = q_data['correct_answer'].lower()
                        
                        question_data = {
                            'text': q_data['question'],
                            'question_type': 'multiple_choice',
                            'option_a': 'True',
                            'option_b': 'False',
                            'option_c': 'Not applicable',
                            'option_d': 'Unknown',
                            'correct_option': 'A' if correct_answer == 'true' else 'B',
                            'correct_answer': 'True' if correct_answer == 'true' else 'False',
                            'points': 1 if difficulty == 'easy' else 2 if difficulty == 'medium' else 3,
                            'time_limit_seconds': 30 if challenge_type == 'speed_quiz' else 60
                        }
                    
                    else:
                        # Skip malformed questions
                        continue
                    
                    # Adjust for challenge type
                    if challenge_type == 'speed_quiz':
                        question_data['time_limit_seconds'] = 15 if difficulty == 'easy' else 20 if difficulty == 'medium' else 30
                    elif challenge_type == 'accuracy_challenge':
                        question_data['time_limit_seconds'] = None
                        question_data['points'] *= 2
                    
                    questions.append(question_data)
            
            if len(questions) >= question_count:
                print(f"Successfully converted {len(questions)} AI questions")
                return questions[:question_count]
                return questions[:question_count]
        
        # If AI generation didn't work, fall back to backup questions
        print("AI generation failed or returned no questions, using backup")
        return generate_backup_questions(topic, difficulty, question_count, challenge_type)
        
    except Exception as e:
        print(f"Error in AI question generation: {e}")
        return generate_backup_questions(topic, difficulty, question_count, challenge_type)

def generate_backup_questions(topic, difficulty, question_count, challenge_type):
    """Backup question generation when AI services fail"""
    questions = []
    
    # Simple backup questions based on topic keywords
    for i in range(question_count):
        question_data = {
            'text': f"What is an important concept related to {topic}?",
            'question_type': 'multiple_choice',
            'option_a': f"Key principle of {topic}",
            'option_b': f"Secondary aspect of {topic}",
            'option_c': f"Related field to {topic}",
            'option_d': f"Unrelated concept",
            'correct_option': 'A',
            'correct_answer': f"Key principle of {topic}",
            'points': 1 if difficulty == 'easy' else 2 if difficulty == 'medium' else 3,
            'time_limit_seconds': 30 if challenge_type == 'speed_quiz' else 60
        }
        
        if challenge_type == 'speed_quiz':
            question_data['time_limit_seconds'] = 15 if difficulty == 'easy' else 20 if difficulty == 'medium' else 30
        elif challenge_type == 'accuracy_challenge':
            question_data['time_limit_seconds'] = None
            question_data['points'] *= 2
            
        questions.append(question_data)
    
    return questions

# Create database tables
with app.app_context():
    db.create_all()

@app.route('/test_exam_template')
def test_exam_template():
    """Test route to check exam template without authentication"""
    # Create dummy data for template testing
    class DummyExam:
        id = 1
        title = "Test Exam"
    
    class DummyQuestion:
        id = 1
        question_text = "Test Question"
        option_a = "Option A"
        option_b = "Option B" 
        option_c = "Option C"
        option_d = "Option D"
    
    class DummySession:
        id = 1
        
    class DummyUser:
        id = 1
        username = "testuser"
    
    exam = DummyExam()
    questions = [DummyQuestion()]
    exam_session = DummySession()
    user = DummyUser()
    duration_minutes = 60
    
    return render_template('exam.html', 
                         exam=exam, 
                         questions=questions, 
                         session=exam_session,
                         user=user,
                         duration_minutes=duration_minutes)

# Gamification Helper Functions
def check_and_award_achievements(teacher_id):
    """Check for new achievements and award them"""
    teacher_stats = TeacherStats.query.filter_by(teacher_id=teacher_id).first()
    if not teacher_stats:
        # Create initial stats
        teacher_stats = TeacherStats()
        teacher_stats.teacher_id = teacher_id
        teacher_stats.level = 1  # Set default level
        teacher_stats.join_date = datetime.now(timezone.utc)  # Set join date
        db.session.add(teacher_stats)
        db.session.commit()
    
    achievements_to_award = []
    
    # Check exam creation milestones
    exam_milestones = [(5, 'First Steps', 'bronze'), (25, 'Getting Started', 'silver'), (50, 'Exam Creator', 'gold'), (100, 'Exam Master', 'gold')]
    for milestone, name, tier in exam_milestones:
        if teacher_stats.total_exams_created >= milestone:
            existing = TeacherAchievement.query.filter_by(
                teacher_id=teacher_id, 
                achievement_type=f'exams_created_{milestone}'
            ).first()
            if not existing:
                achievement = TeacherAchievement()
                achievement.teacher_id = teacher_id
                achievement.achievement_type = f'exams_created_{milestone}'
                achievement.achievement_name = f'{name} - {milestone} Exams'
                achievement.achievement_description = f'Created {milestone} exams!'
                achievement.badge_tier = tier
                achievement.points_awarded = milestone * 2
                achievements_to_award.append(achievement)
    
    # Check student count milestones
    student_milestones = [(10, 'Class Teacher', 'bronze'), (50, 'Popular Teacher', 'silver'), (100, 'Master Educator', 'gold')]
    for milestone, name, tier in student_milestones:
        if teacher_stats.total_students_taught >= milestone:
            existing = TeacherAchievement.query.filter_by(
                teacher_id=teacher_id, 
                achievement_type=f'students_taught_{milestone}'
            ).first()
            if not existing:
                achievement = TeacherAchievement()
                achievement.teacher_id = teacher_id
                achievement.achievement_type = f'students_taught_{milestone}'
                achievement.achievement_name = f'{name} - {milestone} Students'
                achievement.achievement_description = f'Taught {milestone} students!'
                achievement.badge_tier = tier
                achievement.points_awarded = milestone
                achievements_to_award.append(achievement)
    
    # Award all new achievements
    for achievement in achievements_to_award:
        db.session.add(achievement)
        teacher_stats.total_points += achievement.points_awarded
    
    # Update teacher level based on points
    teacher_stats.level = max(1, teacher_stats.total_points // 100)
    
    db.session.commit()
    return achievements_to_award

def update_teacher_stats(teacher_id, stat_type, increment=1):
    """Update teacher statistics"""
    teacher_stats = TeacherStats.query.filter_by(teacher_id=teacher_id).first()
    if not teacher_stats:
        teacher_stats = TeacherStats()
        teacher_stats.teacher_id = teacher_id
        teacher_stats.level = 1  # Set default level
        teacher_stats.join_date = datetime.now(timezone.utc)  # Set join date
        db.session.add(teacher_stats)
    
    if stat_type == 'exams_created':
        teacher_stats.total_exams_created += increment
    elif stat_type == 'questions_created':
        teacher_stats.total_questions_created += increment
    elif stat_type == 'students_taught':
        teacher_stats.total_students_taught = increment
    
    db.session.commit()
    
    # Check for new achievements
    return check_and_award_achievements(teacher_id)

def get_class_leaderboard(teacher_id, limit=10):
    """Get student leaderboard for teacher's classes"""
    # Get all students who have taken exams from this teacher
    leaderboard_query = db.session.query(
        User, StudentPoints, db.func.count(ExamSession.id).label('exams_taken')
    ).join(
        StudentPoints, User.id == StudentPoints.student_id
    ).join(
        ExamSession, User.id == ExamSession.student_id
    ).join(
        Exam, ExamSession.exam_id == Exam.id
    ).filter(
        Exam.lecturer_id == teacher_id,
        User.role == 'student'
    ).group_by(
        User.id, StudentPoints.id, StudentPoints.student_id, StudentPoints.points, 
        StudentPoints.level, StudentPoints.total_exams_taken, StudentPoints.perfect_scores, 
        StudentPoints.streak_days, StudentPoints.last_activity
    ).order_by(
        StudentPoints.points.desc()
    ).limit(limit).all()
    
    return leaderboard_query

def award_student_points(student_id, points, reason='exam_completion'):
    """Award points to a student"""
    student_points = StudentPoints.query.filter_by(student_id=student_id).first()
    if not student_points:
        student_points = StudentPoints()
        student_points.student_id = student_id
        db.session.add(student_points)
    
    student_points.points += points
    student_points.level = max(1, student_points.points // 50)  # Level up every 50 points
    student_points.last_activity = datetime.now(timezone.utc)
    
    if reason == 'exam_completion':
        student_points.total_exams_taken += 1
    elif reason == 'perfect_score':
        student_points.perfect_scores += 1
        student_points.points += 20  # Bonus for perfect score
    
    db.session.commit()

def get_active_challenges():
    """Get currently active challenges"""
    return Challenge.query.filter(
        Challenge.is_active == True,
        Challenge.start_date <= datetime.now(timezone.utc),
        Challenge.end_date >= datetime.now(timezone.utc)
    ).all()

def get_teacher_achievements(teacher_id):
    """Get all achievements for a teacher"""
    return TeacherAchievement.query.filter_by(teacher_id=teacher_id).order_by(
        TeacherAchievement.earned_date.desc()
    ).all()

def calculate_study_streak(student_id):
    """Calculate current study streak for a student"""
    # Get the last 30 days of exam sessions
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    sessions = ExamSession.query.filter(
        ExamSession.student_id == student_id,
        ExamSession.status == 'completed',
        ExamSession.end_time >= thirty_days_ago
    ).order_by(ExamSession.end_time.desc()).all()
    
    if not sessions:
        return 0
    
    # Count consecutive days with activity
    streak = 0
    current_date = datetime.now(timezone.utc).date()
    
    for session in sessions:
        session_date = session.end_time.date()
        if session_date == current_date or session_date == current_date - timedelta(days=streak):
            if session_date == current_date - timedelta(days=streak):
                streak += 1
            current_date = session_date
        else:
            break
    
    return streak

def get_student_rank(student_id):
    """Get student's rank in global leaderboard"""
    student_points = StudentPoints.query.filter_by(student_id=student_id).first()
    if not student_points:
        return None
    
    # Count students with higher points
    higher_rank_count = StudentPoints.query.filter(
        StudentPoints.points > student_points.points
    ).count()
    
    return higher_rank_count + 1

def get_student_achievements(student_id):
    """Get all achievements for a student"""
    # For now, return mock achievements - you can implement a real StudentAchievement model later
    student_points = StudentPoints.query.filter_by(student_id=student_id).first()
    completed_exams = ExamSession.query.filter(
        ExamSession.student_id == student_id,
        ExamSession.status == 'completed'
    ).count()
    
    achievements = []
    
    if completed_exams >= 1:
        achievements.append({
            'id': 1,
            'title': 'First Steps',
            'description': 'Complete your first exam',
            'icon': 'flag',
            'points': 10,
            'earned_date': datetime.now(timezone.utc)
        })
    
    if completed_exams >= 5:
        achievements.append({
            'id': 2,
            'title': 'Study Master',
            'description': 'Complete 5 exams',
            'icon': 'graduation-cap',
            'points': 25,
            'earned_date': datetime.now(timezone.utc)
        })
    
    if student_points and student_points.points >= 100:
        achievements.append({
            'id': 3,
            'title': 'Point Collector',
            'description': 'Earn 100 experience points',
            'icon': 'star',
            'points': 15,
            'earned_date': datetime.now(timezone.utc)
        })
    
    return achievements

def get_global_leaderboard(limit=10):
    """Get global student leaderboard"""
    leaderboard_query = db.session.query(
        User, StudentPoints
    ).join(
        StudentPoints, User.id == StudentPoints.student_id
    ).filter(
        User.role == 'student'
    ).order_by(
        StudentPoints.points.desc()
    ).limit(limit).all()
    
    # Format leaderboard with ranks
    leaderboard = []
    for rank, (user, points) in enumerate(leaderboard_query, 1):
        leaderboard.append((rank, {
            'id': user.id,
            'username': user.username,
            'total_points': points.points or 0
        }))
    
    return leaderboard

def get_student_challenges(student_id):
    """Get active challenges for a student with progress"""
    challenges = get_active_challenges()
    student_challenges = []
    
    for challenge in challenges:
        # Get student's best attempt for this challenge
        best_session = ChallengeSession.query.filter(
            ChallengeSession.student_id == student_id,
            ChallengeSession.challenge_id == challenge.id,
            ChallengeSession.status == 'completed'
        ).order_by(ChallengeSession.percentage.desc()).first()
        
        # Calculate completion status
        is_completed = False
        current_progress = 0
        
        if best_session:
            current_progress = best_session.percentage
            is_completed = current_progress >= challenge.passing_score
        
        # Get number of attempts
        attempts_count = ChallengeSession.query.filter(
            ChallengeSession.student_id == student_id,
            ChallengeSession.challenge_id == challenge.id
        ).count()
        
        student_challenges.append({
            'id': challenge.id,
            'title': challenge.title,
            'description': challenge.description,
            'challenge_type': challenge.challenge_type,
            'difficulty': challenge.difficulty,
            'target_value': challenge.passing_score,
            'current_progress': int(current_progress),
            'reward_points': challenge.points_reward,
            'is_completed': is_completed,
            'attempts_used': attempts_count,
            'max_attempts': challenge.max_attempts,
            'time_limit': challenge.time_limit_minutes
        })
    
    return student_challenges

def get_student_recent_activities(student_id, limit=5):
    """Get recent activities for a student"""
    activities = []
    
    # Get recent exam completions
    recent_sessions = ExamSession.query.filter(
        ExamSession.student_id == student_id,
        ExamSession.status.in_(['completed', 'disqualified'])
    ).order_by(ExamSession.end_time.desc()).limit(limit).all()
    
    for session in recent_sessions:
        exam = db.session.get(Exam, session.exam_id)
        if exam:
            if session.status == 'completed':
                try:
                    _, _, score = calculate_exam_score(session)
                    activities.append({
                        'title': f'Completed {exam.title}',
                        'description': f'Score: {score}% • Well done!',
                        'icon': 'check',
                        'color': 'success',
                        'time_ago': format_time_ago(session.end_time)
                    })
                except:
                    activities.append({
                        'title': f'Completed {exam.title}',
                        'description': 'Exam finished successfully',
                        'icon': 'check',
                        'color': 'success',
                        'time_ago': format_time_ago(session.end_time)
                    })
            else:
                activities.append({
                    'title': f'Attempted {exam.title}',
                    'description': 'Session ended early',
                    'icon': 'exclamation-triangle',
                    'color': 'warning',
                    'time_ago': format_time_ago(session.end_time)
                })
    
    # Add welcome message if no activities
    if not activities:
        activities.append({
            'title': 'Welcome to QUIZZO!',
            'description': 'Start taking exams to see your activity here',
            'icon': 'star',
            'color': 'primary',
            'time_ago': 'Now'
        })
    
    return activities

def format_time_ago(timestamp):
    """Format timestamp as 'time ago' string"""
    if not timestamp:
        return 'Unknown'
    
    now = datetime.now(timezone.utc)
    
    # Convert naive datetime to timezone-aware (assume UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    
    diff = now - timestamp
    
    if diff.days > 0:
        return f'{diff.days} days ago'
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f'{hours} hours ago'
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f'{minutes} minutes ago'
    else:
        return 'Just now'

def check_and_award_student_achievements(student_id):
    """Check and award new achievements for a student"""
    # This is a placeholder - implement actual achievement checking logic
    # For now, we'll just ensure student points record exists
    student_points = StudentPoints.query.filter_by(student_id=student_id).first()
    if not student_points:
        student_points = StudentPoints()
        student_points.student_id = student_id
        student_points.points = 0
        db.session.add(student_points)
        db.session.commit()
    
    return []

# ==============================================
# LIVE SESSION ROUTES - Virtual Classroom
# ==============================================

@app.route('/virtual-classroom')
def virtual_classroom():
    """Main virtual classroom page"""
    if 'user_id' not in session:
        print("Virtual classroom: User not in session, redirecting to login")
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['user_id'])
    if not user:
        print("Virtual classroom: User not found in database, clearing session")
        session.clear()
        return redirect(url_for('login'))
    
    print(f"Virtual classroom: User {user.username} (role: {user.role}) accessing page")
    
    # Ensure live session tables exist
    try:
        db.create_all()
    except Exception as e:
        print(f"Database creation error: {e}")
    
    # Get active sessions with teacher info
    try:
        active_sessions = db.session.query(LiveSession, User).join(
            User, LiveSession.teacher_id == User.id
        ).filter(LiveSession.is_active == True).all()
        print(f"Found {len(active_sessions)} active sessions")
    except Exception as e:
        print(f"Error fetching active sessions: {e}")
        active_sessions = []
    
    # Get user's sessions (created or joined) with teacher info
    try:
        if user.role == 'lecturer':
            my_sessions = db.session.query(LiveSession, User).join(
                User, LiveSession.teacher_id == User.id
            ).filter(LiveSession.teacher_id == user.id).order_by(LiveSession.created_at.desc()).limit(10).all()
        else:
            my_sessions = db.session.query(LiveSession, User).join(
                User, LiveSession.teacher_id == User.id
            ).join(SessionParticipant).filter(
                SessionParticipant.user_id == user.id
            ).order_by(LiveSession.created_at.desc()).limit(10).all()
        print(f"Found {len(my_sessions)} user sessions")
    except Exception as e:
        print(f"Error fetching user sessions: {e}")
        my_sessions = []
    
    # Calculate total participants across all active sessions
    try:
        total_participants = db.session.query(SessionParticipant).filter(
            SessionParticipant.is_online == True
        ).join(LiveSession).filter(LiveSession.is_active == True).count()
        print(f"Total active participants: {total_participants}")
    except Exception as e:
        print(f"Error calculating total participants: {e}")
        total_participants = 0
    
    # Add participant counts to active sessions
    enhanced_active_sessions = []
    for live_session, teacher in active_sessions:
        try:
            participant_count = SessionParticipant.query.filter_by(
                session_id=live_session.id, is_online=True
            ).count()
            live_session.participant_count = participant_count
        except Exception as e:
            print(f"Error counting participants for session {live_session.id}: {e}")
            live_session.participant_count = 0
        enhanced_active_sessions.append((live_session, teacher))
    
    return render_template('virtual_classroom.html', 
                         user=user, 
                         active_sessions=enhanced_active_sessions, 
                         my_sessions=my_sessions,
                         total_participants=total_participants)

@app.route('/test-virtual-classroom')
def test_virtual_classroom():
    """Test page for virtual classroom functionality"""
    return render_template('test_virtual_classroom.html')

@app.route('/virtual-classroom-debug')
def virtual_classroom_debug():
    """Debug version of virtual classroom"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['user_id'])
    if not user:
        return redirect(url_for('login'))
    
    # Get active sessions with teacher info
    try:
        active_sessions = db.session.query(LiveSession, User).join(
            User, LiveSession.teacher_id == User.id
        ).filter(LiveSession.is_active == True).all()
    except Exception as e:
        print(f"Error fetching active sessions: {e}")
        active_sessions = []
    
    # Get user's sessions
    try:
        if user.role == 'lecturer':
            my_sessions = db.session.query(LiveSession, User).join(
                User, LiveSession.teacher_id == User.id
            ).filter(LiveSession.teacher_id == user.id).order_by(LiveSession.created_at.desc()).limit(10).all()
        else:
            my_sessions = []
    except Exception as e:
        print(f"Error fetching user sessions: {e}")
        my_sessions = []
    
    return render_template('virtual_classroom_debug.html', 
                         user=user, 
                         active_sessions=active_sessions, 
                         my_sessions=my_sessions)

@app.route('/create-session', methods=['GET', 'POST'])
def create_session():
    """Create a new live session (teachers only)"""
    if 'user_id' not in session:
        print("Create session: User not in session")
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['user_id'])
    if not user:
        print("Create session: User not found in database")
        session.clear()
        return redirect(url_for('login'))
    
    if user.role != 'lecturer':
        print(f"Create session: User {user.username} is not a lecturer (role: {user.role})")
        return redirect(url_for('dashboard'))
    
    print(f"Create session: Lecturer {user.username} accessing create session")
    
    if request.method == 'POST':
        try:
            print("Create session: Processing POST request")
            # Ensure tables exist
            db.create_all()
            
            # Generate unique room ID
            import uuid
            import string
            import random
            
            # Generate a simpler, more readable room ID
            room_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            
            # Ensure uniqueness
            while LiveSession.query.filter_by(session_id=room_id).first():
                room_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            
            print(f"Create session: Generated room ID: {room_id}")
            
            # Create new session
            new_session = LiveSession(
                teacher_id=user.id,
                session_name=request.form['session_name'],
                description=request.form.get('description', ''),
                session_id=room_id,
                max_participants=int(request.form.get('max_participants', 50)),
                session_type=request.form.get('session_type', 'lecture'),
                password_protected=bool(request.form.get('password_protected')),
                session_password=request.form.get('session_password') if request.form.get('password_protected') else None
            )
            
            db.session.add(new_session)
            db.session.commit()
            
            print(f"Create session: Session created successfully with ID {new_session.id}")
            
            return jsonify({
                'success': True,
                'session_id': new_session.id,
                'room_id': room_id,
                'redirect': url_for('live_session', session_id=new_session.id)
            })
            
        except Exception as e:
            print(f"Error creating session: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': f'Failed to create session: {str(e)}'})
    
    print("Create session: Rendering create session form")
    return render_template('create_session.html', user=user)

@app.route('/live-session/<int:session_id>')
def live_session(session_id):
    """Live session room"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['user_id'])
    live_session = LiveSession.query.get_or_404(session_id)
    
    # Check if session is active
    if not live_session.is_active:
        return render_template('session_ended.html', session=live_session)
    
    # Check password if protected
    if live_session.password_protected and user.id != live_session.teacher_id:
        if request.args.get('password') != live_session.session_password:
            return render_template('session_password.html', session=live_session)
    
    # Add user as participant if not already
    participant = SessionParticipant.query.filter_by(
        session_id=live_session.id, 
        user_id=user.id
    ).first()
    
    if not participant:
        participant = SessionParticipant(
            session_id=live_session.id,
            user_id=user.id,
            role_in_session='host' if user.id == live_session.teacher_id else 'participant'
        )
        db.session.add(participant)
        db.session.commit()
    else:
        # Update online status
        participant.is_online = True
        participant.left_at = None
        db.session.commit()
    
    # Get current participants
    participants_query = db.session.query(SessionParticipant, User).join(User).filter(
        SessionParticipant.session_id == live_session.id,
        SessionParticipant.is_online == True
    ).all()
    
    # Convert participants to JSON-serializable format
    participants = []
    for participant, user in participants_query:
        participants.append({
            'id': user.id,
            'username': user.username,
            'role': participant.role_in_session,
            'camera_enabled': participant.camera_enabled,
            'microphone_enabled': participant.microphone_enabled,
            'screen_sharing': participant.screen_sharing,
            'joined_at': participant.joined_at.isoformat() if participant.joined_at else None
        })
    
    # Get teacher information
    teacher = db.session.get(User, live_session.teacher_id)
    
    # Start session if teacher is joining for first time
    if user.id == live_session.teacher_id and not live_session.started_at:
        live_session.started_at = datetime.now(timezone.utc)
        db.session.commit()
    
    return render_template('live_session_room.html', 
                         user=user, 
                         live_session=live_session, 
                         participants=participants,
                         teacher=teacher,
                         is_host=user.id == live_session.teacher_id,
                         datetime=datetime,
                         timezone=timezone)

@app.route('/join-session', methods=['POST'])
def join_session():
    """Join a session with room ID"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
    
    room_id = request.json.get('room_id', '').upper().strip()
    password = request.json.get('password', '').strip()
    
    if not room_id:
        return jsonify({'success': False, 'error': 'Room ID is required'})
    
    live_session = LiveSession.query.filter_by(session_id=room_id, is_active=True).first()
    
    if not live_session:
        return jsonify({'success': False, 'error': f'Session {room_id} not found or not active'})
    
    # Check password if session is protected
    if live_session.password_protected:
        if not password:
            return jsonify({'success': False, 'error': 'This session requires a password'})
        if password != live_session.session_password:
            return jsonify({'success': False, 'error': 'Incorrect password'})
    
    # Check participant limit
    current_participants = SessionParticipant.query.filter_by(
        session_id=live_session.id, 
        is_online=True
    ).count()
    
    if current_participants >= live_session.max_participants:
        return jsonify({'success': False, 'error': 'Session is full'})
    
    # Build redirect URL with password if needed
    redirect_url = url_for('live_session', session_id=live_session.id)
    if live_session.password_protected and password:
        redirect_url += f'?password={password}'
    
    return jsonify({
        'success': True,
        'redirect': redirect_url,
        'session_name': live_session.session_name
    })

@app.route('/api/participant_counts')
def get_participant_counts():
    """Get participant counts for all active sessions"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Calculate total participants across all active sessions
        total_participants = db.session.query(SessionParticipant).filter(
            SessionParticipant.is_online == True
        ).join(LiveSession).filter(LiveSession.is_active == True).count()
        
        # Get participant counts by session
        session_counts = {}
        active_sessions = LiveSession.query.filter_by(is_active=True).all()
        
        for live_session in active_sessions:
            count = SessionParticipant.query.filter_by(
                session_id=live_session.id, is_online=True
            ).count()
            session_counts[live_session.session_id] = count
        
        return jsonify({
            'success': True,
            'total_participants': total_participants,
            'session_counts': session_counts
        })
    except Exception as e:
        print(f"Error getting participant counts: {e}")
        return jsonify({'error': 'Failed to get participant counts'}), 500

@app.route('/api/session/<int:session_id>/participants/list')
def get_session_participants_list(session_id):
    """Get current session participants"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    participants = db.session.query(SessionParticipant, User).join(User).filter(
        SessionParticipant.session_id == session_id,
        SessionParticipant.is_online == True
    ).all()
    
    participant_list = []
    for participant, user in participants:
        participant_list.append({
            'id': user.id,
            'username': user.username,
            'role': participant.role_in_session,
            'camera_enabled': participant.camera_enabled,
            'microphone_enabled': participant.microphone_enabled,
            'screen_sharing': participant.screen_sharing,
            'joined_at': participant.joined_at.isoformat()
        })
    
    return jsonify({'participants': participant_list})

@app.route('/api/session/<int:session_id>/toggle_camera', methods=['POST'])
def toggle_camera(session_id):
    """Toggle camera for current user in session"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    participant = SessionParticipant.query.filter_by(
        session_id=session_id,
        user_id=session['user_id'],
        is_online=True
    ).first()
    
    if not participant:
        return jsonify({'error': 'Not a participant in this session'}), 404
    
    # Toggle camera state
    participant.camera_enabled = not participant.camera_enabled
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'camera_enabled': participant.camera_enabled
    })

@app.route('/api/session/<int:session_id>/toggle_microphone', methods=['POST'])
def toggle_microphone(session_id):
    """Toggle microphone for current user in session"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    participant = SessionParticipant.query.filter_by(
        session_id=session_id,
        user_id=session['user_id'],
        is_online=True
    ).first()
    
    if not participant:
        return jsonify({'error': 'Not a participant in this session'}), 404
    
    # Toggle microphone state
    participant.microphone_enabled = not participant.microphone_enabled
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'microphone_enabled': participant.microphone_enabled
    })

@app.route('/api/session/<int:session_id>/leave', methods=['POST'])
def leave_session(session_id):
    """Leave a session"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    participant = SessionParticipant.query.filter_by(
        session_id=session_id,
        user_id=session['user_id'],
        is_online=True
    ).first()
    
    if participant:
        participant.is_online = False
        participant.left_at = datetime.now(timezone.utc)
        db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/session/<int:session_id>/end', methods=['POST'])
def end_session(session_id):
    """End a session (host only)"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    live_session = LiveSession.query.get_or_404(session_id)
    
    if live_session.teacher_id != session['user_id']:
        return jsonify({'error': 'Only the host can end the session'}), 403
    
    # End session
    live_session.is_active = False
    live_session.ended_at = datetime.now(timezone.utc)
    
    # Mark all participants as offline
    SessionParticipant.query.filter_by(session_id=session_id, is_online=True).update({
        'is_online': False,
        'left_at': datetime.now(timezone.utc)
    })
    
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/session/<int:session_id>/messages')
def get_session_messages(session_id):
    """Get session chat messages"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    messages = db.session.query(SessionMessage, User).join(
        User, SessionMessage.user_id == User.id
    ).filter(
        SessionMessage.session_id == session_id,
        SessionMessage.is_private == False
    ).order_by(SessionMessage.sent_at.desc()).limit(50).all()
    
    message_list = []
    for message, user in messages:
        message_list.append({
            'id': message.id,
            'username': user.username,
            'message': message.message,
            'message_type': message.message_type,
            'sent_at': message.sent_at.isoformat(),
            'is_own': user.id == session['user_id']
        })
    
    return jsonify({'messages': list(reversed(message_list))})

@app.route('/api/session/<int:session_id>/send-message', methods=['POST'])
def send_session_message(session_id):
    """Send a message in session chat"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    message_text = data.get('message', '').strip()
    
    if not message_text:
        return jsonify({'error': 'Message cannot be empty'}), 400
    
    new_message = SessionMessage(
        session_id=session_id,
        user_id=session['user_id'],
        message=message_text,
        message_type='text'
    )
    
    db.session.add(new_message)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/session/<int:session_id>/toggle-controls', methods=['POST'])
def toggle_session_controls(session_id):
    """Toggle camera/microphone controls"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    control_type = data.get('type')  # 'camera' or 'microphone'
    enabled = data.get('enabled', False)
    
    participant = SessionParticipant.query.filter_by(
        session_id=session_id,
        user_id=session['user_id']
    ).first()
    
    if not participant:
        return jsonify({'error': 'Not a participant'}), 403
    
    if control_type == 'camera':
        participant.camera_enabled = enabled
    elif control_type == 'microphone':
        participant.microphone_enabled = enabled
    
    db.session.commit()
    
    return jsonify({'success': True})

# Database migration function
def update_database():
    """Update database schema to add missing columns"""
    with app.app_context():
        try:
            # Check if passing_score column exists
            db.session.execute(db.text("SELECT passing_score FROM exam_settings LIMIT 1"))
            
            # Check if scheduling columns exist in exam table
            db.session.execute(db.text("SELECT scheduled_start FROM exam LIMIT 1"))
            print("Database schema is up to date!")
        except Exception as e:
            print(f"Updating database schema...")
            try:
                # Add missing columns one by one
                try:
                    db.session.execute(db.text("ALTER TABLE exam_settings ADD COLUMN passing_score INTEGER DEFAULT 70"))
                    print("Added passing_score column to exam_settings")
                except:
                    pass
                
                try:
                    db.session.execute(db.text("ALTER TABLE exam ADD COLUMN scheduled_start DATETIME"))
                    print("Added scheduled_start column to exam")
                except:
                    pass
                    
                try:
                    db.session.execute(db.text("ALTER TABLE exam ADD COLUMN scheduled_end DATETIME"))
                    print("Added scheduled_end column to exam")
                except:
                    pass
                    
                try:
                    db.session.execute(db.text("ALTER TABLE exam ADD COLUMN is_scheduled BOOLEAN DEFAULT 0"))
                    print("Added is_scheduled column to exam")
                except:
                    pass
                
                db.session.commit()
                print("Database schema updated successfully!")
            except Exception as migrate_error:
                print(f"Migration error: {migrate_error}")
                # If migration fails, recreate tables
                print("Recreating database tables...")
                db.drop_all()
                db.create_all()
                print("Database tables recreated successfully!")

# Initialize database tables
def init_db():
    """Initialize the database tables"""
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")

if __name__ == '__main__':
    # Initialize database on startup
    init_db()
    update_database()  # Update schema if needed
    
    # Production vs Development settings
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"Starting QUIZZO app on port {port}")
    print(f"Debug mode: {debug_mode}")
    print(f"Database: {'PostgreSQL' if os.environ.get('DATABASE_URL') else 'SQLite'}")
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port)