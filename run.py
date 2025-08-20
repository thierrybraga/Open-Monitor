#!/usr/bin/env python3
"""
Script to run the Flask application in development mode.
"""

from app import create_app

if __name__ == '__main__':
    app = create_app('development')
    app.run(host='0.0.0.0', port=5000, debug=True)