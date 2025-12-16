from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask import current_app
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from app.services.newsletter_service import NewsletterService
from app.services.email_service import EmailService
from app.forms.newsletter_forms import NewsletterAdminForm
from app.extensions import db
from flask_login import login_required, current_user

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
newsletter_admin_bp = Blueprint(
    'newsletter_admin',
    __name__,
    url_prefix='/admin/newsletter'
)


@newsletter_admin_bp.route('/', methods=['GET'])
@login_required
def admin_dashboard() -> str:
    """Newsletter admin dashboard with statistics and subscriber management."""
    logger.info("Accessing newsletter admin dashboard")
    
    try:
        newsletter_service = NewsletterService(db.session)
        
        # Get statistics
        all_subscribers = newsletter_service.get_all_subscribers()
        active_subscribers = [s for s in all_subscribers if s.is_active]
        inactive_subscribers = [s for s in all_subscribers if not s.is_active]
        
        # Recent subscriptions (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_subscribers = [
            s for s in all_subscribers 
            if s.subscribed_at >= thirty_days_ago
        ]
        
        stats = {
            'total_subscribers': len(all_subscribers),
            'active_subscribers': len(active_subscribers),
            'inactive_subscribers': len(inactive_subscribers),
            'recent_subscribers': len(recent_subscribers),
            'growth_rate': len(recent_subscribers) / max(len(all_subscribers) - len(recent_subscribers), 1) * 100
        }
        
        return render_template(
            'newsletter/admin/dashboard.html',
            stats=stats,
            recent_subscribers=recent_subscribers[:10]  # Show last 10
        )
        
    except Exception as e:
        logger.error(f"Error loading newsletter admin dashboard: {e}")
        flash(f"Erro ao carregar dashboard: {str(e)}", 'danger')
        return render_template('newsletter/admin/dashboard.html', stats={}, recent_subscribers=[])


@newsletter_admin_bp.route('/subscribers', methods=['GET'])
@login_required
def list_subscribers() -> str:
    """List all newsletter subscribers with pagination and filtering."""
    logger.info("Accessing newsletter subscribers list")
    
    try:
        newsletter_service = NewsletterService(db.session)
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status_filter = request.args.get('status', 'all')  # all, active, inactive
        search_query = request.args.get('search', '').strip()
        
        # Get all subscribers
        all_subscribers = newsletter_service.get_all_subscribers()
        
        # Apply filters
        filtered_subscribers = all_subscribers
        
        if status_filter == 'active':
            filtered_subscribers = [s for s in filtered_subscribers if s.is_active]
        elif status_filter == 'inactive':
            filtered_subscribers = [s for s in filtered_subscribers if not s.is_active]
        
        if search_query:
            filtered_subscribers = [
                s for s in filtered_subscribers 
                if search_query.lower() in s.email.lower()
            ]
        
        # Simple pagination
        total = len(filtered_subscribers)
        start = (page - 1) * per_page
        end = start + per_page
        subscribers = filtered_subscribers[start:end]
        
        pagination_info = {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page,
            'has_prev': page > 1,
            'has_next': end < total,
            'prev_num': page - 1 if page > 1 else None,
            'next_num': page + 1 if end < total else None
        }
        
        return render_template(
            'newsletter/admin/subscribers.html',
            subscribers=subscribers,
            pagination=pagination_info,
            status_filter=status_filter,
            search_query=search_query
        )
        
    except Exception as e:
        logger.error(f"Error loading newsletter subscribers: {e}")
        flash(f"Erro ao carregar assinantes: {str(e)}", 'danger')
        return render_template('newsletter/admin/subscribers.html', subscribers=[], pagination={})


@newsletter_admin_bp.route('/send', methods=['GET', 'POST'])
@login_required
def send_newsletter() -> str:
    """Send newsletter to all active subscribers."""
    logger.info(f"Accessing send newsletter page with method: {request.method}")
    
    form = NewsletterAdminForm()
    
    if request.method == 'POST' and form.validate_on_submit():
        try:
            newsletter_service = NewsletterService(db.session)
            email_service = EmailService()
            
            subject = form.subject.data.strip()
            content = form.content.data.strip()
            send_to_active_only = form.send_to_active_only.data
            
            # Get subscribers
            all_subscribers = newsletter_service.get_all_subscribers()
            target_subscribers = [
                s for s in all_subscribers 
                if not send_to_active_only or s.is_active
            ]
            
            if not target_subscribers:
                flash("Nenhum assinante encontrado para envio.", 'warning')
                return render_template('newsletter/admin/send.html', form=form)
            
            # Send newsletter to all target subscribers
            sent_count = 0
            failed_count = 0
            
            for subscriber in target_subscribers:
                try:
                    success = email_service.send_email(
                        [subscriber.email],
                        subject,
                        content,
                        'html'
                    )
                    if success:
                        sent_count += 1
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    logger.error(f"Failed to send newsletter to {subscriber.email}: {e}")
                    failed_count += 1
            
            # Show results
            if sent_count > 0:
                flash(f"Newsletter enviada com sucesso para {sent_count} assinantes!", 'success')
            
            if failed_count > 0:
                flash(f"Falha ao enviar para {failed_count} assinantes.", 'warning')
            
            logger.info(f"Newsletter sent: {sent_count} successful, {failed_count} failed")
            return redirect(url_for('newsletter_admin.admin_dashboard'))
            
        except Exception as e:
            logger.error(f"Error sending newsletter: {e}")
            flash(f"Erro ao enviar newsletter: {str(e)}", 'danger')
    
    elif request.method == 'POST':
        # Form validation failed
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Erro no campo {getattr(form, field).label.text}: {error}", 'danger')
    
    return render_template('newsletter/admin/send.html', form=form)


