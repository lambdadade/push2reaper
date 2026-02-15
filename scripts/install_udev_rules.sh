#!/bin/bash
# Install udev rules for Ableton Push 2 USB access (non-root)
#
# Usage: sudo bash scripts/install_udev_rules.sh

set -euo pipefail

RULES_FILE="/etc/udev/rules.d/50-push2.rules"

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

echo "Installing Push 2 udev rules..."

cat > "$RULES_FILE" << 'EOF'
# Ableton Push 2 — allow non-root USB access for display + MIDI
SUBSYSTEM=="usb", ATTR{idVendor}=="2982", ATTR{idProduct}=="1967", MODE="0666", GROUP="plugdev"
EOF

echo "Reloading udev rules..."
udevadm control --reload-rules
udevadm trigger

echo "Done. Push 2 udev rules installed at $RULES_FILE"
echo ""
echo "Make sure your user is in the 'plugdev' group:"
echo "  sudo usermod -a -G plugdev \$USER"
echo ""
echo "You may need to unplug and replug the Push 2, or log out and back in."
