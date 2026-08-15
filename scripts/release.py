#!/usr/bin/env python3
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = val


load_env_file(ROOT_DIR / ".env")


def run(cmd: list[str] | str, check: bool = True, shell: bool = False) -> str:
    print(f"➜ Running: {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
    res = subprocess.run(
        cmd, check=check, text=True, capture_output=True, shell=shell, cwd=ROOT_DIR
    )
    if res.stdout:
        print(res.stdout.strip())
    if res.stderr and res.returncode != 0:
        print(res.stderr.strip(), file=sys.stderr)
    return res.stdout.strip()


def calculate_sha256(file_path: Path) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def update_file(path: Path, pattern: str, replacement: str) -> None:
    content = path.read_text(encoding="utf-8")
    new_content = re.sub(pattern, replacement, content)
    if content == new_content:
        print(f"Warning: pattern '{pattern}' not replaced in {path.name}")
    path.write_text(new_content, encoding="utf-8")
    print(f"✓ Updated {path.name}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: just release <version> (e.g., just release 1.0.20)")
        sys.exit(1)

    version = sys.argv[1].lstrip("v")
    print(f"\n🚀 Preparing Release v{version} for Voodoo Framework...\n")

    # 1. Run tests
    print("🧪 Running test suite...")
    run(["uv", "run", "pytest"])

    # 2. Bump versions
    print("\n📝 Updating version numbers...")
    update_file(
        ROOT_DIR / "pyproject.toml", r'version\s*=\s*"[^"]+"', f'version = "{version}"'
    )
    update_file(
        ROOT_DIR / "voodoo" / "__init__.py",
        r'__version__\s*=\s*"[^"]+"',
        f'__version__ = "{version}"',
    )
    update_file(
        ROOT_DIR / "voodoo" / "cli.py",
        r'ver = getattr\(voodoo, "__version__", "[^"]+"\)',
        f'ver = getattr(voodoo, "__version__", "{version}")',
    )

    # 3. Clean old builds
    dist_dir = ROOT_DIR / "dist"
    if dist_dir.exists():
        import shutil

        shutil.rmtree(dist_dir)

    # 4. Build package
    print("\n📦 Building distribution packages...")
    run(["uv", "build"])

    tar_path = dist_dir / f"voodoo_framework-{version}.tar.gz"
    wheel_path = dist_dir / f"voodoo_framework-{version}-py3-none-any.whl"

    if not tar_path.exists():
        # check if tarball name differs
        tar_candidates = list(dist_dir.glob("*.tar.gz"))
        if tar_candidates:
            tar_path = tar_candidates[0]
        else:
            print("❌ Error: Distribution tarball not found!", file=sys.stderr)
            sys.exit(1)

    sha256 = calculate_sha256(tar_path)
    print(f"✓ Generated tarball: {tar_path.name}")
    print(f"✓ SHA256: {sha256}")

    # 5. Publish to PyPI
    pypi_password = os.getenv("PYPI_PASSWORD")
    if not pypi_password:
        print(
            "❌ Error: PYPI_PASSWORD not found in .env or environment.", file=sys.stderr
        )
        sys.exit(1)

    print("\n🌐 Publishing to PyPI...")
    env = os.environ.copy()
    env["UV_PUBLISH_TOKEN"] = pypi_password
    pub_res = subprocess.run(
        ["uv", "publish", "--token", pypi_password],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        env=env,
    )
    if pub_res.returncode != 0:
        print(f"Error publishing: {pub_res.stderr}", file=sys.stderr)
        sys.exit(1)
    print("✓ Successfully published to PyPI!")

    # 6. Update Homebrew Formula
    print("\n🍺 Updating Homebrew Formula in helderperez-dev/homebrew-voodoo...")
    formula_content = f"""class Voodoo < Formula
  include Language::Python::Virtualenv

  desc "Fast, Animated, AI-Powered Python Web Framework"
  homepage "https://github.com/helderperez-dev/voodoo"
  url "https://files.pythonhosted.org/packages/source/v/voodoo-framework/voodoo_framework-{version}.tar.gz"
  sha256 "{sha256}"
  license "MIT"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "Voodoo Framework CLI", shell_output("#{{bin}}/voodoo --help")
  end
end
"""
    # Fetch existing sha for formula to update via GitHub API
    try:
        get_res = run(
            [
                "gh",
                "api",
                "repos/helderperez-dev/homebrew-voodoo/contents/Formula/voodoo.rb",
                "--jq",
                ".sha",
            ]
        )
        file_sha = get_res.strip()
        import base64

        b64_content = base64.b64encode(formula_content.encode("utf-8")).decode("utf-8")
        payload = f'{{"message":"chore(release): update voodoo to {version}","content":"{b64_content}","sha":"{file_sha}"}}'
        put_cmd = "gh api --method PUT repos/helderperez-dev/homebrew-voodoo/contents/Formula/voodoo.rb --input -"
        subprocess.run(put_cmd, input=payload, text=True, check=True, shell=True)
        print(
            "✓ Homebrew formula successfully updated in helderperez-dev/homebrew-voodoo!"
        )
    except Exception as e:
        print(f"⚠️  Note on Homebrew update: {e}")

    # 7. Git commit, tag, and push
    print("\n🐙 Committing and pushing release to GitHub...")
    run(["git", "add", "-A"])
    run(["git", "commit", "-m", f"chore(release): bump version to v{version}"])
    run(["git", "push", "origin", "main"])
    run(["git", "tag", f"v{version}"])
    run(["git", "push", "origin", f"v{version}"])

    # 8. GitHub Release
    try:
        run(
            [
                "gh",
                "release",
                "create",
                f"v{version}",
                str(tar_path),
                str(wheel_path),
                "--title",
                f"v{version}",
                "--notes",
                f"Release v{version} of Voodoo Framework.",
            ]
        )
        print(f"✓ GitHub release v{version} created successfully!")
    except Exception as e:
        print(f"⚠️  Note on GitHub Release: {e}")

    print(f"\n🎉 Release v{version} completed successfully!\n")


if __name__ == "__main__":
    main()
