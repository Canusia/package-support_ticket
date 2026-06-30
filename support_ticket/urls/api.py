from rest_framework import routers

from support_ticket.api import (
    CETicketViewSet, StudentTicketViewSet, InstructorTicketViewSet, HSAdminTicketViewSet,
    TicketSummaryViewSet,
)

router = routers.DefaultRouter()
router.register('support-ticket-ce', CETicketViewSet, basename='support-ticket-ce')
router.register('support-ticket-student', StudentTicketViewSet, basename='support-ticket-student')
router.register('support-ticket-instructor', InstructorTicketViewSet,
                basename='support-ticket-instructor')
router.register('support-ticket-hsadmin', HSAdminTicketViewSet, basename='support-ticket-hsadmin')
router.register('support-ticket-summary', TicketSummaryViewSet, basename='support-ticket-summary')

urlpatterns = router.urls
