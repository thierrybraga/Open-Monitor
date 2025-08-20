import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import text, or_, and_
from flask import current_app
from models.vulnerability import Vulnerability
from models.cve_product import CVEProduct
from models.cve_vendor import CVEVendor
from models.weakness import Weakness
from models.references import Reference
from extensions.db import db
from services.openai_service import OpenAIService
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RAGService:
    """
    Serviço RAG (Retrieval-Augmented Generation) para consulta de dados CVE.
    
    Combina busca semântica em dados de vulnerabilidades com geração de respostas
    usando IA para fornecer informações contextualizadas sobre CVEs.
    """
    
    def __init__(self):
        """
        Inicializa o serviço RAG.
        """
        self.openai_service = None
        logger.info("RAG Service inicializado")
    
    def _get_openai_service(self) -> OpenAIService:
        """
        Obtém instância do serviço OpenAI (lazy loading).
        
        Returns:
            Instância do OpenAIService
        """
        if self.openai_service is None:
            try:
                self.openai_service = OpenAIService()
            except Exception as e:
                logger.error(f"Erro ao inicializar OpenAI Service: {str(e)}")
                raise
        return self.openai_service
    
    def search_and_generate_response(
        self, 
        user_query: str, 
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Busca dados relevantes e gera resposta usando IA.
        
        Args:
            user_query: Pergunta do usuário
            conversation_history: Histórico da conversa
            
        Returns:
            Dicionário com resposta e dados relevantes
        """
        try:
            # 1. Analisar a query e extrair entidades
            entities = self._extract_entities(user_query)
            
            # 2. Buscar dados relevantes
            relevant_data = self._search_relevant_data(user_query, entities)
            
            # 3. Construir contexto
            context = self._build_context(relevant_data, user_query)
            
            # 4. Gerar resposta com IA
            openai_service = self._get_openai_service()
            ai_response = openai_service.generate_chat_response(
                user_query, 
                context, 
                conversation_history
            )
            
            return {
                'response': ai_response,
                'relevant_cves': relevant_data.get('vulnerabilities', []),
                'context_used': bool(context),
                'entities_found': entities
            }
            
        except Exception as e:
            logger.error(f"Erro no RAG Service: {str(e)}")
            return {
                'response': "Desculpe, ocorreu um erro ao processar sua pergunta. Tente novamente.",
                'relevant_cves': [],
                'context_used': False,
                'entities_found': {}
            }
    
    def _extract_entities(self, query: str) -> Dict[str, List[str]]:
        """
        Extrai entidades relevantes da query do usuário.
        
        Args:
            query: Query do usuário
            
        Returns:
            Dicionário com entidades extraídas
        """
        entities = {
            'cve_ids': [],
            'products': [],
            'vendors': [],
            'severities': [],
            'years': [],
            'keywords': []
        }
        
        query_lower = query.lower()
        
        # Extrair CVE IDs
        cve_pattern = r'cve-\d{4}-\d{4,}'
        entities['cve_ids'] = re.findall(cve_pattern, query_lower)
        
        # Extrair anos
        year_pattern = r'\b(20\d{2})\b'
        entities['years'] = re.findall(year_pattern, query)
        
        # Extrair severidades
        severity_keywords = ['critical', 'high', 'medium', 'low', 'crítica', 'alta', 'média', 'baixa']
        for severity in severity_keywords:
            if severity in query_lower:
                entities['severities'].append(severity)
        
        # Extrair produtos/tecnologias comuns
        common_products = [
            'windows', 'linux', 'apache', 'nginx', 'mysql', 'postgresql', 
            'wordpress', 'drupal', 'joomla', 'php', 'java', 'python',
            'log4j', 'spring', 'struts', 'tomcat', 'iis', 'exchange',
            'outlook', 'chrome', 'firefox', 'safari', 'edge'
        ]
        
        for product in common_products:
            if product in query_lower:
                entities['products'].append(product)
        
        # Extrair vendors comuns
        common_vendors = [
            'microsoft', 'google', 'apple', 'oracle', 'adobe', 
            'cisco', 'vmware', 'redhat', 'ubuntu', 'debian'
        ]
        
        for vendor in common_vendors:
            if vendor in query_lower:
                entities['vendors'].append(vendor)
        
        # Palavras-chave de segurança
        security_keywords = [
            'rce', 'sql injection', 'xss', 'csrf', 'buffer overflow',
            'privilege escalation', 'denial of service', 'dos', 'ddos',
            'authentication bypass', 'directory traversal', 'lfi', 'rfi'
        ]
        
        for keyword in security_keywords:
            if keyword in query_lower:
                entities['keywords'].append(keyword)
        
        return entities
    
    def _search_relevant_data(
        self, 
        query: str, 
        entities: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """
        Busca dados relevantes no banco de dados.
        
        Args:
            query: Query original do usuário
            entities: Entidades extraídas
            
        Returns:
            Dados relevantes encontrados
        """
        relevant_data = {
            'vulnerabilities': [],
            'total_found': 0
        }
        
        try:
            # Construir query base
            base_query = db.session.query(Vulnerability)
            
            # Aplicar filtros baseados nas entidades
            filters = []
            
            # Filtro por CVE IDs específicos
            if entities['cve_ids']:
                cve_filters = []
                for cve_id in entities['cve_ids']:
                    cve_filters.append(Vulnerability.cve_id.ilike(f"%{cve_id}%"))
                filters.append(or_(*cve_filters))
            
            # Filtro por produtos
            if entities['products']:
                product_filters = []
                for product in entities['products']:
                    product_filters.append(
                        Vulnerability.products.any(
                            CVEProduct.product_name.ilike(f"%{product}%")
                        )
                    )
                filters.append(or_(*product_filters))
            
            # Filtro por vendors
            if entities['vendors']:
                vendor_filters = []
                for vendor in entities['vendors']:
                    vendor_filters.append(
                        Vulnerability.vendors.any(
                            CVEVendor.vendor_name.ilike(f"%{vendor}%")
                        )
                    )
                filters.append(or_(*vendor_filters))
            
            # Filtro por severidade
            if entities['severities']:
                severity_map = {
                    'critical': 'CRITICAL', 'crítica': 'CRITICAL',
                    'high': 'HIGH', 'alta': 'HIGH',
                    'medium': 'MEDIUM', 'média': 'MEDIUM',
                    'low': 'LOW', 'baixa': 'LOW'
                }
                
                severity_filters = []
                for severity in entities['severities']:
                    mapped_severity = severity_map.get(severity.lower())
                    if mapped_severity:
                        severity_filters.append(
                            Vulnerability.base_severity == mapped_severity
                        )
                if severity_filters:
                    filters.append(or_(*severity_filters))
            
            # Filtro por ano
            if entities['years']:
                year_filters = []
                for year in entities['years']:
                    year_start = datetime(int(year), 1, 1)
                    year_end = datetime(int(year), 12, 31)
                    year_filters.append(
                        and_(
                            Vulnerability.published_date >= year_start,
                            Vulnerability.published_date <= year_end
                        )
                    )
                filters.append(or_(*year_filters))
            
            # Busca textual na descrição
            if entities['keywords'] or not any(entities.values()):
                text_search_terms = entities['keywords'] + [query]
                text_filters = []
                for term in text_search_terms:
                    if len(term) > 2:  # Evitar termos muito curtos
                        text_filters.append(
                            Vulnerability.description.ilike(f"%{term}%")
                        )
                if text_filters:
                    filters.append(or_(*text_filters))
            
            # Aplicar filtros
            if filters:
                final_query = base_query.filter(or_(*filters))
            else:
                # Se não há filtros específicos, buscar vulnerabilidades recentes
                recent_date = datetime.now() - timedelta(days=365)
                final_query = base_query.filter(
                    Vulnerability.published_date >= recent_date
                )
            
            # Ordenar por relevância (CVSS score e data)
            final_query = final_query.order_by(
                Vulnerability.cvss_score.desc(),
                Vulnerability.published_date.desc()
            )
            
            # Limitar resultados
            vulnerabilities = final_query.limit(10).all()
            
            # Converter para dicionários
            relevant_data['vulnerabilities'] = [
                self._vulnerability_to_dict(vuln) for vuln in vulnerabilities
            ]
            relevant_data['total_found'] = final_query.count()
            
        except Exception as e:
            logger.error(f"Erro na busca de dados: {str(e)}")
        
        return relevant_data
    
    def _vulnerability_to_dict(self, vulnerability: Vulnerability) -> Dict[str, Any]:
        """
        Converte objeto Vulnerability para dicionário.
        
        Args:
            vulnerability: Objeto Vulnerability
            
        Returns:
            Dicionário com dados da vulnerabilidade
        """
        return {
            'cve_id': vulnerability.cve_id,
            'description': vulnerability.description,
            'base_severity': vulnerability.base_severity,
            'cvss_score': vulnerability.cvss_score,
            'published_date': vulnerability.published_date.isoformat() if vulnerability.published_date else None,
            'patch_available': vulnerability.patch_available,
            'products': [p.product_name for p in vulnerability.products] if vulnerability.products else [],
            'vendors': [v.vendor_name for v in vulnerability.vendors] if vulnerability.vendors else [],
            'weaknesses': [w.weakness_name for w in vulnerability.weaknesses] if vulnerability.weaknesses else []
        }
    
    def _build_context(self, relevant_data: Dict[str, Any], user_query: str) -> str:
        """
        Constrói contexto para a IA baseado nos dados encontrados.
        
        Args:
            relevant_data: Dados relevantes encontrados
            user_query: Query do usuário
            
        Returns:
            Contexto formatado
        """
        if not relevant_data['vulnerabilities']:
            return ""
        
        context_parts = []
        context_parts.append(f"Encontradas {len(relevant_data['vulnerabilities'])} vulnerabilidades relevantes:")
        context_parts.append("")
        
        for i, vuln in enumerate(relevant_data['vulnerabilities'][:5], 1):
            context_parts.append(f"{i}. {vuln['cve_id']}")
            context_parts.append(f"   Severidade: {vuln['base_severity']} (CVSS: {vuln['cvss_score']})")
            context_parts.append(f"   Descrição: {vuln['description'][:200]}...")
            
            if vuln['products']:
                context_parts.append(f"   Produtos: {', '.join(vuln['products'][:3])}")
            
            if vuln['vendors']:
                context_parts.append(f"   Vendors: {', '.join(vuln['vendors'][:3])}")
            
            context_parts.append(f"   Data: {vuln['published_date'][:10] if vuln['published_date'] else 'N/A'}")
            context_parts.append("")
        
        if len(relevant_data['vulnerabilities']) > 5:
            context_parts.append(f"... e mais {len(relevant_data['vulnerabilities']) - 5} vulnerabilidades.")
        
        return "\n".join(context_parts)
    
    def get_cve_details(self, cve_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém detalhes específicos de uma CVE.
        
        Args:
            cve_id: ID da CVE
            
        Returns:
            Dados detalhados da CVE ou None se não encontrada
        """
        try:
            vulnerability = db.session.query(Vulnerability).filter(
                Vulnerability.cve_id.ilike(f"%{cve_id}%")
            ).first()
            
            if vulnerability:
                return self._vulnerability_to_dict(vulnerability)
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao buscar CVE {cve_id}: {str(e)}")
            return None
    
    def get_trending_vulnerabilities(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Obtém vulnerabilidades em tendência (recentes e críticas).
        
        Args:
            days: Número de dias para considerar como "recente"
            
        Returns:
            Lista de vulnerabilidades em tendência
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            vulnerabilities = db.session.query(Vulnerability).filter(
                and_(
                    Vulnerability.published_date >= cutoff_date,
                    Vulnerability.base_severity.in_(['CRITICAL', 'HIGH'])
                )
            ).order_by(
                Vulnerability.cvss_score.desc(),
                Vulnerability.published_date.desc()
            ).limit(10).all()
            
            return [self._vulnerability_to_dict(vuln) for vuln in vulnerabilities]
            
        except Exception as e:
            logger.error(f"Erro ao buscar vulnerabilidades em tendência: {str(e)}")
            return []