# Scrubbed — Devpost submission

Paste the sections below into the matching Devpost fields. Upload the images in this folder.

## Links (Devpost "Try it out" + repo)
- GitHub repo: https://github.com/jo2980958-hub/scrubbed
- Live dashboard: https://d3m2lk7yv7pxks.cloudfront.net
- Live API: https://yu3kfw3x0a.execute-api.us-east-1.amazonaws.com
- Demo video: ADD YOUR LINK (YouTube or Vimeo, public or unlisted)

## Images to upload (in this folder)
- `architecture.png` — architecture (AWS icons)
- Grab a dashboard screenshot or two from the live URL for the gallery / thumbnail.

## Elevator pitch (tagline, keep under ~200 chars)
Run a surgical case from WhatsApp, before and after the operation, and do the one check a team cannot get wrong: a deterministic second count of the instrument tray, with Claude only reading the photo.

## Inspiration
Operations get cancelled on the day because readiness was never confirmed in time, and the things that go wrong around surgery are communication gaps and counts, like a team member who never saw the page or a retained instrument. Both live in the messaging layer the team already uses. We wanted an agent that coordinates the whole case over WhatsApp, with every count and escalation owned by tested code rather than a model.

## What it does
The clinical team runs it from WhatsApp: one-time-code login, a menu, and natural language like "page the team for the 2pm" or "start the checklist for the gallbladder case". It carries the WHO Surgical Safety Checklist, a paging ladder that tracks each recipient from sent to acknowledged and escalates to a voice note and a call when a page goes unacknowledged, and the instrument second-count: before and after tray photos that Claude vision catalogues and a deterministic diff compares, flagging anything unaccounted for and escalating to the surgeon with an audit PDF. The manual WHO count stays the authority. Patients get plain pre-op instructions and a post-op check-in; a danger sign is escalated to a clinician and never diagnosed or reassured. A coordinator dashboard shows the board, the paging ladder, the instrument audit, conversations and the follow-up queue.

## How we built it

**Serverless topology (one SAM stack).** Three Python 3.12 Lambdas share a single Lambda layer.
- `scrubbed-webhook` is subscribed to the Amazon SNS topic that AWS End User Messaging Social publishes WhatsApp events to. The event is triple-wrapped (SNS → AWS envelope → Meta entry JSON) and parsed defensively, idempotent per `wamid`, then routed: a known patient number goes to the readiness / post-op flow, everyone else to the staff app. A tray photo is pulled into S3 and sent to the vision step; a page acknowledgement is accepted even from a number that is not logged in, after verifying it is a recipient of that page.
- `scrubbed-api` sits behind an Amazon API Gateway HTTP API with a Cognito JWT authorizer, resolves the caller to a staff record by the email claim, and scopes every read and write to that staff member's hospital. `OPTIONS` is a separate unauthenticated route for CORS preflight.
- `scrubbed-scheduler` runs on Amazon EventBridge every five minutes: escalate pages past their acknowledgement deadline (computed from `createdAt` plus the horizon, not a stored timer), sweep cases at risk of cancellation and email the worklist, and send due post-op follow-ups.
- The dashboard is a React and Vite build on a private S3 bucket through CloudFront with Origin Access Control, behind Amazon Cognito.

**CDS services called at runtime** (made by the deployed Lambdas; `common/cds.py` and `agent/llm.py` are the only modules that construct the clients):
- AWS End User Messaging Social — `SendWhatsAppMessage` (text, interactive menus/buttons, audio notes, documents), `GetWhatsAppMessageMedia` (pull an inbound tray photo into S3), `PostWhatsAppMessageMedia` (stage a PDF or MP3 in S3 and send it as a document/audio).
- Amazon SES v2 — `SendEmail` for the login codes and the at-risk worklist PDF.
- AWS End User Messaging Voice — `SendVoiceMessage` for the unacknowledged-page escalation.
- Amazon Polly — `SynthesizeSpeech` for the spoken page carried as a WhatsApp voice note.
- Amazon Bedrock — `Converse` with tool use.

