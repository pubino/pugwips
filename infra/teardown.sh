#!/bin/bash
# Teardown Azure infrastructure for VPN Gateway IP Resolver
set -e

RESOURCE_GROUP="${RESOURCE_GROUP:-rg-vpn-gateway-resolver}"

echo "=== VPN Gateway IP Resolver - Azure Teardown ==="
echo "This will DELETE the resource group: $RESOURCE_GROUP"
echo "and ALL resources within it."
echo ""

read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo "Deleting resource group $RESOURCE_GROUP..."
az group delete --name "$RESOURCE_GROUP" --yes --no-wait

echo "Deletion initiated. It may take a few minutes to complete."
echo "Check status with: az group show -n $RESOURCE_GROUP"
