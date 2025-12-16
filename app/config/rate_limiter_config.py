"""Rate Limiter Configuration

This module contains configuration settings for the rate limiting system.
"""

import os
from typing import Dict, Any


class RateLimiterConfig:
    """Configuration class for rate limiting settings."""
    
    # Default rate limiting settings
    DEFAULT_REQUESTS_PER_WINDOW = int(os.getenv('RATE_LIMIT_REQUESTS', '100'))
    DEFAULT_WINDOW_SIZE = int(os.getenv('RATE_LIMIT_WINDOW', '60'))  # seconds
    
    # API-specific rate limits
    API_RATE_LIMITS = {
        # General API endpoints
        'api': {
            'requests': int(os.getenv('API_RATE_LIMIT_REQUESTS', '60')),
            'window': int(os.getenv('API_RATE_LIMIT_WINDOW', '60'))
        },
        
        # Authentication endpoints (more restrictive)
        'auth': {
            'requests': int(os.getenv('AUTH_RATE_LIMIT_REQUESTS', '10')),
            'window': int(os.getenv('AUTH_RATE_LIMIT_WINDOW', '60'))
        },
        
        # Search endpoints (moderate restrictions)
        'search': {
            'requests': int(os.getenv('SEARCH_RATE_LIMIT_REQUESTS', '30')),
            'window': int(os.getenv('SEARCH_RATE_LIMIT_WINDOW', '60'))
        },
        
        # Analytics endpoints
        'analytics': {
            'requests': int(os.getenv('ANALYTICS_RATE_LIMIT_REQUESTS', '20')),
            'window': int(os.getenv('ANALYTICS_RATE_LIMIT_WINDOW', '60'))
        },
        
        # Admin endpoints (very restrictive)
        'admin': {
            'requests': int(os.getenv('ADMIN_RATE_LIMIT_REQUESTS', '5')),
            'window': int(os.getenv('ADMIN_RATE_LIMIT_WINDOW', '60'))
        }
    }
    
    # Rate limiting strategy
    RATE_LIMIT_STRATEGY = os.getenv('RATE_LIMIT_STRATEGY', 'ip')  # 'ip', 'user', 'endpoint'
    
    # Whitelisted IPs (no rate limiting)
    WHITELISTED_IPS = [
        # '127.0.0.1',  # Temporarily disabled for testing
        '::1',
        # 'localhost'   # Temporarily disabled for testing
    ]
    
    # Additional whitelisted IPs from environment
    env_whitelist = os.getenv('RATE_LIMIT_WHITELIST_IPS', '')
    if env_whitelist:
        WHITELISTED_IPS.extend([ip.strip() for ip in env_whitelist.split(',')])
    
    # Routes to skip rate limiting
    SKIP_ROUTES = [
        '/health',
        '/static',
        '/favicon.ico',
        '/robots.txt'
    ]
    
    # Admin routes (additional protection)
    ADMIN_ROUTES = [
        '/admin',
        '/api/admin'
    ]
    
    # Enable/disable rate limiting
    RATE_LIMITING_ENABLED = os.getenv('RATE_LIMITING_ENABLED', 'true').lower() == 'true'
    
    # Redis configuration for distributed rate limiting
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    USE_REDIS = os.getenv('USE_REDIS_RATE_LIMITING', 'false').lower() == 'true'
    
    # Rate limit headers
    INCLUDE_HEADERS = os.getenv('RATE_LIMIT_INCLUDE_HEADERS', 'true').lower() == 'true'

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        return {
            'DEFAULT_REQUESTS_PER_WINDOW': cls.DEFAULT_REQUESTS_PER_WINDOW,
            'DEFAULT_WINDOW_SIZE': cls.DEFAULT_WINDOW_SIZE,
            'API_RATE_LIMITS': dict(cls.API_RATE_LIMITS),
            'RATE_LIMIT_STRATEGY': cls.RATE_LIMIT_STRATEGY,
            'WHITELISTED_IPS': list(cls.WHITELISTED_IPS),
            'SKIP_ROUTES': list(cls.SKIP_ROUTES),
            'ADMIN_ROUTES': list(cls.ADMIN_ROUTES),
            'RATE_LIMITING_ENABLED': cls.RATE_LIMITING_ENABLED,
            'REDIS_URL': cls.REDIS_URL,
            'USE_REDIS': cls.USE_REDIS,
            'INCLUDE_HEADERS': cls.INCLUDE_HEADERS,
        }
    
    @classmethod
    def get_rate_limit_for_endpoint(cls, endpoint: str) -> Dict[str, int]:
        """Get rate limit configuration for a specific endpoint.
        
        Args:
            endpoint: The endpoint path
            
        Returns:
            Dictionary with 'requests' and 'window' keys
        """
        # Check for specific endpoint configurations
        for prefix, config in cls.API_RATE_LIMITS.items():
            if endpoint.startswith(f'/{prefix}') or endpoint.startswith(f'/api/{prefix}'):
                return config
        
        # Default configuration
        return {
            'requests': cls.DEFAULT_REQUESTS_PER_WINDOW,
            'window': cls.DEFAULT_WINDOW_SIZE
        }
    
    @classmethod
    def is_whitelisted_ip(cls, ip: str) -> bool:
        """Check if an IP is whitelisted.
        
        Args:
            ip: IP address to check
            
        Returns:
            True if IP is whitelisted, False otherwise
        """
        return ip in cls.WHITELISTED_IPS
    
    @classmethod
    def should_skip_route(cls, path: str) -> bool:
        """Check if a route should skip rate limiting.
        
        Args:
            path: Request path
            
        Returns:
            True if route should be skipped, False otherwise
        """
        return any(path.startswith(skip_route) for skip_route in cls.SKIP_ROUTES)
    
    @classmethod
    def is_admin_route(cls, path: str) -> bool:
        """Check if a route is an admin route.
        
        Args:
            path: Request path
            
        Returns:
            True if route is admin route, False otherwise
        """
        return any(path.startswith(admin_route) for admin_route in cls.ADMIN_ROUTES)


