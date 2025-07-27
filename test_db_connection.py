# test_db_connection.py - Test your database connection
import os
import pymysql
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
MYSQL_USER = os.environ.get('MYSQL_USER') or 'root'
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD') or ''
MYSQL_HOST = os.environ.get('MYSQL_HOST') or 'localhost'
MYSQL_PORT = int(os.environ.get('MYSQL_PORT') or '3306')
MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE') or 'interview_app'

print("Testing database connection...")
print(f"Host: {MYSQL_HOST}:{MYSQL_PORT}")
print(f"User: {MYSQL_USER}")
print(f"Database: {MYSQL_DATABASE}")

try:
    # Test basic MySQL connection (without database)
    print("\n1. Testing MySQL server connection...")
    connection = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD
    )
    print("✅ MySQL server connection successful!")
    
    # Check if database exists
    print(f"\n2. Checking if database '{MYSQL_DATABASE}' exists...")
    cursor = connection.cursor()
    cursor.execute("SHOW DATABASES")
    databases = [db[0] for db in cursor.fetchall()]
    
    if MYSQL_DATABASE in databases:
        print(f"✅ Database '{MYSQL_DATABASE}' exists!")
    else:
        print(f"❌ Database '{MYSQL_DATABASE}' does not exist!")
        print("Creating database...")
        cursor.execute(f"CREATE DATABASE {MYSQL_DATABASE}")
        print(f"✅ Database '{MYSQL_DATABASE}' created!")
    
    connection.close()
    
    # Test connection to specific database
    print(f"\n3. Testing connection to database '{MYSQL_DATABASE}'...")
    connection = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )
    print(f"✅ Connection to database '{MYSQL_DATABASE}' successful!")
    
    # Test table creation
    print("\n4. Testing table operations...")
    cursor = connection.cursor()
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    print(f"Current tables: {[table[0] for table in tables]}")
    
    connection.close()
    print("\n🎉 All database tests passed!")
    
except pymysql.MySQLError as e:
    print(f"❌ MySQL Error: {e}")
    print("\nPossible solutions:")
    print("1. Make sure MySQL server is running")
    print("2. Check your username and password")
    print("3. Verify the host and port")
    print("4. Make sure the user has proper permissions")
    
except Exception as e:
    print(f"❌ Connection Error: {e}")
    print("\nPossible solutions:")
    print("1. Install pymysql: uv add pymysql")
    print("2. Check your .env file configuration")
    print("3. Make sure MySQL service is started")