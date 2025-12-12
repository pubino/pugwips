#!/bin/bash
# Deploy Azure infrastructure for VPN Gateway IP Resolver
set -e

# Configuration
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-vpn-gateway-resolver}"
LOCATION="${LOCATION:-eastus}"
GITHUB_OWNER="${GITHUB_OWNER:-YOUR_GITHUB_USERNAME}"
GITHUB_REPO="${GITHUB_REPO:-pugwips}"

echo "=== VPN Gateway IP Resolver - Azure Deployment ==="
echo "Resource Group: $RESOURCE_GROUP"
echo "Location: $LOCATION"
echo "GitHub: $GITHUB_OWNER/$GITHUB_REPO"
echo ""

# Check if logged in
if ! az account show &>/dev/null; then
    echo "Please log in to Azure first: az login"
    exit 1
fi

# Create resource group
echo "Creating resource group..."
az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --output none

# Deploy infrastructure
echo "Deploying infrastructure..."
DEPLOYMENT_OUTPUT=$(az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --template-file "$(dirname "$0")/main.bicep" \
    --parameters githubOwner="$GITHUB_OWNER" githubRepo="$GITHUB_REPO" \
    --query "properties.outputs" \
    --output json)

FUNCTION_APP_NAME=$(echo "$DEPLOYMENT_OUTPUT" | jq -r '.functionAppName.value')
FUNCTION_APP_URL=$(echo "$DEPLOYMENT_OUTPUT" | jq -r '.functionAppUrl.value')

echo ""
echo "=== Deployment Complete ==="
echo "Function App: $FUNCTION_APP_NAME"
echo "Function URL: $FUNCTION_APP_URL"
echo ""
echo "Next steps:"
echo "1. Deploy the function code:"
echo "   cd azure-function && func azure functionapp publish $FUNCTION_APP_NAME"
echo ""
echo "2. Get the function key:"
echo "   az functionapp keys list -g $RESOURCE_GROUP -n $FUNCTION_APP_NAME --query functionKeys"
echo ""
echo "3. Test the function:"
echo "   curl '$FUNCTION_APP_URL/api/resolve_gateway_ips?code=<function-key>'"