@newsletter_admin_bp.route('/subscriber/<int:subscriber_id>/toggle', methods=['POST'])
@login_required
def toggle_subscriber_status(subscriber_id: int) -> str:
    """Toggle subscriber active/inactive status."""
    logger.info(f"Toggling subscriber status for ID: {subscriber_id}")
    
    try:
        newsletter_service = NewsletterService(db.session)
        
        # Get subscriber by ID (you'll need to implement this method)
        # For now, we'll use email-based lookup as a workaround
        all_subscribers = newsletter_service.get_all_subscribers()
        subscriber = None
        
        # Find subscriber by index (temporary solution)
        if 0 <= subscriber_id < len(all_subscribers):
            subscriber = all_subscribers[subscriber_id]
        
        if not subscriber:
            flash("Assinante não encontrado.", 'danger')
            return redirect(url_for('newsletter_admin.list_subscribers'))
        
        # Toggle status
        if subscriber.is_active:
            newsletter_service.unsubscribe(subscriber.email)
            flash(f"Assinante {subscriber.email} foi desativado.", 'success')
        else:
            newsletter_service.resubscribe(subscriber.email)
            flash(f"Assinante {subscriber.email} foi reativado.", 'success')
        
        logger.info(f"Subscriber {subscriber.email} status toggled")
        
    except Exception as e:
        logger.error(f"Error toggling subscriber status: {e}")
        flash(f"Erro ao alterar status do assinante: {str(e)}", 'danger')
    
    return redirect(url_for('newsletter_admin.list_subscribers'))


@newsletter_admin_bp.route('/export', methods=['GET'])
@login_required
def export_subscribers() -> str:
    """Export subscribers list as CSV."""
    logger.info("Exporting newsletter subscribers")
    
    try:
        from flask import make_response
        import csv
        from io import StringIO
        
        newsletter_service = NewsletterService(db.session)
        subscribers = newsletter_service.get_all_subscribers()
        
        # Create CSV content
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Email', 'Status', 'Data de Inscrição', 'Data de Cancelamento', 'Origem'])
        
        # Write data
        for subscriber in subscribers:
            writer.writerow([
                subscriber.email,
                'Ativo' if subscriber.is_active else 'Inativo',
                subscriber.subscribed_at.strftime('%Y-%m-%d %H:%M:%S') if subscriber.subscribed_at else '',
                subscriber.unsubscribed_at.strftime('%Y-%m-%d %H:%M:%S') if subscriber.unsubscribed_at else '',
                subscriber.source or 'Website'
            ])
        
        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=newsletter_subscribers_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        logger.info(f"Exported {len(subscribers)} subscribers")
        return response
        
    except Exception as e:
        logger.error(f"Error exporting subscribers: {e}")
        flash(f"Erro ao exportar assinantes: {str(e)}", 'danger')
        return redirect(url_for('newsletter_admin.list_subscribers'))


@newsletter_admin_bp.route('/api/stats', methods=['GET'])
@login_required
def api_stats() -> str:
    """API endpoint for newsletter statistics."""
    try:
        newsletter_service = NewsletterService(db.session)
        all_subscribers = newsletter_service.get_all_subscribers()
        
        # Calculate stats by month for the last 12 months
        monthly_stats = {}
        for i in range(12):
            month_start = datetime.utcnow().replace(day=1) - timedelta(days=30*i)
            month_end = month_start + timedelta(days=31)
            month_key = month_start.strftime('%Y-%m')
            
            month_subscribers = [
                s for s in all_subscribers
                if s.subscribed_at and month_start <= s.subscribed_at < month_end
            ]
            
            monthly_stats[month_key] = len(month_subscribers)
        
        stats = {
            'total_subscribers': len(all_subscribers),
            'active_subscribers': len([s for s in all_subscribers if s.is_active]),
            'monthly_growth': monthly_stats
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting newsletter stats: {e}")
        return jsonify({'error': str(e)}), 500
