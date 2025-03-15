from typing import List, Dict, Optional
import requests
from canvasapi import Canvas
from datetime import datetime, timedelta
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
        self.cache_duration = 300
        
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
            print(f"Canvas API returned {len(result)} courses")
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

    def sync_assignments_to_firebase(self):
        """Sync assignments to Firebase for the current month"""
        try:
            if not self.user_id:
                print("No user ID provided")
                return False

            # Get all assignments
            assignments = self.get_all_assignments()
            
            # Filter and format assignments for current month
            current_date = datetime.now()
            current_month_assignments = {}
            
            for assignment in assignments:
                if assignment.get('due_at'):
                    due_date = datetime.strptime(assignment['due_at'], '%Y-%m-%dT%H:%M:%SZ')
                    
                    # Only process assignments for current month
                    if (due_date.year == current_date.year and 
                        due_date.month == current_date.month):
                        
                        date_key = due_date.strftime('%Y-%m-%d')
                        if date_key not in current_month_assignments:
                            current_month_assignments[date_key] = []
                            
                        current_month_assignments[date_key].append({
                            'name': assignment.get('name'),
                            'course_name': assignment.get('course_name', ''),
                            'due_at': assignment.get('due_at'),
                            'id': assignment.get('id'),
                            'course_id': assignment.get('course_id')
                        })

            # Store in Firebase
            month_key = current_date.strftime('%Y-%m')
            db_ref = db.reference(f'users/{self.user_id}/calendar_assignments/{month_key}')
            db_ref.set(current_month_assignments)
            
            # Store last sync timestamp
            db.reference(f'users/{self.user_id}/last_calendar_sync').set({
                'timestamp': datetime.now().isoformat(),
                'month': month_key
            })
            
            return True
            
        except Exception as e:
            print(f"Error syncing assignments to Firebase: {str(e)}")
            return False

    def get_course(self, course_id: int) -> Optional[Dict]:
        """Get details for a specific course."""
        endpoint = f"{self.canvas_url}/api/v1/courses/{course_id}"
        params = {
            'include[]': ['term', 'teachers']
        }
        
        try:
            response = requests.get(endpoint, headers=self.get_headers(), params=params)
            response.raise_for_status()
            course = response.json()
            
            # Add teacher info if available
            if 'teachers' in course and course['teachers']:
                course['professor'] = course['teachers'][0]['display_name']
            else:
                course['professor'] = 'Not Available'
            
            return course
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching course {course_id}: {e}")
            return None

    def get_course_syllabus(self, course_id: int) -> Optional[Dict]:
        """Get the syllabus for a specific course.
        
        Args:
            course_id (int): The Canvas course ID
            
        Returns:
            Optional[Dict]: Dictionary containing syllabus body and course name,
                           or None if syllabus couldn't be retrieved
        """
        cache_key = f'syllabus_{course_id}'
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        endpoint = f"{self.canvas_url}/api/v1/courses/{course_id}"
        params = {
            'include[]': ['syllabus_body']
        }
        
        try:
            response = requests.get(endpoint, headers=self.get_headers(), params=params)
            response.raise_for_status()
            course_data = response.json()
            
            result = {
                'course_name': course_data.get('name', 'Unknown Course'),
                'syllabus_body': course_data.get('syllabus_body', ''),
                'has_syllabus': bool(course_data.get('syllabus_body'))
            }
            
            self._set_cached_data(cache_key, result)
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching syllabus for course {course_id}: {e}")
            return None

    def get_current_classes(self) -> List[Dict]:
        """Get user's current classes (classes in progress)"""
        cache_key = 'current_classes'
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data

        # First get all active classes
        all_classes = self.get_classes()
        
        if not all_classes:
            print("No classes found from Canvas API")
            return []
        
        # Determine current semester based on date
        current_time = datetime.now()
        # Spring: January-May, Summer: June-July, Fall: August-December
        if 1 <= current_time.month <= 5:
            current_semester = 'Spring'
        elif 6 <= current_time.month <= 7:
            current_semester = 'Summer'
        else:  # 8-12
            current_semester = 'Fall'
        
        current_year = current_time.year
        print(f"Current semester determined to be: {current_semester} {current_year}")
        
        # Filter for classes in the current semester
        current_classes = []
        
        for course in all_classes:
            # Skip classes that are explicitly marked as completed or concluded
            if course.get('workflow_state') == 'completed' or course.get('concluded', False):
                continue
            
            # Check term information if available
            if 'term' in course and course['term']:
                term = course['term']
                term_name = term.get('name', '').lower()
                
                # Extract term information from the name
                # Most Canvas instances use format like "2025 Spring" or "Spring 2025"
                if not term_name:
                    continue
                    
                # Check if this is a current term course by looking for current year and semester
                is_current_term = False
                
                # Check for current year in term name
                if str(current_year) in term_name:
                    # Check for current semester in term name
                    if current_semester.lower() in term_name:
                        is_current_term = True
                
                # If not current term, skip this course
                if not is_current_term:
                    continue
                
                # If we get here, it's a current term course
                current_classes.append(course)
            else:
                # If no term info, use course dates as fallback
                if course.get('start_at') and course.get('end_at'):
                    start_date = datetime.strptime(course['start_at'], '%Y-%m-%dT%H:%M:%SZ')
                    end_date = datetime.strptime(course['end_at'], '%Y-%m-%dT%H:%M:%SZ')
                    
                    # If current date is between start and end dates, include this course
                    if start_date <= current_time <= end_date:
                        current_classes.append(course)
        
        # Cache the result
        self._set_cached_data(cache_key, current_classes)
        return current_classes

    def get_current_grades(self) -> List[Dict]:
        """Get grades for all current classes
        
        Returns:
            List[Dict]: List of dictionaries containing course information with grades
        """
        cache_key = 'current_grades'
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
            
        # Get current classes first
        current_classes = self.get_current_classes()
        
        if not current_classes:
            print("No current classes found")
            return []
            
        # Fetch grades for each current class
        classes_with_grades = []
        
        for course in current_classes:
            course_id = course['id']
            course_info = {
                'id': course_id,
                'name': course.get('name', 'Unknown Course'),
                'code': course.get('course_code', ''),
            }
            
            # Get professor name if available
            if 'teachers' in course and course['teachers']:
                course_info['professor'] = course['teachers'][0]['display_name']
            else:
                course_info['professor'] = 'Not Available'
                
            # Get grade information
            grade_data = self.get_grades(course_id)
            if grade_data:
                course_info['grade_percentage'] = grade_data.get('percentage')
                course_info['grade_letter'] = grade_data.get('letter')
            else:
                course_info['grade_percentage'] = None
                course_info['grade_letter'] = 'N/A'
                
            classes_with_grades.append(course_info)
            
        # Cache the results
        self._set_cached_data(cache_key, classes_with_grades)
        return classes_with_grades