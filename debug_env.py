import os
from dotenv import load_dotenv

load_dotenv()

print("=== Environment Variables Debug ===")
print(f"AUTH0_DOMAIN: '{os.getenv('AUTH0_DOMAIN')}'")
print(f"AUTH0_CLIENT_ID: '{os.getenv('AUTH0_CLIENT_ID')}'")
print(f"AUTH0_CLIENT_SECRET: '{os.getenv('AUTH0_CLIENT_SECRET')}'")
print(f"AUTH0_AUDIENCE: '{os.getenv('AUTH0_AUDIENCE')}'")
print(f"GEMINI_API_KEY: '{os.getenv('GEMINI_API_KEY')}'")
print("====================================")