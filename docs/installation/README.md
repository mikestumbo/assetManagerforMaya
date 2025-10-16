# Installation Documentation

This directory contains all documentation related to installing and deploying Asset Manager v1.3.0 for Maya.

---

## 📚 Documentation Files

### Installation Guides

- **[INSTALL_INSTRUCTIONS.md](INSTALL_INSTRUCTIONS.md)** - Standard installation using DRAG&DROP.mel
- **[AUTO_LOAD_CONFIGURATION.md](AUTO_LOAD_CONFIGURATION.md)** - Auto-load setup with userSetup.py
- **[DEPLOYMENT_GUIDE_v1.3.0.md](DEPLOYMENT_GUIDE_v1.3.0.md)** - Production deployment guide
- **[MAYA_INSTALLATION_TROUBLESHOOTING.md](MAYA_INSTALLATION_TROUBLESHOOTING.md)** - Common installation issues

---

## 🚀 Quick Start

For most users, the installation process is simple:

1. **Drag & Drop**: Drag `DRAG&DROP.mel` from the root directory into Maya viewport
2. **Run**: The installer handles everything automatically
3. **Restart**: Restart Maya (optional but recommended)
4. **Launch**: Click the shelf button or run: `import assetManager; assetManager.show_asset_manager()`

See **[INSTALL_INSTRUCTIONS.md](INSTALL_INSTRUCTIONS.md)** for complete details.

---

## 🔧 Installation Method

Asset Manager uses **DRAG&DROP.mel** as the standard installation method:

- ✅ Professional installer with GUI feedback
- ✅ Installs to Maya scripts directory
- ✅ Creates professional shelf button with hover icons
- ✅ Configures auto-load via userSetup.py
- ✅ Works across all Maya 2025+ versions

---

## 📋 Post-Installation

After installation, verify:

1. **Shelf Button**: Asset Manager button appears on current shelf
2. **Console Message**: "[OK] Asset Manager v1.3.0 path added - Ready for use"
3. **Module Import**: `import assetManager` works without errors
4. **UI Launch**: Shelf button opens Asset Manager window

---

## 🐛 Troubleshooting

If you encounter installation issues, see:

- **[MAYA_INSTALLATION_TROUBLESHOOTING.md](MAYA_INSTALLATION_TROUBLESHOOTING.md)**

Common issues:

- Path not found → Check scripts directory permissions
- Import errors → Verify Python environment is configured
- Shelf button missing → Re-run DRAG&DROP.mel installer

---

## 🏢 Production Deployment

For studio/production deployments with multiple users:

- **[DEPLOYMENT_GUIDE_v1.3.0.md](DEPLOYMENT_GUIDE_v1.3.0.md)**

Includes:

- Network installation strategies
- Centralized configuration
- Multi-user setup
- Maya module system deployment

---

## 📖 Related Documentation

- **[../README.md](../README.md)** - Main documentation index
- **[../PLUGIN_vs_SCRIPT_ANALYSIS.md](../PLUGIN_vs_SCRIPT_ANALYSIS.md)** - Why Asset Manager uses Python script approach
- **[../legal/](../legal/)** - Trademark and legal documentation

---

*Last Updated: October 1, 2025*  
*Asset Manager v1.3.0 - Installation Documentation*
