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

app = Flask(__name__, static_folder='static')
app.debug = True
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')
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

# Initialize Firebase with all required configurations
try:
    # Get credentials path from environment variable
    cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
    
    # Debug: Print the contents of the credentials file (BE CAREFUL with sensitive info)
    try:
        with open(cred_path, 'r') as f:
            cred_content = f.read()
            print(f"Credential file length: {len(cred_content)} characters")
            print(f"Credential file starts with: {cred_content[:50]}...")  # Only print start of file
    except Exception as file_error:
        print(f"Error reading credentials file: {str(file_error)}")
    
    cred = credentials.Certificate(cred_path)
    firebase_app = initialize_app(cred, {
        'databaseURL': 'https://student-hub-28ea1-default-rtdb.firebaseio.com/'
    })
    print("Firebase initialized successfully")
    
    # Test the database connection immediately
    test_ref = db.reference('test')
    test_ref.set({'test': 'connection successful'})
    print("Database connection test successful")
    
except Exception as e:
    print(f"Firebase initialization error: {str(e)}")
    print(f"Error type: {type(e).__name__}")
    if hasattr(e, 'args'):
        print(f"Error args: {e.args}")

# Test the database connection
def test_db_connection():
    try:
        ref = db.reference('test')
        ref.set({'test': 'connection successful'})
        print("Database connection successful")
    except Exception as e:
        print(f"Database connection error: {str(e)}")

# Call this function when your app starts
test_db_connection()

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'studyhubservice@gmail.com'
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_USE_SSL'] = False

mail = Mail(app)

def get_class_image(class_name, course_code=None):
    """Get image URL for a class using predefined images from class_images.json"""
    try:
        # Load the predefined images once and cache in memory
        if not hasattr(get_class_image, '_class_images'):
            with open('static/images/cache/class_images.json', 'r') as f:
                get_class_image._class_images = json.load(f)
        
        # Try course code first
        if course_code:
            dept_code = course_code.split('-')[0]
            if dept_code in get_class_image._class_images:
                return get_class_image._class_images[dept_code]['pexels_image']
        
        # Try class name match
        for dept_code, info in get_class_image._class_images.items():
            if dept_code in class_name.upper():
                return info['pexels_image']
        
        return url_for('static', filename='images/classes/default.jpg')
        
    except Exception as e:
        print(f"Error getting class image: {str(e)}")
        return url_for('static', filename='images/classes/default.jpg')

@app.template_filter('format_date')
def format_date(date_str):
    if not date_str or date_str == 'No due date':
        return 'No due date'
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ')
        return date_obj.strftime('%m/%d')  # This will output like "11/13"
    except:
        return date_str

@app.template_filter('timestamp_to_date')
def timestamp_to_date(timestamp):
    try:
        dt = datetime.fromtimestamp(int(timestamp))
        return dt.strftime('%B %d, %Y at %I:%M %p')
    except:
        return 'Invalid date'

# Add this decorator function near the top of your app.py
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# Add this new function to handle image caching
def cache_class_images(classes):
    """Cache class images to avoid reloading them on every request"""
    cache_dir = Path('static/images/cache')
    cache_file = cache_dir / 'class_image_cache.json'
    
    # Create cache directory if it doesn't exist
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Load existing cache if it exists
    cached_images = {}
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            cached_images = json.load(f)
    
    # Update cache with new class images
    for class_obj in classes:
        class_id = str(class_obj['id'])
        if class_id not in cached_images:
            cached_images[class_id] = get_class_image(
                class_obj['name'],
                class_obj.get('course_code', '')
            )
    
    # Save updated cache
    with open(cache_file, 'w') as f:
        json.dump(cached_images, f)
    
    return cached_images
# Modify the dashboard route to use cached images
@app.route('/base')
@login_required
def base():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))
            
        # Initialize Canvas service with user_id
        canvas_service = CanvasService(user_id)
        
        if not canvas_service.api_key:
            return redirect(url_for('login'))
            
        return render_template('base.html')
        
    except Exception as e:
        print(f"Error in base route: {str(e)}")
        return redirect(url_for('login'))

def make_cache_key(*args, **kwargs):
    """Create a cache key based on the user ID and route name"""
    # Get the current route name
    route = request.endpoint or 'default'
    return f'{route}-{session.get("user_id", "")}'

@app.route('/')
@app.route('/dashboard')
@login_required
@cache.cached(timeout=3600, key_prefix=make_cache_key)  # Will create keys like "dashboard-user_id"
def dashboard():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))

        # Initialize services
        canvas_service = CanvasService(user_id)
        docs_service = DocsService(user_id)
        
        # Check for new semester and create folders if needed
        docs_service.check_new_semester(canvas_service)
        
        # Get classes and cache their images
        classes = canvas_service.get_classes()
        cached_images = cache_class_images(classes)
        
        # Calculate homework status
        current_time = datetime.now()
        overdue_count = 0
        upcoming_count = 0
        
        # Get all assignments across all classes
        for class_obj in classes:
            assignments = canvas_service.get_current_assignments(class_obj['id'])
            if assignments:
                for assignment in assignments:
                    if assignment.get('due_at'):
                        due_date = datetime.strptime(assignment['due_at'], '%Y-%m-%dT%H:%M:%SZ')
                        if due_date < current_time:
                            # Check if assignment is submitted
                            if not assignment.get('has_submitted_submissions', False):
                                overdue_count += 1
                        elif due_date < current_time + timedelta(days=7):  # Due within next 7 days
                            upcoming_count += 1

        # Determine homework status
        if overdue_count > 0:
            homework_status = "red"  # Behind on homework
        elif upcoming_count >= 3:
            homework_status = "yellow"  # Good bit of homework upcoming
        else:
            homework_status = "green"  # All caught up

        total_points = 0
        total_classes = 0
        
        # Use cached images instead of fetching new ones
        for class_obj in classes:
            class_id = str(class_obj['id'])
            class_obj['image_path'] = cached_images.get(class_id, url_for('static', filename='images/classes/default.jpg'))
            
            # Get grades for this class
            grades = canvas_service.get_grades(class_obj['id'])
            
            if grades is None:
                class_obj['current_score'] = 'N/A'
            elif isinstance(grades, dict) and 'percentage' in grades:
                class_obj['current_score'] = grades['percentage']
                class_obj['letter_grade'] = grades.get('letter', '')
                
                if grades['percentage'] is not None:
                    # Convert percentage to 4.0 scale
                    if grades['percentage'] >= 93:
                        gpa_points = 4.0
                    elif grades['percentage'] >= 90:
                        gpa_points = 3.7
                    elif grades['percentage'] >= 87:
                        gpa_points = 3.3
                    elif grades['percentage'] >= 83:
                        gpa_points = 3.0
                    elif grades['percentage'] >= 80:
                        gpa_points = 2.7
                    elif grades['percentage'] >= 77:
                        gpa_points = 2.3
                    elif grades['percentage'] >= 73:
                        gpa_points = 2.0
                    elif grades['percentage'] >= 70:
                        gpa_points = 1.7
                    elif grades['percentage'] >= 67:
                        gpa_points = 1.3
                    elif grades['percentage'] >= 63:
                        gpa_points = 1.0
                    elif grades['percentage'] >= 60:
                        gpa_points = 0.7
                    else:
                        gpa_points = 0.0
                        
                    total_points += gpa_points
                    total_classes += 1
            else:
                class_obj['current_score'] = 'N/A'
                
        # Calculate current GPA
        current_gpa = round(total_points / total_classes, 2) if total_classes > 0 else 'N/A'
        
        # Get current assignments
        current_assignments = []
        for course in classes:
            assignments = canvas_service.get_current_assignments(course['id'])
            if assignments:
                for assignment in assignments:
                    assignment['course_name'] = course['name']
                    current_assignments.extend(assignments)
        
        return render_template('dashboard.html', 
                             classes=classes,
                             current_gpa=current_gpa,
                             current_assignments=current_assignments,
                             homework_status=homework_status)
                             
    except Exception as e:
        return str(e), 500

