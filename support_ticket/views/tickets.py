from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test

from django.template.context_processors import csrf

from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse

from cis.utils import user_has_cis_role
from cis.models.customuser import CustomUser
from ..settings.support_ticket_settings import support_ticket_settings as STS

from crispy_forms.utils import render_crispy_form

from ..models.ticket import Ticket, TicketNote, TicketType
from ..forms.types import (
    SupportTicketForm, SupportTicketAssignmentForm,
    SupportTicketNoteForm, NewSupportTicketForm
)
from ..services import create_ticket_with_files, add_note_with_files

from cis.menu import cis_menu, draw_menu

from ..actions import ticket_actions


@user_passes_test(user_has_cis_role, login_url='/')
def delete(request, record_id):
    record = get_object_or_404(Ticket, pk=record_id)

    try:
        notes = TicketNote.objects.filter(support_ticket=record).delete()

        record.delete()
    except Exception as e:
        messages.add_message(
            request,
            messages.SUCCESS,
            'Unable to delete record. Make sure there are no tickets assigned to this type',
            'list-group-item-danger')
        print(e)
        return redirect("support_ticket:request", record.id)

    messages.add_message(
        request,
        messages.SUCCESS,
        'Successfully deleted record',
        'list-group-item-success')
    return redirect("support_ticket:requests")

from django.views.decorators.clickjacking import xframe_options_exempt
@xframe_options_exempt
@user_passes_test(user_has_cis_role, login_url='/')
def detail(request, record_id):
    '''
    Record details page
    '''
    template = 'support_ticket/ticket/details.html'
    record = get_object_or_404(Ticket, pk=record_id)

    # Always initialise both forms; rebind whichever one was submitted on POST.
    assignment_form = SupportTicketAssignmentForm(initial={
        'assigned_to': record.assigned_to,
        'status': record.status,
    })
    noteform = SupportTicketNoteForm(initial={
        'model': 'ticketnote',
        'ajax': 0,
        'add_to': record_id,
        'id': -1,
    })

    if request.method == 'POST':
        if request.POST.get('add_note') == 'Add Note':
            noteform = SupportTicketNoteForm(request.POST, request.FILES)

            if noteform.is_valid():
                add_note_with_files(
                    request.user,
                    record,
                    noteform.cleaned_data['note'],
                    'Public',
                    noteform.cleaned_data.get('files') or [],
                )
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'Successfully added note',
                    'list-group-item-success')
                return redirect('support_ticket:request', record_id=record_id)
        else:
            assignment_form = SupportTicketAssignmentForm(request.POST)

            if assignment_form.is_valid():
                record.assigned_to = assignment_form.cleaned_data['assigned_to']
                record.status = assignment_form.cleaned_data['status']
                record.save()

                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'Successfully updated record',
                    'list-group-item-success')
                return redirect('support_ticket:request', record_id=record_id)

    # CE staff see all notes (Public + Internal); submitters' portals filter to Public only.
    notes = TicketNote.objects.filter(
        support_ticket=record
    ).order_by('-createdon')
    return render(
        request,
        template, {
            'form': assignment_form,
            'noteform': noteform,
            'page_title': "Support Request",
            'labels': {
                'all_items': 'All Requests'
            },
            'urls': {
                'all_items': 'support_ticket:requests'
            },
            'menu': draw_menu(cis_menu, 'support_reqs', 'requests'),
            'notes': notes,
            'record': record
        })

@user_passes_test(user_has_cis_role, login_url='/')
def index(request):
    '''
    Index page for CE staff — table data served via scoped DRF endpoint.
    '''
    return render(request, 'support_ticket/ticket/index.html', {
        'page_title': 'Support Requests',
        'api_url': '/api/v1/support-ticket-ce/?format=datatables',
        'urls': {
            'details': 'support_ticket:request',
        },
        'menu': draw_menu(cis_menu, 'support_reqs', 'requests'),
        'add_new_request_form': NewSupportTicketForm(initial={'send_to': 'Students'}),
        'can_start': True,
        'statuses': STS.get_statuses(),
        'ce_users': CustomUser.objects.filter(groups__name='ce', is_active=True).order_by('last_name', 'first_name'),
    })


@user_passes_test(user_has_cis_role, login_url='/')
def support_ticket_bulk_actions(request):
    """Dispatch point for CE bulk actions on support tickets."""
    return ticket_actions.dispatch(request, request.POST.get('action'))


@user_passes_test(user_has_cis_role, login_url='/')
def summary(request):
    return render(request, 'support_ticket/ticket/summary.html', {
        'page_title': 'Support Requests — Summary',
        'summary_url_base': '/api/v1/support-ticket-summary/',
        'menu': draw_menu(cis_menu, 'support_reqs', 'summary'),
    })


@user_passes_test(user_has_cis_role, login_url='/')
def add_new_support_request(request):
    """
    Add support request for CE Staff
    """
    ajax = request.GET.get('ajax', None)
    base_template = 'cis/logged-base.html' if not ajax else 'cis/ajax-base.html'
    template = 'cis/students/edit_registration.html'

    if request.method == 'POST':
        """
        Refresh add new support request form
        """
        if request.POST.get('action') == 'refresh_addSupportRequest':
            form = NewSupportTicketForm(initial=request.POST)

            ctx = {}
            ctx.update(csrf(request))
            form_html = render_crispy_form(form, context=ctx)

            data = {
                'status':'status',
                'form_html':form_html,
            }
            return JsonResponse(data)

        """
        Add New Support Request
        """
        if request.POST.get('action') == 'add_new_support_request':
            form = NewSupportTicketForm(initial=request.POST, data=request.POST,
                                        files=request.FILES)

            if form.is_valid():
                if form.cleaned_data['send_to'] == TicketType.STUDENTS:
                    target_user = form.cleaned_data['student'].user
                elif form.cleaned_data['send_to'] == TicketType.SCHOOL_ADMINS:
                    target_user = form.cleaned_data['administrator'].user
                else:
                    form.add_error(
                        'send_to',
                        'CE on-behalf submission is only supported for Students '
                        'and School Administrators.'
                    )
                    ctx = {}
                    ctx.update(csrf(request))
                    form_html = render_crispy_form(form, context=ctx)
                    return JsonResponse({
                        'status': 'error',
                        'form_html': form_html,
                        'message': 'Invalid recipient type.',
                    })

                ticket = create_ticket_with_files(
                    target_user,
                    form.cleaned_data['ticket_type'],
                    form.cleaned_data['message'],
                    form.cleaned_data.get('files') or [],
                )
                # Set assignee and status via .update() to avoid re-firing the
                # post_save create signal a second time.
                Ticket.objects.filter(pk=ticket.pk).update(
                    assigned_to=request.user, status='Pending')

                data = {
                    'status': 'success',
                    'message': 'Successfully processed your request',
                }
                return JsonResponse(data)

            ctx = {}
            ctx.update(csrf(request))
            form_html = render_crispy_form(form, context=ctx)

            data = {
                'status':'error',
                'form_html':form_html,
                'message':'There was an error while completing your request. Please try again'
            }
            return JsonResponse(data)
