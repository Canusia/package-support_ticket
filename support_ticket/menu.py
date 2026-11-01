"""Support ticket sidebar items (cis.menu_registry).

ce `support_reqs` section (cis migration 0064) is the last ce item (150);
`support` is the last item of the student, instructor and highschool_admin
menus. On a cis without the registry nothing registers.
"""
try:
    from cis.menu_registry import menu
except ImportError:   # cis without the registry: the menu migrations still apply
    menu = None

if menu is not None:
    menu.section('ce', 'support_reqs', 'Support Requests', 'fas fa-fw fa-ticket-alt',
                 order=150)
    for _id, _label, _url, _order in [
        ('all_requests', 'All Requests', 'support_ticket:requests', 10),
        ('summary', 'Summary', 'support_ticket:summary', 20),
        ('types', 'Manage Types', 'support_ticket:types', 30),
    ]:
        menu.register('ce', _id, _label, url=_url, parent='support_reqs',
                      order=_order)
    for _role, _url, _order in [
        ('student', 'student_support_ticket:requests', 90),
        ('instructor', 'instructor_support_ticket:requests', 100),
        ('highschool_admin', 'hs_admin_support_ticket:requests', 140),
    ]:
        menu.register(_role, 'support', 'Support Requests', url=_url,
                      icon='fas fa-fw fa-question-circle', order=_order)
