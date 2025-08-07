# v1.0.0 Release Creation Guide

## Git Tag Information
- **Tag**: v1.0.0
- **Target Commit**: d613904f8d69702353d7f614a180a275774b5c80
- **Message**: Asset Manager for Maya v1.0.0 - Initial Release

## GitHub Release Details
- **Title**: Asset Manager for Maya v1.0.0 - Initial Release
- **Tag**: v1.0.0 (will be created from target commit)
- **Target**: main branch (commit d613904)
- **Release Type**: Historical release (not latest)
- **Asset**: assetManager-v1.0.0.zip (49,275 bytes)

## Release Description
The release description will be taken from `releases/v1.0.0-release-notes.md`.

## Creation Status
- [x] Git tag created locally (v1.0.0 -> d613904)
- [x] Release asset prepared (/tmp/assetManager-v1.0.0.zip)
- [x] Release notes available (releases/v1.0.0-release-notes.md)
- [ ] GitHub tag and release created
- [ ] Release asset attached
- [ ] Release marked as historical

## Tag Details Created
```bash
git tag -a v1.0.0 d613904 -m "Asset Manager for Maya v1.0.0 - Initial Release"
```

Target commit: d613904f8d69702353d7f614a180a275774b5c80
Commit message: "Fixed markdown formatting for documentation"
Author: Mike Stumbo <43553625+mikestumbo@users.noreply.github.com>
Date: Thu Aug 7 14:34:40 2025 -0700

## Instructions for Manual Creation
If automated creation fails, create the release manually:
1. Go to https://github.com/mikestumbo/assetManagerforMaya/releases/new
2. Enter tag version: v1.0.0
3. Target: main branch (d613904)
4. Title: Asset Manager for Maya v1.0.0 - Initial Release
5. Description: Copy from releases/v1.0.0-release-notes.md
6. Attach: releases/assetManager-v1.0.0.zip
7. Check "Set as a pre-release" (for historical marking)
8. Publish release