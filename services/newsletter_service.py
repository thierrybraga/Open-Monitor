
"""
NewsletterService handles business logic for managing newsletter subscriptions.

This service provides methods to add email addresses to a subscription list,
performing validation and storing data in the database via SQLAlchemy.
"""

from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime
from email_validator import validate_email, EmailNotValidError
from ..models.newsletter_subscription import NewsletterSubscription


class NewsletterService:
    """Service for managing newsletter subscriptions."""

    def __init__(self, session: Session):
        """
        Initialize the service with a database session.

        Args:
            session: SQLAlchemy session for database operations.
        """
        self.session = session

    def signup(self, email: str) -> bool:
        """
        Add an email address to the newsletter subscription list.

        Validates the email, checks for existing subscriptions, and stores the subscription.

        Args:
            email: The email address to subscribe.

        Returns:
            True if the subscription was successful, False if the email is already subscribed.

        Raises:
            ValueError: If the email is invalid.
            RuntimeError: If the database operation fails.
        """
        try:
            # Validate email format
            validate_email(email, check_deliverability=False)
            email = email.strip().lower()

            # Check for existing subscription
            existing = (
                self.session.query(NewsletterSubscription)
                .filter_by(email=email)
                .first()
            )
            if existing:
                return False  # Email already subscribed

            # Create new subscription
            subscription = NewsletterSubscription(
                email=email,
                subscribed_at=datetime.utcnow()
            )
            self.session.add(subscription)
            self.session.commit()
            return True

        except EmailNotValidError as e:
            raise ValueError(f"Invalid email address: {e}")
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Error subscribing email '{email}': {e}")