#!/usr/bin/env python3
"""
Melhorias para o NVDFetcher: mapeamento automático de CWEs e processamento melhorado de referências
"""

import re
from typing import List, Dict, Set, Optional, Tuple

class CWEAutoMapper:
    """
    Classe para mapeamento automático de CWEs baseado em descrições de vulnerabilidades
    """
    
    def __init__(self):
        # Padrões de texto para mapeamento automático de CWEs
        # Baseado nos CWEs mais comuns identificados no relatório
        self.cwe_patterns = {
            'CWE-79': [  # Cross-site Scripting (XSS)
                r'cross[\s-]?site\s+script',
                r'\bxss\b',
                r'script\s+injection',
                r'reflected\s+xss',
                r'stored\s+xss',
                r'dom\s+xss'
            ],
            'CWE-119': [  # Buffer Overflow
                r'buffer\s+overflow',
                r'buffer\s+overrun',
                r'stack\s+overflow',
                r'heap\s+overflow',
                r'memory\s+corruption'
            ],
            'CWE-20': [  # Input Validation
                r'input\s+validation',
                r'improper\s+input',
                r'insufficient\s+input',
                r'malformed\s+input',
                r'invalid\s+input'
            ],
            'CWE-200': [  # Information Exposure
                r'information\s+disclosure',
                r'information\s+exposure',
                r'sensitive\s+information',
                r'data\s+leak',
                r'information\s+leak'
            ],
            'CWE-787': [  # Out-of-bounds Write
                r'out[\s-]?of[\s-]?bounds\s+write',
                r'buffer\s+overwrite',
                r'memory\s+overwrite',
                r'write\s+beyond\s+buffer'
            ],
            'CWE-89': [  # SQL Injection
                r'sql\s+injection',
                r'sqli',
                r'database\s+injection',
                r'sql\s+query\s+injection'
            ],
            'CWE-22': [  # Path Traversal
                r'path\s+traversal',
                r'directory\s+traversal',
                r'file\s+inclusion',
                r'\.\.\/'
            ],
            'CWE-352': [  # Cross-Site Request Forgery (CSRF)
                r'cross[\s-]?site\s+request\s+forgery',
                r'\bcsrf\b',
                r'request\s+forgery'
            ],
            'CWE-78': [  # OS Command Injection
                r'command\s+injection',
                r'os\s+command',
                r'shell\s+injection',
                r'code\s+injection'
            ],
            'CWE-125': [  # Out-of-bounds Read
                r'out[\s-]?of[\s-]?bounds\s+read',
                r'buffer\s+over[\s-]?read',
                r'read\s+beyond\s+buffer'
            ],
            'CWE-476': [  # NULL Pointer Dereference
                r'null\s+pointer',
                r'null\s+dereference',
                r'nullptr\s+dereference'
            ],
            'CWE-190': [  # Integer Overflow
                r'integer\s+overflow',
                r'numeric\s+overflow',
                r'arithmetic\s+overflow'
            ],
            'CWE-416': [  # Use After Free
                r'use\s+after\s+free',
                r'dangling\s+pointer',
                r'freed\s+memory'
            ],
            'CWE-94': [  # Code Injection
                r'code\s+injection',
                r'script\s+injection',
                r'eval\s+injection'
            ],
            'CWE-862': [  # Missing Authorization
                r'missing\s+authorization',
                r'insufficient\s+authorization',
                r'bypass\s+authorization'
            ]
        }
        
        # Compilar padrões regex para melhor performance
        self.compiled_patterns = {}
        for cwe_id, patterns in self.cwe_patterns.items():
            self.compiled_patterns[cwe_id] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]
    
    def map_cwe_from_description(self, description: str) -> List[str]:
        """
        Mapeia CWEs baseado na descrição da vulnerabilidade
        
        Args:
            description: Descrição da vulnerabilidade
            
        Returns:
            Lista de CWE IDs identificados
        """
        if not description:
            return []
        
        identified_cwes = set()
        
        for cwe_id, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(description):
                    identified_cwes.add(cwe_id)
                    break  # Uma correspondência por CWE é suficiente
        
        return list(identified_cwes)

class EnhancedReferenceProcessor:
    """
    Classe para melhorar o processamento de referências
    """
    
    def __init__(self):
        # Indicadores expandidos para detecção de patches
        self.patch_indicators = [
            'patch', 'fix', 'update', 'hotfix', 'security update',
            'vendor advisory', 'mitigation', 'workaround', 'solution',
            'security bulletin', 'security notice', 'advisory',
            'bugfix', 'correction', 'repair'
        ]
        
        # Padrões de URL que indicam patches
        self.patch_url_patterns = [
            r'patch',
            r'fix',
            r'update',
            r'security',
            r'advisory',
            r'bulletin',
            r'hotfix',
            r'bugfix'
        ]
        
        # Compilar padrões
        self.compiled_url_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.patch_url_patterns
        ]
    
    def enhanced_patch_detection(self, reference: Dict) -> bool:
        """
        Detecção melhorada de patches em referências
        
        Args:
            reference: Dicionário com dados da referência (url, source, tags)
            
        Returns:
            True se a referência indica um patch
        """
        url = reference.get('url', '').lower()
        tags = reference.get('tags', [])
        source = reference.get('source', '').lower()
        
        # Verificar tags
        if tags:
            for tag in tags:
                if any(indicator.lower() in tag.lower() for indicator in self.patch_indicators):
                    return True
        
        # Verificar URL
        for pattern in self.compiled_url_patterns:
            if pattern.search(url):
                return True
        
        # Verificar fonte
        if any(indicator in source for indicator in ['security', 'advisory', 'patch']):
            return True
        
        return False
    
    def validate_reference(self, reference) -> bool:
        """
        Valida se uma referência é válida
        
        Args:
            reference: URL (string) ou dicionário com dados da referência
            
        Returns:
            True se a referência é válida
        """
        # Aceitar tanto string quanto dicionário
        if isinstance(reference, str):
            url = reference
        elif isinstance(reference, dict):
            url = reference.get('url', '')
        else:
            return False
        
        # Verificações básicas
        if not url or len(url.strip()) < 10:
            return False
        
        # Verificar se é uma URL válida
        if not (url.startswith('http://') or url.startswith('https://')):
            return False
        
        # Verificar se não é uma URL suspeita
        suspicious_patterns = ['localhost', '127.0.0.1', 'example.com']
        if any(pattern in url.lower() for pattern in suspicious_patterns):
            return False
        
        return True
    
    def process_references_enhanced(self, references_data: List[Dict]) -> Tuple[List[Dict], bool, List[Dict]]:
        """
        Processa referências com melhorias
        
        Args:
            references_data: Lista de referências da API NVD
            
        Returns:
            Tupla com (referências_válidas, patch_disponível, referências_de_patch)
        """
        valid_references = []
        patch_available = False
        patch_references = []
        
        for ref in references_data:
            # Validar referência
            if not self.validate_reference(ref):
                continue
            
            # Adicionar à lista de válidas
            valid_references.append(ref)
            
            # Verificar se é patch
            if self.enhanced_patch_detection(ref):
                patch_available = True
                patch_references.append(ref)
        
        return valid_references, patch_available, patch_references