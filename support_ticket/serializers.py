from django.urls import NoReverseMatch, reverse
from rest_framework import serializers

from .models.ticket import Ticket


class TicketSerializer(serializers.ModelSerializer):
    ticket_type_name = serializers.CharField(source='ticket_type.name', read_only=True)
    submitter_name = serializers.SerializerMethodField()
    submitter_email = serializers.CharField(source='submitted_by.email', read_only=True)
    assignee_name = serializers.SerializerMethodField()
    attachment_count = serializers.IntegerField(read_only=True)
    submitted_on = serializers.DateTimeField(format='%m/%d/%Y', read_only=True)
    last_updated_on = serializers.DateTimeField(format='%m/%d/%Y', read_only=True)
    detail_url = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            'id', 'ticket_type_name', 'submitter_name', 'submitter_email',
            'assignee_name', 'status', 'submitted_on', 'last_updated_on',
            'attachment_count', 'detail_url',
        ]
        datatables_always_serialize = ['id', 'detail_url']

    def get_submitter_name(self, obj):
        u = obj.submitted_by
        return f'{u.last_name}, {u.first_name}'.strip(', ')

    def get_assignee_name(self, obj):
        if not obj.assigned_to_id:
            return ''
        u = obj.assigned_to
        return f'{u.last_name}, {u.first_name}'.strip(', ')

    def get_detail_url(self, obj):
        urlname = self.context.get('portal_detail_urlname')
        if not urlname:
            return ''
        try:
            return reverse(urlname, args=[obj.id])
        except NoReverseMatch:
            # Portal namespace not registered (e.g. instructor portal not yet wired).
            return ''


class TicketSummarySerializer(serializers.Serializer):
    group = serializers.SerializerMethodField()
    count = serializers.IntegerField(read_only=True)

    def get_group(self, obj):
        return obj.get('group') or 'Unassigned'
