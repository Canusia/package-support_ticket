from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.template import Context, Template
from django.contrib.sites.models import Site

from mailer import send_mail

from .models.ticket import Ticket, TicketNote
from .models.attachment import TicketAttachment
from .settings.support_ticket_settings import (
    support_ticket_settings as STS, DEFAULT_ASSIGNMENT_SUBJECT, DEFAULT_ASSIGNMENT_EMAIL,
)


def _site_url():
    try:
        return f"https://{Site.objects.get_current().domain}"
    except Exception:
        return ''


def _resolve_recipients(intended):
    """Apply Debug mode: in Debug, redirect to default_to instead of real recipients."""
    cfg = STS.from_db()
    if cfg.get('is_active') == 'Debug':
        return [a.strip() for a in (cfg.get('default_to') or '').split(',') if a.strip()]
    return [a for a in intended if a]


def _send(subject, body, recipients):
    cfg = STS.from_db()
    if cfg.get('is_active', 'Yes') == 'No':
        return
    recipients = _resolve_recipients(recipients)
    if not recipients:
        return
    from_email = cfg.get('from_email') or None  # None → Django DEFAULT_FROM_EMAIL
    send_mail(subject, body, from_email, recipients, fail_silently=True)


def notify_assignee(ticket, assignee):
    """Email a newly assigned person, if the ticket's type has "Email assignee" checked."""
    if assignee is None or not ticket.ticket_type.email_assignee:
        return
    cfg = STS.from_db()
    submitter = ticket.submitted_by
    body = Template(cfg.get('assignment_email') or DEFAULT_ASSIGNMENT_EMAIL).render(Context({
        'first_name': assignee.first_name,
        'submitter_name': submitter.get_full_name() or submitter.email,
        'ticket_type': ticket.ticket_type.name,
        'message': ticket.message,
        'site_url': _site_url(),
    }))
    _send(cfg.get('assignment_subject') or DEFAULT_ASSIGNMENT_SUBJECT, body, [assignee.email])


@receiver(pre_save, sender=Ticket)
def ticket_pre_save(sender, instance, **kwargs):
    # Ticket uses a UUID PK with a uuid4 default, so ``instance.pk`` is already
    # populated on a brand-new unsaved row. Use ``_state.adding`` to reliably tell
    # a fresh insert (default status) from an update (capture old status).
    if not instance._state.adding:
        try:
            old = Ticket.objects.values('status', 'assigned_to_id').get(pk=instance.pk)
            instance._old_status = old['status']
            instance._old_assigned_to_id = old['assigned_to_id']
        except Ticket.DoesNotExist:
            instance._old_status = None
            instance._old_assigned_to_id = None
    else:
        instance._old_status = None
        instance._old_assigned_to_id = None
        if not instance.status:
            instance.status = STS.get_default_status()


@receiver(post_save, sender=Ticket)
def ticket_post_save(sender, instance, created, **kwargs):
    cfg = STS.from_db()
    if created:
        # copy default assignee from the type (without re-triggering email loops)
        if instance.ticket_type.assigned_to and not instance.assigned_to:
            Ticket.objects.filter(pk=instance.pk).update(
                assigned_to=instance.ticket_type.assigned_to)
        notify_assignee(instance, instance.assigned_to or instance.ticket_type.assigned_to)
        # email the type's notify list
        recipients = instance.ticket_type.notify_recipient_emails()
        subject = cfg.get('submission_subject', 'Support request received')
        body = Template(cfg.get('submission_email', '')).render(Context({
            'first_name': instance.submitted_by.first_name,
            'ticket_type': instance.ticket_type.name,
            'message': instance.message,
            'site_url': _site_url(),
        }))
        _send(subject, body, recipients)
        return

    if instance.assigned_to_id and \
            instance.assigned_to_id != getattr(instance, '_old_assigned_to_id', None):
        notify_assignee(instance, instance.assigned_to)

    # status change → email submitter with that status's template
    old = getattr(instance, '_old_status', None)
    if old is not None and old != instance.status:
        tpl = STS.status_template(instance.status)
        if tpl and tpl['notify']:
            body = Template(tpl['email']).render(Context({
                'first_name': instance.submitted_by.first_name,
                'status': instance.status,
                'ticket_type': instance.ticket_type.name,
                'site_url': _site_url(),
            }))
            _send(tpl['subject'] or 'Your support request was updated',
                  body, [instance.submitted_by.email])


@receiver(post_save, sender=TicketNote)
def ticketnote_post_save(sender, instance, created, **kwargs):
    if not created:
        return
    cfg = STS.from_db()
    ticket = instance.support_ticket
    if ticket is None:
        return
    # email the OTHER party
    to = []
    if instance.createdby_id == ticket.assigned_to_id:
        to = [ticket.submitted_by.email]
    elif instance.createdby_id == ticket.submitted_by_id:
        to = [ticket.assigned_to.email] if ticket.assigned_to_id else \
             [a.strip() for a in (cfg.get('default_to') or '').split(',') if a.strip()]
    else:
        to = [ticket.submitted_by.email]
        if ticket.assigned_to_id:
            to.append(ticket.assigned_to.email)
        else:
            to += [a.strip() for a in (cfg.get('default_to') or '').split(',') if a.strip()]
    # internal notes never notify the submitter
    if instance.note_type == 'Internal':
        to = [ticket.assigned_to.email] if ticket.assigned_to_id else []
    subject = cfg.get('note_subject', 'Update added to support request')
    body = Template(cfg.get('note_email', '{{update}}')).render(Context({
        'update': instance.note, 'site_url': _site_url(),
    }))
    _send(subject, body, to)


@receiver(post_delete, sender=TicketAttachment)
def attachment_post_delete(sender, instance, **kwargs):
    if instance.media:
        instance.media.delete(save=False)
