import re


def validate_password_strength(password: str, min_length: int = 8) -> tuple[bool, str]:
    """
    Validates that a password satisfies minimum security requirements:
    - Minimum length
    - At least one letter and at least one digit or special character
    """
    if not password or len(password) < min_length:
        return False, f"Password must be at least {min_length} characters long"

    has_letter = bool(re.search(r"[A-Za-z]", password))
    has_digit = bool(re.search(r"\d", password))
    has_symbol = bool(re.search(r"[^A-Za-z0-9]", password))

    if not has_letter:
        return False, "Password must contain at least one letter"
    if not (has_digit or has_symbol):
        return False, "Password must contain at least one number or symbol"

    return True, ""
