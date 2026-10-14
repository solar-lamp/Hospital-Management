"""Build the static GitHub Pages site.

The same Python source runs in the browser through stlite (Streamlit on
Pyodide/WebAssembly). The SQLite database lives in the browser's IndexedDB,
so each visitor gets a private copy of the fictional demo data.

    python scripts/build_site.py            # writes _site/
    python -m http.server -d _site 8000     # preview at http://localhost:8000
"""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_site"

STLITE_VERSION = "1.9.2"  # bundles Streamlit 1.62.0 and Pyodide 0.29.3
SOURCES = ["app.py", "config.py", "database.py", "seed.py"]
PACKAGES = ["pages", "services", "repositories", "utils"]
# Pure-Python wheels installed with micropip; pandas comes prebuilt with Pyodide.
REQUIREMENTS = ["plotly==7.1.0", "openpyxl==3.1.5"]
# Pyodide ships these stdlib modules separately: sqlite3, and _hashlib (OpenSSL),
# which provides hashlib.pbkdf2_hmac for password hashing.
PREBUILT = ["sqlite3", "hashlib"]

ENV = {
    "HMS_DB_PATH": "/meditrack/hospital.db",   # IndexedDB-backed mount point
    "HMS_DEMO_MODE": "1",
    "HMS_AUTO_SEED_DEMO": "1",
    # WebAssembly hashing is slower than native; still a strong salted KDF.
    "HMS_PBKDF2_ITERATIONS": "210000",
}

INDEX = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
  <title>MediTrack HMS</title>
  <meta name="description" content="MediTrack: hospital management and resource tracking demo built with Python, Streamlit and SQLite, running in your browser.">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🏥</text></svg>">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@stlite/browser@__VERSION__/build/stlite.css">
  <style>
    #boot { font-family: system-ui, sans-serif; max-width: 560px; margin: 18vh auto 0; padding: 0 16px; color: #333; text-align: center; }
    #boot h1 { margin-bottom: .2em; }
    #boot p { color: #666; line-height: 1.5; }
  </style>
</head>
<body>
  <div id="root">
    <div id="boot">
      <h1>🏥 MediTrack</h1>
      <p>Starting the hospital management app in your browser&hellip;<br>
      The first visit downloads Python (about 30&nbsp;MB) and builds fictional demo data;
      later visits are faster.</p>
      <noscript><p><strong>JavaScript is required.</strong></p></noscript>
    </div>
  </div>
  <script type="module">
    import { mount } from "https://cdn.jsdelivr.net/npm/@stlite/browser@__VERSION__/build/stlite.js";
    const files = __FILES__;
    mount({
      entrypoint: "app.py",
      files: Object.fromEntries(files.map((f) => [f, { url: "./app/" + f }])),
      requirements: __REQUIREMENTS__,
      prebuiltPackageNames: __PREBUILT__,
      idbfsMountpoints: ["/meditrack"],
      env: __ENV__,
      streamlitConfig: {
        "client.toolbarMode": "minimal",
        "theme.primaryColor": "#2a78d6",
      },
    }, document.getElementById("root"));
  </script>
</body>
</html>
"""

# GitHub Pages serves 404.html for unknown paths (e.g. reloading a page URL);
# send the visitor back to the app root, which restores their session state.
NOT_FOUND = """<!doctype html>
<meta charset="utf-8"><title>MediTrack HMS</title>
<script>
  const repo = location.pathname.split("/")[1];
  location.replace(location.hostname.endsWith("github.io") && repo ? "/" + repo + "/" : "/");
</script>
"""


def collect() -> list[str]:
    files = list(SOURCES)
    for package in PACKAGES:
        files += sorted(p.relative_to(ROOT).as_posix()
                        for p in (ROOT / package).rglob("*.py") if "__pycache__" not in p.parts)
    return files


def build() -> Path:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "app").mkdir(parents=True)
    files = collect()
    for rel in files:
        dest = OUT / "app" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dest)
    html = (INDEX.replace("__VERSION__", STLITE_VERSION)
            .replace("__FILES__", json.dumps(files))
            .replace("__REQUIREMENTS__", json.dumps(REQUIREMENTS))
            .replace("__PREBUILT__", json.dumps(PREBUILT))
            .replace("__ENV__", json.dumps(ENV)))
    (OUT / "index.html").write_text(html, encoding="utf-8")
    (OUT / "404.html").write_text(NOT_FOUND, encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Built {OUT} with {len(files)} Python files")
    return OUT


if __name__ == "__main__":
    build()
