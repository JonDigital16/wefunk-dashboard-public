#!/usr/bin/env python3

import os
from pathlib import Path

SITE = Path(os.environ.get("WEFUNK_SITE_DIR", str(Path(__file__).resolve().parents[1] / "site")))

CSS = """
<style>
.back-to-top{
  position:fixed;
  right:18px;
  bottom:18px;
  z-index:1800;
  display:none;
  width:46px;
  height:46px;
  border-radius:999px;
  border:1px solid #2b2f36;
  background:#F7931E;
  color:#111;
  font-size:22px;
  font-weight:900;
  cursor:pointer;
  box-shadow:0 10px 30px rgba(0,0,0,.35);
}

.back-to-top:hover{
  transform:translateY(-2px);
}
</style>
"""

JS = """
<button class="back-to-top" id="backToTop" onclick="window.scrollTo({top:0,behavior:'smooth'})">↑</button>

<script>
window.addEventListener('scroll', function(){
  const btn = document.getElementById('backToTop');
  if(!btn) return;
  btn.style.display = window.scrollY > 600 ? 'block' : 'none';
});
</script>
"""

updated = 0

for path in SITE.rglob("*.html"):
    html = path.read_text(encoding="utf-8")

    if "backToTop" in html:
        continue

    html = html.replace("</head>", CSS + "\n</head>", 1)
    html = html.replace("</body>", JS + "\n</body>", 1)

    path.write_text(html, encoding="utf-8")
    updated += 1

print(f"Added Back to Top button to {updated} pages")
