from flask import render_template, request, redirect, url_for, flash, session, jsonify, current_app, send_file
from app.main import bp
from app.auth.decorators import requires_auth
from app.models import User, InterviewSession
from app import db
from werkzeug.utils import secure_filename
import os
import PyPDF2
import pdfplumber
import json
import time
import wave
from typing import List, Dict, Tuple
import google.generativeai as genai
from google import genai as genai_client
from google.genai import types
import tempfile

# Configure upload settings
UPLOAD_FOLDER = 'uploads'
AUDIO_FOLDER = 'audio_files'
ALLOWED_EXTENSIONS = {'pdf'}

@bp.route('/')
def index():
    """Homepage route"""
    user = session.get('user')
    return render_template('index.html', user=user)

@bp.route('/dashboard')
@requires_auth
def dashboard():
    """User dashboard"""
    userinfo = session.get('user', {})
    
    return render_template('dashboard.html', 
                         user=userinfo,
                         userinfo=userinfo,
                         userinfo_pretty=json.dumps(userinfo, indent=2))

@bp.route('/debug-session')
@requires_auth
def debug_session():
    """Debug route to check session contents"""
    session_data = dict(session)
    user_data = session.get('user', {})
    
    debug_info = {
        'session_keys': list(session.keys()),
        'user_data': user_data,
        'user_sub': user_data.get('sub') if user_data else None,
        'userinfo': user_data.get('userinfo') if user_data else None,
        'full_session': session_data
    }
    
    return f"<pre>{json.dumps(debug_info, indent=2, default=str)}</pre>"

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(file_path):
    """Extract text from PDF file"""
    text = ""
    
    try:
        # Try pdfplumber first
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        # If no text found, try PyPDF2
        if len(text.strip()) < 50:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                    
    except Exception as e:
        current_app.logger.error(f"PDF extraction error: {str(e)}")
        return None
        
    return text.strip()

def parse_resume_data(resume_text):
    """Parse resume text (currently just returns the text)"""
    return resume_text

def get_current_user():
    """Get current user from session and database"""
    auth0_id = None
    user = None
    
    # Method 1: Check if user_id is stored (easier approach)
    if 'user_id' in session:
        user_id = session['user_id']
        user = User.query.get(user_id)
        if user:
            return user
    
    # Method 2: Check if auth0_id is directly stored in session
    if 'auth0_id' in session:
        auth0_id = session['auth0_id']
    
    # Method 3: Try to extract from the token structure
    else:
        auth0_user_info = session.get('user', {})
        
        # Try different ways to get the Auth0 ID
        if 'sub' in auth0_user_info:
            auth0_id = auth0_user_info['sub']
        elif 'userinfo' in auth0_user_info and 'sub' in auth0_user_info['userinfo']:
            auth0_id = auth0_user_info['userinfo']['sub']
    
    if auth0_id:
        user = User.query.filter_by(auth0_id=auth0_id).first()
    
    return user

@bp.route('/interview-setup')
@requires_auth
def interview_setup():
    """Render the interview setup page"""
    user = session.get('user')
    return render_template('interview_setup.html', user=user)

