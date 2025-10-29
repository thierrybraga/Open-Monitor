# project/jobs/monitoring_dispatcher.py (Assumindo que está na pasta 'jobs' dentro de 'project')

import logging
from sqlalchemy.orm import joinedload, Session # Importar Session para type hinting
from sqlalchemy.exc import SQLAlchemyError # Importar exceção de DB
from flask import Flask # Importar Flask para type hinting, se necessário para contexto
# Importação CORRETA da instância db do pacote extensions
from app.extensions import db
# Importações CORRETAS dos modelos (Assumindo que estão em project/models)
from app.models.monitoring_rule import MonitoringRule # Corrigido
from app.models.vulnerability import Vulnerability # Corrigido
from app.models.vendor import Vendor # Corrigido (assumindo este modelo existe e está relacionado a Vulnerability)

logger = logging.getLogger(__name__)

# TODO: Mover a lógica de envio de e-mail para um serviço separado (ex: project/services/email_service.py)
class EmailService:
     @staticmethod
     def send_email(to: str, subject: str, content: str) -> None:
         """Placeholder para enviar e-mail."""
         logger.info(f"Simulating sending email to {to}:\nSubject: {subject}\n{content}")
         # TODO: Implementar envio de e-mail real com Flask-Mail ou outra biblioteca
         pass


class MonitoringDispatcher:
    """
    Dispatcher responsável por encontrar vulnerabilidades correspondentes a regras
    de monitoramento ativas e despachar alertas.
    """

    # Reduzir dependência da sessão no __init__. A sessão pode ser passada para os métodos.
    # Ou, se usar um padrão de repositório/serviço, o dispatcher interage com estes.
    def __init__(self, email_service: EmailService = None): # Pode injetar serviços necessários
        self.email_service = email_service or EmailService()
        # self.db_session = db_session # Remover acoplamento direto, usar db.session no método

    def dispatch_alerts(self, db_session: Session) -> int: # Passar sessão explicitamente
        """
        Busca regras de monitoramento ativas, encontra vulnerabilidades correspondentes
        e despacha alertas.

        Retorna o número total de alertas despachados.
        """
        alerts_dispatched_count = 0
        logger.info("Starting monitoring alert dispatch.")
        try:
            # Buscar regras ativas do usuário, carregando o usuário junto
            rules = db_session.query(MonitoringRule)\
                               .filter_by(is_active=True)\
                               .options(joinedload(MonitoringRule.user))\
                               .all()
            logger.info(f"Found {len(rules)} active monitoring rules.")

            for rule in rules:
                try:
                    # Buscar vulnerabilidades para a regra atual
                    vulnerabilities = self.fetch_vulnerabilities(db_session, rule) # Passar sessão
                    if vulnerabilities:
                        logger.info(f"Rule '{rule.name}' (user={rule.user.username}) found {len(vulnerabilities)} new vulnerabilities.")
                        self.send_alert(rule, vulnerabilities) # Passar vulnerabilidades encontradas
                        alerts_dispatched_count += 1
                    else:
                        logger.debug(f"Rule '{rule.name}' (user={rule.user.username}) found no new vulnerabilities.")
                except SQLAlchemyError as db_err:
                    logger.error(f"DB error processing rule {rule.id} (user={rule.user.username}).", exc_info=db_err)
                    # Continuar para a próxima regra
                except Exception as e:
                    logger.error(f"Error processing rule {rule.id} (user={rule.user.username}).", exc_info=e)
                    # Continuar para a próxima regra

        except SQLAlchemyError as e:
            logger.error("DB error fetching active monitoring rules.", exc_info=e)
        except Exception as e:
            logger.error("An unexpected error occurred during dispatch_alerts.", exc_info=e)


        logger.info(f"Monitoring alert dispatch finished. Total alerts dispatched: {alerts_dispatched_count}.")
        return alerts_dispatched_count


    # Passar sessão explicitamente para este método
    def fetch_vulnerabilities(self, db_session: Session, rule: MonitoringRule) -> List[Vulnerability]: # Adicionado type hinting
        """
        Busca vulnerabilidades do banco de dados que correspondem aos critérios de uma regra.
        TODO: Implementar lógica para buscar APENAS vulnerabilidades NOVAS desde a última notificação para esta regra.
        """
        query = db_session.query(Vulnerability) # Usar a sessão passada

        # Aplicar filtros da regra
        if rule.vendor_id:
            # Assumindo que Vulnerability tem uma relação 'vendors' ou pode ser unido a Vendor
            # A lógica abaixo pode precisar de ajuste dependendo do seu modelo
            # query = query.join(Vulnerability.vendors).filter(Vendor.id == rule.vendor_id) # Exemplo, verificar relação
            # TODO: Se Vulnerability não tem relação direta com Vendor, pode precisar de uma tabela de associação
            pass  # Temporariamente desabilitado

        if rule.severity_filter:
            query = query.filter(Vulnerability.base_severity == rule.severity_filter)

        if rule.query:
            # Usar ilike para busca case-insensitive
            query = query.filter(Vulnerability.description.ilike(f"%{rule.query}%"))

        # TODO: Adicionar filtro de data ou outro mecanismo para buscar apenas NOVAS vulnerabilidades
        # Ex: query = query.filter(Vulnerability.published_date > rule.last_notified_date)
        # Isso requer um campo last_notified_date no modelo MonitoringRule e lógica para atualizá-lo.

        try:
            # Executar a query, ordenar e limitar
            vulnerabilities = query.order_by(Vulnerability.published_date.desc()).limit(10).all()
            return vulnerabilities
        except SQLAlchemyError as e:
            logger.error(f"DB error fetching vulnerabilities for rule {rule.id}.", exc_info=e)
            return [] # Retornar lista vazia em caso de erro


    # Passar rule e vulnerabilities encontradas
    def send_alert(self, rule: MonitoringRule, vulnerabilities: List[Vulnerability]) -> None: # Adicionado type hinting
        """
        Prepara e envia um alerta (e-mail) para o usuário associado à regra.
        TODO: Atualizar rule.last_notified_date após envio bem-sucedido.
        """
        if not rule.user or not rule.user.email:
            logger.warning(f"Rule {rule.id} has no associated user or email. Cannot send alert.")
            return

        user_email = rule.user.email
        # Assunto e conteúdo do e-mail
        subject = f"Alert: New vulnerabilities matching your rule ({rule.name or rule.query})" # Usar nome da regra se existir
        # Criar um conteúdo mais detalhado ou link para a UI
        content = "Recent vulnerabilities found for your monitoring rule:\n\n" + "\n".join(
            f"- {v.cve_id}: {v.description[:150]}... Severity: {v.base_severity} (Published: {v.published_date.strftime('%Y-%m-%d')})" # Formatar data
            for v in vulnerabilities
        ) + "\n\nView all matching vulnerabilities on the platform." # TODO: Adicionar link real

        # Usar o serviço de e-mail injetado
        try:
            self.email_service.send_email(user_email, subject, content)
            logger.info(f"Alert sent successfully for rule {rule.id} to {user_email}.")
            # TODO: Atualizar rule.last_notified_date e commitar a sessão
        except Exception as e:
            logger.error(f"Failed to send alert email for rule {rule.id} to {user_email}.", exc_info=e)


