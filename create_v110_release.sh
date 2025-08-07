#!/bin/bash

# Script to create GitHub Release v1.1.0 for Asset Manager for Maya
# This script should be run by someone with repository access

set -e

echo "Creating GitHub Release v1.1.0 for Asset Manager for Maya..."

# Repository details
REPO_OWNER="mikestumbo"
REPO_NAME="assetManagerforMaya"
TAG_NAME="v1.1.0"
RELEASE_NAME="Asset Manager for Maya v1.1.0 - Enhanced Organization"
TARGET_COMMIT="2af1924c499b90b41c2e6b2208c3f6a14c048f27"

# Files needed
RELEASE_NOTES_FILE="releases/v1.1.0-release-notes.md"
ASSET_FILE="releases/assetManager-v1.1.0.zip"

# Verify files exist
if [ ! -f "$RELEASE_NOTES_FILE" ]; then
    echo "Error: Release notes file not found: $RELEASE_NOTES_FILE"
    exit 1
fi

if [ ! -f "$ASSET_FILE" ]; then
    echo "Error: Asset file not found: $ASSET_FILE"
    exit 1
fi

echo "✅ Release notes file found: $RELEASE_NOTES_FILE"
echo "✅ Asset file found: $ASSET_FILE ($(stat -c%s "$ASSET_FILE") bytes)"

# Step 1: Create and push the git tag
echo "Step 1: Creating and pushing git tag..."
git tag -a "$TAG_NAME" "$TARGET_COMMIT" -m "Asset Manager for Maya v1.1.0 - Enhanced Organization

Release Date: March 10, 2025

Major features:
- Asset Tagging System with custom labels and filtering
- Asset Collections/Sets for grouping assets  
- Asset Dependencies Tracking with visual representation
- Batch Operations with progress tracking and error reporting
- Asset Versioning with history and notes
- Enhanced Context Menus and Management Dialogs
- Full backward compatibility with v1.0.0" || echo "Tag may already exist"

echo "Pushing tag to GitHub..."
git push origin "$TAG_NAME"

# Step 2: Create GitHub Release using GitHub CLI
echo "Step 2: Creating GitHub Release..."
gh release create "$TAG_NAME" \
    --title "$RELEASE_NAME" \
    --notes-file "$RELEASE_NOTES_FILE" \
    --target "$TARGET_COMMIT" \
    "$ASSET_FILE"

echo "✅ GitHub Release v1.1.0 created successfully!"
echo "📦 Release includes:"
echo "   - Tag: $TAG_NAME"
echo "   - Target: $TARGET_COMMIT"
echo "   - Asset: $ASSET_FILE"
echo "   - Release Notes: $RELEASE_NOTES_FILE"
echo ""
echo "🔗 View the release at: https://github.com/$REPO_OWNER/$REPO_NAME/releases/tag/$TAG_NAME"