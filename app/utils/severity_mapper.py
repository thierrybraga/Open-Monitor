#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilitário para mapeamento de scores CVSS para severidade.
Resolve o problema de CVEs antigos que não possuem campo baseSeverity na API NVD v2.0.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def map_cvss_score_to_severity(cvss_score: Optional[float], cvss_version: str = '3.1') -> str:
    """
    Mapeia um score CVSS para severidade baseado na versão do CVSS.
    
    Args:
        cvss_score: Score CVSS (0.0 - 10.0)
        cvss_version: Versão do CVSS ('2.0', '3.0', '3.1', '4.0')
        
    Returns:
        Severidade mapeada: 'NONE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL', ou 'N/A'
    """
    if cvss_score is None:
        return 'N/A'
        
    try:
        score = float(cvss_score)
    except (ValueError, TypeError):
        logger.warning(f"Score CVSS inválido: {cvss_score}")
        return 'N/A'
    
    # Validar range do score
    if score < 0.0 or score > 10.0:
        logger.warning(f"Score CVSS fora do range válido (0.0-10.0): {score}")
        return 'N/A'
    
    # Mapeamento para CVSS v3.x e v4.0 (padrão atual)
    if cvss_version in ['3.0', '3.1', '4.0']:
        if score == 0.0:
            return 'NONE'
        elif 0.1 <= score <= 3.9:
            return 'LOW'
        elif 4.0 <= score <= 6.9:
            return 'MEDIUM'
        elif 7.0 <= score <= 8.9:
            return 'HIGH'
        elif 9.0 <= score <= 10.0:
            return 'CRITICAL'
    
    # Mapeamento para CVSS v2.0 (CVEs antigos)
    elif cvss_version == '2.0':
        if score == 0.0:
            return 'NONE'
        elif 0.1 <= score <= 3.9:
            return 'LOW'
        elif 4.0 <= score <= 6.9:
            return 'MEDIUM'
        elif 7.0 <= score <= 10.0:
            return 'HIGH'  # CVSS v2.0 não tem CRITICAL
    
    else:
        logger.warning(f"Versão CVSS não suportada: {cvss_version}")
        return 'N/A'
    
    # Fallback para casos não cobertos
    logger.warning(f"Score CVSS não mapeado: {score} (versão {cvss_version})")
    return 'N/A'


def get_primary_severity_from_metrics(cvss_metrics: list) -> tuple[str, Optional[float]]:
    """
    Extrai a severidade primária de uma lista de métricas CVSS.
    Prioriza CVSS v3.1 > v3.0 > v2.0.
    
    Args:
        cvss_metrics: Lista de dicionários com métricas CVSS
        
    Returns:
        Tupla (severidade, score) da métrica primária
    """
    if not cvss_metrics:
        return 'N/A', None
    
    # Ordem de prioridade das versões
    version_priority = ['3.1', '3.0', '2.0']
    
    for version in version_priority:
        # Buscar métricas primárias desta versão
        primary_metrics = [
            m for m in cvss_metrics 
            if m.get('cvss_version') == version and m.get('is_primary', False)
        ]
        
        if primary_metrics:
            metric = primary_metrics[0]
            
            # Se já tem severidade definida, usar ela
            existing_severity = metric.get('base_severity')
            if existing_severity and existing_severity.upper() not in ['UNKNOWN', 'N/A']:
                return existing_severity.upper(), metric.get('base_score')
            
            # Caso contrário, mapear do score
            score = metric.get('base_score')
            if score is not None:
                mapped_severity = map_cvss_score_to_severity(score, version)
                return mapped_severity, score
    
    # Fallback: usar qualquer métrica disponível
    for metric in cvss_metrics:
        score = metric.get('base_score')
        version = metric.get('cvss_version', '3.1')
        if score is not None:
            mapped_severity = map_cvss_score_to_severity(score, version)
            return mapped_severity, score
    
    return 'N/A', None


def validate_severity(severity: str) -> str:
    """
    Valida e normaliza uma string de severidade.
    
    Args:
        severity: String de severidade para validar
        
    Returns:
        Severidade normalizada ou 'N/A' se inválida
    """
    if not severity:
        return 'N/A'
    
    valid_severities = ['NONE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'N/A']
    normalized = severity.upper().strip()
    
    if normalized in valid_severities:
        return normalized
    
    # Mapeamentos alternativos comuns
    severity_mappings = {
        'UNKNOWN': 'N/A',
        'INFO': 'LOW',
        'INFORMATIONAL': 'LOW',
        'MODERATE': 'MEDIUM',
        'SEVERE': 'HIGH',
        'IMPORTANT': 'HIGH'
    }
    
    mapped = severity_mappings.get(normalized)
    if mapped:
        return mapped
    
    logger.warning(f"Severidade inválida: {severity}")
    return 'N/A'
