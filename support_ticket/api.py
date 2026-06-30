from django.db.models import Count, F
from rest_framework import mixins, viewsets

from cis.utils import CIS_user_only
from .models.ticket import Ticket
from .serializers import TicketSerializer
from .permissions import IsStudent, IsInstructor, IsHSAdmin


def _base_qs():
    return Ticket.objects.select_related(
        'ticket_type', 'submitted_by', 'assigned_to'
    ).annotate(attachment_count=Count('attachments'))


class _BaseTicketViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TicketSerializer
    portal_detail_urlname = None

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['portal_detail_urlname'] = self.portal_detail_urlname
        return ctx


class CETicketViewSet(_BaseTicketViewSet):
    permission_classes = [CIS_user_only]
    portal_detail_urlname = 'support_ticket:request'

    def get_queryset(self):
        qs = _base_qs().all()
        status = self.request.GET.get('status')
        assigned_to = self.request.GET.get('assigned_to')
        if status:
            qs = qs.filter(status__iexact=status)
        if assigned_to == 'unassigned':
            qs = qs.filter(assigned_to__isnull=True)
        elif assigned_to:
            try:
                assigned_to_id = int(assigned_to)
            except (ValueError, AttributeError, TypeError):
                return qs.none()
            qs = qs.filter(assigned_to_id=assigned_to_id)
        return qs.order_by('-submitted_on')


class StudentTicketViewSet(_BaseTicketViewSet):
    permission_classes = [IsStudent]
    portal_detail_urlname = 'student_support_ticket:details'

    def get_queryset(self):
        return _base_qs().filter(
            submitted_by=self.request.user).order_by('-submitted_on')


class InstructorTicketViewSet(_BaseTicketViewSet):
    permission_classes = [IsInstructor]
    portal_detail_urlname = 'instructor_support_ticket:details'

    def get_queryset(self):
        return _base_qs().filter(
            submitted_by=self.request.user).order_by('-submitted_on')


class HSAdminTicketViewSet(_BaseTicketViewSet):
    permission_classes = [IsHSAdmin]
    portal_detail_urlname = 'hs_admin_support_ticket:details'

    def get_queryset(self):
        from .services import tickets_for_hsadmin
        scoped = tickets_for_hsadmin(self.request.user)
        return _base_qs().filter(
            pk__in=scoped.values_list('pk', flat=True)).order_by('-submitted_on')


class TicketSummaryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [CIS_user_only]
    serializer_class = None  # resolved lazily to avoid forward-reference

    GROUP_FIELDS = {
        'status': 'status',
        'type': 'ticket_type__name',
        'assignee': 'assigned_to__last_name',
    }

    def get_serializer_class(self):
        from .serializers import TicketSummarySerializer
        return TicketSummarySerializer

    def get_queryset(self):
        group_by = self.request.GET.get('group_by', 'status')
        field = self.GROUP_FIELDS.get(group_by, 'status')
        return (Ticket.objects
                .annotate(group=F(field))
                .values('group')
                .annotate(count=Count('id'))
                .order_by('group'))
