# Scrubbed — build plan

How we build the spec with ~10 agents without slop: the lead owns the shared foundation, the contracts, the safety engine and all integration; agents fill isolated modules against fixed interfaces. Reuses Arrearo's proven pattern and ports its infra where it is domain-agnostic.

## Principles

- **Spine vs brain.** Deterministic, tested code owns every rule, count, score and record (`safety/engine.py`, the data model). Claude only reads photos and messages and decides what the user meant and what to flag. Any case/patient the agent names is validated against the staff member's own hospital and permissions.
- **Contracts first.** Every module is a stub with fixed signatures before anyone fills it. Agents edit only their files, never shared ones; if they think a shared module must change, they stop and report.
- **Real at runtime.** Every CDS call is real; demo on our verified numbers; sandbox/template/voice-number limits disclosed.
- **Tests per module**, stubbed boto3 (moto) and stubbed Bedrock; keep the whole suite green; a full-surface audit at the end.

## Lead owns (me)

- `common/config.py` (done), the module **stub contracts**, `common/db.py` generic helpers.
- `safety/engine.py` — the deterministic core: readiness scoring, cancellation-risk rule, the instrument-count **diff**, escalation thresholds, the WHO checklist definition, paging routing. The trust boundary. (I write it; an agent may extend under review.)
- `infra/template.yaml` + IAM (all tables, 3 Lambdas, API, Cognito, SNS, EventBridge, S3/CloudFront, voice permissions), `infra/deploy.sh`, `infra/seed.py`.
- `services/functions/` — `webhook.py` (route inbound: staff→app, patient→readiness/follow-up, tray photo→instrument check), `api.py` (dashboard API), `scheduler.py` (the 30-min page escalation, pre-op reminders, the not-ready sweep, post-op follow-up timing).
- Integration, deploy, the seeded demo, review of every module.

## Agents (isolated modules, fixed contracts)

1. **Data model + accessors** — `common/db.py` domain accessors for staff, cases, patients, trays, readiness, pages (per-recipient delivery/read/ack), forms, events, conversations; `conftest.py` table schemas. + tests.
2. **CDS channels (incl. voice)** — `common/cds.py`: WhatsApp send (text, interactive, audio note, document), `GetWhatsAppMessageMedia`, `PostWhatsAppMessageMedia`; SES `SendEmail`; **AWS Voice** `SendVoiceMessage` (pinpoint-sms-voice-v2, Polly) for the call page; a Polly-synth helper to make the audio note. Dry/live aware. + tests.
3. **Staff auth + session** — port `wa/session.py`; adapt `wa/auth.py` so OTP links a number to a **staff** record (via `db.get_staff_by_email`), admin-provisioned, no self-signup. + tests.
4. **Instrument second-count (the hero)** — `agent/vision.py`: Claude vision catalogues a tray photo into a structured instrument list with per-line confidence; `wa/actions` tray flow stores before/after and calls `safety.instrument_diff`; escalates on a discrepancy; "second count, manual WHO count is authority" framing. + tests (stub Bedrock).
5. **Paging ladder** — `services/paging.py`: fan a page out to a case's roster, write a per-recipient page record, handle the Acknowledge tap, and arm/cancel the 30-min escalation (hooks the scheduler the lead wires). + tests.
6. **Readiness + patient flow** — `services/readiness.py` + patient messaging: pre-op instructions, confirmations (fasting/consent), balance (track-and-confirm), readiness score via `safety`, cancellation-risk flag; post-op follow-up messages + danger-sign triage via `agent/classify`. + tests.
7. **WhatsApp app — router/intent/menus** — port the pattern: `wa/router.py`, `wa/intent.py` (natural-language → action/answer, safe menu fallback, ownership-validated), `wa/menus.py`. Surgeon self-service ("my list"), checklist entry, page/flag by language. + tests.
8. **WhatsApp app — views/actions** — `wa/views.py` (my list, case detail, checklist, readiness, paging status) and `wa/actions.py` (run checklist, page team, flag case, send case brief, start tray check, missed-member form). + tests.
9. **Documents** — extend `common/documents.py`: case brief PDF, coordinator worklist PDF, the instrument-count audit PDF (before/after catalogues + diff), the missed-member form PDF. + tests.
10. **Coordinator dashboard (web)** — `web/` React + Vite, polished, Scrubbed's own clinical identity: live case board, case detail (team/patient/checklist/balance/instrument audit with photos), the paging ladder per case (each person's sent/delivered/read-time/ack/escalated), every conversation with read times, uploaded forms, the follow-up queue. Against the `api`. Real loading/error/empty states. + a couple of component tests.

## Waves

- **Wave 0 (lead):** config ✓, generic db helpers, all module stubs (contracts), the `safety/engine.py` first cut, the SAM skeleton. Agents cannot start before the stubs exist.
- **Wave 1 (parallel):** 1 data model, 2 CDS channels, 3 auth/session, 9 documents, and the lead's `safety` engine. These are the foundation other modules call.
- **Wave 2 (parallel):** 4 instrument check, 5 paging, 6 readiness/patient, 7 router/intent, 8 views/actions, 10 dashboard. Built against Wave-1 contracts.
- **Integration (lead):** webhook/api/scheduler wiring, IAM, deploy, seed the demo case/team/patient/tray, full-surface audit, live verification on our numbers.

## Definition of done (per module)

Real logic (no placeholders), its own tests green, the whole suite green, house style (plain English, short sentences, no em dashes), money in integer pence via `config.gbp`, no secrets, no files touched outside the module's list, committed by the lead (agents do not run git).
