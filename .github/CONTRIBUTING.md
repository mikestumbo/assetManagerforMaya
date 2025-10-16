# Contributing to Asset Manager for Maya

First off, thank you for considering contributing to Asset Manager for Maya! It's people like you that make this tool better for the entire Maya community. 🎬

## Table of Contents

* [Code of Conduct](#code-of-conduct)
* [Getting Started](#getting-started)
* [Development Setup](#development-setup)
* [How Can I Contribute?](#how-can-i-contribute)
* [Coding Standards](#coding-standards)
* [Commit Message Guidelines](#commit-message-guidelines)
* [Pull Request Process](#pull-request-process)
* [Testing](#testing)
* [Documentation](#documentation)

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to [mikestumbo@github].

## Getting Started

### Prerequisites

* Autodesk Maya 2025 or later
* Python 3.10+ (included with Maya 2025+)
* PySide6 (included with Maya 2025+)
* Git for version control

### Recommended Knowledge

* Python programming
* Maya Python API (maya.cmds, OpenMaya)
* PySide6/Qt for UI development
* Character rigging concepts (for USD pipeline features)
* USD (Universal Scene Description) - optional but helpful

## Development Setup

1. **Fork the Repository**

   ```bash
   # Fork via GitHub UI, then clone your fork
   git clone https://github.com/YOUR_USERNAME/assetManagerforMaya.git
   cd assetManagerforMaya
   ```

2. **Install in Maya Development Mode**

   ```python
   # In Maya Script Editor (Python):
   import sys
   sys.path.append(r'C:\path\to\assetManagerforMaya')
   
   import assetManager
   assetManager.show()
   ```

3. **Create a Branch**

   ```bash
   git checkout -b feature/my-new-feature
   # or
   git checkout -b bugfix/issue-123-fix-description
   ```

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates. When you create a bug report, include as many details as possible using our [bug report template](.github/ISSUE_TEMPLATE/bug_report.md).

**Include:**

* Maya version and operating system
* Steps to reproduce
* Expected vs actual behavior
* Screenshots if applicable
* Error messages or console output

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. Use our [feature request template](.github/ISSUE_TEMPLATE/feature_request.md) and provide:

* Clear use case description
* Why this would be useful to Maya users
* Proposed implementation (if you have ideas)
* Examples from other tools (if relevant)

### Pull Requests

1. **Keep PRs Focused**: One feature/fix per PR
2. **Update Documentation**: If you change functionality, update README.md
3. **Add Tests**: Include tests for new features (see `tests/` directory)
4. **Follow Code Style**: Match existing code formatting
5. **Update CHANGELOG**: Add entry to CHANGELOG.md

## Coding Standards

### Python Style Guide

We follow **PEP 8** with these specific guidelines:

```python
# Class names: PascalCase
class AssetLibrary:
    pass

# Function/method names: snake_case
def load_asset(self, asset_path):
    pass

# Constants: UPPER_CASE
MAX_THUMBNAIL_SIZE = 512

# Private methods: Leading underscore
def _internal_helper(self):
    pass
```

### Clean Code Principles

This project emphasizes Clean Code and SOLID principles:

* **Single Responsibility Principle**: Each class/function does ONE thing
* **Descriptive Names**: Variables/functions should explain their purpose
* **Small Functions**: Keep functions focused and under 50 lines when possible
* **DRY (Don't Repeat Yourself)**: Extract common logic into reusable functions
* **YAGNI (You Aren't Gonna Need It)**: Don't add features "just in case"
* **Minimize Side Effects**: Functions should be predictable

### Maya-Specific Guidelines

```python
# Good: Use context managers for undo chunks
import maya.cmds as cmds

def import_asset(asset_path):
    """Import asset with undo support."""
    cmds.undoInfo(openChunk=True, chunkName="Import Asset")
    try:
        # Import operations
        result = cmds.file(asset_path, i=True, returnNewNodes=True)
        return result
    finally:
        cmds.undoInfo(closeChunk=True)

# Good: Error handling for Maya operations
try:
    selection = cmds.ls(selection=True)
    if not selection:
        raise ValueError("No objects selected")
except Exception as e:
    cmds.warning(f"Operation failed: {e}")
    return None
```

### UI Development (PySide6)

```python
from PySide6 import QtWidgets, QtCore

class MyWidget(QtWidgets.QWidget):
    """Widget description."""
    
    # Use signals for communication
    asset_loaded = QtCore.Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Create UI elements."""
        pass
    
    def _connect_signals(self):
        """Connect signals and slots."""
        pass
```

## Commit Message Guidelines

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**

* `feat:` New feature
* `fix:` Bug fix
* `docs:` Documentation changes
* `style:` Code formatting (no logic change)
* `refactor:` Code restructuring (no feature change)
* `test:` Adding or updating tests
* `chore:` Maintenance tasks

**Examples:**

```text
feat(usd): Add UsdSkel skin cluster export

Implement Maya skin cluster extraction and conversion to USD
skeletal animation format. Preserves joint weights and bind poses.

Closes #42
```

```text
fix(ui): Resolve thumbnail cache refresh issue

Thumbnails now properly regenerate when source files are modified.
Added cache invalidation logic based on file modification times.

Fixes #38
```

## Pull Request Process

1. **Update Documentation**
   * Update README.md if user-facing changes
   * Add docstrings to new functions/classes
   * Update CHANGELOG.md with your changes

2. **Ensure Tests Pass**
   * Run existing tests: `python -m pytest tests/`
   * Add tests for new features
   * Test in Maya 2025+ manually

3. **Get Code Review**
   * At least one maintainer approval required
   * Address review comments
   * Keep discussions professional and constructive

4. **Squash Commits** (if requested)
   * Combine multiple commits into logical units
   * Keep commit history clean

5. **Merge**
   * Maintainer will merge when approved
   * Delete your branch after merge

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_asset_library.py

# Run with coverage
python -m pytest --cov=src tests/
```

### Writing Tests

```python
import pytest
from src.services.asset_library_service import AssetLibraryService

def test_asset_detection():
    """Test that Maya files are properly detected."""
    service = AssetLibraryService()
    assets = service.scan_directory("test_assets/")
    
    assert len(assets) > 0
    assert any(a.file_path.endswith('.mb') for a in assets)

@pytest.fixture
def temp_maya_file(tmp_path):
    """Create temporary Maya file for testing."""
    test_file = tmp_path / "test.mb"
    # Create test file
    return test_file
```

### Manual Testing in Maya

1. Load the plugin in Maya
2. Test the specific feature you changed
3. Check error messages in Script Editor
4. Verify UI updates correctly
5. Test with different Maya scenes

## Documentation

### Code Documentation

```python
def export_to_usd(maya_scene, output_path, options=None):
    """
    Export Maya scene to USD format with rigging data.
    
    Args:
        maya_scene (str): Path to source Maya file
        output_path (str): Destination USD file path
        options (dict, optional): Export options:
            - include_rigging (bool): Export skin clusters
            - include_materials (bool): Convert materials
            - material_format (str): 'preview' or 'renderman'
    
    Returns:
        bool: True if export succeeded, False otherwise
    
    Raises:
        ValueError: If maya_scene doesn't exist
        RuntimeError: If USD export fails
    
    Example:
        >>> export_to_usd(
        ...     'character.mb',
        ...     'character.usd',
        ...     {'include_rigging': True}
        ... )
        True
    """
    pass
```

### README Updates

When adding new features, update:

* Features list
* Screenshots (if UI changed)
* Installation steps (if changed)
* Usage examples

## Questions?

* **General Questions**: Open a [discussion](https://github.com/mikestumbo/assetManagerforMaya/discussions)
* **Bug Reports**: Use [bug report template](.github/ISSUE_TEMPLATE/bug_report.md)
* **Feature Ideas**: Use [feature request template](.github/ISSUE_TEMPLATE/feature_request.md)

## Recognition

Contributors will be recognized in:

* CHANGELOG.md for their contributions
* README.md contributors section
* GitHub's automatic contributor tracking

---

## Additional Resources

* [Maya Python API Documentation](https://help.autodesk.com/view/MAYAUL/2025/ENU/)
* [PySide6 Documentation](https://doc.qt.io/qtforpython-6/)
* [USD Documentation](https://openusd.org/)
* [Clean Code Principles](docs/MAYA_CODING_STANDARDS.md)

---

**Thank you for contributing to making Asset Manager for Maya better for everyone!** 🎬✨
