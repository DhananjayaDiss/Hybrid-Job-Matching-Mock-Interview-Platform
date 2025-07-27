import json
from urllib.parse import quote_plus, urlencode
from flask import redirect, render_template, session, url_for, current_app
from authlib.integrations.flask_client import OAuth
from app.auth import bp
from app.models import User
from app import db

oauth = OAuth()

def init_oauth(app):
    oauth.init_app(app)

    oauth.register(
        "auth0",
        client_id=app.config['AUTH0_CLIENT_ID'],
        client_secret=app.config['AUTH0_CLIENT_SECRET'],
        client_kwargs={
            "scope": "openid profile email",
        },
        server_metadata_url=f'https://{app.config["AUTH0_DOMAIN"]}/.well-known/openid-configuration'
    )

@bp.route("/login")
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("auth.callback", _external=True)
    )

@bp.route("/callback", methods=["GET", "POST"])
def callback():
    token = oauth.auth0.authorize_access_token()
    print(f"=== AUTH CALLBACK DEBUG ===")
    print(f"Token keys: {list(token.keys())}")
    
    # Get user info from the token
    auth0_user_info = token.get('userinfo')
    if not auth0_user_info:
        # Try to get it from the token directly
        auth0_user_info = {
            'sub': token.get('sub'),
            'email': token.get('email'),
            'name': token.get('name'),
            'nickname': token.get('nickname'),
            'picture': token.get('picture')
        }
    
    print(f"Auth0 user info: {auth0_user_info}")
    
    # Automatically create or update user in database
    user = User.get_or_create_user(auth0_user_info)
    print(f"Database user created/updated: {user}")
    
    # Store token and enhanced user info in session
    session["user"] = token  # Keep the full token
    session["user_id"] = user.id  # Store database user ID for easy access
    session["user_email"] = user.email
    session["auth0_id"] = auth0_user_info.get('sub')  # Store Auth0 ID separately
    
    print(f"Session data stored - user_id: {user.id}, auth0_id: {auth0_user_info.get('sub')}")
    
    return redirect(url_for("main.dashboard"))

@bp.route("/logout")
def logout():
    session.clear()
    return redirect(
        "https://" + current_app.config['AUTH0_DOMAIN']
        + "/v2/logout?"
        + urlencode(
            {
                "returnTo": url_for("main.index", _external=True),
                "client_id": current_app.config['AUTH0_CLIENT_ID'],
            },
            quote_via=quote_plus,
        )
    )