# Development configuration
class DevelopmentRateLimiterConfig(RateLimiterConfig):
    """Development-specific rate limiter configuration."""
    
    # More lenient limits for development
    DEFAULT_REQUESTS_PER_WINDOW = 1000
    DEFAULT_WINDOW_SIZE = 60
    
    API_RATE_LIMITS = {
        'api': {'requests': 300, 'window': 60},
        'auth': {'requests': 50, 'window': 60},
        'search': {'requests': 100, 'window': 60},
        'analytics': {'requests': 100, 'window': 60},
        'admin': {'requests': 50, 'window': 60}
    }


# Production configuration
class ProductionRateLimiterConfig(RateLimiterConfig):
    """Production-specific rate limiter configuration."""
    
    # Stricter limits for production
    DEFAULT_REQUESTS_PER_WINDOW = 50
    DEFAULT_WINDOW_SIZE = 60
    
    API_RATE_LIMITS = {
        'api': {'requests': 30, 'window': 60},
        'auth': {'requests': 5, 'window': 60},
        'search': {'requests': 15, 'window': 60},
        'analytics': {'requests': 10, 'window': 60},
        'admin': {'requests': 3, 'window': 60}
    }


# Configuration mapping
config_map = {
    'development': DevelopmentRateLimiterConfig,
    'production': ProductionRateLimiterConfig,
    'default': RateLimiterConfig
}


def get_rate_limiter_config(env: str = None) -> RateLimiterConfig:
    """Get rate limiter configuration for the specified environment.
    
    Args:
        env: Environment name (development, production, etc.)
        
    Returns:
        Rate limiter configuration class
    """
    env = env or os.getenv('FLASK_ENV', 'development')
    config_cls = config_map.get(env, config_map['default'])
    return config_cls()
