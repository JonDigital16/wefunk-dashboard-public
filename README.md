# WEFUNK Dashboard

> **Explore decades of WEFUNK Radio playlists alongside your own music
> library.**

*Transforming playlists into a living music knowledge base.*

------------------------------------------------------------------------

<img width="2499" height="852" alt="Screenshot 2026-08-17 at 3 05 10 PM" src="https://github.com/user-attachments/assets/c1b19d13-ac8f-447f-a47a-755fabac5c03" />

## Highlights

-   🎵 Intelligent matching against your personal music library
-   📚 Browse WEFUNK episodes, artists, albums, genres, and years
-   🧠 Fuzzy artist and title matching with metadata normalization
-   📊 Collection statistics and missing-track analysis
-   🖼️ Album, artist, and episode artwork support
-   ▶️ Optional Navidrome play-count and now-playing integration
-   🔎 Fast client-side search
-   🚀 Static dashboard generation
-   ⚙️ Portable environment-based configuration

## Screenshots

### Homepage

<img width="2498" height="993" alt="Screenshot 2026-08-17 at 3 06 26 PM" src="https://github.com/user-attachments/assets/855df213-b8aa-495b-a1e6-58191ed4b21d" />

### Episode Browser

<img width="1477" height="945" alt="Screenshot 2026-08-17 at 3 07 06 PM" src="https://github.com/user-attachments/assets/6c3fdea7-acc6-408c-b681-6256ab64226f" />

### Artist Pages

<img width="1235" height="1127" alt="Screenshot 2026-08-17 at 3 20 38 PM" src="https://github.com/user-attachments/assets/b684f6f0-e273-4e65-a9c6-c0dff300691c" />

### Album Index

<img width="1226" height="560" alt="Screenshot 2026-08-17 at 3 22 50 PM" src="https://github.com/user-attachments/assets/6b419b32-2df1-4d03-915f-93edf4f5b202" />

### Album Page

<img width="2379" height="765" alt="Screenshot 2026-08-17 at 3 24 10 PM" src="https://github.com/user-attachments/assets/14249a68-8ab6-4034-bcf9-715385f235bc" />

### Genre Index

<img width="2453" height="1092" alt="Screenshot 2026-08-17 at 3 10 56 PM" src="https://github.com/user-attachments/assets/dd520888-c709-4c81-a2d0-bf6e0a975227" />

### Search

<img width="783" height="876" alt="Screenshot 2026-08-17 at 3 11 25 PM" src="https://github.com/user-attachments/assets/7a9d67c3-7cd0-4683-8027-16682ed230fe" />

### Collection Goals

<img width="2455" height="376" alt="Screenshot 2026-08-17 at 3 13 14 PM" src="https://github.com/user-attachments/assets/4be96c67-70a0-40de-be92-77d0fed3296d" />

### Statistics

<img width="2457" height="915" alt="Screenshot 2026-08-17 at 3 14 25 PM" src="https://github.com/user-attachments/assets/63cb6a6c-4ac6-4dbe-b235-dedc39af9bf5" />

### Missing Tracks

<img width="1786" height="629" alt="Screenshot 2026-08-17 at 3 16 59 PM" src="https://github.com/user-attachments/assets/bb4ad45b-10d3-4653-984f-331668fcdcb4" />

### WEFUNK DNA

<img width="2494" height="1138" alt="Screenshot 2026-08-17 at 3 18 04 PM" src="https://github.com/user-attachments/assets/3cac27cf-7dd1-4a28-b8b7-ab63dc8e266c" />

### Listening History

<img width="1518" height="1148" alt="image" src="https://github.com/user-attachments/assets/8361e7f8-211a-4f28-9d53-eaf84b85b432" />

## How It Works

``` text
WEFUNK playlist metadata
        │
        ▼
Import / database engine
        │
        ▼
Local music-library matching
        │
        ▼
Metadata and genre enrichment
        │
        ▼
Artwork / play-count processing
        │
        ▼
Dashboard generator
        │
        ▼
Static website
```

Each stage enriches the previous one while keeping runtime data separate
from the application source.

The generated site can be served locally or placed behind a normal web
server or reverse proxy.

## Requirements

