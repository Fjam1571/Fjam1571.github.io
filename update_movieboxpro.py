import requests
import os
import re
import json
from datetime import datetime
from email.utils import parsedate_to_datetime
from io import BytesIO
import plistlib
import zipfile

# Step 1: Get the final URL after following redirects
initial_url = "http://movieboxpro.app/ipa"
response = requests.get(initial_url, allow_redirects=True)
final_url = response.url
print("Final URL:", final_url)

# Step 2: Get file size and Last-Modified using a HEAD request on the final URL
head_response = requests.head(final_url, allow_redirects=True)
file_size = head_response.headers.get("Content-Length")
if file_size:
    file_size = int(file_size)
    print("File Size:", file_size, "bytes")
else:
    print("File size not found in headers.")

last_modified = head_response.headers.get("Last-Modified")
if last_modified:
    try:
        last_modified_dt = parsedate_to_datetime(last_modified)
        version_date = last_modified_dt.isoformat() + "Z"
    except Exception as e:
        print("Error parsing Last-Modified:", e)
        version_date = datetime.utcnow().isoformat() + "Z"
else:
    version_date = datetime.utcnow().isoformat() + "Z"
print("Version Date (from Last-Modified):", version_date)

# Step 3: Extract a fallback version from the final URL's filename
filename = os.path.basename(final_url)
match = re.search(r'_(\d+(?:\.\d+)+)\.ipa$', filename)
if match:
    fetched_version = match.group(1)
    print("Fetched Version (from filename):", fetched_version)
else:
    print("Version could not be extracted from the filename.")
    fetched_version = "unknown"
fetched_version_str = fetched_version

# Step 3.5: Download the IPA file and extract info from its Info.plist
# Default values
min_os_version = "13.0"  # Default MinimumOSVersion
plist_app_version = fetched_version_str  # Fallback to version from filename
bundle_identifier = None  # Will update if found in the plist

ipa_response = requests.get(final_url)
if ipa_response.ok:
    ipa_file_bytes = BytesIO(ipa_response.content)
    try:
        with zipfile.ZipFile(ipa_file_bytes) as ipa_zip:
            # Look for the Info.plist file in the Payload/<folder>.app/ directory only
            for file_name in ipa_zip.namelist():
                # This regex matches only files in the form:
                # Payload/<folder>.app/Info.plist
                if re.match(r'^Payload/[^/]+\.app/Info\.plist$', file_name):
                    plist_data = ipa_zip.read(file_name)
                    try:
                        plist_dict = plistlib.loads(plist_data)
                        # Extract the Minimum OS Version
                        min_os_version = plist_dict.get("MinimumOSVersion", min_os_version)
                        # Extract the app version using CFBundleShortVersionString if available
                        plist_app_version = plist_dict.get("CFBundleShortVersionString", plist_app_version)
                        # Extract the bundle identifier using CFBundleIdentifier
                        bundle_identifier = plist_dict.get("CFBundleIdentifier", bundle_identifier)
                        print("Minimum OS Version extracted:", min_os_version)
                        print("App Version from plist:", plist_app_version)
                        print("Bundle Identifier from plist (CFBundleIdentifier):", bundle_identifier)
                    except Exception as e:
                        print("Error parsing Info.plist:", e)
                    break
    except Exception as e:
        print("Error reading IPA file as zip:", e)
else:
    print("Failed to download IPA for extracting Info.plist data")

# Step 4: Load the JSON file and update the app's bundleIdentifier and version info
json_file = "Sources/MovieBoxPro.json"
try:
    with open(json_file, "r") as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"{json_file} not found. Exiting.")
    exit(1)

app = data["apps"][0]

if "versions" in app and app["versions"]:
    current_version = app["versions"][0]["version"]
    print("Current Version in JSON:", current_version)
else:
    print("No versions found in JSON, initializing versions list.")
    app["versions"] = []
    current_version = None

# Step 5: Compare the version from the plist with the current version in JSON and update if necessary
if current_version != plist_app_version:

    app["version"] = plist_app_version
    app["downloadURL"] = final_url
    # Update the app's bundleIdentifier if one was extracted from the IPA's Info.plist
    if bundle_identifier:
        app["bundleIdentifier"] = bundle_identifier

    print("Version mismatch detected. Updating JSON file...")
    new_version_entry = {
        "version": plist_app_version,
        "date": version_date,
        "downloadURL": final_url,
        "localizedDescription": f"Updated to {plist_app_version} on {version_date}",
        "size": file_size,
        "minOSVersion": min_os_version
    }
    # Insert the new version entry at the beginning of the versions list
    app["versions"].insert(0, new_version_entry)

    # Write the updated data back to the JSON file
    with open(json_file, "w") as f:
        json.dump(data, f, indent=2)
    print("JSON file updated.")
else:
    print("No update needed. Versions match.")
