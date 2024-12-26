from flask import Flask
from app import app

def handler(request):
    """Handle requests from Vercel serverless function"""
    return app(request.environ, lambda x, y: [])