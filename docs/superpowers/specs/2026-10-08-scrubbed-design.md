# Scrubbed — design spec

Date: 2026-10-08. Status: draft for review. Working name **Scrubbed** (brand provisional, like Arrearo's slug).

The second AWS CDS Agentic AI hackathon entry. A perioperative coordination and safety agent that a surgical team runs from WhatsApp. It keeps everything around an operation on track, before and after: the schedule, paging the team, patient readiness, a photo-based instrument second-count, and post-op follow-up.

## Goal

Give a surgical team one agent, on WhatsApp, that makes sure every case is ready and nothing is missed around it. A coordinator sets up a case; the team is paged; the patient is prepared and their readiness tracked; a before/after photo of the instrument tray is compared as a second count; and the patient is followed up after surgery. Spine plus brain, the Arrearo way: deterministic rules and records hold the facts, Claude reads photos and messages and decides what the user meant and what to flag. The model never makes the safety call alone.

## Users

- **Primary: the surgical team** — a coordinator (sets up cases, sees the worklist), surgeons (check their list, get the case brief, run the pre-op checklist), and theatre staff / scrub nurse (send the tray photos). Staff log in once by OTP and their WhatsApp number is linked to their staff record.
- **Secondary: the patient** — identified by their number on a case, no login. Receives pre-op instructions, readiness nudges, and post-op follow-up.

## Non-goals (v1)

- **No help during the operation, and no clinical decision support.** Scrubbed is operational: scheduling, paging, logistics, readiness, the instrument second-count, and follow-up. It never diagnoses, never says "you are fine", and is not a medical device. Post-op danger signs are recognised and **escalated to the team**, not judged.
- **The instrument check is a second count, not the count.** It flags discrepancies for a human; the manual WHO surgical count remains authoritative. We never claim the app counted the instruments.
- **No payment rail.** Patient balance is a readiness signal, tracked and confirmed, not collected.
- **No EHR/PACS integration.** v1 is self-contained with seeded cases.

## The v1 spine (one case, end to end — the demo)

A case is scheduled → the **team is paged** on WhatsApp (an auto-generated audio message, plus an AWS voice call for an urgent page) → the **patient is prepared** and their **readiness tracked** (instructions sent, fasting confirmed, consent, balance clearing), and a **not-ready case is flagged** before the day → the **instrument second-count**: the scrub nurse sends a tray photo before and after, Claude compares them and **flags anything unaccounted for**, which **escalates** to the surgeon and coordinator → after surgery the **patient is followed up**, and a **danger sign escalates** to the team. A surgeon can ask "my list today" any time.

That walk exercises WhatsApp (text, interactive, audio, vision, documents), AWS Voice, SES and Bedrock.

## Modules

- **A. Schedule + case board** — cases (patient, procedure code, theatre, time, assigned team), the source of truth. Coordinator CRUD; surgeon read ("my list").
- **B. Team paging, acknowledgement and escalation — the page ladder.** A case has a team roster (often ~10: surgeon, assistant, anaesthetist, scrub and circulating nurses, ODP). When a page fires — agent-triggered on a new or changed case, or composed by the coordinator — Scrubbed sends it to **each member individually** on WhatsApp (text, with an audio version for urgency), and asks each to **Acknowledge** with a tap.
  - **Per-recipient tracking:** for every member Scrubbed records sent, delivered, **read** (the WhatsApp read receipt, when the recipient has them on), and **acknowledged**, each with a timestamp.
  - **Escalation ladder:** if a member has not acknowledged within **30 minutes**, Scrubbed **places a voice call** (AWS Voice, Polly speaks the page) to get their attention. The timer is a per-page EventBridge schedule; acknowledging cancels it.
  - **The reliable signal is the Acknowledge tap.** WhatsApp read receipts can be switched off by the recipient, so the ladder escalates on no *acknowledgement*; the read-time is shown on top whenever WhatsApp provides it.
  - **Audit:** every page, delivery, read-time and acknowledgement is stored and shown on the dashboard, per case and per person, so you can see later exactly who was told and when each of them saw it.
  - **Missed-member form:** if a member still does not respond after the call, the agent sends them a **form** (a PDF, or a short structured in-chat form) to capture their status or handover; they complete it and **upload it back** on WhatsApp; Scrubbed stores it against the case on the dashboard (`GetWhatsAppMessageMedia` → S3), and can read it with Claude vision.
  - The coordinator can also **compose and send a page or a broadcast** to a case's team from the dashboard or WhatsApp; the same tracking and ladder apply.
- **C. Surgeon self-service + pre-op checklist** — "my list today/tomorrow", a case brief, and an interactive WHO-style sign-in / time-out checklist the surgeon runs in chat.
- **D. Patient readiness** — send pre-op instructions (fasting, arrival time), collect confirmations, track consent and the balance (track-and-confirm). A deterministic readiness score; cases at risk of cancellation are flagged early on the coordinator's worklist (SES) and board.
- **E. Post-op follow-up** — scheduled check-ins to the patient on WhatsApp; Claude classifies the reply; recognised danger signs escalate to the team. Never diagnoses, never reassures.
- **F. Instrument second-count (the centrepiece)** — before and after tray photos over WhatsApp; Claude vision catalogues the visible instruments in each into a structured list; a deterministic compare flags items present-before-absent-after; a discrepancy escalates. Both photos, both catalogues and the diff are stored as an audit record.

## Architecture (AWS serverless, one SAM stack — Arrearo's shape)

- **WhatsApp inbound:** End User Messaging Social → SNS → `webhook` Lambda. Staff numbers run the app (login + router); patient numbers on a case run the readiness/follow-up flow; the scrub nurse's tray photos run the instrument check.
- **App layer** (reused pattern from Arrearo's `wa/`): `session` + `auth` (staff OTP login), `router` + `intent`, `views`, `actions`, `messages` (text/interactive/audio/document builders).
- **Navigation and natural language (first-class, ported from Arrearo):** a tappable menu makes everything reachable in a couple of taps — my list, a case, the checklist, the tray check, page the team, the follow-up queue. On top of that, a staff member can just **ask in plain language** and the agent does exactly that: "what's on my list this afternoon", "page the team for the 2pm", "start the pre-op checklist for Mr X", "flag the cholecystectomy as not ready, no consent yet", "send me the case brief as a PDF". Claude reads the message, picks the one action, and takes them there, or answers in words; anything it is unsure of falls back to the menu. Claude only decides *where to go* and *what was meant* — the spine owns every rule, count and record, and any case or patient it names is validated against the staff member's own hospital and permissions. This is the `intent` + `router` + `menus` pattern proven on Arrearo.
- **Brain (Bedrock):** Claude vision compares tray photos and reads inbound photos; Claude routes free text, classifies patient replies, triages danger signs, and drafts pages and messages. Claude Haiku for reading/classifying/routing, Sonnet for drafting.
- **Spine (deterministic, tested):** readiness scoring and the cancellation-risk rule; the instrument-count comparison and the escalation thresholds; paging cadence and routing; the checklist definition. A `safety` engine module, the analogue of Arrearo's `legal` engine — the facts and the flags are code, not the model.
- **Voice:** `pinpoint-sms-voice-v2` `SendVoiceMessage` (Polly TTS or an MP3) for the call page. Needs an origination number; sandbox for the demo (verified destinations).
- **Email (SES):** the coordinator worklist and digest, patient instruction emails, a case-brief PDF.
- **Documents:** reuse the pure-Python PDF renderer for a case brief, the worklist, and the instrument-count audit record.
- **Data (DynamoDB):** cases, staff, patients, trays (instrument sets + the per-case before/after catalogues), readiness items, events, conversations (every message in and out, per person, timestamped), **page deliveries** (per page, per recipient: sent / delivered / read / acknowledged, each with a time, plus the escalation state), **uploaded forms** (who, which case, S3 key, status), wa-sessions.
- **Scheduling:** EventBridge Scheduler for pre-op reminders, the not-ready sweep, and post-op follow-up timing.
- **Storage:** S3 for the tray photos and generated audio/PDFs.
- **Coordinator dashboard (first-class):** a real, polished web app (React + Vite on S3 + CloudFront, API Gateway HTTP API + Cognito), the command centre the coordinator and charge nurse actually use: a live case board (today's theatres and their readiness); each case's detail (team, patient, checklist, the balance, the instrument second-count audit with before/after photos and the diff); the **paging ladder per case** — every team member with their sent / delivered / read-time / acknowledged state and whether they were escalated to a call; **every conversation** for the case, per person, with read times; **uploaded forms** filed against the case; and the post-op follow-up queue. Real-time against the same API the WhatsApp app uses. This is the permanent record, not a demo screen.

### Design

Scrubbed gets its own identity, not a borrowed one (distinct UI per project). The quality bar is a polished modern SaaS app in the spirit of Zapier: clean, confident, lots of air, clear type hierarchy, card and table surfaces, obvious primary actions, calm empty states, real loading and error states. The palette is Scrubbed's own, built for a clinical setting: a trustworthy deep teal/ink primary, a clean off-white canvas, a single alert accent (a warm amber or a clear red) reserved for flags and escalations, and generous legible typography. Colours are chosen for contrast and named in words. No AI-slop tells: no empty cards, no duplicated badges, no fake telemetry, one provenance line not five. It should look and feel like a product a hospital would buy.

## CDS services called at runtime

| Service | Call | Use |
|---|---|---|
| End User Messaging Social | `SendWhatsAppMessage` | pages, interactive checklist, follow-up, flags (text/interactive) |
| End User Messaging Social | `PostWhatsAppMessageMedia` | send the generated audio page and PDF documents |
| End User Messaging Social | `GetWhatsAppMessageMedia` | pull the inbound tray photos for the second-count |
| End User Messaging Voice | `SendVoiceMessage` | the urgent voice-call page (Polly TTS) |
| Amazon SES v2 | `SendEmail` | coordinator worklist, digest, patient instructions |
| Amazon Bedrock | `Converse` (vision + text) | compare trays, read photos, route, classify, triage, draft |

## The instrument second-count, in detail

1. Before the case, the scrub nurse sends a photo of the laid-out tray on WhatsApp. Claude vision returns a structured catalogue: each instrument type and a count (e.g. `{"artery forceps": 6, "scalpel handle": 2, "swab": 10}`), plus a confidence per line.
2. After the case, a second photo. Claude vision catalogues it the same way.
3. A deterministic compare produces the diff: items whose after-count is below the before-count are flagged as potentially unaccounted for.
4. If the diff is non-empty, Scrubbed escalates: a WhatsApp flag to the scrub nurse and surgeon naming the item(s), and an entry on the coordinator board; a voice page if configured.
5. The two photos, the two catalogues, the diff and the human's acknowledgement are stored as an audit record (and a PDF).

**Honesty, in the product and the README:** counting instruments from a photo is hard (overlap, angle, similar tools). Scrubbed is a **second check that surfaces discrepancies for a human**; the manual WHO count is authoritative. Confidence is shown, low-confidence lines are marked "please verify", and a clear tray photo is requested. We never present the app's number as the count.

## Security, safety and privacy

- Operational only; no diagnosis; danger signs escalate, never resolve. Not a medical device.
- **PHI over WhatsApp reaches Meta.** Minimise it: team comms use a case reference and procedure code rather than clinical narrative where possible; the tray photos are instruments, not patients. Patient follow-up carries some health context by nature — disclosed, and a real deployment needs consent, a BAA-equivalent and region review. Flagged as a known constraint, demoed with synthetic patients.
- **Login / access (both surfaces, like Arrearo):**
  - **Web dashboard:** Cognito sign-in (email + password) for the coordinator and admins.
  - **WhatsApp:** the OTP login we built for Arrearo, ported — a staff member messages the number, taps Log in, enters their work email, gets a 6-digit code (SES), and their WhatsApp number is linked to their staff record. No passwords in chat; hashed, expiring, rate-limited; one number, one staff member.
  - **Provisioning:** staff do not self-sign-up. An admin adds a staff member (name, role, work email, WhatsApp number) on the dashboard; that person then links their number by OTP. A clinical tool gates who gets in.
  - **Patients** never log in; they are only ever messaged in the context of their own case, and only about that case.
  - Reuse Arrearo's `wa/session` + `wa/auth` modules as the starting point.
- Every send honours a dry/live switch and the 24-hour window; cold outbound needs a template (disclosed).

## Demo (judges watch the video; everything really calls CDS on our verified numbers)

Seeded scenario: one scheduled case (Theatre 2, 14:00, a named synthetic patient and procedure), a team (surgeon + scrub nurse) on our verified numbers, a patient on a verified number, and a tray with a known set. The video walks: schedule the case → team paged (WhatsApp audio + a real voice call to our number) → patient gets instructions, readiness tracked, a not-ready case flagged → tray photo before and after (we remove one clamp) → Scrubbed flags the missing clamp and escalates → post-op follow-up, a danger-sign reply escalates → surgeon asks "my list". Real runtime calls throughout, on our controlled setup; sandbox/template/production-access limits disclosed as future work.

## Submission logistics (second entry — to confirm with Roger)

This is the **second** CDS entry, so it needs its own net-new ACE opportunity tagged `AWS CDS Agentic AI Hackathon -Sept. 2026`, its own corporate email on its own APN-registered domain, and its own public repo (handle `jo2980958`). The build account and entity (Kasamafo vs a second Brownshift-linked setup) are unresolved and need deciding before the WABA/voice numbers are provisioned. Not a code question; does not block building the app.

## Build split (after this spec and the plan are approved)

Reuse Arrearo's proven pattern. Agents on isolated modules against fixed contracts: schedule + data model; staff auth + session (port from Arrearo); paging (WhatsApp audio + voice); the instrument second-count (vision compare + the deterministic diff); readiness + funds + risk; post-op follow-up + triage; router + intent + views; documents/worklist. Lead owns the data model, the safety engine, IaC/IAM, webhook integration, deploy and the seeded demo.

## Quality bar

9–10/10, in-depth, no AI slop. A real app a hospital could use, not a demo. Both surfaces are first-class: the WhatsApp agent and the polished web dashboard. Every CDS call is real at runtime. Deep, tested spine logic (the safety engine), genuine seeded data, real loading/error/empty states, and an honest, specific product. Built by ~10 agents against fixed contracts so the depth is real and consistent, not shallow or divergent.

## Decisions taken (change on review)

- **Dashboard:** in v1, first-class and polished (above).
- **Build/demo account:** build and demo on Brownshift's existing WABA + a provisioned voice number to get a working app fast. Separating this into its own entity/WABA for the second *submission* is a later logistics step, not a build blocker.
- **Name:** working name **Scrubbed** (provisional, finalise from a quick name check like Arrearo).

## Open questions for review

1. "Zapier design" — confirm you mean a polished modern-SaaS *quality bar* for Scrubbed's own dashboard (not literally cloning Zapier's brand).
2. The **voice-call page** needs a voice origination number provisioned (none today); fine to provision, or start with the WhatsApp audio page and build+disclose voice?
3. Keep the name **Scrubbed**?
