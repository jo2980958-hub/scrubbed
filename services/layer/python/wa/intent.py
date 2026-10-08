"""Natural-language intent for the staff app (Claude Haiku on Bedrock).

Free text that is not a tap or an expected answer is mapped to an action, answered in
words, or falls back to the menu. Claude only decides WHERE to go and WHAT was meant;
the spine owns every rule and record, and any case it names is validated against the
staff member in the router before anything happens. Contract fixed.

Claude gets the staff member's upcoming cases (id + procedure + theatre + time) as
context, so "the 2pm" or "the gallbladder case" resolves to a caseId. Any caseId it
returns is validated here against the staff member's own hospital; otherwise we fall
back to the menu. Mirrors Arrearo's tool + validation shape.
"""
from __future__ import annotations

from typing import Optional

from agent import llm
from common import config, db

ACTIONS = ["mylist", "open_case", "checklist", "page", "readiness", "brief",
           "tray", "paging", "answer", "menu", "unknown"]

ROUTE_TOOL = {"toolSpec": {
    "name": "route",
    "description": "Decide what a staff member wants to do in the Scrubbed WhatsApp app.",
    "inputSchema": {"json": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ACTIONS,
                       "description": "The single best match for the user's message."},
            "caseId": {"type": "string",
                       "description": "For open_case/checklist/page/readiness/brief/tray/paging: "
                                      "the exact caseId copied from the Cases list. Match on procedure, "
                                      "theatre, patient or time (e.g. 'the 2pm', 'the gallbladder case'). "
                                      "Never invent one."},
            "when": {"type": "string", "enum": ["today", "tomorrow"],
                     "description": "For mylist: which day, if the user said so."},
            "phase": {"type": "string",
                      "description": "For checklist: 'signin' (pre-op sign-in) or 'timeout'. "
                                     "For tray: 'before' or 'after'."},
            "item": {"type": "string",
                     "description": "For readiness: which item - one of consent, fasting, balance, "
                                    "instructions."},
            "ready": {"type": "boolean",
                      "description": "For readiness: true if the item is done/ready, false if it is "
                                     "not ready, missing or outstanding."},
            "answer": {"type": "string",
                       "description": "For action=answer: a short plain-English reply using ONLY the "
                                      "facts provided. Never state a fact that is not in the context."},
        },
        "required": ["action"],
    }},
}}

SYSTEM = (
    "You route messages in Scrubbed, a WhatsApp app a surgical team runs to keep every operation on "
    "track. Choose the single action that matches the staff member's message.\n"
    "- mylist: their list of cases (set when to today or tomorrow if they said so).\n"
    "- open_case: show one specific case. checklist: start the pre-op checklist on a case (phase "
    "signin or timeout). page: page the team for a case. brief: send the case brief as a PDF. "
    "tray: start the instrument tray check on a case (phase before or after). paging: show who has "
    "acknowledged a case's page. For any of these, copy the caseId EXACTLY from the Cases list; "
    "match on procedure, theatre, patient or time. Never invent a caseId.\n"
    "- readiness: flag a readiness item on a case (set caseId, item and ready). item is one of "
    "consent, fasting, balance, instructions; ready is false when they say it is not done, missing "
    "or outstanding (e.g. 'flag the cholecystectomy as not ready, no consent yet' -> item=consent, "
    "ready=false).\n"
    "- answer: a question you can answer from the context given; keep it to one or two short "
    "sentences and never state a fact that is not in the context.\n"
    "- menu for the menu or options; unknown when unsure.\n"
    "You only decide where to go and what was meant. You never make a safety call, never count "
    "instruments, and never confirm a readiness fact that is not in the context."
)

# The short words the model is told to use, mapped to the engine's canonical readiness
# keys (safety.engine.READINESS_ITEMS). The NL path writes through db.set_readiness_item,
# so it must store the exact engine key or engine.readiness() never reads it back.
_ITEM_KEYS = {
    "consent": "consent",
    "fasting": "fasting_confirmed",
    "balance": "balance_cleared",
    "instructions": "instructions_sent",
    "team": "team_confirmed",
    "site": "site_marked",
}


