import os
import google.generativeai as genai
import speech_recognition as sr
from flask import Flask, render_template, request, jsonify, url_for
from gtts import gTTS
from pydub import AudioSegment # Import pydub
from dotenv import load_dotenv
import uuid # For generating unique filenames
import logging

# --- Basic Setup ---
load_dotenv() # Load environment variables from .env file
logging.basicConfig(level=logging.INFO) # Setup basic logging

app = Flask(__name__)
app.secret_key = os.urandom(24) # Needed for session management if used later

# Configure Google Gemini API
try:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables.")
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel('gemini-1.5-flash') # Or 'gemini-pro' etc.
    logging.info("Gemini API configured successfully.")
except Exception as e:
    logging.error(f"Error configuring Gemini API: {e}")
    # You might want to exit or provide a fallback mechanism here
    model = None

# Initialize Speech Recognizer
recognizer = sr.Recognizer()

# Store conversation history in memory (for simplicity)
# In a real app, use a database or more persistent storage per user session
conversation_history = []

# Ensure the static/audio directory exists
audio_dir = os.path.join('static', 'audio')
os.makedirs(audio_dir, exist_ok=True)

# --- Helper Functions ---

def text_to_speech(text, lang='en'):
    """Converts text to speech using gTTS and saves it as an MP3 file."""
    try:
        tts = gTTS(text=text, lang=lang)
        filename = f"{uuid.uuid4()}.mp3"
        filepath = os.path.join(audio_dir, filename)
        tts.save(filepath)
        # Return the URL path for the audio file
        return url_for('static', filename=f'audio/{filename}')
    except Exception as e:
        logging.error(f"Error in text_to_speech: {e}")
        return None

def speech_to_text(audio_file):
    """Converts an audio file to text using SpeechRecognition."""
    try:
        # Convert audio to WAV format if necessary (using pydub)
        # Browsers often send webm or ogg
        audio = AudioSegment.from_file(audio_file)
        # Increase volume slightly if needed (optional)
        # audio = audio + 6 # Increase volume by 6 dB
        wav_path = "temp_audio.wav"
        audio.export(wav_path, format="wav")

        with sr.AudioFile(wav_path) as source:
            # Adjust for ambient noise (optional but good practice)
            # recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio_data = recognizer.record(source)

        # Clean up temporary WAV file
        os.remove(wav_path)

        # Recognize speech using Google Web Speech API
        text = recognizer.recognize_google(audio_data)
        logging.info(f"Speech recognized: {text}")
        return text
    except sr.UnknownValueError:
        logging.warning("Google Speech Recognition could not understand audio")
        return None # Indicate recognition failure
    except sr.RequestError as e:
        logging.error(f"Could not request results from Google Speech Recognition service; {e}")
        return None # Indicate service error
    except Exception as e:
        logging.error(f"Error in speech_to_text: {e}")
        return None

def get_gemini_response(prompt):
    """Gets a response from the Gemini API."""
    if not model:
        return "Error: Chatbot model is not configured."
    try:
        # We'll use a simple prompt for now. For history, structure it properly.
        # Example for maintaining history:
        # history_formatted = [{"role": msg["role"], "parts": [msg["text"]]} for msg in conversation_history]
        # response = model.generate_content(history_formatted + [{"role": "user", "parts": [prompt]}])

        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logging.error(f"Error getting response from Gemini: {e}")
        return "Sorry, I encountered an error."

def get_gemini_summary(history):
    """Gets a summary from the Gemini API based on conversation history."""
    if not model:
        return "Error: Chatbot model is not configured."
    if not history:
        return "No conversation to summarize."

    try:
        # Format conversation for summarization prompt
        conversation_text = "\n".join([f"{msg['role'].capitalize()}: {msg['text']}" for msg in history])
        summary_prompt = f"Please summarize the following conversation concisely:\n\n{conversation_text}"

        response = model.generate_content(summary_prompt)
        return response.text
    except Exception as e:
        logging.error(f"Error getting summary from Gemini: {e}")
        return "Sorry, I couldn't summarize the conversation due to an error."


# --- Flask Routes ---

@app.route('/')
def index():
    """Renders the main chat page."""
    global conversation_history # Clear history for a new session (basic approach)
    conversation_history = []
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Handles text chat messages."""
    global conversation_history
    data = request.get_json()
    user_message = data.get('message')

    if not user_message:
        return jsonify({"error": "No message received"}), 400

    # Add user message to history
    conversation_history.append({"role": "user", "text": user_message})
    logging.info(f"User (text): {user_message}")

    # Get bot response from Gemini
    bot_response_text = get_gemini_response(user_message) # Pass only current msg for simple chat

    # Add bot response to history
    conversation_history.append({"role": "bot", "text": bot_response_text})
    logging.info(f"Bot response: {bot_response_text}")

    # Generate speech for the bot response
    audio_url = text_to_speech(bot_response_text)

    return jsonify({
        "user_message": user_message,
        "bot_response": bot_response_text,
        "audio_url": audio_url
    })

@app.route('/recognize', methods=['POST'])
def recognize_speech():
    """Handles speech input, converts to text, gets bot response, and returns both + TTS."""
    global conversation_history
    if 'audio_data' not in request.files:
        return jsonify({"error": "No audio file part"}), 400

    audio_file = request.files['audio_data']

    if audio_file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Process speech to text
    recognized_text = speech_to_text(audio_file)

    if recognized_text is None:
        # Failed to recognize - maybe return an error message or a default prompt?
        failed_text = "Sorry, I couldn't understand the audio."
        audio_url = text_to_speech(failed_text)
        return jsonify({
             "recognized_text": "[Audio not recognized]", # Indicate failure
             "bot_response": failed_text,
             "audio_url": audio_url
             }), 200 # Return 200 OK, but with error details in payload

    # Add recognized user message to history
    conversation_history.append({"role": "user", "text": recognized_text})
    logging.info(f"User (speech): {recognized_text}")

    # Get bot response from Gemini using the recognized text
    bot_response_text = get_gemini_response(recognized_text)

    # Add bot response to history
    conversation_history.append({"role": "bot", "text": bot_response_text})
    logging.info(f"Bot response: {bot_response_text}")

    # Generate speech for the bot response
    audio_url = text_to_speech(bot_response_text)

    return jsonify({
        "recognized_text": recognized_text, # Send back the recognized text
        "bot_response": bot_response_text,
        "audio_url": audio_url
    })


@app.route('/summarize', methods=['GET'])
def summarize():
    """Summarizes the current conversation."""
    global conversation_history
    logging.info("Summarize request received.")

    summary_text = get_gemini_summary(conversation_history)
    logging.info(f"Summary: {summary_text}")

    audio_url = text_to_speech(summary_text)

    # Add summary action to history (optional)
    # conversation_history.append({"role": "system", "text": f"[Summarized conversation: {summary_text}]"})

    return jsonify({
        "summary": summary_text,
        "audio_url": audio_url
        })


# --- Run Application ---
if __name__ == '__main__':
    # Make sure to set debug=False in a production environment!
    app.run(debug=True, host='0.0.0.0', port=5000) # Run on port 5000 accessible on network