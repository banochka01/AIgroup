#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

need() {
  command -v "$1" >/dev/null 2>&1
}

install_docker() {
  if need docker && docker compose version >/dev/null 2>&1; then
    return
  fi

  if ! need sudo; then
    echo "sudo is required to install Docker automatically" >&2
    exit 1
  fi

  sudo apt-get update
  sudo apt-get install -y ca-certificates curl gnupg git

  if ! need docker; then
    curl -fsSL https://get.docker.com | sudo sh
  fi
}

require_env_file() {
  if [ -f .env ]; then
    return
  fi

  if [ -f .env.example ]; then
    cp .env.example .env
  fi

  cat >&2 <<'MSG'
.env was created from .env.example.
Fill OPENAI_API_KEY, TELEGRAM_*_BOT_TOKEN and TELEGRAM_GROUP_CHAT_ID, then run:
  bash scripts/deploy_vps.sh
MSG
  exit 1
}

validate_env() {
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a

  required=(
    OPENAI_API_KEY
    TELEGRAM_COORDINATOR_BOT_TOKEN
    TELEGRAM_FRONTEND_BOT_TOKEN
    TELEGRAM_BACKEND_BOT_TOKEN
    TELEGRAM_QA_BOT_TOKEN
    TELEGRAM_DEVOPS_BOT_TOKEN
    TELEGRAM_DESIGNER_BOT_TOKEN
    TELEGRAM_MANAGER_BOT_TOKEN
    TELEGRAM_GROUP_CHAT_ID
  )

  missing=()
  for key in "${required[@]}"; do
    if [ -z "${!key:-}" ] || [ "${!key:-}" = "0" ]; then
      missing+=("$key")
    fi
  done

  if [ "${#missing[@]}" -gt 0 ]; then
    echo "Missing required env values:" >&2
    printf '  - %s\n' "${missing[@]}" >&2
    exit 1
  fi
}

install_docker
require_env_file
validate_env

sudo docker compose up --build -d
sudo docker compose ps
sudo docker compose logs --tail=80 api telegram
