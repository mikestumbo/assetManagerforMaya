# GitHub Releases Setup Instructions

This document provides instructions for setting up GitHub Releases for the Asset Manager for Maya project.

## 📦 Release Archives Created

The following release archives have been prepared:

- `assetManager-v1.0.0.zip` - Initial Release (January 15, 2025)
- `assetManager-v1.1.0.zip` - Enhanced Organization (March 10, 2025)
- `assetManager-v1.1.1.zip` - Visual Organization (May 22, 2025)
- `assetManager-v1.1.2.zip` - Collection Tabs & Customization (July 29, 2025)

## 🚀 Creating GitHub Releases

### For v1.0.0 (Initial Release)

1. Go to your GitHub repository
2. Click on "Releases" in the right sidebar
3. Click "Create a new release"
4. **Tag version**: `v1.0.0`
5. **Release title**: `Asset Manager for Maya v1.0.0 - Initial Release`
6. **Description**: Copy content from `releases/v1.0.0-release-notes.md`
7. **Attach files**: Upload `releases/assetManager-v1.0.0.zip`
8. Check "Set as a pre-release" if desired
9. Click "Publish release"

### For v1.1.0 (Enhanced Organization)

1. Create a new release
2. **Tag version**: `v1.1.0`
3. **Release title**: `Asset Manager for Maya v1.1.0 - Enhanced Organization`
4. **Description**: Copy content from `releases/v1.1.0-release-notes.md`
5. **Attach files**: Upload `releases/assetManager-v1.1.0.zip`
6. Click "Publish release"

### For v1.1.1 (Visual Organization)

1. Create a new release
2. **Tag version**: `v1.1.1`
3. **Release title**: `Asset Manager for Maya v1.1.1 - Visual Organization`
4. **Description**: Copy content from `releases/v1.1.1-release-notes.md`
5. **Attach files**: Upload `releases/assetManager-v1.1.1.zip`
6. Click "Publish release"

### For v1.1.2 (Collection Tabs & Customization)

1. Create a new release
2. **Tag version**: `v1.1.2`
3. **Release title**: `Asset Manager for Maya v1.1.2 - Collection Tabs & Customization`
4. **Description**: Copy content from `releases/v1.1.2-release-notes.md`
5. **Attach files**: Upload `releases/assetManager-v1.1.2.zip`
6. Check "Set as the latest release"
7. Click "Publish release"

## 📝 Release Notes

Each release has detailed release notes prepared:

- `v1.0.0-release-notes.md` - Initial release features and setup
- `v1.1.0-release-notes.md` - Enhanced organization features
- `v1.1.1-release-notes.md` - Visual enhancement features
- `v1.1.2-release-notes.md` - Collection tabs and customization features

## 🗂️ After Creating Releases

1. **Update README.md**: The README has been updated to reference GitHub Releases
2. **Remove releases folder**: After creating GitHub releases, you can remove the local `releases/` folder
3. **Update links**: Verify that release links in README.md work correctly

## 🔗 Benefits of GitHub Releases

- **Clean Repository**: Removes large version archives from main codebase
- **Proper Versioning**: Git tags for each release
- **Download Statistics**: Track how many times each version is downloaded
- **Release Notes**: Formatted release notes with markdown support
- **Asset Management**: Attach multiple files (zips, documentation, etc.)
- **API Access**: Programmatic access to releases via GitHub API

## 🚨 Important Notes

- Create releases in chronological order (oldest first)
- Use semantic versioning for tags (v1.0.0, v1.1.0, etc.)
- Mark the latest stable version as "Latest release"
- Include comprehensive release notes for each version
- Attach the complete plugin archive for easy downloads

---

After setting up GitHub Releases, users can easily download any version and view detailed release notes directly from GitHub.
