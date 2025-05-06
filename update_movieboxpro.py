import requests
import os
import re
import json
from datetime import datetime
from email.utils import parsedate_to_datetime
from io import BytesIO
import plistlib
import zipfile

def fetch_ipa_metadata(url, default_min_os="13.0"):
    """
    Returns a tuple (file_size, min_os_version, plist_version, bundle_id)
    by:
      1) issuing a byte-range GET for bytes=0-0 to parse Content-Range → total size
      2) downloading the IPA fully into memory
      3) locating exactly Payload/<App>.app/Info.plist
      4) extracting MinimumOSVersion, CFBundleShortVersionString, CFBundleIdentifier
    """
    # 1) Get file size via byte-range GET
    r = requests.get(url, headers={"Range": "bytes=0-0"}, allow_redirects=True)
    content_range = r.headers.get("Content-Range", "")
    m = re.match(r"bytes \d+-\d+/(\d+)", content_range)
    file_size = int(m.group(1)) if m else None

    # 2) Download full IPA
    ipa_resp = requests.get(url)
    ipa_resp.raise_for_status()
    ipa_bytes = BytesIO(ipa_resp.content)

    # Defaults
    min_os    = default_min_os
    plist_ver = None
    bundle_id = None

    # 3) Open ZIP and find the canonical Info.plist
    with zipfile.ZipFile(ipa_bytes) as zf:
        for path in zf.namelist():
            if re.match(r"^Payload/[^/]+\.app/Info\.plist$", path):
                plist_data = zf.read(path)
                info = plistlib.loads(plist_data)
                min_os    = info.get("MinimumOSVersion", default_min_os)
                plist_ver = info.get("CFBundleShortVersionString")
                bundle_id = info.get("CFBundleIdentifier")
                break

    return file_size, min_os, plist_ver, bundle_id


# — Step 1: Resolve the real download URL by following redirects
initial_url = "http://movieboxpro.app/ipa"
resp = requests.get(initial_url, allow_redirects=True)
resp.raise_for_status()
final_url = resp.url
print("Final URL:", final_url)

# — Step 2: Fetch Last-Modified header for version_date fallback
head = requests.head(final_url, allow_redirects=True)
lm = head.headers.get("Last-Modified")
if lm:
    try:
        lm_dt = parsedate_to_datetime(lm)
        version_date = lm_dt.isoformat() + "Z"
    except Exception:
        version_date = datetime.utcnow().isoformat() + "Z"
else:
    version_date = datetime.utcnow().isoformat() + "Z"
print("Version Date:", version_date)

# — Step 3: Attempt to extract version & bundle-id from the IPA
file_size, min_os_version, plist_app_version, bundle_identifier = fetch_ipa_metadata(
    final_url,
    default_min_os="13.0"
)

print("File Size:", file_size, "bytes")
print("Minimum OS Version:", min_os_version)
print("Info.plist Version:", plist_app_version)
print("Bundle Identifier:", bundle_identifier)

# — Step 4: Fallback to filename-based version ONLY if plist had none
if not plist_app_version:
    fname = os.path.basename(final_url)
    fm = re.search(r'_(\d+(?:\.\d+)+)\.ipa$', fname)
    plist_app_version = fm.group(1) if fm else None
    if plist_app_version:
        print("Falling back to filename version:", plist_app_version)
    else:
        print("No version found in filename either—plist and filename both empty.")

# — Step 5: Load & update JSON if needed
json_file = "Sources/MovieBoxPro.json"
try:
    with open(json_file, "r") as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"{json_file} not found. Exiting.")
    exit(1)

app = data["apps"][0]
versions = app.get("versions", [])
current_version = versions[0]["version"] if versions else None
print("Current JSON version:", current_version)

if current_version != plist_app_version:
    print("Version change detected. Updating JSON…")

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
    print("No update needed; version matches.")
