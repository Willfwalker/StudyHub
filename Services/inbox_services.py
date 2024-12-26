from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import os.path
import base64
from typing import List, Dict, Optional
from os import getenv
from dotenv import load_dotenv
from pathlib import Path

class InboxService:
    GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

    def __init__(self):
        # Load .env file from project root
        env_path = Path('..') / '.env'
        load_dotenv(dotenv_path=env_path)
        
        # Get allowed senders with fallback and filtering
        allowed_senders = getenv('ALLOWED_SENDERS', '')
        self.allowed_senders = [s.strip() for s in allowed_senders.split(',') if s.strip()]
        
        # Debug print to verify environment variables are loaded
        print(f"Loaded allowed senders: {self.allowed_senders}")
        
        # Gmail setup
        self.gmail_credentials_path = os.path.join('.', getenv('CREDENTIALS_PATH', 'credentials.json'))
        print(f"Loaded credentials path: {self.gmail_credentials_path}")
        
        if not self.gmail_credentials_path:
            self.gmail_service = None
            print("Warning: CREDENTIALS_PATH not found in environment variables")
        else:
            self.token_path = os.path.join('.', 'token.pickle')
            self.gmail_service = self._get_gmail_service()

        # Outlook setup
        self.outlook_service = None

        if not self.gmail_service:
            raise ValueError("No email service credentials provided")

    def _get_gmail_service(self):
        """Creates and returns Gmail API service"""
        if not self.gmail_credentials_path or not os.path.exists(self.gmail_credentials_path):
            return None

        creds = None
        if os.path.exists(self.token_path):
            try:
                with open(self.token_path, 'rb') as token:
                    creds_data = token.read()
                    creds = Credentials.from_authorized_user_info(eval(creds_data), self.GMAIL_SCOPES)
            except Exception as e:
                if os.path.exists(self.token_path):
                    os.remove(self.token_path)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None
            
            if not creds:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.gmail_credentials_path, self.GMAIL_SCOPES)
                creds = flow.run_local_server(port=0)
            
            try:
                with open(self.token_path, 'wb') as token:
                    token.write(str(creds.to_json()).encode())
            except Exception:
                pass

        return build('gmail', 'v1', credentials=creds)

    def get_emails_from_sender(self, sender_email: str, page: int = 1, per_page: int = 20) -> Dict:
        """Get paginated emails from sender"""
        try:
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            all_emails = []

            if sender_email == "all":
                for sender in self.allowed_senders:
                    if self.gmail_service:
                        gmail_emails = self._get_gmail_emails(sender, per_page)
                        all_emails.extend(gmail_emails)
            elif sender_email in self.allowed_senders:
                if self.gmail_service:
                    gmail_emails = self._get_gmail_emails(sender_email, per_page)
                    all_emails.extend(gmail_emails)
            else:
                raise ValueError(f"Invalid or unauthorized sender: {sender_email}")

            # Sort and paginate
            all_emails.sort(key=lambda x: int(x['timestamp']), reverse=True)
            total_emails = len(all_emails)
            paginated_emails = all_emails[start_idx:end_idx]
            
            return {
                'emails': paginated_emails,
                'total': total_emails,
                'page': page,
                'per_page': per_page,
                'total_pages': (total_emails + per_page - 1) // per_page
            }

        except Exception as e:
            print(f"Error in get_emails_from_sender: {str(e)}")  # Add logging
            return {
                'emails': [],
                'total': 0,
                'page': page,
                'per_page': per_page,
                'total_pages': 0
            }

    def _get_gmail_emails(self, sender_email: str, max_results: int) -> List[Dict]:
        try:
            query = f"from:{sender_email}"
            results = self.gmail_service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            if not messages:
                return []
            
            emails = []
            for message in messages:
                try:
                    msg = self.gmail_service.users().messages().get(
                        userId='me',
                        id=message['id'],
                        format='full'
                    ).execute()
                    
                    headers = msg['payload']['headers']
                    subject = next(
                        (header['value'] for header in headers if header['name'].lower() == 'subject'),
                        'No Subject'
                    )
                    
                    text = self._extract_gmail_body(msg['payload']) or 'No content available'
                    
                    emails.append({
                        'id': message['id'],
                        'subject': subject,
                        'body': text,
                        'timestamp': msg['internalDate'],
                        'source': 'Gmail',
                        'sender': sender_email
                    })
                except Exception:
                    continue
            
            return emails
            
        except Exception:
            return []

    def _extract_gmail_body(self, payload):
        def get_body_from_part(part):
            if part.get('body', {}).get('data'):
                try:
                    data = part['body']['data']
                    padded_data = data + ('=' * (4 - len(data) % 4))
                    decoded = base64.urlsafe_b64decode(padded_data)
                    return decoded.decode('utf-8', errors='replace')
                except Exception:
                    return None
            return None

        if 'parts' in payload:
            text_content = []
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain':
                    content = get_body_from_part(part)
                    if content:
                        text_content.append(content)
                elif 'parts' in part:
                    nested_content = self._extract_gmail_body(part)
                    if nested_content:
                        text_content.append(nested_content)
            return '\n'.join(filter(None, text_content))
        else:
            return get_body_from_part(payload)

    def verify_credentials(self) -> Dict[str, bool]:
        """Verify that the email service credentials are valid"""
        status = {
            'gmail': False,
        }
        
        if self.gmail_service:
            try:
                self.gmail_service.users().getProfile(userId='me').execute()
                status['gmail'] = True
            except Exception:
                pass

        return status

    def verify_sender_emails(self, sender_email: str) -> bool:
        """Test method to verify if we can fetch emails from a specific sender"""
        try:
            query = f"from:{sender_email}"
            results = self.gmail_service.users().messages().list(
                userId='me',
                q=query,
                maxResults=1
            ).execute()
            
            messages = results.get('messages', [])
            return len(messages) > 0
        except Exception as e:
            print(f"Error testing sender {sender_email}: {str(e)}")
            return False