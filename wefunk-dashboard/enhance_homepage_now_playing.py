#!/usr/bin/env python3

import os
from pathlib import Path

SITE = Path(os.environ.get("WEFUNK_SITE_DIR", str(Path(__file__).resolve().parents[1] / "site")))

INDEX = SITE / "index.html"

if not INDEX.exists():
    raise SystemExit("index.html does not exist.")

html = INDEX.read_text(encoding="utf-8")

if "liveNowPlayingCard" in html:
    print("Live Now Playing card already present")
    raise SystemExit(0)

card = """
<div class="card now-playing-card" id="liveNowPlayingCard">
  <h2>🎵 Now Playing</h2>
  <div id="nowPlayingContent">
    <p class="small">Loading Navidrome status...</p>
  </div>
</div>
"""

css = """
<style>
.now-playing-layout{display:flex;gap:20px;align-items:center;flex-wrap:wrap}
.now-playing-layout img{width:150px;height:150px;object-fit:cover;border-radius:18px;box-shadow:0 12px 40px rgba(0,0,0,.35)}
.now-playing-title{font-size:28px;font-weight:900;line-height:1.15;margin-bottom:8px}
.now-playing-artist{color:#F7931E;font-size:18px;font-weight:800;margin-bottom:6px}
.now-playing-album{color:#aaa;font-size:15px}
.now-playing-stats{
  display:flex;
  flex-wrap:wrap;
  gap:10px;
  margin-top:12px;
}

.now-playing-stats span{
  padding:6px 10px;
  border:1px solid #2b2f36;
  border-radius:999px;
  background:#171a1f;
  font-size:13px;
  font-weight:800;
}

.now-progress{height:8px;background:#2b2f36;border-radius:999px;overflow:hidden;margin:14px 0 8px;max-width:420px}
.now-progress-fill{height:100%;background:#F7931E;border-radius:999px}
.recent-track-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin-top:12px}
.recent-track{display:flex;gap:12px;align-items:center;background:#171a1f;border:1px solid #2b2f36;border-radius:14px;padding:10px}
.recent-track img{width:52px;height:52px;border-radius:9px;object-fit:cover}
.recent-title{font-weight:800;line-height:1.2}
.recent-meta{color:#aaa;font-size:12px;line-height:1.35}
</style>
"""

script = """
<script>
let nowPlayingProgressTimer = null;

async function loadNowPlaying(){
  const box = document.getElementById('nowPlayingContent');
  if(!box) return;

  try{
    const res = await fetch('/now-playing.json?ts=' + Date.now());
    const data = await res.json();

    const now = data.now_playing || [];
    const rediscover = data.rediscover || [];
    const updated = data.updated ? new Date(data.updated * 1000).toLocaleTimeString([], {hour:'numeric', minute:'2-digit'}) : '';

    function fmtTime(sec){
      sec = Math.max(0, Number(sec || 0));
      const m = Math.floor(sec / 60);
      const s = Math.floor(sec % 60).toString().padStart(2, '0');
      return `${m}:${s}`;
    }

    let html = '';
    let duration = 0;
    let elapsed = 0;

    if(now.length){
      const t = now[0];
      duration = Number(t.duration || 0);
      const minutesAgo = Number(t.minutesAgo || 0);
      const playCount = Number(t.playCount || 0);
      const loved = Boolean(t.starred);
      elapsed = Math.min(duration, Math.max(0, Math.round(minutesAgo * 60)));
      const pct = duration ? Math.min(100, Math.round((elapsed / duration) * 100)) : 0;

      html += `
        <div class="now-playing-layout">
          <img src="${t.cover || ''}" loading="lazy" onerror="this.style.display='none';">
          <div>
            <div class="now-playing-title">${t.title || ''}</div>
            <div class="now-playing-artist">${t.artist || ''}</div>
            <div class="now-playing-album">${t.album || ''}</div>

            <div class="now-playing-stats">
              <span>${loved ? '❤️ Loved' : '♡ Not loved'}</span>
              <span>▶ ${playCount.toLocaleString()} plays</span>
            </div>

            <p class="small">Listening as ${t.username || ''}</p>
            <div class="now-progress">
              <div class="now-progress-fill" id="nowProgressFill" style="width:${pct}%"></div>
            </div>
            <p class="small">
              <span id="nowElapsed">${fmtTime(elapsed)}</span> /
              ${fmtTime(duration)} · Updated ${updated}
            </p>
          </div>
        </div>
      `;
    } else {
      html += `<p class="small">Nothing is currently playing in Navidrome.</p><p class="small">Updated ${updated}</p>`;
    }

    html += `<h3 style="margin-top:24px;">🔥 Rediscover These</h3>
      <p class="small">Shuffled picks from your Navidrome library.</p>
      <div class="recent-track-grid">`;

    html += rediscover.slice(0,10).map(x => `
      <div class="recent-track">
        <img src="${x.cover || ''}" loading="lazy" onerror="this.style.display='none';">
        <div>
          <div class="recent-title">${x.title || ''}</div>
          <div class="recent-meta">${x.artist || ''} · ${x.album || ''}</div>
        </div>
      </div>
    `).join('');

    html += `</div>`;
    box.innerHTML = html;

    if(nowPlayingProgressTimer){
      clearInterval(nowPlayingProgressTimer);
      nowPlayingProgressTimer = null;
    }

    if(now.length && duration > 0){
      let liveElapsed = elapsed;

      nowPlayingProgressTimer = setInterval(() => {
        liveElapsed = Math.min(duration, liveElapsed + 1);

        const elapsedNode = document.getElementById('nowElapsed');
        const progressNode = document.getElementById('nowProgressFill');

        if(elapsedNode){
          elapsedNode.textContent = fmtTime(liveElapsed);
        }

        if(progressNode){
          progressNode.style.width =
            Math.min(100, (liveElapsed / duration) * 100) + '%';
        }

        if(liveElapsed >= duration){
          clearInterval(nowPlayingProgressTimer);
          nowPlayingProgressTimer = null;
        }
      }, 1000);
    }

  } catch(e){
    box.innerHTML = '<p class="small">Unable to load Now Playing data.</p>';
  }
}

loadNowPlaying();
setInterval(loadNowPlaying, 15000);
</script>
"""

html = html.replace("</head>", css + "\n</head>", 1)
html = html.replace('<div class="card">', card + '\n<div class="card">', 1)
html = html.replace("</body>", script + "\n</body>", 1)

INDEX.write_text(html, encoding="utf-8")

print("Added live Now Playing card to homepage")
