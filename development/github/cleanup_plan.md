# Master Package Cleanup Plan

## Current State Analysis

### Files to Keep (Core Distribution)

- assetManager.py (main plugin)
- assetManager.mod (plugin descriptor)
- icon_utils.py (utilities)
- DRAG&DROP.mel (installer)
- README.md (main documentation)
- LICENSE (legal)
- version.json (version tracking)
- setup.py (Python installer)
- install.bat (Windows installer)
- install.sh (Unix installer)
- CHANGELOG.md (change history)
- icons/ (icon assets)

### Files to Keep (Development/Contributing)

- CONTRIBUTING.md (contribution guidelines)
- .github/ (GitHub templates)

### Files to Consolidate/Remove

- DRAG_DROP_INSTALL_GUIDE.md (merge into README.md)
- FINAL_PACKAGE_STATUS.md (development artifact - remove)
- plan/ (development planning - move to .github or remove)
- versions/ (version archive - may be redundant)

### Cleanup Actions

1. Merge installation guide into README.md
2. Remove development artifacts
3. Consolidate documentation
4. Organize development files
5. Update references and links

## Post-Cleanup Structure

```markdown
assetManagerforMaya-master/
├── assetManager.py              # Main plugin
├── assetManager.mod             # Plugin descriptor
├── icon_utils.py                # Icon utilities
├── DRAG&DROP.mel                # Primary installer
├── README.md                    # Comprehensive documentation (includes install guide)
├── CHANGELOG.md                 # Change history
├── CONTRIBUTING.md              # Contribution guidelines
├── LICENSE                      # MIT License
├── version.json                 # Version information
├── setup.py                     # Python setup script
├── install.bat                  # Windows installer
├── install.sh                   # Unix installer
├── .github/                     # GitHub templates and workflows
│   ├── CHANGELOG_TEMPLATE.md
│   └── pull_request_template.md
└── icons/                       # Icon assets
    ├── assetManager_icon.png
    ├── assetManager_icon2.png
    └── README.md
```
