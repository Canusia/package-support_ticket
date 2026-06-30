from django.contrib import admin
from support_ticket.models.ticket import TicketType, Ticket, TicketNote
from support_ticket.models.attachment import TicketAttachment

admin.site.register([TicketType, Ticket, TicketNote, TicketAttachment])
