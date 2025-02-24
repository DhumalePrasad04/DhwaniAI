import os
import requests
from flask import Flask, request, Response, send_file
from twilio.twiml.voice_response import VoiceResponse, Gather
import whisper
import ollama
from TTS.api import TTS
from pyngrok import ngrok
import time
from deep_translator import GoogleTranslator  # Importing for language translation

# Twilio Credentials (Replace with your Twilio details)
TWILIO_ACCOUNT_SID = "AC8c63cc6eb8a765630de0a185ad289f7b"
TWILIO_AUTH_TOKEN = "2b934e4dd3d410ef7702d4f88ac3f832"

# Flask App
app = Flask(__name__)

# Open Ngrok tunnel to expose Flask to the internet
public_url = ngrok.connect(5000).public_url
print(f"Public URL: {public_url}")

# Load Whisper Model for Speech-to-Text
whisper_model = whisper.load_model("base")

# Available Languages and Corresponding Models
LANGUAGES = {
    "1": {"name": "English", "whisper": "en", "tts": "tts_models/en/ljspeech/tacotron2-DDC"},
    "2": {"name": "Hindi", "whisper": "hi", "tts": "tts_models/hi/coqui/vits"},
    "3": {"name": "Kannada", "whisper": "kn", "tts": "tts_models/kn/coqui/vits"}
}

# Dictionary to Store Language Preferences for Each Caller
user_languages = {}

# Function to Generate AI Response Using Ollama
def get_ai_response(text, lang="en"):
    response = ollama.chat(model="llama3.2:1b", messages=[{"role": "user", "content": text}])
    return response["message"]["content"]

# Function to Convert AI Response to Speech
def text_to_speech(text, lang_code, filename="response.wav"):
    tts_model = TTS(LANGUAGES[lang_code]["tts"])
    tts_model.tts_to_file(text=text, file_path=filename)

# ----------------- New Feature: Language Selection -----------------
@app.route("/incoming_call", methods=["POST"])
def handle_call():
    """Handles incoming Twilio calls and prompts for language selection."""

    response = VoiceResponse()
    gather = Gather(numDigits=1, action=f"{public_url}/set_language")
    gather.say("Press 1 for English, Press 2 for Hindi, Press 3 for Kannada.")
    response.append(gather)

    return Response(str(response), mimetype="text/xml")

@app.route("/set_language", methods=["POST"])
def set_language():
    """Stores the user's selected language."""
    caller_id = request.form.get("From")
    digit = request.form.get("Digits", "1")  # Default to English

    if digit not in LANGUAGES:
        digit = "1"  # Default to English if invalid input

    user_languages[caller_id] = digit  # Store language preference
    response = VoiceResponse()
    response.say(f"You selected {LANGUAGES[digit]['name']}. Please speak after the beep.")

    gather = Gather(input="speech", action=f"{public_url}/process_speech", timeout=5, speechTimeout="auto")
    response.append(gather)

    return Response(str(response), mimetype="text/xml")

# ----------------- Speech Processing -----------------
@app.route("/process_speech", methods=["POST"])
def process_speech():
    """Processes user speech input and responds using AI-generated speech."""

    caller_id = request.form.get("From")
    audio_url = request.form.get("RecordingUrl")  # Get recorded audio URL

    if not audio_url:
        return Response("<Response><Say>Sorry, no audio received. Please try again.</Say></Response>", mimetype="text/xml")

    # Get User Language (Default to English)
    lang_code = user_languages.get(caller_id, "1")
    whisper_lang = LANGUAGES[lang_code]["whisper"]

    # Download Audio from Twilio
    audio_file = "user_audio.wav"
    try:
        audio_response = requests.get(audio_url)
        with open(audio_file, "wb") as f:
            f.write(audio_response.content)
    except Exception as e:
        return Response(f"<Response><Say>Failed to download audio. Error: {str(e)}</Say></Response>", mimetype="text/xml")

    # Verify Audio File Exists
    if not os.path.exists(audio_file):
        return Response("<Response><Say>Audio file not found. Please try again.</Say></Response>", mimetype="text/xml")

    # Speech Recognition
    try:
        transcribed_text = whisper_model.transcribe(audio_file, language=whisper_lang)["text"]
        print(f"User said ({LANGUAGES[lang_code]['name']}): {transcribed_text}")
    except Exception as e:
        return Response(f"<Response><Say>Speech processing failed. Error: {str(e)}</Say></Response>", mimetype="text/xml")

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
    try:
        text_to_speech(ai_response, lang_code, "response.wav")
    except Exception as e:
        return Response(f"<Response><Say>Failed to generate speech. Error: {str(e)}</Say></Response>", mimetype="text/xml")

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