**Claude on Amazon Bedrock, boxed in by design.** Three model jobs, all read-and-route, through forced tool use on the `us.` inference profiles. Claude Sonnet 4.5 reads a tray photo and returns a per-instrument catalogue with a confidence per line; it never decides the final count. Claude Haiku 4.5 classifies a patient reply against a fixed danger-sign list and routes staff free text to one action and a hospital-validated case id. On any model error the classifier fails closed and escalates for a human to read, rather than silently deciding nothing is wrong. Low-confidence or unreadable tray reads are treated as "not read" and re-prompted, never stored as a count of zero.

**The deterministic safety engine (the spine).** `safety/engine.py` is pure, tested Python with no I/O. It owns readiness scoring, the cancellation-risk band (from the outstanding required items and the hours to surgery), the WHO checklist content, the danger-sign list, the page escalation threshold, and `instrument_diff`: the union of instrument names across the before and after catalogues, flagging any count that fell (a possible retained item) or rose or appeared (a discrepancy to verify). Claude reads the photo; the engine decides what it means, and every case id the model names is re-validated against the caller's hospital before anything happens.

**The paging ladder.** A page is a meta row plus one recipient row per team member. Delivery and read callbacks advance a per-recipient status that only ever moves forward, so a late receipt arriving after an acknowledgement never regresses it or re-arms escalation. When the scheduler finds a page past its deadline with unacknowledged recipients, it synthesises the page with Polly and sends it as a WhatsApp voice note, and places a voice call through End User Messaging Voice.

**The patient flow is honest.** It only acknowledges, and it escalates a danger sign, a stated inability to attend, or a question to the responsible clinician (surgeon, then the case team, then a hospital coordinator). It tells the patient the team was told only when a clinician was actually reached, and never diagnoses or reassures.

**Data model.** Ten DynamoDB tables, on-demand, with GSIs for the access patterns: staff by email and by WhatsApp number, cases by hospital and by surgeon, patients by number, the pages meta-plus-recipient rows, a per-case audit timeline with collision-safe sort keys, conversations for the 24-hour window, and the WhatsApp session/login state. PDFs (case brief, worklist, instrument audit, missed-member form) are rendered by hand-written byte-level PDF code because the layer has no pip step.

**Auth and PHI.** Login is an emailed one-time code: `secrets`-random, stored only as a salted SHA-256 hash with expiry, verified with `hmac.compare_digest`, rate-limited, single-use. No password over WhatsApp. IAM is least-privilege per function; patient numbers and message bodies are redacted from logs.

**Testing.** 186 tests on `moto` and a fake Bedrock. The safety engine is tested directly, including the instrument-appeared-after-the-case branch; the dashboard API tenancy, the OTP flow, the paging ladder, the instrument second-count and its escalation, and the scheduler's escalation timing at the real 30-minute deadline all have real assertions on real state.

## Challenges we ran into
The instrument count is safety-critical, so the model could never own it; the diff is pure tested Python and the manual WHO count stays the authority. A failed vision read had to be treated as "could not read", never as a count of zero, or the other phase would diff every item as unaccounted for. The patient flow had to be built so it can never diagnose or reassure and never claims the team was told when no clinician was reached. WhatsApp delivery callbacks arrive out of order, so the paging ladder had to be monotonic to avoid re-escalating an acknowledged page.

## Accomplishments that we're proud of
A second count that stays silent on a failed photo read instead of guessing, and escalates a real discrepancy with an audit trail and a surgeon page. A fail-closed classifier. A patient flow that is honest about whether a human was reached. A deterministic engine that owns every count and escalation, one SAM stack with per-function least-privilege IAM, and 186 tests.

## What we learned
In a safety product the boundary is everything. A deterministic, tested engine has to own the counts and the rules; the model only reads a tray photo or a patient message and routes it, and its output is validated and re-scoped to the caller before it touches the record.

## What's next for Scrubbed
Provision a voice origination number so the escalation places a real call rather than the voice note alone, add WhatsApp message templates for first contact outside the 24-hour window, and run more than one hospital at a time.

## Built with
AWS Lambda, Amazon DynamoDB, Amazon API Gateway (HTTP API), Amazon Cognito, Amazon SNS, Amazon EventBridge, Amazon S3, Amazon CloudFront, AWS SAM, Amazon Bedrock, Anthropic Claude (Sonnet 4.5, Haiku 4.5), AWS End User Messaging Social (WhatsApp), AWS End User Messaging Voice, Amazon Polly, Amazon SES v2, Python 3.12, React, Vite, TypeScript
