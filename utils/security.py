# utils/security.py

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
from flask import request, session
from functools import wraps
from collections import defaultdict

logger = logging.getLogger(__name__)

class RateLimiter:
    """Sistema de rate limiting para prevenir ataques de força bruta."""
    
    def __init__(self):
        self.attempts = defaultdict(list)
        self.blocked_ips = defaultdict(datetime)
    
    def is_rate_limited(self, identifier: str, max_attempts: int = 5, window_minutes: int = 15) -> bool:
        """Verifica se um identificador (IP, usuário) está limitado por rate limiting."""
        now = datetime.utcnow()
        
        # Verificar se está bloqueado
        if identifier in self.blocked_ips:
            if now < self.blocked_ips[identifier]:
                return True
            else:
                # Remover bloqueio expirado
                del self.blocked_ips[identifier]
        
        # Limpar tentativas antigas
        cutoff_time = now - timedelta(minutes=window_minutes)
        self.attempts[identifier] = [
            attempt_time for attempt_time in self.attempts[identifier]
            if attempt_time > cutoff_time
        ]
        
        # Verificar se excedeu o limite
        if len(self.attempts[identifier]) >= max_attempts:
            # Bloquear por 30 minutos
            self.blocked_ips[identifier] = now + timedelta(minutes=30)
            logger.warning(f"Rate limit exceeded for {identifier}. Blocked for 30 minutes.")
            return True
        
        return False
    
    def record_attempt(self, identifier: str):
        """Registra uma tentativa de login."""
        self.attempts[identifier].append(datetime.utcnow())
    
    def clear_attempts(self, identifier: str):
        """Limpa as tentativas de um identificador após login bem-sucedido."""
        if identifier in self.attempts:
            del self.attempts[identifier]
        if identifier in self.blocked_ips:
            del self.blocked_ips[identifier]

# Instância global do rate limiter
rate_limiter = RateLimiter()

def get_client_ip() -> str:
    """Obtém o IP real do cliente, considerando proxies."""
    # Verificar headers de proxy
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr or 'unknown'

def log_security_event(event_type: str, user_id: Optional[int] = None, 
                      username: Optional[str] = None, details: Optional[Dict] = None):
    """Registra eventos de segurança para auditoria."""
    client_ip = get_client_ip()
    user_agent = request.headers.get('User-Agent', 'Unknown')
    
    log_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': event_type,
        'client_ip': client_ip,
        'user_agent': user_agent,
        'user_id': user_id,
        'username': username,
        'session_id': session.get('_id', 'no_session'),
        'details': details or {}
    }
    
    # Log com nível apropriado baseado no tipo de evento
    if event_type in ['login_failed', 'rate_limit_exceeded', 'suspicious_activity']:
        logger.warning(f"Security Event: {event_type}", extra=log_data)
    elif event_type in ['login_success', 'logout', 'register_success']:
        logger.info(f"Security Event: {event_type}", extra=log_data)
    else:
        logger.debug(f"Security Event: {event_type}", extra=log_data)

def require_rate_limit(max_attempts: int = 5, window_minutes: int = 15):
    """Decorador para aplicar rate limiting a rotas."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = get_client_ip()
            
            if rate_limiter.is_rate_limited(client_ip, max_attempts, window_minutes):
                log_security_event('rate_limit_exceeded', details={
                    'max_attempts': max_attempts,
                    'window_minutes': window_minutes
                })
                from flask import jsonify, abort
                if request.is_json:
                    return jsonify({
                        'error': 'Muitas tentativas. Tente novamente em 30 minutos.',
                        'retry_after': 1800
                    }), 429
                else:
                    abort(429)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_password_strength(password: str) -> Dict[str, any]:
    """Valida a força de uma senha e retorna feedback detalhado."""
    import re
    
    score = 0
    feedback = []
    
    # Verificações de força
    if len(password) >= 8:
        score += 1
    else:
        feedback.append("Deve ter pelo menos 8 caracteres")
    
    if len(password) >= 12:
        score += 1
    
    if re.search(r'[a-z]', password):
        score += 1
    else:
        feedback.append("Deve conter pelo menos uma letra minúscula")
    
    if re.search(r'[A-Z]', password):
        score += 1
    else:
        feedback.append("Deve conter pelo menos uma letra maiúscula")
    
    if re.search(r'\d', password):
        score += 1
    else:
        feedback.append("Deve conter pelo menos um número")
    
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        score += 1
    else:
        feedback.append("Deve conter pelo menos um caractere especial")
    
    # Verificar sequências comuns
    common_sequences = ['123456', 'abcdef', 'qwerty', 'password']
    if any(seq in password.lower() for seq in common_sequences):
        score -= 1
        feedback.append("Não deve conter sequências comuns")
    
    # Determinar nível de força
    if score >= 5:
        strength = 'forte'
    elif score >= 3:
        strength = 'média'
    else:
        strength = 'fraca'
    
    return {
        'score': max(0, score),
        'strength': strength,
        'feedback': feedback,
        'is_valid': score >= 4 and len(feedback) <= 2
    }

def sanitize_input(input_string: str, max_length: int = 255) -> str:
    """Sanitiza entrada do usuário para prevenir ataques."""
    if not isinstance(input_string, str):
        return ''
    
    # Remover caracteres de controle e espaços extras
    sanitized = ''.join(char for char in input_string if ord(char) >= 32 or char in '\t\n\r')
    sanitized = sanitized.strip()
    
    # Limitar comprimento
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized