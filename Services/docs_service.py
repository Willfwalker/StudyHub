from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os.path
import pickle
import datetime
import csv
from typing import Optional, Dict, List
import pandas as pd
from datetime import datetime
from os import getenv
from dotenv import load_dotenv
import json
from pathlib import Path
from firebase_admin import db

class DocsService:
    SCOPES = [
        'https://www.googleapis.com/auth/documents',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/presentations'
    ]
    
    def __init__(self, user_id=None):
        load_dotenv()
        
        # Get credentials path from environment variable
        self.credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 
            os.path.join(os.getcwd(), 'credentials.json'))
        
        # Debug print
        print(f"Looking for credentials at: {self.credentials_path}")
        
        if not os.path.exists(self.credentials_path):
            raise ValueError(f"Credentials file not found at: {self.credentials_path}")
        
        self.user_id = user_id
        self.creds = self._get_credentials()
        if self.creds:
            self.docs_service = build('docs', 'v1', credentials=self.creds)
            self.drive_service = build('drive', 'v3', credentials=self.creds)
        else:
            self.docs_service = None
            self.drive_service = None

    def _get_token_path(self):
        """Get the token file path for the specific user"""
        # Create google_tokens directory if it doesn't exist
        tokens_dir = Path('google_tokens')
        tokens_dir.mkdir(exist_ok=True)
        
        # Return path to user-specific token file
        return tokens_dir / f'google_token_{self.user_id}.pickle'

    def _get_credentials(self):
        """Gets valid credentials for the current user."""
        creds = None
        
        if not self.user_id:
            return None

        token_path = self._get_token_path()

        # Load existing credentials if they exist
        if token_path.exists():
            try:
                with open(token_path, 'rb') as token:
                    creds = pickle.load(token)
            except Exception as e:
                print(f"Error loading credentials: {str(e)}")
                return None

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing credentials: {str(e)}")
                    return None
            else:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        os.getenv('CREDENTIALS_PATH'), self.SCOPES)
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    print(f"Error creating new credentials: {str(e)}")
                    return None

            # Save the credentials for the next run
            try:
                with open(token_path, 'wb') as token:
                    pickle.dump(creds, token)
            except Exception as e:
                print(f"Error saving credentials: {str(e)}")

        return creds

    def delete_token(self):
        """Delete the user's Google token"""
        if not self.user_id:
            return False
            
        token_path = self._get_token_path()
        try:
            if token_path.exists():
                token_path.unlink()
            return True
        except Exception as e:
            print(f"Error deleting token: {str(e)}")
            return False

    def create_document(self, title: str) -> Optional[Dict]:
        """Creates a new Google Doc with the given title."""
        try:
            document = self.docs_service.documents().create(
                body={'title': title}).execute()
            print(f'Created document with title: {title}')
            return document
        except Exception as e:
            print(f'Error creating document: {e}')
            return None

    def update_document(self, document_id: str, name: str, professor: str, class_name: str) -> Optional[Dict]:
        try:
            # Create header
            header_requests = [{'createHeader': {'type': 'DEFAULT'}}]
            self.docs_service.documents().batchUpdate(
                documentId=document_id,
                body={'requests': header_requests}
            ).execute()

            # Get header ID
            doc = self.docs_service.documents().get(
                documentId=document_id).execute()
            header_id = doc.get('headers', {}).popitem()[0]

            # Get current date
            current_date = datetime.now().strftime('%d %B %Y')
            last_name = name.split()[-1]

            # Update header and content with proper formatting
            requests = [
                # Header content (Last Name #) - Right aligned
                {
                    'insertText': {
                        'location': {'segmentId': header_id, 'index': 0},
                        'text': f"{last_name} #\n"
                    }
                },
                {
                    'updateParagraphStyle': {
                        'range': {'segmentId': header_id, 'startIndex': 0, 'endIndex': len(last_name) + 2},
                        'paragraphStyle': {'alignment': 'END'},
                        'fields': 'alignment'
                    }
                },
                # Main content - Left aligned
                {
                    'insertText': {
                        'location': {'index': 1},
                        'text': f"{name}\n\n{professor}\n\n{class_name}\n\n{current_date}\n\n"
                    }
                }
            ]

            # Execute the update
            result = self.docs_service.documents().batchUpdate(
                documentId=document_id,
                body={'requests': requests}
            ).execute()

            return result
        except Exception as e:
            print(f"Error updating document: {e}")
            return None

    def update_document_apa(self, document_id: str, name: str, professor: str, class_name: str) -> Optional[Dict]:
        """Updates a Google Doc with APA formatting."""
        try:
            # Create header
            header_requests = [{'createHeader': {'type': 'DEFAULT'}}]
            self.docs_service.documents().batchUpdate(
                documentId=document_id,
                body={'requests': header_requests}
            ).execute()

            # Get header ID
            doc = self.docs_service.documents().get(
                documentId=document_id).execute()
            header_id = doc.get('headers', {}).popitem()[0]

            # Get current date
            current_date = datetime.now().strftime('%B %d, %Y')

            # Update header and content with proper APA formatting
            requests = [
                # Header content (Running head: TITLE) - Left aligned
                {
                    'insertText': {
                        'location': {'segmentId': header_id, 'index': 0},
                        'text': f"Running head: {class_name.upper()}\n"
                    }
                },
                # Main content - Center aligned title block
                {
                    'insertText': {
                        'location': {'index': 1},
                        'text': f"{class_name}\n\n{name}\n{professor}\n{current_date}\n\n"
                    }
                },
                # Center align the title block
                {
                    'updateParagraphStyle': {
                        'range': {'startIndex': 1, 'endIndex': len(f"{class_name}\n\n{name}\n{professor}\n{current_date}\n\n")},
                        'paragraphStyle': {'alignment': 'CENTER'},
                        'fields': 'alignment'
                    }
                }
            ]

            # Execute the update
            result = self.docs_service.documents().batchUpdate(
                documentId=document_id,
                body={'requests': requests}
            ).execute()

            return result
        except Exception as e:
            print(f"Error updating document: {e}")
            return None

    def move_to_folder(self, file_id: str, folder_id: str) -> bool:
        """Moves a file to specified folder in Google Drive."""
        try:
            file = self.drive_service.files().get(
                fileId=file_id,
                fields='parents'
            ).execute()
            
            previous_parents = ",".join(file.get('parents', []))
            self.drive_service.files().update(
                fileId=file_id,
                addParents=folder_id,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()
            
            return True
        except Exception as e:
            print(f'Error moving file: {e}')
            return False

    def create_class_folders(self, parent_folder_id: str, class_names: list) -> list:
        """Creates folders for each class and a Notes subfolder within each."""
        created_folders = []
        for class_name in class_names:
            try:
                # Create main class folder
                folder_metadata = {
                    'name': class_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [parent_folder_id]
                }
                
                folder = self.drive_service.files().create(
                    body=folder_metadata,
                    fields='id'
                ).execute()
                
                folder_id = folder.get('id')
                
                # Create Notes subfolder
                notes_metadata = {
                    'name': 'Notes',
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [folder_id]
                }
                
                notes_folder = self.drive_service.files().create(
                    body=notes_metadata,
                    fields='id'
                ).execute()
                
                # Save both folders to Firebase
                self._save_folder_info(class_name, {
                    'main_folder_id': folder_id,
                    'notes_folder_id': notes_folder.get('id')
                })
                
                created_folders.append(folder_id)
                
            except Exception as e:
                print(f'Error creating folder for {class_name}: {e}')
                
        return created_folders

    def _save_folder_info(self, folder_name: str, folder_data: dict):
        """Saves folder information to Firebase"""
        try:
            if not self.user_id:
                return False
                
            folders_ref = db.reference(f'users/{self.user_id}/folders')
            
            # Create a unique key for the folder
            folder_key = folder_name.replace('.', '_').replace('/', '_').replace(' ', '_')
            
            # Store folder information
            folders_ref.child(folder_key).set({
                'name': folder_name,
                'main_folder_id': folder_data['main_folder_id'],
                'notes_folder_id': folder_data['notes_folder_id'],
                'created_at': datetime.now().isoformat()
            })
            
            return True
            
        except Exception as e:
            print(f"Error saving folder info: {e}")
            return False

    def create_homework_document(self, canvas_service, selected_assignment_index=None, student_name=None, professor=None) -> Dict:
        try:
            # Get student name from Canvas if not provided
            if student_name is None:
                student_name = canvas_service.get_user_name()
                if not student_name:
                    return {"error": "Could not get student name from Canvas"}

            # If we have specific assignment details from the request
            if hasattr(canvas_service, 'current_assignment'):
                assignment = canvas_service.current_assignment
                course = canvas_service.current_course
                
                # Get folder ID for the class
                folder_id = self._get_folder_id(course['name'])
                if not folder_id:
                    return {"error": "Could not find folder ID for class"}

                # Create assignment info structure
                assignment_info = {
                    'course_name': course['name'],
                    'name': assignment['name'],
                    'course_id': course['id'],
                    'assignment_data': assignment
                }

                # Create and setup document
                doc_info = self._create_and_setup_document(
                    assignment=assignment_info,
                    student_name=student_name,
                    professor=professor or canvas_service.get_course_professor(course['id']),
                    folder_id=folder_id
                )

                if doc_info:
                    # Store document info in database
                    self.store_document_info(course['id'], assignment['id'], doc_info)
                    return {
                        "status": "document_created",
                        "doc_info": doc_info
                    }
                else:
                    return {"error": "Failed to create document"}

            # Legacy code for selection-based creation
            else:
                # Get all assignments from Canvas
                assignments = []
                courses = canvas_service.get_classes()
                
                # Collect assignments in a list
                for course in courses:
                    course_assignments = canvas_service.get_current_assignments(course['id'])
                    professor = canvas_service.get_course_professor(course['id'])  # Get professor for each course
                    
                    for assignment in course_assignments:
                        due_date = assignment.get("due_at")
                        if due_date:
                            due_date = datetime.strptime(due_date, "%Y-%m-%dT%H:%M:%SZ")
                            due_date = due_date.strftime("%B %d, %Y at %I:%M %p")
                        
                        assignment_info = {
                            'index': len(assignments),
                            'course_name': course['name'],
                            'name': assignment.get('name'),
                            'due_date': due_date or 'No due date',
                            'course_id': course['id'],
                            'assignment_data': assignment
                        }
                        assignments.append(assignment_info)

                # If no assignment is selected, return the list of assignments
                if selected_assignment_index is None:
                    return {
                        "assignments": assignments,
                        "status": "pending_selection"
                    }

                # If an assignment is selected, create the document
                selected_assignment = assignments[selected_assignment_index]
                
                # Get folder ID for the class
                folder_id = self._get_folder_id(selected_assignment['course_name'])
                if not folder_id:
                    return {"error": "Could not find folder ID for class"}

                # Create and setup document
                doc_info = self._create_and_setup_document(
                    assignment=selected_assignment,
                    student_name=student_name,
                    professor=professor,
                    folder_id=folder_id
                )

                if doc_info:
                    return {
                        "status": "document_created",
                        "doc_info": doc_info
                    }
                else:
                    return {"error": "Failed to create document"}

        except Exception as e:
            print(f"Error in create_homework_document: {str(e)}")  # Add debug logging
            return {"error": f"Error in create_homework_document: {str(e)}"}

    def _get_assignment_selection(self, assignments: List[Dict]) -> Optional[Dict]:
        """Get user selection for assignment"""
        while True:
            try:
                selection = int(input("\nEnter the number of the assignment you want to work on: "))
                if 0 <= selection < len(assignments):
                    selected = assignments[selection]
                    print(f"\nYou selected: {selected['name']} from {selected['course_name']}")
                    return selected
                else:
                    print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
            except Exception as e:
                print(f"Error in assignment selection: {e}")
                return None

    def _get_folder_id(self, class_name: str) -> Optional[str]:
        """Get folder ID from Firebase for given class"""
        try:
            if not self.user_id:
                return None
                
            folders_ref = db.reference(f'users/{self.user_id}/folders')
            folders = folders_ref.get()
            
            if folders:
                for folder_data in folders.values():
                    if folder_data.get('name') == class_name:
                        return folder_data.get('folder_id')
            return None
            
        except Exception as e:
            print(f"Error: Could not find folder ID for {class_name}: {e}")
            return None

    def _create_and_setup_document(self, 
                                 assignment: Dict,
                                 student_name: str,
                                 professor: str,
                                 folder_id: str) -> Optional[Dict]:
        """Create and setup the document with initial content"""
        try:
            # Create document
            doc = self.create_document(assignment['name'])
            if not doc:
                return None

            document_id = doc.get('documentId')
            
            # Update document content
            self.update_document(
                document_id=document_id,
                name=student_name,
                professor=professor,
                class_name=assignment['course_name']
            )

            # Move to appropriate folder
            self.move_to_folder(document_id, folder_id)

            # Create return info
            doc_info = {
                'document_id': document_id,
                'assignment_name': assignment['name'],
                'course_name': assignment['course_name'],
                'url': f'https://docs.google.com/document/d/{document_id}/edit'
            }

            print("\nDocument created and set up successfully!")
            print(f"You can view your document at: {doc_info['url']}")

            return doc_info

        except Exception as e:
            print(f"Error setting up document: {e}")
            return None

    def get_existing_document(self, course_id, assignment_id):
        """Check if a document already exists for this assignment in Firebase"""
        try:
            if not self.user_id:
                return None
                
            key = f"{course_id}_{assignment_id}"
            docs_ref = db.reference(f'users/{self.user_id}/documents/{key}')
            return docs_ref.get()
        except Exception as e:
            print(f"Error getting document from Firebase: {e}")
            return None

    def store_document_info(self, course_id, assignment_id, doc_info):
        """Store document information in Firebase"""
        try:
            if not self.user_id:
                return False
                
            key = f"{course_id}_{assignment_id}"
            docs_ref = db.reference(f'users/{self.user_id}/documents')
            docs_ref.child(key).set(doc_info)
            return True
        except Exception as e:
            print(f"Error storing document in Firebase: {e}")
            return False

    def export_as_pdf(self, document_id: str) -> Optional[bytes]:
        """Export a Google Doc as PDF."""
        try:
            # Get the PDF export
            response = self.drive_service.files().export(
                fileId=document_id,
                mimeType='application/pdf'
            ).execute()
            
            return response

        except Exception as e:
            print(f"Error exporting document as PDF: {str(e)}")
            return None

    def create_mla_document(self, assignment_data: dict) -> Optional[Dict]:
        """Creates an MLA formatted document for the assignment."""
        try:
            # Create base document
            doc = self.create_document(assignment_data['name'])
            if not doc:
                return None

            document_id = doc.get('documentId')
            
            # Get user info from assignment data
            student_name = assignment_data.get('student_name', '')
            professor = assignment_data.get('professor', '')
            class_name = assignment_data.get('course_name', '')

            # Apply MLA formatting using existing update_document method
            result = self.update_document(
                document_id=document_id,
                name=student_name,
                professor=professor,
                class_name=class_name
            )

            if not result:
                return None

            # Move document to correct class folder
            folder_id = self._get_folder_id(class_name)
            if folder_id:
                self.move_to_folder(document_id, folder_id)

            return {
                'id': document_id,
                'url': f'https://docs.google.com/document/d/{document_id}/edit'
            }

        except Exception as e:
            print(f"Error creating MLA document: {e}")
            return None

    def create_apa_document(self, assignment_data: dict) -> Optional[Dict]:
        """Creates an APA formatted document for the assignment."""
        try:
            # Create base document
            doc = self.create_document(assignment_data['name'])
            if not doc:
                return None

            document_id = doc.get('documentId')
            
            # Get user info from assignment data
            student_name = assignment_data.get('student_name', '')
            professor = assignment_data.get('professor', '')
            class_name = assignment_data.get('course_name', '')

            # Apply APA formatting using existing update_document_apa method
            result = self.update_document_apa(
                document_id=document_id,
                name=student_name,
                professor=professor,
                class_name=class_name
            )

            if not result:
                return None

            # Move document to correct class folder
            folder_id = self._get_folder_id(class_name)
            if folder_id:
                self.move_to_folder(document_id, folder_id)

            # Create document info
            doc_info = {
                'document_id': document_id,
                'assignment_name': assignment_data['name'],
                'course_name': class_name,
                'url': f'https://docs.google.com/document/d/{document_id}/edit',
                'format': 'APA'
            }

            # Store in Firebase if course_id and assignment_id are provided
            if 'course_id' in assignment_data and 'assignment_id' in assignment_data:
                self.store_document_info(
                    assignment_data['course_id'],
                    assignment_data['assignment_id'],
                    doc_info
                )

            return doc_info

        except Exception as e:
            print(f"Error creating APA document: {e}")
            return None

    def create_spreadsheet(self, assignment_data: dict) -> Optional[Dict]:
        """Creates a Google Sheets document for the assignment."""
        try:
            # Build the sheets service
            sheets_service = build('sheets', 'v4', credentials=self.creds)
            
            # Create spreadsheet with assignment name
            spreadsheet_body = {
                'properties': {
                    'title': assignment_data['name']
                },
                'sheets': [
                    {
                        'properties': {
                            'title': 'Sheet1',
                            'gridProperties': {
                                'rowCount': 1000,
                                'columnCount': 26
                            }
                        }
                    }
                ]
            }
            
            # Create the spreadsheet
            spreadsheet = sheets_service.spreadsheets().create(
                body=spreadsheet_body
            ).execute()
            
            spreadsheet_id = spreadsheet.get('spreadsheetId')
            
            # Add header information
            header_data = [
                [assignment_data.get('course_name', '')],
                [assignment_data.get('student_name', '')],
                [datetime.now().strftime('%B %d, %Y')],
                ['']  # Blank row after header
            ]
            
            # Update the spreadsheet with header information
            sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range='A1:A4',
                valueInputOption='RAW',
                body={'values': header_data}
            ).execute()
            
            # Format header
            requests = [
                {
                    'repeatCell': {
                        'range': {'startRowIndex': 0, 'endRowIndex': 3},
                        'cell': {
                            'userEnteredFormat': {
                                'textFormat': {'bold': True, 'fontSize': 12}
                            }
                        },
                        'fields': 'userEnteredFormat.textFormat'
                    }
                }
            ]
            
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': requests}
            ).execute()

            # Move spreadsheet to correct class folder
            folder_id = self._get_folder_id(assignment_data.get('course_name', ''))
            if folder_id:
                self.move_to_folder(spreadsheet_id, folder_id)

            return {
                'document_id': spreadsheet_id,
                'assignment_name': assignment_data['name'],
                'course_name': assignment_data.get('course_name', ''),
                'url': f'https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit'
            }

        except Exception as e:
            print(f"Error creating spreadsheet: {e}")
            return None

    def create_presentation(self, assignment_data: dict) -> Optional[Dict]:
        """Creates a Google Slides presentation for the assignment."""
        try:
            # Build the slides service
            slides_service = build('slides', 'v1', credentials=self.creds)
            
            # Create presentation with assignment name
            presentation = slides_service.presentations().create(
                body={'title': assignment_data['name']}
            ).execute()
            
            presentation_id = presentation.get('presentationId')
            
            # Create title slide with proper text elements
            requests = [
                {
                    'createSlide': {
                        'objectId': 'titleSlide',
                        'slideLayoutReference': {
                            'predefinedLayout': 'TITLE_AND_SUBTITLE'
                        },
                        'placeholderIdMappings': [
                            {
                                'layoutPlaceholder': {
                                    'type': 'TITLE',
                                    'index': 0
                                },
                                'objectId': 'titleTextBox'
                            },
                            {
                                'layoutPlaceholder': {
                                    'type': 'SUBTITLE',
                                    'index': 1
                                },
                                'objectId': 'subtitleTextBox'
                            }
                        ]
                    }
                },
                # Insert title text
                {
                    'insertText': {
                        'objectId': 'titleTextBox',
                        'text': assignment_data['name']
                    }
                },
                # Insert subtitle text
                {
                    'insertText': {
                        'objectId': 'subtitleTextBox',
                        'text': f"{assignment_data.get('student_name', '')}\n{assignment_data.get('course_name', '')}\n{datetime.now().strftime('%B %d, %Y')}"
                    }
                }
            ]
            
            # Execute the requests
            slides_service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={'requests': requests}
            ).execute()

            # Move presentation to correct class folder
            folder_id = self._get_folder_id(assignment_data.get('course_name', ''))
            if folder_id:
                self.move_to_folder(presentation_id, folder_id)

            return {
                'document_id': presentation_id,
                'assignment_name': assignment_data['name'],
                'course_name': assignment_data.get('course_name', ''),
                'url': f'https://docs.google.com/presentation/d/{presentation_id}/edit'
            }

        except Exception as e:
            print(f"Error creating presentation: {e}")
            return None

    def create_notes_doc(self, doc_name: str, folder_id: str) -> Optional[Dict]:
        """Create a new Google Doc formatted for notes and move it to specified folder
        
        Args:
            doc_name: Name of the document
            folder_id: ID of the folder where the document should be saved
        """
        try:
            # Create an empty document
            doc_body = {
                'title': doc_name
            }
            doc = self.docs_service.documents().create(body=doc_body).execute()
            document_id = doc.get('documentId')

            # Format requests for the document
            requests = [
                {
                    'updateParagraphStyle': {
                        'range': {
                            'startIndex': 1,
                            'endIndex': 2
                        },
                        'paragraphStyle': {
                            'lineSpacing': 200,  # Double spacing
                        },
                        'fields': 'lineSpacing'
                    }
                },
                {
                    'updateTextStyle': {
                        'range': {
                            'startIndex': 1,
                            'endIndex': 2
                        },
                        'textStyle': {
                            'fontSize': {
                                'magnitude': 12,
                                'unit': 'PT'
                            },
                            'weightedFontFamily': {
                                'fontFamily': 'Times New Roman'
                            }
                        },
                        'fields': 'fontSize,weightedFontFamily'
                    }
                }
            ]

            # Execute the formatting requests
            self.docs_service.documents().batchUpdate(
                documentId=document_id,
                body={'requests': requests}
            ).execute()

            # Move document to specified folder
            if not self.move_to_folder(document_id, folder_id):
                print(f"Warning: Failed to move document to specified folder")

            return {
                'document_id': document_id,
                'title': doc_name,
                'url': f'https://docs.google.com/document/d/{document_id}/edit'
            }

        except Exception as e:
            print(f"Error creating notes document: {e}")
            return None

    def get_folder_documents_content(self, folder_id):
        """Get the content of all documents in a folder"""
        try:
            # List all files in the folder
            results = self.drive_service.files().list(
                q=f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document'",
                fields="files(id, name)"
            ).execute()
            
            files = results.get('files', [])
            
            # Get content from each document
            contents = []
            for file in files:
                doc = self.docs_service.documents().get(documentId=file['id']).execute()
                content = ''
                for element in doc.get('body', {}).get('content', []):
                    if 'paragraph' in element:
                        for para_element in element['paragraph']['elements']:
                            if 'textRun' in para_element:
                                content += para_element['textRun'].get('content', '')
                contents.append(content)
            
            return contents

        except Exception as e:
            print(f"Error getting folder documents: {str(e)}")
            return None