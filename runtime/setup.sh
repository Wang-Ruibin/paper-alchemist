#!/bin/sh
set -eu
uv_version=0.13.6
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
plugin_root=$(dirname "$script_dir")
runtime_root=${PAPER_ALCHEMIST_RUNTIME:-${XDG_CACHE_HOME:-$HOME/.cache}/paper-alchemist/runtime}
case "$runtime_root" in /*) ;; *) echo 'PAPER_ALCHEMIST_RUNTIME must be absolute' >&2; exit 2;; esac
case "${1:-}" in '') managed=0;; --managed-python) managed=1;; *) echo 'Usage: setup.sh [--managed-python]' >&2; exit 2;; esac
hash_file() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1"; else shasum -a 256 "$1"; fi; }
digest=$(hash_file "$script_dir/requirements.txt" | cut -c1-16)
environment_path="$runtime_root/envs/$digest"
python_path="$environment_path/bin/python"
uv_path="$runtime_root/uv-$uv_version/uv"
mkdir -p "$runtime_root"
if ! mkdir "$runtime_root/.setup-lock" 2>/dev/null; then echo 'Another setup is running. Inspect a stale lock before removing it.' >&2; exit 2; fi
stage=
cleanup() {
    if [ -n "$stage" ] && [ -d "$stage" ]; then
        case "$stage" in "$runtime_root"/.download-*) rm -rf -- "$stage";; *) echo 'Unexpected cleanup path' >&2; return 2;; esac
    fi
    rmdir "$runtime_root/.setup-lock"
}
trap cleanup EXIT
trap 'exit 130' INT TERM
export UV_PYTHON_INSTALL_DIR="$runtime_root/python" UV_CACHE_DIR="$runtime_root/cache" UV_NO_PROGRESS=1
if [ ! -x "$uv_path" ]; then
    case "$(uname -s)" in Linux) system=linux;; Darwin) system=darwin;; *) echo 'Unsupported operating system' >&2; exit 2;; esac
    case "$(uname -m)" in x86_64|amd64) architecture=x86_64;; aarch64|arm64) architecture=aarch64;; *) echo 'Unsupported architecture' >&2; exit 2;; esac
    platform="$system-$architecture"
    filename=$(awk -F '\t' -v platform="$platform" '$1 == platform {print $2}' "$script_dir/downloads.tsv")
    expected=$(awk -F '\t' -v platform="$platform" '$1 == platform {print $3}' "$script_dir/downloads.tsv")
    expected_bytes=$(awk -F '\t' -v platform="$platform" '$1 == platform {print $4}' "$script_dir/downloads.tsv")
    [ -n "$filename" ] && [ -n "$expected" ] || { echo 'Missing runtime download entry' >&2; exit 2; }
    stage=$(mktemp -d "$runtime_root/.download-XXXXXXXX")
    curl --fail --location --retry 2 --connect-timeout 20 --max-time 180 --proto '=https' --tlsv1.2 "https://github.com/astral-sh/uv/releases/download/$uv_version/$filename" -o "$stage/uv.tar.gz"
    actual=$(hash_file "$stage/uv.tar.gz" | cut -c1-64)
    actual_bytes=$(wc -c < "$stage/uv.tar.gz" | tr -d ' ')
    [ "$actual" = "$expected" ] && [ "$actual_bytes" = "$expected_bytes" ] || { echo 'uv download checksum or size mismatch' >&2; exit 2; }
    tar -xzf "$stage/uv.tar.gz" -C "$stage"
    directory=${filename%.tar.gz}
    mkdir -p "$(dirname "$uv_path")"
    mv "$stage/$directory/uv" "$uv_path"
fi
if [ ! -x "$python_path" ]; then
    [ ! -e "$environment_path" ] || { echo "Incomplete environment preserved: $environment_path" >&2; exit 2; }
    created=0
    if [ "$managed" = 0 ] && "$uv_path" --no-config venv --python '>=3.11,<3.15' --python-preference system --no-python-downloads "$environment_path"; then created=1; fi
    if [ "$created" = 0 ]; then "$uv_path" --no-config venv --python 3.12 --managed-python "$environment_path"; fi
fi
"$uv_path" --no-config pip install --python "$python_path" --link-mode copy --only-binary :all: --requirement "$script_dir/requirements.txt"
"$python_path" -I "$plugin_root/skills/paper-alchemist/scripts/run.py" --version
"$python_path" -I -c 'import json,sys; from pathlib import Path; r={"ready":True,"python":sys.executable,"runtime_root":sys.argv[1],"dependency_lock":sys.argv[2],"uv_version":sys.argv[3],"system_path_changed":False}; p=Path(sys.argv[1])/"runtime.json"; p.write_text(json.dumps(r,indent=2)+"\n"); print(json.dumps(r,indent=2))' "$runtime_root" "$digest" "$uv_version"
