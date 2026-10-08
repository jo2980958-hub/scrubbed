# Scrubbed

Scrubbed is a WhatsApp-native agent that keeps a surgical case on track before and after
the operation, and does the one check a team cannot afford to get wrong: a second count of
the instrument tray. The clinical team runs it from WhatsApp; the coordinator watches it
from a dashboard. A deterministic, tested safety engine owns every rule, count and
escalation. Claude only reads photos and messages and decides where to route them. It never
makes a safety call.

Built for the AWS CDS Agentic AI Hackathon on AWS serverless (Lambda, DynamoDB, API Gateway
+ Cognito, SNS, EventBridge, S3 + CloudFront, Bedrock) and the CDS messaging services
(End User Messaging Social for WhatsApp, Amazon SES for email, End User Messaging Voice +
Amazon Polly for the voice escalation).

## The problem

Operations get cancelled or delayed on the day because readiness was never confirmed in
time: consent unsigned, patient not fasted, balance unpaid, the team not acknowledged, the
site not marked. Around the operation itself, the things that go wrong are communication
gaps (a team member who never saw the page) and counts (a retained instrument). These are
coordination failures, not clinical ones, and they happen in the messaging layer the team
already lives in.

## What it does

- **Staff WhatsApp app** — email one-time-code login (no passwords in chat), a menu, and
  natural language ("page the team for the 2pm", "start the checklist for the gallbladder
  case"). Every action is scoped to the staff member's own hospital.
- **WHO Surgical Safety Checklist** — sign-in, time-out and sign-out, ticked item by item
  in chat, recorded on the case timeline.
- **Paging ladder** — fan a page out to the case roster, track each recipient from sent to
  delivered to read to acknowledged, one-tap Acknowledge, and automatic escalation to a
  WhatsApp voice note (and a phone call when a voice number is provisioned) when a page is
  not acknowledged in time.
- **Instrument second-count** — before and after photos of the tray; Claude vision
  catalogues each; a deterministic diff flags anything unaccounted for, or a count that
  rose, and escalates to the surgeon with an audit PDF. It is a second check. The manual WHO
  count stays the authority, and the code never presents its figure as the count.
- **Patient readiness and follow-up** — plain pre-op instructions, readiness items (consent,
  fasting, balance, team, instructions, site), a cancellation-risk score, a not-ready sweep
  that emails the coordinator the day's worklist, and a post-op check-in. A patient reply is
  classified for danger signs and escalated to a clinician. It never diagnoses and never
  reassures, and it only tells the patient the team was told when a clinician was actually
  reached.
- **Coordinator dashboard** — the case board, case detail (readiness, team, patient,
  instrument audit), the paging ladder, conversations, forms and the follow-up queue.

## How it works

WhatsApp inbound arrives on an SNS topic and a **webhook** Lambda routes it: a known
patient number goes to the readiness / follow-up flow, everyone else to the staff app
(login, then menu or natural-language navigation, plus tray photos and page
acknowledgements). An **api** Lambda serves the dashboard behind a Cognito JWT authorizer,
resolving the caller to a staff record and scoping every read to their hospital. A
**scheduler** Lambda runs every five minutes: escalate pages past their acknowledgement
deadline, sweep for cases at risk of cancellation and email the worklist, and send any
post-op follow-ups that are due.

The split that matters: a deterministic **safety spine** (`services/layer/python/safety/
engine.py`) owns readiness scoring, the cancellation-risk band, the instrument diff, the WHO
checklist content, the danger-sign list and the escalation threshold. It is pure, tested
code with no model in the loop. Claude reads a tray photo or a patient message and returns
structured data through a forced tool call; the spine decides what that means, and any case
id Claude names is re-validated against the caller's hospital before anything happens.

## Architecture

```
WhatsApp  ──SNS──▶  webhook Lambda ──▶ patient flow  (readiness, follow-up, danger-sign escalation)
                                   └─▶ staff router  (login, menu, NL, checklist, paging, tray)
Dashboard ──HTTPS──▶ API Gateway (HTTP API + Cognito JWT) ──▶ api Lambda  (hospital-scoped reads/writes)
EventBridge (rate 5 min) ──▶ scheduler Lambda  (page escalation, not-ready sweep + worklist email, follow-ups)

Shared layer: safety engine, Claude agents (vision, classify, intent), db, cds, documents, wa
Storage: 10 DynamoDB tables (on-demand, GSIs) · S3 (media + the dashboard) · CloudFront
```

Three Lambdas (Python 3.12) plus a common layer; one SAM template defines all of it.

## CDS services called at runtime

| Service | Call | Used for |
|---|---|---|
| End User Messaging Social | `SendWhatsAppMessage` | text, interactive menus/buttons, audio notes, documents |
| End User Messaging Social | `GetWhatsAppMessageMedia` | pull an inbound tray photo / form into S3 |
| End User Messaging Social | `PostWhatsAppMessageMedia` | stage a PDF/MP3 in S3 to send as a WhatsApp document/audio |
| Amazon SES v2 | `SendEmail` | the login one-time code and the at-risk worklist PDF |
| End User Messaging Voice | `SendVoiceMessage` | the voice-call escalation when a page goes unacknowledged |
| Amazon Polly | `SynthesizeSpeech` | the spoken page for the WhatsApp voice note |
| Amazon Bedrock | `Converse` (tool use) | Claude reads tray photos and patient replies, and routes NL |

## How Claude is used

Three jobs, all read-and-route, never decide:

- **Vision** (`agent/vision.py`) catalogues the instruments visible in a tray photo for the
  second count. It never decides the final count.
- **Classify** (`agent/classify.py`) reads a patient reply and flags recognised danger signs
  from a fixed list. It never diagnoses and never reassures, and on a model error it fails
  closed (escalate for a human to read).
- **Intent** (`wa/intent.py`) maps free text to an app action and a hospital-validated case.

All three use forced tool use on Bedrock inference profiles (Claude Sonnet 4.5 for vision,
Claude Haiku 4.5 for classify and intent). The deterministic spine validates every output.

## The safety spine

`safety/engine.py` is pure, tested logic: `readiness` (score and whether a case is ready),
`cancellation_risk` (a band from the outstanding items and the hours to surgery),
`instrument_diff` (compare a before and after catalogue, flag unaccounted-for items and
counts that rose), the WHO checklist content, the danger-sign list, and the page escalation
threshold. No I/O, no model. It is tested directly in `test_engine.py`, including the
instrument "appeared after the case" branch that signals a possible retained item.

## The in-WhatsApp app

A full app in the chat: one-time-code login that links a number to a staff record; a menu
and natural-language control; the day's list; a case screen with the checklist, paging, the
case-brief PDF and the tray check; the tray second-count by photo; and designed PDFs sent as
WhatsApp documents. A paged recipient can acknowledge even without logging in.

## Documents

Pure-Python PDF rendering (no third-party dependency, so the Lambda layer stays a plain
copy): the case brief, the theatre worklist, the instrument second-count audit, and the
missed-member follow-up form.

## Data model

Ten DynamoDB tables (on-demand), keyed and indexed for the access patterns above: staff
(by email, by WhatsApp number), cases (by hospital, by surgeon), patients (by WhatsApp
number), trays, readiness, pages (meta row + one recipient row each), forms, the per-case
audit events timeline, conversations (every message in and out), and the WhatsApp session /
login state.

## Testing

```
cd scrubbed && .venv/bin/python -m pytest services/tests -q
```

186 tests on pytest + moto (mocked DynamoDB): the safety engine directly, the WhatsApp app
end to end through the real router, auth, the paging ladder, the instrument second-count and
its escalation, the dashboard API's hospital tenancy, and the scheduler's escalation timing
at the real deadline.

## Deploy

```
# backend: build and deploy the stack (sends stay dry)
cd scrubbed/infra && ./deploy.sh
# turn real WhatsApp, SES and voice sends on
./deploy.sh SendMode=live SesSender=billing@brownshift.com
# seed a demo hospital, team, patient and theatre list
cd .. && .venv/bin/python infra/seed.py
# dashboard: build, sync to the web bucket, invalidate CloudFront
cd web && npm run build && aws s3 sync dist/ s3://<WebBucket>/ --delete \
  && aws cloudfront create-invalidation --distribution-id <id> --paths '/*'
```

## Known limitations

- No voice origination number is provisioned yet, so the voice-call escalation logs and
  falls back; the WhatsApp voice note is the primary escalation and the call path is built
  and disclosed.
- The demo reuses one shared WhatsApp business number, so one hospital at a time runs live.
- Amazon SES is in sandbox for the demo account; the login code reaches addresses in the
  verified sending domain.

## AI disclosure

Claude (on Amazon Bedrock) reads tray photos and patient messages and routes natural
language. It never makes a clinical or safety decision, never produces the instrument count,
and never writes to the record directly. The deterministic engine owns every rule, count and
escalation, and validates everything Claude returns. This codebase was built with AI
assistance.

## Repository layout

```
infra/       SAM template, deploy script, seed
services/    functions (webhook, api, scheduler), layer (safety, agent, common, wa), tests
web/         React + Vite coordinator dashboard
```

## Licence

MIT. See [LICENSE](LICENSE).
