from django.db.models import Q, Count
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse

from cis.utils import user_has_cis_role

from ..models.ticket import TicketType
from ..forms.types import TicketTypeForm

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
            return redirect('support_ticket:type', record_id=record_id)
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
            'menu': draw_menu(cis_menu, 'support_ticket', 'types'),
            'record': record
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
            'menu': draw_menu(cis_menu, 'support_reqs', 'types')
        })

@user_passes_test(user_has_cis_role, login_url='/')
def index(request):
    '''
     search and index page for staff
    '''
    menu = draw_menu(cis_menu, 'support_reqs', 'manage_types')

    template = 'support_ticket/type/index.html'
    query = request.GET.get('q', '')
    page = request.GET.get('page', 1)
    order_by = request.GET.get('order_by', 'name').lower()
    order = request.GET.get('order', 'asc')

    valid_order_by_fields = [
        'name', 'assigned_to',
        'applies_to'
    ]
    if order_by not in valid_order_by_fields:
        order_by = 'name'

    valid_order = [
        'asc', 'desc'
    ]
    if order not in valid_order:
        order = 'asc'

    if not query:
        record_list = TicketType.objects.all().order_by(
            order_by if order == 'asc' else f"-{order_by}")
    else:
        record_list = TicketType.objects.filter(
            Q(name__contains=query)).order_by(
                order_by if order == 'asc' else f"-{order_by}")
    
    record_list = record_list.annotate(number_of_tickets=Count('ticket'))

    paginator = Paginator(record_list, 30)
    try:
        records = paginator.page(page)
    except PageNotAnInteger:
        records = paginator.page(1)
    except EmptyPage:
        records = paginator.page(paginator.num_pages)

    return render(
        request,
        template, {
            'page_title': 'Request Types',
            'urls': {
                'add_new': 'support_ticket:add_new_type',
                'details': 'support_ticket:type'
            },
            'menu': menu,
            'records':records,
            'q': query,
            'order_by': order_by,
            'order': order})
