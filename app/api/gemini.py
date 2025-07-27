import google.generativeai as genai
from google import genai as genai_new  # For TTS functionality
from google.genai import types
from flask import request, jsonify, current_app, send_file
from app.api import bp
from app.auth.decorators import requires_auth
import wave
import tempfile
import os

def configure_gemini():
    genai.configure(api_key=current_app.config['GEMINI_API_KEY'])
    return genai.GenerativeModel('gemini-2.0-flash')

def configure_gemini_tts():
    """Configure Gemini client for TTS functionality"""
    return genai_new.Client(api_key=current_app.config['GEMINI_API_KEY'])

def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
    """Helper function to save wave file"""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width) 
        wf.setframerate(rate)
        wf.writeframes(pcm)

@bp.route('/chat', methods=['POST'])
@requires_auth
def chat():
    try:
        data = request.get_json()
        message = data.get('message', '')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        model = configure_gemini()
        response = model.generate_content(message)
        
        return jsonify({
            'response': response.text,
            'status': 'success'
        })
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@bp.route('/generate', methods=['POST'])
@requires_auth
def generate():
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        
        model = configure_gemini()
        response = model.generate_content(prompt)
        
        return jsonify({
            'generated_text': response.text,
            'status': 'success'
        })
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@bp.route('/generate-speech', methods=['POST'])
@requires_auth
def generate_speech():
    """Generate speech from text using Gemini TTS"""
    try:
        data = request.get_json()
        text = data.get('text', '')
        voice_name = data.get('voice', 'Kore')  # Allow voice selection
        
        if not text:
            return jsonify({'error': 'Text is required'}), 400
        
        # Initialize Gemini TTS client
        client = configure_gemini_tts()
        
        # Generate speech
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=f"Say cheerfully: {text}",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_name,
                        )
                    )
                ),
            )
        )
        
        # Get audio data
        audio_data = response.candidates[0].content.parts[0].inline_data.data
        
        # Create temporary wav file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav', dir=tempfile.gettempdir())
        wave_file(temp_file.name, audio_data)
        
        return send_file(
            temp_file.name, 
            as_attachment=True, 
            download_name='speech.wav',
            mimetype='audio/wav'
        )
        
    except Exception as e:
        current_app.logger.error(f"TTS Error: {str(e)}")
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@bp.route('/voices', methods=['GET'])
@requires_auth
def get_available_voices():
    """Get list of available TTS voices"""
    try:
        # Available voices for Gemini TTS
        voices = [
            {'name': 'Kore', 'description': 'Default cheerful voice'},
            {'name': 'Charon', 'description': 'Alternative voice option'},
            # Add more voices as they become available
        ]
        
        return jsonify({
            'voices': voices,
            'status': 'success'
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@bp.route('/chat-with-speech', methods=['POST'])
@requires_auth
def chat_with_speech():
    """Chat with Gemini and optionally generate speech response"""
    try:
        data = request.get_json()
        message = data.get('message', '')
        generate_audio = data.get('generate_audio', False)
        voice_name = data.get('voice', 'Kore')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Generate text response
        model = configure_gemini()
        response = model.generate_content(message)
        
        result = {
            'response': response.text,
            'status': 'success'
        }
        
        # Optionally generate speech
        if generate_audio:
            try:
                client = configure_gemini_tts()
                
                speech_response = client.models.generate_content(
                    model="gemini-2.5-flash-preview-tts",
                    contents=f"Say cheerfully: {response.text}",
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=voice_name,
                                )
                            )
                        ),
                    )
                )
                
                # Get audio data and encode as base64 for JSON response
                import base64
                audio_data = speech_response.candidates[0].content.parts[0].inline_data.data
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                
                result['audio'] = audio_base64
                result['audio_format'] = 'wav'
                
            except Exception as audio_error:
                current_app.logger.warning(f"Audio generation failed: {str(audio_error)}")
                result['audio_error'] = str(audio_error)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500