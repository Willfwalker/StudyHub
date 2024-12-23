# Student Hub App

A comprehensive educational automation tool that integrates Canvas LMS, Google Docs, and AI services to help students manage their academic work more efficiently.

## Features

### Canvas Integration
- Fetch course information and assignments
- Get real-time grades and due dates
- Access professor information
- Track academic progress
- View past assignments and grades
- Monitor upcoming deadlines

### Google Docs Automation
- Create formatted homework documents
- Automatic header formatting with student name
- Course-specific document organization
- Smart folder management
- Interactive document creation
- Assignment tracking system
- Automatic date formatting
- Document status tracking

### AI Services
- Convert lecture speech to text
- Generate lecture summaries
- Get AI assistance with homework
- Receive personalized YouTube video recommendations
- Smart content generation
- Educational video recommendations

## Setup Requirements

1. Canvas LMS API Token
   - Generate from Canvas Account Settings
   - Add to `.env` file as `CANVAS_API_TOKEN`

2. Google Cloud Setup
   - Create project in Google Cloud Console
   - Enable Google Docs and Drive APIs
   - Create OAuth 2.0 credentials
   - Save as `credentials.json`

3. Firebase Configuration
   - Create Firebase project
   - Add configuration to `.env`
   - Enable Authentication
   - Set up Realtime Database

## Installation

1. Clone the repository:
   ```bash
   git clone [repository-url]
   cd student-hub
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```bash
   CANVAS_URL=your_canvas_url
   CANVAS_API_TOKEN=your_api_token
   GOOGLE_CREDENTIALS_PATH=/path/to/credentials.json
   FOLDER_IDS_PATH=/path/to/folder_ids.csv
   ```

## Dependencies

- Flask
- firebase-admin
- google-api-python-client
- google-auth-oauthlib
- canvasapi
- python-dotenv
- pandas
- requests

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Support

For support, please open an issue in the GitHub repository.