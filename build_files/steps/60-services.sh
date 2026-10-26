#!/usr/bin/bash
# Enable Tamarack's own systemd units.
# shellcheck source=/dev/null
source "${CTX}/lib.sh"

systemctl enable tamarack-flatpak-setup.service

# Image signature verification for updates: trust our cosign key for our
# registry namespace, in addition to Universal Blue's existing entries.
load_brand
require_file "${CTX}/keys/cosign.pub" /etc/containers/policy.json
install -D -m 0644 "${CTX}/keys/cosign.pub" "/etc/pki/containers/${BRAND_IMAGE_MAIN}.pub"

policy=/etc/containers/policy.json
tmp="$(mktemp)"
jq --arg registry "${BRAND_REGISTRY}" --arg key "/etc/pki/containers/${BRAND_IMAGE_MAIN}.pub" \
    '.transports.docker[$registry] = [{
        "type": "sigstoreSigned",
        "keyPath": $key,
        "signedIdentity": {"type": "matchRepository"}
    }]' "${policy}" >"${tmp}"
mv "${tmp}" "${policy}"
chmod 0644 "${policy}"

install -d /etc/containers/registries.d
cat >"/etc/containers/registries.d/${BRAND_IMAGE_MAIN}.yaml" <<EOF
docker:
  ${BRAND_REGISTRY}:
    use-sigstore-attachments: true
EOF

jq -e --arg r "${BRAND_REGISTRY}" '.transports.docker[$r][0].type == "sigstoreSigned"' "${policy}" >/dev/null ||
    die "signature policy for ${BRAND_REGISTRY} was not written"
