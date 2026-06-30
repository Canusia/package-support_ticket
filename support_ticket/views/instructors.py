from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render

from cis.utils import user_has_instructor_role
from cis.menu import draw_menu, INSTRUCTOR_MENU

from support_ticket.models.ticket import Ticket, TicketNote
from support_ticket.forms.types import SupportTicketForm, SupportTicketNoteForm
from support_ticket.services import create_ticket_with_files, add_note_with_files
from support_ticket.settings.support_ticket_settings import support_ticket_settings as STS


@user_passes_test(user_has_instructor_role, login_url='/')
def tickets(request):
    return render(request, 'support_ticket/instructor/index.html', {
        'page_title': 'Support Requests',
        'api_url': '/api/v1/support-ticket-instructor/?format=datatables',
        'urls': {'add_new': 'instructor_support_ticket:add_new',
                 'details': 'instructor_support_ticket:details'},
        'menu': draw_menu(INSTRUCTOR_MENU, 'support', ''),
        'can_start': STS.can_start('instructor'),
    })


@user_passes_test(user_has_instructor_role, login_url='/')
def add_new(request):
    """
    Create a new support ticket for the instructor. Gated by STS.can_start('instructor').
    """
    if not STS.can_start('instructor'):
        messages.add_message(
            request, messages.ERROR,
            'New support requests are currently disabled.',
            'list-group-item-danger')
        return redirect('instructor_support_ticket:requests')

    form = SupportTicketForm('instructor')
    if request.method == 'POST':
        form = SupportTicketForm('instructor', request.POST, request.FILES)
        if form.is_valid():
            create_ticket_with_files(
                request.user,
                form.cleaned_data['ticket_type'],
                form.cleaned_data['message'],
                form.cleaned_data['files'],
            )
            messages.add_message(
                request, messages.SUCCESS,
                'Successfully submitted request',
                'list-group-item-success')
            return redirect('instructor_support_ticket:requests')

    return render(request, 'support_ticket/instructor/add_new.html', {
        'base_template': 'cis/logged-base.html',
        'form': form,
        'page_title': 'Submit New Support Request',
        'labels': {'all_items': 'All Requests'},
        'urls': {'all_items': 'instructor_support_ticket:requests'},
        'menu': draw_menu(INSTRUCTOR_MENU, 'support', ''),
    })


@user_passes_test(user_has_instructor_role, login_url='/')
def details(request, record_id):
    """
    Show details for a ticket submitted by the current instructor (IDOR guard).
    """
    record = get_object_or_404(Ticket, pk=record_id, submitted_by=request.user)
    menu = draw_menu(INSTRUCTOR_MENU, 'support', '')

    if request.method == 'POST':
        form = SupportTicketNoteForm(request.POST, request.FILES)
        if form.is_valid():
            add_note_with_files(
                request.user, record,
                form.cleaned_data['note'], 'Public',
                form.cleaned_data['files'],
            )
            messages.add_message(
                request, messages.SUCCESS,
                'Successfully added note',
                'list-group-item-success')
            return redirect('instructor_support_ticket:details', record_id=record_id)
    else:
        form = SupportTicketNoteForm(initial={
            'model': 'ticketnote',
            'ajax': 0,
            'add_to': record_id,
            'id': -1,
        })

    # Submitters only see Public notes
    notes = TicketNote.objects.filter(
        support_ticket=record, note_type='Public').order_by('-createdon')

    return render(request, 'support_ticket/instructor/details.html', {
        'form': form,
        'page_title': 'Support Request',
        'record': record,
        'notes': notes,
        'labels': {'all_items': 'All Requests'},
        'urls': {'all_items': 'instructor_support_ticket:requests'},
        'menu': menu,
    })
