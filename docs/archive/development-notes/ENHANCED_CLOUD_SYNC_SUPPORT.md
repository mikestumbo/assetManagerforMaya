# Enhanced Cloud Sync Support - Asset Manager v1.3.0

## Overview

Asset Manager v1.3.0 now includes comprehensive cloud synchronization support across all major platforms, ensuring seamless installation regardless of your cloud storage configuration.

## Supported Cloud Services

### 🪟 Windows - OneDrive Support

- **Primary Path**: `~/OneDrive/Documents/maya/scripts`
- **Fallback Path**: `~/Documents/maya/scripts`
- **Detection**: Automatically detects and prefers OneDrive-synced Documents folder
- **Benefits**: Assets and plugins sync across Windows devices

### 🍎 macOS - iCloud Drive Support

- **Primary Path**: `~/Library/Mobile Documents/com~apple~CloudDocs/Documents/maya/scripts`
- **Secondary Path**: `~/Documents/maya/scripts` (may be iCloud-synced)
- **Fallback Path**: `~/Library/Preferences/Autodesk/maya/scripts`
- **Detection**: Prioritizes iCloud Drive when Desktop & Documents sync is enabled
- **Benefits**: Assets and plugins sync across Mac devices and iOS (where applicable)

### 🐧 Linux - Standard Support

- **Primary Path**: `~/maya/scripts`
- **Detection**: Uses standard Linux Maya directory structure
- **Benefits**: Consistent with Linux Maya conventions

## How It Works

### Intelligent Path Detection

The installer uses a priority-based system to find the best installation location:

1. **Cloud-Synced Locations** (highest priority)
   - Windows: OneDrive Documents
   - macOS: iCloud Drive Documents

2. **Standard Documents Folder** (medium priority)
   - May be cloud-synced transparently by the OS

3. **Maya-Specific Locations** (fallback)
   - Platform-specific Maya preferences/configuration directories

### Installation Process

```python
# The installer automatically:
1. Detects your platform (Windows/macOS/Linux)
2. Checks cloud-synced locations first
3. Falls back to standard locations if needed
4. Creates directories if they don't exist
5. Provides clear feedback about which location is used
```

## Benefits

### For Users

- **Automatic Sync**: Plugins and assets sync across your devices
- **No Configuration**: Works out-of-the-box with default cloud settings
- **Consistent Experience**: Same plugin behavior across all your Maya installations
- **Backup Protection**: Cloud sync provides automatic backup of custom assets

### For Developers

- **Clean Code**: Single installation logic handles all platforms and cloud services
- **Robust Detection**: Multiple fallback options ensure installation always succeeds
- **Clear Feedback**: Detailed logging shows exactly which path was selected
- **Future-Proof**: Easy to extend for new cloud services

## Technical Implementation

### Path Priority Logic (Windows)

```python
possible_bases = [
    home / "OneDrive" / "Documents" / "maya",     # OneDrive sync
    home / "Documents" / "maya"                   # Regular Documents
]
```

### Path Priority Logic (macOS)

```python
possible_bases = [
    home / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Documents" / "maya",  # iCloud Drive
    home / "Documents" / "maya",                                                           # Regular Documents
    home / "Library" / "Preferences" / "Autodesk" / "maya"                               # Maya Preferences
]
```

### Installation Methods

All installation methods use the same enhanced cloud detection:

- `setup.py` (Python installer)
- `DRAG&DROP.mel` (Maya GUI installer)
- `install.bat` (Windows command-line)
- `install.sh` (Unix/Linux/macOS command-line)

## Installation Examples

### Windows with OneDrive

```console
📂 Found existing Maya scripts directory: C:\Users\YourName\OneDrive\Documents\maya\scripts
   ✨ Using OneDrive synced location (Windows)
```

### macOS with iCloud Drive

```console
📂 Found existing Maya scripts directory: /Users/YourName/Library/Mobile Documents/com~apple~CloudDocs/Documents/maya/scripts
   ☁️ Using iCloud Drive synced location (macOS)
```

### Standard Installation

```console
📂 Found existing Maya scripts directory: /Users/YourName/Documents/maya/scripts
   📁 Using Documents folder (may be cloud-synced)
```

## Compatibility

### Maya Versions

- Maya 2022, 2023, 2024, 2025+
- All versions use the same general `maya/scripts` directory

### Operating Systems

- ✅ Windows 10/11 (OneDrive)
- ✅ macOS 10.15+ (iCloud Drive)
- ✅ Linux (standard Maya directories)

### Cloud Services

- ✅ OneDrive (Windows)
- ✅ iCloud Drive (macOS)
- ✅ Google Drive (via Documents folder sync)
- ✅ Dropbox (via Documents folder sync)
- ✅ Any service that syncs the Documents folder

## Troubleshooting

### If Installation Fails

The installer provides detailed error messages showing:

- All paths that were checked
- Whether directories exist or can be created
- Specific permission or access issues

### Manual Path Override

For non-standard configurations, you can still manually specify paths:

```python
installer = AssetManagerInstaller(source_dir="custom/path")
```

### Verification

Run the test script to verify cloud sync support:

```bash
python test_enhanced_cloud.py
```

## Future Enhancements

### Potential Additions

- Dropbox explicit support
- Google Drive explicit support
- OneDrive for Business detection
- Custom cloud path configuration
- Sync status verification

### Extensibility

The modular design makes it easy to add support for new cloud services by extending the `possible_bases` list in `_get_maya_scripts_directory()`.

---

*This enhanced cloud sync support ensures Asset Manager works seamlessly across all your devices and cloud configurations, providing a consistent and reliable Maya plugin experience.*
