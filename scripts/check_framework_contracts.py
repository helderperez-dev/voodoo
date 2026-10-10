"""Run the Framework's static compatibility and exception contracts."""

from __future__ import annotations

from check_api_compatibility import main as check_api_compatibility
from check_exception_contract import main as check_exception_contract
from check_native_domain_inventory import main as check_native_domain_inventory


def main() -> int:
    check_exception_contract()
    check_api_compatibility()
    check_native_domain_inventory()
    print("framework contracts passed (exceptions, compatibility, native domains)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
