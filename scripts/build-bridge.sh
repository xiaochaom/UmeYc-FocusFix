#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
mkdir -p bin
"${FOCUSFIX_CC:-x86_64-w64-mingw32-gcc}" \
    -O2 -Wall -Wextra -Werror -mconsole -static \
    -o bin/focus-bridge.exe native/focus_bridge.c -luser32 -lgdi32
