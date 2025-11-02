#!/bin/bash
# Dealereye Update Watcher
# Watches for update trigger file and executes update when detected

TRIGGER_FILE="/opt/dealereye/config/.update_trigger"
INSTALL_DIR="/opt/dealereye"
LOG_FILE="/opt/dealereye/update.log"

echo "[$(date)] Update watcher started" >> "$LOG_FILE"

while true; do
    if [ -f "$TRIGGER_FILE" ]; then
        echo "[$(date)] Update trigger detected!" >> "$LOG_FILE"

        # Remove trigger file
        rm -f "$TRIGGER_FILE"

        # Run the installer (which handles updates)
        echo "[$(date)] Running installer..." >> "$LOG_FILE"
        cd "$INSTALL_DIR"
        curl -fsSL https://raw.githubusercontent.com/espressojuice/dealereye/main/install.sh | bash >> "$LOG_FILE" 2>&1

        echo "[$(date)] Update complete" >> "$LOG_FILE"
    fi

    # Check every 5 seconds
    sleep 5
done
