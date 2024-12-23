from app import app

# Remove the if __name__ == '__main__': block from app.py
# and add this handler
def handler(request, context):
    return app(request, context)