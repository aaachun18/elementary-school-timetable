"""帳號改版: the initial password of a new account (sent by mail).

Plain function, no FastAPI / database: easy to test on its own."""

import secrets

INITIAL_PASSWORD_LENGTH = 8
# Letters and digits without the easily confused 0/O, 1/l/I.
_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_DIGITS = "23456789"
_ALPHABET = _LETTERS + _DIGITS


def generate_initial_password(length: int = INITIAL_PASSWORD_LENGTH) -> str:
    """A random password of `length` characters with at least one letter
    and one digit (meets the shared Password rule: 8+ characters)."""
    while True:
        password = "".join(secrets.choice(_ALPHABET) for _ in range(length))
        has_letter = any(char in _LETTERS for char in password)
        has_digit = any(char in _DIGITS for char in password)
        if has_letter and has_digit:
            return password
