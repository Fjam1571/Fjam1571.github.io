import requests
import os
import re
import json
from datetime import datetime
from email.utils import parsedate_to_datetime

# Step 1: Get the final URL after following redirects
initial_url = "https://www.movieboxpro.app/ipa"
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
        # Parse the Last-Modified header into a datetime object and convert to ISO format
        last_modified_dt = parsedate_to_datetime(last_modified)
        version_date = last_modified_dt.isoformat() + "Z"
    except Exception as e:
        print("Error parsing Last-Modified:", e)
        version_date = datetime.utcnow().isoformat() + "Z"
else:
    version_date = datetime.utcnow().isoformat() + "Z"
print("Version Date (from Last-Modified):", version_date)

# Step 3: Extract the version from the final URL's filename
filename = os.path.basename(final_url)
# Assumes filename format: MovieBoxPro_<version>.ipa (e.g., MovieBoxPro_9.6.ipa)
match = re.search(r'_(\d+(?:\.\d+)+)\.ipa$', filename)
if match:
    fetched_version = match.group(1)
    print("Fetched Version:", fetched_version)
else:
    print("Version could not be extracted from the filename.")
    fetched_version = "unknown"

# Format version to match JSON convention (e.g., "v9.6")
fetched_version_str = fetched_version

# Step 4: Load the JSON file from Sources/MovieBoxPro.json and compare version
json_file = "Sources/MovieBoxPro.json"
try:
    with open(json_file, "r") as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"{json_file} not found. Exiting.")
    exit(1)

# Assume the JSON structure contains an "apps" list; update the first element.
app = data["apps"][0]
current_version = app.get("version", "unknown")
print("Current Version in JSON:", current_version)

# Step 5: Compare the fetched version with the current version and update if necessary
if current_version != fetched_version_str:
    print("Version mismatch detected. Updating JSON file...")
    app["version"] = fetched_version_str
    app["versionDate"] = version_date
    app["size"] = file_size
    app["versionDescription"] = f"Updated to {fetched_version_str} on {version_date}"
    
    # Write the updated data back to the JSON file
    with open(json_file, "w") as f:
        json.dump(data, f, indent=2)
    print("JSON file updated.")
else:
    print("No update needed. Versions match.")
