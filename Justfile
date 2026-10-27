set dotenv-filename := "image.env"
set dotenv-load

export image_vendor := env("IMAGE_VENDOR")
export image_registry := env("IMAGE_REGISTRY")
export image_desc := env("IMAGE_DESC")
export image_keywords := env("IMAGE_KEYWORDS")
export default_tag := env("DEFAULT_TAG")
export bib_image := env("BIB_IMAGE")

[private]
default:
    @just --list

# ---------------------------------------------------------------------------
# Development checks (run on any machine with Python 3.11+)
# ---------------------------------------------------------------------------

# Run unit tests
[group('Check')]
test:
    PYTHONPATH=src:branding python3 -m pytest -q tests

# Lint Python, shell scripts and the Justfile
[group('Check')]
lint:
    ruff check src branding tests
    ruff format --check src branding tests
    PYTHONPATH=src:branding python3 -m mypy src/tamarack branding/tamarack_branding
    find build_files system_files tests -type f \( -name '*.sh' -o -path '*/libexec/tamarack/*' \) \
        -exec grep -lE '^#!.*(bash|sh)' {} + | xargs shellcheck --external-sources
    just --unstable --fmt --check -f Justfile

# Generate branding into ./output/branding without rasterizing (fast preview)
[group('Check')]
branding out="output/branding":
    PYTHONPATH=src:branding python3 -m tamarack_branding --brand branding/brand.toml \
        --presets branding/presets --out {{ out }} --no-render

# ---------------------------------------------------------------------------
# Image builds (Linux with podman; CI runs these)
# ---------------------------------------------------------------------------

# Print "<image> <base image>" for a flavor (main | nvidia)
[group('Build')]
variant flavor="main":
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{ flavor }}" in
        main) echo "${IMAGE_MAIN} ${BASE_MAIN}" ;;
        nvidia) echo "${IMAGE_NVIDIA} ${BASE_NVIDIA}" ;;
        *) echo "unknown flavor '{{ flavor }}' (expected main or nvidia)" >&2; exit 1 ;;
    esac

# Build the OS image for a flavor (main | nvidia)
[group('Build')]
build flavor="main" tag=default_tag:
    #!/usr/bin/env bash
    set -euo pipefail
    read -r image base < <(just variant "{{ flavor }}")
    sha="unknown"
    LABELS=()
    if git rev-parse --git-dir >/dev/null 2>&1; then
        sha="$(git rev-parse --short HEAD)"
        if [[ -z "$(git status --porcelain)" ]]; then
            url="https://github.com/${image_vendor}/tamarack-os"
            LABELS+=(--label "org.opencontainers.image.source=${url}")
            LABELS+=(--label "org.opencontainers.image.revision=$(git rev-parse HEAD)")
            LABELS+=(--label "io.artifacthub.package.readme-url=https://raw.githubusercontent.com/${image_vendor}/tamarack-os/${sha}/README.md")
        fi
    fi
    LABELS+=(--label "org.opencontainers.image.title=${image}")
    # Override labels inherited from the Bazzite base so the image is not misattributed.
    LABELS+=(--label "org.opencontainers.image.url=https://github.com/${image_vendor}/tamarack-os")
    LABELS+=(--label "io.artifacthub.package.logo-url=https://raw.githubusercontent.com/${image_vendor}/tamarack-os/main/docs/assets/tamarack-logo.svg")
    LABELS+=(--label "org.opencontainers.image.description=${image_desc}")
    LABELS+=(--label "org.opencontainers.image.vendor=${image_vendor}")
    LABELS+=(--label "org.opencontainers.image.licenses=Apache-2.0")
    LABELS+=(--label "org.opencontainers.image.created=$(date -u +%Y-%m-%dT%H:%M:%SZ)")
    LABELS+=(--label "org.opencontainers.image.base.name=${base}")
    LABELS+=(--label "io.artifacthub.package.keywords=${image_keywords}")
    LABELS+=(--label "containers.bootc=1")
    podman build \
        --pull=newer \
        --build-arg "BASE_IMAGE=${base}" \
        --build-arg "IMAGE_NAME=${image}" \
        --build-arg "IMAGE_FLAVOR={{ flavor }}" \
        --build-arg "IMAGE_VENDOR=${image_vendor}" \
        --build-arg "IMAGE_TAG={{ tag }}" \
        --build-arg "GIT_SHA=${sha}" \
        "${LABELS[@]}" \
        --tag "${image}:{{ tag }}" \
        --file Containerfile \
        .

