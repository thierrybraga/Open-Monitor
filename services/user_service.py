
"""
UserService handles business logic for user-related operations.

This service provides methods to fetch and update user account data,
interacting with the database via SQLAlchemy and supporting Flask-Login for authentication.
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from flask_login import current_user
from ..models.user import User


class UserService:
    """Service for managing user-related operations."""

    def __init__(self, session: Session):
        """
        Initialize the service with a database session.

        Args:
            session: SQLAlchemy session for database operations.
        """
        self.session = session

    def get_user_data(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Fetch user account data for the specified user or the current user.

        Args:
            user_id: Optional ID of the user to fetch. If None, uses the current user's ID.

        Returns:
            Dictionary containing user data (e.g., username, email, first_name, last_name).

        Raises:
            RuntimeError: If the user is not found or not authenticated.
        """
        try:
            # Determine user ID to fetch
            if user_id is None:
                if not current_user.is_authenticated:
                    raise RuntimeError("No authenticated user found.")
                user_id = current_user.id

            # Fetch user from database
            user = self.session.query(User).filter_by(id=user_id).first()
            if not user:
                raise RuntimeError(f"User with ID {user_id} not found.")

            # Return user data as a dictionary
            return {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                # Add other fields as needed
            }
        except Exception as e:
            raise RuntimeError(f"Error fetching user data for ID {user_id}: {e}")

    def update_user_data(self, user_id: int, data: Dict[str, Any]) -> bool:
        """
        Update user account data with the provided information.

        Args:
            user_id: ID of the user to update.
            data: Dictionary containing updated user data (e.g., {'email': 'new@example.com'}).

        Returns:
            True if the update was successful, False otherwise.

        Raises:
            RuntimeError: If the user is not found or the update fails.
        """
        try:
            user = self.session.query(User).filter_by(id=user_id).first()
            if not user:
                raise RuntimeError(f"User with ID {user_id} not found.")

            # Update fields if provided in data
            if 'email' in data:
                user.email = data['email']
            if 'first_name' in data:
                user.first_name = data['first_name']
            if 'last_name' in data:
                user.last_name = data['last_name']
            # Add other fields as needed

            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Error updating user data for ID {user_id}: {e}")