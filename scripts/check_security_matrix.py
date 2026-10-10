"""Require focused regression coverage for the Profile 1 security matrix."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]
REQUIREMENTS = {
    "tests/unit/auth/test_security.py": (
        "test_security_headers_csp_present",
        "test_security_headers_hsts_only_in_production",
        "test_cookie_flags_http_only_and_samesite",
        "test_cors_preflight_fails_closed_for_disallowed_policy",
        "test_cors_wildcard_credentials_never_reflects_origin",
        "test_csrf_does_not_exempt_trace_or_mutating_exempt_paths",
        "test_csrf_exempt_api_key_requests",
        "test_error_messages_no_secret_leakage",
        "test_jwt_rejects_algorithm_confusion_header",
        "test_jwt_issuer_and_audience_are_enforced",
        "test_jwt_previous_secret_supports_rotation",
        "test_jwt_revocation_invalidates_only_the_selected_token",
        "test_jwt_subject_revocation_invalidates_all_subject_sessions",
        "test_rate_limiter_rejects_invalid_runtime_limits",
        "test_rate_limit_ignores_unvalidated_credential_buckets",
        "test_auth_middleware_uses_configured_rotation_keys",
    ),
    "tests/unit/auth/test_websocket_security.py": (
        "test_websocket_origin_policy_is_fail_closed_in_production",
        "test_invalid_websocket_auth_cookie_does_not_create_a_principal",
    ),
    "tests/unit/cli/test_cli.py": ("test_cli_start_rejects_wildcard_proxy_trust",),
    "tests/unit/storage/test_storage_manager_security.py": (
        "test_object_keys_reject_traversal_and_ambiguous_paths",
        "test_local_adapter_applies_the_same_key_policy",
    ),
    "tests/unit/storage/test_s3_security.py": ("test_presign_expiry_is_bounded",),
    "tests/unit/storage/test_upload_limits.py": (
        "test_storage_manager_rejects_oversized_payload_before_provider_write",
    ),
    "tests/integration/test_capability_security.py": (
        "TestLocalSecretStore",
        "TestSensitiveCapabilityMatrix",
        "TestEffectAuthContext",
        "test_redact_sensitive_key",
        "TestRedactionInEngine",
    ),
    "tests/integration/test_local_objects.py": (
        "test_local_object_get_rejects_checksum_corruption",
        "test_local_object_stat_rejects_corrupt_metadata",
    ),
    "tests/integration/test_voodoo_store_objects.py": (
        "test_native_store_object_metadata_rejects_malformed_json",
        "test_native_store_object_metadata_rejects_integrity_mismatch",
        "test_native_store_object_get_rejects_payload_checksum_mismatch",
    ),
    "tests/unit/runtime/test_runtime.py": (
        "test_unauthorized_effect_cannot_execute",
        "test_effect_boundary_rechecks_capability",
    ),
    "tests/integration/test_mesh_remote_authority.py": (
        "test_network_payload_cannot_self_authorize",
        "test_remote_grant_can_be_revoked_immediately",
    ),
}


def _declared_symbols(source: str) -> set[str]:
    """Return test/class declarations, including methods on test classes.

    A substring check can be satisfied by a comment or an unrelated string.
    Parsing the source keeps this lightweight contract tied to executable
    declarations without importing a test module or triggering side effects.
    """
    tree = ast.parse(source)
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def main() -> int:
    missing: list[str] = []
    covered = 0
    for relative, markers in REQUIREMENTS.items():
        path = ROOT / relative
        if not path.is_file():
            missing.append(f"missing security test file: {relative}")
            continue
        source = path.read_text(encoding="utf-8")
        try:
            declared = _declared_symbols(source)
        except SyntaxError as error:
            missing.append(f"{relative}: security test source is invalid: {error}")
            continue
        for marker in markers:
            if marker not in declared:
                missing.append(
                    f"{relative}: missing focused regression declaration {marker}"
                )
            else:
                covered += 1
    if missing:
        raise SystemExit("security matrix contract failed:\n- " + "\n- ".join(missing))
    print(f"security matrix contract passed ({covered} focused declarations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
