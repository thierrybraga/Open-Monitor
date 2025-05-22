# test_app.py: Unit tests for the Flask application
# This file contains tests to verify application functionality,
# including route responses and configuration.

import pytest
from ..app import create_app

@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_hello_world(client):
    """Test the root URL returns Hello World."""
    response = client.get('/')
    assert response.status_code == 200
    assert response.data.decode() == 'Hello World'

def test_config():
    """Test that the app loads the correct configuration."""
    app = create_app()
    assert app.config['DEBUG']
    assert app.config['SECRET_KEY'] is not None
