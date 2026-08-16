import hashlib
import secrets

from voodoo.config import config

# =========================================================================
# Cryptographic Password Hashing (Zero-dependency PBKDF2-HMAC-SHA256)
# =========================================================================


def hash_password(
    password: str, salt: str | None = None, iterations: int = 600_000
) -> str:
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with 600,000 iterations (OWASP standard).
    Format: pbkdf2_sha256$<iterations>$<salt>$<hex_hash>
    """
    if salt is None:
        salt = secrets.token_hex(16)

    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    hash_hex = dk.hex()
    return f"pbkdf2_sha256${iterations}${salt}${hash_hex}"


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against a PBKDF2-HMAC-SHA256 hash using constant-time comparison.
    """
    if not hashed_password or not isinstance(hashed_password, str):
        return False

    parts = hashed_password.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return False

    try:
        iterations = int(parts[1])
        salt = parts[2]
        expected_hash = parts[3]
    except (ValueError, IndexError):
        return False

    computed_dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    computed_hex = computed_dk.hex()
    return secrets.compare_digest(computed_hex, expected_hash)


# =========================================================================
# API Key Management (Prefix + High-Entropy Random + SHA256 Hash)
# =========================================================================


def generate_api_key(prefix: str | None = None) -> tuple[str, str]:
    """
    Generates a secure API key with prefix and its SHA-256 hash.
    Returns: (raw_key, key_hash)
    Example: ("vd_live_4a89fb...", "c59600a7...")
    """
    pref = prefix or config.auth.api_key_prefix
    random_part = secrets.token_urlsafe(32)
    raw_key = f"{pref}_{random_part}"
    key_hash = hash_api_key(raw_key)
    return raw_key, key_hash


def hash_api_key(api_key: str) -> str:
    """Computes deterministic SHA-256 hash of an API key for safe database storage."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def verify_api_key(api_key: str, key_hash: str) -> bool:
    """Constant-time verification of an API key against stored hash."""
    if not api_key or not key_hash:
        return False
    computed_hash = hash_api_key(api_key)
    return secrets.compare_digest(computed_hash, key_hash)


def generate_secret_key(length: int = 32) -> str:
    """Generates a cryptographically strong random hex secret key."""
    return secrets.token_hex(length)
