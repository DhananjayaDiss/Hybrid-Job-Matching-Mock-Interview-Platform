import os
from app import create_app
from app.auth.routes import init_oauth

def main():
    app = create_app(os.getenv('FLASK_CONFIG') or 'default')
    init_oauth(app)
    app.run(debug=True)

if __name__ == '__main__':
    main()