#!/bin/bash

# Colors for enhanced terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo
echo -e "${BOLD}${CYAN}====================================================================${NC}"
echo -e "${BOLD}${CYAN}    Asset Manager for Maya (All Versions) v1.4.0 - Unix/Linux/macOS Installer${NC}"
echo -e "${BOLD}${CYAN}====================================================================${NC}"
echo -e "${CYAN}    Unified Installation Architecture ${NC}${BOLD}|${NC}${CYAN} Multi-Version Compatible${NC}"
echo -e "${CYAN}    OneDrive & iCloud Drive Support ${NC}${BOLD}|${NC}${CYAN} Smart Path Detection${NC}"
echo -e "${BOLD}${CYAN}====================================================================${NC}"
echo

# Function to check command existence
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if Python is available
echo -e "${YELLOW}[1/4]${NC} Checking Python installation..."

PYTHON_CMD=""
if command_exists python3; then
    PYTHON_CMD="python3"
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d ' ' -f 2)
elif command_exists python; then
    # Check if it's Python 3
    PYTHON_VERSION=$(python --version 2>&1)
    if [[ $PYTHON_VERSION == *"Python 3"* ]]; then
        PYTHON_CMD="python"
        PYTHON_VERSION=$(echo $PYTHON_VERSION | cut -d ' ' -f 2)
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    echo
    echo -e "${RED}❌ ERROR: Python 3 is not installed or not available in PATH${NC}"
    echo
    echo -e "    Please install Python 3:"
    echo -e "    • ${BOLD}Ubuntu/Debian:${NC} sudo apt-get install python3"
    echo -e "    • ${BOLD}CentOS/RHEL:${NC} sudo yum install python3"
    echo -e "    • ${BOLD}macOS:${NC} brew install python3 (or download from python.org)"
    echo
    exit 1
fi

echo -e "    ${GREEN}✅ Python $PYTHON_VERSION detected${NC}"

echo
echo -e "${YELLOW}[2/4]${NC} Initializing unified installation core..."
echo -e "    ${CYAN}📦 Using AssetManagerInstaller class for consistent results${NC}"

# Change to script directory to ensure relative paths work
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo
echo -e "${YELLOW}[3/4]${NC} Running installation with unified setup.py core..."
echo -e "    ${CYAN}🔧 This uses the same core logic as DRAG&DROP.mel and install.bat${NC}"
echo

# Run the unified installation
$PYTHON_CMD setup.py

if [ $? -ne 0 ]; then
    echo
    echo -e "${RED}❌ Installation failed. Please check error messages above.${NC}"
    echo
    exit 1
fi

echo
echo -e "${YELLOW}[4/4]${NC} Installation verification..."
echo -e "    ${GREEN}✅ Unified installation architecture complete${NC}"
echo
echo -e "${BOLD}${GREEN}====================================================================${NC}"
echo -e "${BOLD}${GREEN}                    🎉 INSTALLATION SUCCESSFUL 🎉${NC}"
echo -e "${BOLD}${GREEN}====================================================================${NC}"
echo
echo -e "${BOLD}${CYAN}🚀 NEXT STEPS:${NC}"
echo
echo -e "   ${YELLOW}1️⃣${NC}  Launch any Maya version (2022, 2023, 2024, 2025+)"
echo -e "   ${YELLOW}2️⃣${NC}  Run in Maya's Script Editor (Python):"
echo -e "        ${BOLD}import assetManager${NC}"
echo -e "        ${BOLD}assetManager.show_asset_manager()${NC}"
echo
echo -e "   ${CYAN}💡 TIP: Works across all Maya versions - installed once, use everywhere!${NC}"
echo
echo -e "${BOLD}${CYAN}� INSTALLATION METHODS COMPARISON:${NC}"
echo -e "   • ${BOLD}install.sh${NC} (this method): Unix/Linux/macOS command-line installation"
echo -e "   • ${BOLD}DRAG&DROP.mel${NC}: Maya GUI installation with shelf button"
echo -e "   • ${BOLD}install.bat${NC}: Windows installation"
echo -e "   • ${GREEN}All methods use the same unified setup.py core!${NC}"
echo
echo -e "${BOLD}${CYAN}🔧 ARCHITECTURE HIGHLIGHTS:${NC}"
echo -e "   • ${BOLD}Single Source of Truth:${NC} All installers use setup.py core"
echo -e "   • ${BOLD}Clean Code:${NC} AssetManagerInstaller class with clear methods"
echo -e "   • ${BOLD}DRY Principle:${NC} No code duplication between installation methods"
echo -e "   • ${BOLD}Multi-Version Support:${NC} Works with all Maya versions (2022-2025+)"
echo -e "   • ${BOLD}General Scripts Directory:${NC} ~/Documents/maya/scripts/ (not version-specific)"
echo
echo -e "${CYAN}Press any key to continue...${NC}"
read -n 1