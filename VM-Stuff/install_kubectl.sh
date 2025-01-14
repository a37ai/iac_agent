#!/usr/bin/env bash
set -euxo pipefail

echo "--- Installing kubectl (latest stable) ---"

KUBECTL_VERSION="$(curl -sL https://dl.k8s.io/release/stable.txt | tr -d '\n' | tr -d '\r')"
echo "KUBECTL_VERSION: $KUBECTL_VERSION"

if [[ ! "$KUBECTL_VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Error: Invalid kubectl version format: $KUBECTL_VERSION"
  exit 1
fi

# 1) Download to a temp file (in your user-writable /tmp)
curl -sSLf "https://dl.k8s.io/release/$KUBECTL_VERSION/bin/linux/amd64/kubectl" \
  -o /tmp/kubectl

# 2) Move it into /usr/local/bin with sudo
sudo mv /tmp/kubectl /usr/local/bin/kubectl

# 3) Make it executable
sudo chmod +x /usr/local/bin/kubectl

echo "kubectl install complete."
