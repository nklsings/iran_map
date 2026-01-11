import sys
import os

# Add the project root to the python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.app.main import app

# Vercel expects a handler named 'app' or 'handler'
handler = app
