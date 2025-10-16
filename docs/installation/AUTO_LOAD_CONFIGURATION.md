# Asset Manager v1.3.0 - Auto-Load Configuration

## ✅ What Was Added

DRAG&DROP.mel now automatically configures Asset Manager to be available on Maya startup through the `userSetup.py` mechanism.

---

## 🔧 How It Works

### Auto-Load Configuration

When you run DRAG&DROP.mel, it now:

1. **Checks for existing `userSetup.py`** in Maya scripts directory
2. **Adds Asset Manager path** to Python sys.path automatically
3. **Preserves existing userSetup.py** content (if present)
4. **Provides optional auto-launch** code (commented out by default)

### userSetup.py Location

The configuration is added to:

```text
~/Documents/maya/scripts/userSetup.py
  OR
~/OneDrive/Documents/maya/scripts/userSetup.py
```

### What Gets Added

```python
# Asset Manager v1.3.0 - Auto-load Configuration
# Added by DRAG&DROP.mel installer
import sys
from pathlib import Path

asset_manager_path = r'C:\Users\...\maya\scripts\assetManager'
if asset_manager_path not in sys.path:
    sys.path.insert(0, asset_manager_path)
    print('[OK] Asset Manager v1.3.0 path added - Ready for use')

# Optional: Uncomment to auto-launch Asset Manager on Maya startup
# try:
#     import assetManager
#     assetManager.show_asset_manager()
#     print('[OK] Asset Manager v1.3.0 launched automatically')
# except Exception as e:
#     print('[ERROR] Asset Manager auto-launch failed:', str(e))
```

---

## 🎯 Benefits

### Always Available

- ✅ **No manual path setup** required
- ✅ **Works across Maya sessions**
- ✅ **Survives Maya updates** (version-independent scripts location)
- ✅ **Ready to import** immediately after Maya starts

### Professional Workflow

```python
# After Maya startup, this just works:
import assetManager
assetManager.show_asset_manager()
```

### Optional Auto-Launch

Users can uncomment the auto-launch section if they want Asset Manager to open automatically when Maya starts.

---

## 🔍 Verification

### Check Auto-Load Status

After running DRAG&DROP.mel, verify in Maya Script Editor:

```python
# Check if Asset Manager is in path
import sys
asset_manager_in_path = any('assetManager' in p for p in sys.path)
print(f"Asset Manager in path: {asset_manager_in_path}")

# Test import
try:
    import assetManager
    print("✅ Asset Manager module available!")
except ImportError as e:
    print(f"❌ Import failed: {e}")
```

### Check userSetup.py Content

```python
# View what was added to userSetup.py
import maya.cmds as cmds
scripts_dir = cmds.internalVar(userScriptDir=True)
userSetup_path = scripts_dir + 'userSetup.py'

try:
    with open(userSetup_path, 'r') as f:
        content = f.read()
        if 'Asset Manager v1.3.0' in content:
            print("✅ Auto-load configured in userSetup.py")
            print("\nConfigured section:")
            for line in content.split('\n'):
                if 'Asset Manager' in line or 'asset_manager' in line:
                    print(f"  {line}")
        else:
            print("⚠️ Asset Manager not found in userSetup.py")
except FileNotFoundError:
    print("❌ userSetup.py not found")
```

---

## 📋 Installation Output

When you run DRAG&DROP.mel, you'll see:

```text
Starting Professional Asset Manager Installer...
Asset Manager Professional Installer v1.3.0
...
Creating professional shelf button...
Professional button created with custom icons!
Configuring auto-load on Maya startup...
Configuring auto-load for Asset Manager...
Existing userSetup.py found, checking content...
  OR
Creating new userSetup.py with Asset Manager auto-load...
[OK] Asset Manager auto-load added to userSetup.py
  OR
[OK] Asset Manager auto-load already configured
[OK] Auto-load configuration complete
===========================================
PROFESSIONAL INSTALLATION COMPLETE!
===========================================
Asset Manager v1.3.0 installed successfully
Professional icons and EMSA architecture ready
Module activated for immediate use
Auto-load enabled for Maya startup
Professional shelf button created
===========================================
READY FOR PRODUCTION USE!
===========================================
```

---

## 🔄 Manual Configuration

### To Enable Auto-Launch

Edit your `userSetup.py` and uncomment these lines:

```python
# Change from:
# try:
#     import assetManager
#     assetManager.show_asset_manager()

# To:
try:
    import assetManager
    assetManager.show_asset_manager()
```

### To Disable Auto-Load

Remove or comment out the Asset Manager section in `userSetup.py`:

```python
# Comment out or delete this section:
# # Asset Manager v1.3.0 - Auto-load Configuration
# import sys
# asset_manager_path = r'...'
# if asset_manager_path not in sys.path:
#     sys.path.insert(0, asset_manager_path)
```

---

## ⚙️ Advanced: Multiple Maya Versions

The auto-load configuration is added to the **version-independent** scripts directory, so it works across all Maya versions (2025.1, 2025.2, 2025.3, etc.).

If you need version-specific configuration:

1. Copy the Asset Manager section from general `userSetup.py`
2. Paste into version-specific `userSetup.py`:

   ```text
   ~/Documents/maya/2025.3/scripts/userSetup.py
   ```

---

## 🐛 Troubleshooting

### Asset Manager Not Available After Restart

**Check 1**: Verify userSetup.py exists

```python
import maya.cmds as cmds
print(cmds.internalVar(userScriptDir=True) + 'userSetup.py')
```

**Check 2**: Check Maya startup messages

- Look for `[OK] Asset Manager v1.3.0 path added` in Script Editor after Maya starts

**Check 3**: Verify path in userSetup.py

```python
import os
scripts_dir = cmds.internalVar(userScriptDir=True)
userSetup_path = scripts_dir + 'userSetup.py'
if os.path.exists(userSetup_path):
    with open(userSetup_path) as f:
        print(f.read())
```

### Re-run Installer

If auto-load isn't working, simply run DRAG&DROP.mel again. It will:

- Detect existing configuration
- Update if needed
- Report status

---

## 📊 Comparison: Before vs After

### Before (Manual)

```python
# User had to do this every Maya session:
import sys
sys.path.insert(0, r'C:\...\maya\scripts\assetManager')
import assetManager
assetManager.show_asset_manager()
```

### After (Automatic)

```python
# Now just do this (or click shelf button):
import assetManager
assetManager.show_asset_manager()
```

---

## ✅ Summary

**What Changed**:

- ✅ DRAG&DROP.mel now configures auto-load
- ✅ Creates/updates `userSetup.py` automatically
- ✅ Adds Asset Manager to Python path on startup
- ✅ Preserves existing userSetup.py content
- ✅ Optional auto-launch (commented by default)

**Benefits**:

- ✅ Professional installation experience
- ✅ Works immediately after Maya restart
- ✅ No manual configuration required
- ✅ Survives Maya updates
- ✅ Version-independent

**Next Maya Startup**:

```text
[OK] Asset Manager v1.3.0 path added - Ready for use
```

**Production Ready**: Yes! Auto-load makes Asset Manager truly plug-and-play.

---

*Auto-Load Feature Added: September 30, 2025*  
*Asset Manager v1.3.0 - Professional Installation*
