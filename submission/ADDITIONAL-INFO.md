# Scrubbed — Additional information (Devpost)

Paste into the Devpost "Additional info" / eligibility fields as needed.

## AWS CDS services used (the hackathon requirement)
Made by the deployed Lambdas at runtime, not by a script:
- **AWS End User Messaging Social (WhatsApp)** — `SendWhatsAppMessage` (text, interactive menus/buttons, audio notes, documents), `GetWhatsAppMessageMedia` (inbound tray photos into S3), `PostWhatsAppMessageMedia` (send a PDF or MP3 as a document/audio).
- **Amazon SES v2** — `SendEmail` for login one-time codes and the at-risk worklist PDF.
- **AWS End User Messaging Voice** — `SendVoiceMessage` for the unacknowledged-page escalation call.
- **Amazon Polly** — `SynthesizeSpeech` for the spoken page carried as a WhatsApp voice note.

## Other AWS services
Amazon Bedrock (Anthropic Claude Sonnet 4.5 for tray vision + Haiku 4.5 for classify/route), AWS Lambda, Amazon DynamoDB (10 tables), Amazon API Gateway (HTTP API), Amazon Cognito, Amazon SNS, Amazon EventBridge, Amazon S3, Amazon CloudFront, AWS SAM. One stack, region us-east-1.

## How to test it (for judges)
- **Live dashboard:** https://d3m2lk7yv7pxks.cloudfront.net — opens straight to the coordinator board (case board, case detail with the instrument second-count audit, the paging ladder, conversations, forms, follow-up queue).
- **Live API:** https://yu3kfw3x0a.execute-api.us-east-1.amazonaws.com
- **WhatsApp:** message the agent number from the submission, tap **Log in**, use the demo email; a one-time code is emailed, then: My list → open a case → run the WHO checklist, page the team (and acknowledge), and the instrument tray check by sending a before photo then an after photo (a mismatch escalates to the surgeon with an audit PDF).
- **Repo:** https://github.com/jo2980958-hub/scrubbed — `pytest services/tests` runs 186 tests (moto for DynamoDB, a fake Bedrock for the agent logic; the safety engine, API tenancy, OTP, paging ladder, instrument second-count and scheduler timing all have real assertions).

## AI tools disclosure
- **At runtime,** Claude on Amazon Bedrock reads tray photos (Sonnet 4.5) and classifies patient replies and routes staff messages (Haiku 4.5), always through forced tool use. Claude never makes a clinical or safety decision, never produces the instrument count, and never writes to the record directly. A deterministic, tested safety engine owns every rule, count and escalation, and validates everything the model returns, re-scoping any case to the caller's hospital.
- **At build time,** the codebase was written with AI assistance (Claude Code) under human direction. A person set the product, made the decisions, and reviewed and deployed the result.

## Notes for judges
- The instrument check is a **second count**: Claude catalogues the photo, a deterministic diff compares the before and after, and the manual WHO count stays the authority. A failed photo read is treated as "could not read" and re-prompted, never stored as a count of zero. The classifier fails closed on a model error (escalate for a human).
- The patient flow only acknowledges and escalates; it never diagnoses or reassures, and only tells a patient the team was told when a clinician was actually reached.
- `SendMode` defaults to dry; the deployed stack runs live. SES is in sandbox (login codes reach the verified domain). No voice origination number is provisioned yet, so the escalation call logs and the WhatsApp voice note is primary; the call path is built and disclosed.

## Licence
MIT (see LICENSE in the repo).
