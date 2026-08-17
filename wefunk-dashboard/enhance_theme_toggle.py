#!/usr/bin/env python3

import os
import re
from pathlib import Path

SITE = Path(os.environ.get("WEFUNK_SITE_DIR", str(Path(__file__).resolve().parents[1] / "site")))

updated = 0

for path in SITE.rglob("*.html"):
    html = path.read_text(encoding="utf-8")

    html = re.sub(
        r'<style>\s*\.theme-toggle.*?</style>',
        '',
        html,
        flags=re.S
    )

    html = re.sub(
        r'<button class="theme-toggle".*?</script>',
        '',
        html,
        flags=re.S
    )

    html = html.replace('class="light-mode"', '')
    html = html.replace("class='light-mode'", "")

    path.write_text(html, encoding="utf-8")
    updated += 1

print(f"Removed theme toggle from {updated} pages")
