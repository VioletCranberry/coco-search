#!/usr/bin/env bash
set -euo pipefail

# Script location detection
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Variables
CLEANUP_NEEDED=false
export COCOSEARCH_DATABASE_URL="postgresql://cocosearch:cocosearch@localhost:5432/cocosearch"
export COCOSEARCH_OLLAMA_URL="http://localhost:11434"

# Trap handlers
cleanup_on_exit() {
  local exit_code=$?

  if [[ $exit_code -ne 0 ]] && [[ "$CLEANUP_NEEDED" == "true" ]]; then
    echo ""
    echo "Setup failed. Containers may be running."
    read -p "Keep containers for debugging? [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      echo "Cleaning up containers..."
      docker compose down
    fi
  fi
}

trap cleanup_on_exit EXIT

trap 'echo ""; echo "Interrupted"; exit 130' INT TERM

# Functions

check_docker() {
  if ! command -v docker &>/dev/null; then
    echo "Error: docker command not found"
    echo ""
    echo "Install Docker from: https://docs.docker.com/get-docker/"
    exit 1
  fi

  if ! docker info &>/dev/null; then
    echo "Error: Docker daemon is not running"
    echo ""
    echo "Start Docker Desktop or Docker daemon and try again"
    exit 1
  fi
}

check_uv() {
  if ! command -v uv &>/dev/null; then
    echo "Error: uv command not found"
    echo ""
    echo "Install uv with:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
  fi
}

check_port() {
  local port=$1
  local service_name=$2

  if lsof -Pi ":$port" -sTCP:LISTEN -t &>/dev/null; then
    local process_info
    process_info=$(lsof -Pi ":$port" -sTCP:LISTEN -P 2>/dev/null | tail -n +2 | head -n 1)
    echo "Error: Port $port is already in use by $service_name"
    echo ""
    echo "Process using port $port:"
    echo "$process_info"
    echo ""
    echo "Stop the process or use a different port"
    exit 1
  fi
}

start_services() {
  echo "postgres: Starting container..."
  echo "ollama: Starting container..."
  docker compose up -d --wait
  CLEANUP_NEEDED=true
}

pull_model() {
  local MODEL="nomic-embed-text"

  if docker exec cocosearch-ollama ollama list 2>/dev/null | grep -q "$MODEL"; then
    echo "ollama: $MODEL already available"
  else
    echo "ollama: Pulling $MODEL model..."
    docker exec cocosearch-ollama ollama pull "$MODEL"
  fi
}

install_dependencies() {
  echo "dependencies: Installing Python packages..."
  uv sync
}

index_codebase() {
  echo "cocosearch: Indexing codebase..."
  uv run cocosearch index . --name cocosearch
}

run_demo_search() {
  echo ""
  echo "cocosearch: Running demo search... [how does indexing work]"
  uv run cocosearch search "how does indexing work" --index cocosearch --limit 3 --pretty
}

show_next_steps() {
  echo ""
  echo "Setup complete!"
  echo "==============="
  echo ""
  echo "DATABASE_URL defaults to postgresql://cocosearch:cocosearch@localhost:5432/cocosearch"
  echo "No environment variable needed when using docker compose."
  echo ""
  echo "To override (add to ~/.bashrc or ~/.zshrc):"
  echo "  export COCOSEARCH_DATABASE_URL=\"postgresql://custom:pass@host:5432/db\""
  echo ""
  echo "Quick reference commands:"
  echo ""
  echo "  # Search codebase"
  echo "  uv run cocosearch search \"query\" --index cocosearch --pretty"
  echo ""
  echo "  # Index a different codebase"
  echo "  uv run cocosearch index /path/to/codebase --name my-index"
  echo ""
  echo "  # Interactive REPL"
  echo "  uv run cocosearch search -i --index cocosearch"
  echo ""
  echo "Teardown instructions:"
  echo ""
  echo "  # Stop services"
  echo "  docker compose down"
  echo ""
  echo "  # Remove data volumes"
  echo "  docker compose down -v"
  echo ""
}

main() {
  cd "$SCRIPT_DIR" # Ensure we're in repo root

  echo "CocoSearch Developer Setup"
  echo "=========================="
  echo ""

  check_docker
  check_uv
  check_port 5432 "PostgreSQL"
  check_port 11434 "Ollama"

  start_services
  pull_model
  install_dependencies
  index_codebase
  run_demo_search
  show_next_steps
}

main
