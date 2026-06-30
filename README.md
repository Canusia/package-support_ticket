# myce-support-ticket

Multi-role **support request / ticketing** for [MyCE](https://github.com/Canusia) (Canusia's
Concurrent/Dual Enrollment platform). Students, instructors, and high-school administrators open
requests; CE (Concurrent Enrollment) staff triage, assign, respond, and report. The app provides
configurable ticket **types** and **statuses**, settings-driven **email templates** (Django
shortcodes, delivered async via django-mailer), multiple **file attachments** per ticket/note,
server-side **DRF + DataTables** index pages, a **CSV report** of ticket types, a CE **summary
dashboard** (Chart.js), and **bulk actions** (update status / reassign) on the CE table.

The package name is `myce-support-ticket`; the Django app label is always `support_ticket`.

---

## Requirements

This app is **tightly coupled to a MyCE host deployment** — it is not a standalone reusable Django
app. It expects the host's `cis` and `myce` apps, the MyCE role helpers, and several MyCE
frameworks to be importable. Do not install it outside a MyCE tenant.

**Python / Django**

- Python `>= 3.8` (per `setup.cfg` / `pyproject.toml`)
- `Django >= 3.2` (declared `install_requires`)

**Third-party packages** (provided by the host's environment)

- `djangorestframework` + `rest_framework_datatables` — server-side DataTables index pages
- `django-crispy-forms` (Bootstrap 4 template pack) — forms
- `django-mailer` (`mailer`) — async outgoing email queue

**MyCE host apps / frameworks it imports directly**

- `cis` — CustomUser, role helpers (`user_has_cis_role`, `user_has_student_role`,
  `user_has_instructor_role`, `user_has_highschool_admin_role`), `cis.models.note.Note`
  (abstract base for `TicketNote`), `cis.models.settings.Setting` (settings storage), the
  `LoginRequiredMiddleware` allowlist, and the DB-driven sidebar menu (`cis.settings.menu`)
- The `setting` framework — `register_settings`, the `/ce/settings/` Configurator surface
- The `report` framework — `register_reports`, the `/ce/reports/` surface
- `myce.component_registry.ActionRegistry` — powers the CE table's bulk actions
  (`actions.py`)
- `myce_tenant_configs.services.bulk_enroller._csv_safe` — CSV formula-injection guard used by
  the `ticket_types_export` report
- A private S3 media storage (`PrivateMediaStorage`) for attachments

---

## Dual-package layout (editable-submodule pattern)

This repo is both an **installable package root** and an **editable in-tree submodule**, mirroring
`ethos`, `invoice`, `future_sections`, etc. There are two nested package levels:

```
package-support_ticket/            <- repo root = outer/installable package
├── setup.cfg, pyproject.toml, MANIFEST.in
├── README.md, CLAUDE.md
├── models/, forms/, views/        <- outer proxy SHIMS (re-export inner symbols for dev mode)
└── support_ticket/                <- inner Django app (the real code)
    ├── apps.py                    <- SupportTicketConfig + DevSupportTicketConfig
    ├── models/, forms/, views/, urls/, signals.py, api.py, services.py, ...
    ├── settings/, reports/, actions.py
    ├── migrations/
    ├── templates/support_ticket/
    └── staticfiles/support_ticket/
```

Two `AppConfig` classes live in `support_ticket/apps.py`, both with `label = 'support_ticket'`
(so migrations, FKs, and `app_label` are identical in either mode):

| Config | `name` | When it loads |
|--------|--------|---------------|
| `SupportTicketConfig` | `support_ticket` | **prod** — package pip-installed, inner package is top-level `support_ticket` |
| `DevSupportTicketConfig` | `support_ticket.support_ticket` | **dev** — in-tree submodule present; selected via `find_spec('support_ticket.support_ticket')` |

The outer proxy shims (`models/`, `forms/`, `views/` at the repo root) exist only so that
`support_ticket.X` imports resolve in dev mode, where the outer package is on `sys.path` but the
Django app is the inner package. In prod the inner package *is* `support_ticket`, so no shims are
needed.

For deeper internals (signal flow, model overloads, service layer), see
[`CLAUDE.md`](CLAUDE.md) and [`docs/TECHNICAL.md`](docs/TECHNICAL.md).

---

## Installation

### a. Pip-installed (production / other tenants)

For tenants that do **not** carry the in-tree copy, install from a tagged release:

```bash
pip install git+https://github.com/Canusia/package-support_ticket.git@v0.0.1
```

Pin it in the host's `webapp/requirements.txt`:

```
git+https://github.com/Canusia/package-support_ticket.git@v0.0.1
```

In this mode `find_spec('support_ticket.support_ticket')` is **false**, so the host wiring (below)
falls through to the top-level `support_ticket.*` branches and loads `SupportTicketConfig`.

### b. Editable submodule (development / in-tree)

For the tenant that owns the source (e.g. EWU), add it as a git submodule at
`webapp/support_ticket/`:

```bash
git submodule add git@github.com:Canusia/package-support_ticket.git webapp/support_ticket
```

Now the inner package `support_ticket.support_ticket` is importable, so
`find_spec('support_ticket.support_ticket')` is **true** and the host wiring selects the
inner-path branches and `DevSupportTicketConfig`. Migrations are authored in the **inner**
package (`webapp/support_ticket/support_ticket/migrations/`).

---

## Wiring into a MyCE host

The host selects dev vs. prod paths with `importlib.util.find_spec(...)`. Add the following blocks
**exactly** as the host does.

### 1. `INSTALLED_APPS` (`myce/settings.py`)

```python
'support_ticket.support_ticket.apps.DevSupportTicketConfig'
if importlib.util.find_spec('support_ticket.support_ticket')
else 'support_ticket.apps.SupportTicketConfig',
```

### 2. `STATICFILES_DIRS` (`myce/settings.py`)

```python
os.path.join(get_package_path("support_ticket.support_ticket"), 'staticfiles')
if importlib.util.find_spec('support_ticket.support_ticket')
else os.path.join(get_package_path("support_ticket"), 'staticfiles')
if get_package_path("support_ticket") else None,
```

### 3. URL includes (`myce/urls.py`)

Mounts the four portals and the `api/v1/` DRF router. Both branches are required: the `if` branch
uses inner (`support_ticket.support_ticket.urls.*`) paths for dev, the `else` branch uses
top-level (`support_ticket.urls.*`) paths for prod.

```python
if importlib.util.find_spec('support_ticket.support_ticket'):
    urlpatterns += [
        path('ce/support_reqs/', include('support_ticket.support_ticket.urls.ce')),
        path('student/support_requests/', include('support_ticket.support_ticket.urls.student')),
        path('highschool_admin/support_requests/',
             include('support_ticket.support_ticket.urls.highschool_admin')),
        path('instructor/support_requests/',
             include('support_ticket.support_ticket.urls.instructor')),
        path('api/v1/', include('support_ticket.support_ticket.urls.api')),
    ]
else:
    urlpatterns += [
        path('ce/support_reqs/', include('support_ticket.urls.ce')),
        path('student/support_requests/', include('support_ticket.urls.student')),
        path('highschool_admin/support_requests/', include('support_ticket.urls.highschool_admin')),
        path('instructor/support_requests/', include('support_ticket.urls.instructor')),
        path('api/v1/', include('support_ticket.urls.api')),
    ]
```

### 4. `LoginRequiredMiddleware` allowlist (`cis/middleware.py`)

The DRF viewsets must be exempt from the host's HTML login-redirect middleware so that
unauthenticated/forbidden API calls return JSON `401`/`403` instead of a `302` to the login page.
Add the five viewset **class names** to the allowlist in
`LoginRequiredMiddleware.process_view` (the `if view_func.__name__ in [...]` list):

```python
'CETicketViewSet',
'StudentTicketViewSet',
'InstructorTicketViewSet',
'HSAdminTicketViewSet',
'TicketSummaryViewSet',
```

---

## Post-install commands

Run inside the host container (for EWU: `docker exec -w /app/webapp django_web_ewu python manage.py ...`):

```bash
python manage.py migrate support_ticket      # create the ticket tables
python manage.py register_settings           # surfaces "Support Ticket Settings" under CE Settings -> Misc
python manage.py register_reports            # registers the ticket_types_export CSV report
python manage.py collectstatic               # ships the bundled Chart.js (staticfiles/support_ticket/js/chart.umd.min.js)
```

### Sidebar navigation (DB-driven)

The "Support Requests" nav entries are **not** read from the static `cis/menu.py` at runtime — the
sidebar is rendered from a DB Setting row keyed `cis.settings.menu`. Two ways to surface the nav:

- **Fresh installs** — `menu.install()` defaults already include the entries; nothing to do.
- **Existing installs** — run the host's `cis` data migration
  `0064_add_support_ticket_nav` (`python manage.py migrate cis`), which idempotently injects a
  "Support Requests" entry into each of the `ce_menu`, `student_menu`, `instructor_menu`, and
  `highschool_admin_menu` keys of the `cis.settings.menu` Setting. It no-ops if the Setting row is
  absent and is reversible.

  The CE entry links to `support_ticket:requests` / `:summary` / `:types`; each role entry links to
  its portal's `*_support_ticket:requests`.

If you maintain the menu by hand, edit the `cis.settings.menu` Setting value (a dict of JSON
strings per role) rather than `cis/menu.py`.

---

## Configuration

Settings live at **CE `/ce/settings/` → Misc → "Support Ticket Settings"** (registered via the
`CONFIGURATORS`/`category 4` entry in `apps.py`; there is no bespoke settings page). They are stored
as a single `cis.models.settings.Setting` row keyed
`support_ticket.settings.support_ticket_settings`. Always read them through the
`support_ticket_settings` classmethods (`from_db()`, `get_statuses()`, `get_default_status()`,
`is_active()`, `can_start(role)`, `status_template(status)`) — never the `Setting` model directly.

| Field | Purpose |
|-------|---------|
| `is_active` | `Yes` / `No` / `Debug`. `No` skips all mail; `Debug` redirects all recipients to `default_to` |
| `who_can_start` | Multi-select of roles (`student`, `instructor`, `highschool_admin`) allowed to open tickets |
| `from_email` | Sender address; falls back to Django's `DEFAULT_FROM_EMAIL` |
| `default_to` | Comma-separated fallback recipients when there's no assignee/notify list |
| `statuses` | Newline-separated status list; the **first** entry is the default for new tickets |
| `submission_subject` / `submission_email` | Template sent to the type's notify list on ticket creation |
| `note_subject` / `note_email` | Template sent when a note is added |
| `status_<slug>_notify` / `_subject` / `_email` | Per-status templates, generated dynamically from the `statuses` list (`_notify` gates whether a status change emails the submitter) |

Email bodies/subjects support **Django shortcodes**. All mail is enqueued through **django-mailer**
(async) — drain the queue with a cron/periodic `send_queued_mail` invocation, otherwise messages
will sit unsent.

---

## Features overview

### Portals

Each portal is role-gated and has its own URL namespace. Index pages are server-rendered shells
that POST to a scoped DRF DataTables endpoint; detail/create views are object-scoped (IDOR guards).

| Portal | URL prefix | URL namespace | Capabilities |
|--------|-----------|---------------|--------------|
| CE staff | `/ce/support_reqs/` | `support_ticket` | Full CRUD: list / detail / delete tickets, manage `TicketType`s, summary dashboard, "new request on behalf of" form, bulk actions |
| Student | `/student/support_requests/` | `student_support_ticket` | List / create / detail of own requests + add notes |
| Instructor | `/instructor/support_requests/` | `instructor_support_ticket` | List / create / detail of own requests + add notes |
| HS admin | `/highschool_admin/support_requests/` | `hs_admin_support_ticket` | List / create / detail of requests from users in their high schools + add notes |

### DRF endpoints (`/api/v1/`)

| Endpoint (basename) | ViewSet | Scope |
|---------------------|---------|-------|
| `support-ticket-ce` | `CETicketViewSet` | All tickets (CE-only) |
| `support-ticket-student` | `StudentTicketViewSet` | `submitted_by = request.user` |
| `support-ticket-instructor` | `InstructorTicketViewSet` | `submitted_by = request.user` |
| `support-ticket-hsadmin` | `HSAdminTicketViewSet` | Tickets from users in the HS admin's high schools |
| `support-ticket-summary` | `TicketSummaryViewSet` | Aggregated counts by `group_by` (`status` / `type` / `assignee`); CE-only, list-only |

All ticket viewsets annotate `attachment_count`. The DataTables format is requested with
`?format=datatables`.

### CE table

The CE "All Requests" table supports CSV/PDF export, status and assigned-to filters,
open-in-modal detail, and **two-phase bulk actions** (registered in `actions.py` via
`myce.component_registry.ActionRegistry`):

- **Update Status** (`bulk_update_status`) — set all selected tickets to a chosen status
- **Update Assigned To** (`bulk_update_assigned_to`) — reassign all selected tickets to a CE user

### CE summary dashboard

CE-only page at `support_ticket:summary` rendering three Chart.js charts (by status, by type, by
assignee), fed by `/api/v1/support-ticket-summary/?group_by=<status|type|assignee>`. The bundled
`chart.umd.min.js` ships under the app's `staticfiles/`.

### Reports

`ticket_types_export` — CSV export of all `TicketType` rows (Name, Applies To, Default Assignee,
Notify Users, Notify Emails, Requires Attachment). Values are formula-safe via `_csv_safe`.
Registered through the `REPORTS` entry in `apps.py`; run from `/ce/reports/`.

---

## Versioning & release

Releases are **tag-driven**. The version in `setup.cfg`/`pyproject.toml` stays nominal
(`0.0.1`); what consumers pin is the git tag.

To cut a release:

1. Make/verify migrations in the **inner** package; run the `submod-package-manifest` skill if you
   added templates, static, settings, or new top-level modules (so `MANIFEST.in` ships them and the
   outer proxy shims exist).
2. Tag and push: `git tag v0.0.2 && git push --tags`.
3. In each consuming tenant, bump the `webapp/requirements.txt` pin
   (`...@v0.0.2`) — and, for a submodule tenant, advance the submodule pointer — **together** in
   one change.

---

## License

Proprietary — © Canusia. No `LICENSE` file is currently included in this repository; add one
before any external distribution. The `MANIFEST.in` already references `LICENSE` so it will ship
once added.
