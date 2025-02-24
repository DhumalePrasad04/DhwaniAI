import os
import requests
from flask import Flask, request, Response, send_file
from twilio.twiml.voice_response import VoiceResponse, Gather
import whisper
import ollama
from TTS.api import TTS
from pyngrok import ngrok
import time
from deep_translator import GoogleTranslator  # For translation

# Twilio Credentials (Replace with your Twilio details)
TWILIO_ACCOUNT_SID = "AC8c63cc6eb8a765630de0a185ad289f7b"
TWILIO_AUTH_TOKEN = "2b934e4dd3d410ef7702d4f88ac3f832"

# Flask App
app = Flask(__name__)

# Open Ngrok tunnel to expose Flask to the internet
public_url = ngrok.connect(5000).public_url
print(f"Public URL: {public_url}")

# Load Whisper Model
whisper_model = whisper.load_model("base")

# Available Languages and TTS Models
LANGUAGES = {
    "1": {"name": "English", "whisper": "en", "tts": "tts_models/en/ljspeech/tacotron2-DDC"},
    "2": {"name": "Hindi", "whisper": "hi", "tts": "tts_models/hi/coqui/vits"},
    "3": {"name": "Kannada", "whisper": "kn", "tts": "tts_models/kn/coqui/vits"}
}
user_languages = {}  # Store language preference for each caller

# Function to generate AI response using Ollama
def get_ai_response(text, lang="en"):
    response = ollama.chat(model="llama3.2:1b", messages=[{"role": "user", "content": text}])
    return response["message"]["content"]

# Function to convert AI response to speech
def text_to_speech(text, lang_code, filename="response.wav"):
    tts_model = TTS(LANGUAGES[lang_code]["tts"])
    tts_model.tts_to_file(text=text, file_path=filename)

# Twilio Call Handling (Language Selection)
@app.route("/incoming_call", methods=["POST"])
def handle_call():
    """Handles incoming Twilio calls and asks the user to select a language."""
    response = VoiceResponse()
    gather = Gather(numDigits=1, action=f"{public_url}/set_language")
    gather.say("Press 1 for English, Press 2 for Hindi, Press 3 for Kannada.")
    response.append(gather)
    return Response(str(response), mimetype="text/xml")

# Set User Language
@app.route("/set_language", methods=["POST"])
def set_language():
    """Stores the user's selected language."""
    caller_id = request.form.get("From")
    digit = request.form.get("Digits", "1")  # Default to English

    if digit not in LANGUAGES:
        digit = "1"  # Default to English if invalid input

    user_languages[caller_id] = digit
    response = VoiceResponse()
    response.say(f"You selected {LANGUAGES[digit]['name']}. Please speak after the beep.")
    gather = Gather(input="speech", action=f"{public_url}/process_speech", timeout=5)
    response.append(gather)

    return Response(str(response), mimetype="text/xml")

# Process Speech & Generate AI Response
@app.route("/process_speech", methods=["POST"])
def process_speech():
    """Processes user speech input and responds using AI-generated speech."""
    caller_id = request.form.get("From")
    user_text = request.form.get("SpeechResult", "")

    if not user_text:
        return Response("<Response><Say>Sorry, I didn't catch that. Please try again.</Say></Response>", mimetype="text/xml")

    # Get User Language (Default to English)
    lang_code = user_languages.get(caller_id, "1")
    whisper_lang = LANGUAGES[lang_code]["whisper"]

    # Speech Recognition
    transcribed_text = whisper_model.transcribe(user_text, language=whisper_lang)["text"]
    print(f"User said ({LANGUAGES[lang_code]['name']}): {transcribed_text}")

    # Translate to English for AI processing if needed
    if whisper_lang != "en":
        transcribed_text = GoogleTranslator(source=whisper_lang, target="en").translate(transcribed_text)

    # Generate AI response
    ai_response = get_ai_response(transcribed_text)
    print(f"AI Response (English): {ai_response}")

    # Translate AI Response back to User's Language
    if whisper_lang != "en":
        ai_response = GoogleTranslator(source="en", target=whisper_lang).translate(ai_response)

    print(f"AI Response ({LANGUAGES[lang_code]['name']}): {ai_response}")

    # Convert AI response to speech
    text_to_speech(ai_response, lang_code, "response.wav")

    # Twilio Response with AI-generated speech
    response = VoiceResponse()
    response.play(f"{public_url}/response.wav")

    return Response(str(response), mimetype="text/xml")

# Serve AI-generated audio response
@app.route("/response.wav")
def serve_audio():
    return send_file("response.wav", mimetype="audio/wav", as_attachment=True)

if __name__ == "__main__":
    app.run(port=5000)
