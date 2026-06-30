from django.db import transaction

from support_ticket.models.ticket import Ticket, TicketNote
from support_ticket.models.attachment import TicketAttachment


@transaction.atomic
def create_ticket_with_files(user, ticket_type, message, files):
    ticket = Ticket.objects.create(
        ticket_type=ticket_type, submitted_by=user, message=message)
    for f in files or []:
        TicketAttachment.objects.create(ticket=ticket, media=f, uploaded_by=user)
    return ticket


@transaction.atomic
def add_note_with_files(user, ticket, note_text, note_type, files):
    note = TicketNote.objects.create(
        support_ticket=ticket, createdby=user, note=note_text, note_type=note_type)
    for f in files or []:
        TicketAttachment.objects.create(note=note, media=f, uploaded_by=user)
    return note


def tickets_for_hsadmin(user):
    """
    Return a Ticket queryset scoped to tickets submitted by students or HS admins
    who belong to one of the given user's high schools. Single source of truth for
    HS-admin scoping — used by both HSAdminTicketViewSet and the hs-admin detail view.
    """
    from cis.models.student import Student
    from cis.models.highschool_administrator import (
        HSAdministrator, HSAdministratorPosition)

    highschool_ids = user.get_highschools_for_admin()
    student_user_ids = Student.objects.filter(
        highschool_id__in=highschool_ids).values_list('user_id', flat=True)
    admin_user_ids = HSAdministrator.objects.filter(
        pk__in=HSAdministratorPosition.objects.filter(
            highschool_id__in=highschool_ids).values_list('hsadmin', flat=True)
    ).values_list('user_id', flat=True)
    allowed = list(student_user_ids) + list(admin_user_ids)
    return Ticket.objects.filter(submitted_by_id__in=allowed)
