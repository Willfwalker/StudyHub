from flask import Flask
from app import app

def handler(request):
    """Handle requests from Vercel serverless function"""
    if request.method == "POST":
        return app.handle_request(request)
    return app