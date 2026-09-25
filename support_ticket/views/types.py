from django.db.models import Count
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.http import JsonResponse

from cis.utils import user_has_cis_role

from ..models.ticket import TicketType
from ..forms.types import TicketTypeForm
from .tickets import ce_table_context

from cis.menu import cis_menu, draw_menu


@user_passes_test(user_has_cis_role, login_url='/')
def delete(request, record_id):
    record = get_object_or_404(TicketType, pk=record_id)

    try:
        record.delete()
    except Exception as e:
        messages.add_message(
            request,
            messages.SUCCESS,
            'Unable to delete record. Make sure there are no tickets assigned to this type',
            'list-group-item-danger')
        return redirect("support_ticket:type", record.id)

    messages.add_message(
        request,
        messages.SUCCESS,
        'Successfully deleted record',
        'list-group-item-success')
    return redirect("support_ticket:types")


from django.views.decorators.clickjacking import xframe_options_exempt
@xframe_options_exempt
@user_passes_test(user_has_cis_role, login_url='/')
def detail(request, record_id):
    '''
    Record details page
    '''
    template = 'support_ticket/type/details.html'
    record = get_object_or_404(TicketType, pk=record_id)

    if request.method == 'POST':
        form = TicketTypeForm(request.POST, instance=record)

        if form.is_valid():
            record = form.save(commit=False)
            record.save()

            messages.add_message(
                request,
                messages.SUCCESS,
                'Successfully updated record',
                'list-group-item-success') 
            # reopen the Details tab the form lives on
            return redirect(reverse('support_ticket:type', args=[record_id]) + '#details')
    else:
        form = TicketTypeForm(instance=record)

    return render(
        request,
        template, {
            'form': form,
            'page_title': "Type",
            'labels': {
                'all_items': 'All Types'
            },
            'urls': {
                'add_new': 'support_ticket:add_new_type',
                'all_items': 'support_ticket:types'
            },
            'menu': draw_menu(cis_menu, 'support_reqs', 'types', 'ce'),
            'record': record,
            'table': ce_table_context('support_type_requests_table', ticket_type=record),
            # a POST that reaches render() failed validation: show the form's tab
            'active_tab': 'details' if request.method == 'POST' else 'requests',
        })

@user_passes_test(user_has_cis_role, login_url='/')
def add_new(request):
    '''
    Add new page
    '''
    base_template = 'cis/logged-base.html'
    template = 'support_ticket/type/add_new.html'
    ajax = request.GET.get('ajax', None)

    if request.method == 'POST':
        form = TicketTypeForm(request.POST)
        ajax = request.POST.get('ajax', None)

        if form.is_valid():
            record = form.save(commit=False)
            record.save()

            if ajax == '1':
                data = {
                    'status':'success',
                    'message':'Successfully added new record',
                    'new_record_id':record.id,
                    'new_record_name':record.name
                }
                return JsonResponse(data)

            messages.add_message(
                request,
                messages.SUCCESS,
                'Successfully added record',
                'list-group-item-success') 
            return redirect('support_ticket:type', record_id=record.id) #d
        
        if ajax == '1':
            data = {
                'status':'error',
                'message': ''.join([' '.join(x for x in l) for l in list(form.errors.values())])
            }
            return JsonResponse(data)
    else:
        form = TicketTypeForm()

    if ajax == '1':
        base_template = 'cis/ajax-base.html'

    return render(
        request,
        template, {
            'form': form,
            'page_title': "Add New",
            'labels': {
                'all_items': 'All Types'
            },
            'urls': {
                'all_items': 'support_ticket:types'
            },
            'ajax': ajax,
            'base_template': base_template,
            'menu': draw_menu(cis_menu, 'support_reqs', 'types', 'ce')
        })

@user_passes_test(user_has_cis_role, login_url='/')
def index(request):
    '''
    Request types list for staff. Types are few, so the whole list is rendered
    and searched/sorted client-side by DataTables.
    '''
    records = (TicketType.objects
               .select_related('assigned_to')
               .annotate(number_of_tickets=Count('ticket'))
               .order_by('applies_to', 'name'))
    return render(request, 'support_ticket/type/index.html', {
        'page_title': 'Request Types',
        'menu': draw_menu(cis_menu, 'support_reqs', 'types', 'ce'),
        'records': records,
        'applies_to_choices': TicketType.APPLIES_TO,
    })