# Routes for sidebar navigation
@app.route('/courses')
@login_required
def courses():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))

        canvas_service = CanvasService(user_id)
        courses = canvas_service.get_classes()
        return render_template('courses.html', courses=courses)
    except Exception as e:
        return str(e), 500

@app.route('/study-recommendations')
def study_recommendations():
    # Remove the redirect and just render the template
    return render_template('recommend_videos.html')

@app.route('/api/create-homework-doc', methods=['POST'])
@login_required
def create_homework_doc():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not logged in'}), 401

        data = request.get_json()
        course_id = data.get('course_id')
        assignment_id = data.get('assignment_id')
        doc_type = data.get('doc_type', 'mla')  # Default to MLA if not specified
        check_only = data.get('check_only', False)

        if not course_id or not assignment_id:
            return jsonify({'error': 'Missing course_id or assignment_id'}), 400

        # Initialize services
        canvas_service = CanvasService(user_id)
        docs_service = DocsService(user_id)

        # Check for existing document
        existing_doc = docs_service.get_existing_document(course_id, assignment_id)
        if existing_doc:
            return jsonify({
                'success': True,
                'doc_info': existing_doc
            })

        # If just checking document existence
        if check_only:
            return jsonify({'doc_info': None})

        # Get assignment details
        assignment_details = canvas_service.get_assignment_details(course_id, assignment_id)
        if not assignment_details:
            return jsonify({'error': 'Assignment not found'}), 404

        # Get course details
        courses = canvas_service.get_classes()
        course = next((c for c in courses if c['id'] == course_id), None)
        if not course:
            return jsonify({'error': 'Course not found'}), 404

        # Prepare assignment data
        assignment_data = {
            'name': assignment_details['title'],
            'course_name': course['name'],
            'student_name': canvas_service.get_user_name(),
            'professor': assignment_details.get('professor', 'Professor'),
            'course_id': course_id,
            'assignment_id': assignment_id
        }

        # Create document based on type
        doc_info = None
        if doc_type == 'mla':
            doc_info = docs_service.create_mla_document(assignment_data)
        elif doc_type == 'apa':
            doc_info = docs_service.create_apa_document(assignment_data)
        elif doc_type == 'sheets':
            doc_info = docs_service.create_spreadsheet(assignment_data)
        elif doc_type == 'slides':
            doc_info = docs_service.create_presentation(assignment_data)
        else:
            return jsonify({'error': 'Invalid document type'}), 400

        if not doc_info:
            return jsonify({'error': 'Failed to create document'}), 500

        # Store document info in Firebase
        docs_service.store_document_info(course_id, assignment_id, doc_info)

        return jsonify({
            'success': True,
            'doc_info': doc_info
        })

    except Exception as e:
        print(f"Error in create_homework_doc: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/assignments')
@login_required
def assignments():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))

        # Initialize Canvas service with user_id
        canvas_service = CanvasService(user_id=user_id)
        
        if not canvas_service.api_key:
            return redirect(url_for('login'))

        courses = canvas_service.get_classes()
        
        # Get assignments for each course
        assignments = []
        for course in courses:
            course_assignments = canvas_service.get_current_assignments(course['id'])
            if course_assignments:
                for assignment in course_assignments:
                    assignment['course_name'] = course['name']
                    assignments.append(assignment)
        
        return render_template('assignments.html', 
                             assignments=assignments)
                             
    except Exception as e:
        print(f"Error in assignments route: {str(e)}")
        return str(e), 500

@app.route('/make-hw-doc')
def make_hw_doc():
    canvas_service = CanvasService()
    courses = canvas_service.get_classes()
    
    # Get assignments for each course
    assignments = []
    for course in courses:
        course_assignments = canvas_service.get_current_assignments(course['id'])
        for assignment in course_assignments:
            assignments.append({
                'index': len(assignments),
                'name': assignment['name'],
                'course_name': course['name'],
                'due_date': format_date(assignment.get('due_at', 'No due date')),
                'course_id': course['id'],
                'assignment_id': assignment['id']
            })
    
    return render_template('make_hw_doc.html', assignments=assignments)

@app.route('/summarize-text', methods=['GET'])
@app.route('/summarize-text/', methods=['GET'])
def summarize_text():
    return render_template('summarize_text.html')

