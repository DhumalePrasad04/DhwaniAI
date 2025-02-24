import os
import requests
from flask import Flask, request, Response, send_file
from twilio.twiml.voice_response import VoiceResponse, Gather
import whisper
import ollama
from TTS.api import TTS
from pyngrok import ngrok
import time

# Twilio Credentials (Replace with your Twilio details)
import os
from dotenv import load_dotenv
load_dotenv()  # Load variables from .env
TWILIO_ACCOUNT_SID = os.getenv("sid")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")


# Flask App
app = Flask(__name__)

# Open Ngrok tunnel to expose Flask to the internet
public_url = ngrok.connect(5000).public_url
print(f"Public URL: {public_url}")

# Whisper Speech-to-Text Model
whisper_model = whisper.load_model("base")

# Coqui TTS Model
tts_model = TTS("tts_models/en/ljspeech/tacotron2-DDC")

# Function to generate AI response using Ollama
def get_ai_response(text):
    response = ollama.chat(model="llama3.2:1b", messages=[{"role": "user", "content": text}])
    return response["message"]["content"]

# Function to convert AI response to speech
def text_to_speech(text, filename="response.wav"):
    tts_model.tts_to_file(text=text, file_path=filename)

# Twilio Call Handling (Live Conversation)
@app.route("/incoming_call", methods=["POST"])
def handle_call():
    """Handles incoming Twilio calls and gathers user input via speech."""

    response = VoiceResponse()
    gather = Gather(input="speech", action=f"{public_url}/process_speech", timeout=5)
    gather.say("Hello! How can I help you?")
    response.append(gather)

    return Response(str(response), mimetype="text/xml")

# Process Speech & Generate AI Response
@app.route("/process_speech", methods=["POST"])
def process_speech():
    """Processes user speech input and responds using AI-generated speech."""

    user_text = request.form.get("SpeechResult", "")
    print(f"User said: {user_text}")

    if not user_text:
        return Response("<Response><Say>Sorry, I didn't catch that. Please try again.</Say></Response>", mimetype="text/xml")

    # Generate AI response
    ai_response = get_ai_response(user_text)
    print(f"AI Response: {ai_response}")

    # Convert AI response to speech
    text_to_speech(ai_response, "response.wav")

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
