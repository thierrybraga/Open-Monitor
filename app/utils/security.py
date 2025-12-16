# utils/security.py

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from flask import request, session
from functools import wraps
from collections import defaultdict, OrderedDict
import hashlib
import json

logger = logging.getLogger(__name__)

# Armazenar informações de sessão para cálculo de duração de login
session_start_times = {}
last_login_info = {}

class RateLimiter:
    """Sistema de rate limiting para prevenir ataques de força bruta."""
    
    def __init__(self):
        self.attempts = defaultdict(list)
        self.blocked_ips = defaultdict(datetime)
    
    def is_rate_limited(self, identifier: str, max_attempts: int = 5, window_minutes: int = 15) -> bool:
        """Verifica se um identificador (IP, usuário) está limitado por rate limiting."""
        now = datetime.now(timezone.utc)
        
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
        self.attempts[identifier].append(datetime.now(timezone.utc))
    
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
    """Registra eventos de segurança para auditoria com informações detalhadas."""
    client_ip = get_client_ip()
    user_agent = request.headers.get('User-Agent', 'Unknown')
    referer = request.headers.get('Referer', 'Unknown')
    
    # Extrair informações do User-Agent
    user_agent_info = parse_user_agent(user_agent)
    
    log_data = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'event_type': event_type,
        'client_ip': client_ip,
        'user_agent': user_agent,
        'user_agent_parsed': user_agent_info,
        'referer': referer,
        'request_method': request.method,
        'request_endpoint': request.endpoint,
        'request_url': request.url,
        'user_id': user_id,
        'username': username,
        'session_id': session.get('_id', 'no_session'),
        'session_permanent': session.permanent,
        'request_headers': dict(request.headers),
        'details': details or {}
    }
    
    # Adicionar informações específicas baseadas no tipo de evento
    if event_type == 'login_failed':
        log_data['details'].update({
            'failed_attempts_count': len(rate_limiter.attempts.get(client_ip, [])),
            'is_rate_limited': rate_limiter.is_rate_limited(client_ip)
        })
    elif event_type == 'login_success':
        log_data['details'].update({
            'login_duration': calculate_login_duration(),
            'previous_login': get_previous_login_info(user_id) if user_id else None
        })
    
    # Log com nível apropriado baseado no tipo de evento
    if event_type in ['login_failed', 'rate_limit_exceeded', 'suspicious_activity', 'password_reset_requested']:
        logger.warning(f"Security Event: {event_type}", extra=log_data)
    elif event_type in ['login_success', 'logout', 'register_success', 'email_confirmed', 'password_reset_completed']:
        logger.info(f"Security Event: {event_type}", extra=log_data)
    else:
        logger.debug(f"Security Event: {event_type}", extra=log_data)


def parse_user_agent(user_agent: str) -> Dict[str, str]:
    """Extrai informações básicas do User-Agent."""
    try:
        # Análise básica do User-Agent
        info = {
            'browser': 'Unknown',
            'os': 'Unknown',
            'device': 'Unknown'
        }
        
        user_agent_lower = user_agent.lower()
        
        # Detectar navegador
        if 'chrome' in user_agent_lower:
            info['browser'] = 'Chrome'
        elif 'firefox' in user_agent_lower:
            info['browser'] = 'Firefox'
        elif 'safari' in user_agent_lower and 'chrome' not in user_agent_lower:
            info['browser'] = 'Safari'
        elif 'edge' in user_agent_lower:
            info['browser'] = 'Edge'
        elif 'opera' in user_agent_lower:
            info['browser'] = 'Opera'
        
        # Detectar sistema operacional
        if 'windows' in user_agent_lower:
            info['os'] = 'Windows'
        elif 'mac' in user_agent_lower:
            info['os'] = 'macOS'
        elif 'linux' in user_agent_lower:
            info['os'] = 'Linux'
        elif 'android' in user_agent_lower:
            info['os'] = 'Android'
        elif 'ios' in user_agent_lower or 'iphone' in user_agent_lower or 'ipad' in user_agent_lower:
            info['os'] = 'iOS'
        
        # Detectar tipo de dispositivo
        if 'mobile' in user_agent_lower or 'android' in user_agent_lower or 'iphone' in user_agent_lower:
            info['device'] = 'Mobile'
        elif 'tablet' in user_agent_lower or 'ipad' in user_agent_lower:
            info['device'] = 'Tablet'
        else:
            info['device'] = 'Desktop'
        
        return info
    except Exception as e:
        logger.debug(f"Erro ao analisar User-Agent: {e}")
        return {'browser': 'Unknown', 'os': 'Unknown', 'device': 'Unknown'}


def calculate_login_duration() -> Optional[float]:
    """Calcula a duração desde o início da sessão de login."""
    try:
        session_id = session.get('_id')
        if session_id and session_id in session_start_times:
            start_time = session_start_times[session_id]
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            return round(duration, 2)
        return None
    except Exception as e:
        logger.debug(f"Erro ao calcular duração do login: {e}")
        return None


def get_previous_login_info(user_id: int) -> Optional[Dict]:
    """Obtém informações do login anterior do usuário."""
    try:
        if user_id in last_login_info:
            return last_login_info[user_id]
        return None
    except Exception as e:
        logger.debug(f"Erro ao obter informações do login anterior: {e}")
        return None


def record_login_start():
    """Registra o início de uma tentativa de login."""
    try:
        session_id = session.get('_id')
        if session_id:
            session_start_times[session_id] = datetime.now(timezone.utc)
    except Exception as e:
        logger.debug(f"Erro ao registrar início do login: {e}")


def record_successful_login(user_id: int, username: str):
    """Registra informações de um login bem-sucedido."""
    try:
        client_ip = get_client_ip()
        login_info = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'client_ip': client_ip,
            'user_agent': request.headers.get('User-Agent', 'Unknown'),
            'username': username
        }
        last_login_info[user_id] = login_info
        
        # Limpar informações antigas (manter apenas os últimos 1000 usuários)
        if len(last_login_info) > 1000:
            # Remover as entradas mais antigas
            oldest_keys = list(last_login_info.keys())[:100]
            for key in oldest_keys:
                del last_login_info[key]
                
    except Exception as e:
        logger.debug(f"Erro ao registrar login bem-sucedido: {e}")


def cleanup_session_data():
    """Limpa dados de sessão antigos para evitar vazamento de memória."""
    try:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        
        # Limpar tempos de início de sessão antigos
        expired_sessions = [
            session_id for session_id, start_time in session_start_times.items()
            if start_time < cutoff_time
        ]
        
        for session_id in expired_sessions:
            del session_start_times[session_id]
            
        logger.debug(f"Limpeza de dados de sessão: {len(expired_sessions)} sessões antigas removidas")
        
    except Exception as e:
        logger.debug(f"Erro na limpeza de dados de sessão: {e}")

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
