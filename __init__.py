# Outer package root for the support_ticket submodule.
# Do NOT import Django models or app code here — this module is imported before
# the app registry is ready. Outer proxy modules (urls.py) re-export from the
# inner `support_ticket.support_ticket` package.
