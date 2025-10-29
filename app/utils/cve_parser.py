#!/usr/bin/env python3
"""
Parser de descrições CVE para extrair produtos e vendors automaticamente.
Implementa padrões regex e heurísticas para identificar produtos em descrições.
"""

import re
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

@dataclass
class ProductMatch:
    """Representa um produto encontrado na descrição."""
    product_name: str
    vendor_name: Optional[str]
    confidence: float
    pattern_type: str
    raw_match: str

class CVEDescriptionParser:
    """Parser para extrair produtos e vendors de descrições CVE."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._compile_patterns()
        self._load_known_vendors()
    
    def _compile_patterns(self):
        """Compila padrões regex para identificar produtos."""
        
        # Padrões para produtos com versões
        self.version_patterns = [
            # "Adobe Flash Player before 32.0.0.465"
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+[A-Z][a-z]+)*?)\s+(?:before|prior\s+to|up\s+to|through|version)\s+([\d\.]+)',
            
            # "Microsoft Windows 10 version 1903"
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+\d+)?)\s+version\s+([\d\.]+)',
            
            # "Google Chrome 89.0.4389.82"
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+([\d\.]+)',
            
            # "WordPress plugin XYZ 1.2.3"
            r'([A-Z][a-z]+(?:\s+[a-z]+)*\s+plugin\s+[A-Za-z0-9_-]+)\s+([\d\.]+)',
        ]
        
        # Padrões para produtos sem versões específicas
        self.product_patterns = [
            # "in Adobe Flash Player"
            r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+[A-Z][a-z]+)*)',
            
            # "affects Microsoft Office"
            r'affects?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            
            # "vulnerability in Oracle Database"
            r'vulnerability\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            
            # "The XYZ component of ABC"
            r'The\s+[A-Za-z]+\s+component\s+of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        ]
        
        # Padrões para vendor + produto
        self.vendor_product_patterns = [
            # "Adobe Flash Player", "Microsoft Windows"
            r'\b(Adobe|Microsoft|Google|Apple|Oracle|IBM|Cisco|VMware|Red\s+Hat|Canonical|Mozilla|Sun|Intel|AMD|NVIDIA)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            
            # "WordPress by Automattic"
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+by\s+([A-Z][a-z]+)',
        ]
        
        # Compilar todos os padrões
        self.compiled_version_patterns = [re.compile(p, re.IGNORECASE) for p in self.version_patterns]
        self.compiled_product_patterns = [re.compile(p, re.IGNORECASE) for p in self.product_patterns]
        self.compiled_vendor_product_patterns = [re.compile(p, re.IGNORECASE) for p in self.vendor_product_patterns]
    
    def _load_known_vendors(self):
        """Carrega lista de vendors conhecidos."""
        self.known_vendors = {
            'adobe', 'microsoft', 'google', 'apple', 'oracle', 'ibm', 'cisco',
            'vmware', 'red hat', 'canonical', 'mozilla', 'sun', 'intel', 'amd',
            'nvidia', 'hp', 'dell', 'lenovo', 'samsung', 'lg', 'sony', 'asus',
            'wordpress', 'drupal', 'joomla', 'magento', 'prestashop', 'opencart',
            'debian', 'ubuntu', 'centos', 'fedora', 'suse', 'redhat', 'linux'
        }
    
    def parse_description(self, description: str) -> List[ProductMatch]:
        """Extrai produtos da descrição CVE."""
        if not description:
            return []
        
        matches = []
        
        # 1. Buscar padrões com versões
        for i, pattern in enumerate(self.compiled_version_patterns):
            for match in pattern.finditer(description):
                product_name = match.group(1).strip()
                version = match.group(2).strip()
                vendor = self._extract_vendor_from_product(product_name)
                
                matches.append(ProductMatch(
                    product_name=product_name,
                    vendor_name=vendor,
                    confidence=0.9,
                    pattern_type=f'version_pattern_{i}',
                    raw_match=match.group(0)
                ))
        
        # 2. Buscar padrões vendor + produto
        for i, pattern in enumerate(self.compiled_vendor_product_patterns):
            for match in pattern.finditer(description):
                if len(match.groups()) == 2:
                    vendor_name = match.group(1).strip()
                    product_name = match.group(2).strip()
                    
                    # Verificar se o primeiro grupo é realmente um vendor
                    if vendor_name.lower() in self.known_vendors:
                        matches.append(ProductMatch(
                            product_name=f"{vendor_name} {product_name}",
                            vendor_name=vendor_name,
                            confidence=0.85,
                            pattern_type=f'vendor_product_pattern_{i}',
                            raw_match=match.group(0)
                        ))
        
        # 3. Buscar padrões de produtos simples
        for i, pattern in enumerate(self.compiled_product_patterns):
            for match in pattern.finditer(description):
                product_name = match.group(1).strip()
                vendor = self._extract_vendor_from_product(product_name)
                
                matches.append(ProductMatch(
                    product_name=product_name,
                    vendor_name=vendor,
                    confidence=0.7,
                    pattern_type=f'product_pattern_{i}',
                    raw_match=match.group(0)
                ))
        
        # Remover duplicatas e ordenar por confiança
        unique_matches = self._deduplicate_matches(matches)
        return sorted(unique_matches, key=lambda x: x.confidence, reverse=True)
    
    def _extract_vendor_from_product(self, product_name: str) -> Optional[str]:
        """Tenta extrair vendor do nome do produto."""
        product_lower = product_name.lower()
        
        for vendor in self.known_vendors:
            if vendor in product_lower:
                return vendor.title()
        
        # Verificar se a primeira palavra é um vendor conhecido
        first_word = product_name.split()[0].lower()
        if first_word in self.known_vendors:
            return first_word.title()
        
        return None
    
    def _deduplicate_matches(self, matches: List[ProductMatch]) -> List[ProductMatch]:
        """Remove matches duplicados baseado no nome do produto."""
        seen = set()
        unique_matches = []
        
        for match in matches:
            # Normalizar nome do produto para comparação
            normalized_name = match.product_name.lower().strip()
            
            if normalized_name not in seen:
                seen.add(normalized_name)
                unique_matches.append(match)
        
        return unique_matches
    
    def extract_products_batch(self, descriptions: List[str]) -> Dict[int, List[ProductMatch]]:
        """Processa múltiplas descrições em lote."""
        results = {}
        
        for i, description in enumerate(descriptions):
            try:
                results[i] = self.parse_description(description)
            except Exception as e:
                self.logger.error(f"Erro ao processar descrição {i}: {e}")
                results[i] = []
        
        return results
    
    def get_statistics(self, matches_dict: Dict[int, List[ProductMatch]]) -> Dict[str, int]:
        """Calcula estatísticas dos matches encontrados."""
        total_descriptions = len(matches_dict)
        descriptions_with_matches = sum(1 for matches in matches_dict.values() if matches)
        total_matches = sum(len(matches) for matches in matches_dict.values())
        
        pattern_counts = {}
        confidence_levels = {'high': 0, 'medium': 0, 'low': 0}
        
        for matches in matches_dict.values():
            for match in matches:
                # Contar padrões
                pattern_counts[match.pattern_type] = pattern_counts.get(match.pattern_type, 0) + 1
                
                # Contar níveis de confiança
                if match.confidence >= 0.8:
                    confidence_levels['high'] += 1
                elif match.confidence >= 0.6:
                    confidence_levels['medium'] += 1
                else:
                    confidence_levels['low'] += 1
        
        return {
            'total_descriptions': total_descriptions,
            'descriptions_with_matches': descriptions_with_matches,
            'match_rate': descriptions_with_matches / total_descriptions if total_descriptions > 0 else 0,
            'total_matches': total_matches,
            'avg_matches_per_description': total_matches / total_descriptions if total_descriptions > 0 else 0,
            'pattern_counts': pattern_counts,
            'confidence_levels': confidence_levels
        }

# Função utilitária para uso direto
def parse_cve_description(description: str) -> List[ProductMatch]:
    """Função utilitária para parsing rápido de uma descrição."""
    parser = CVEDescriptionParser()
    return parser.parse_description(description)

if __name__ == '__main__':
    # Teste básico
    parser = CVEDescriptionParser()
    
    test_descriptions = [
        "Adobe Flash Player before 32.0.0.465 allows remote code execution",
        "Microsoft Windows 10 version 1903 has a vulnerability in the kernel",
        "Google Chrome 89.0.4389.82 contains a buffer overflow",
        "Vulnerability in Oracle Database allows privilege escalation",
        "The authentication component of Cisco IOS contains a flaw",
        "WordPress plugin Contact Form 7 version 5.4.1 is vulnerable"
    ]
    
    print("=== TESTE DO PARSER CVE ===")
    for i, desc in enumerate(test_descriptions):
        print(f"\nDescrição {i+1}: {desc}")
        matches = parser.parse_description(desc)
        
        if matches:
            for match in matches:
                print(f"  Produto: {match.product_name}")
                print(f"  Vendor: {match.vendor_name or 'N/A'}")
                print(f"  Confiança: {match.confidence:.2f}")
                print(f"  Padrão: {match.pattern_type}")
                print(f"  Match: {match.raw_match}")
                print()
        else:
            print("  Nenhum produto encontrado")
