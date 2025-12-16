# models/newsletter_subscriber.py

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from app.models.base_model import BaseModel


class NewsletterSubscription(BaseModel):
    __bind_key__ = 'public'
    """Model for newsletter subscriptions."""
    
    __tablename__ = 'newsletter_subscriptions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    subscribed_at = Column(DateTime, nullable=False, default=func.now())
    is_active = Column(Boolean, nullable=False, default=True)
    unsubscribed_at = Column(DateTime, nullable=True)
    preferences = Column(Text, nullable=True)  # JSON string for notification preferences
    source = Column(String(50), nullable=True, default='website')  # Source of subscription
    
    def __repr__(self):
        return f'<NewsletterSubscription(id={self.id}, email="{self.email}", active={self.is_active})>'
    
    def to_dict(self):
        """Convert the subscription to a dictionary."""
        return {
            'id': self.id,
            'email': self.email,
            'subscribed_at': self.subscribed_at.isoformat() if self.subscribed_at else None,
            'is_active': self.is_active,
            'unsubscribed_at': self.unsubscribed_at.isoformat() if self.unsubscribed_at else None,
            'preferences': self.preferences,
            'source': self.source
        }
    
    def unsubscribe(self):
        """Mark subscription as inactive."""
        self.is_active = False
        self.unsubscribed_at = datetime.now(timezone.utc)
    
    def resubscribe(self):
        """Reactivate subscription."""
        self.is_active = True
        self.unsubscribed_at = None


# Alias for backward compatibility
NewsletterSubscriber = NewsletterSubscription
