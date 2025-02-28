import requests
import os
import re
import json
from datetime import datetime
from email.utils import parsedate_to_datetime

# Step 1: Get the final URL from the redirect
initial_url = "https://www.movieboxpro.app/ipa"
response = requests.get(initial_url, allow_redirects=True)
final_url = response.url
print("Final URL:", final_url)

# Step 2: Get the file size and Last-Modified date using a HEAD request on the final URL
head_response = requests.head(final_url, allow_redirects=True)
file_size = head_response.headers.get("Content-Length")
if file_size:
    file_size = int(file_size)
    print("File Size:", file_size, "bytes")
else:
    print("File size not found in the headers.")

# Grab the Last-Modified header as the version date
last_modified = head_response.headers.get("Last-Modified")
version_date_iso = "unknown"
if last_modified:
    try:
        # Convert Last-Modified to a datetime object and then to ISO format.
        dt = parsedate_to_datetime(last_modified)
        version_date_iso = dt.isoformat()
    except Exception as e:
        print("Error parsing Last-Modified header:", e)
else:
    print("Last-Modified header not found.")

print("Version Date (ISO):", version_date_iso)

# Step 3: Extract the version from the final URL's filename
filename = os.path.basename(final_url)
# Assumes the filename is in the format "MovieBoxPro_<version>.ipa"
match = re.search(r'_(\d+(?:\.\d+)+)\.ipa$', filename)
if match:
    fetched_version = match.group(1)
    print("Fetched Version:", fetched_version)
else:
    print("Version could not be extracted from the filename.")
    exit(1)

# Format the fetched version to match the JSON convention (e.g., "v9.6")
fetched_version_str = fetched_version

# Step 4: Load the JSON file and compare the version
json_file = "Sources/MovieBoxPro.json"
try:
    with open(json_file, "r") as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"{json_file} not found.")
    exit(1)

# Assume the JSON structure has an "apps" list and the first element is our target
app = data["apps"][0]
current_version = app.get("version", "")
print("Current Version in JSON:", current_version)

# Step 5: Compare and update if there is a version mismatch or if the version date has changed
if current_version != fetched_version_str or app.get("versionDate") != version_date_iso:
    print("Update detected. Updating JSON file...")
    app["version"] = fetched_version_str
    app["versionDate"] = version_date_iso  # Update the version date using the Last-Modified header
    app["size"] = file_size
    app["versionDescription"] = f"Updated to version {fetched_version_str} on {version_date_iso}"

    # Write the updated JSON back to file
    with open(json_file, "w") as f:
        json.dump(data, f, indent=2)
    print("JSON file updated.")
else:
    print("No update detected. Versions match.")
