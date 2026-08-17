#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import SITE

TEMPLATE = SITE / "index.html"
OUT = SITE / "search.html"

template = TEMPLATE.read_text(encoding="utf-8")

card = """
<div class="card">
<p><a href="/">← Back</a></p>
<h2>Search</h2>
<p class="small">Search artists, albums, genres, and WEFUNK episodes.</p>

<input id="unifiedSearch" placeholder="Search everything..." oninput="doUnifiedSearch()" autofocus>

<div id="unifiedResults" style="margin-top:20px;"></div>
</div>

<script>
let unifiedData = [];

fetch('/search-index.json')
  .then(r => r.json())
  .then(j => unifiedData = j);

function doUnifiedSearch(){
  const q = document.getElementById('unifiedSearch').value.toLowerCase().trim();
  const box = document.getElementById('unifiedResults');

  if(q.length < 2){
    box.innerHTML = '';
    return;
  }

  const hits = unifiedData.filter(x =>
    (x.title || '').toLowerCase().includes(q) ||
    (x.type || '').toLowerCase().includes(q)
  ).slice(0, 100);

  const groups = {};

  hits.forEach(x => {
    const type = x.type || 'other';
    if(!groups[type]) groups[type] = [];
    groups[type].push(x);
  });

  box.innerHTML = Object.keys(groups).map(type => {
    return `
      <h3 style="margin-top:22px;text-transform:capitalize;">
${type}s (${groups[type].length})
</h3>
      <table>
        <thead><tr><th>Result</th></tr></thead>
        <tbody>
          ${groups[type].map(x =>
            `<tr><td><a href="${x.url}">${x.title}</a></td></tr>`
          ).join('')}
        </tbody>
      </table>
    `;
  }).join('');
}
</script>
"""

start = template.find('<div class="card">')
end = template.rfind("</body>")

page = template[:start] + card + "\n" + template[end:]

OUT.write_text(page, encoding="utf-8")

print(f"Wrote: {OUT}")
