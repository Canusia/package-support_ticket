# Changelog

All notable changes to `package-support_ticket` (MyCE Support Requests).
Releases are git-tag-driven: pin a tag in the host's `webapp/requirements.txt`
(`git+https://github.com/Canusia/package-support_ticket.git@vX.Y.Z`). The
declared version in `setup.cfg` and `pyproject.toml` always matches the tag.

## v1.2.1 — 2026-11-13

- **Support pages follow the renamed menu item (#8).** A renamed Support Requests menu item (Settings → Menu Layout) now renames the student, instructor and HS admin support pages (list "<label>", add "<label> — New", detail "<label>"). Unrenamed tenants keep "Support Requests".
- **Saved page text shows (#8).** Each portal's Portal Language `support_blurb` renders above the requests table; blank text and the untouched placeholders show nothing.

### Upgrading

- No migrations or settings changes.
- Before upgrading, check each portal's Support Requests text in Portal Language: the form requires it, so filler such as "." may have been saved, and it now shows.

## v1.2.0 — 2026-11-09

- **Sender address setting removed (#5).** Support Request emails always go from the site's `DEFAULT_FROM_EMAIL`. A `from_email` value stored on a tenant is ignored and dropped the next time the settings are saved. If a tenant's stored sender differs from `DEFAULT_FROM_EMAIL`, its support emails now come from a different address.
- **New statuses keep their email templates on the first save (#4)** when the settings are saved through the settings API (for example a client_management workbook push). On the settings page, save once to add or rename statuses, then fill in their emails; a renamed status's old templates are not carried over.
- **Filters on Request Types and the CE requests table** sit at the left instead of floating right.

### Upgrading

- No migrations and no `register_settings` changes.
- Release client_management's support requests workbook fix (e68164d8) with this: without it, a workbook push to an upgraded tenant is rejected because it still sends `from_email`.
- `docs/support-requests.pdf` still shows the Sender address field; `docs/support-requests.md` is current.

## v1.1.0 — 2026-11-06

- Request types have a **Description** (migration 0011), edited on the CE type form with the rich-text editor. Students, instructors and HS admins see the picked type's description under Request Type on the new-request page; links open in a new tab, so a docrepo file link (docrepo v0.0.5) can share a form to download. The description is rebuilt in the browser from a tag/link allowlist.

## v1.0.3 — 2026-11-02

- Publishes the Support Requests sidebar items (CE, student, instructor, HS admin) to the cis menu registry (myce_cis v0.1.43a+). On older cis nothing changes.

## v1.0.0 — 2026-09-25

The first stable release. It adds terms to requests, lets CE choose whether a
note is emailed and records who was emailed, and redesigns the CE request and
request-type pages.

### Upgrading

- **Run `migrate`.** Adds `support_ticket.0010_ticket_term_note_emailed`
  (`Ticket.term`, `TicketNote.emailed_to`, `TicketNote.emailed_on`). Coming
  from before v0.0.6, `0009_tickettype_email_assignee` runs as well. `0010`
  depends on `('cis', '__first__')`, so any `cis` version works.
- **Existing requests have no term.** Only requests created after the upgrade
  get one automatically. CE can set it on each request's page.
- **Saved table state resets once.** The CE requests table has a new ID
  (`support_requests_table`), so each user's saved sorting and page length
  start fresh.
- **Note emails change for CE:** see "Changed" below.

### Added

- **Term on requests.** `Ticket.term` (nullable foreign key to `cis.Term`)
  defaults to the active term (`cis.utils.active_term()`) when a request is
  created. If the term can't be found, the request is still created. CE can
  change the term on the request detail page, next to Status and Assigned To.
- **Record of note emails.** Every note records who it was actually emailed
  to and when (`emailed_to`, `emailed_on`). In Debug mode that's the
  `default_to` addresses it was redirected to. The CE "Request Updates" table
  has an Emailed column ("Emailed to … on …" / "Not emailed") and shows
  "No updates found." when there are no notes.
- **Filters on the CE requests API** (`/api/v1/support-ticket-ce/`):
  `ticket_type`, `term_id`, `submitted_from` and `submitted_until` (dates as
  `YYYY-MM-DD`). A malformed value returns no rows instead of a 500 error.
  Rows gain `term_label`.
- **Requests on the type detail page.** A request type's page lists its
  requests, in the same table as the requests list, limited to that type.
- **"Email assignee" per request type** (v0.0.6, listed here for completeness).
  When ticked, the assignee is emailed on submission, on reassignment, and on
  bulk reassignment. The wording is set by the `assignment_subject` /
  `assignment_email` settings.

### Changed

- **CE notes can skip the submitter email.** The CE note form has "Email this
  note to the submitter", **ticked by default**, so the default behaviour is
  unchanged. Unticked, the note is still visible to the submitter in their
  portal, and the other party (the assignee, or `default_to` when there is
  none) is still emailed.
  `services.add_note_with_files(..., email_submitter=True)` takes the same
  choice.
- **CE requests list** (`/ce/support_reqs/`) is laid out like the CE Students
  page. It has an Actions dropdown, a tabbed bordered pane, a grey filter card
  (Status, Assignee, Type, Term, Submitted from/until) and Term / Type
  columns. The table is `ticket/_table.html`, built by
  `views.tickets.ce_table_context()`, and the requests list and the type
  detail page share it. The index view's context moved under `table`.
- **Request types list** (`/ce/support_reqs/types/`) uses the same layout,
  with an Applies To filter. Its columns are Default Assignee, Email Assignee,
  Requires Attachment and the number of requests. It is a client-side
  DataTable instead of a paginated, server-sorted table.
- **Request type detail** is laid out like the CE student page. It has a
  breadcrumb, an Actions dropdown (Add New Type, Delete Type), and
  "<type> Requests" / "Details" tabs. Saving returns to the Details tab.

### Fixed

- **Server-side search and sorting on the CE requests table.** The checkbox
  column was `data: null`, which stops `rest_framework_datatables` reading the
  column list. It now sends `data: 'id'`.
- **Sidebar highlighting** on the CE support pages. The views passed item
  names the `cis` menu doesn't use (`manage_types`, `requests`, and parent
  `support_ticket` on the type detail page), so All Requests and Manage Types
  never highlighted.

## v0.0.7 — 2026-09-25

### Fixed
- The ticket types export no longer imports `myce_tenant_configs`, which
  only some tenants have (#2).
- Tests resolve module paths in both the in-tree and pip-installed layouts (#3).

## v0.0.6 — 2026-09-24

### Added
- "Email assignee" on request types, with `assignment_subject` /
  `assignment_email` settings. Migration `0009`.

### Fixed
- The declared version now matches the tag (#1). v0.0.2–v0.0.5 all declared
  `0.0.1`, so pip treated them as already installed on existing environments.
