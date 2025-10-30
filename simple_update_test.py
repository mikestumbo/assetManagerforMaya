# Simple Update Check Test - Run in Maya Script Editor (Python tab)
# This tests the update check without the complex threading

import urllib.request
import urllib.error
import json

print("🔍 Testing simple update check...")

try:
    # Test the GitHub API call directly
    url = "https://api.github.com/repos/mikestumbo/assetManagerforMaya/releases/latest"
    print(f"📍 Making request to: {url}")
    
    req = urllib.request.Request(url)
    req.add_header('Accept', 'application/vnd.github.v3+json')
    
    with urllib.request.urlopen(req, timeout=10) as response:
        print("📍 HTTP request successful")
        data = json.loads(response.read().decode('utf-8'))
        latest_version = data.get('tag_name', '').lstrip('v')
        print(f"✅ Latest version from GitHub: {latest_version}")
        
        # Show some release info
        name = data.get('name', 'Unknown')
        print(f"📋 Release name: {name}")
        
except urllib.error.URLError as e:
    print(f"❌ Network error: {e}")
except Exception as e:
    print(f"❌ General error: {e}")
    import traceback
    traceback.print_exc()

print("✅ Simple update check test complete")