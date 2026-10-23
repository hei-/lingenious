#!/usr/bin/env bash
# Build the image, run the CLI in a container and copy the results back to ./out/<name>.
# usage: scripts/run.sh <name> "<requirement text>" [extra core.cli args...]
#   e.g. scripts/run.sh bracket "L 型铝支架: ..." --material 6061 --modify "立板厚度改成 4mm"
set -euo pipefail
cd "$(dirname "$0")/.."
DOCKER=(docker)
BUILD_ARGS=()
[ -n "${APT_MIRROR:-}" ] && BUILD_ARGS+=(--build-arg "APT_MIRROR=$APT_MIRROR")
[ -n "${PIP_INDEX_URL:-}" ] && BUILD_ARGS+=(--build-arg "PIP_INDEX_URL=$PIP_INDEX_URL")
name=$1; shift; req=$1; shift
"${DOCKER[@]}" build -q --target dev ${BUILD_ARGS[@]+"${BUILD_ARGS[@]}"} -t lingenious:dev . >/dev/null
cid=lingenious-run-$name-$$
"${DOCKER[@]}" run --name "$cid" --env-file .env lingenious:dev python -W ignore -m core.cli "$req" --out /tmp/out/$name "$@" || true
mkdir -p out && rm -rf "out/$name" && "${DOCKER[@]}" cp "$cid:/tmp/out/$name" "out/$name" || true
"${DOCKER[@]}" rm "$cid" >/dev/null
echo "results: out/$name"
