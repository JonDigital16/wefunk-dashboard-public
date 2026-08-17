import os
from flask import Flask, send_from_directory, redirect
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent

# Load project-local configuration without overriding
# variables already supplied by the operating environment.
load_dotenv(PROJECT_ROOT / ".env", override=False)

SITE = Path(
    os.environ.get(
        "WEFUNK_SITE_DIR",
        PROJECT_ROOT / "site",
    )
).expanduser().resolve()

app = Flask(__name__)


@app.route("/health")
def health():
    return "ok\n"


@app.route("/")
def index():
    return send_from_directory(SITE, "index.html")


@app.route("/shows/<path:filename>")
def shows(filename):
    return send_from_directory(SITE / "shows", filename)


@app.route("/data/<path:filename>")
def data(filename):
    return send_from_directory(SITE / "data", filename)


@app.route("/artists/<path:filename>")
def artists(filename):
    return send_from_directory(SITE / "artists", filename)


@app.route("/missing.html")
def missing():
    return send_from_directory(SITE, "missing.html")


@app.route("/<path:filename>")
def root_files(filename):
    return send_from_directory(SITE, filename)


@app.route("/show/<show_id>")
def old_show_link(show_id):
    return redirect(f"/shows/{show_id}.html")


if __name__ == "__main__":
    port = int(os.environ.get("WEFUNK_PORT", "8099"))
    app.run(host="0.0.0.0", port=port)
