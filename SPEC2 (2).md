# Contractor Billable Hours Tracker: Build Spec 2 (Escrow + Payouts)

Phase 2. Builds on the phase-1 prototype: single-tenant, real Stripe money movement, contractor Connect payouts, immutable submission/dispute records, and a 2% platform fee. Not multi-tenant yet.

Platform's role in disputes: the app records an immutable, timestamped evidence trail (submissions, rejections, reasons, photos) for every project. Resolving a dispute is between the client and the contractor; the platform does not arbitrate. The Stripe hold's only job is guaranteeing payment once things resolve normally — it is not the evidence record and does not survive a prolonged dispute (see section 7).

## 1. Objects

| Object | Key fields | Notes |
| --- | --- | --- |
| Client | name, email, org (future: teams/roles within one account) | Creates projects and contractors. Every Client account's data is isolated from every other's from the start — see section 13 |
| Contractor | name, email, phone, stripe_connect_account_id, connect_status | Standalone; many-to-many with Project via Assignment. Cannot be assigned to a project without a completed Connect account. Deletion is blocked (archive instead) while assigned to any active project |
| Project | customer_name, customer_contact, description, status, frozen (bool), frozen_reason | Created by client. Never deleted, even unresolved — a stalled project is superseded by a new one, not removed. Completion requires every approved (non-denied, non-pending) SubJob to be `accepted` (see section 4). Escrow lives on SubJob now, not Project — see that row and section 7. `frozen` is independent of `status`: when any sub-job's escrow expires or detaches, the whole project freezes regardless of what stage it's in (section 7) |
| Assignment | project ref, contractor ref, status (invited/accepted/rejected), invited_at, responded_at | Created on drag-and-drop + Save. Drives the notification and accept/reject flow |
| SubJob | project ref, label, before_photos (required at creation), amount (nullable until approved), status (pending_approval/denied/open/pending_review/accepted), created_by (client/contractor), denial_reason (nullable) | A project holds 1 to many SubJobs, all direct children of the project (e.g. "Fix bathtub," "Fix pipe," "Fix mold," "Fix drywall" are siblings under one project, distinguished only by their project ref — no nesting between sub-jobs). A before photo is required to create any sub-job, client- or contractor-created. A client-created sub-job skips `pending_approval` — the client is both creator and approver, so it's priced and goes to `open` in one action. A contractor-created one starts `pending_approval`; the client acts on the before photo to approve-and-fund, deny, or leave it (see section 4). `denied` is terminal but never deleted: it stays visible on the project as a permanent record, just unfunded |
| Submission | sub_job ref, contractor ref, timestamp, hours (decimal), after_photos, notes, review_status (pending/accepted/rejected), reviewed_by, review_reason, review_evidence | Immutable and append-only, one per completion attempt on an `open` sub-job. Never deleted or overwritten, including on rejection. Hours are entered per sub-job, not per project. This is the completion record (after photo + hours) — the before photo lives on SubJob itself, since it's created earlier and drives a separate decision (fund or deny, not accept or reject a completion) |
| Escrow | sub_job ref, stripe_payment_intent_id, amount, capture_method: manual, status, platform_fee_amount | One per sub-job, not per project — a project with multiple contractors can only pay each contractor through their own sub-job's own PaymentIntent, since a Stripe destination charge routes to a single Connect account. Created when the client sets that sub-job's amount. platform_fee_amount = 2% of amount, passed as Stripe's application_fee_amount on capture. Each sub-job's escrow captures independently when that sub-job is accepted, so a project with 1 disputed sub-job out of 10 still pays out the other 9 |

## 2. Project status flow

`Created -> Contractor Assigned -> Contractor In Route -> Project In Progress -> Ready For Evaluation -> Project Complete and Funds Disbursed`

- Client creates the project (customer name, contact, description/completion criteria) -> project appears in the project list.
- Client drags contractor(s) into the project and saves -> Assignment created, contractor notified at their primary contact.
- Contractor accepts -> status moves to Contractor Assigned; flow proceeds through the remaining states as work happens.
- Contractor Assigned -> Contractor In Route: a second notification goes out after acceptance with an "I'm on my way" link. Since the contractor logs in for everything else at this level (section 5), this link deep-links into their logged-in dashboard to confirm, rather than being its own anonymous token.
- Contractor rejects -> Assignment removed, status reverts to Created so the client can assign someone else.
- Each sub-job's escrow captures independently as that sub-job is accepted (section 7) — funds move as work is approved, not in one lump sum. A submission moving a sub-job to Ready-for-review triggers client review of that sub-job. Once every sub-job is `accepted` (and therefore already paid out), the project moves to Project Complete and Funds Disbursed — that status confirms everything is done, it doesn't itself trigger a payment.
- If no submission is ever accepted, the project stays as a permanent record. The client opens a new project for that customer.

