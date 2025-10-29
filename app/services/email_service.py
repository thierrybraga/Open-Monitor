# services/email_service.py

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict, Any
from flask import current_app
from jinja2 import Template

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails including newsletters."""
    
    def __init__(self):
        """Initialize email service with Flask app configuration."""
        self.smtp_server = current_app.config.get('MAIL_SERVER', 'localhost')
        self.smtp_port = current_app.config.get('MAIL_PORT', 587)
        self.smtp_username = current_app.config.get('MAIL_USERNAME')
        self.smtp_password = current_app.config.get('MAIL_PASSWORD')
        self.use_tls = current_app.config.get('MAIL_USE_TLS', True)
        self.use_ssl = current_app.config.get('MAIL_USE_SSL', False)
        self.default_sender = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@opencvereport.com')
    
    def _create_smtp_connection(self):
        """Create and configure SMTP connection."""
        try:
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                if self.use_tls:
                    server.starttls()
            
            if self.smtp_username and self.smtp_password:
                server.login(self.smtp_username, self.smtp_password)
            
            return server
        except Exception as e:
            logger.error(f"Failed to create SMTP connection: {e}")
            raise
    
    def send_email(
        self,
        to_emails: List[str],
        subject: str,
        content: str,
        content_type: str = 'html',
        from_email: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Send email to multiple recipients.
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            content: Email content
            content_type: 'html' or 'plain'
            from_email: Sender email (optional)
            attachments: List of attachment dictionaries with 'filename' and 'content'
        
        Returns:
            True if email was sent successfully, False otherwise
        """
        try:
            from_email = from_email or self.default_sender
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = from_email
            msg['To'] = ', '.join(to_emails)
            
            # Add content
            if content_type == 'html':
                msg.attach(MIMEText(content, 'html', 'utf-8'))
            else:
                msg.attach(MIMEText(content, 'plain', 'utf-8'))
            
            # Add attachments if any
            if attachments:
                for attachment in attachments:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment['content'])
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {attachment["filename"]}'
                    )
                    msg.attach(part)
            
            # Send email
            with self._create_smtp_connection() as server:
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {len(to_emails)} recipients")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def send_newsletter(
        self,
        subscribers: List[str],
        subject: str,
        content: str,
        content_type: str = 'html',
        template_vars: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send newsletter to multiple subscribers.
        
        Args:
            subscribers: List of subscriber email addresses
            subject: Newsletter subject
            content: Newsletter content (can include Jinja2 template variables)
            content_type: 'html' or 'plain'
            template_vars: Variables to render in the template
        
        Returns:
            Dictionary with success/failure statistics
        """
        if not subscribers:
            return {'sent': 0, 'failed': 0, 'errors': []}
        
        # Render template if variables provided
        if template_vars:
            try:
                template = Template(content)
                content = template.render(**template_vars)
            except Exception as e:
                logger.error(f"Failed to render newsletter template: {e}")
                return {'sent': 0, 'failed': len(subscribers), 'errors': [str(e)]}
        
        # Send in batches to avoid overwhelming SMTP server
        batch_size = current_app.config.get('NEWSLETTER_BATCH_SIZE', 50)
        sent_count = 0
        failed_count = 0
        errors = []
        
        for i in range(0, len(subscribers), batch_size):
            batch = subscribers[i:i + batch_size]
            
            try:
                if self.send_email(batch, subject, content, content_type):
                    sent_count += len(batch)
                else:
                    failed_count += len(batch)
                    errors.append(f"Failed to send batch {i//batch_size + 1}")
            except Exception as e:
                failed_count += len(batch)
                errors.append(f"Batch {i//batch_size + 1} error: {str(e)}")
        
        logger.info(f"Newsletter sent: {sent_count} successful, {failed_count} failed")
        
        return {
            'sent': sent_count,
            'failed': failed_count,
            'errors': errors
        }
    
    def send_welcome_email(self, email: str) -> bool:
        """Send welcome email to new subscriber."""
        subject = "Welcome to Open CVE Report Newsletter!"
        content = """
        <html>
        <body>
            <h2>Welcome to Open CVE Report!</h2>
            <p>Thank you for subscribing to our cybersecurity newsletter.</p>
            <p>You'll receive regular updates about:</p>
            <ul>
                <li>Latest CVE vulnerabilities</li>
                <li>Security insights and analysis</li>
                <li>Best practices for cybersecurity</li>
            </ul>
            <p>If you have any questions, feel free to contact us.</p>
            <p>Best regards,<br>The Open CVE Report Team</p>
            <hr>
            <small>If you didn't subscribe to this newsletter, please ignore this email.</small>
        </body>
        </html>
        """
        
        return self.send_email([email], subject, content, 'html')
    
    def send_email_confirmation(self, email: str, username: str, confirmation_url: str) -> bool:
        """Send email confirmation to new user."""
        subject = "Confirme seu email - Open CVE Report"
        content = f"""
        <html>
        <body>
            <h2>Bem-vindo ao Open CVE Report, {username}!</h2>
            <p>Obrigado por se registrar em nossa plataforma de monitoramento de vulnerabilidades.</p>
            <p>Para ativar sua conta, clique no link abaixo:</p>
            <p><a href="{confirmation_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Confirmar Email</a></p>
            <p>Ou copie e cole este link no seu navegador:</p>
            <p>{confirmation_url}</p>
            <p><strong>Este link expira em 24 horas.</strong></p>
            <p>Se você não se registrou em nossa plataforma, ignore este email.</p>
            <p>Atenciosamente,<br>Equipe Open CVE Report</p>
        </body>
        </html>
        """
        
        return self.send_email([email], subject, content, 'html')
    
    def send_password_reset(self, user_email: str, username: str, reset_link: str) -> bool:
        """
        Envia um e-mail de recuperação de senha.
        
        Args:
            user_email: E-mail do usuário
            username: Nome de usuário
            reset_link: Link de recuperação de senha (expira em 1 hora)
            
        Returns:
            bool: True se o e-mail foi enviado com sucesso, False caso contrário
        """
        subject = "Recuperação de Senha - Open Monitor"
        
        html_body = f"""
        <html>
        <body>
            <h2>Recuperação de Senha</h2>
            <p>Olá {username},</p>
            <p>Recebemos uma solicitação para redefinir a senha da sua conta no Open Monitor.</p>
            <p>Para redefinir sua senha, clique no link abaixo:</p>
            <p><a href="{reset_link}" style="background-color: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Redefinir Senha</a></p>
            <p><strong>Este link expira em 1 hora por motivos de segurança.</strong></p>
            <p>Se você não solicitou a recuperação de senha, ignore este e-mail. Sua senha permanecerá inalterada.</p>
            <br>
            <p>Atenciosamente,<br>Equipe Open Monitor</p>
        </body>
        </html>
        """
        
        text_body = f"""
        Recuperação de Senha - Open Monitor
        
        Olá {username},
        
        Recebemos uma solicitação para redefinir a senha da sua conta no Open Monitor.
        
        Para redefinir sua senha, acesse o link abaixo:
        {reset_link}
        
        Este link expira em 1 hora por motivos de segurança.
        
        Se você não solicitou a recuperação de senha, ignore este e-mail. Sua senha permanecerá inalterada.
        
        Atenciosamente,
        Equipe Open Monitor
        """
        
        return self.send_email(
            to_email=user_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body
        )
    
    def send_unsubscribe_confirmation(self, email: str) -> bool:
        """Send unsubscribe confirmation email."""
        subject = "Unsubscribed from Open CVE Report Newsletter"
        content = """
        <html>
        <body>
            <h2>Unsubscription Confirmed</h2>
            <p>You have been successfully unsubscribed from the Open CVE Report newsletter.</p>
            <p>We're sorry to see you go! If you change your mind, you can always subscribe again on our website.</p>
            <p>Thank you for your interest in cybersecurity.</p>
            <p>Best regards,<br>The Open CVE Report Team</p>
        </body>
        </html>
        """
        
        return self.send_email([email], subject, content, 'html')
