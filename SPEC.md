# Contractor Billable Hours Tracker: Build Spec (v1)

Goal: build the whole workflow end to end, single-tenant, running in local Docker. Not multi-tenant, not deployed.

## 1. Product summary

A client (owner or property manager) creates a project, assigns contractors, and sees a running log of photo-backed work and hours. Contractors use a no-install mobile web page reached through a link the client shares by any messaging app.

Out of scope: scheduling, CRM, invoicing, Stripe, QuickBooks, multi-tenancy, customer (third-party) view, change-order approval, contractor accounts, native apps, deployment.

## 2. Roles

| Role | Auth | Can do |
| --- | --- | --- |
| Client | Django session login | Create projects, assign contractors, get/revoke links, view jobs and visits, approve or dispute, export |
| Contractor | Bearer token in URL (one per assignment) | Start jobs, add before/after photos, log visits, view own entries and dispute comments |

The client is the only role that logs in and the only role that approves or disputes.

## 3. Data model

- **User**: email, password, role. Only clients log in.
- **Project**: owner (FK User), name, scope, budget (optional).
- **Contractor**: name, phone and/or email. No login.
- **Assignment**: project, contractor, hourly_rate, token (long random, unique), revoked (bool). The token is the link.
- **Visit**: assignment, date, hours (decimal, > 0, max 16), notes, status (pending / approved / disputed), client_comment (nullable).
- **Job**: assignment, label, parent (nullable self-FK, set when it is a "found issue" under another job), notes, status (open / complete / approved / disputed), client_comment (nullable).
- **Photo**: job, kind (before / after), file, captured_at, latitude (nullable), longitude (nullable), location_missing (bool).

Rules:
- A job is **complete** only when it has at least one before photo and at least one after photo. Adding the first after photo is the completion signal. There is no separate completion checkbox.
- Multiple jobs can be open at once and close in any order. A parent can close after its found issues.
- Hours belong to visits, not jobs. Do not allocate hours to jobs.
- Entries are append-only. A contractor may edit or delete a visit or job only while it is pending/open, before approval or dispute.
- Approved entries are locked. If the client approves while the contractor is editing, approval wins and the edit is rejected with a clear message.
- Found issues (jobs with a parent) are informational: show a badge in the UI and notify the client. No approval is required before work starts.

## 4. Flows

### 4.1 Client
1. Log in, create a project (name, scope, optional budget).
2. Assign a contractor: name, phone or email, hourly rate. The app generates the link; the UI offers Copy link.
3. Project view: totals (hours, cost = approved hours x rate, pending shown separately), jobs list with before/after photo timeline, found issues nested under their parent job, visits list.
4. Approve or dispute each completed job and each visit: one button plus an optional comment on dispute. Bulk-approve selected items is nice to have.
5. Revoke a link at any time.
6. Export approved visits and jobs to CSV.

### 4.2 Contractor (token link, mobile web)
Home screen shows open jobs, recent visits, and any client dispute comments.

- **Start a job**: label, optional "found issue under" selector (lists open jobs), before photos, notes.
- **Finish a job**: add after photos, optional notes. The job becomes complete.
- **Log a visit**: date, hours (decimal), notes.
- **Disputed item**: the contractor sees the client comment, adds a correction, and resubmits. The item returns to the client queue as pending. The original stays in history.

## 5. Photo capture and reliability

- Use the native camera input (`<input type="file" accept="image/*" capture>`), multiple photos allowed.
- Always store the capture timestamp. Request browser geolocation at photo time. If denied, still allow submit and set `location_missing`; the client sees a "no location" flag.
- Tell the contractor on the form that location is recorded at photo time.
- Weak signal: compress and resize photos client-side before upload, enforce max photo count and size per job, retry failed uploads, and never lose form state on a failed upload.
- The server resizes and validates images on upload. Serve photos only through an authenticated or token-scoped API endpoint, never guessable URLs.

## 6. Security

- Client: standard Django session auth with CSRF protection.
- Contractor token endpoints are a separate namespace, rate-limited, and scoped to that assignment only: create/edit own pending entries, list own entries and project summary. They never expose other contractors, budget, or other assignments.
- Revoked tokens return 403 everywhere.
- Tokens are at least 32 bytes, urlsafe.

## 7. API (DRF)

Client (session auth):
- POST /api/projects/, GET /api/projects/, GET /api/projects/{id}/
- POST /api/projects/{id}/assignments/ (returns link), POST /api/assignments/{id}/revoke/
- GET /api/projects/{id}/jobs/, GET /api/projects/{id}/visits/
- POST /api/jobs/{id}/approve/, POST /api/jobs/{id}/dispute/ (comment)
- POST /api/visits/{id}/approve/, POST /api/visits/{id}/dispute/ (comment)
- GET /api/projects/{id}/export.csv

Contractor (token auth, prefix /api/c/{token}/):
- GET summary (project name, scope, open jobs, recent visits, dispute comments)
- POST jobs, PATCH/DELETE job while open, POST jobs/{id}/photos (kind before or after)
- POST visits, PATCH/DELETE visit while pending
- POST resubmit for a disputed job or visit

Generate the OpenAPI schema with drf-spectacular and commit it.

## 8. Stack

Docker Compose, run locally. Access the app at `http://localhost`, which Chrome treats as a secure context, so geolocation and camera inputs work without HTTPS. Serve the frontend and API through the reverse proxy on one port so they share an origin.

Services:
- Reverse proxy (Caddy)
- Web app: Vue PWA (chosen for Phase 2)
- API: Django + DRF
- Postgres
- Photo storage: Docker volume, accessed through Django's storage backend
- n8n: notifies the client on new entries, found issues, and resubmissions

## 9. Build phases

Build one phase at a time, each with tests.

1. **Backend**: Compose stack, models, migrations, client auth, project -> assign -> job/visit/photo -> roll-up API. Tests: token scoping, revoked token, append-only and lock rules, approval-wins race, 16-hour cap, completion rule (needs before and after).
2. **Contractor form**: token page, start/finish job, found-issue parent, log visit, camera capture, geolocation with fallback, client-side compression, upload retry.
3. **Client dashboard**: project view, job photo timeline with nested found issues, totals, approve/dispute, bulk approve, revoke.
4. **Notify and export**: n8n notifications, CSV export.
5. **Seed data**: a management command that loads the scenario below.

## 10. Seed scenario

A bathtub repair project with one contractor. The contractor starts "Bathtub" with before photos, then opens three found issues under it (broken pipe, mold, drywall crack), each with before and after photos, then closes the bathtub with its after photo. Include several visits with hours, at least one approved job, and one disputed job with a client comment.
