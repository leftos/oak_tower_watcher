#!/usr/bin/env python3
"""
Startup script for the OAK Tower Watcher web application
"""

import sys
import os

# Add the backend directory to the Python path
backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_dir)

from backend.app import main

if __name__ == "__main__":
    main()