# --- Lógica para execução como script standalone ---

if __name__ == "__main__":
    # Importar a fábrica de aplicação principal
    from project.app import create_app # Corrigido importação

    # TODO: Adicionar argparse para lidar com flags como --full, --rule-id, etc.
    # import argparse
    # parser = argparse.ArgumentParser(description="Monitoring alert dispatcher job.")
    # parser.add_argument('--rule-id', type=int, help='Dispatch alerts for a specific rule ID.')
    # args = parser.parse_args()

    # Criar a aplicação Flask e rodar dentro do contexto
    app = create_app() # Usar a fábrica principal
    with app.app_context():
        # A sessão db.session já está disponível dentro do contexto do app
        dispatcher = MonitoringDispatcher() # Instanciar o dispatcher

        # TODO: Adicionar lógica para despachar para regras específicas se um ID foi passado
        # if args.rule_id:
        #     rule = db.session.query(MonitoringRule).filter_by(id=args.rule_id).first()
        #     if rule:
        #          vulnerabilities = dispatcher.fetch_vulnerabilities(db.session, rule)
        #          if vulnerabilities:
        #              dispatcher.send_alert(rule, vulnerabilities)
        #     else:
        #          logger.warning(f"Rule with ID {args.rule_id} not found.")
        # else:
        # Despachar para todas as regras ativas
        alerts_sent = dispatcher.dispatch_alerts(db.session) # Passar a sessão
        logger.info(f"Monitoring dispatch job finished. Sent {alerts_sent} alerts.")


    # TODO: Considerar adicionar um código de saída (exit code) para indicar sucesso/falha