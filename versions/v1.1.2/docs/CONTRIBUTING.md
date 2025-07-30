# Contributing to Asset Manager for Maya

Thank you for your interest in contributing to Asset Manager for Maya! This document provides guidelines for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Changelog Guidelines](#changelog-guidelines)
- [Development Workflow](#development-workflow)
- [Pull Request Process](#pull-request-process)

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for all contributors.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Create a new branch for your feature or fix
4. Make your changes
5. Test your changes
6. Update the changelog (see below)
7. Submit a pull request

## Changelog Guidelines

We follow the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format and [Semantic Versioning](https://semver.org/spec/v2.0.0.html) for version management.

### Adding Changelog Entries

**For every contribution, you MUST update the `CHANGELOG.md` file:**

1. **Location**: Add entries to the `[Unreleased]` section at the top of the changelog
2. **Categories**: Use the appropriate category for your change:
   - `Added` for new features
   - `Changed` for changes in existing functionality
   - `Deprecated` for soon-to-be removed features
   - `Removed` for now removed features
   - `Fixed` for any bug fixes
   - `Security` in case of vulnerabilities

3. **Format**: Use clear, concise descriptions that explain the change from a user's perspective

#### Example Changelog Entry

```markdown
## [Unreleased]

### Added in Unreleased

- New asset preview functionality with thumbnail generation
- Support for additional file formats (.abc, .usd)

### Changed in Unreleased

- Improved UI responsiveness for large asset libraries
- Updated Python dependency requirements

### Fixed in Unreleased

- Fixed crash when importing corrupted asset files
- Resolved memory leak in asset browser
```

### Release Process

When preparing a release, maintainers will:

1. **Move entries** from `[Unreleased]` to a new version section
2. **Add version number** following semantic versioning (e.g., `[1.1.0]`)
3. **Add release date** in ISO format (YYYY-MM-DD)
4. **Reset `[Unreleased]`** section with empty categories
5. **Update version links** at the bottom of the changelog

#### Version Numbering Guidelines

- **Major (X.0.0)**: Breaking changes or major new features
- **Minor (0.X.0)**: New features that are backward compatible
- **Patch (0.0.X)**: Bug fixes and small improvements

### Changelog Maintenance Checklist

Before submitting a pull request, ensure:

- [ ] Changes are documented in the `[Unreleased]` section
- [ ] Entry is in the correct category (Added, Changed, Fixed, etc.)
- [ ] Description is clear and user-focused
- [ ] No breaking changes are undocumented
- [ ] Links and references are valid

## Development Workflow

1. **Branch naming**: Use descriptive names like `feature/asset-preview` or `fix/memory-leak`
2. **Commit messages**: Write clear, descriptive commit messages
3. **Testing**: Ensure your changes work with Maya 2025.3+
4. **Documentation**: Update relevant documentation if needed

## Pull Request Process

1. **Title**: Use a descriptive title that summarizes the change
2. **Description**: Explain what the change does and why it's needed
3. **Changelog**: Confirm the changelog has been updated
4. **Testing**: Describe how the change was tested
5. **Breaking Changes**: Clearly identify any breaking changes

### Pull Request Template

```markdown
## Description
Brief description of the change and motivation.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
Describe the tests you ran and how to reproduce them.

## Changelog
- [ ] I have updated the CHANGELOG.md file with my changes
- [ ] My changes are documented in the correct category

## Checklist
- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my code
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have tested my changes with Maya 2025.3+
```

## Questions or Issues?

If you have questions about contributing or encounter issues:

1. Check existing [issues](https://github.com/mikestumbo/assetManagerforMaya/issues)
2. Create a new issue with detailed information
3. Tag maintainers if urgent

## Additional Resources

- [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
- [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
- [Maya Plugin Development](https://help.autodesk.com/view/MAYAUL/2025/ENU/)
- [PySide6 Documentation](https://doc.qt.io/qtforpython/)

Thank you for contributing to Asset Manager for Maya! 🎉