@app.route('/api/summarize-text', methods=['POST'])
@csrf.exempt
def api_summarize_text():
    try:
        text = request.json.get('text')
        if not text:
            return jsonify({'error': 'No text provided'}), 400

        ai_service = AIService()
        try:
            summary = ai_service.summarize_text(text)
            if summary:
                return jsonify({'summary': summary})
            else:
                return jsonify({'error': 'Failed to generate summary - empty response'}), 500
        except Exception as e:
            print(f"AI Service error: {str(e)}")
            return jsonify({'error': str(e)}), 500
            
    except Exception as e:
        print(f"API error: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/recommend-videos', methods=['POST'])
@csrf.exempt
def api_recommend_videos():
    try:
        prompt = request.json.get('prompt')
        if not prompt:
            return jsonify({'error': 'No prompt provided'}), 400

        ai_service = AIService()
        try:
            video_urls = ai_service.recommend_videos(prompt)
            if video_urls:
                return jsonify({'videos': video_urls})
            else:
                return jsonify({'error': 'Failed to get video recommendations'}), 500
        except Exception as e:
            print(f"AI Service error: {str(e)}")
            return jsonify({'error': str(e)}), 500
            
    except Exception as e:
        print(f"API error: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/recommend-videos')
def recommend_videos():
    prompt = request.args.get('prompt', '')
    videos = []
    
    if prompt:
        ai_service = AIService()
        try:
            videos = ai_service.recommend_videos(prompt)
        except Exception as e:
            print(f"Error getting video recommendations: {e}")
    
    return render_template('recommend_videos.html', videos=videos, prompt=prompt)

@app.route('/video-prompt')
def video_prompt():
    return render_template('video_prompt.html')

@app.route('/grades')
@app.route('/check-grades')
@login_required
@cache.cached(timeout=3600, key_prefix=make_cache_key)  # Will create keys like "check_grades-user_id"
def check_grades():
    try:
        user_id = session.get('user_id')
        if not user_id:
            print("No user_id in session")
            return redirect(url_for('login'))
                
        try:
            # Test Firebase connection
            user_ref = db.reference(f'users/{user_id}')
            user_data = user_ref.get()
            print(f"Firebase user data: {user_data}")
            
            if not user_data:
                return render_template('check_grades.html', 
                                    courses=[], 
                                    error="User data not found. Please log in again.")
                                    
            if not user_data.get('canvas_api_key'):
                return render_template('check_grades.html', 
                                    courses=[], 
                                    error="Canvas API key not found. Please update your profile.")
                                    
        except Exception as firebase_error:
            print(f"Firebase error: {str(firebase_error)}")
            return render_template('check_grades.html', 
                                courses=[], 
                                error="Error accessing user data. Please try logging in again.")

        # Initialize Canvas service
        canvas_service = CanvasService(user_id)
        
        if not canvas_service.api_key:
            return render_template('check_grades.html', 
                                courses=[], 
                                error="Canvas API key not found. Please update your profile.")

        # Get courses and grades
        courses = canvas_service.get_classes()
        courses_with_grades = []
        
        for course in courses:
            grades = canvas_service.get_grades(course['id'])
            course_data = {
                'name': course['name'],
                'grade': grades.get('percentage', 'N/A') if isinstance(grades, dict) else 'N/A'
            }
            courses_with_grades.append(course_data)
        
        return render_template('check_grades.html', 
                             courses=courses_with_grades,
                             error=None)
                             
    except Exception as e:
        print(f"Error in check_grades: {str(e)}")
        return render_template('check_grades.html', 
                             courses=[], 
                             error="An unexpected error occurred. Please try again later.")

@app.route('/create-lecture-summary')
def create_lecture_summary():
    return render_template('create_lecture_summary.html')

@app.route('/sidebar')
def sidebar():
    return render_template('sidebar.html')

@app.route('/api/create-lecture-summary', methods=['POST'])
@csrf.exempt
def api_create_lecture_summary():
    try:
        duration = request.json.get('duration')
        if not duration:
            return jsonify({'error': 'No duration provided'}), 400

        ai_service = AIService()
        try:
            summary = ai_service.create_lecture_summary(duration)
            if summary:
                return jsonify({'summary': summary})
            else:
                return jsonify({'error': 'Failed to create summary - empty response'}), 500
        except Exception as e:
            print(f"AI Service error: {str(e)}")
            return jsonify({'error': str(e)}), 500
            
    except Exception as e:
        print(f"API error: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/lecture-summary-result')
def lecture_summary_result():
    summary = request.args.get('summary', '')
    return render_template('lecture_summary_result.html', summary=summary)

@app.route('/get-hw-help', methods=['GET'])
def get_hw_help():
    print("Rendering homework help page")
    return render_template('get_hw_help.html')

@app.route('/api/get-hw-help', methods=['POST'])
@csrf.exempt
def api_get_hw_help():
    try:
        prompt = request.json.get('prompt')
        if not prompt:
            return jsonify({'error': 'No prompt provided'}), 400

        ai_service = AIService()
        response = ai_service.get_ai_response(prompt)
        if response:
            return jsonify({'response': response})
        else:
            return jsonify({'error': 'Failed to get AI response'}), 500
            
    except Exception as e:
        print(f"API error: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/todo-list')
@login_required
def todo_list():
    return render_template('to-do_list_creator.html')

@app.route('/api/generate-todo-pdf', methods=['POST'])
@csrf.exempt
def generate_todo_pdf():
    try:
        data = request.json
        title = data.get('title', 'Todo List')
        items = data.get('items', [])
        
        canvas_service = CanvasService()
        pdf_path = canvas_service.create_todo_list(title, items)
        
        if pdf_path and os.path.exists(pdf_path):
            return send_file(
                pdf_path,
                mimetype='application/pdf',
                as_attachment=True,
                download_name='todo_list.pdf'
            )
        else:
            return jsonify({'error': 'Failed to generate PDF'}), 500
            
    except Exception as e:
        print(f"API error: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/get-assignments')
@login_required
@cache.cached(timeout=300)
def get_assignments_api():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not logged in'}), 401

        canvas_service = CanvasService(user_id=user_id)
        
        if not canvas_service.api_key:
            return jsonify({'error': 'Canvas API key not found'}), 401

        assignments = canvas_service.get_all_assignments()
        
        # Pre-process assignments to reduce payload size
        formatted_assignments = []
        current_time = datetime.now()
        two_months_ago = current_time - timedelta(days=60)
        two_months_ahead = current_time + timedelta(days=60)
        
        for assignment in assignments:
            if assignment.get('due_at'):
                due_date = datetime.strptime(assignment['due_at'], '%Y-%m-%dT%H:%M:%SZ')
                
                # Only include assignments within a 4-month window
                if two_months_ago <= due_date <= two_months_ahead:
                    formatted_assignments.append({
                        'id': assignment.get('id'),
                        'name': assignment.get('name'),
                        'due_at': assignment.get('due_at'),
                        'course_id': assignment.get('course_id'),
                        'course_name': assignment.get('course_name'),
                        'points_possible': assignment.get('points_possible')
                    })

        return jsonify(formatted_assignments)
        
    except Exception as e:
        print(f"Error fetching assignments: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/assignment-details/<int:course_id>/<int:assignment_id>')
def get_assignment_details(course_id, assignment_id):
    try:
        canvas_service = CanvasService()
        assignments = canvas_service.get_current_assignments(course_id)
        
        # Find the specific assignment
        assignment = next((a for a in assignments if a['id'] == assignment_id), None)
        
        if assignment:
            # Get the course name
            courses = canvas_service.get_classes()
            course = next((c for c in courses if c['id'] == course_id), None)
            if course:
                assignment['course_name'] = course['name']
            
            return jsonify(assignment)
        else:
            return jsonify({'error': 'Assignment not found'}), 404
            
    except Exception as e:
        print(f"Error getting assignment details: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.template_filter('get_grade_color')
def get_grade_color(percentage):
    if percentage is None:
        return ''
    try:
        percentage = float(percentage)
        if percentage >= 90:
            return 'grade-a'
        elif percentage >= 80:
            return 'grade-b'
        elif percentage >= 70:
            return 'grade-c'
        elif percentage >= 60:
            return 'grade-d'
        else:
            return 'grade-f'
    except (ValueError, TypeError):
        return ''

@app.route('/course/<int:course_id>')
@login_required
@cache.cached(timeout=3600, key_prefix=lambda: f'course-{session.get("user_id", "")}-{request.view_args.get("course_id", "")}')  # Cache for 1 hour with user and course specific keys
def course_page(course_id):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))

        canvas_service = CanvasService(user_id=user_id)
        
        if not canvas_service.api_key:
            return redirect(url_for('login'))

        # Get course details
        course = next((c for c in canvas_service.get_classes() if c['id'] == course_id), None)
        if not course:
            return "Course not found", 404

        # Get current assignments
        current_assignments = canvas_service.get_current_assignments(course_id)
        
        # Get past assignments
        past_assignments = canvas_service.get_past_assignments(course_id)
        
        # Get the grade info
        grade_info = canvas_service.get_grades(course_id)
        if grade_info:
            course['grade'] = f"{grade_info['percentage']}% ({grade_info['letter']})"
        else:
            course['grade'] = 'N/A'

        # Calculate and format assignment grades
        for assignment in past_assignments:
            if (assignment.get('score') is not None and 
                assignment.get('points_possible') is not None and 
                float(assignment['points_possible']) > 0):
                try:
                    percentage = (float(assignment['score']) / float(assignment['points_possible'])) * 100
                    assignment['percentage'] = percentage
                    assignment['grade'] = f"{int(round(percentage))}%"
                except (ValueError, TypeError):
                    assignment['percentage'] = None
                    assignment['grade'] = 'N/A'
            else:
                assignment['percentage'] = None
                assignment['grade'] = 'N/A'

        return render_template('course_page.html', 
                             course=course,
                             current_assignments=current_assignments,
                             past_assignments=past_assignments)

    except Exception as e:
        print(f"Error in course_page: {str(e)}")
        return str(e), 500

@app.route('/select-assignment-for-videos')
@login_required
def select_assignment_for_videos():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login_page'))

        # Initialize Canvas service with user_id
        canvas_service = CanvasService(user_id=user_id)
        
        # Check if API key exists
        if not canvas_service.api_key:
            # Redirect to profile page or show error message
            return render_template('error.html', 
                error="Canvas API key not found. Please update your profile with a valid Canvas API key.")
        
        current_time = datetime.now()
        two_weeks_future = current_time + timedelta(days=14)
        
        current_assignments = []
        courses = canvas_service.get_classes()
        
        for course in courses:
            try:
                course_assignments = canvas_service.get_current_assignments(course['id'])
                if course_assignments:
                    for assignment in course_assignments:
                        if assignment.get('due_at'):
                            due_date = datetime.strptime(assignment['due_at'], '%Y-%m-%dT%H:%M:%SZ')
                            if (due_date > current_time - timedelta(days=1) and 
                                due_date < two_weeks_future):
                                # Add course name to assignment
                                assignment['course_name'] = course['name']
                                # Ensure description exists and is a string
                                assignment['description'] = str(assignment.get('description', ''))
                                # Clean description HTML if present
                                if assignment['description']:
                                    # Basic HTML tag removal
                                    description = assignment['description'].replace('<p>', '').replace('</p>', '\n')
                                    assignment['description'] = description.strip()
                                current_assignments.append(assignment)
            except Exception as e:
                print(f"Error processing course {course['name']}: {e}")
                continue
        
        # Sort by due date
        current_assignments.sort(key=lambda x: datetime.strptime(x['due_at'], '%Y-%m-%dT%H:%M:%SZ'))
        
        return render_template('select_assignment_for_videos.html', 
                             assignments=current_assignments)
                             
    except Exception as e:
        print(f"Error in select_assignment_for_videos: {str(e)}")
        return render_template('error.html', error=str(e)), 500

@app.route('/api/get-video-prompt', methods=['POST'])
@csrf.exempt
def api_get_video_prompt():
    try:
        data = request.json
        name = data.get('name')
        description = data.get('description')
        
        if not name:
            return jsonify({'error': 'Assignment name is required'}), 400
            
        # Use a default description if none provided
        description = description or "No description available"
        
        ai_service = AIService()
        search_prompt = ai_service.create_video_search_prompt(name, description)
        
        if search_prompt:
            return jsonify({'prompt': search_prompt})
        else:
            return jsonify({'error': 'Failed to generate search prompt'}), 500
            
    except Exception as e:
        print(f"Error in api_get_video_prompt: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/graphing-calculator')
def graphing_calculator():
    return render_template('desmos.html')

@app.route('/assignment/<int:course_id>/<int:assignment_id>')
@login_required
def assignment_details(course_id, assignment_id):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))

        # Initialize Canvas service with user_id
        canvas_service = CanvasService(user_id=user_id)
        
        if not canvas_service.api_key:
            return redirect(url_for('login'))

        details = canvas_service.get_assignment_details(course_id, assignment_id)
        
        if not details:
            return "Assignment not found", 404
            
        # Add submission types if not present
        if 'submission_types' not in details:
            details['submission_types'] = []
            
        # Ensure all required fields are present
        required_fields = ['title', 'professor', 'description', 'due_date', 
                         'points_possible', 'submission_types', 'course_id']
        for field in required_fields:
            if field not in details:
                details[field] = 'N/A'
                
        return render_template('assignment_details.html', assignment=details)
        
    except Exception as e:
        print(f"Error in assignment_details: {str(e)}")
        return str(e), 500

@app.route('/api/notifications')
@login_required
def get_notifications():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify([])

        # Initialize empty notifications list
        # In the future, you can fetch these from your database
        notifications = []

        return jsonify(notifications)

    except Exception as e:
        print(f"Error fetching notifications: {str(e)}")
        return jsonify([]), 500

@app.route('/api/todo', methods=['GET', 'POST'])
def handle_todo():
    if request.method == 'GET':
        # Implement todo list fetching
        return jsonify(get_todo_list())
    elif request.method == 'POST':
        data = request.json
        # Implement adding new todo item
        return jsonify(add_todo_item(data['task']))

@app.route('/api/todo/<int:task_id>/toggle', methods=['POST'])
def toggle_todo(task_id):
    # Implement todo item toggling
    return jsonify({'success': True})

@app.route('/api/todo/<int:task_id>', methods=['DELETE'])
def delete_todo(task_id):
    # Implement todo item deletion
    return jsonify({'success': True})

def get_todo_list():
    # Implement todo list storage and retrieval
    return []

def add_todo_item(task_text):
    # Implement todo item addition
    return {'id': 1, 'text': task_text, 'completed': False}

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    firebase_config = {
        'FIREBASE_API_KEY': os.getenv('FIREBASE_API_KEY'),
        'FIREBASE_AUTH_DOMAIN': os.getenv('FIREBASE_AUTH_DOMAIN'),
        'FIREBASE_PROJECT_ID': os.getenv('FIREBASE_PROJECT_ID'),
        'FIREBASE_STORAGE_BUCKET': os.getenv('FIREBASE_STORAGE_BUCKET'),
        'FIREBASE_MESSAGING_SENDER_ID': os.getenv('FIREBASE_MESSAGING_SENDER_ID'),
        'FIREBASE_APP_ID': os.getenv('FIREBASE_APP_ID')
    }
    return render_template('index.html', config=firebase_config)
            
@app.route('/api/login', methods=['POST'])
def handle_login():
    try:
        # Get the ID token from the request
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        if 'idToken' not in data:
            return jsonify({'error': 'No ID token provided'}), 400

        id_token = data['idToken']

        try:
            # Add clock tolerance when verifying the token
            decoded_token = auth.verify_id_token(
                id_token,
                check_revoked=True,
                clock_skew_seconds=60
            )
            
            # Get the user's ID from the decoded token
            user_id = decoded_token['uid']
            
            # Store user info in session
            session['user_id'] = user_id
            session['email'] = decoded_token.get('email', '')
            
            # Set session expiry
            session.permanent = True
            
            # Return a properly formatted JSON response
            return jsonify({
                'success': True,
                'redirect': url_for('dashboard')
            })

        except auth.InvalidIdTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        except auth.ExpiredIdTokenError:
            return jsonify({'error': 'Token expired'}), 401
        except auth.RevokedIdTokenError:
            return jsonify({'error': 'Token revoked'}), 401
        except auth.UserDisabledError:
            return jsonify({'error': 'User disabled'}), 401
        except Exception as e:
            return jsonify({
                'error': 'Authentication error',
                'details': str(e)
            }), 400

    except Exception as e:
        print(f"Login error: {str(e)}")
        return jsonify({
            'error': 'Server error',
            'details': str(e)
        }), 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        firebase_config = {
            'FIREBASE_API_KEY': os.getenv('FIREBASE_API_KEY'),
            'FIREBASE_AUTH_DOMAIN': os.getenv('FIREBASE_AUTH_DOMAIN'),
            'FIREBASE_PROJECT_ID': os.getenv('FIREBASE_PROJECT_ID'),
            'FIREBASE_STORAGE_BUCKET': os.getenv('FIREBASE_STORAGE_BUCKET'),
            'FIREBASE_MESSAGING_SENDER_ID': os.getenv('FIREBASE_MESSAGING_SENDER_ID'),
            'FIREBASE_APP_ID': os.getenv('FIREBASE_APP_ID')
        }
        return render_template('register.html', config=firebase_config)

@app.route('/api/register', methods=['POST'])
def api_register():
    try:
        data = request.get_json()
        email = data.get('email')
        uid = data.get('uid')
        canvas_api_key = data.get('canvas_api_key')
        canvas_url = data.get('canvas_url', getenv('CANVAS_URL'))
        google_folder_link = data.get('google_folder_link')
        
        if not all([email, uid, canvas_api_key, canvas_url, google_folder_link]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400
            
        # Extract folder ID from Google Drive link
        folder_id = None
        if 'folders' in google_folder_link:
            folder_id = google_folder_link.split('folders/')[-1].split('?')[0]
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid Google Drive folder link'
            }), 400

        # Store in Firebase Realtime Database
        try:
            db_ref = db.reference('users')
            user_data = {
                'email': email,
                'canvas_api_key': canvas_api_key,
                'canvas_url': canvas_url,
                'google_parent_folder': folder_id,
                'created_at': str(datetime.now()),
                'setup_complete': True
            }
            
            # Store the data
            db_ref.child(uid).set(user_data)
            
            # Initialize services
            canvas_service = CanvasService(uid)
            docs_service = DocsService(uid)
            
            # Get classes from Canvas
            classes = canvas_service.get_classes()
            if not classes:
                raise Exception("Unable to fetch classes from Canvas")
                
            class_names = [course['name'] for course in classes]
            
            # Create semester-based folders in Google Drive
            created_folders = docs_service.create_semester_folders(class_names, folder_id)
            
            if not created_folders:
                return jsonify({
                    'success': False,
                    'error': 'Failed to create semester folders'
                }), 500

            return jsonify({
                'success': True,
                'message': 'Registration successful',
                'redirect': url_for('dashboard')
            })
            
        except Exception as e:
            print(f"Database error: {str(e)}")
            raise
            
    except Exception as e:
        print(f"Registration error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/verify-registration', methods=['POST'])
def verify_registration():
    try:
        data = request.get_json()
        uid = data.get('uid')
        
        if not uid:
            return jsonify({
                'success': False,
                'error': 'No UID provided'
            }), 400
            
        # Check if the data exists in Firebase
        db_ref = db.reference(f'users/{uid}')
        user_data = db_ref.get()
        
        return jsonify({
            'success': bool(user_data and 'canvas_api_key' in user_data),
            'data': user_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Add a test route
@app.route('/test')
def test():
    return jsonify({'session': dict(session)})

@app.route('/logout')
def logout():
    try:
        user_id = session.get('user_id')
        if user_id:
            # Delete Google token when logging out
            docs_service = DocsService(user_id)
            docs_service.delete_token()
            
        session.clear()
        return redirect(url_for('login_page'))
    except Exception as e:
        print(f"Logout error: {str(e)}")
        return redirect(url_for('login_page'))

app.permanent_session_lifetime = timedelta(days=5)  # Set session lifetime
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=5)

@app.route('/clear-image-cache')
@login_required
def clear_image_cache():
    try:
        cache_file = Path('static/images/cache/class_image_cache.json')
        if cache_file.exists():
            cache_file.unlink()
        return jsonify({'success': True, 'message': 'Image cache cleared'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/calendar')
@login_required
def show_calendar():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))

        # Get current date info
        today = datetime.now()
        year = today.year
        month = today.month
        month_key = today.strftime('%Y-%m')

        # Check if we need to sync assignments
        user_ref = db.reference(f'users/{user_id}')
        last_sync = user_ref.child('last_calendar_sync').get()
        
        canvas_service = CanvasService(user_id)
        
        # Sync if:
        # 1. No last sync data
        # 2. Different month
        # 3. Last sync was more than 1 hour ago
        should_sync = True
        if last_sync:
            last_sync_time = datetime.fromisoformat(last_sync.get('timestamp'))
            time_diff = datetime.now() - last_sync_time
            if (last_sync.get('month') == month_key and 
                time_diff.total_seconds() < 3600):  # 1 hour
                should_sync = False

        if should_sync:
            canvas_service.sync_assignments_to_firebase()

        # Get assignments from Firebase
        assignments_ref = db.reference(
            f'users/{user_id}/calendar_assignments/{month_key}'
        )
        stored_assignments = assignments_ref.get() or {}

        # Convert stored assignments to the format needed by the template
        assignment_dict = {}
        for date_str, assignments in stored_assignments.items():
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            assignment_dict[date_obj] = assignments

        # Create calendar data structure
        calendar_data = []
        month_range = calendar.monthrange(year, month)
        prev_month_days = (datetime(year, month, 1).weekday() + 1) % 7
        
        # Get previous month's days if needed
        if prev_month_days > 0:
            if month == 1:
                prev_month = 12
                prev_year = year - 1
            else:
                prev_month = month - 1
                prev_year = year
            prev_month_range = calendar.monthrange(prev_year, prev_month)[1]
            prev_month_dates = range(prev_month_range - prev_month_days + 1, 
                                   prev_month_range + 1)
        
        # Build calendar weeks
        current_week = []
        
        # Add previous month's days
        for i in range(prev_month_days):
            date = datetime(prev_year, prev_month, prev_month_dates[i])
            current_week.append({
                'day': prev_month_dates[i],
                'other_month': True,
                'is_today': False,
                'assignments': assignment_dict.get(date.date(), [])
            })
        
        # Add current month's days
        for day in range(1, month_range[1] + 1):
            date = datetime(year, month, day)
            current_week.append({
                'day': day,
                'other_month': False,
                'is_today': date.date() == today.date(),
                'assignments': assignment_dict.get(date.date(), [])
            })
            
            if len(current_week) == 7:
                calendar_data.append(current_week)
                current_week = []
        
        # Add next month's days if needed
        if current_week:
            next_month_day = 1
            while len(current_week) < 7:
                date = datetime(year + (month//12), 
                              ((month % 12) + 1), 
                              next_month_day)
                current_week.append({
                    'day': next_month_day,
                    'other_month': True,
                    'is_today': False,
                    'assignments': assignment_dict.get(date.date(), [])
                })
                next_month_day += 1
            calendar_data.append(current_week)

        return render_template('calendar.html',
                             calendar_data=calendar_data,
                             month_name=calendar.month_name[month],
                             year=year)

    except Exception as e:
        print(f"Error in show_calendar: {str(e)}")
        return render_template('error.html', error=str(e))

@app.route('/profile')
@login_required
def profile():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
        
    canvas_service = CanvasService(user_id)
    
    # Get user information
    user_name = canvas_service.get_user_name()
    user_profile_picture = canvas_service.get_user_profile_picture()
    
    return render_template('profile.html',
                         user_name=user_name,
                         user_profile_picture=user_profile_picture)

@app.route('/api/calendar-events')
@login_required
def get_calendar_events():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not logged in'}), 401

        canvas_service = CanvasService(user_id)
        
        # Add error handling for Canvas service initialization
        if not canvas_service.api_key:
            return jsonify({'error': 'Canvas API key not found'}), 401

        try:
            # Get all assignments
            assignments = canvas_service.get_all_assignments()
            if assignments is None:
                return jsonify({'error': 'Failed to fetch assignments'}), 500
                
            # Convert assignments to calendar events
            events = []
            for assignment in assignments:
                if assignment.get('due_at'):
                    try:
                        events.append({
                            'title': assignment['name'],
                            'date': assignment['due_at'],  # Keep ISO format for proper parsing
                            'course': assignment.get('course_name', 'Unknown Course'),
                            'type': 'assignment',
                            'id': assignment.get('id'),
                            'course_id': assignment.get('course_id')
                        })
                    except Exception as e:
                        print(f"Error processing assignment {assignment.get('name')}: {e}")
                        continue

            return jsonify(events)

        except Exception as canvas_error:
            print(f"Canvas service error: {str(canvas_error)}")
            return jsonify({'error': 'Failed to fetch Canvas data'}), 500

    except Exception as e:
        print(f"Calendar events error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
@csrf.exempt
def api_chat():
    try:
        prompt = request.json.get('prompt')
        if not prompt:
            return jsonify({'error': 'No prompt provided'}), 400

        ai_service = AIService()
        try:
            response = ai_service.AI_Chat_Bot(prompt)
            if response:
                return jsonify({'response': response})
            else:
                return jsonify({'error': 'Failed to get AI response'}), 500
        except Exception as e:
            print(f"AI Service error: {str(e)}")
            return jsonify({'error': str(e)}), 500
            
    except Exception as e:
        print(f"API error: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/study')
@login_required
def study_help():
    return render_template('study_help.html')

@app.route('/api/canvas/classes')
@login_required
def get_canvas_classes():
    try:
        user_id = session.get('user_id')  # Get user_id from session
        if not user_id:
            return jsonify({'error': 'User not logged in'}), 401
            
        canvas_service = CanvasService(user_id)  # Pass the user_id to CanvasService
        classes = canvas_service.get_classes()
        
        # Filter out duplicate classes by name
        unique_classes = {}
        for course in classes:
            if course.get('name') not in unique_classes:
                unique_classes[course.get('name')] = course
                
        return jsonify(list(unique_classes.values()))
        
    except Exception as e:
        print(f"Error getting classes: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/citation-generator')
@login_required
def citation_generator():
    """Route to display the citation generator page"""
    return render_template('citation_generator.html')

@app.route('/api/generate-citation', methods=['POST'])
@csrf.exempt
def api_generate_citation():
    """API endpoint to handle citation generation requests"""
    try:
        data = request.json
        style = data.get('style')
        source_type = data.get('sourceType')
        source_data = data.get('data')
        
        if not all([style, source_type, source_data]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Here you could integrate with a citation service or AI service
        # For now, returning a basic formatted citation
        citation = format_citation(style, source_type, source_data)
        
        return jsonify({'citation': citation})
        
    except Exception as e:
        print(f"Error generating citation: {str(e)}")
        return jsonify({'error': str(e)}), 500

def format_citation(style, source_type, data):
    """Helper function to format citations based on style and source type"""
    try:
        if style == 'apa':
            if source_type == 'book':
                return f"{data.get('author')}. ({data.get('year')}). {data.get('title')}. {data.get('publisher')}."
            elif source_type == 'website':
                return f"{data.get('author')}. ({data.get('year')}). {data.get('title')}. {data.get('website_name')}. {data.get('url')}"
            elif source_type == 'journal':
                return f"{data.get('author')}. ({data.get('year')}). {data.get('article_title')}. {data.get('journal_name')}, {data.get('volume')}({data.get('issue')}), {data.get('pages')}."
            elif source_type == 'newspaper':
                return f"{data.get('author')}. ({data.get('date_published')}). {data.get('article_title')}. {data.get('newspaper_name')}, {data.get('page_number')}."
        
        # Add other citation styles (MLA, Chicago, Harvard) here
        
        return "Citation format not yet implemented"
        
    except Exception as e:
        print(f"Error formatting citation: {str(e)}")
        return "Error formatting citation"

@app.route('/api/submit-doc', methods=['POST'])
@login_required
def submit_doc():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not logged in'}), 401

        data = request.get_json()
        course_id = data.get('course_id')
        assignment_id = data.get('assignment_id')
        document_id = data.get('document_id')

        if not all([course_id, assignment_id, document_id]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Initialize services
        canvas_service = CanvasService(user_id)
        docs_service = DocsService(user_id)

        # Export Google Doc as PDF
        pdf_file = docs_service.export_as_pdf(document_id)
        if not pdf_file:
            return jsonify({'error': 'Failed to export document as PDF'}), 500

        # Submit to Canvas
        submission_result = canvas_service.submit_assignment(
            course_id=course_id,
            assignment_id=assignment_id,
            file_content=pdf_file
        )

        if submission_result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Assignment submitted successfully',
                'submission_id': submission_result.get('submission_id')
            })
        else:
            return jsonify({
                'error': submission_result.get('error', 'Failed to submit assignment')
            }), 500

    except Exception as e:
        print(f"Error in submit_doc: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/submit_bug_report', methods=['POST'])
@csrf.exempt
def submit_bug_report():
    try:
        data = request.json
        topic = data.get('topic')
        message = data.get('message')
        
        msg = Message('Bug Report: ' + topic,
                     sender='studyhubservice@gmail.com',
                     recipients=['studyhubservice@gmail.com'])
        
        msg.body = f"""
        Bug Report Details:
        Topic: {topic}
        Message: {message}
        """
        
        mail.send(msg)
        return jsonify({'success': True, 'message': 'Bug report sent successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/create-notes/<int:course_id>')
@login_required
def create_notes(course_id):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not logged in'}), 401

        canvas_service = CanvasService(user_id)
        docs_service = DocsService(user_id)
        
        # Get course details
        course = next((c for c in canvas_service.get_classes() if c['id'] == course_id), None)
        if not course:
            return jsonify({'error': 'Course not found'}), 404

        # Get current semester folder structure
        current_date = datetime.now()
        semester = 'Spring' if current_date.month < 7 else 'Fall'
        semester_name = f"{semester} {current_date.year}"
        
        # Get folder ID from semester structure
        semester_ref = db.reference(f'users/{user_id}/semesters/{semester_name}/folders')
        folders = semester_ref.get()
        
        if not folders:
            return jsonify({'error': 'No folders found for current semester'}), 404

        # Find the correct folder by matching course name
        folder_id = None
        for folder_data in folders.values():
            if folder_data.get('name') == course['name']:
                folder_id = folder_data.get('folder_id')
                break

        if not folder_id:
            return jsonify({'error': 'Course folder not found'}), 404

        # Create the notes document
        doc_name = f"{course['name']} - Notes {datetime.now().strftime('%m/%d/%Y')}"
        doc_info = docs_service.create_notes_doc(doc_name, folder_id)
        
        if doc_info and doc_info.get('url'):
            return jsonify({'url': doc_info['url']})
        else:
            return jsonify({'error': 'Failed to create notes document'}), 500

    except Exception as e:
        print(f"Error creating notes: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/past-notes')
@login_required
def past_notes():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))

        course_id = request.args.get('course_id')
        course_name = request.args.get('course_name')

        if not course_id or not course_name:
            return "Missing course information", 400

        # Get current semester folder structure
        current_date = datetime.now()
        semester = 'Spring' if current_date.month < 7 else 'Fall'
        semester_name = f"{semester} {current_date.year}"
        
        # Get folder ID from semester structure
        semester_ref = db.reference(f'users/{user_id}/semesters/{semester_name}/folders')
        folders = semester_ref.get()
        
        if not folders:
            return "No folders found for current semester", 404

        # Find the correct folder by matching course name
        folder_url = None
        for folder_data in folders.values():
            if folder_data.get('name') == course_name:
                folder_id = folder_data.get('folder_id')
                if folder_id:
                    folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
                break

        if not folder_url:
            return "Course folder not found", 404

        # Return a script that opens the URL in a new tab
        return f"""
        <script>
            window.open('{folder_url}', '_blank');
            window.history.back();
        </script>
        """

    except Exception as e:
        print(f"Error accessing past notes: {str(e)}")
        return str(e), 500

@app.route('/quiz-maker')
@login_required
def quiz_maker():
    return render_template('quiz_maker.html')

@app.route('/create-quiz/<int:course_id>', methods=['GET', 'POST'])
@login_required
@csrf.exempt
def create_quiz(course_id):
    try:
        print(f"\n=== Starting quiz creation for course_id: {course_id} ===")
        
        user_id = session.get('user_id')
        if not user_id:
            print("Error: No user_id in session")
            if request.method == 'POST':
                return jsonify({"error": "Not logged in"}), 401
            return render_template('error.html', error="Not logged in")
        print(f"User ID: {user_id}")
            
        # Initialize services with user_id
        canvas_service = CanvasService(user_id)
        docs_service = DocsService(user_id)
        print("Services initialized")
        
        # Get course info
        courses = canvas_service.get_classes()
        print(f"Retrieved {len(courses)} courses")
        current_course = next((c for c in courses if str(c['id']) == str(course_id)), None)
        
        if not current_course:
            print(f"Course {course_id} not found in user's courses")
            if request.method == 'POST':
                return jsonify({"error": "Course not found"}), 404
            return render_template('error.html', error="Course not found")
        print(f"Found course: {current_course['name']}")
            
        # Get documents content
        print(f"Retrieving documents for course: {current_course['name']}")
        documents_content = docs_service.get_folder_documents_content(current_course['name'])
        if not documents_content:
            print("No documents content found")
            if request.method == 'POST':
                return jsonify({"error": "No notes found"}), 404
            return render_template('error.html', error="No notes found")
        print(f"Retrieved content from {len(documents_content)} documents")

        # Initialize AI service and generate quiz
        print("Initializing AI service and generating quiz")
        ai_service = AIService()
        quiz = ai_service.generate_quiz(documents_content)
        
        if not quiz:
            print("Failed to generate quiz")
            if request.method == 'POST':
                return jsonify({"error": "Failed to generate quiz"}), 500
            return render_template('error.html', error="Failed to generate quiz")
        print("Quiz generated successfully")
        
        # Store quiz data in session for answer checking
        session['current_quiz'] = quiz
        
        # Return JSON for POST requests, render template for GET requests
        if request.method == 'POST':
            return jsonify(quiz)
        return render_template('quiz_display.html',
                           course=current_course,
                           quiz=quiz)
                                
    except Exception as e:
        print(f"Error in create_quiz: {str(e)}")
        if request.method == 'POST':
            return jsonify({"error": str(e)}), 500
        return render_template('error.html', error=str(e))

@app.template_filter('nl2br')
def nl2br(value):
    """Convert newlines to HTML line breaks"""
    if not value:
        return value
    return value.replace('\n', '<br>')

@app.route('/take-notes')
@login_required
def take_notes():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))

        course_id = request.args.get('course_id')
        course_name = request.args.get('course_name')
        notes_name = request.args.get('notes_name')

        if not all([course_id, course_name, notes_name]):
            return "Missing required parameters", 400

        # Initialize services
        canvas_service = CanvasService(user_id)
        docs_service = DocsService(user_id)

        # Get current semester folder structure
        current_date = datetime.now()
        semester = 'Spring' if current_date.month < 7 else 'Fall'
        semester_name = f"{semester} {current_date.year}"
        
        # Get folder ID from semester structure
        semester_ref = db.reference(f'users/{user_id}/semesters/{semester_name}/folders')
        folders = semester_ref.get()
        
        if not folders:
            return "No folders found for current semester", 404

        # Find the correct folder by matching course name
        folder_id = None
        for folder_data in folders.values():
            if folder_data.get('name') == course_name:
                folder_id = folder_data.get('folder_id')
                break

        if not folder_id:
            return "Course folder not found", 404

        # Create the notes document
        doc_info = docs_service.create_notes_doc(notes_name, folder_id)
        
        if not doc_info:
            return "Failed to create notes document", 500
            
        if not doc_info.get('url'):
            return "Document created but URL not found", 500

        # Success - open in new tab and go back
        return f"""
        <script>
            window.open('{doc_info['url']}', '_blank');
            window.history.back();
        </script>
        """

    except Exception as e:
        print(f"Error creating notes: {str(e)}")
        return str(e), 500

@app.route('/lecture-summary')
def lecture_summary():
    # ... your logic ...
    return render_template('lecture_summary_result.html', summary=summary)

@app.route('/resource-finder')
@login_required
def resource_finder():
    return render_template('resource_finder.html')

@app.route('/api/search-resources', methods=['POST'])
@login_required
def search_resources():
    try:
        data = request.get_json()
        topic = data.get('topic')
        
        if not topic:
            return jsonify({'error': 'No search topic provided'}), 400        
        ai_service = AIService()
        
        # Add error handling around the AI service call
        try:
            resources = ai_service.find_learning_resources(topic)
            
            if resources is None:
                return jsonify({'error': 'Failed to find resources'}), 500
                
            return jsonify(resources)
            
        except Exception as ai_error:
            return jsonify({'error': f'AI Service error: {str(ai_error)}'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/document-summarizer')
@login_required
def document_summarizer():
    return render_template('document_summarizer.html')

@app.route('/api/summarize-url', methods=['POST'])
@csrf.exempt
def api_summarize_url():
    try:
        url = request.json.get('url')
        if not url:
            return jsonify({'error': 'No URL provided'}), 400

        ai_service = AIService()
        try:
            summary = ai_service.summarize_url_content(url)
            if summary:
                return jsonify({'summary': summary})
            else:
                return jsonify({'error': 'Failed to generate summary - empty response'}), 500
        except Exception as e:
            print(f"AI Service error: {str(e)}")
            return jsonify({'error': str(e)}), 500
            
    except Exception as e:
        print(f"API error: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/clear-cache', methods=['POST'])
@login_required
def clear_cache():
    try:
        user_id = session.get('user_id', '')
        
        # Clear all user-specific caches
        cache.delete(f'dashboard-{user_id}')
        cache.delete(f'check_grades-{user_id}')
        cache.delete(f'course-{user_id}')
        
        # Clear any other potential cache keys
        cache.delete_many([
            f'assignments-{user_id}',
            f'calendar-{user_id}',
            f'courses-{user_id}'
        ])
        
        # For debugging
        print(f"Cache cleared for user: {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Cache cleared successfully'
        })
    except Exception as e:
        print(f"Error clearing cache: {str(e)}")
        return jsonify({
            'error': str(e),
            'message': 'Failed to clear cache'
        }), 500

@app.route('/api/sync-calendar', methods=['POST'])
@login_required
def sync_calendar():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not logged in'}), 401

        canvas_service = CanvasService(user_id)
        success = canvas_service.sync_assignments_to_firebase()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Calendar synced successfully'
            })
        else:
            return jsonify({
                'error': 'Failed to sync calendar'
            }), 500
            
    except Exception as e:
        print(f"Error syncing calendar: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/flashcards')
@login_required
def flashcard_maker():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))

        # Initialize Canvas service with user_id
        canvas_service = CanvasService(user_id=user_id)
        
        # Get courses
        courses = canvas_service.get_classes()
        
        return render_template('flashcard_maker.html', courses=courses)
                             
    except Exception as e:
        print(f"Error in flashcard maker route: {str(e)}")
        return str(e), 500

@app.route('/create-flashcards/<int:course_id>')
@login_required
def create_flashcards(course_id):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))

        # Get the requested number of flashcards
        card_count = int(request.args.get('count', 10))
        
        # Initialize services
        canvas_service = CanvasService(user_id)
        docs_service = DocsService(user_id)
        ai_service = AIService()
        
        # Get course info
        courses = canvas_service.get_classes()
        current_course = next((c for c in courses if str(c['id']) == str(course_id)), None)
        
        if not current_course:
            return "Course not found", 404
            
        # Get documents content
        documents_content = docs_service.get_folder_documents_content(current_course['name'])
        if not documents_content:
            return "No notes found for this course", 404

        # Generate flashcards with a small artificial delay to ensure loading state is visible
        time.sleep(0.5)  # Add a small delay to ensure loading state is visible
        flashcards = ai_service.generate_flashcards(documents_content)
        
        if not flashcards:
            return "Failed to generate flashcards", 500

        # Limit to requested number of cards
        flashcards = flashcards[:card_count]
        
        return render_template('flashcards_display.html', 
                             flashcards=flashcards,
                             course=current_course)
                             
    except Exception as e:
        print(f"Error creating flashcards: {str(e)}")
        return str(e), 500

if __name__ == '__main__':
    app.debug = True  
    app.run(debug=True)  