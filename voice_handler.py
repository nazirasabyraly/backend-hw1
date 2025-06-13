import speech_recognition as sr
from gtts import gTTS
import tempfile
import os
from openai import OpenAI
from dotenv import load_dotenv
import logging
from pydub import AudioSegment
import io

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

class VoiceHandler:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        logger.info("VoiceHandler initialized")

    def speech_to_text(self, audio_data):
        """Convert speech to text using Google Speech Recognition"""
        try:
            logger.info("Starting speech to text conversion")
            
            # Convert WebM to WAV using pydub
            logger.info("Converting WebM to WAV")
            audio = AudioSegment.from_file(io.BytesIO(audio_data), format="webm")
            
            # Save to temporary WAV file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
                audio.export(temp_audio.name, format="wav")
                temp_audio_path = temp_audio.name
                logger.info(f"Saved audio to temporary file: {temp_audio_path}")

            # Use speech recognition
            with sr.AudioFile(temp_audio_path) as source:
                logger.info("Reading audio file")
                audio = self.recognizer.record(source)
                logger.info("Recognizing speech")
                text = self.recognizer.recognize_google(audio)
                logger.info(f"Recognized text: {text}")
            
            # Clean up temporary file
            os.unlink(temp_audio_path)
            logger.info("Temporary file cleaned up")
            return text
        except Exception as e:
            logger.error(f"Error in speech recognition: {str(e)}")
            return f"Error in speech recognition: {str(e)}"

    def text_to_speech(self, text):
        """Convert text to speech using gTTS"""
        try:
            logger.info("Starting text to speech conversion")
            # Create a temporary file for the audio
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_audio:
                # Generate speech
                logger.info("Generating speech")
                tts = gTTS(text=text, lang='en')
                tts.save(temp_audio.name)
                logger.info(f"Speech saved to: {temp_audio.name}")
                
                # Read the audio file
                with open(temp_audio.name, 'rb') as audio_file:
                    audio_data = audio_file.read()
                    logger.info("Audio file read successfully")
                
                # Clean up temporary file
                os.unlink(temp_audio.name)
                logger.info("Temporary file cleaned up")
                return audio_data
        except Exception as e:
            logger.error(f"Error in text to speech: {str(e)}")
            return None

    def get_ai_response(self, text):
        """Get response from OpenAI"""
        try:
            logger.info("Getting AI response")
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Keep your responses concise and clear."},
                    {"role": "user", "content": text}
                ]
            )
            ai_response = response.choices[0].message.content
            logger.info(f"AI response received: {ai_response}")
            return ai_response
        except Exception as e:
            logger.error(f"Error getting AI response: {str(e)}")
            return f"Error getting AI response: {str(e)}"

voice_handler = VoiceHandler() 