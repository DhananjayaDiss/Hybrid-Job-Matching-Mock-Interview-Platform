# app/models.py - Simplified models for interview system
from app import db
from datetime import datetime
from sqlalchemy.dialects.mysql import JSON

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    auth0_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100))
    picture = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    @staticmethod
    def get_or_create_user(auth0_user_info):
        """Get existing user or create new one from Auth0 user info"""
        user = User.query.filter_by(auth0_id=auth0_user_info['sub']).first()
        
        if not user:
            user = User(
                auth0_id=auth0_user_info['sub'],
                email=auth0_user_info.get('email'),
                name=auth0_user_info.get('name'),
                username=auth0_user_info.get('nickname'),
                picture=auth0_user_info.get('picture')
            )
            db.session.add(user)
            db.session.commit()
        else:
            # Update user info on login
            user.email = auth0_user_info.get('email', user.email)
            user.name = auth0_user_info.get('name', user.name)
            user.picture = auth0_user_info.get('picture', user.picture)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
        return user
    
    def __repr__(self):
        return f'<User {self.email}>'


class InterviewSession(db.Model):
    __tablename__ = 'interview_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    job_title = db.Column(db.String(200), nullable=False)
    difficulty_level = db.Column(db.Enum('easy', 'medium', 'hard', name='difficulty_levels'), 
                                default='medium', nullable=False)
    resume_text_data = db.Column(db.Text, nullable=False)
    
    # Questions and Answers - JSON arrays to store questions and answers
    questions = db.Column(JSON)  # Array of questions
    answers = db.Column(JSON)    # Array of corresponding answers
    
    # Session metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    status = db.Column(db.Enum('setup', 'in_progress', 'completed', name='session_status'), 
                      default='setup', nullable=False)
    
    # Relationships
    user = db.relationship('User', backref='interview_sessions')
    
    def __init__(self, **kwargs):
        super(InterviewSession, self).__init__(**kwargs)
        # Only initialize answers, leave questions to be set by the application logic
        if self.answers is None:
            self.answers = []
    
    def add_question(self, question_text):
        """Add a question to the session"""
        if not self.questions:
            self.questions = []
        
        self.questions.append(question_text)
        db.session.commit()
    
    def add_answer(self, question_index, answer_text):
        """Add answer for a specific question index"""
        if not self.answers:
            self.answers = []
        
        # Ensure answers array has enough slots
        while len(self.answers) <= question_index:
            self.answers.append(None)
        
        self.answers[question_index] = {
            'answer': answer_text,
            'answered_at': datetime.utcnow().isoformat()
        }
        db.session.commit()
    
    def get_question_count(self):
        """Get current number of questions"""
        return len(self.questions) if self.questions else 0
    
    def get_answered_count(self):
        """Get number of answered questions"""
        if not self.answers:
            return 0
        return len([a for a in self.answers if a is not None])
    
    def __repr__(self):
        return f'<InterviewSession {self.id}: {self.job_title}>'

class JobPosting(db.Model):
    __tablename__ = 'job_postings'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    company = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100))
    requirements = db.Column(db.Text)
    skills_required = db.Column(JSON)  # Array of required skills
    experience_level = db.Column(db.String(50))
    employment_type = db.Column(db.String(50))  # full-time, part-time, contract
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    posted_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    poster = db.relationship('User', backref='job_postings')
    
    def __repr__(self):
        return f'<JobPosting {self.title}>'
    



    