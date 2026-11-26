#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ "$(pwd)" == /home/ansy/app/trading ]] || { echo 'Adjust checked-in unit paths for this checkout first.'; exit 1; }
.venv/bin/python scripts/setup_operations_database.py
mkdir -p "$HOME/.config/systemd/user"
cp deploy/systemd/quant-operations.service deploy/systemd/quant-operations.timer "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now quant-operations.timer
