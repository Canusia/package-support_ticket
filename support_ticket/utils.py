"""Small helpers shared inside the support_ticket package."""


def _csv_safe(value):
    """Neutralize CSV formula injection: a cell whose first char is one a
    spreadsheet treats as a formula trigger is prefixed with a single quote.
    Ticket type names and notify emails are user-entered and land in a file the
    admin opens in Excel/Sheets.

    Kept here rather than imported from myce_tenant_configs, which only some
    tenants have (#2)."""
    text = '' if value is None else str(value)
    if text[:1] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + text
    return text
