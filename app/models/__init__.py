from app.models.user import User, InterviewSession

def register_blueprints(app):
    from api.interview_routes import interview_bp
    app.register_blueprint(interview_bp, url_prefix='/api/interview')

    