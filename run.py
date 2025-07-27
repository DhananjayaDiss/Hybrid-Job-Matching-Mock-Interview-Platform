import os
from app import create_app
from app.auth.routes import init_oauth

# Create app globally so gunicorn can find it
app = create_app(os.getenv('FLASK_CONFIG') or 'default')
init_oauth(app)

def main():
    # Only used in local development
    app.run(debug=True)

if __name__ == '__main__':
    main()
