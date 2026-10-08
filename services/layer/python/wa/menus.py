"""Static menus and the global command parser for the staff app. Role-aware.
Returns Replies via wa.messages. Contract fixed.
"""
from __future__ import annotations

from typing import Optional

START = "START"
MENU = "MENU"
MYLIST = "MYLIST"
HELP = "HELP"
LOGOUT = "LOGOUT"


def parse_command(text: Optional[str]) -> Optional[str]: raise NotImplementedError
def welcome_logged_out() -> dict: raise NotImplementedError
def main_menu(staff: dict) -> dict: raise NotImplementedError
def help_text() -> dict: raise NotImplementedError
