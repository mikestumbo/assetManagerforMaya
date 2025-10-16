# Maya Development Coding Standards & Best Practices

## Asset Manager v1.3.0+ - Clean Code Standards

## 🚨 CRITICAL: Maya Character Encoding Standards

### **Rule #1: NEVER Use Unicode/Emoji in Maya Scripts**

Maya's MEL parser uses `cp1252` codec and **CANNOT** handle Unicode characters.

#### ❌ FORBIDDEN Characters

```text
🎯 🚀 ✅ ❌ ⚠️ ℹ️ 📦 🔧 🎨 📂 📄 🔄 💻 🛤️ 🧹 🎉
Any emoji, Unicode symbols, or extended ASCII characters
```

#### ✅ REQUIRED: ASCII-Only Status Markers

```text
[OK]       - Success/completion
[ERROR]    - Errors/failures  
[WARN]     - Warnings
[INFO]     - Information
[DONE]     - Task completion
[READY]    - System ready
[TEST]     - Testing/debug
[INSTALL]  - Installation steps
[FEATURES] - Feature highlights
[SYSTEM]   - System checks
```

### **Rule #2: Maya-Compatible Text Formatting**

#### Status Messages

```mel
// ✅ CORRECT:
print("[OK] Asset Manager loaded successfully\n");
print("[ERROR] Failed to load module\n");
print("[WARN] PySide6 not available\n");

// ❌ WRONG:
print("✅ Asset Manager loaded successfully\n");
print("❌ Failed to load module\n"); 
print("⚠️ PySide6 not available\n");
```

#### Progress Indicators

```text
// ✅ CORRECT:
print("--- Cleaning Python module cache ---\n");
print("=== Installation Complete ===\n");
print("*** IMPORTANT: Restart Required ***\n");

// ❌ WRONG: 
print("🔄 Cleaning Python module cache\n");
print("🎉 Installation Complete\n");
print("⚡ IMPORTANT: Restart Required\n");
```

### **Rule #3: Python String Handling in MEL**

```text
// ✅ CORRECT:
python("print('[OK] Python integration working')");
python("print(f'[INFO] Found {count} modules')");

// ❌ WRONG:
python("print('✅ Python integration working')");
python("print(f'ℹ️ Found {count} modules')");
```

### **Rule #4: Python Multi-line Statements in MEL**

**CRITICAL**: Never split Python lists/dictionaries across multiple `python()` calls in MEL!

```mel
// ✅ CORRECT: Single python() call for complete statements
python("cache_paths = [r'C:\\path1\\__pycache__', r'C:\\path2\\__pycache__']");
python("for path in cache_paths: print(path)");

// ❌ WRONG: Split lists across python() calls - BREAKS SYNTAX!
python("cache_paths = [");
python("    r'C:\\path1\\__pycache__',");
python("    r'C:\\path2\\__pycache__'");
python("]");  // Error: '[' was never closed
```

**Why this fails**: Each `python()` call is executed separately. MEL cannot maintain Python syntax context between calls.

#### **Python Indentation in MEL - CRITICAL**

**Problem**: Python indented blocks (for, if, try) cannot span multiple `python()` calls.

```mel
// ❌ WRONG: Split indented blocks - BREAKS SYNTAX!
python("for item in items:");
python("    print(item)");  // Error: expected indented block

// ✅ CORRECT: Complete indented block in single call
python("for item in items:\n    print(item)");

// ✅ CORRECT: Multi-line with proper escaping
python("for path in cache_paths:\n    if os.path.exists(path):\n        try:\n            shutil.rmtree(path)\n        except:\n            pass");
```

#### **Real-World Example - Directory Removal**

```mel
// ❌ WRONG: Split complex logic - BREAKS!
python("if os.path.exists(asset_dir):");
python("    try:");
python("        shutil.rmtree(asset_dir)");
python("        print('Removed directory')");
python("    except Exception as e:");
python("        print(f'Error: {e}')");

// ✅ CORRECT: Complete logic block in single call
python("if os.path.exists(asset_dir):\n    try:\n        shutil.rmtree(asset_dir)\n        print('[OK] Successfully removed directory')\n    except Exception as e:\n        print(f'[ERROR] Error removing directory: {e}')");
```

---

## 📋 Maya Script Development Checklist

### Before Committing ANY Maya Script

- [ ] **Character Check**: No Unicode/emoji characters anywhere
- [ ] **Status Markers**: Use `[OK]`, `[ERROR]`, `[WARN]`, `[INFO]` format
- [ ] **Path Handling**: Use forward slashes `/` for Maya compatibility
- [ ] **Python Integration**: Test embedded Python code separately
- [ ] **Error Handling**: Robust fallback for all file operations
- [ ] **Clear Feedback**: User knows what's happening at each step

### MEL Script Template

