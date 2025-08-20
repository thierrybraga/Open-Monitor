
"""
NewsletterService handles business logic for managing newsletter subscriptions.

This service provides methods to add email addresses to a subscription list,
performing validation and storing data in the database via SQLAlchemy.
"""

from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime
from email_validator import validate_email, EmailNotValidError
from models.newsletter_subscriber import NewsletterSubscription


class NewsletterService:
    """Service for managing newsletter subscriptions."""

    def __init__(self, session: Session):
        """
        Initialize the service with a database session.

        Args:
            session: SQLAlchemy session for database operations.
        """
        self.session = session
    
    def get_all_subscribers(self, active_only: bool = True):
        """Get all newsletter subscribers."""
        query = self.session.query(NewsletterSubscription)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.all()
    
    def get_subscriber_by_email(self, email: str) -> Optional[NewsletterSubscription]:
        """Get a subscriber by email address."""
        return self.session.query(NewsletterSubscription).filter_by(email=email.strip().lower()).first()
    
    def unsubscribe(self, email: str) -> bool:
        """Unsubscribe an email from the newsletter."""
        try:
            subscriber = self.get_subscriber_by_email(email)
            if subscriber and subscriber.is_active:
                subscriber.unsubscribe()
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Error unsubscribing email '{email}': {e}")
    
    def resubscribe(self, email: str) -> bool:
        """Resubscribe an email to the newsletter."""
        try:
            subscriber = self.get_subscriber_by_email(email)
            if subscriber and not subscriber.is_active:
                subscriber.resubscribe()
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Error resubscribing email '{email}': {e}")

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