@bp.route('/upload-resume', methods=['POST'])
@requires_auth
def upload_resume():
    """Handle resume upload and process it"""
    try:
        # Validate file upload
        if 'resume' not in request.files:
            return jsonify({'success': False, 'error': 'No file selected'})
        
        file = request.files['resume']
        job_title = request.form.get('job_title', '').strip()
        difficulty_level = request.form.get('difficulty_level', 'medium')
        
        # Basic validation
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        if not job_title:
            return jsonify({'success': False, 'error': 'Job title is required'})
        
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Only PDF files are allowed'})
        
        # Get current user
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'error': 'User not authenticated - please log in again'})
        
        # Create temp directory
        upload_dir = os.path.join(os.getcwd(), UPLOAD_FOLDER)
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save file temporarily
        filename = secure_filename(file.filename)
        timestamp = str(int(time.time()))
        unique_filename = f"{user.id}_{timestamp}_{filename}"
        file_path = os.path.join(upload_dir, unique_filename)
        file.save(file_path)
        
        # Extract text from PDF
        resume_text = extract_text_from_pdf(file_path)
        
        if not resume_text or len(resume_text.strip()) < 50:
            # Clean up temp file
            try:
                os.remove(file_path)
            except:
                pass
            return jsonify({'success': False, 'error': 'Could not extract readable text from PDF. Please try a different file.'})
        
        # Parse resume data
        resume_text_data = parse_resume_data(resume_text)
        
        # Create new interview session in database
        interview_session = InterviewSession(
            user_id=user.id,
            job_title=job_title,
            difficulty_level=difficulty_level,
            resume_text_data=resume_text_data,
            status='setup'
        )
        
        # Override the default questions initialization - we'll generate them later
        interview_session.questions = None
        
        # Add to database
        db.session.add(interview_session)
        db.session.commit()
        
        # Store session ID for easy access
        session['current_interview_session_id'] = interview_session.id
        
        # Clean up temp file
        try:
            os.remove(file_path)
        except:
            pass
        
        return jsonify({
            'success': True, 
            'message': f'Resume processed successfully! Extracted {len(resume_text_data)} characters of text.',
            'session_id': interview_session.id,
            'redirect_url': url_for('main.start_interview')
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in upload_resume: {str(e)}")
        return jsonify({'success': False, 'error': f'Error processing resume: {str(e)}'})

def initialize_gemini_client():
    """Initialize and return Gemini client"""
    api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is required")
    
    # Configure Gemini
    genai.configure(api_key=api_key)
    text_model = genai.GenerativeModel('gemini-2.0-flash')
    
    return text_model

def initialize_gemini_tts_client():
    """Initialize and return Gemini TTS client"""
    api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is required")
    
    # Initialize the Gemini client for TTS
    client = genai_client.Client(api_key=api_key)
    return client

def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
    """Save PCM data as a wave file"""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)

def generate_audio_for_questions(session_id: int, questions: List[str]) -> Dict[str, str]:
    """
    Generate audio files for all interview questions using Gemini TTS
    
    Args:
        session_id: Interview session ID
        questions: List of questions to convert to audio
        
    Returns:
        Dict mapping question index to audio file path
    """
    try:
        # Create audio directory if it doesn't exist
        audio_dir = os.path.join(os.getcwd(), AUDIO_FOLDER)
        os.makedirs(audio_dir, exist_ok=True)
        
        # Create session-specific directory
        session_audio_dir = os.path.join(audio_dir, f'session_{session_id}')
        os.makedirs(session_audio_dir, exist_ok=True)
        
        # Initialize Gemini TTS client
        client = initialize_gemini_tts_client()
        
        audio_files = {}
        
        for i, question in enumerate(questions):
            try:
                current_app.logger.info(f"Generating audio for question {i+1}: {question[:50]}...")
                
                # Generate audio using Gemini TTS
                response = client.models.generate_content(
                    model="gemini-2.5-flash-preview-tts",
                    contents=f"Say in a professional, friendly interviewer tone: {question}",
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name='Kore',  # Professional female voice
                                )
                            )
                        ),
                    )
                )
                
                # Extract audio data
                if (response.candidates and 
                    len(response.candidates) > 0 and 
                    response.candidates[0].content and 
                    response.candidates[0].content.parts and
                    len(response.candidates[0].content.parts) > 0 and
                    response.candidates[0].content.parts[0].inline_data):
                    
                    audio_data = response.candidates[0].content.parts[0].inline_data.data
                    
                    # Save audio file
                    filename = f'question_{i+1}.wav'
                    file_path = os.path.join(session_audio_dir, filename)
                    wave_file(file_path, audio_data)
                    
                    # Store relative path for serving
                    relative_path = f'{AUDIO_FOLDER}/session_{session_id}/{filename}'
                    audio_files[str(i)] = relative_path
                    
                    current_app.logger.info(f"Successfully generated audio for question {i+1}")
                else:
                    current_app.logger.error(f"No audio data received for question {i+1}")
                    
            except Exception as e:
                current_app.logger.error(f"Error generating audio for question {i+1}: {str(e)}")
                # Continue with other questions even if one fails
                continue
        
        current_app.logger.info(f"Generated {len(audio_files)} audio files out of {len(questions)} questions")
        return audio_files
        
    except Exception as e:
        current_app.logger.error(f"Error in generate_audio_for_questions: {str(e)}")
        return {}

