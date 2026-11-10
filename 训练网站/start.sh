#!/bin/sh
# Train Site launcher (Linux / macOS).
# Windows users: double-click 启动网站.cmd instead.
#
# Usage:  sh 训练网站/start.sh
#         PYTHON=/path/to/python3 sh 训练网站/start.sh
cd "$(dirname "$0")" || exit 1
exec "${PYTHON:-python3}" server.py