# Run the image content checks inside a built image
[group('Build')]
check-image flavor="main" tag=default_tag:
    #!/usr/bin/env bash
    set -euo pipefail
    read -r image base < <(just variant "{{ flavor }}")
    podman run --rm --network=none \
        -v "$(pwd)/tests/image:/tests:ro,Z" \
        "localhost/${image}:{{ tag }}" \
        bash /tests/check-image.sh "{{ flavor }}"

# Split the image into ostree chunks for smaller updates (as in ublue-os/image-template)
[group('Build')]
rechunk flavor="main" tag=default_tag:
    #!/usr/bin/env bash
    set -xeuo pipefail
    read -r image base < <(just variant "{{ flavor }}")
    GRAPHROOT="$(podman info --format '{{ '{{.Store.GraphRoot}}' }}')"
    # --rootfs builds a fresh image config, dropping every label. Carry them over
    # (except ostree's own) and add the version: bootc records it at install time,
    # and a missing version makes bootupd fail on new installs (coreos/bootupd#1166).
    LABELS=()
    while IFS= read -r kv; do
        LABELS+=(--label "${kv}")
    done < <(podman image inspect "localhost/${image}:{{ tag }}" |
        jq -r '.[0].Labels // {} | to_entries[] | select(.key | test("^(ostree\\.|containers\\.bootc$)") | not) | "\(.key)=\(.value)"')
    version="$(podman run --rm --pull=never --entrypoint /usr/bin/bash "localhost/${image}:{{ tag }}" \
        -c '. /usr/lib/os-release && echo "${IMAGE_VERSION}"')"
    [[ -n "${version}" ]] || { echo "IMAGE_VERSION missing from os-release" >&2; exit 1; }
    LABELS+=(--label "org.opencontainers.image.version=${version}")
    podman run --rm --pull=never --privileged \
      --mount=type=image,src="${image}:{{ tag }}",target=/rpm-ostree \
      --mount=type=bind,src=${GRAPHROOT},target=/run/host-container-storage,rw \
      --mount=type=tmpfs,target=/run/rpm-ostree-storage \
      --entrypoint /usr/bin/rpm-ostree \
      "localhost/${image}:{{ tag }}" \
      compose build-chunked-oci \
      --max-layers 127 \
      --format-version=2 \
      --bootc \
      "${LABELS[@]}" \
      --rootfs /rpm-ostree \
      --output "containers-storage:[overlay@/run/host-container-storage+/run/rpm-ostree-storage]localhost/${image}:{{ tag }}"
    # Guard against regressions: the published image must carry its version.
    podman image inspect "localhost/${image}:{{ tag }}" |
        jq -e --arg v "${version}" '.[0].Labels["org.opencontainers.image.version"] == $v' >/dev/null

# Tags to publish for a build: tag, tag-YYYYMMDD, YYYYMMDD and tag-<sha> when clean
[group('Build')]
build-tags tag=default_tag:
    #!/usr/bin/env bash
    set -euo pipefail
    date="$(date -u +%Y%m%d)"
    tags=("{{ tag }}" "{{ tag }}-${date}" "${date}" "latest")
    if [[ -z "$(git status --porcelain 2>/dev/null)" ]]; then
        tags+=("{{ tag }}-$(git rev-parse --short HEAD)")
    fi
    echo "${tags[@]}"

# ---------------------------------------------------------------------------
# Disk images and VMs (Linux with root podman and KVM)
# ---------------------------------------------------------------------------

# Build an installer ISO or qcow2 from a published or local image with bootc-image-builder
[group('Disk')]
disk flavor="main" type="anaconda-iso" image_ref="":
    #!/usr/bin/env bash
    set -euo pipefail
    read -r image base < <(just variant "{{ flavor }}")
    ref="{{ image_ref }}"
    [[ -n "${ref}" ]] || ref="${image_registry}/${image}:${default_tag}"
    if [[ "{{ type }}" == "anaconda-iso" ]]; then config="disk_config/iso-{{ flavor }}.toml"; else config="disk_config/disk.toml"; fi
    mkdir -p output
    sudo podman pull "${ref}"
    sudo podman run --rm -it --privileged --pull=newer --net=host \
      --security-opt label=type:unconfined_t \
      -v "$(pwd)/${config}:/config.toml:ro" \
      -v "$(pwd)/output:/output" \
      -v /var/lib/containers/storage:/var/lib/containers/storage \
      "${bib_image}" --type "{{ type }}" --use-librepo=True --rootfs=btrfs "${ref}"
    sudo chown -R "$(id -u):$(id -g)" output
