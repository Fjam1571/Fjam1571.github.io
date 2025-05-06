import cloudscraper
import requests
import os
import re
import json
from datetime import datetime
from email.utils import parsedate_to_datetime
from io import BytesIO
import plistlib
import zipfile

# ——— Create a Cloudflare-bypassing scraper ———
# This uses Cloudscraper under the hood to solve IUAM (JS) challenges.
scraper = cloudscraper.create_scraper(
    browser={
        "browser": "chrome",
        "platform": "windows",
        "desktop": True
    },
    debug=False  # set True to see request/response headers
)  # :contentReference[oaicite:0]{index=0}

# ——— Step 1: Resolve final URL with Cloudscraper ———
initial_url = "http://movieboxpro.app/ipa"
try:
    resp = scraper.get(initial_url, timeout=15)
    resp.raise_for_status()
    final_url = resp.url
    print("Final URL:", final_url)
except requests.exceptions.HTTPError as e:
    print(f"Failed to resolve final URL ({initial_url}): {e}")
    exit(1)

# ——— Step 2: Last-Modified → version_date ———
try:
    head = scraper.head(final_url, timeout=10)
    lm = head.headers.get("Last-Modified")
    if lm:
        lm_dt = parsedate_to_datetime(lm)
        version_date = lm_dt.isoformat() + "Z"
    else:
        raise KeyError
except Exception:
    version_date = datetime.utcnow().isoformat() + "Z"
print("Version Date:", version_date)

def fetch_ipa_metadata(url, default_min_os="13.0"):
    """
    Returns (file_size, min_os_version, plist_version, bundle_id),
    using Cloudscraper to bypass Cloudflare, with HEAD fallback for size.
    """
    # 1) Try byte-range GET for size via Cloudscraper
    r = scraper.get(url, headers={"Range": "bytes=0-0"}, stream=True)
    content_range = r.headers.get("Content-Range", "")
    m = re.match(r"bytes \d+-\d+/(\d+)", content_range)
    if m:
        file_size = int(m.group(1))
    else:
        # fallback: HEAD for Content-Length
        h = scraper.head(url)
        cl = h.headers.get("Content-Length")
        file_size = int(cl) if cl and cl.isdigit() else None

    # 2) Download full IPA via Cloudscraper
    ipa_resp = scraper.get(url)
    ipa_resp.raise_for_status()
    ipa_bytes = BytesIO(ipa_resp.content)

    # 3) Parse Info.plist
    min_os    = default_min_os
    plist_ver = None
    bundle_id = None

    with zipfile.ZipFile(ipa_bytes) as zf:
        for path in zf.namelist():
            if re.match(r"^Payload/[^/]+\.app/Info\.plist$", path):
                info = plistlib.loads(zf.read(path))
                min_os    = info.get("MinimumOSVersion", default_min_os)
                plist_ver = info.get("CFBundleShortVersionString")
                bundle_id = info.get("CFBundleIdentifier")
                break

    return file_size, min_os, plist_ver, bundle_id

# ——— Steps 3 & 3.5: Fetch IPA metadata ———
file_size, min_os_version, plist_app_version, bundle_identifier = \
    fetch_ipa_metadata(final_url, default_min_os="13.0")

print("File Size:", file_size)
print("Min OS Version:", min_os_version)
print("Plist Version:", plist_app_version)
print("Bundle Identifier:", bundle_identifier)

# ——— Step 4: Filename fallback only if plist had no version ———
if not plist_app_version:
    fname = os.path.basename(final_url)
    fm = re.search(r'_(\d+(?:\.\d+)+)\.ipa$', fname)
    if fm:
        plist_app_version = fm.group(1)
        print("Filename fallback version:", plist_app_version)
    else:
        print("No version found in filename either.")

# ——— Step 5: Load and update JSON ———
json_file = "Sources/MovieBoxPro.json"
try:
    with open(json_file, "r") as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"{json_file} not found; aborting.")
    exit(1)

app = data["apps"][0]
current_version = app.get("versions", [{}])[0].get("version")
print("Current JSON version:", current_version)

if current_version != plist_app_version:
    print("Updating to version", plist_app_version)
    app["version"]     = plist_app_version
    app["downloadURL"] = final_url
    if bundle_identifier:
        app["bundleIdentifier"] = bundle_identifier

    new_entry = {
        "version":          plist_app_version,
        "date":             version_date,
        "downloadURL":      final_url,
        "localizedDescription":
            f"Updated to {plist_app_version} on {version_date}",
        "size":             file_size,
        "minOSVersion":     min_os_version
    }
    app.setdefault("versions", []).insert(0, new_entry)

    with open(json_file, "w") as f:
        json.dump(data, f, indent=2)
    print("JSON file updated.")
else:
    print("No update needed; versions match.")
