from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle
from datetime import datetime
import base64
from email.mime.text import MIMEText
from firebase_admin import db
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class InboxService:
    def __init__(self, user_id=None):
        """Initialize the InboxService with user-specific credentials."""
        self.user_id = user_id
        self.gmail_service = None
        self.SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
        
        try:
            # Initialize service if user_id is provided
            if user_id:
                creds = self._get_credentials()
                if creds:
                    self.gmail_service = build('gmail', 'v1', credentials=creds)
        except Exception as e:
            print(f"Error initializing InboxService: {str(e)}")

    def _get_credentials(self):
        """Get Gmail API credentials for the current user."""
        try:
            if not self.user_id:
                return None

            # Get credentials from Firebase
            user_ref = db.reference(f'users/{self.user_id}/google_credentials')
            stored_creds = user_ref.get()

            if not stored_creds:
                return self._create_new_credentials()

            creds = Credentials(
                token=stored_creds.get('token'),
                refresh_token=stored_creds.get('refresh_token'),
                token_uri=stored_creds.get('token_uri'),
                client_id=stored_creds.get('client_id'),
                client_secret=stored_creds.get('client_secret'),
                scopes=stored_creds.get('scopes')
            )

            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    self._save_credentials_to_firebase(creds)
                else:
                    return self._create_new_credentials()

            return creds

        except Exception as e:
            print(f"Error getting credentials: {str(e)}")
            return None

    def _create_new_credentials(self):
        """Create new credentials with proper scopes"""
        try:
            # Get credentials from environment variable
            google_creds = os.getenv('GOOGLE_CREDENTIALS_JSON')
            if not google_creds:
                print("Error: GOOGLE_CREDENTIALS_JSON not found in environment variables")
                return None
                
            flow = InstalledAppFlow.from_client_config(
                json.loads(google_creds), self.SCOPES)
            creds = flow.run_local_server(port=0)
            
            # Save new credentials
            self._save_credentials_to_firebase(creds)
            return creds
            
        except Exception as e:
            print(f"Error creating new credentials: {str(e)}")
            return None

    def _save_credentials_to_firebase(self, creds):
        """Saves Gmail credentials to Firebase for the current user."""
        try:
            if not self.user_id:
                return False

            # Convert credentials to dictionary format
            token_data = {
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': creds.scopes,
                'expiry': creds.expiry.isoformat() if creds.expiry else None,
                'updated_at': datetime.now().isoformat()
            }

            # Save to Firebase
            user_ref = db.reference(f'users/{self.user_id}/google_credentials')
            user_ref.set(token_data)
            return True

        except Exception as e:
            print(f"Error saving credentials to Firebase: {str(e)}")
            return False

    # ... rest of your InboxService methods ...