```mel
// [SCRIPT NAME] - Asset Manager v1.3.0+
// [DESCRIPTION]

global proc [procedureName]()
{
    print("\n=== [SCRIPT TITLE] ===\n");
    
    // Always provide clear feedback
    print("[INFO] Starting [operation]...\n");
    
    // Robust error handling
    if (`condition`) {
        print("[OK] Operation successful\n");
    } else {
        print("[ERROR] Operation failed\n");
        return;
    }
    
    print("[DONE] [Script completed successfully]\n");
}

// Execute
[procedureName]();
```

---

## 🏗️ Clean Code Principles for Maya Development

### Single Responsibility Principle

Each MEL procedure should do ONE thing well:

```mel
// ✅ GOOD: Focused responsibility
global proc clearPythonCache() { /* only clears cache */ }
global proc removeShelfButtons() { /* only removes buttons */ }
global proc verifyInstallation() { /* only verifies */ }

// ❌ BAD: Multiple responsibilities  
global proc doEverything() { /* clears cache, removes buttons, installs, etc. */ }
```

### DRY Principle - Don't Repeat Yourself

```mel
// ✅ GOOD: Define paths once
string $baseDir = `internalVar -userScriptDir`;
string $assetDir = $baseDir + "assetManager/";
string $cacheDir = $assetDir + "__pycache__/";

// ❌ BAD: Repeat path logic everywhere
if (`filetest -d $scriptsDir + "assetManager/"`) { ... }
if (`filetest -d $scriptsDir + "assetManager/__pycache__/"`) { ... }
```

### Clear Naming Convention

```mel
// ✅ GOOD: Descriptive names
string $mayaScriptsDirectory = `internalVar -userScriptDir`;
int $removedButtonCount = 0;
string $assetManagerInstallPath = "";

// ❌ BAD: Unclear names
string $dir = `internalVar -userScriptDir`;
int $count = 0;
string $path = "";
```

---

## 🎯 Maya-Specific Best Practices

### Path Handling

```mel
// ✅ CORRECT: Maya-compatible paths
string $path = "C:/Users/UserName/Documents/maya/scripts/";
string $combined = $basePath + "subfolder/file.py";

// ❌ WRONG: Windows-specific paths  
string $path = "C:\\Users\\UserName\\Documents\\maya\\scripts\\";
```

### Python Integration Testing

Always test Python code separately before embedding:

```python
# Test this in Maya's Python console first:
import sys
modules = [m for m in sys.modules.keys() if 'asset' in m.lower()]
print(f"Found modules: {modules}")
```

Then embed in MEL:

```mel
python("import sys");
python("modules = [m for m in sys.modules.keys() if 'asset' in m.lower()]");
python("print(f'[INFO] Found modules: {modules}')");
```

### Error Recovery

Always provide graceful fallbacks:

```mel
// ✅ GOOD: Graceful error handling
if (`filetest -d $assetManagerDir`) {
    // Try to remove
    python("# removal code with try/catch");
} else {
    print("[INFO] No installation found to remove\n");
}

// ❌ BAD: Assume success
python("shutil.rmtree(asset_dir)");  // What if it fails?
```

---

## 📝 Documentation Standards

### File Headers

```mel
// Asset Manager [Component] v1.3.0+
// [Brief Description]
// 
// Usage: [How to use]
// Requirements: Maya 2025+, PySide6
// Encoding: ASCII only - NO Unicode characters!
//
// Author: [Name]
// Date: [Date]
```

### Comment Style

```mel
// Single responsibility: Clear cache only
global proc clearAssetManagerCache()
{
    // Step 1: Identify cache locations
    string $cachePaths[] = getCachePaths();
    
    // Step 2: Remove each cache directory
    for ($path in $cachePaths) {
        removeCacheDirectory($path);
    }
    
    // Step 3: Verify cleanup completed
    verifyCacheCleared();
}
```

---

## 🚀 Quick Reference: Maya-Safe Characters

### Status Indicators

```text
[OK] [ERROR] [WARN] [INFO] [DONE] [READY] [TEST]
[INSTALL] [FEATURES] [SYSTEM] [DEBUG] [LOADING]
```

### Separators

```text
=== Main Headers ===
--- Sub Sections ---  
*** Important Notes ***
... Progress Dots ...
```

### Lists

```text
* Bullet points (not Unicode bullets)
1. Numbered lists
- Dashes for sub-items
```

---

## 📋 Review Checklist Template

```text
Maya Script Review Checklist:
[ ] No Unicode/emoji characters used
[ ] All status messages use [OK]/[ERROR]/[WARN] format  
[ ] Paths use forward slashes (/)
[ ] Python code tested separately first
[ ] Error handling for all file operations
[ ] Clear user feedback at each step
[ ] Single responsibility per function
[ ] Descriptive variable names
[ ] No repeated code (DRY principle)
[ ] Maya 2025+ compatibility verified
```

---

**Remember: Maya compatibility is NOT optional - it's fundamental!**  
Always prioritize Maya-compatible ASCII characters over visual aesthetics.

*This document should be referenced for ALL Maya development going forward.*
**Remember: Maya compatibility is NOT optional - it's fundamental!**  
Always prioritize Maya-compatible ASCII characters over visual aesthetics.

*This document should be referenced for ALL Maya development going forward.*
