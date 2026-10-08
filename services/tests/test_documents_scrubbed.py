"""The four Scrubbed documents render to real PDFs with the right content on the page.
Mirrors the arrearo test_documents.py style: assert the bytes are a PDF, then decode
latin-1 and look for the strings that must appear.
"""
from common import documents
from safety import engine


def _is_pdf(blob: bytes) -> str:
    assert isinstance(blob, bytes)
    assert blob.startswith(b"%PDF")
    assert blob.rstrip().endswith(b"%%EOF")
    return blob.decode("latin-1")


def _team():
    return [
        {"name": "Dr Ada Lovelace", "role": "surgeon"},
        {"name": "Grace Hopper", "role": "scrub nurse"},
        {"name": "Alan Turing", "role": "anaesthetist"},
    ]


def _case():
    return {"procedure": "Laparoscopic cholecystectomy", "theatre": "Theatre 2",
            "scheduledAt": "2026-10-09T14:00:00Z",
            "readiness": {"doneCount": 4, "total": 6, "isReady": False,
                          "outstandingRequired": ["Consent signed", "Balance cleared"]}}


def _patient():
    return {"name": "John Doe"}


def test_case_brief_pdf_has_procedure_team_and_checklist():
    text = _is_pdf(documents.case_brief_pdf(_case(), _team(), _patient()))
    assert "CASE BRIEF" in text
    assert "Laparoscopic cholecystectomy" in text
    assert "Theatre 2" in text
    assert "09 Oct 2026, 14:00" in text          # scheduled time, formatted
    assert "John Doe" in text                     # patient
    assert "Grace Hopper" in text                 # a team member name
    assert "scrub nurse" in text                  # and their role
    assert "Not ready." in text                   # readiness summary line
    assert "Consent signed" in text               # an outstanding item
    # the WHO sign-in and time-out items are listed verbatim
    assert "Anaesthesia safety check complete" in text
    assert engine.CHECKLIST["time_out"][0] in text


def test_case_brief_pdf_ready_case_and_raw_status():
    case = {"procedure": "Hernia repair", "theatre": "Theatre 1",
            "scheduledAt": "2026-10-09T09:30:00Z",
            "readinessStatus": {k: True for k, _, _ in engine.READINESS_ITEMS}}
    text = _is_pdf(documents.case_brief_pdf(case, _team(), _patient()))
    assert "Hernia repair" in text
    assert "Ready." in text                       # engine scored the raw status as ready


def test_case_brief_pdf_no_team():
    text = _is_pdf(documents.case_brief_pdf(_case(), [], _patient()))
    assert "No team assigned." in text


def test_worklist_pdf_lists_cases_with_risk():
    hospital = {"name": "St Jude Teaching Hospital"}
    cases = [
        {"theatre": "Theatre 2", "scheduledAt": "2026-10-09T14:00:00Z",
         "patientName": "John Doe", "procedure": "Hernia repair",
         "readiness": {"doneCount": 4, "total": 6}, "risk": "high"},
        {"theatre": "Theatre 1", "scheduledAt": "2026-10-09T09:30:00Z",
         "patient": {"name": "Jane Roe"}, "procedure": "Cataract",
         "readiness": {"doneCount": 6, "total": 6}, "cancellationRisk": "low"},
    ]
    text = _is_pdf(documents.worklist_pdf(hospital, cases))
    assert "THEATRE WORKLIST" in text
    assert "St Jude Teaching Hospital" in text
    assert "Theatre 2" in text
    assert "14:00" in text                         # time of day in the dense table
    assert "John Doe" in text
    assert "Jane Roe" in text                       # patient read from the nested dict
    assert "high" in text and "low" in text         # risk per row
    assert "4/6" in text                            # readiness as done/total


def test_worklist_pdf_empty():
    text = _is_pdf(documents.worklist_pdf({"name": "St Jude"}, []))
    assert "No cases." in text


def test_instrument_audit_pdf_flags_discrepancy():
    case = {"procedure": "Laparoscopic cholecystectomy", "theatre": "Theatre 2",
            "scheduledAt": "2026-10-09T14:00:00Z"}
    before = {"artery forceps": 6, "scalpel handle": 2, "clamp": 2, "swab": 10}
    after = {"artery forceps": 6, "scalpel handle": 2, "clamp": 1, "swab": 10}
    diff = engine.instrument_diff(before, after)
    assert not diff["ok"]
    text = _is_pdf(documents.instrument_audit_pdf(case, before, after, diff))
    assert "INSTRUMENT SECOND COUNT" in text
    assert "Laparoscopic cholecystectomy" in text
    assert "artery forceps" in text                 # a before/after instrument name
    assert "scalpel handle" in text
    assert "unaccounted for after the case" in text  # the flag message from the diff
    # the one claim the product is careful about
    assert "A second check only." in text
    assert "manual WHO surgical count is the authority." in text


def test_instrument_audit_pdf_clean_count():
    case = {"procedure": "Hernia repair", "theatre": "Theatre 1"}
    before = {"clamp": 2, "swab": 8}
    after = {"clamp": 2, "swab": 8}
    diff = engine.instrument_diff(before, after)
    text = _is_pdf(documents.instrument_audit_pdf(case, before, after, diff))
    assert "No discrepancies flagged." in text
    assert "manual WHO surgical count is the authority." in text


def test_missed_form_pdf_is_a_fillable_form():
    case = {"procedure": "Laparoscopic cholecystectomy", "theatre": "Theatre 2",
            "scheduledAt": "2026-10-09T14:00:00Z"}
    staff = {"name": "Grace Hopper", "role": "scrub nurse"}
    text = _is_pdf(documents.missed_form_pdf(case, staff, "page_missed"))
    assert "TEAM FOLLOW-UP FORM" in text
    assert "Laparoscopic cholecystectomy" in text    # the case
    assert "Grace Hopper" in text                     # the team member
    assert "scrub nurse" in text
    assert "Can you attend?" in text                  # a labelled blank line (parens are PDF-escaped)
    assert "Signature" in text
    assert "WhatsApp" in text                          # how to send it back


def test_all_four_build_plain_dicts():
    # Each renderer accepts plain dicts and makes a non-trivial PDF.
    blobs = [
        documents.case_brief_pdf(_case(), _team(), _patient()),
        documents.worklist_pdf({"name": "St Jude"}, []),
        documents.instrument_audit_pdf(_case(), {"clamp": 2}, {"clamp": 2},
                                       engine.instrument_diff({"clamp": 2}, {"clamp": 2})),
        documents.missed_form_pdf(_case(), {"name": "Alan Turing", "role": "ODP"}, "handover"),
    ]
    for blob in blobs:
        _is_pdf(blob)
        assert len(blob) > 800
