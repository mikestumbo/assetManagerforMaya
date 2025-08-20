#!/bin/bash

echo "Asset Manager for Maya 2025.3 v1.2.1 - Installation Script"
echo "========================================================="
echo

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed or not in PATH"
    echo "Please install Python 3 or add it to your PATH"
    exit 1
fi

echo "Installing Asset Manager plugin..."
echo

# Run the installation script
python3 setup.py

echo
echo "Installation complete!"
echo
echo "Next steps:"
echo "1. Open Maya 2025.3"
echo "2. Go to Windows > Settings/Preferences > Plug-in Manager"
echo "3. Find 'assetManager.py' and enable it"
echo "4. The Asset Manager menu will appear in Maya's menu bar"
echo

read -p "Press any key to continue..."
