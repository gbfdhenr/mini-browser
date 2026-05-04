#!/usr/bin/env python3
"""Helper script to extract translatable strings and update .po files.

Usage:
    # Generate .pot template from source
    python3 tools/update-translations.py extract

    # Create a new language (e.g., Japanese)
    python3 tools/update-translations.py init ja_JP

    # Update all .po files after source changes
    python3 tools/update-translations.py update

    # Compile all .po to .mo
    python3 tools/update-translations.py compile
"""

import os
import re
import sys
import subprocess
import shutil

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_FILE = os.path.join(PROJECT_DIR, "mini-browser.py")
LOCALE_DIR = os.path.join(PROJECT_DIR, "locale")
DOMAIN = "mini-browser"


def extract_strings() -> list[str]:
    """Extract all _('...') strings from the source file."""
    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    strings = set()
    for m in re.finditer(r"""_\('([^']*)'\)""", content):
        strings.add(m.group(1))
    for m in re.finditer(r'''_\('([^']*)'\)''', content):
        strings.add(m.group(1))
    return sorted(strings)


def generate_pot():
    """Generate a .pot template file."""
    strings = extract_strings()
    pot_path = os.path.join(LOCALE_DIR, f"{DOMAIN}.pot")

    lines = [
        r'msgid ""',
        'msgstr ""',
        f'"Project-Id-Version: MiniBrowser 1.0\\n"',
        '"POT-Creation-Date: \\n"',
        '"MIME-Version: 1.0\\n"',
        '"Content-Type: text/plain; charset=UTF-8\\n"',
        '"Content-Transfer-Encoding: 8bit\\n"',
        "",
    ]

    for s in strings:
        # Escape special characters
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'msgid "{escaped}"')
        lines.append('msgstr ""')
        lines.append("")

    with open(pot_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[OK] Generated {pot_path} ({len(strings)} strings)")


def init_language(lang_code: str):
    """Create a new .po file for a language."""
    strings = extract_strings()
    po_dir = os.path.join(LOCALE_DIR, lang_code, "LC_MESSAGES")
    os.makedirs(po_dir, exist_ok=True)
    po_path = os.path.join(po_dir, f"{DOMAIN}.po")

    if os.path.exists(po_path):
        print(f"[!] {po_path} already exists, use 'update' instead")
        return

    lines = [
        f'# {lang_code} translation for MiniBrowser.',
        '# Copyright (C) 2026 MiniBrowser',
        '#',
        'msgid ""',
        'msgstr ""',
        f'"Project-Id-Version: MiniBrowser 1.0\\n"',
        '"POT-Creation-Date: \\n"',
        f'"Language: {lang_code}\\n"',
        '"MIME-Version: 1.0\\n"',
        '"Content-Type: text/plain; charset=UTF-8\\n"',
        '"Content-Transfer-Encoding: 8bit\\n"',
        "",
    ]

    for s in strings:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'msgid "{escaped}"')
        lines.append('msgstr ""')
        lines.append("")

    with open(po_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[OK] Created {po_path} ({len(strings)} strings)")
    print(f"[*] Edit the file and fill in the translations, then run 'compile'")


def compile_all():
    """Compile all .po files to .mo."""
    count = 0
    for root, dirs, files in os.walk(LOCALE_DIR):
        for f in files:
            if f.endswith(".po"):
                po_path = os.path.join(root, f)
                mo_path = po_path[:-3] + ".mo"
                try:
                    subprocess.run(
                        ["msgfmt", po_path, "-o", mo_path],
                        check=True, capture_output=True
                    )
                    print(f"[OK] {po_path} -> {mo_path}")
                    count += 1
                except subprocess.CalledProcessError as e:
                    print(f"[ERR] {po_path}: {e.stderr.decode().strip()}")
                except FileNotFoundError:
                    print("[ERR] msgfmt not found. Install gettext.")
                    return
    print(f"\nCompiled {count} .po file(s)")


def update_all():
    """Update all .po files with new strings (in-place)."""
    # Regenerate .pot first
    generate_pot()
    pot_path = os.path.join(LOCALE_DIR, f"{DOMAIN}.pot")

    for root, dirs, files in os.walk(LOCALE_DIR):
        for f in files:
            if f.endswith(".po"):
                po_path = os.path.join(root, f)
                rel_path = os.path.relpath(po_path, PROJECT_DIR)
                try:
                    subprocess.run(
                        ["msgmerge", "--update", po_path, pot_path],
                        check=True, capture_output=True
                    )
                    print(f"[OK] Updated {rel_path}")
                except subprocess.CalledProcessError as e:
                    print(f"[ERR] {rel_path}: {e.stderr.decode().strip()}")
                except FileNotFoundError:
                    print("[ERR] msgmerge not found. Install gettext.")
                    return


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "extract":
        generate_pot()
    elif command == "init":
        if len(sys.argv) < 3:
            print("Usage: python3 tools/update-translations.py init <lang_code>")
            print("Example: python3 tools/update-translations.py init ja_JP")
            sys.exit(1)
        init_language(sys.argv[2])
    elif command == "update":
        update_all()
    elif command == "compile":
        compile_all()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)
