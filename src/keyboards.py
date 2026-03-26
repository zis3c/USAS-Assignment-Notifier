from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton


def main_menu() -> ReplyKeyboardMarkup:
    """Standard user menu."""
    return ReplyKeyboardMarkup(
        [
            ["Check Now", "Status"],
            ["Register", "Help"],
            ["Logout"],
        ],
        resize_keyboard=True,
        input_field_placeholder="Choose an action…",
    )


def help_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for the Help message."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("How it works?", callback_data="how_it_works")]]
    )


def back_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for the Detail message."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Back", callback_data="help_back")]]
    )


def admin_menu() -> ReplyKeyboardMarkup:
    """Admin-only dashboard menu."""
    return ReplyKeyboardMarkup(
        [
            ["User Stats", "User List"],
            ["Poll All Now", "View Logs"],
            ["Broadcast", "Find User"],
            ["Ban/Unban", "Backup DB"],
            ["Maint. Mode", "Server Performance"],
            ["Main Menu"],
        ],
        resize_keyboard=True,
        input_field_placeholder="Admin Tools…",
    )


def confirmation_keyboard() -> ReplyKeyboardMarkup:
    """Yes/No keyboard for confirmations."""
    return ReplyKeyboardMarkup(
        [["Confirm Sending", "Cancel"]],
        resize_keyboard=True,
    )
def cancel_menu() -> ReplyKeyboardMarkup:
    """Simple 'Cancel' menu for conversation flows."""
    return ReplyKeyboardMarkup(
        [["Cancel"]],
        resize_keyboard=True,
    )
def confirm_menu() -> ReplyKeyboardMarkup:
    """Confirmation menu for logout."""
    return ReplyKeyboardMarkup(
        [["Logout", "Cancel"]],
        resize_keyboard=True,
    )