WEFUNK Dashboard is currently developed and tested primarily on
**macOS**. Much of the Python code should also be portable to Linux, but
the included shell helpers and some optional integrations are
macOS-oriented.

You will need:

-   Python 3.14+
-   A local music library
-   WEFUNK playlist metadata in JSON format
-   SQLite support, included with standard Python installations

Optional integrations include:

-   Navidrome
-   An external WEFUNK episode downloader
-   An external WEFUNK playlist scraper

## Installation

Clone or download the repository, then create a Python virtual
environment:

``` bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

Create your local configuration:

``` bash
cp .env.example .env
```

Edit `.env` and set the paths appropriate for your system.

At minimum, review:

``` text
WEFUNK_DATA_DIR
WEFUNK_MUSIC_DIR
WEFUNK_EPISODE_DIR
WEFUNK_SITE_DIR
```

If you use Navidrome, also configure:

``` text
ND_URL
ND_USER
ND_PASS
```

Your real `.env` file is ignored by Git and should never be committed.

## First-Run Setup

After installing dependencies and configuring `.env`, run:

```bash
./bin/wefunk-init
```

The first-run check:

- creates the runtime directory structure;
- verifies the Python environment and required packages;
- checks your configured music directory;
- checks for WEFUNK metadata;
- checks for required databases;
- reports what still needs to be configured.

It does not modify your music library or perform a full scan.

### Add WEFUNK playlist metadata

Place at least one WEFUNK playlist JSON export in:

```text
$WEFUNK_DATA_DIR/json
```

The filename must match:

```text
wefunk_shows_<first-show>_<last-show>.json
```

For example:

```text
wefunk_shows_1_1300.json
```

Each show should contain its playlist entries under `playlistbox`.

An external WEFUNK playlist scraper can also be used to collect or
refresh metadata. Configure its location with:

```text
WEFUNK_SCRAPER_SCRIPT=/path/to/scraper
```

The scraper integration is optional and is not required when compatible
playlist JSON already exists.

### Initialize and import the primary database

The first metadata import is intentionally a two-step process.

First run a dry run:

```bash
./bin/wefunk-import
```

On a new installation this creates the empty primary `wefunk.db`,
validates the newest `wefunk_shows_*.json` file, and reports the shows
and tracks that would be imported.

Review the report. If it looks correct, apply the import:

```bash
./bin/wefunk-import --apply
```

Subsequent imports preserve existing show and track IDs and create a
database backup before inserting new shows.

### Run the first full scan

Once metadata has been imported:

```bash
./bin/wefunk-scan
```

The full scan indexes the configured music library, matches WEFUNK
playlist entries against local music, exports reports and playlists,
and safely rebuilds the dashboard.

Navidrome is optional. If `ND_URL`, `ND_USER`, and `ND_PASS` are all
configured, the scan also synchronizes Navidrome play counts and
attempts Navidrome-backed artist-image enrichment. If they are not
configured, those steps are skipped automatically without prompting.

## Main Workflow

### Full scan

``` bash
./bin/wefunk-scan
```

The full scan runs the WEFUNK engine and safely rebuilds the dashboard.
If Navidrome credentials are configured, it also synchronizes play
counts and attempts Navidrome-backed artist-image enrichment.

### WEFUNK Listening History

WEFUNK Dashboard can optionally maintain a personal listening history
containing only tracks that also appear in the WEFUNK tracklist database.

This feature is independent of Last.fm. Playback information is read from
Navidrome using the existing `ND_URL`, `ND_USER`, and `ND_PASS` configuration.

Initialize listening history once with `./bin/wefunk-listening init`.

Inspect its current status with `./bin/wefunk-listening status`.

Process the currently playing Navidrome track with
`./bin/wefunk-listening collect`.

The collector records a qualifying play only after enough of the track has
been heard and protects against duplicate entries while the same playback
remains active. Tracks that do not appear in the WEFUNK database are ignored.

`collect` is designed to be run periodically by a scheduler such as launchd,
cron, or systemd. Listening History remains optional; users who do not
configure Navidrome can continue using the rest of WEFUNK Dashboard normally.

The generated `/listening.html` page includes recent WEFUNK-matched plays,
time-range filtering, listening activity, top artists, top albums, top tracks,
listening time, and links back into WEFUNK artist, album, and episode pages.

### Navidrome Playlists

WEFUNK Dashboard can generate `.m3u` playlists from tracks in your local
music library that have been matched against the WEFUNK database.

Preview the playlists without writing anything:

``` bash
python3 wefunk-dashboard/generate_navidrome_playlists.py
```

Write the current canonical playlists:

``` bash
python3 wefunk-dashboard/generate_navidrome_playlists.py --apply
```

By default, playlists are written to:

``` text
$WEFUNK_MUSIC_DIR/playlists/wefunk
```

The generated playlist paths use `/music` as the music-library path visible
inside Navidrome. Override that if your Navidrome MusicFolder uses a different
path:

``` bash
python3 wefunk-dashboard/generate_navidrome_playlists.py --navidrome-root /music --apply
```

Playlist state is stored in:

``` text
$WEFUNK_DATA_DIR/state/navidrome-playlists.json
```

Use `--expand` together with `--apply` to add newly qualifying Genre, Artist,
and Episode Range playlists to the canonical playlist manifest:

``` bash
python3 wefunk-dashboard/generate_navidrome_playlists.py --expand --apply
```

This feature does not require Navidrome API credentials. It operates directly
on the WEFUNK database and local music library and writes playlist files that
Navidrome can discover from the configured music folder.

### Incremental update

After the initial library index exists:

``` bash
./bin/wefunk-update
```

This updates WEFUNK data using the existing library index and rebuilds
the dashboard.

### Rebuild only

To rebuild the dashboard from the existing databases and exports:

``` bash
./bin/wefunk-dashboard
```

### Serve locally

Start the included dashboard server:

``` bash
./wefunk-dashboard/run-dashboard.sh
```

The default local address is:

``` text
http://localhost:8099
```

Open the configured dashboard URL with:

``` bash
./bin/wefunk-dashboard-open
```

The Flask application also exposes:

``` text
/health
```

for a simple HTTP health check.

## Command-Line Helpers

  -----------------------------------------------------------------------
  Command                             Purpose
  ----------------------------------- -----------------------------------
  `./bin/wefunk-init`                 Validate a new installation and
                                      create runtime directories
                                      
  `./bin/wefunk-import`               Initialize/import WEFUNK playlist
                                      metadata into the primary database
  
  `./bin/wefunk-scan`                 Run a full WEFUNK/library scan and
                                      dashboard rebuild

  `./bin/wefunk-update`               Run an incremental update using the
                                      existing library index

  `./bin/wefunk-sync`                 Sync Navidrome play counts and
                                      rebuild

  `./bin/wefunk-dashboard`            Safely rebuild the generated
                                      dashboard

  `./bin/wefunk-dashboard-health`     Check whether generated dashboard
                                      output exists

  `./bin/wefunk-dashboard-open`       Open the configured dashboard URL

  `./bin/wefunk-dashboard-steps`      Display the dashboard build
                                      pipeline

  `./bin/wefunk-check-scripts`        Display key project script
                                      locations

  `./bin/wefunk-album-art`            Download missing album artwork and
                                      rebuild

  `./bin/wefunk-art`                  Download WEFUNK episode artwork

  `./bin/wefunk-download`             Run the optional external
                                      episode-download workflow

  `./bin/wefunk-nowplaying`           Export current Navidrome
                                      now-playing data

  `./bin/wefunk-listening`            Initialize, collect, or inspect
                                      WEFUNK-only listening history

  `./bin/wefunk-nowplaying-status`    Inspect now-playing state on macOS

  `./bin/wefunk-snapshot`             Create a recovery snapshot of code,
                                      database, and operational state

  `./bin/wefunk-restore`              Restore an individual recovery
                                      snapshot component

  `./bin/wefunk-rollback`             Roll back code, database, and state
                                      together from a recovery snapshot

  `./bin/wefunk-weekly`               Run the optional download, artwork,
                                      and update workflow
  -----------------------------------------------------------------------

## Recovery Toolkit

WEFUNK Dashboard includes a recovery toolkit for creating independent,
timestamped snapshots of the project source, SQLite database, and runtime state.

Recovery snapshots are stored by default under:

``` text
$WEFUNK_DATA_DIR/recovery
```

Create a snapshot:

``` bash
./bin/wefunk-snapshot
```

Optionally include a description:

``` bash
./bin/wefunk-snapshot "Before dashboard upgrade"
```

Each snapshot contains the project source and configuration, an
SQLite-consistent copy of `wefunk.db`, WEFUNK operational state files,
and optional configured system files.

Generated dashboard output, virtual environments, logs, backups, Git
metadata, and other disposable data are excluded.

### Restore one component

Review a restore first:

``` bash
./bin/wefunk-restore --dry-run <snapshot-id> database
```

Then perform it:

``` bash
./bin/wefunk-restore <snapshot-id> database
```

Valid components are `database`, `state`, and `code`.

A live restore automatically creates a fresh pre-restore snapshot.
Database restores verify checksums and SQLite integrity, block writable
SQLite handles, preserve the current database, and run `PRAGMA quick_check`
after restoration.

### Full rollback

Review the complete rollback plan:

``` bash
./bin/wefunk-rollback --dry-run <snapshot-id>
```

Then restore code, database, and state together:

``` bash
./bin/wefunk-rollback <snapshot-id>
```

A full rollback creates an automatic pre-rollback snapshot before making
changes. When configured macOS LaunchAgents are available, the toolkit
coordinates service shutdown and restart around recovery.

Files created after the target snapshot are not deleted, and the recovery
toolkit scripts are preserved during code restoration.

Recovery paths and service settings can be customized using the variables
documented in `.env.example`.

## Configuration

Configuration is controlled through environment variables.

The included `.env.example` documents the available settings. Values
supplied by the operating environment take precedence over values in the
project-local `.env`.

### Runtime data

`WEFUNK_DATA_DIR` is the runtime data root.

Default:

``` text
~/.local/share/wefunk
```

Runtime data may include:

``` text
db/
exports/
json/
artwork/
playlists/
state/
timing-cache/
```

### Music library

`WEFUNK_MUSIC_DIR` points to your main music library.

Default:

``` text
~/Music
```

### WEFUNK episodes

`WEFUNK_EPISODE_DIR` points to downloaded WEFUNK episode audio.

Default:

``` text
$WEFUNK_MUSIC_DIR/wefunkradio mixes
```

### Generated site

`WEFUNK_SITE_DIR` controls the generated dashboard location.

Default:

``` text
<project>/site
```

### Database and exports

The normal defaults are:

``` text
WEFUNK_DB_FILE=$WEFUNK_DATA_DIR/db/wefunk.db
WEFUNK_EXPORT_DIR=$WEFUNK_DATA_DIR/exports
```

Both can be overridden independently.

### Dashboard server

The default local port is:

``` text
WEFUNK_PORT=8099
```

Set `WEFUNK_PUBLIC_URL` if the dashboard is available through an
external URL or reverse proxy.

### Navidrome

Optional Navidrome integration uses:

``` text
ND_URL
ND_USER
ND_PASS
```

Navidrome is used by play-count, now-playing, and Listening History features.

The Navidrome playlist generator does not use these API credentials. It writes
`.m3u` files directly beneath the configured music library. Its default
Navidrome-visible music path is `/music`; use `--navidrome-root` when your
Navidrome MusicFolder uses a different path.

### Advanced overrides

Advanced configuration can override locations such as:

``` text
WEFUNK_PROJECT_ROOT
WEFUNK_VENV
WEFUNK_PYTHON
WEFUNK_ENGINE_SCRIPT
WEFUNK_MATCHER_SCRIPT
WEFUNK_BUILD_STEPS
WEFUNK_SITE_NEXT_DIR
WEFUNK_SITE_BACKUP_DIR
WEFUNK_LOG_DIR
```

See `.env.example` for details.

## Project Structure

``` text
wefunk-dashboard/
├── .env.example
├── .gitattributes
├── .gitignore
├── README.md
├── requirements.txt
├── bin/
│   └── command-line helpers
├── docs/
│   └── screenshots and documentation assets
├── engine/
│   └── matching, database, and library-processing modules
├── generators/
├── render/
├── wefunk-dashboard/
│   └── dashboard generators, Flask app, and build pipeline
└── wefunk-engine/
    └── standalone WEFUNK processing engine
