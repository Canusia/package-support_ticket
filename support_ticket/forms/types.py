from django import forms
from django.forms import ValidationError
from django.utils.translation import gettext_lazy as _

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from cis.models.customuser import CustomUser
from cis.models.highschool import HighSchool
from cis.models.highschool_administrator import (
    HSAdministrator, HSAdministratorPosition
)
from cis.models.student import Student

from cis.forms.note import NoteForm
from support_ticket.constants import DEFAULT_STATUSES, ROLE_TO_APPLIES_TO
from support_ticket.forms.fields import MultipleFileField
from support_ticket.models.ticket import TicketType, Ticket
from support_ticket.settings.support_ticket_settings import support_ticket_settings as STS

class TicketTypeForm(forms.ModelForm):
    class Meta:
        model = TicketType
        fields = ['name', 'applies_to', 'assigned_to']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['assigned_to'].queryset = CustomUser.objects.filter(
            groups__name='ce'
        )
        
class SupportTicketAssignmentForm(forms.Form):
    assigned_to = forms.ModelChoiceField(
        label='Assign To',
        queryset=None
    )

    status = forms.ChoiceField(
        label='Status',
        choices=[]
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # get all CE users
        self.fields['assigned_to'].queryset = CustomUser.objects.filter(groups__name='ce')
        # source statuses from settings (falls back to DEFAULT_STATUSES)
        self.fields['status'].choices = [
            (s, s) for s in STS.get_statuses()
        ]

class SupportTicketForm(forms.ModelForm):
    files = MultipleFileField(required=False, label='Attachments')

    class Meta:
        model = Ticket
        fields = ['ticket_type', 'message']

        labels = {
            'ticket_type': _('Request Type'),
            'message': _("Request"),
        }

    def __init__(self, role='student', *args, **kwargs):
        super().__init__(*args, **kwargs)
        applies_to = ROLE_TO_APPLIES_TO.get(role, 'Students')
        self.fields['ticket_type'].queryset = TicketType.objects.filter(applies_to=applies_to)

    def clean(self):
        cleaned = super().clean()
        ticket_type = cleaned.get('ticket_type')
        files = cleaned.get('files') or []
        if ticket_type and ticket_type.requires_attachment and not files:
            self.add_error('files', 'This request type requires at least one attachment.')
        return cleaned


class SupportTicketNoteForm(NoteForm):
    files = MultipleFileField(required=False, label='Attachments')

class NewSupportTicketForm(forms.Form):
    """
    Form for CE staff to add new support requests.
    CE on-behalf submission is only supported for Students and School Administrators;
    Instructors submit their own tickets via the instructor portal.
    """
    send_to = forms.ChoiceField(
        choices=[
            (TicketType.STUDENTS, TicketType.STUDENTS),
            (TicketType.SCHOOL_ADMINS, TicketType.SCHOOL_ADMINS),
        ]
    )

    ticket_type = forms.ModelChoiceField(
        queryset=None
    )

    highschool = forms.ModelChoiceField(
        queryset=None
    )

    student = forms.ModelChoiceField(
        queryset=Student.objects.none()
    )

    administrator = forms.ModelChoiceField(
        queryset=HSAdministrator.objects.none()
    )

    message = forms.CharField(
        widget=forms.Textarea
    )

    files = MultipleFileField(required=False, label='Attachments')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = 'frm_ajax'
        self.helper.form_id = 'frm_add_support_request'
        self.helper.form_method = 'POST'

        self.helper.add_input(Submit('submit', 'Add Request'))

        initial_args = kwargs.get('initial')
        if initial_args:
            ticket_types = TicketType.objects.filter(
                applies_to=initial_args.get('send_to')
            )
            self.fields['ticket_type'].queryset = ticket_types

            self.fields['highschool'].queryset = HighSchool.objects.all()

            if initial_args['send_to'] == TicketType.STUDENTS:
                if initial_args.get('highschool', None):
                    self.fields['student'].queryset = Student.objects.filter(
                        highschool=initial_args['highschool']
                    )

                del self.fields['administrator']

            if initial_args['send_to'] == TicketType.SCHOOL_ADMINS:
                del self.fields['student']

                if initial_args.get('highschool', None):
                    self.fields['administrator'].queryset = HSAdministrator.objects.filter(
                        pk__in=HSAdministratorPosition.objects.filter(
                            highschool=initial_args.get('highschool')).distinct(
                                'hsadmin').values_list('hsadmin', flat=True)
                        )
