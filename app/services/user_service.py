
"""
UserService handles business logic for user-related operations.

This service provides methods to fetch and update user account data,
interacting with the database via SQLAlchemy and supporting Flask-Login for authentication.
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from flask_login import current_user
from app.models.user import User
from app.extensions import db


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
        Fetch user account data for the specified user.
        REMOVIDO: Não depende mais de autenticação.

        Args:
            user_id: ID of the user to fetch. If None, returns default guest data.

        Returns:
            Dictionary containing user data (e.g., username, email, first_name, last_name).

        Raises:
            RuntimeError: If the user is not found.
        """
        try:
            # Se não foi fornecido user_id, retorna dados de visitante
            if user_id is None:
                return {
                    'id': None,
                    'username': 'Visitante',
                    'email': 'visitante@exemplo.com',
                    'first_name': 'Usuário',
                    'last_name': 'Visitante',
                    'phone': None,
                    'address': None,
                    'bio': 'Usuário visitante do sistema',
                    'profile_picture': None,
                    'is_active': True,
                    'is_admin': False,
                    'created_at': None,
                    'updated_at': None
                }

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
                'phone': user.phone,
                'address': user.address,
                'bio': user.bio,
                'profile_picture': user.profile_picture,
                'is_active': user.is_active,
                'is_admin': user.is_admin,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'updated_at': user.updated_at.isoformat() if user.updated_at else None
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
            if 'phone' in data:
                user.phone = data['phone']
            if 'address' in data:
                user.address = data['address']
            if 'bio' in data:
                user.bio = data['bio']
            if 'profile_picture' in data:
                user.profile_picture = data['profile_picture']

            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Error updating user data for ID {user_id}: {e}")