## 3. Drag-and-drop assignment (Vue)

- Vue frontend consuming the Django/DRF API (not Django templates). Use vue-draggable (SortableJS).
- Contractor pool: all of the client's contractors, filterable and searchable by name; each card shows a reliability badge (accept rate, rejection count — see section 8) and a visual marker if already assigned to this project or others.
- Drag a contractor card into the project's "assigned" zone. On drop, create the Assignment client-side optimistically, then confirm against the API; roll back the card on a failed confirm.
- Save fires the assignment notification (n8n) to the contractor's primary contact.
- This is an interaction-layer concern only — Assignment's accept/reject logic is unchanged by how the assignment was made.

## 4. Sub-jobs, submissions, and the dispute model

A project holds 1 to many sub-jobs, all direct children of the project. The bathtub scenario: "Fix bathtub," "Fix pipe," "Fix mold," "Fix drywall" — four sub-jobs, all siblings under the "Fix Bathtub" project, distinguished only by their project ref. There is no nesting between sub-jobs; a found issue is just another sub-job on the same project, not a child of the sub-job it was found under. Each sub-job carries a before photo from creation and a decimal hours entry with an after photo from its completion, and is approved or rejected on its own.

**Who creates a sub-job, and how it gets funded:** the client can pre-create sub-jobs when scoping the project; a contractor with an accepted Assignment can also create one themselves, mid-project, from their phone — the client isn't on site and can't know what the contractor finds once work starts. Either way, a before photo is required to create the sub-job at all — it's the evidence the client uses to decide whether to fund it.

- **Client-created:** the client is both creator and approver, so there's no separate approval step — they attach the before photo and set the amount in one action, creating the escrow and going straight to `open`.
- **Contractor-created:** starts `pending_approval` with no amount yet, since the client hasn't seen it. The client reviews the before photo (notified per section 8) and makes one decision:
  - **Approve and fund:** sets the amount, which creates that sub-job's own escrow (section 7) and moves it to `open`. The contractor can now do the work and submit a completion.
  - **Deny:** the sub-job moves to `denied`, with an optional reason. No escrow is ever created for it. It is never deleted — it stays visible on the project's sub-job list as a permanent record, just unfunded, the same way a rejected completion stays in history rather than disappearing.
  - **No action:** if the client never responds, the sub-job just sits `pending_approval` indefinitely. It's treated as if it were never part of the project — no money committed, and it doesn't count toward project completion or anything else. No auto-deny, no deadline; a courtesy reminder (section 8) is as far as it goes.

Once `open`, the contractor submits a completion (after photo, hours, notes) as a Submission. That's a separate decision from the one above — the client is now evaluating finished work, not deciding whether to fund it.

**Project completion requires every approved (non-denied, non-pending) sub-job to be accepted.** A denied sub-job and one still sitting `pending_approval` don't count against this — neither ever entered the work pipeline. A one-sub-job project needs one completion approval. A ten-sub-job project needs all ten completions approved before the project can reach Project Complete and Funds Disbursed. A single outstanding sub-job blocks the project's completion status, but not the other sub-jobs' payouts — because each sub-job's escrow captures independently on its own acceptance (section 7), a project with 1 disputed sub-job out of 10 still pays out the other 9 as they're approved. Only the disputed one stays held.

Every submission is its own immutable, append-only record permanently tied to its sub-job. Nothing is ever deleted or overwritten.

Example, for the "Molded wall" sub-job:
1. Contractor creates the sub-job with a before photo. Client approves and sets the amount -> escrow authorized, sub-job moves to `open`.
2. Contractor submits completion 1: timestamp, after photo, hours.
3. Client rejects completion 1: free-text reason + optional evidence (photos/files), attached to the rejection event permanently.
4. Contractor submits completion 2: timestamp, after photo, hours.
5. Client accepts completion 2 -> that sub-job is `accepted`, its escrow captures; the project checks whether every other approved sub-job is also accepted before it can move to Complete.

Completion 1 and its rejection stay attached to the sub-job alongside completion 2, in order — the same as a denied sub-job staying attached to the project rather than disappearing.

