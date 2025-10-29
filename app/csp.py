# csp.py
"""
Content Security Policy (CSP) configuration for Flask application.
"""

import logging
from flask import Flask, g, request
from typing import Dict, List

logger = logging.getLogger(__name__)


def build_csp_header(csp_config: Dict[str, List[str]], nonce: str = None) -> str:
    """
    Build CSP header string from configuration dictionary.
    
    Args:
        csp_config: Dictionary with CSP directives
        nonce: Nonce value to replace in script-src
        
    Returns:
        CSP header string
    """
    csp_parts = []
    
    for directive, sources in csp_config.items():
        if sources:
            # Replace nonce placeholder with actual nonce
            processed_sources = []
            for source in sources:
                if nonce and "'nonce-{{ csp_nonce }}'" in source:
                    processed_sources.append(f"'nonce-{nonce}'")
                else:
                    processed_sources.append(source)
            
            csp_parts.append(f"{directive} {' '.join(processed_sources)}")
    
    return "; ".join(csp_parts)


def setup_csp(app: Flask) -> None:
    """
    Setup Content Security Policy for the Flask application.
    
    Args:
        app: Flask application instance
    """
    
    @app.context_processor
    def inject_csp_context():
        """Inject CSP header into template context."""
        try:
            # Get CSP configuration from app config
            csp_config = app.config.get('CSP', {})
            
            if csp_config:
                # Get nonce from existing context (should be available from inject_base_variables)
                from flask import g
                nonce = g.get('csp_nonce', None)
                
                # If not in g, try to get from template context
                if not nonce:
                    # This should be available from the inject_base_variables context processor
                    import secrets
                    nonce = secrets.token_urlsafe(16)
                
                # Build CSP header
                csp_header = build_csp_header(csp_config, nonce)
                
                logger.debug(f"CSP header generated: {csp_header}")
                
                return {
                    'csp_header': csp_header
                }
            else:
                logger.warning("No CSP configuration found in app config")
                return {'csp_header': None}
                
        except Exception as e:
            logger.error(f"Error setting up CSP header: {e}", exc_info=True)
            return {'csp_header': None}
    
    logger.info("CSP setup completed")