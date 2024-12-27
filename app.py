from flask import Flask, jsonify, request, render_template, redirect, url_for, send_file, session
from flask_wtf.csrf import CSRFProtect
from flask_caching import Cache
from Services.docs_service import DocsService
from Services.canvas_service import CanvasService 
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import calendar
from Services.ai_service import AIService
from Services.inbox_services import InboxService
from PIL import Image
import requests
import json
import firebase_admin
from firebase_admin import credentials, auth, db
from firebase_admin import initialize_app
from functools import wraps
from pathlib import Path
from functools import lru_cache
from flask_mail import Mail, Message
from os import getenv
import time

load_dotenv()

# Create Flask app first
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.debug = False if os.getenv('FLASK_ENV') == 'production' else True
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')

# Then update the config
app.config.update({
    'FIREBASE_API_KEY': os.getenv('FIREBASE_API_KEY'),
    'FIREBASE_AUTH_DOMAIN': os.getenv('FIREBASE_AUTH_DOMAIN'),
    'FIREBASE_PROJECT_ID': os.getenv('FIREBASE_PROJECT_ID'),
    'FIREBASE_STORAGE_BUCKET': os.getenv('FIREBASE_STORAGE_BUCKET'),
    'FIREBASE_MESSAGING_SENDER_ID': os.getenv('FIREBASE_MESSAGING_SENDER_ID'),
    'FIREBASE_APP_ID': os.getenv('FIREBASE_APP_ID')
})

print("Firebase Config:", {k: v for k, v in app.config.items() if k.startswith('FIREBASE_')})

# Ensure static folder exists
static_folder = os.path.join(os.getcwd(), 'static')
if not os.path.exists(static_folder):
    os.makedirs(static_folder)

# Ensure cache folder exists
cache_dir = os.path.join(static_folder, 'images', 'cache')
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

csrf = CSRFProtect(app)
cache = Cache(app, config={
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 300
})

print("Current working directory:", os.getcwd())
print("Static folder absolute path:", os.path.abspath(app.static_folder))

# Add this near the top of your file with other configurations
CLASS_IMAGES = {
    "Calc/Analyt Geo I": "math.jpg",
    "Freshman English I": "english.jpg",
    "Programming Fundamentals": "programming.jpg",
    "Introduction to Cybersecurity": "cybersecurity.jpg",
    "Exploring the Old Testament": "bible.jpg",
    "Belhaven Basics": "belhaven.jpg"
}

# Initialize Firebase with credentials from environment variable
try:
    firebase_cred_dict = json.loads(os.getenv('FIREBASE_CREDENTIALS_JSON'))
    cred = credentials.Certificate(firebase_cred_dict)
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://student-hub-28ea1-default-rtdb.firebaseio.com/'
    })
    print("Firebase initialized successfully")
except Exception as e:
    print(f"Firebase initialization error: {str(e)}")

# Test the database connection
def test_db_connection():
    try:
        ref = db.reference('test')
        ref.set({'test': 'connection successful'})
        print("Database connection successful")
    except Exception as e:
        print(f"Database connection error: {str(e)}")

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'studyhubservice@gmail.com'
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_USE_SSL'] = False

mail = Mail(app)

[... rest of the file remains unchanged ...]