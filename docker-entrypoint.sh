#!/usr/bin/env bash
# docker-entrypoint.sh — Atlas container entrypoint
#
# Validates required API keys per subcommand before handing off to the CLI,
# giving clear, actionable errors instead of cryptic library stack traces.
#
# 12-factor: all configuration is sourced exclusively from environment variables.
# No config files are read or written by this script.

set -euo pipefail

# ── Helpers ────────────────────────────────────────────────────────────────
red()   { printf '\033[0;31m%s\033[0m\n' "$*" >&2; }
yellow(){ printf '\033[0;33m%s\033[0m\n' "$*" >&2; }
green() { printf '\033[0;32m%s\033[0m\n' "$*" >&2; }

require_env() {
  local var_name="$1"
  local hint="$2"
  if [[ -z "${!var_name:-}" ]]; then
    red "❌  Missing required environment variable: ${var_name}"
    yellow "   ${hint}"
    yellow "   Pass it with: docker run -e ${var_name}=\"<your-key>\" ..."
    exit 1
  fi
}

# ── Per-subcommand key validation ──────────────────────────────────────────
# Detect the first positional arg (the subcommand) from the arguments passed
# to the entrypoint. Flags like --help are skipped so that `atlas --help`
# always works without any keys set.

SUBCOMMAND=""
for arg in "$@"; do
  case "$arg" in
    --*|-*) continue ;;   # skip flags
    *)      SUBCOMMAND="$arg"; break ;;
  esac
done

case "${SUBCOMMAND}" in
  extract|index)
    # Both providers required: Gemini for multimodal analysis, Groq Whisper for transcription
    require_env GEMINI_API_KEY \
      "Obtain a free key at https://aistudio.google.com/app/apikey"
    require_env GROQ_API_KEY \
      "Obtain a free key at https://console.groq.com/keys"
    ;;
  search|chat)
    require_env GEMINI_API_KEY \
      "Obtain a free key at https://aistudio.google.com/app/apikey"
    ;;
  transcribe)
    require_env GROQ_API_KEY \
      "Obtain a free key at https://console.groq.com/keys"
    ;;
  list-videos|list-chat|stats|queue|serve|"")
    # No API keys needed
    ;;
  *)
    # Unknown subcommand — let the CLI handle it with its own error message
    ;;
esac

# ── Ensure writable data directories ────────────────────────────────────────
ATLAS_HOME="${HOME}/.atlas"
mkdir -p \
    "${ATLAS_HOME}/index" \
    "${ATLAS_HOME}/queue/queued_tasks/results"

# ── Exec ───────────────────────────────────────────────────────────────────
exec atlas "$@"
