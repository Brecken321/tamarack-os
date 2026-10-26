# Tamarack OS image definition.
#
# Tamarack OS is a custom bootc image layered on Bazzite (Universal Blue),
# which is itself built on Fedora Atomic KDE. Kernel, drivers, Mesa,
# Steam/Proton support and the update/rollback machinery come from upstream;
# this file adds Tamarack's identity, defaults, privacy settings and tools.
#
# Build locally:  just build            (see Justfile)
# Build in CI:    .github/workflows/build.yml

# Base image per hardware variant (set by the build matrix):
#   ghcr.io/ublue-os/bazzite:stable             AMD / Intel graphics
#   ghcr.io/ublue-os/bazzite-nvidia-open:stable NVIDIA GTX 16xx / RTX (Turing+)
ARG BASE_IMAGE="ghcr.io/ublue-os/bazzite:stable"

# --- Stage 1: render branding artwork and theme files ----------------------
FROM quay.io/fedora/fedora:44 AS branding
RUN dnf5 -y install --setopt=install_weak_deps=False \
        python3 python3-pillow librsvg2-tools google-noto-sans-fonts && \
    dnf5 clean all
COPY src/tamarack /src/tamarack
COPY branding /branding
RUN PYTHONPATH=/src:/branding python3 -m tamarack_branding \
        --brand /branding/brand.toml --presets /branding/presets --out /out

# --- Stage 2: build context (bind-mounted, never copied into the image) ----
FROM scratch AS ctx
COPY build_files /
COPY system_files /system_files
COPY src /src
COPY data /data
COPY LICENSE /LICENSE
COPY cosign.pub /keys/cosign.pub
COPY --from=branding /out /generated

# --- Stage 3: the operating system image ------------------------------------
FROM ${BASE_IMAGE}

ARG IMAGE_NAME="tamarack-os"
ARG IMAGE_VENDOR="brecken321"
ARG IMAGE_FLAVOR="main"
ARG IMAGE_TAG="stable"
ARG BASE_IMAGE="ghcr.io/ublue-os/bazzite:stable"
ARG GIT_SHA="unknown"
ARG VERSION=""

RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=tmpfs,dst=/tmp \
    bash /ctx/build.sh

# Verify the result is a valid bootable container image.
RUN bootc container lint
