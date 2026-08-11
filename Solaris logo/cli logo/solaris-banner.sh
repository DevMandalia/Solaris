#!/usr/bin/env bash
# Solaris CLI banner (10G) — 256-color ANSI
GOLD=$'\033[38;5;221m'   # #e8b53c
EMBER=$'\033[38;5;209m'  # #e8703a
MUTED=$'\033[38;5;138m'  # #a89075
BONE=$'\033[38;5;250m'   # #cbbfae
RESET=$'\033[0m'

printf '  %s(*) solaris%s  %sv1.0.0%s\n' "$GOLD" "$RESET" "$MUTED" "$RESET"
printf '  %s>%s %ssolaris init --star polaris%s\n' "$EMBER" "$RESET" "$BONE" "$RESET"
