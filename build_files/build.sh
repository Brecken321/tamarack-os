#!/usr/bin/bash
# Tamarack OS image build entry point (runs inside the Containerfile).
# Executes every numbered step in build_files/steps in order; each step is a
# small, single-purpose script so failures point at one area.
set -euo pipefail

export CTX=/ctx
# shellcheck source=/dev/null
source "${CTX}/lib.sh"

for step in "${CTX}"/steps/[0-9][0-9]-*.sh; do
    name="$(basename "${step}")"
    group "${name}"
    bash -euo pipefail "${step}"
    endgroup
done

log "Tamarack OS build steps finished"