def _readiness_item(raw: Optional[str]) -> Optional[str]:
    f = (raw or "").lower()
    for word, key in _ITEM_KEYS.items():
        if word in f:
            return key
    if "fast" in f or "nil by mouth" in f or "nbm" in f:
        return "fasting_confirmed"
    if "consent" in f or "sign" in f:
        return "consent"
    if "pay" in f or "fund" in f or "balance" in f or "deposit" in f:
        return "balance_cleared"
    if "instruct" in f or "arrival" in f:
        return "instructions_sent"
    if "mark" in f:
        return "site_marked"
    return None


def _cases_for(staff: dict) -> list:
    """The cases this staff member may act on: a surgeon's own list, otherwise the
    whole hospital worklist. Same set the router validates against."""
    role = (staff.get("role") or "").lower()
    if "surgeon" in role and staff.get("staffId"):
        cases = db.list_cases_for_surgeon(staff["staffId"])
    else:
        cases = db.list_cases(staff.get("hospitalId"))
    return cases or []


def _context(staff: dict) -> str:
    lines = ["Cases:"]
    for c in _cases_for(staff)[:40]:
        procedure = c.get("procedure") or c.get("procedureCode") or "-"
        line = (f"- caseId={c.get('caseId')} | {procedure} | theatre {c.get('theatre') or '-'} | "
                f"{c.get('scheduledAt') or '-'}")
        patient = c.get("patientName") or c.get("patient")
        if patient:
            line += f" | {patient}"
        lines.append(line)
    if len(lines) == 1:
        lines.append("- (no upcoming cases)")
    return "\n".join(lines)


def resolve(text: str, staff: dict, screen: Optional[str] = None) -> dict:
    """Returns one of: {"kind":"route","tap_id":...} | {"kind":"answer","text":...}
    | {"kind":"menu"} (safe fallback). A route always carries a validated, hospital-owned
    caseId where one is needed."""
    content = [{"text": f"User said: {text}\n\nContext:\n{_context(staff)}"}]
    try:
        out = llm.converse_tool(config.BEDROCK_FAST_MODEL, SYSTEM, content, ROUTE_TOOL, max_tokens=400)
    except Exception:
        return {"kind": "menu"}

    action = out.get("action")
    hospital_id = staff.get("hospitalId")

    def owned_case() -> Optional[str]:
        case_id = out.get("caseId")
        case = db.get_case(case_id) if case_id else None
        return case_id if case and case.get("hospitalId") == hospital_id else None

    if action == "mylist":
        when = out.get("when")
        return {"kind": "route", "tap_id": f"mylist:{when}" if when else "mylist"}
    if action == "menu":
        return {"kind": "menu"}
    if action == "open_case":
        cid = owned_case()
        return {"kind": "route", "tap_id": f"case:{cid}"} if cid else {"kind": "menu"}
    if action == "checklist":
        cid = owned_case()
        # Map the tool's phase words to the engine's canonical WHO-phase keys.
        phase = {"signin": "sign_in", "timeout": "time_out"}.get((out.get("phase") or "").lower(), "sign_in")
        return {"kind": "route", "tap_id": f"check:{cid}:{phase}"} if cid else {"kind": "menu"}
    if action == "page":
        cid = owned_case()
        return {"kind": "route", "tap_id": f"page:{cid}"} if cid else {"kind": "menu"}
    if action == "brief":
        cid = owned_case()
        return {"kind": "route", "tap_id": f"brief:{cid}"} if cid else {"kind": "menu"}
    if action == "tray":
        cid = owned_case()
        phase = (out.get("phase") or "before").lower()
        phase = phase if phase in ("before", "after") else "before"
        return {"kind": "route", "tap_id": f"tray:{cid}:{phase}"} if cid else {"kind": "menu"}
    if action == "paging":
        cid = owned_case()
        return {"kind": "route", "tap_id": f"paging:{cid}"} if cid else {"kind": "menu"}
    if action == "readiness":
        cid = owned_case()
        item = _readiness_item(out.get("item"))
        if cid and item:
            value = "1" if out.get("ready") else "0"
            return {"kind": "route", "tap_id": f"ready:{cid}:{item}:{value}"}
        return {"kind": "menu"}
    if action == "answer" and out.get("answer"):
        return {"kind": "answer", "text": out["answer"]}
    return {"kind": "menu"}
