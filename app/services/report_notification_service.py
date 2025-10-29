"""
Serviço de notificações para relatórios de segurança
Gerencia notificações por email, webhook, Slack e outras integrações
"""

import logging
import smtplib
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from dataclasses import dataclass, asdict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
import asyncio
import aiohttp

logger = logging.getLogger(__name__)

class NotificationType(Enum):
    """Tipos de notificação"""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    TEAMS = "teams"
    DISCORD = "discord"
    SMS = "sms"
    PUSH = "push"

class NotificationPriority(Enum):
    """Prioridades de notificação"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

class NotificationEvent(Enum):
    """Eventos que geram notificações"""
    REPORT_CREATED = "report_created"
    REPORT_COMPLETED = "report_completed"
    REPORT_FAILED = "report_failed"
    CRITICAL_VULNERABILITIES = "critical_vulnerabilities"
    HIGH_RISK_DETECTED = "high_risk_detected"
    COMPLIANCE_VIOLATION = "compliance_violation"
    SCHEDULED_REPORT = "scheduled_report"
    MANUAL_TRIGGER = "manual_trigger"

@dataclass
class NotificationChannel:
    """Canal de notificação"""
    id: str
    name: str
    type: NotificationType
    config: Dict[str, Any]
    enabled: bool = True
    events: List[NotificationEvent] = None
    priority_filter: Optional[NotificationPriority] = None
    created_at: Optional[datetime] = None

@dataclass
class NotificationTemplate:
    """Template de notificação"""
    id: str
    name: str
    event: NotificationEvent
    subject_template: str
    body_template: str
    html_template: Optional[str] = None
    variables: List[str] = None
    created_at: Optional[datetime] = None

@dataclass
class Notification:
    """Notificação individual"""
    id: str
    channel_id: str
    event: NotificationEvent
    priority: NotificationPriority
    subject: str
    message: str
    html_message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    status: str = "pending"  # pending, sent, failed
    attempts: int = 0
    max_attempts: int = 3
    created_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None

class ReportNotificationService:
    """Serviço de notificações para relatórios"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.channels = {}
        self.templates = {}
        self.notification_queue = []
        self._initialize_default_templates()
        
    def _initialize_default_templates(self):
        """Inicializa templates padrão de notificação"""
        
        # Template para relatório criado
        self.templates["report_created"] = NotificationTemplate(
            id="report_created",
            name="Relatório Criado",
            event=NotificationEvent.REPORT_CREATED,
            subject_template="Novo relatório criado: {report_title}",
            body_template="""
Olá {recipient_name},

Um novo relatório de segurança foi criado:

📊 Título: {report_title}
🔍 Tipo: {report_type}
📅 Data de Criação: {created_at}
👤 Criado por: {created_by}
🎯 Escopo: {scope}

O relatório está sendo processado e você será notificado quando estiver concluído.

Acesse o relatório: {report_url}

---
Sistema de Monitoramento de Segurança
            """.strip(),
            html_template="""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #007bff;">📊 Novo Relatório Criado</h2>
    
    <p>Olá <strong>{recipient_name}</strong>,</p>
    
    <p>Um novo relatório de segurança foi criado:</p>
    
    <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0;">
        <p><strong>📊 Título:</strong> {report_title}</p>
        <p><strong>🔍 Tipo:</strong> {report_type}</p>
        <p><strong>📅 Data de Criação:</strong> {created_at}</p>
        <p><strong>👤 Criado por:</strong> {created_by}</p>
        <p><strong>🎯 Escopo:</strong> {scope}</p>
    </div>
    
    <p>O relatório está sendo processado e você será notificado quando estiver concluído.</p>
    
    <div style="text-align: center; margin: 20px 0;">
        <a href="{report_url}" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
            Acessar Relatório
        </a>
    </div>
    
    <hr style="margin: 20px 0;">
    <p style="color: #6c757d; font-size: 12px;">Sistema de Monitoramento de Segurança</p>
</div>
            """.strip(),
            variables=["recipient_name", "report_title", "report_type", "created_at", "created_by", "scope", "report_url"]
        )
        
        # Template para relatório concluído
        self.templates["report_completed"] = NotificationTemplate(
            id="report_completed",
            name="Relatório Concluído",
            event=NotificationEvent.REPORT_COMPLETED,
            subject_template="✅ Relatório concluído: {report_title}",
            body_template="""
Olá {recipient_name},

O relatório de segurança foi concluído com sucesso:

📊 Título: {report_title}
🔍 Tipo: {report_type}
✅ Status: Concluído
📅 Gerado em: {completed_at}
⏱️ Tempo de processamento: {processing_time}

📈 Resumo dos Resultados:
• Total de vulnerabilidades: {total_vulnerabilities}
• Vulnerabilidades críticas: {critical_vulnerabilities}
• Vulnerabilidades altas: {high_vulnerabilities}
• Score de risco: {risk_score}/10

Acesse o relatório completo: {report_url}

---
Sistema de Monitoramento de Segurança
            """.strip(),
            html_template="""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #28a745;">✅ Relatório Concluído</h2>
    
    <p>Olá <strong>{recipient_name}</strong>,</p>
    
    <p>O relatório de segurança foi concluído com sucesso:</p>
    
    <div style="background: #d4edda; border: 1px solid #c3e6cb; padding: 15px; border-radius: 5px; margin: 15px 0;">
        <p><strong>📊 Título:</strong> {report_title}</p>
        <p><strong>🔍 Tipo:</strong> {report_type}</p>
        <p><strong>✅ Status:</strong> Concluído</p>
        <p><strong>📅 Gerado em:</strong> {completed_at}</p>
        <p><strong>⏱️ Tempo de processamento:</strong> {processing_time}</p>
    </div>
    
    <h3 style="color: #495057;">📈 Resumo dos Resultados</h3>
    <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0;">
        <p>• <strong>Total de vulnerabilidades:</strong> {total_vulnerabilities}</p>
        <p>• <strong>Vulnerabilidades críticas:</strong> <span style="color: #dc3545;">{critical_vulnerabilities}</span></p>
        <p>• <strong>Vulnerabilidades altas:</strong> <span style="color: #fd7e14;">{high_vulnerabilities}</span></p>
        <p>• <strong>Score de risco:</strong> <span style="font-size: 18px; font-weight: bold;">{risk_score}/10</span></p>
    </div>
    
    <div style="text-align: center; margin: 20px 0;">
        <a href="{report_url}" style="background: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
            Acessar Relatório Completo
        </a>
    </div>
    
    <hr style="margin: 20px 0;">
    <p style="color: #6c757d; font-size: 12px;">Sistema de Monitoramento de Segurança</p>
</div>
            """.strip(),
            variables=["recipient_name", "report_title", "report_type", "completed_at", "processing_time", 
                      "total_vulnerabilities", "critical_vulnerabilities", "high_vulnerabilities", 
                      "risk_score", "report_url"]
        )
        
        # Template para vulnerabilidades críticas
        self.templates["critical_vulnerabilities"] = NotificationTemplate(
            id="critical_vulnerabilities",
            name="Vulnerabilidades Críticas Detectadas",
            event=NotificationEvent.CRITICAL_VULNERABILITIES,
            subject_template="🚨 CRÍTICO: Vulnerabilidades críticas detectadas - {report_title}",
            body_template="""
ALERTA CRÍTICO DE SEGURANÇA

Olá {recipient_name},

Vulnerabilidades críticas foram detectadas no relatório: {report_title}

🚨 VULNERABILIDADES CRÍTICAS ENCONTRADAS: {critical_count}

Detalhes das vulnerabilidades mais críticas:
{critical_vulnerabilities_list}

⚠️ AÇÃO IMEDIATA NECESSÁRIA ⚠️

Este alerta requer atenção imediata da equipe de segurança.

Acesse o relatório completo: {report_url}

---
Sistema de Monitoramento de Segurança - ALERTA CRÍTICO
            """.strip(),
            html_template="""
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background: #dc3545; color: white; padding: 15px; border-radius: 5px 5px 0 0; text-align: center;">
        <h2 style="margin: 0;">🚨 ALERTA CRÍTICO DE SEGURANÇA</h2>
    </div>
    
    <div style="border: 2px solid #dc3545; padding: 20px; border-radius: 0 0 5px 5px;">
        <p>Olá <strong>{recipient_name}</strong>,</p>
        
        <p><strong>Vulnerabilidades críticas foram detectadas no relatório:</strong> {report_title}</p>
        
        <div style="background: #f8d7da; border: 1px solid #f5c6cb; padding: 15px; border-radius: 5px; margin: 15px 0;">
            <h3 style="color: #721c24; margin-top: 0;">🚨 VULNERABILIDADES CRÍTICAS ENCONTRADAS: {critical_count}</h3>
            
            <div style="margin: 15px 0;">
                <strong>Detalhes das vulnerabilidades mais críticas:</strong>
                <div style="margin-top: 10px;">
                    {critical_vulnerabilities_list}
                </div>
            </div>
        </div>
        
        <div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 15px 0; text-align: center;">
            <h3 style="color: #856404; margin: 0;">⚠️ AÇÃO IMEDIATA NECESSÁRIA ⚠️</h3>
            <p style="margin: 10px 0 0 0; color: #856404;">Este alerta requer atenção imediata da equipe de segurança.</p>
        </div>
        
        <div style="text-align: center; margin: 20px 0;">
            <a href="{report_url}" style="background: #dc3545; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                ACESSAR RELATÓRIO COMPLETO
            </a>
        </div>
    </div>
    
    <hr style="margin: 20px 0;">
    <p style="color: #6c757d; font-size: 12px; text-align: center;">Sistema de Monitoramento de Segurança - ALERTA CRÍTICO</p>
</div>
            """.strip(),
            variables=["recipient_name", "report_title", "critical_count", "critical_vulnerabilities_list", "report_url"]
        )
        
        # Template para falha no relatório
        self.templates["report_failed"] = NotificationTemplate(
            id="report_failed",
            name="Falha na Geração do Relatório",
            event=NotificationEvent.REPORT_FAILED,
            subject_template="❌ Falha na geração do relatório: {report_title}",
            body_template="""
Olá {recipient_name},

Houve uma falha na geração do relatório de segurança:

📊 Título: {report_title}
🔍 Tipo: {report_type}
❌ Status: Falhou
📅 Tentativa em: {failed_at}
🔄 Tentativas: {attempts}/{max_attempts}

❗ Erro: {error_message}

A equipe técnica foi notificada e está investigando o problema.
{retry_info}

Acesse os detalhes: {report_url}

---
Sistema de Monitoramento de Segurança
            """.strip(),
            variables=["recipient_name", "report_title", "report_type", "failed_at", "attempts", 
                      "max_attempts", "error_message", "retry_info", "report_url"]
        )
    
    def add_channel(self, channel: NotificationChannel):
        """Adiciona um canal de notificação"""
        self.channels[channel.id] = channel
        logger.info(f"Canal de notificação adicionado: {channel.name} ({channel.type.value})")
    
    def add_email_channel(self, channel_id: str, name: str, smtp_config: Dict[str, Any], 
                         recipients: List[str], events: List[NotificationEvent] = None):
        """Adiciona canal de email"""
        config = {
            "smtp_server": smtp_config.get("server"),
            "smtp_port": smtp_config.get("port", 587),
            "username": smtp_config.get("username"),
            "password": smtp_config.get("password"),
            "use_tls": smtp_config.get("use_tls", True),
            "from_email": smtp_config.get("from_email"),
            "from_name": smtp_config.get("from_name", "Sistema de Segurança"),
            "recipients": recipients
        }
        
        channel = NotificationChannel(
            id=channel_id,
            name=name,
            type=NotificationType.EMAIL,
            config=config,
            events=events or list(NotificationEvent),
            created_at=datetime.now()
        )
        
        self.add_channel(channel)
    
    def add_slack_channel(self, channel_id: str, name: str, webhook_url: str, 
                         channel_name: str = None, events: List[NotificationEvent] = None):
        """Adiciona canal do Slack"""
        config = {
            "webhook_url": webhook_url,
            "channel": channel_name,
            "username": "Security Bot",
            "icon_emoji": ":shield:"
        }
        
        channel = NotificationChannel(
            id=channel_id,
            name=name,
            type=NotificationType.SLACK,
            config=config,
            events=events or list(NotificationEvent),
            created_at=datetime.now()
        )
        
        self.add_channel(channel)
    
    def add_webhook_channel(self, channel_id: str, name: str, webhook_url: str,
                           headers: Dict[str, str] = None, events: List[NotificationEvent] = None):
        """Adiciona canal de webhook"""
        config = {
            "webhook_url": webhook_url,
            "headers": headers or {"Content-Type": "application/json"},
            "method": "POST"
        }
        
        channel = NotificationChannel(
            id=channel_id,
            name=name,
            type=NotificationType.WEBHOOK,
            config=config,
            events=events or list(NotificationEvent),
            created_at=datetime.now()
        )
        
        self.add_channel(channel)
    
    def send_notification(self, event: NotificationEvent, report_data: Dict[str, Any],
                         priority: NotificationPriority = NotificationPriority.NORMAL,
                         custom_data: Dict[str, Any] = None):
        """Envia notificação para todos os canais configurados"""
        
        try:
            # Filtrar canais que devem receber esta notificação
            target_channels = self._get_target_channels(event, priority)
            
            if not target_channels:
                logger.info(f"Nenhum canal configurado para evento {event.value}")
                return
            
            # Preparar dados para templates
            template_data = self._prepare_template_data(report_data, custom_data)
            
            # Enviar para cada canal
            for channel in target_channels:
                try:
                    self._send_to_channel(channel, event, template_data, priority)
                except Exception as e:
                    logger.error(f"Erro ao enviar notificação para canal {channel.name}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Erro ao processar notificação: {str(e)}")
    
    def _get_target_channels(self, event: NotificationEvent, 
                           priority: NotificationPriority) -> List[NotificationChannel]:
        """Obtém canais que devem receber a notificação"""
        target_channels = []
        
        for channel in self.channels.values():
            if not channel.enabled:
                continue
                
            # Verificar se o canal está configurado para este evento
            if channel.events and event not in channel.events:
                continue
                
            # Verificar filtro de prioridade
            if channel.priority_filter:
                priority_levels = {
                    NotificationPriority.LOW: 1,
                    NotificationPriority.NORMAL: 2,
                    NotificationPriority.HIGH: 3,
                    NotificationPriority.CRITICAL: 4
                }
                
                if priority_levels[priority] < priority_levels[channel.priority_filter]:
                    continue
                    
            target_channels.append(channel)
            
        return target_channels
    
    def _prepare_template_data(self, report_data: Dict[str, Any], 
                             custom_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Prepara dados para os templates de forma robusta (datetime ou string ISO)."""

        def _format_dt(value: Any) -> str:
            try:
                if isinstance(value, datetime):
                    return value.strftime("%d/%m/%Y %H:%M")
                if isinstance(value, str):
                    try:
                        iso = value.replace("Z", "+00:00")
                        dt = datetime.fromisoformat(iso)
                        return dt.strftime("%d/%m/%Y %H:%M")
                    except Exception:
                        return value
                return str(value)
            except Exception:
                return str(value)

        data = {
            "recipient_name": "Usuário",
            "report_title": report_data.get("title", "Relatório de Segurança"),
            "report_type": report_data.get("type", "Análise"),
            "report_url": report_data.get("url", "#"),
            "created_at": _format_dt(report_data.get("created_at", datetime.now())),
            "created_by": report_data.get("created_by", "Sistema"),
            "scope": report_data.get("scope", "Não especificado"),
            "completed_at": _format_dt(report_data.get("completed_at", datetime.now())),
            "processing_time": report_data.get("processing_time", "N/A"),
            "total_vulnerabilities": report_data.get("total_vulnerabilities", 0),
            "critical_vulnerabilities": report_data.get("critical_vulnerabilities", 0),
            "high_vulnerabilities": report_data.get("high_vulnerabilities", 0),
            "risk_score": report_data.get("risk_score", 0),
            "critical_count": report_data.get("critical_vulnerabilities", 0),
            "error_message": report_data.get("error_message", "Erro desconhecido"),
            "attempts": report_data.get("attempts", 1),
            "max_attempts": report_data.get("max_attempts", 3),
            "failed_at": _format_dt(report_data.get("failed_at", datetime.now())),
            "retry_info": report_data.get("retry_info", "")
        }
        
        # Preparar lista de vulnerabilidades críticas
        if "critical_vulnerabilities_details" in report_data:
            vuln_list = []
            for vuln in report_data["critical_vulnerabilities_details"][:5]:  # Top 5
                vuln_list.append(f"• {vuln.get('title', 'N/A')} (CVSS: {vuln.get('cvss_score', 'N/A')})")
            data["critical_vulnerabilities_list"] = "\n".join(vuln_list)
        else:
            data["critical_vulnerabilities_list"] = "Detalhes não disponíveis"
        
        # Adicionar dados customizados
        if custom_data:
            data.update(custom_data)
            
        return data
    
    def _send_to_channel(self, channel: NotificationChannel, event: NotificationEvent,
                        template_data: Dict[str, Any], priority: NotificationPriority):
        """Envia notificação para um canal específico"""
        
        # Obter template
        template = self.templates.get(event.value)
        if not template:
            logger.warning(f"Template não encontrado para evento {event.value}")
            return
        
        # Renderizar mensagem
        subject = self._render_template(template.subject_template, template_data)
        message = self._render_template(template.body_template, template_data)
        html_message = None
        
        if template.html_template:
            html_message = self._render_template(template.html_template, template_data)
        
        # Criar notificação
        notification = Notification(
            id=f"{channel.id}_{event.value}_{datetime.now().timestamp()}",
            channel_id=channel.id,
            event=event,
            priority=priority,
            subject=subject,
            message=message,
            html_message=html_message,
            data=template_data,
            created_at=datetime.now()
        )
        
        # Enviar baseado no tipo do canal
        if channel.type == NotificationType.EMAIL:
            self._send_email(channel, notification)
        elif channel.type == NotificationType.SLACK:
            self._send_slack(channel, notification)
        elif channel.type == NotificationType.WEBHOOK:
            self._send_webhook(channel, notification)
        else:
            logger.warning(f"Tipo de canal não suportado: {channel.type.value}")
    
    def _render_template(self, template: str, data: Dict[str, Any]) -> str:
        """Renderiza template com dados"""
        try:
            return template.format(**data)
        except KeyError as e:
            logger.warning(f"Variável não encontrada no template: {e}")
            return template
        except Exception as e:
            logger.error(f"Erro ao renderizar template: {e}")
            return template
    
    def _send_email(self, channel: NotificationChannel, notification: Notification):
        """Envia notificação por email"""
        try:
            config = channel.config
            
            # Configurar servidor SMTP
            server = smtplib.SMTP(config["smtp_server"], config["smtp_port"])
            if config.get("use_tls", True):
                server.starttls()
            
            if config.get("username") and config.get("password"):
                server.login(config["username"], config["password"])
            
            # Criar mensagem
            msg = MIMEMultipart('alternative')
            msg['Subject'] = notification.subject
            msg['From'] = f"{config.get('from_name', 'Sistema')} <{config['from_email']}>"
            msg['To'] = ", ".join(config["recipients"])
            
            # Adicionar texto simples
            text_part = MIMEText(notification.message, 'plain', 'utf-8')
            msg.attach(text_part)
            
            # Adicionar HTML se disponível
            if notification.html_message:
                html_part = MIMEText(notification.html_message, 'html', 'utf-8')
                msg.attach(html_part)
            
            # Enviar
            server.send_message(msg)
            server.quit()
            
            notification.status = "sent"
            notification.sent_at = datetime.now()
            logger.info(f"Email enviado com sucesso para {len(config['recipients'])} destinatários")
            
        except Exception as e:
            notification.status = "failed"
            notification.error_message = str(e)
            notification.attempts += 1
            logger.error(f"Erro ao enviar email: {str(e)}")
    
    def _send_slack(self, channel: NotificationChannel, notification: Notification):
        """Envia notificação para Slack"""
        try:
            config = channel.config
            
            # Preparar payload
            payload = {
                "text": notification.subject,
                "username": config.get("username", "Security Bot"),
                "icon_emoji": config.get("icon_emoji", ":shield:")
            }
            
            if config.get("channel"):
                payload["channel"] = config["channel"]
            
            # Criar attachment com detalhes
            color = self._get_slack_color(notification.priority)
            attachment = {
                "color": color,
                "text": notification.message,
                "ts": int(notification.created_at.timestamp())
            }
            
            payload["attachments"] = [attachment]
            
            # Enviar
            response = requests.post(
                config["webhook_url"],
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            notification.status = "sent"
            notification.sent_at = datetime.now()
            logger.info("Notificação Slack enviada com sucesso")
            
        except Exception as e:
            notification.status = "failed"
            notification.error_message = str(e)
            notification.attempts += 1
            logger.error(f"Erro ao enviar notificação Slack: {str(e)}")
    
    def _send_webhook(self, channel: NotificationChannel, notification: Notification):
        """Envia notificação via webhook"""
        try:
            config = channel.config
            
            # Preparar payload
            payload = {
                "event": notification.event.value,
                "priority": notification.priority.value,
                "subject": notification.subject,
                "message": notification.message,
                "timestamp": notification.created_at.isoformat(),
                "data": notification.data
            }
            
            # Enviar
            response = requests.post(
                config["webhook_url"],
                json=payload,
                headers=config.get("headers", {}),
                timeout=30
            )
            response.raise_for_status()
            
            notification.status = "sent"
            notification.sent_at = datetime.now()
            logger.info("Webhook enviado com sucesso")
            
        except Exception as e:
            notification.status = "failed"
            notification.error_message = str(e)
            notification.attempts += 1
            logger.error(f"Erro ao enviar webhook: {str(e)}")
    
    def _get_slack_color(self, priority: NotificationPriority) -> str:
        """Obtém cor para notificação Slack baseada na prioridade"""
        color_map = {
            NotificationPriority.LOW: "#36a64f",      # Verde
            NotificationPriority.NORMAL: "#439fe0",   # Azul
            NotificationPriority.HIGH: "#ff9500",     # Laranja
            NotificationPriority.CRITICAL: "#ff0000"  # Vermelho
        }
        return color_map.get(priority, "#439fe0")
    
    def get_notification_history(self, limit: int = 100) -> List[Notification]:
        """Obtém histórico de notificações"""
        return self.notification_queue[-limit:]
    
    def get_channel_statistics(self) -> Dict[str, Any]:
        """Obtém estatísticas dos canais"""
        stats = {
            "total_channels": len(self.channels),
            "active_channels": len([c for c in self.channels.values() if c.enabled]),
            "channels_by_type": {},
            "total_notifications": len(self.notification_queue),
            "notifications_by_status": {"sent": 0, "failed": 0, "pending": 0}
        }
        
        # Estatísticas por tipo de canal
        for channel in self.channels.values():
            channel_type = channel.type.value
            if channel_type not in stats["channels_by_type"]:
                stats["channels_by_type"][channel_type] = 0
            stats["channels_by_type"][channel_type] += 1
        
        # Estatísticas por status
        for notification in self.notification_queue:
            status = notification.status
            if status in stats["notifications_by_status"]:
                stats["notifications_by_status"][status] += 1
        
        return stats