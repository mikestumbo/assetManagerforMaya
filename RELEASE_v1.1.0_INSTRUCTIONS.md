# GitHub Release v1.1.0 Creation Instructions

This document provides step-by-step instructions for creating the GitHub Release v1.1.0 for Asset Manager for Maya.

## Prerequisites

- Repository access to `mikestumbo/assetManagerforMaya`
- GitHub CLI (`gh`) installed and authenticated, OR access to GitHub web interface
- Git access to push tags

## Automated Script Method

A script `create_v110_release.sh` has been created to automate the process:

```bash
./create_v110_release.sh
```

## Manual Method

### Step 1: Create and Push Git Tag

The git tag has already been created locally. To push it:

```bash
git push origin v1.1.0
```

**Tag Details:**
- Name: `v1.1.0`
- Target Commit: `2af1924c499b90b41c2e6b2208c3f6a14c048f27`
- Date: March 10, 2025 (historical release)

### Step 2: Create GitHub Release via CLI

```bash
gh release create v1.1.0 \
    --title "Asset Manager for Maya v1.1.0 - Enhanced Organization" \
    --notes-file "releases/v1.1.0-release-notes.md" \
    --target "2af1924c499b90b41c2e6b2208c3f6a14c048f27" \
    "releases/assetManager-v1.1.0.zip"
```

### Step 3: Create GitHub Release via Web Interface

1. Go to https://github.com/mikestumbo/assetManagerforMaya/releases
2. Click "Create a new release"
3. Fill in the following details:

**Release Form Fields:**
- **Tag**: `v1.1.0` 
- **Target**: Select commit `2af1924` (Initial commit of Asset Manager for Maya)
- **Release title**: `Asset Manager for Maya v1.1.0 - Enhanced Organization`
- **Description**: Copy content from `releases/v1.1.0-release-notes.md`
- **Assets**: Upload `releases/assetManager-v1.1.0.zip`
- **Pre-release**: ☐ (unchecked)
- **Latest release**: ☐ (unchecked, since this is historical)

## Release Content Summary

### Release Title
Asset Manager for Maya v1.1.0 - Enhanced Organization

### Release Date  
March 10, 2025 (Historical Release)

### Major Features Included
- **🏷️ Asset Tagging System**: Custom labels, tag filtering, quick tagging via right-click
- **📦 Asset Collections/Sets**: Grouping assets like "Character Props" and "Environment Kit"  
- **🔗 Asset Dependencies Tracking**: Dependency mapping with visual representation
- **⚡ Batch Operations**: Batch import/export with progress tracking
- **📊 Asset Versioning**: Version tracking, notes, and complete history
- **Enhanced Context Menus**: Right-click asset management
- **Advanced Filtering**: Filter by tags, collections, and more
- **Management Dialogs**: Dedicated windows for collections and dependencies

### Assets
- **assetManager-v1.1.0.zip** (51,397 bytes) - Complete plugin package

### Backward Compatibility
- Fully compatible with v1.0.0 projects
- All v1.0.0 features remain unchanged  
- New features are additive, not replacement
- Configuration automatically upgrades

## Verification

After creating the release, verify:
1. ✅ Release appears at https://github.com/mikestumbo/assetManagerforMaya/releases/tag/v1.1.0
2. ✅ Release title and description match specifications
3. ✅ assetManager-v1.1.0.zip is attached and downloadable
4. ✅ Release is dated March 10, 2025
5. ✅ Tag `v1.1.0` points to commit `2af1924`

## Files Prepared
- `releases/v1.1.0-release-notes.md` - Complete release notes
- `releases/assetManager-v1.1.0.zip` - Release package (51KB)
- Git tag `v1.1.0` created and ready to push