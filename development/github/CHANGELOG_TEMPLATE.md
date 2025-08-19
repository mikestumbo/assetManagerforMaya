# Changelog Entry Template

Use this template when adding entries to the CHANGELOG.md file.

## Quick Checklist

Before submitting your pull request:

- [ ] Added entry to `[Unreleased]` section
- [ ] Used correct category (Added, Changed, Deprecated, Removed, Fixed, Security)
- [ ] Entry is clear and user-focused
- [ ] No technical jargon or internal references
- [ ] Breaking changes are clearly marked
- [ ] Entry follows the project's writing style

## Entry Format

```markdown
## [Unreleased]

### [Category] in Unreleased

- Brief, clear description of what changed from user's perspective
- Another change if applicable
```

## Categories

### Added

Use for new features, capabilities, or functionality.

**Examples:**

- New asset preview functionality with thumbnail generation
- Support for additional file formats (.abc, .usd)
- Integration with Maya's native asset browser

### Changed

Use for changes in existing functionality that don't break backward compatibility.

**Examples:**

- Improved UI responsiveness for large asset libraries
- Updated asset import dialog with better error messages
- Enhanced search performance in asset browser

### Deprecated

Use for soon-to-be removed features. Always include timeline and alternatives.

**Examples:**

- Legacy import format support (will be removed in v2.0.0, use new format instead)
- Old API methods marked for removal in next major version

### Removed

Use for now removed features, files, or functionality.

**Examples:**

- Removed support for Maya 2024 and earlier
- Dropped deprecated API methods from v1.x

### Fixed

Use for any bug fixes.

**Examples:**

- Fixed crash when importing corrupted asset files
- Resolved memory leak in asset browser
- Fixed incorrect asset thumbnail generation on Windows

### Security

Use in case of vulnerabilities or security improvements.

**Examples:**

- Fixed potential code injection in asset path validation
- Updated dependencies to address security vulnerabilities

## Writing Guidelines

### Good Examples

✅ **Good**: "Added support for USD file format in asset importer"
✅ **Good**: "Fixed crash when opening assets with special characters in filename"
✅ **Good**: "Improved asset loading performance by 40% for large libraries"

### Bad Examples

❌ **Bad**: "Updated AssetLoader.py"
❌ **Bad**: "Bug fixes"
❌ **Bad**: "Refactored code in src/utils/"

### Key Principles

1. **User-focused**: Describe impact on users, not technical implementation
2. **Specific**: Be concrete about what changed
3. **Action-oriented**: Start with verbs (Added, Fixed, Improved)
4. **Concise**: One line per change when possible
5. **Complete**: Don't leave out important details

## Breaking Changes

If your change breaks backward compatibility:

1. **Mark clearly** in the entry
2. **Explain impact** on existing users
3. **Provide migration path** when possible

**Example:**

```markdown
### Changed in Unreleased

- **BREAKING**: Asset import API now requires explicit format specification. Update calls from `import_asset(path)` to `import_asset(path, format='ma')`. See migration guide for details.
```

## Multiple Changes

Group related changes under a single bullet point when appropriate:

**Example:**

```markdown
### Added in Unreleased

- Asset preview functionality:
  - Thumbnail generation for 3D assets
  - Preview panel in asset browser
  - Customizable preview quality settings
```

## Need Help?

- Check existing changelog entries for style reference
- Ask in pull request if unsure about categorization
- See [CONTRIBUTING.md](CONTRIBUTING.md) for full guidelines
