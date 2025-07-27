import os
import json
import wave
from typing import List, Dict, Tuple
from google import genai
from google.genai import types
import google.generativeai as genai_text
from models import db, InterviewSession

# Global configuration - initialize once
def initialize_gemini_clients():
    """Initialize and return Gemini clients"""
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is required")
    
    # For text generation
    genai_text.configure(api_key=api_key)
    text_model = genai_text.GenerativeModel('gemini-1.5-flash')
    
    # For audio generation
    audio_client = genai.Client()
    
    return text_model, audio_client

def ensure_audio_directory():
    """Ensure audio directory exists"""
    audio_dir = os.path.join('static', 'audio', 'interviews')
    os.makedirs(audio_dir, exist_ok=True)
    return audio_dir

def generate_questions(text_model, resume_text: str, job_title: str, difficulty_level: str) -> List[str]:
    """
    Generate 5 interview questions based on resume, job title, and difficulty level.
    """
    
    # Define difficulty-specific instructions
    difficulty_prompts = {
        'easy': "Focus on basic concepts, fundamental skills, and general experience questions.",
        'medium': "Include both fundamental and intermediate-level questions with some scenario-based problems.",
        'hard': "Create challenging questions including complex scenarios, advanced technical concepts, and problem-solving situations."
    }
    
    prompt = f"""
    You are an expert interviewer tasked with creating interview questions for a {job_title} position.
    
    Candidate's Resume/Background:
    {resume_text}
    
    Job Title: {job_title}
    Difficulty Level: {difficulty_level}
    
    Instructions:
    - {difficulty_prompts.get(difficulty_level, difficulty_prompts['medium'])}
    - Generate exactly 5 interview questions 
    - Questions should be relevant to the job title and the candidate's background
    - Include a mix of behavioral, technical, and situational questions as appropriate
    - Make questions specific and engaging
    - Avoid generic questions - tailor them to the role and candidate's experience
    - Keep questions concise and clear for audio playback
    
    Return your response as a JSON array of exactly 5 questions, like this:
    ["Question 1", "Question 2", "Question 3", "Question 4", "Question 5"]
    
    Do not include any additional text or formatting - just the JSON array.
    """
    
    try:
        response = text_model.generate_content(prompt)
        questions_json = response.text.strip()
        
        # Parse the JSON response
        questions = json.loads(questions_json)
        
        # Validate we got exactly 5 questions
        if not isinstance(questions, list) or len(questions) != 5:
            raise ValueError(f"Expected 5 questions, got {len(questions) if isinstance(questions, list) else 'invalid format'}")
        
        return questions
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse Gemini response as JSON: {e}")
    except Exception as e:
        raise ValueError(f"Error generating questions with Gemini: {e}")

def create_audio_file(filename: str, pcm_data: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2):
    """Create a wave file from PCM data"""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm_data)

def generate_audio_for_question(audio_client, audio_dir: str, question_text: str, question_number: int, session_id: int) -> str:
    """
    Generate audio file for a single question
    Returns the filename of the generated audio file
    """
    try:
        # Prepare the audio prompt
        audio_prompt = f"Say this interview question in a professional, friendly tone: {question_text}"
        
        response = audio_client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=audio_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name='Kore',
                        )
                    )
                ),
            )
        )
        
        # Extract audio data
        audio_data = response.candidates[0].content.parts[0].inline_data.data
        
        # Create filename
        filename = f"session_{session_id}_question_{question_number}.wav"
        filepath = os.path.join(audio_dir, filename)
        
        # Save audio file
        create_audio_file(filepath, audio_data)
        
        return filename
        
    except Exception as e:
        print(f"Error generating audio for question {question_number}: {e}")
        return None

