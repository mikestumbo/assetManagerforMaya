#!/bin/bash

# Validation script for GitHub Release v1.1.0 components
# Verifies all required files and git tag are ready

echo "🔍 Validating GitHub Release v1.1.0 components..."
echo ""

EXIT_CODE=0

# Check git tag exists
echo "📍 Checking git tag v1.1.0..."
if git tag -l | grep -q "v1.1.0"; then
    TAG_COMMIT=$(git rev-list -n 1 v1.1.0)
    echo "   ✅ Tag v1.1.0 exists, points to commit: ${TAG_COMMIT:0:7}"
    
    # Check if it points to the expected commit
    EXPECTED_COMMIT="2af1924c499b90b41c2e6b2208c3f6a14c048f27"
    if [ "${TAG_COMMIT}" = "${EXPECTED_COMMIT}" ]; then
        echo "   ✅ Tag points to correct commit (2af1924)"
    else
        echo "   ⚠️  Tag points to ${TAG_COMMIT:0:7}, expected 2af1924"
    fi
else
    echo "   ❌ Tag v1.1.0 not found"
    EXIT_CODE=1
fi

# Check release notes file
echo ""
echo "📄 Checking release notes..."
RELEASE_NOTES="releases/v1.1.0-release-notes.md"
if [ -f "$RELEASE_NOTES" ]; then
    SIZE=$(stat -c%s "$RELEASE_NOTES")
    LINES=$(wc -l < "$RELEASE_NOTES")
    echo "   ✅ Release notes found: $RELEASE_NOTES ($SIZE bytes, $LINES lines)"
    
    # Check for key content
    if grep -q "Enhanced Organization" "$RELEASE_NOTES"; then
        echo "   ✅ Contains 'Enhanced Organization' title"
    else
        echo "   ⚠️  Missing 'Enhanced Organization' in title"
    fi
    
    if grep -q "March 10, 2025" "$RELEASE_NOTES"; then
        echo "   ✅ Contains correct release date"
    else
        echo "   ⚠️  Missing or incorrect release date"
    fi
    
    if grep -q "Asset Tagging System" "$RELEASE_NOTES"; then
        echo "   ✅ Contains Asset Tagging System feature"
    else
        echo "   ⚠️  Missing Asset Tagging System feature"
    fi
else
    echo "   ❌ Release notes file not found: $RELEASE_NOTES"
    EXIT_CODE=1
fi

# Check release asset file
echo ""
echo "📦 Checking release asset..."
ASSET_FILE="releases/assetManager-v1.1.0.zip"
if [ -f "$ASSET_FILE" ]; then
    SIZE=$(stat -c%s "$ASSET_FILE")
    echo "   ✅ Asset file found: $ASSET_FILE ($SIZE bytes)"
    
    # Check if it's a valid zip file
    if file "$ASSET_FILE" | grep -q "Zip archive"; then
        echo "   ✅ Valid ZIP archive format"
    else
        echo "   ⚠️  File may not be a valid ZIP archive"
    fi
    
    # Check size is reasonable (should be around 51KB)
    if [ "$SIZE" -gt 40000 ] && [ "$SIZE" -lt 100000 ]; then
        echo "   ✅ File size is reasonable ($SIZE bytes)"
    else
        echo "   ⚠️  File size seems unusual ($SIZE bytes)"
    fi
else
    echo "   ❌ Asset file not found: $ASSET_FILE"
    EXIT_CODE=1
fi

# Summary
echo ""
echo "📋 Validation Summary:"
if [ $EXIT_CODE -eq 0 ]; then
    echo "   ✅ All components ready for GitHub Release v1.1.0"
    echo ""
    echo "🚀 Ready to create release with:"
    echo "   - Tag: v1.1.0 → commit 2af1924"
    echo "   - Title: Asset Manager for Maya v1.1.0 - Enhanced Organization"
    echo "   - Notes: releases/v1.1.0-release-notes.md"
    echo "   - Asset: releases/assetManager-v1.1.0.zip"
    echo ""
    echo "Next steps:"
    echo "   1. Run: ./create_v110_release.sh"
    echo "   2. Or follow: RELEASE_v1.1.0_INSTRUCTIONS.md"
else
    echo "   ❌ Some components are missing or invalid"
    echo "   Please fix the issues above before creating the release"
fi

exit $EXIT_CODE