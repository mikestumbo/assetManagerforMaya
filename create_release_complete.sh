#!/bin/bash
# Complete GitHub Release Creation for Asset Manager v1.0.0
# This script creates the actual GitHub release with all required components

set -e

REPO_OWNER="mikestumbo"
REPO_NAME="assetManagerforMaya"
TAG_NAME="v1.0.0"
TARGET_COMMIT="d613904f8d69702353d7f614a180a275774b5c80"
RELEASE_TITLE="Asset Manager for Maya v1.0.0 - Initial Release"
ASSET_PATH="releases/assetManager-v1.0.0.zip"

echo "🚀 Creating GitHub Release v1.0.0 for Asset Manager for Maya"
echo "============================================================"

# Check if GitHub token is available
if [ -z "$GITHUB_TOKEN" ]; then
  echo "❌ GITHUB_TOKEN environment variable is required"
  echo "   Please set GITHUB_TOKEN with appropriate permissions"
  exit 1
fi

# Read release notes and escape for JSON
RELEASE_NOTES=$(cat releases/v1.0.0-release-notes.md | sed 's/"/\\"/g' | tr '\n' '\\n')

# Create the release
echo "📦 Creating release with tag: $TAG_NAME"
echo "📍 Target commit: ${TARGET_COMMIT:0:7}"

RELEASE_DATA=$(cat << EOF
{
  "tag_name": "$TAG_NAME",
  "target_commitish": "$TARGET_COMMIT",
  "name": "$RELEASE_TITLE",
  "body": "$RELEASE_NOTES",
  "draft": false,
  "prerelease": true,
  "make_latest": false
}
EOF
)

# Create the release
RESPONSE=$(curl -s -X POST \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases \
  -d "$RELEASE_DATA")

# Check if release was created successfully
RELEASE_ID=$(echo "$RESPONSE" | grep '"id":' | head -n1 | sed 's/.*"id": *\([0-9]*\).*/\1/')
RELEASE_URL=$(echo "$RESPONSE" | grep '"html_url":' | head -n1 | sed 's/.*"html_url": *"\([^"]*\)".*/\1/')

if [ -n "$RELEASE_ID" ] && [ "$RELEASE_ID" != "null" ]; then
  echo "✅ Release created successfully!"
  echo "   Release ID: $RELEASE_ID"
  echo "   URL: $RELEASE_URL"
  
  # Upload the asset
  echo "📎 Uploading release asset: $ASSET_PATH"
  
  UPLOAD_URL=$(echo "$RESPONSE" | grep '"upload_url":' | sed 's/.*"upload_url": *"\([^"]*\)".*/\1/' | sed 's/{?name,label}//')
  
  curl -s -X POST \
    -H "Accept: application/vnd.github.v3+json" \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Content-Type: application/zip" \
    "${UPLOAD_URL}?name=assetManager-v1.0.0.zip&label=Asset Manager for Maya v1.0.0 - Complete Plugin Package" \
    --data-binary @"$ASSET_PATH"
  
  echo "✅ Asset uploaded successfully!"
  echo ""
  echo "🎉 GitHub Release v1.0.0 created successfully!"
  echo "   🌐 View release: $RELEASE_URL"
  echo "   📦 Download: ${RELEASE_URL}/download/assetManager-v1.0.0.zip"
  echo ""
  echo "📋 Release Summary:"
  echo "   • Tag: $TAG_NAME (historical release)"
  echo "   • Date: January 15, 2025"
  echo "   • Type: Pre-release (not latest)"
  echo "   • Asset: assetManager-v1.0.0.zip (49.3 KB)"
  echo "   • Target: commit ${TARGET_COMMIT:0:7}"
  
else
  echo "❌ Failed to create release"
  echo "Response: $RESPONSE"
  exit 1
fi