"""Heading and page text for the student, instructor and HS admin support pages (#8).

Staff can rename the ``support`` menu item (Settings → Menu Layout) and save
header text for it in the role's portal settings, under ``support_blurb``
(each portal's settings form keys its fields ``<menu item name>_blurb``).

cis v0.2.10a has one shared copy of both lookups (``cis.portal_text.page_heading``
/ ``page_blurb``); this module uses it when present and keeps its own for older cis.
"""
import importlib
import logging

log = logging.getLogger(__name__)

MENU_ITEM = 'support'
STOCK_LABEL = 'Support Requests'   # the label menu.py registers

# role → the cis portal setting that holds its page text (older cis only).
PORTAL_SETTINGS = {
    'highschool_admin': 'cis.settings.highschool_admin_portal.highschool_admin_portal',
    'instructor': 'cis.settings.instructor_portal.instructor_portal',
    'student': 'cis.settings.student_portal.student_portal',
}


def _cis_helper(name):
    """``cis.portal_text.<name>``, or None on a cis without it."""
    try:
        module = importlib.import_module('cis.portal_text')
    except Exception:
        return None
    return getattr(module, name, None)


def renamed_label(role):
    """The label staff gave the role's support menu item, or None if unchanged.

    None also when the item is not in the menu, has no label, or the menu
    cannot be read, so callers keep their built-in text.
    """
    cis_heading = _cis_helper('page_heading')
    if cis_heading is not None:
        return cis_heading(role, MENU_ITEM, None)
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


def _stored_text(role):
    """The role's stored portal text (a dict), read the way this cis allows."""
    # Instructor text belongs to package-instructor_portal when it is
    # installed (cis#82); cis.portal_text.portal_text() follows the owner.
    owned = _cis_helper('portal_text')
    if role == 'instructor' and owned is not None:
        return owned('instructor_portal')
    module_path, cls_name = PORTAL_SETTINGS[role].rsplit('.', 1)
    return getattr(importlib.import_module(module_path), cls_name).from_db()


def page_blurb(role):
    """The ``support_blurb`` saved in the role's portal settings, or ''."""
    if role not in PORTAL_SETTINGS:
        return ''
    cis_blurb = _cis_helper('page_blurb')
    if cis_blurb is not None:
        return cis_blurb(role, MENU_ITEM)
    try:
        stored = _stored_text(role)
    except Exception:
        log.exception('support_ticket: could not read the %s portal text', role)
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
