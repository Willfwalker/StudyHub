Make .env file and add the following:

- YOUTUBE_API_KEY
- GEMINI_API_KEY
- CANVAS_URL
- FIREBASE_CREDENTIALS_JSON
- CREDENTIALS_PATH
- FLASK_SECRET_KEY
- PEXELS_API_KEY
- PEXELS_API_URL
- FIREBASE_API_KEY
- FIREBASE_AUTH_DOMAIN
- FIREBASE_PROJECT_ID
- FIREBASE_STORAGE_BUCKET
- FIREBASE_MESSAGING_SENDER_ID
- FIREBASE_APP_ID
- FIREBASE_DATABASE_URL
- FLASK_APP
- MAIL_PASSWORD
- CANVAS_API_KEY
- GOOGLE_CREDENTIALS_JSON

Make sure to download the necassary requirements for the project.

Set firebase rules to this:
{
  "rules": {
    "users": {
      "$uid": {
        ".read": "auth != null && auth.uid === $uid",
        ".write": "auth != null && auth.uid === $uid",
        "documents": {
          "$doc_id": {
            ".read": "auth != null && auth.uid === $uid",
            ".write": "auth != null && auth.uid === $uid",
            ".validate": "newData.hasChildren(['document_id', 'assignment_name', 'course_name', 'url'])"
          }
        },
        "canvas_api_key": {
          ".read": "auth != null && auth.uid === $uid",
          ".write": "auth != null && auth.uid === $uid"
        }
      }
    },
    "test": {
      ".read": true,
      ".write": true
    }
  }
}

Make sure that you're google cloud api key is enabled for the following apis:

- Youtube Data API
- Gemini API
- Docs API
- Sheets API
- Drive API

You'll need to have an email with and app password for the gmail account you're using to send bugs to.

After this, run app.py