def generate_questions(text_model, resume_text: str, job_title: str, difficulty_level: str) -> List[str]:
    """Generate 4 interview questions based on resume, job title, and difficulty level"""
    
    # Define difficulty-specific instructions
    difficulty_prompts = {
        'easy': "Focus on basic concepts, fundamental skills, and general experience questions.",
        'medium': "Include both fundamental and intermediate-level questions with some scenario-based problems.",
        'hard': "Create challenging questions including complex scenarios, advanced technical concepts, and problem-solving situations."
    }
    
    prompt = f"""
    You are an expert interviewer tasked with creating interview questions for a {job_title} position.
    
    Candidate's Resume/Background:
    {resume_text[:2000]}  # Limit text to avoid token limits
    
    Job Title: {job_title}
    Difficulty Level: {difficulty_level}
    
    Instructions:
    - {difficulty_prompts.get(difficulty_level, difficulty_prompts['medium'])}
    - Generate exactly 4 interview questions (NOT 5, as "Tell me about yourself" will be added separately)
    - Questions should be relevant to the job title and the candidate's background
    - Include a mix of behavioral, technical, and situational questions as appropriate
    - Make questions specific and engaging
    - Avoid generic questions - tailor them to the role and candidate's experience
    - Keep questions concise and clear for audio playback
    - DO NOT include "Tell me about yourself" as it's already the first question
    
    Return your response as a JSON array of exactly 4 questions, like this:
    ["Question 1", "Question 2", "Question 3", "Question 4"]
    
    Do not include any additional text or formatting - just the JSON array.
    """
    
    try:
        response = text_model.generate_content(prompt)
        questions_json = response.text.strip()
        
        # Remove any code block markers if present
        if questions_json.startswith('```json'):
            questions_json = questions_json[7:]
        if questions_json.endswith('```'):
            questions_json = questions_json[:-3]
        questions_json = questions_json.strip()
        
        # Parse the JSON response
        questions = json.loads(questions_json)
        
        # Validate we got exactly 4 questions
        if not isinstance(questions, list) or len(questions) != 4:
            raise ValueError(f"Expected 4 questions, got {len(questions) if isinstance(questions, list) else 'invalid format'}")
        
        return questions
        
    except json.JSONDecodeError as e:
        current_app.logger.error(f"Failed to parse Gemini response as JSON: {e}")
        current_app.logger.error(f"Raw response: {response.text if 'response' in locals() else 'No response'}")
        raise ValueError(f"Failed to parse AI response. Please try again.")
    except Exception as e:
        current_app.logger.error(f"Error generating questions with Gemini: {e}")
        raise ValueError(f"Error generating questions: {str(e)}")

