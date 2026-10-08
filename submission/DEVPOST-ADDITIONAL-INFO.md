# Scrubbed — Devpost "Additional info" (for judges and organizers)

Scrubbed is the SECOND CDS entry. As a distinct submission it needs its OWN ACE opportunity, its OWN corporate email on its APN-registered domain, and its OWN public repo (per the one-entry-per-account rule). Decide the entity/account before submitting.

**AWS Partner Company Name**
Brownshift Technologies — unless you register/submit this entry under a separate entity. (We build and demo on Brownshift's WABA; the submission entity is yours to decide.)

**AWS Partner Headquarter Country**
Ghana

**Which CDS service(s) does your solution use?** (RCS / WhatsApp / SMS / SES)
Select: **WhatsApp** and **SES**.
NOTE: the form only lists RCS / WhatsApp / SMS / SES — it does NOT list Voice. Scrubbed also uses **AWS End User Messaging Voice** (SendVoiceMessage) for the call-page escalation, but since Voice is not a selectable option, the two qualifying CDS services for this form are WhatsApp and SES. We describe the voice call in the write-up as an additional built channel. (Scrubbed qualifies cleanly on WhatsApp + SES alone.)

**Did you use AWS End User Messaging Social (WhatsApp) as the sole CDS service or one of multiple?**
**One of multiple AWS CDS services** (WhatsApp + SES, plus End User Messaging Voice for the escalation).

**Describe how AWS End User Messaging Social (EUM - WhatsApp) was used.**
Scrubbed is a perioperative coordination agent that a surgical team runs from WhatsApp, and End User Messaging Social carries all of it. The team is paged over WhatsApp with text, interactive Acknowledge buttons, and a spoken audio note (an MP3 synthesised with Amazon Polly, uploaded via PostWhatsAppMessageMedia and sent as a WhatsApp audio message); each page is tracked per recipient for delivery, read and acknowledgement. Surgeons check their list, read the case brief and run the pre-op safety checklist in chat. For the instrument second-count, the scrub nurse sends a photo of the tray before and after the case; the webhook Lambda pulls each photo with GetWhatsAppMessageMedia, Claude vision on Bedrock catalogues it, and a deterministic compare flags anything unaccounted for. Case briefs and the instrument-count audit go out as WhatsApp documents (PostWhatsAppMessageMedia). Patients receive pre-op instructions and post-op follow-up on WhatsApp, and a missed team member is sent a form to fill and upload back. Every call is made at runtime by the deployed Lambdas (services/layer/python/common/cds.py). SES sends the coordinator worklist and the login codes; End User Messaging Voice places the call-page escalation when a member does not acknowledge in time.

**Code Repository Access**
PENDING. Push `scrubbed/` to its own public repo (MIT visible in About), separate from Arrearo's.

**Architecture Diagram**
PENDING. (Will be generated for Scrubbed like Arrearo's.)

**ACE Opportunity ID**
PENDING. Create a SECOND net-new ACE opportunity, tagged `AWS CDS Agentic AI Hackathon -Sept. 2026`, distinct from Arrearo's. Record the Opportunity ID.

**Country of residence**
Ghana.

**Entrant / corporate email**
PENDING. Its own corporate email on the APN-registered domain for this entry (not the same one as Arrearo, if submitting as separate entries).

**Confirmations**
Age of majority: yes. No conflict of interest: yes (only tick if true).
