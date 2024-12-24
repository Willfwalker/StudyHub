from typing import List, Dict, Optional
import requests
from canvasapi import Canvas
from datetime import datetime
from os import getenv
from dotenv import load_dotenv
from functools import lru_cache
import time
import os
from firebase_admin import db

class CanvasService:
    def __init__(self, user_id=None):
        # Initialize cache
        self._cache = {}
        self.cache_duration = 300  # Cache duration in seconds (5 minutes)
        
        self.user_id = user_id
        self.api_key = None
        self.canvas_url = None
        
        if user_id:
            try:
                user_ref = db.reference(f'users/{user_id}')
                user_data = user_ref.get()
                
                if user_data:
                    self.api_key = user_data.get('canvas_api_key')
                    self.canvas_url = user_data.get('canvas_url', getenv('CANVAS_URL'))
                    
                    if not self.api_key:
                        print(f"No Canvas API key found for user {user_id}")
                    if not self.canvas_url:
                        print(f"No Canvas URL found for user {user_id}")
                else:
                    print(f"No user data found for user {user_id}")
                    
            except Exception as e:
                print(f"Error initializing CanvasService: {str(e)}")
                raise

    def get_headers(self):
        if not self.api_key:
            raise ValueError("Canvas API key not found for user")
        return {
            'Authorization': f'Bearer {self.api_key}'
        }

    def _format_canvas_url(self, url: str) -> str:
        """Format Canvas URL consistently"""
        if not url.startswith('http'):
            url = f"https://{url}"
        return url.rstrip('/')

    def _get_cached_data(self, key):
        """Get cached data if it exists and is not expired"""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time.time() - timestamp < self.cache_duration:
                return data
        return None

    def _set_cached_data(self, key, data):
        """Cache data with current timestamp"""
        self._cache[key] = (data, time.time())

    @lru_cache(maxsize=32)
    def get_user_name(self) -> Optional[str]:
        """Get current user's full name (cached)"""
        endpoint = f"{self.canvas_url}/api/v1/users/self"
        try:
            response = requests.get(endpoint, headers=self.get_headers())
            response.raise_for_status()
            return response.json().get('name')
        except requests.exceptions.RequestException as e:
            print(f"Error getting user name: {str(e)}")
            return None

    def get_classes(self) -> List[Dict]:
        """Get user's active classes (cached)"""
        cache_key = 'classes'
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data

        endpoint = f"{self.canvas_url}/api/v1/courses"
        params = {
            'enrollment_state': 'active',
            'include[]': ['term', 'teachers'],
            'per_page': 100
        }
        try:
            response = requests.get(endpoint, headers=self.get_headers(), params=params)
            response.raise_for_status()
            result = response.json()
            self._set_cached_data(cache_key, result)
            return result
        except requests.exceptions.RequestException as e:
            print(f"Error fetching courses: {e}")
            return []

    def get_course_professor(self, course_id: int) -> Optional[str]:
        """Get professor name for a specific course"""
        try:
            course = self.canvas.get_course(course_id)
            teachers = course.get_users(enrollment_type=['teacher'])
            for teacher in teachers:
                return teacher.name
            return None
        except Exception as e:
            print(f"Error: {str(e)}")
            return None

    def _percentage_to_letter_grade(self, percentage: float) -> str:
        """Convert percentage to letter grade"""
        if percentage is None:
            return 'N/A'
        
        if percentage >= 93: return 'A'
        elif percentage >= 90: return 'A-'
        elif percentage >= 87: return 'B+'
        elif percentage >= 83: return 'B'
        elif percentage >= 80: return 'B-'
        elif percentage >= 77: return 'C+'
        elif percentage >= 73: return 'C'
        elif percentage >= 70: return 'C-'
        elif percentage >= 67: return 'D+'
        elif percentage >= 63: return 'D'
        elif percentage >= 60: return 'D-'
        else: return 'F'

    def get_grades(self, course_id: int) -> Optional[float]:
        """Get grades for a specific course"""
        endpoint = f"{self.canvas_url}/api/v1/courses/{course_id}/enrollments"
        params = {
            "type[]": ["StudentEnrollment"],
            "user_id": "self",
            "include[]": ["current_grade", "current_score"],
            "per_page": 100
        }
        try:
            response = requests.get(endpoint, headers=self.get_headers(), params=params)
            response.raise_for_status()
            enrollments = response.json()
            
            # Return the first enrollment that has grade data
            for enrollment in enrollments:
                grades = enrollment.get('grades', {})
                current_score = grades.get('current_score')
                if current_score is not None:
                    return {
                        'percentage': current_score,
                        'letter': self._percentage_to_letter_grade(current_score)
                    }
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching grades for course {course_id}: {e}")
            return None

    def get_current_assignments(self, course_id: int) -> List[Dict]:
        """Get current assignments for a specific course"""
        endpoint = f"{self.canvas_url}/api/v1/courses/{course_id}/assignments"
        params = {
            "order_by": "due_at",
            "include[]": ["submission"],
            "bucket": "upcoming",
            "per_page": 100
        }
        try:
            response = requests.get(endpoint, headers=self.get_headers(), params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching assignments: {e}")
            return []

    def get_all_assignments(self) -> List[Dict]:
        """Get all assignments (cached)"""
        try:
            if not self.api_key or not self.canvas_url:
                print("Missing API key or Canvas URL")
                return []

            cache_key = 'all_assignments'
            cached_data = self._get_cached_data(cache_key)
            if cached_data:
                return cached_data

            assignments = []
            # First get all active courses
            courses = self.get_classes()
            if not courses:
                print("No courses found")
                return []
            
            # Then get assignments for each course
            for course in courses:
                try:
                    course_id = course['id']
                    endpoint = f"{self.canvas_url}/api/v1/courses/{course_id}/assignments"
                    params = {
                        "include[]": ["submission"],
                        "per_page": 100
                    }
                    
                    response = requests.get(endpoint, headers=self.get_headers(), params=params)
                    response.raise_for_status()
                    course_assignments = response.json()
                    
                    # Add course information to each assignment
                    for assignment in course_assignments:
                        if assignment.get('due_at'):  # Only include assignments with due dates
                            assignment['course_name'] = course.get('name')
                            assignment['course_id'] = course_id
                            assignments.append(assignment)
                            
                except Exception as course_error:
                    print(f"Error fetching assignments for course {course.get('name', 'Unknown')}: {str(course_error)}")
                    continue
                    
            self._set_cached_data(cache_key, assignments)
            return assignments
            
        except Exception as e:
            print(f"Error in get_all_assignments: {str(e)}")
            return []

    def get_current_year(self) -> Optional[str]:
        """Get student's current academic year"""
        try:
            user = self.canvas.get_current_user()
            enrollments = user.get_enrollments()
            
            total_credits = 0
            for enrollment in enrollments:
                if hasattr(enrollment, 'grades') and enrollment.grades.get('final_score'):
                    if enrollment.grades['final_score'] >= 60:
                        total_credits += 3
            
            if total_credits < 30:
                return "Freshman"
            elif total_credits < 60:
                return "Sophomore"
            elif total_credits < 90:
                return "Junior"
            else:
                return "Senior"
        except Exception as e:
            print(f"Error determining year: {str(e)}")
            return None

    def get_user_profile_picture(self) -> Optional[str]:
        """Get current user's profile picture URL"""
        endpoint = f"{self.canvas_url}/api/v1/users/self/avatars"
        try:
            response = requests.get(endpoint, headers=self.get_headers())
            response.raise_for_status()
            avatars = response.json()
            # Return the URL of the first avatar (usually the current one)
            return avatars[0]['url'] if avatars else None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching profile picture: {str(e)}")
            return None

    def get_past_assignments(self, course_id: int) -> List[Dict]:
        """Get past assignments with grades for a specific course."""
        endpoint = f"{self.canvas_url}/api/v1/courses/{course_id}/assignments"
        params = {
            "include[]": ["submission"],
            "order_by": "due_at",
            "per_page": 100
        }
        try:
            response = requests.get(endpoint, headers=self.get_headers(), params=params)
            response.raise_for_status()
            assignments = response.json()
            
            past_assignments = []
            current_time = datetime.now()
            
            for assignment in assignments:
                if assignment.get('due_at'):
                    due_date = datetime.strptime(assignment['due_at'], '%Y-%m-%dT%H:%M:%SZ')
                    if due_date < current_time:
                        submission = assignment.get('submission', {})
                        past_assignments.append({
                            'id': assignment['id'],
                            'name': assignment['name'],
                            'score': submission.get('score'),
                            'points_possible': assignment.get('points_possible'),
                            'submitted_at': submission.get('submitted_at'),
                            'due_at': assignment['due_at']
                        })
            
            past_assignments.sort(key=lambda x: x['submitted_at'] if x['submitted_at'] else '', reverse=True)
            return past_assignments
            
        except Exception as e:
            print(f"Error fetching past assignments: {e}")
            return []

    def get_assignment_details(self, course_id: int, assignment_id: int) -> Optional[Dict]:
        """Get detailed information about a specific assignment."""
        try:
            # Get assignment details
            endpoint = f"{self.canvas_url}/api/v1/courses/{course_id}/assignments/{assignment_id}"
            response = requests.get(endpoint, headers=self.get_headers())
            response.raise_for_status()
            assignment = response.json()

            # Get course details to get professor name
            course_endpoint = f"{self.canvas_url}/api/v1/courses/{course_id}"
            course_response = requests.get(course_endpoint, headers=self.get_headers())
            course_response.raise_for_status()
            course = course_response.json()

            # Get professor name from course
            professor = None
            if 'teachers' in course:
                professor = course['teachers'][0]['display_name'] if course['teachers'] else None
            else:
                # Try to get teacher info through enrollments
                enrollments_endpoint = f"{self.canvas_url}/api/v1/courses/{course_id}/enrollments"
                enrollments_response = requests.get(
                    enrollments_endpoint,
                    params={'type[]': 'TeacherEnrollment'},
                    headers=self.get_headers()
                )
                enrollments_response.raise_for_status()
                enrollments = enrollments_response.json()
                if enrollments:
                    professor = enrollments[0]['user']['name']

            # Get submission if it exists
            submission = assignment.get('submission', {})

            return {
                'title': assignment.get('name', 'Untitled Assignment'),
                'professor': professor or 'Not Available',
                'description': assignment.get('description', 'No description available'),
                'due_date': assignment.get('due_at'),
                'points_possible': assignment.get('points_possible', 'N/A'),
                'submission_types': assignment.get('submission_types', []),
                'course_id': course_id,
                'assignment_id': assignment_id,
                'grade': submission.get('grade', 'Not Graded'),
                'submitted': submission.get('submitted_at'),
                'status': 'Submitted' if submission.get('submitted_at') else 'Not Submitted'
            }

        except Exception as e:
            print(f"Error getting assignment details: {e}")
            return None

    def submit_assignment(self, course_id: int, assignment_id: int, file_content: bytes) -> Dict:
        """Submit a file to a Canvas assignment."""
        try:
            # First, get upload URL from Canvas
            endpoint = f"{self.canvas_url}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/self/files"
            params = {
                'name': 'assignment_submission.pdf',
                'content_type': 'application/pdf',
                'size': len(file_content)
            }
            
            response = requests.post(
                endpoint,
                headers=self.get_headers(),
                params=params
            )
            response.raise_for_status()
            upload_data = response.json()

            # Upload the file to the provided URL
            upload_url = upload_data.get('upload_url')
            upload_params = upload_data.get('upload_params', {})
            
            files = {
                'file': ('assignment_submission.pdf', file_content, 'application/pdf')
            }
            
            upload_response = requests.post(
                upload_url,
                data=upload_params,
                files=files
            )
            upload_response.raise_for_status()
            file_data = upload_response.json()

            # Submit the uploaded file
            submit_endpoint = f"{self.canvas_url}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions"
            submit_data = {
                'submission': {
                    'submission_type': 'online_upload',
                    'file_ids': [file_data['id']]
                }
            }
            
            submit_response = requests.post(
                submit_endpoint,
                headers=self.get_headers(),
                json=submit_data
            )
            submit_response.raise_for_status()
            submission = submit_response.json()

            return {
                'success': True,
                'submission_id': submission.get('id')
            }

        except Exception as e:
            print(f"Error submitting assignment: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }