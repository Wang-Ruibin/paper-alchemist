#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
runtime_root=${PAPER_ALCHEMIST_RUNTIME:-${XDG_CACHE_HOME:-$HOME/.cache}/paper-alchemist/runtime}
if command -v sha256sum >/dev/null 2>&1; then digest=$(sha256sum "$script_dir/requirements.txt" | cut -c1-16); else digest=$(shasum -a 256 "$script_dir/requirements.txt" | cut -c1-16); fi
python_path="$runtime_root/envs/$digest/bin/python"
if [ ! -x "$python_path" ]; then echo 'Plugin runtime is not ready. Ask Codex to run runtime/setup.sh during installation.' >&2; exit 2; fi
exec "$python_path" -I "$(dirname "$script_dir")/skills/paper-alchemist/scripts/run.py" "$@"