Evaluation step: a submission moves its sub-job to `pending_review`. The client reviews the after-photo evidence against the before photo recorded at creation (and contacts the customer if needed) per sub-job. Accept -> that sub-job is `accepted` and its escrow captures. Reject -> reason recorded, contractor remedies that sub-job and resubmits. The project as a whole moves to Ready For Evaluation once at least one sub-job is pending, and to Project Complete only once all approved sub-jobs are accepted.

**Activity feed:** one chronological, read-only log per project — every assignment, submission, rejection, and capture event, each with actor, timestamp, and any attached reason/evidence. This is the evidence trail made visible; build it as a single endpoint that folds Assignment, Submission, and Escrow events into one ordered list.

## 5. Contractor mobile access

Contractors log in. Creating a sub-job, pricing gates, Connect onboarding, accepting/rejecting an assignment, and confirming in-route all need real interaction and a persistent identity — Connect onboarding especially, since it ties a Stripe account to that contractor permanently. Build a lightweight contractor login into the same Vue app (separate contractor-facing views, no drag-and-drop or client data), replacing phase 1's anonymous token-link approach entirely at this level.

## 6. Contractor onboarding (Stripe Connect)

- Connect Express, for lightweight onboarding.
- A contractor's `connect_status` must be `complete` before they can be dragged into a project (enforce at the Assignment-create endpoint, not just in the UI).
- Store `stripe_connect_account_id` on Contractor once onboarding finishes (via Connect's hosted onboarding + webhook on `account.updated`).
- No Connect account -> contractor can still exist as a record (for the pool), but assignment is blocked with a clear reason shown in the UI.

## 7. Escrow / Stripe integration

- One manual-capture PaymentIntent (`capture_method: manual`) per sub-job, not per project — this is what lets a project with multiple contractors pay each one correctly, since a destination charge only routes to a single Connect account. Authorized against the client's card. Funds are held by Stripe against the card, never in the platform's own balance.
- Created when the client approves and prices a sub-job: for a client-created sub-job, that can happen right at creation; for a contractor-found one, it's the client's response to the before-photo notification (section 8, section 4), which moves the sub-job from `pending_approval` to `open`. A denied sub-job never gets one.
- **Platform fee:** 2% of the sub-job's amount. Pass it as `application_fee_amount` on the destination charge at capture time, so Stripe splits it automatically — the platform receives its 2%, the contractor's Connect account receives the remainder, no manual transfer step needed.
- Capture fires automatically when that specific sub-job is accepted, as a destination charge to the contractor who submitted it. This happens independently per sub-job as each is approved — not held until the whole project is done — so a disputed sub-job doesn't block payout on the others.
- **Hold expiry:** authorization holds expire (historically ~7 days, varies by card network — confirm current limits in Stripe's docs before building the expiry-handling logic). On expiry, or an unresolved dispute past the hold window, for that sub-job:
  - Its escrow object is detached.
  - **The whole project freezes**, not just that sub-job — once any sub-job on a project is no longer holding money, the entire project locks: no new sub-job creation, approvals, submissions, or status progression on any sub-job in the project, even ones whose own escrow is fine. This is a project-level `frozen` flag, not a new stage in the 6-state flow — a project can freeze from any status and resumes wherever it was.
  - No new state is added anywhere on the project during a prolonged dispute; the permanent submission history and evidence stand regardless of escrow status.
  - **Unfreezing:** the client re-authorizes a fresh PaymentIntent for each expired sub-job. The project unfreezes automatically once none remain in an expired/detached state — if more than one sub-job expired, all of them need to be refunded, not just one.
- **Removal restriction:** the client cannot detach an active escrow object from a sub-job except when it's `open` with no submission yet, or in a dispute state past the hold's expiry window (your working rule: 7 business days). Enforced by app logic, not Stripe — this does not prevent the client's bank-side chargeback, which is outside the app's control.
- **Re-authorization after expiry:** when a dispute resolves after the hold expired, the app does not silently re-charge the client's saved card. It prompts the client to actively re-authorize — a new PaymentIntent for that sub-job's agreed amount, which the client confirms (possibly through a card re-entry or SCA/3D-Secure step). This also clears that sub-job's contribution to a project-wide freeze. No automatic background charge, even with a saved card on file.
- **No amount-increase mechanic needed:** because escrow is per sub-job, "scope grows" just means creating another sub-job with its own amount and its own PaymentIntent, not amending an existing hold.

## 8. Notifications and reminders (n8n)

- Contractor notified on assignment invite, and again right after accepting with the "I'm on my way" in-route link.
- Client notified on: a new contractor-created sub-job with its before photo, awaiting an approve-and-fund or deny decision; submission received; a sub-job reaching pending_review; escrow nearing expiry per sub-job (e.g. 24h before the ~7-day window closes); the project freezing when a sub-job's escrow expires, and unfreezing once resolved.
- Reminder to the contractor if an assignment invite goes unanswered past a set window, if the in-route link goes untapped past a set window; to the client if a sub-job sits `pending_approval` past a set window (courtesy only, no forced action — section 4), a submission sits in review past a set window, or a project stays frozen past a set window.

## 9. Contractor reliability (pool badge)

- Computed field per Contractor: accepted-submission rate and rejection count, derived from Submission history. No separate model — a query/annotation on existing data.
- Shown as a badge on the contractor card in the drag-and-drop pool.

## 10. Reporting

- Simple dashboard: active projects by status, sub-jobs awaiting approval, count of frozen projects, total escrow currently held (summed across open sub-job PaymentIntents), count of sub-jobs in a dispute/expired-hold state, total platform fees captured to date.
- Read from existing Project/SubJob/Escrow data; no new write path.

## 11. Tech stack

- Backend: Django + DRF + Postgres.
- Frontend: Vue + vue-draggable (SortableJS).
- Payments: Stripe (manual-capture PaymentIntents, Connect Express, `application_fee_amount` for the 2% platform fee).
- Automation/notifications: n8n.
- Hosting: same reusable Docker Compose template (Django + DRF + Postgres + n8n + Vue), local for now, consistent with phase 1.

## 12. Build phases

1. **Contractor + Connect onboarding**: Contractor CRUD, Connect Express onboarding flow, `account.updated` webhook, assignment-blocked-without-Connect rule.
2. **Drag-and-drop assignment**: pool + project drop zone, optimistic create/confirm, reliability badge, assignment notification.
3. **Status flow + sub-jobs + submissions**: flat SubJob model (project-level children only, no nesting) with mandatory before-photo at creation and `pending_approval`/`denied`/`open` gating, 6-state project status machine driven by "all approved sub-jobs accepted," immutable per-sub-job Submission model with decimal hours (blocked until `open`), accept/reject with reason + evidence, activity feed endpoint.
4. **Escrow**: per-sub-job PaymentIntent create-on-approval and capture-on-accept with `application_fee_amount`, expiry detection, project-wide freeze/unfreeze on any sub-job's escrow expiry, re-authorization prompt.
5. **Notifications + reminders**: n8n wiring for all events in section 8.
6. **Reporting**: dashboard endpoint + Vue view.

## 13. Security and tenant isolation

Multiple Client accounts (separate businesses) use this platform from the start, so per-account isolation is not deferred with the rest of multi-tenancy — only the org/team layer (multiple users inside one client account, roles, platform billing) is deferred.

- Every Project, Contractor, SubJob, Submission, and Escrow row is owned by exactly one Client account, directly or via its Project. Every endpoint filters by the requesting Client's (or Contractor's) own id — never by trusting an id passed in the URL or request body alone.
- A request for an object outside the requester's own scope returns 404, not 403, so a client cannot confirm another client's project id even exists.
- A Contractor can be assigned across multiple different Client accounts. Their view is scoped to their own Assignments, SubJobs, and Submissions across whichever clients they work for — never another contractor's data, and never the rest of a client's account beyond what they're assigned to.
- Stripe Connect account ids and PaymentIntent ids are only ever looked up through the owning Contractor/Project relation, never taken raw from client input. Webhook handlers verify the Stripe signature and map events to internal records by the platform's own stored ids, not by trusting webhook metadata.
- Photo and file URLs stay non-guessable and are served only through the authenticated, scoped endpoint (carried over from phase 1's rule).
- **Test requirement, added to phase 1 (Contractor + Connect onboarding) and re-run for every object type added in later phases:** create two Client accounts (and a Contractor assigned to only one of them), then confirm every list and detail endpoint returns 404 when the other account's ids are substituted in in place of the requester's own.

## 14. Open items to confirm before/while building

- [ ] Exact Stripe auth-hold expiry window for the cards you'll support.
- [ ] Legal review of the escrow/dispute language and the platform's own obligations as a Stripe platform (this is outside what the app's data model can settle, and belongs with a lawyer before real client money moves through it).