```

Runtime and generated data are intentionally kept outside the tracked
source.

## Safe Dashboard Builds

`./bin/wefunk-dashboard` builds a new site in a staging directory before
replacing the current generated site.

Conceptually:

``` text
site-next
    │
    │ build succeeds
    ▼
  site
```

Before replacement, the previous generated site can be retained as:

``` text
site-backup-last-good
```

The staging site, generated site, and local backup are excluded from
version control.

## WEFUNK Metadata

WEFUNK Dashboard expects playlist metadata in JSON format under:

```text
$WEFUNK_DATA_DIR/json
```

Metadata filenames must use the form:

```text
wefunk_shows_<first-show>_<last-show>.json
```

The importer accepts a JSON list of show objects, or an object
containing a `shows` list. Playlist entries for each show are read from
the `playlistbox` field.

Before the first scan, initialize and import the metadata with:

```bash
./bin/wefunk-import
./bin/wefunk-import --apply
```

The first command is a dry run. The second applies the reviewed import.

Playlist metadata can also be collected using an external WEFUNK
playlist scraper. The optional setting:

```text
WEFUNK_SCRAPER_SCRIPT
```

can point to a scraper used by metadata-refresh workflows.

## Optional Episode Downloads

The project can integrate with an external WEFUNK episode downloader.

Configure:

``` text
WEFUNK_DOWNLOADER_DIR=/path/to/downloader
```

and run:

``` bash
./bin/wefunk-download
```

This integration is optional. It is not required when you already have
the WEFUNK metadata and audio needed for your workflow.

## Artwork

WEFUNK Dashboard contains tools for processing episode, album, and
artist artwork.

Useful helpers include:

``` bash
./bin/wefunk-art
./bin/wefunk-album-art
```

Some artist-image workflows use external services such as MusicBrainz
and may require network access.

## Generated Dashboard

The build pipeline generates a static dashboard containing HTML, CSS,
JavaScript, images, JSON assets, and client-side search data.

The generated `site/` directory is not committed to the repository by
default.

The repository also includes a small Flask/Waitress application for
serving the generated site locally.

## Privacy and Local Data

WEFUNK Dashboard is designed so personal library data and credentials
remain outside the source repository.

The default `.gitignore` excludes items such as:

-   `.env`;
-   Python virtual environments;
-   generated dashboard output;
-   runtime databases;
-   CSV exports;
-   logs;
-   reports;
-   backups;
-   runtime playback state;
-   generated artwork caches.

Before publishing your own fork, always review the files selected for
commit and make sure they do not contain credentials, private URLs,
personal filesystem paths, or music-library data.

## Development Checks

### Python syntax

``` bash
find . \
  -type f \
  -name '*.py' \
  -not -path './.venv/*' \
  -not -path '*/__pycache__/*' \
  -print0 |