def generate_and_store_questions_with_audio(session_id: int) -> bool:
    """
    Generate questions for an interview session, store them in DB, and create audio files.
    
    Args:
        session_id: The ID of the InterviewSession
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Initialize clients and directory
        text_model, audio_client = initialize_gemini_clients()
        audio_dir = ensure_audio_directory()
        
        # Get the interview session
        session = InterviewSession.query.get(session_id)
        if not session:
            raise ValueError(f"Interview session with ID {session_id} not found")
        
        # Check if questions are already generated
        if session.get_question_count() > 1:
            print(f"Questions already generated for session {session_id}")
            return True
        
        # Step 1: Generate 5 questions using Gemini text API
        print(f"Generating questions for session {session_id}...")
        generated_questions = generate_questions(
            text_model,
            resume_text=session.resume_text_data,
            job_title=session.job_title,
            difficulty_level=session.difficulty_level
        )
        
        # Step 2: Prepare all questions (first one is "Tell me about yourself", then the 5 generated ones)
        all_questions = ["Tell me about yourself"] + generated_questions
        
        # Step 3: Update the session with all questions
        session.questions = all_questions
        db.session.commit()
        
        # Step 4: Generate audio files for all questions
        print(f"Generating audio files for {len(all_questions)} questions...")
        audio_files = []
        
        for i, question in enumerate(all_questions, 1):
            print(f"Generating audio for question {i}/{len(all_questions)}")
            audio_filename = generate_audio_for_question(
                audio_client, audio_dir, question, i, session_id
            )
            if audio_filename:
                audio_files.append(audio_filename)
            else:
                print(f"Failed to generate audio for question {i}")
        
        # Step 5: Store audio filenames in session (you might want to add this field to your model)
        # For now, we'll create a simple mapping
        audio_mapping = {
            f"question_{i}": filename for i, filename in enumerate(audio_files, 1)
        }
        
        # Update session status
        session.status = 'in_progress'
        db.session.commit()
        
        print(f"Successfully generated {len(generated_questions)} questions + 1 default question and {len(audio_files)} audio files for session {session_id}")
        print(f"Audio files: {audio_files}")
        
        return True
        
    except Exception as e:
        print(f"Error generating questions and audio for session {session_id}: {e}")
        db.session.rollback()
        return False

def get_audio_file_path(session_id: int, question_number: int) -> str:
    """Get the path to an audio file for a specific question"""
    audio_dir = ensure_audio_directory()
    filename = f"session_{session_id}_question_{question_number}.wav"
    return os.path.join(audio_dir, filename)

def get_all_audio_files(session_id: int) -> List[Dict[str, str]]:
    """Get all audio files for a session"""
    audio_dir = ensure_audio_directory()
    session = InterviewSession.query.get(session_id)
    if not session:
        return []
    
    audio_files = []
    question_count = session.get_question_count()
    
    for i in range(1, question_count + 1):
        filename = f"session_{session_id}_question_{i}.wav"
        filepath = os.path.join(audio_dir, filename)
        
        if os.path.exists(filepath):
            audio_files.append({
                'question_number': i,
                'question_text': session.questions[i-1] if session.questions else '',
                'audio_filename': filename,
                'audio_path': filepath,
                'audio_url': f'/static/audio/interviews/{filename}'
            })
    
    return audio_files

# Optional: If you want to maintain some state between calls, you can use module-level variables
_text_model = None
_audio_client = None
_audio_dir = None

def get_or_initialize_clients():
    """Get cached clients or initialize them if not already done"""
    global _text_model, _audio_client, _audio_dir
    
    if _text_model is None or _audio_client is None:
        _text_model, _audio_client = initialize_gemini_clients()
    
    if _audio_dir is None:
        _audio_dir = ensure_audio_directory()
    
    return _text_model, _audio_client, _audio_dir

def generate_and_store_questions_with_audio_cached(session_id: int) -> bool:
    """
    Alternative version that uses cached clients for better performance
    when calling multiple times
    """
    try:
        # Get cached clients
        text_model, audio_client, audio_dir = get_or_initialize_clients()
        
        # Get the interview session
        session = InterviewSession.query.get(session_id)
        if not session:
            raise ValueError(f"Interview session with ID {session_id} not found")
        
        # Check if questions are already generated
        if session.get_question_count() > 1:
            print(f"Questions already generated for session {session_id}")
            return True
        
        # Step 1: Generate 5 questions using Gemini text API
        print(f"Generating questions for session {session_id}...")
        generated_questions = generate_questions(
            text_model,
            resume_text=session.resume_text_data,
            job_title=session.job_title,
            difficulty_level=session.difficulty_level
        )
        
        # Step 2: Prepare all questions
        all_questions = ["Tell me about yourself"] + generated_questions
        
        # Step 3: Update the session with all questions
        session.questions = all_questions
        db.session.commit()
        
        # Step 4: Generate audio files for all questions
        print(f"Generating audio files for {len(all_questions)} questions...")
        audio_files = []
        
        for i, question in enumerate(all_questions, 1):
            print(f"Generating audio for question {i}/{len(all_questions)}")
            audio_filename = generate_audio_for_question(
                audio_client, audio_dir, question, i, session_id
            )
            if audio_filename:
                audio_files.append(audio_filename)
            else:
                print(f"Failed to generate audio for question {i}")
        
        # Update session status
        session.status = 'in_progress'
        db.session.commit()
        
        print(f"Successfully generated {len(generated_questions)} questions + 1 default question and {len(audio_files)} audio files for session {session_id}")
        
        return True
        
    except Exception as e:
        print(f"Error generating questions and audio for session {session_id}: {e}")
        db.session.rollback()
        return False