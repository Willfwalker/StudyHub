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
from config.settings import GOOGLE_CREDENTIALS_JSON

class DocsService:
    SCOPES = [
        'https://www.googleapis.com/auth/documents',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/drive.metadata.readonly',
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/presentations'
    ]
    
    def __init__(self, user_id=None):
        """Initialize the DocsService with user credentials"""
        self.user_id = user_id
        self.creds = None
        
        if user_id:
            # Get credentials from Firebase
            self.creds = self._get_credentials()
            
            if self.creds:
                # Build the services
                self.drive_service = build('drive', 'v3', credentials=self.creds)
                self.docs_service = build('docs', 'v1', credentials=self.creds)

    def _get_credentials(self):
        """Gets valid credentials for the current user from Firebase."""
        if not self.user_id:
            return None

        try:
            # Load credentials from settings string
            credentials_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
            
            # Get token data from Firebase
            user_ref = db.reference(f'users/{self.user_id}/google_credentials')
            token_data = user_ref.get()

            if token_data:
                print("\nStored scopes in Firebase:", token_data.get('scopes'))
                
                # Check if we have all required scopes
                required_scopes = set(self.SCOPES)
                stored_scopes = set(token_data.get('scopes', []))
                missing_scopes = required_scopes - stored_scopes
                
                if missing_scopes:
                    print(f"Missing required scopes: {missing_scopes}")
                    # Force new token creation
                    return self._create_new_credentials()

            creds = None
            if token_data:
                # Convert stored token data back to Credentials object
                creds = Credentials(
                    token=token_data.get('token'),
                    refresh_token=token_data.get('refresh_token'),
                    token_uri=token_data.get('token_uri'),
                    client_id=credentials_dict['installed']['client_id'],     # Use from settings
                    client_secret=credentials_dict['installed']['client_secret'],  # Use from settings
                    scopes=token_data.get('scopes')
                )

            # If there are no (valid) credentials available, let the user log in
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        # Save refreshed credentials
                        self._save_credentials_to_firebase(creds)
                    except Exception as e:
                        print(f"Error refreshing credentials: {str(e)}")
                        return self._create_new_credentials()
                else:
                    return self._create_new_credentials()

            return creds

        except Exception as e:
            print(f"Error getting credentials: {str(e)}")
            return None

    def _create_new_credentials(self):
        """Create new credentials with proper scopes"""
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                os.path.join('.', os.getenv('CREDENTIALS_PATH')), self.SCOPES)
            creds = flow.run_local_server(port=0)
            # Save new credentials
            self._save_credentials_to_firebase(creds)
            return creds
        except Exception as e:
            print(f"Error creating new credentials: {str(e)}")
            return None

    def delete_token(self):
        """Delete the user's Google token from Firebase"""
        try:
            if not self.user_id:
                return False
            
            user_ref = db.reference(f'users/{self.user_id}/google_credentials')
            user_ref.delete()
            return True
        except Exception as e:
            print(f"Error deleting token from Firebase: {str(e)}")
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

            # Calculate the end index for the main content
            main_content = f"{name}\n\n{professor}\n\n{class_name}\n\n{current_date}\n\n"
            main_content_end_index = len(main_content) + 1  # +1 for the initial index

            requests = [
                # Header content (Last Name and page number) - Right aligned
                {
                    'insertText': {
                        'location': {'segmentId': header_id, 'index': 0},
                        'text': f"{last_name} "
                    }
                },
                # Insert page number field
                {
                    'insertText': {
                        'location': {'segmentId': header_id, 'index': len(last_name) + 1},
                        'text': '1'  # This will be automatically updated by Google Docs
                    }
                },
                {
                    'insertText': {
                        'location': {'segmentId': header_id, 'index': len(last_name) + 2},
                        'text': "\n"
                    }
                },
                {
                    'updateParagraphStyle': {
                        'range': {'segmentId': header_id, 'startIndex': 0, 'endIndex': len(last_name) + 3},
                        'paragraphStyle': {'alignment': 'END'},
                        'fields': 'alignment'
                    }
                },
                # Main content - Left aligned
                {
                    'insertText': {
                        'location': {'index': 1},
                        'text': main_content
                    }
                },
                # Apply Times New Roman, 12pt to entire document
                {
                    'updateTextStyle': {
                        'range': {'startIndex': 1, 'endIndex': main_content_end_index},
                        'textStyle': {
                            'fontSize': {'magnitude': 12, 'unit': 'PT'},
                            'weightedFontFamily': {'fontFamily': 'Times New Roman'}
                        },
                        'fields': 'fontSize,weightedFontFamily'
                    }
                },
                # Apply Times New Roman, 12pt to header
                {
                    'updateTextStyle': {
                        'range': {
                            'segmentId': header_id,
                            'startIndex': 0,
                            'endIndex': len(last_name) + 3
                        },
                        'textStyle': {
                            'fontSize': {'magnitude': 12, 'unit': 'PT'},
                            'weightedFontFamily': {'fontFamily': 'Times New Roman'}
                        },
                        'fields': 'fontSize,weightedFontFamily'
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
            # First, set up 1-inch margins
            margin_requests = [{
                'updateDocumentStyle': {
                    'documentStyle': {
                        'marginTop': {'magnitude': 72, 'unit': 'PT'},
                        'marginBottom': {'magnitude': 72, 'unit': 'PT'},
                        'marginLeft': {'magnitude': 72, 'unit': 'PT'},
                        'marginRight': {'magnitude': 72, 'unit': 'PT'}
                    },
                    'fields': 'marginTop,marginBottom,marginLeft,marginRight'
                }
            }]
            
            self.docs_service.documents().batchUpdate(
                documentId=document_id,
                body={'requests': margin_requests}
            ).execute()

            # Create header for page number
            header_requests = [{'createHeader': {'type': 'DEFAULT'}}]
            self.docs_service.documents().batchUpdate(
                documentId=document_id,
                body={'requests': header_requests}
            ).execute()

            # Get header ID
            doc = self.docs_service.documents().get(documentId=document_id).execute()
            header_id = doc.get('headers', {}).popitem()[0]

            # Get current date
            current_date = datetime.now().strftime('%B %d, %Y')

            # Calculate content with proper spacing
            content = (
                f"{class_name}\n"  # Title at the top
                f"{name}\n"  # Author name
                f"{professor}\n"  # Professor
                f"{class_name}\n"  # Course name
                f"{current_date}"  # Date
            )
            
            requests = [
                # Add page number to header (right-aligned)
                {
                    'insertText': {
                        'location': {'segmentId': header_id, 'index': 0},
                        'text': "1"
                    }
                },
                # Right align page number
                {
                    'updateParagraphStyle': {
                        'range': {'segmentId': header_id, 'startIndex': 0, 'endIndex': 1},
                        'paragraphStyle': {'alignment': 'END'},
                        'fields': 'alignment'
                    }
                },
                # Main content
                {
                    'insertText': {
                        'location': {'index': 1},
                        'text': content
                    }
                },
                # Center align all content
                {
                    'updateParagraphStyle': {
                        'range': {'startIndex': 1, 'endIndex': len(content) + 1},
                        'paragraphStyle': {
                            'alignment': 'CENTER',
                            'lineSpacing': 240,  # Double spacing
                            'spaceAbove': {'magnitude': 0, 'unit': 'PT'},  # Remove extra space above paragraphs
                            'spaceBelow': {'magnitude': 0, 'unit': 'PT'}   # Remove extra space below paragraphs
                        },
                        'fields': 'alignment,lineSpacing,spaceAbove,spaceBelow'
                    }
                },
                # Apply Times New Roman, 12pt to entire document
                {
                    'updateTextStyle': {
                        'range': {'startIndex': 1, 'endIndex': len(content) + 1},
                        'textStyle': {
                            'fontSize': {'magnitude': 12, 'unit': 'PT'},
                            'weightedFontFamily': {'fontFamily': 'Times New Roman'}
                        },
                        'fields': 'fontSize,weightedFontFamily'
                    }
                },
                # Apply Times New Roman, 12pt to header
                {
                    'updateTextStyle': {
                        'range': {
                            'segmentId': header_id,
                            'startIndex': 0,
                            'endIndex': 1
                        },
                        'textStyle': {
                            'fontSize': {'magnitude': 12, 'unit': 'PT'},
                            'weightedFontFamily': {'fontFamily': 'Times New Roman'}
                        },
                        'fields': 'fontSize,weightedFontFamily'
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
            
            # Get current semester
            current_date = datetime.now()
            semester = 'Spring' if current_date.month < 7 else 'Fall'
            semester_name = f"{semester} {current_date.year}"
            
            # Look up folder in current semester
            semester_ref = db.reference(f'users/{self.user_id}/semesters/{semester_name}/folders')
            folders = semester_ref.get()
            
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
        """Creates a simple Google Sheets document for the assignment."""
        try:
            # Build the sheets service
            sheets_service = build('sheets', 'v4', credentials=self.creds)
            
            # Create spreadsheet with assignment name
            spreadsheet_body = {
                'properties': {
                    'title': assignment_data['name']
                }
            }
            
            # Create the spreadsheet
            spreadsheet = sheets_service.spreadsheets().create(
                body=spreadsheet_body
            ).execute()
            
            spreadsheet_id = spreadsheet.get('spreadsheetId')

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
        """Creates a simple Google Slides presentation for the assignment."""
        try:
            # Build the slides service
            slides_service = build('slides', 'v1', credentials=self.creds)
            
            # Create presentation with assignment name
            presentation = slides_service.presentations().create(
                body={'title': assignment_data['name']}
            ).execute()
            
            presentation_id = presentation.get('presentationId')
            
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
        """Create a new Google Doc formatted for notes and move it to notes subfolder"""
        try:
            # Create an empty document
            doc_body = {
                'title': doc_name
            }
            doc = self.docs_service.documents().create(body=doc_body).execute()
            document_id = doc.get('documentId')

            # Get the notes folder ID from Firebase
            current_date = datetime.now()
            semester = 'Spring' if current_date.month < 7 else 'Fall'
            semester_name = f"{semester} {current_date.year}"
            
            # Look up the notes folder ID
            semester_ref = db.reference(f'users/{self.user_id}/semesters/{semester_name}/folders')
            folders = semester_ref.get()
            
            notes_folder_id = None
            if folders:
                for folder_data in folders.values():
                    if folder_data.get('folder_id') == folder_id:
                        notes_folder_id = folder_data.get('notes_folder_id')
                        break

            if not notes_folder_id:
                print(f"Warning: Notes folder not found, using main folder")
                notes_folder_id = folder_id

            # Move document to notes folder
            if not self.move_to_folder(document_id, notes_folder_id):
                print(f"Warning: Failed to move document to notes folder")

            return {
                'document_id': document_id,
                'title': doc_name,
                'url': f'https://docs.google.com/document/d/{document_id}/edit'
            }

        except Exception as e:
            print(f"Error creating notes document: {e}")
            return None

    def get_folder_documents_content(self, class_name: str) -> Optional[List[str]]:
        try:
            
            if not self.user_id:
                return None
            
            # Get credentials from Firebase
            creds = self._get_credentials()
            if not creds:
                return None
            
            # Build services with Firebase credentials
            self.drive_service = build('drive', 'v3', credentials=creds)
            self.docs_service = build('docs', 'v1', credentials=creds)

            # Get folder IDs
            folder_ids = self._get_folder_ids(class_name)
            if not folder_ids:
                return None
            
            
            contents = []
            for folder_id in folder_ids:
                try:
                    # First, verify we can access the folder
                    try:
                        folder = self.drive_service.files().get(
                            fileId=folder_id,
                            fields="name, mimeType, permissions"
                        ).execute()
                    except Exception as e:
                        continue
                    
                    # List all files the user has access to
                    page_token = None
                    while True:
                        # Get all files with detailed information
                        response = self.drive_service.files().list(
                            q=f"mimeType='application/vnd.google-apps.document'",
                            spaces='drive',
                            fields='nextPageToken, files(id, name, mimeType, parents)',
                            pageToken=page_token,
                            pageSize=1000,
                            orderBy='modifiedTime desc'
                        ).execute()
                        
                        files = response.get('files', [])
                        print(f"Retrieved {len(files)} files in this batch")
                        
                        # Filter files that belong to our folder
                        matching_files = [
                            f for f in files 
                            if 'parents' in f and folder_id in f['parents']
                        ]
                        
                        
                        # Process matching files
                        for file in matching_files:
                            try:
                                document = self.docs_service.documents().get(
                                    documentId=file['id']
                                ).execute()
                                
                                content = ''
                                for element in document.get('body', {}).get('content', []):
                                    if 'paragraph' in element:
                                        for para_element in element['paragraph']['elements']:
                                            if 'textRun' in para_element:
                                                content += para_element['textRun'].get('content', '')
                        
                                if content.strip():
                                    contents.append(content)
                                
                            except Exception as e:
                                print(f"Error processing document {file.get('name')}: {str(e)}")
                                continue
                        
                        page_token = response.get('nextPageToken')
                        if not page_token:
                            break
                            
                except Exception as e:
                    continue
            
            if contents:
                return contents
                
            return None
            
        except Exception as e:
            return None

    def _get_folder_ids(self, class_name: str) -> List[str]:
        """Helper method to get folder IDs from Firebase"""
        try:
            current_date = datetime.now()
            semester = 'Spring' if current_date.month < 7 else 'Fall'
            semester_name = f"{semester} {current_date.year}"
            
            semester_ref = db.reference(f'users/{self.user_id}/semesters/{semester_name}/folders')
            folders = semester_ref.get()
            
            folder_ids = []
            if folders:
                for folder_data in folders.values():
                    if folder_data.get('name') == class_name:
                        if folder_data.get('folder_id'):
                            folder_ids.append(folder_data.get('folder_id'))
                        if folder_data.get('notes_folder_id'):
                            folder_ids.append(folder_data.get('notes_folder_id'))
                        break
                    
            return folder_ids
        except Exception as e:
            print(f"Error getting folder IDs: {str(e)}")
            return []

    def create_semester_folders(self, class_names: list, parent_folder_id: str = None) -> bool:
        """Creates new folders for a new semester's classes."""
        try:
            if not self.user_id:
                return False
            
            # If no parent folder provided, get the user's root folder from Firebase
            if not parent_folder_id:
                user_ref = db.reference(f'users/{self.user_id}')
                user_data = user_ref.get()
                if not user_data or 'google_parent_folder' not in user_data:
                    return False
                parent_folder_id = user_data['google_parent_folder']

            # Create semester folder
            current_date = datetime.now()
            semester = 'Spring' if current_date.month < 7 else 'Fall'
            semester_name = f"{semester} {current_date.year}"
            
            semester_metadata = {
                'name': semester_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_folder_id]
            }
            
            semester_folder = self.drive_service.files().create(
                body=semester_metadata,
                fields='id'
            ).execute()
            
            semester_folder_id = semester_folder.get('id')
            
            # Create folders for each class
            created_folders = []
            for class_name in class_names:
                try:
                    # Create main class folder
                    folder_metadata = {
                        'name': class_name,
                        'mimeType': 'application/vnd.google-apps.folder',
                        'parents': [semester_folder_id]
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
                    
                    notes_folder_id = notes_folder.get('id')
                    
                    # Save folder info to Firebase with both IDs
                    self._save_semester_folder_info(
                        semester_name=semester_name,
                        class_name=class_name,
                        folder_data={
                            'folder_id': folder_id,
                            'notes_folder_id': notes_folder_id
                        }
                    )
                    
                    created_folders.append(folder_id)
                    
                except Exception as e:
                    print(f'Error creating folder for {class_name}: {e}')
                    continue
                    
            return len(created_folders) > 0
            
        except Exception as e:
            print(f"Error creating semester folders: {e}")
            return False

    def _save_semester_folder_info(self, semester_name: str, class_name: str, folder_data: dict):
        """Saves semester folder information to Firebase with notes subfolder"""
        try:
            if not self.user_id:
                return False
            
            # Create a reference to the semester folders
            semester_ref = db.reference(f'users/{self.user_id}/semesters/{semester_name}/folders')
            
            # Create a unique key for the folder
            folder_key = class_name.replace('.', '_').replace('/', '_').replace(' ', '_')
            
            # Store folder information with notes folder ID
            semester_ref.child(folder_key).set({
                'name': class_name,
                'folder_id': folder_data['folder_id'],
                'notes_folder_id': folder_data['notes_folder_id'],
                'created_at': datetime.now().isoformat()
            })
            
            return True
            
        except Exception as e:
            print(f"Error saving semester folder info: {e}")
            return False

    def check_new_semester(self, canvas_service) -> bool:
        """Checks if a new semester has started and creates folders if needed.
        
        Args:
            canvas_service: Instance of CanvasService to get current classes
            
        Returns:
            bool: True if new semester was detected and folders were created
        """
        try:
            if not self.user_id:
                return False
            
            # Get current semester
            current_date = datetime.now()
            current_semester = 'Spring' if current_date.month < 7 else 'Fall'
            current_semester_name = f"{current_semester} {current_date.year}"
            
            # Check if we already have folders for this semester
            semester_ref = db.reference(f'users/{self.user_id}/semesters/{current_semester_name}')
            existing_semester = semester_ref.get()
            
            if existing_semester:
                return False  # Semester folders already exist
            
            # Get current classes from Canvas
            current_classes = canvas_service.get_classes()
            if not current_classes:
                return False
            
            class_names = [course['name'] for course in current_classes]
            
            # Create new folders for the semester
            return self.create_semester_folders(class_names)
            
        except Exception as e:
            print(f"Error checking for new semester: {e}")
            return False

    def _save_credentials_to_firebase(self, creds):
        """Saves Google credentials to Firebase for the current user."""
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