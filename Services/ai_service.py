import google.generativeai as genai
from typing import Optional, List
from googleapiclient.discovery import build
import speech_recognition as sr
import os
from dotenv import load_dotenv
from PIL import Image

# Load environment variables from .env file
load_dotenv()

class AIService:
    def __init__(self):
        self._configure_gemini()
        self.model = genai.GenerativeModel('gemini-pro')
        self.recognizer = sr.Recognizer()

    def _configure_gemini(self):
        """Configure Gemini AI with API key."""
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

    def transcribe_speech(self) -> Optional[str]:
        """Convert speech to text.
        Listens continuously until 'exit' is typed in terminal."""
        try:
            with sr.Microphone() as source:
                print("Starting transcription...")
                print("Type 'exit' in terminal to stop listening")
                
                # Adjust for ambient noise
                print("Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                
                transcribed_text = []
                
                while True:
                    print("\nListening... Speak now")
                    try:
                        audio = self.recognizer.listen(source, timeout=None)
                        print("Audio captured, processing...")
                        
                        # Check if user typed 'exit'
                        if input().lower().strip() == 'exit':
                            break
                        
                        # Try services in order of reliability
                        try:
                            # Try Google Web Speech API first
                            text = self.recognizer.recognize_google(audio)
                            transcribed_text.append(text)
                            print(f"Transcribed: {text}")
                        except sr.UnknownValueError:
                            try:
                                # Fallback to Sphinx (offline)
                                text = self.recognizer.recognize_sphinx(audio)
                                transcribed_text.append(text)
                                print(f"Transcribed (Sphinx): {text}")
                            except:
                                print("Speech not recognized")
                                
                    except sr.WaitTimeoutError:
                        continue
                        
                return " ".join(transcribed_text) if transcribed_text else None
                print(f"Transcribed text: {transcribed_text}")
                
        except Exception as e:
            print(f"Unexpected error during transcription: {e}")
            return None

    def summarize_text(self, text: str) -> Optional[str]:
        """Generate a summary of the provided text."""
        try:
            if not text or not text.strip():
                raise ValueError("Empty text provided")
            
            prompt = f"""Please provide a concise summary of the following text, 
            highlighting the key points and main ideas:
            
            {text}"""
            
            response = self.model.generate_content(prompt)
            
            if not response:
                raise Exception("No response received from Gemini API")
            
            if not response.text:
                raise Exception("Empty response received from Gemini API")
            
            return response.text.strip()
            
        except Exception as e:
            print(f"Error generating summary: {str(e)}")
            raise Exception(f"Failed to generate summary: {str(e)}")

    def recommend_videos(self, prompt: str, max_results: int = 3) -> Optional[List[dict]]:
        """Recommend YouTube videos based on a topic."""
        try:
            print(f"Starting video search for prompt: {prompt}")  # Debug log
            
            # Search YouTube directly with the prompt
            youtube = build('youtube', 'v3', developerKey=os.getenv('YOUTUBE_API_KEY'))
            
            response = youtube.search().list(
                part="snippet",
                maxResults=max_results,
                q=prompt,
                type="video",
                relevanceLanguage="en",
                videoEmbeddable="true"
            ).execute()
            
            # Format the videos
            videos = []
            for item in response['items']:
                video = {
                    'title': item['snippet']['title'],
                    'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                    'description': item['snippet']['description']
                }
                videos.append(video)
                print(f"Found video: {video['title']}")  # Debug log
            
            return videos
            
        except Exception as e:
            print(f"Error recommending videos: {e}")
            return None

    def create_lecture_summary(self, duration: int) -> Optional[str]:
        """Create a summary from spoken lecture."""
        try:
            print(f"Starting lecture summary for duration: {duration}")  # Debug log
            
            text = self.transcribe_speech()
            print(f"Transcribed text: {text}")  # Debug log
            
            if not text:
                raise ValueError("No transcription available - speech not detected or understood")
            
            summary = self.summarize_text(text)
            print(f"Generated summary: {summary}")  # Debug log
            
            return summary
            
        except Exception as e:
            print(f"Error in create_lecture_summary: {str(e)}")
            raise Exception(f"Failed to create summary: {str(e)}")

    def get_homework_help(self, assignment_name: str, course_name: str, 
                         description: str) -> Optional[str]:
        """Get AI assistance for homework."""
        try:
            prompt = f"""Do this assignment for my {course_name} class: {assignment_name}
            Assignment Description: {description}
            
            Please answer like a college student, following these rules:
            - Use complete sentences and clear language
            - Write in paragraph form with proper indentation
            - Use double spacing
            - Include only the assignment content
            - No headers, footers, or special formatting
            
            Format the response as plain text without any Markdown or special characters."""
            
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Error getting homework help: {e}")
            return None    

    def AI_Chat_Bot(self, prompt: str) -> Optional[str]:
        """Get a response from AI for any given prompt."""
        try:
            if not prompt or not prompt.strip():
                raise ValueError("Empty prompt provided")
            
            # Add instruction for shorter response
            prompt = f"Please provide a brief, concise response (2-3 sentences max) to: {prompt}"
            response = self.model.generate_content(prompt)
            
            if not response:
                raise Exception("No response received from Gemini API")
            
            if not response.text:
                raise Exception("Empty response received from Gemini API")
            
            # Clean up the response by removing asterisks
            cleaned_response = response.text.strip().replace('*', '')
            return cleaned_response
            
        except Exception as e:
            print(f"Error getting AI response: {str(e)}")
            return None

    def generate_image(self, prompt: str, 
                      height: int = 1024, 
                      width: int = 1024,
                      seed: Optional[int] = None) -> Optional[Image.Image]:
        """Return the default icon."""
        try:
            return Image.open("@default_icon.png")
        except Exception as e:
            print(f"Error loading default icon: {str(e)}")
            return None

    def create_video_search_prompt(self, assignment_name: str, description: str) -> Optional[str]:
        """Create an optimized YouTube search prompt from assignment details."""
        try:
            if not assignment_name or not description:
                print("Missing assignment name or description")
                return None
            
            # Clean and validate inputs
            assignment_name = str(assignment_name).strip()
            description = str(description).strip()
            
            prompt = f"""Given this assignment:
            Title: {assignment_name}
            Description: {description}

            Create a concise, focused YouTube search query that will find educational videos 
            explaining the core concepts needed to complete this assignment. 
            The query should:
            - Be 2-3 key phrases
            - Focus on the main topic or skill needed
            - Use common educational terminology
            - Exclude assignment-specific details
            
            Return only the search query, no other text."""
            
            try:
                response = self.model.generate_content(prompt)
                
                if not response:
                    print("No response received from Gemini API")
                    return None
                    
                if not hasattr(response, 'text'):
                    print("Response missing text attribute")
                    return None
                    
                text = response.text
                if not text or not isinstance(text, str):
                    print("Invalid response text")
                    return None
                    
                # Clean up and format the response
                search_query = text.strip().replace('\n', ' ')
                print(f"Generated search query: {search_query}")  # Debug log
                return search_query
                
            except AttributeError as e:
                print(f"Attribute error with Gemini response: {e}")
                return None
                
        except Exception as e:
            print(f"Error creating video search prompt: {e}")
            return None
    
    def generate_quiz(self, documents_content: List[str]) -> dict:
        """Generate a quiz from the provided documents content."""
        try:
            if not documents_content:
                return None
            
            # Combine all documents content
            combined_content = "\n\n".join(documents_content)
            
            # Generate multiple choice questions
            mc_prompt = f"""Based on the following notes, create 5 multiple choice questions.
            Format each question as:
            Q: [Question]
            A) [Option A]
            B) [Option B]
            C) [Option C]
            D) [Option D]
            CORRECT: [Correct letter]

            Notes:
            {combined_content}"""
            
            mc_response = self.model.generate_content(mc_prompt)
            if not mc_response or not mc_response.text:
                return None
            
            # Split the response into questions and answers
            mc_parts = mc_response.text.strip().split('\n\n')
            mc_questions = []
            mc_answers = []
            
            for part in mc_parts:
                lines = part.split('\n')
                if len(lines) >= 6:  # Question + 4 options + correct answer
                    # Clean up the question and options by removing asterisks
                    cleaned_lines = [line.replace('*', '').replace('**', '') for line in lines[:5]]
                    mc_questions.append('\n'.join(cleaned_lines))  # Question and options
                    mc_answers.append(lines[5].replace('CORRECT:', '').strip())
            
            # Generate written response questions
            wr_prompt = f"""Based on the following notes, create 3 short answer questions 
            that test understanding of key concepts.
            Format as:
            Q: [Question]
            A: [Expected answer key points]

            Notes:
            {combined_content}"""
            
            wr_response = self.model.generate_content(wr_prompt)
            if not wr_response or not wr_response.text:
                return None
            
            # Split written response into questions and answers
            wr_parts = wr_response.text.strip().split('\n\n')
            wr_questions = []
            wr_answers = []
            
            for part in wr_parts:
                if 'Q:' in part and 'A:' in part:
                    q_part = part.split('A:')[0].replace('Q:', '').strip().replace('*', '').replace('**', '')
                    a_part = part.split('A:')[1].strip().replace('*', '').replace('**', '')
                    wr_questions.append(q_part)
                    wr_answers.append(a_part)
            
            return {
                'multiple_choice': {
                    'questions': mc_questions,
                    'answers': mc_answers
                },
                'written_response': {
                    'questions': wr_questions,
                    'answers': wr_answers
                }
            }
            
        except Exception as e:
            print(f"Error generating quiz: {str(e)}")
            return None

    def find_learning_resources(self, topic: str) -> Optional[List[dict]]:
        """Find diverse learning resources on a given topic."""
        try:
            if not topic or not isinstance(topic, str):
                raise ValueError("Invalid topic provided")
            
            # Create a prompt to get search terms for different resource types
            prompt = f"""For the topic '{topic}', generate 5 specific search queries that would help find:
            - Academic papers/journals
            - Online courses
            - Tutorial websites
            - Educational videos
            - Documentation/guides
            Return only the search queries, one per line."""
            
            # Get optimized search terms
            response = self.model.generate_content(prompt)
            if not response or not response.text:
                raise Exception("Failed to generate search terms")
            
            search_terms = response.text.strip().split('\n')
            
            # Initialize YouTube API
            youtube = build('youtube', 'v3', developerKey=os.getenv('YOUTUBE_API_KEY'))
            
            resources = []
            
            # Get more YouTube videos
            video_response = youtube.search().list(
                part="snippet",
                maxResults=5,
                q=topic,
                type="video",
                relevanceLanguage="en",
                videoEmbeddable="true"
            ).execute()
            
            for item in video_response['items']:
                resources.append({
                    'title': item['snippet']['title'],
                    'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                    'type': 'Video Tutorial'
                })
            
            # Generate other resource suggestions using AI
            resource_prompt = f"""Generate 8 high-quality learning resources for '{topic}'. 
            For each resource provide exactly three pieces of information in this format:
            Title | URL | Type
            
            Include a mix of:
            - Academic papers or journal articles
            - Online courses (from platforms like Coursera, edX)
            - Documentation or guide websites
            - Interactive tutorial websites
            
            Each line should contain exactly three items separated by | characters."""
            
            response = self.model.generate_content(resource_prompt)
            if not response or not response.text:
                raise Exception("Failed to generate resources")
            
            # Parse AI-generated resources
            for line in response.text.strip().split('\n'):
                parts = line.split('|')
                if len(parts) == 3:  # Only process lines with exactly 3 parts
                    title, url, res_type = [x.strip() for x in parts]
                    resources.append({
                        'title': title,
                        'url': url,
                        'type': res_type
                    })
            
            return resources[:10]  # Ensure we return max 10 resources
            
        except Exception as e:
            print(f"Error finding learning resources: {e}")
            return None

    def summarize_url_content(self, url: str) -> Optional[str]:
        """Generate a summary of the content from a URL."""
        try:
            # Import requests here to avoid circular imports
            import requests
            from bs4 import BeautifulSoup
            
            # Fetch the webpage content
            response = requests.get(url)
            response.raise_for_status()
            
            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract main content (you might need to adjust this based on the websites you want to support)
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Clean up the text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            # Use the existing summarize_text method
            return self.summarize_text(text)
            
        except Exception as e:
            print(f"Error summarizing URL content: {str(e)}")
            raise Exception(f"Failed to summarize URL content: {str(e)}")


if __name__ == "__main__":
    # Create an instance of AIService
    ai_service = AIService()
    # Call the method on the instance
    ai_service.transcribe_speech()