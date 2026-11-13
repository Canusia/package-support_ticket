"""Heading and page text for the student, instructor and HS admin support pages (#8).

Staff can rename the ``support`` menu item (Settings → Menu Layout) and save
header text for it in the role's portal settings, under ``support_blurb``
(each portal's settings form keys its fields ``<menu item name>_blurb``).
"""
import importlib
import logging

log = logging.getLogger(__name__)

MENU_ITEM = 'support'
STOCK_LABEL = 'Support Requests'   # the label menu.py registers

# role → the cis portal setting that holds its page text.
PORTAL_SETTINGS = {
    'highschool_admin': 'cis.settings.highschool_admin_portal.highschool_admin_portal',
    'instructor': 'cis.settings.instructor_portal.instructor_portal',
    'student': 'cis.settings.student_portal.student_portal',
}


def renamed_label(role):
    """The label staff gave the role's support menu item, or None if unchanged.

    None also when the item is not in the menu, has no label, or the menu
    cannot be read, so callers keep their built-in text.
    """
    try:
        from cis.menu import get_role_menu
        # A renamed item staff hid is still reachable by URL; keep its label.
        items = get_role_menu(role, visible_only=False)
    except Exception:
        log.exception('support_ticket: could not read the %s menu', role)
        return None
    # Staff can move an item into a group, so search the groups too.
    stack = list(items or ())
    while stack:
        item = stack.pop(0)
        if not isinstance(item, dict):
            continue
        if item.get('name') == MENU_ITEM:
            label = item.get('label')
            if isinstance(label, str) and label.strip() and label.strip() != STOCK_LABEL:
                return label.strip()
            return None
        stack.extend(item.get('sub_menu') or ())
    return None


def page_heading(role, default=STOCK_LABEL):
    """The list page heading: the renamed menu label, else ``default``."""
    return renamed_label(role) or default


def page_blurb(role):
    """The ``support_blurb`` saved in the role's portal settings, or ''."""
    path = PORTAL_SETTINGS.get(role)
    if not path:
        return ''
    module_path, cls_name = path.rsplit('.', 1)
    try:
        stored = getattr(importlib.import_module(module_path), cls_name).from_db()
    except Exception:
        log.exception('support_ticket: could not read %s', path)
        return ''
    if not isinstance(stored, dict):
        return ''
    value = stored.get(f'{MENU_ITEM}_blurb')
    if not isinstance(value, str) or not value.strip():
        return ''
    # The settings forms require every blurb, so untouched ones hold placeholders.
    if value.strip() == 'Change me' or value.strip().startswith('Change this in Settings'):
        return ''
    return value


def page_titles(role):
    """``(list, add, detail)`` headings for the role's support pages."""
    label = renamed_label(role)
    if not label:
        return STOCK_LABEL, 'Submit New Support Request', 'Support Request'
    return label, f'{label} — New', label