@bp.route('/start-interview')
@requires_auth
def start_interview():
    """Start the interview session and generate audio files"""
    try:
        session_id = session.get('current_interview_session_id')
        
        if not session_id:
            flash('No interview session found. Please upload your resume first.', 'error')
            return redirect(url_for('main.interview_setup'))
        
        # Get interview session from database
        interview_session = InterviewSession.query.get(session_id)
        
        if not interview_session:
            flash('Interview session not found.', 'error')
            return redirect(url_for('main.interview_setup'))
        
        user = session.get('user')
        
        # Check if questions are already generated and valid
        current_app.logger.info(f"Current questions: {interview_session.questions}")
        current_app.logger.info(f"Questions type: {type(interview_session.questions)}")
        
        if not interview_session.questions or len(interview_session.questions) != 5:
            current_app.logger.info("Generating new questions...")
            try:
                # Initialize Gemini client
                text_model = initialize_gemini_client()
                
                # Generate questions (4 questions + "Tell me about yourself")
                generated_questions = generate_questions(
                    text_model, 
                    interview_session.resume_text_data, 
                    interview_session.job_title, 
                    interview_session.difficulty_level
                )
                
                # Add the standard opening question
                all_questions = ["Tell me about yourself and your professional background."] + generated_questions
                
                current_app.logger.info(f"Generated questions: {all_questions}")
                
                # Store generated questions in the session
                interview_session.questions = all_questions
                interview_session.status = 'in_progress'
                db.session.commit()
                
                current_app.logger.info("Questions saved to database")
                
            except Exception as question_error:
                current_app.logger.error(f"Error generating questions: {str(question_error)}")
                # Provide fallback questions if AI generation fails
                fallback_questions = [
                    "Tell me about yourself and your professional background.",
                    f"What interests you most about this {interview_session.job_title} position?",
                    "Describe a challenging project you've worked on and how you overcame obstacles.",
                    "What are your greatest strengths and how do they apply to this role?",
                    "Where do you see yourself in 5 years, and how does this position fit into your career goals?"
                ]
                interview_session.questions = fallback_questions
                interview_session.status = 'in_progress'
                db.session.commit()
                current_app.logger.info("Using fallback questions due to AI generation error")
        
        # Refresh the session from database to ensure we have the latest data
        db.session.refresh(interview_session)
        current_app.logger.info(f"Final questions before audio generation: {interview_session.questions}")
        
        # Generate audio files for all questions
        current_app.logger.info("Starting audio generation...")
        audio_files = generate_audio_for_questions(interview_session.id, interview_session.questions)
        
        # Store audio file paths in the session (you might want to add an audio_files column to your model)
        if hasattr(interview_session, 'audio_files'):
            interview_session.audio_files = audio_files
            db.session.commit()
        else:
            # For now, store in Flask session
            session[f'audio_files_{interview_session.id}'] = audio_files
        
        current_app.logger.info(f"Audio generation completed. Generated {len(audio_files)} files.")
        
        return render_template('interview_placeholder.html', 
                             user=user, 
                             interview_session=interview_session,
                             audio_files=audio_files)
    
    except Exception as e:
        current_app.logger.error(f"Error starting interview: {str(e)}")
        flash(f'Error starting interview: {str(e)}', 'error')
        return redirect(url_for('main.interview_setup'))

@bp.route('/regenerate-questions', methods=['POST'])
@requires_auth
def regenerate_questions():
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        interview_session = InterviewSession.query.get(session_id)
        if not interview_session:
            return jsonify({'success': False, 'error': 'Session not found'})
        
        # Regenerate questions
        text_model = initialize_gemini_client()
        generated_questions = generate_questions(
            text_model,
            interview_session.resume_text_data,
            interview_session.job_title,
            interview_session.difficulty_level
        )
        
        # Add the standard opening question
        all_questions = ["Tell me about yourself and your professional background."] + generated_questions
        
        interview_session.questions = all_questions
        db.session.commit()
        
        # Regenerate audio files
        audio_files = generate_audio_for_questions(interview_session.id, all_questions)
        session[f'audio_files_{interview_session.id}'] = audio_files
        
        return jsonify({'success': True, 'questions': all_questions, 'audio_files': audio_files})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/serve-audio/<int:session_id>/<filename>')
@requires_auth
def serve_audio(session_id, filename):
    """Serve audio files for interview questions"""
    try:
        # Security check: ensure user owns this session
        user = get_current_user()
        interview_session = InterviewSession.query.get(session_id)
        
        if not interview_session or interview_session.user_id != user.id:
            return "Unauthorized", 403
        
        # Construct file path
        audio_dir = os.path.join(os.getcwd(), AUDIO_FOLDER, f'session_{session_id}')
        file_path = os.path.join(audio_dir, filename)
        
        # Security check: ensure file exists and is within the expected directory
        if not os.path.exists(file_path) or not os.path.commonpath([audio_dir, file_path]) == audio_dir:
            return "File not found", 404
        
        return send_file(file_path, mimetype='audio/wav')
        
    except Exception as e:
        current_app.logger.error(f"Error serving audio file: {str(e)}")
        return "Internal server error", 500