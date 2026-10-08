"""Static menus and the global command parser for the staff app. Role-aware.
Returns Replies via wa.messages. Contract fixed.
"""
from __future__ import annotations

from typing import Optional

from common import config
from wa import messages

# canonical global commands
START = "START"
MENU = "MENU"
MYLIST = "MYLIST"
HELP = "HELP"
LOGOUT = "LOGOUT"

# text -> command. Keys are compared against the lowercased, stripped message.
_WORDS = {
    "start": START, "/start": START, "hi": START, "hello": START, "hey": START,
    "menu": MENU, "/menu": MENU, "main menu": MENU, "home": MENU,
    "show menu": MENU, "show me menu": MENU, "show me the menu": MENU, "options": MENU,
    "mylist": MYLIST, "/mylist": MYLIST, "my list": MYLIST, "my cases": MYLIST,
    "list": MYLIST, "my list today": MYLIST,
    "help": HELP, "/help": HELP,
    "logout": LOGOUT, "/logout": LOGOUT, "log out": LOGOUT, "sign out": LOGOUT,
}


def parse_command(text: Optional[str]) -> Optional[str]:
    """Map free text like 'start', '/menu', 'my list' or 'log out' to a command
    constant, else None."""
    if not text:
        return None
    return _WORDS.get(text.strip().lower())


def welcome_logged_out() -> dict:
    body = (f"Welcome to {config.BRAND}, the assistant that keeps every operation on "
            "track, before and after: your list, the pre-op checklist, paging the team, "
            "patient readiness and the instrument second-count.\n\n"
            "Log in with your work email to get started.")
    return messages.buttons(body, [("login", "Log in")], header=config.BRAND)


def main_menu(staff: dict) -> dict:
    """A list menu. Everyone gets My list, Settings, Help and Log out. The surgeon's
    'My list' describes their own theatre list; a coordinator's describes the worklist."""
    role = (staff.get("role") or "").lower()
    if "surgeon" in role:
        mylist_desc = "Your cases today, with brief and checklist"
    elif "coordinator" in role or "charge" in role or "admin" in role:
        mylist_desc = "Today's worklist and readiness"
    else:
        mylist_desc = "The cases you are on today"

    rows = [
        {"id": "mylist", "title": "My list", "description": mylist_desc},
        {"id": "settings", "title": "Settings", "description": "Your linked staff details"},
        {"id": "help", "title": "Help", "description": "What I can do"},
        {"id": "logout", "title": "Log out", "description": "Unlink this number"},
    ]
    sections = [{"title": config.BRAND, "rows": rows}]
    return messages.list_message("What would you like to do?", "Open menu", sections,
                                 header=config.BRAND)


def settings_text(staff: dict) -> dict:
    """The staff member's own linked record. Self-contained; no case data."""
    name = staff.get("name") or "your account"
    role = staff.get("role")
    who = f"{name}, {role}" if role else name
    lines = [f"You're logged in as {who}."]
    if staff.get("hospitalId"):
        lines.append(f"Hospital: {staff['hospitalId']}")
    if staff.get("email"):
        lines.append(f"Work email: {staff['email']}")
    if staff.get("whatsappNumber"):
        lines.append(f"This number: {staff['whatsappNumber']}")
    lines.append("\nType LOGOUT to unlink this number.")
    return messages.text("\n".join(lines))


def help_text() -> dict:
    return messages.text(
        f"I'm {config.BRAND}. I keep your operations on track, before and after.\n\n"
        "You can just tell me what you need, like:\n"
        "• \"my list this afternoon\"\n"
        "• \"page the team for the 2pm\"\n"
        "• \"start the pre-op checklist for the gallbladder case\"\n"
        "• \"send me the case brief as a PDF\"\n\n"
        "Or anytime type:\n"
        "• MENU to open the menu\n"
        "• MY LIST for your cases\n"
        "• LOGOUT to unlink this number\n\n"
        "To log the instrument tray, start the tray check on a case and send the photo.")
