"""
CE bulk actions for the support-ticket app.

Instantiates a local ActionRegistry and registers two two-phase bulk handlers:
  - bulk_update_status   : set all selected tickets to a chosen status
  - bulk_update_assigned_to : reassign all selected tickets to a CE user

Both handlers follow the change_application_status two-phase pattern:
  Phase 1 (no action_confirmed): render a form inside the shared
      cis/students/bulk_action.html modal and return {outcome:'modal'}.
  Phase 2 (action_confirmed=1): validate form, call form.save(request),
      return {outcome:'call', fn:'refreshTable'} on success or a 400 with
      form errors on failure.

See forms/bulk.py for the design note on why update() is used (no signal /
no per-ticket emails on bulk — intentional, mirrors students pattern).
"""
from collections import OrderedDict

from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse

from myce.component_registry import ActionRegistry

ticket_actions = ActionRegistry(OrderedDict({
    'bulk_ticket': {'actions': OrderedDict()},
}))


@ticket_actions.action(
    'bulk_ticket',
    label='Update Status',
    scope=['bulk'],
    slug='bulk_update_status',
    method='form',
    icon='fas fa-exchange-alt',
    btn_class='btn-warning',
)
def bulk_update_status(request):
    from support_ticket.forms.bulk import BulkTicketStatusForm
    ids = request.POST.getlist('ids[]')
    template = 'cis/students/bulk_action.html'

    if request.POST.get('action_confirmed'):
        form = BulkTicketStatusForm(ticket_ids=ids, data=request.POST)
        if form.is_valid():
            updated = form.save(request)
            return JsonResponse({
                'outcome': 'call',
                'fn': 'refreshTable',
                'args': {
                    'title': 'Done',
                    'message': f'Updated status for {updated} ticket(s).',
                    'status': 'success',
                },
            })
        return JsonResponse({
            'message': 'Please correct the errors and try again.',
            'errors': form.errors.as_json(),
        }, status=400)

    form = BulkTicketStatusForm(ticket_ids=ids)
    html = render_to_string(template, {
        'title': 'Update Ticket Status',
        'form': form,
        'form_action': reverse('support_ticket:bulk_actions'),
        'action_slug': 'bulk_update_status',
        'ids': ids,
    }, request=request)
    return JsonResponse({'outcome': 'modal', 'html': html})


@ticket_actions.action(
    'bulk_ticket',
    label='Update Assigned To',
    scope=['bulk'],
    slug='bulk_update_assigned_to',
    method='form',
    icon='fas fa-user-edit',
    btn_class='btn-info',
)
def bulk_update_assigned_to(request):
    from support_ticket.forms.bulk import BulkTicketAssignForm
    ids = request.POST.getlist('ids[]')
    template = 'cis/students/bulk_action.html'

    if request.POST.get('action_confirmed'):
        form = BulkTicketAssignForm(ticket_ids=ids, data=request.POST)
        if form.is_valid():
            updated = form.save(request)
            return JsonResponse({
                'outcome': 'call',
                'fn': 'refreshTable',
                'args': {
                    'title': 'Done',
                    'message': f'Reassigned {updated} ticket(s).',
                    'status': 'success',
                },
            })
        return JsonResponse({
            'message': 'Please correct the errors and try again.',
            'errors': form.errors.as_json(),
        }, status=400)

    form = BulkTicketAssignForm(ticket_ids=ids)
    html = render_to_string(template, {
        'title': 'Update Assigned To',
        'form': form,
        'form_action': reverse('support_ticket:bulk_actions'),
        'action_slug': 'bulk_update_assigned_to',
        'ids': ids,
    }, request=request)
    return JsonResponse({'outcome': 'modal', 'html': html})