while IFS= read -r -d '' f; do
  .venv/bin/python -m py_compile "$f" || exit 1
done
```

### Shell syntax

``` bash
find bin wefunk-dashboard \
  -type f \
  -print0 |
while IFS= read -r -d '' f; do
  head -1 "$f" | grep -qE '^#!.*(zsh|bash|sh)' || continue
  zsh -n "$f" || exit 1
done
```

## Contributing

Contributions are welcome.

Please:

-   keep changes focused;
-   avoid committing generated or personal data;
-   never commit credentials;
-   avoid machine-specific paths in source;
-   run Python and shell syntax checks;
-   test against isolated runtime directories when practical.

## License

WEFUNK Dashboard is released under the [MIT License](LICENSE).

## Acknowledgements

WEFUNK Dashboard exists because of the remarkable work of **WEFUNK
Radio** and its decades-long commitment to sharing exceptional music.

This project is an independent companion created to help listeners
explore, organize, and rediscover the artists, albums, tracks, and
musical history represented throughout the WEFUNK archive.

### WEFUNK Downloader

The `evanslynk/wefunkdownloader` project provides tooling for
downloading and preserving WEFUNK Radio episodes and can be used as an
optional external integration.

### WEFUNK Playlist Downloader

The `gmg77/wefunk_pl` project provides tooling for collecting WEFUNK
playlist metadata. Playlist JSON produced by tooling such as this can
serve as source material for WEFUNK Dashboard.

WEFUNK Dashboard is not affiliated with or endorsed by WEFUNK Radio.
