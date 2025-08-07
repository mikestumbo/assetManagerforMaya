#!/bin/bash

# GitHub Release Creation Script for v1.0.0
# This script documents the exact API calls needed to create the v1.0.0 release

REPO_OWNER="mikestumbo"
REPO_NAME="assetManagerforMaya"
TAG_NAME="v1.0.0"
TARGET_COMMIT="d613904f8d69702353d7f614a180a275774b5c80"
RELEASE_TITLE="Asset Manager for Maya v1.0.0 - Initial Release"
ASSET_PATH="releases/assetManager-v1.0.0.zip"

echo "=== GitHub Release Creation for v1.0.0 ==="
echo "Repository: ${REPO_OWNER}/${REPO_NAME}"
echo "Tag: ${TAG_NAME}"
echo "Target Commit: ${TARGET_COMMIT}"
echo "Title: ${RELEASE_TITLE}"
echo "Asset: ${ASSET_PATH}"
echo ""

# Read release notes
RELEASE_NOTES=$(cat releases/v1.0.0-release-notes.md)

echo "Release Notes Preview:"
echo "====================="
head -10 releases/v1.0.0-release-notes.md
echo "... (truncated)"
echo ""

echo "GitHub API curl command that would be used:"
echo "curl -X POST \\"
echo "  -H \"Accept: application/vnd.github.v3+json\" \\"
echo "  -H \"Authorization: token \$GITHUB_TOKEN\" \\"
echo "  https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases \\"
echo "  -d '{"
echo "    \"tag_name\": \"${TAG_NAME}\","
echo "    \"target_commitish\": \"${TARGET_COMMIT}\","
echo "    \"name\": \"${RELEASE_TITLE}\","
echo "    \"body\": \"<release_notes_content>\","
echo "    \"draft\": false,"
echo "    \"prerelease\": true"
echo "  }'"

echo ""
echo "=== Manual Creation Instructions ==="
echo "1. Go to: https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/new"
echo "2. Tag version: ${TAG_NAME}"
echo "3. Target: main (commit ${TARGET_COMMIT:0:7})"
echo "4. Release title: ${RELEASE_TITLE}"
echo "5. Description: Copy from releases/v1.0.0-release-notes.md"
echo "6. Attach binary: ${ASSET_PATH}"
echo "7. Check 'Set as a pre-release' (for historical marking)"
echo "8. Click 'Publish release'"