#!/usr/bin/env bash
# Build the two images and put them in the cluster without a registry.
#
# Images are tagged with the git SHA, never `latest`: a rollback has to be a
# real rollback, and `latest` makes "which build is running" unanswerable.
set -euo pipefail

CLUSTER="${CLUSTER:-rancher-cluster}"
SHA="$(git rev-parse --short=12 HEAD)"
DIRTY=""
git diff --quiet || DIRTY="-dirty"
TAG="${SHA}${DIRTY}"

if [[ -n "$DIRTY" ]]; then
  echo "warning: working tree is dirty; tagging ${TAG}" >&2
  echo "         a -dirty image is for your laptop, never for a demo" >&2
fi

for img in coding-engineer eval-harness; do
  echo "==> building ${img}:${TAG}"
  docker build -f "docker/Dockerfile.${img}" -t "localhost/ai-sdlc/${img}:${TAG}" .
  echo "==> importing into ${CLUSTER}"
  k3d image import "localhost/ai-sdlc/${img}:${TAG}" -c "${CLUSTER}"
done

echo
echo "Set the tag in the overlay, then apply:"
echo "  (cd deploy/overlays/local && kustomize edit set image \\"
echo "     localhost/ai-sdlc/coding-engineer=localhost/ai-sdlc/coding-engineer:${TAG} \\"
echo "     localhost/ai-sdlc/eval-harness=localhost/ai-sdlc/eval-harness:${TAG})"
echo "  kubectl apply -k deploy/overlays/local"
