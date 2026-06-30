from django.contrib import admin
from .models.ticket import TicketType, Ticket, TicketNote
from .models.attachment import TicketAttachment

admin.site.register([TicketType, Ticket, TicketNote, TicketAttachment])
