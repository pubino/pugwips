# VPN Gateway IP Resolver

Automatically resolves VPN gateway hostnames to IP addresses for use with Azure IP Groups and network rules.

## Overview

This solution provides:
- **GitHub Actions workflow** - Automatically resolves IPs every 6 hours and commits updates
- **Python script** - Local DNS resolution with multiple output formats
- **Azure Function** - On-demand IP resolution via HTTP API
- **Infrastructure-as-Code** - Bicep templates for Azure deployment

## Quick Start

### Option 1: GitHub-Only (Recommended)

1. Fork/clone this repository to your GitHub account
2. Push to trigger the workflow or run manually from Actions tab
3. Access resolved IPs in the `output/` directory:
   - `ip_list.txt` - Plain list of IPs
   - `resolved_gateways.json` - Full JSON with hostname-to-IP mappings
   - `azure_ip_group.json` - Azure IP Group format
   - `ip_group.bicep` - Ready-to-deploy Bicep template
   - `ip_group.tf` - Terraform configuration

### Option 2: Local Execution

```bash
# Run the resolver
python resolve_gateways.py

# Custom input/output
python resolve_gateways.py --input gateways.txt --output-dir ./my-output

# Specific format only
python resolve_gateways.py --format ips
```

### Option 3: Azure Function

Deploy an Azure Function for on-demand resolution via HTTP API.

---

## Setup Instructions

### GitHub Setup

1. **Create repository**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   gh repo create pugwips --public --source=. --push
   ```

2. **Enable GitHub Actions**
   - Go to repository Settings > Actions > General
   - Ensure "Allow all actions" is enabled
   - Under "Workflow permissions", select "Read and write permissions"

3. **Trigger first run**
   - Go to Actions tab > "Resolve VPN Gateway IPs" > "Run workflow"
   - Or push a change to `gateways.txt`

### Azure Function Setup

#### Prerequisites
- Azure CLI installed and logged in (`az login`)
- Azure Functions Core Tools (`npm install -g azure-functions-core-tools@4`)
- Python 3.11+

#### Deploy Infrastructure

```bash
# Set your GitHub username
export GITHUB_OWNER="your-github-username"
export GITHUB_REPO="pugwips"
export RESOURCE_GROUP="rg-vpn-gateway-resolver"
export LOCATION="eastus"

# Deploy Azure resources
./infra/deploy.sh
```

#### Deploy Function Code

```bash
cd azure-function

# Get the function app name from deployment output
FUNCTION_APP_NAME="func-vpn-resolver-xxxxx"

# Deploy
func azure functionapp publish $FUNCTION_APP_NAME
```

#### Get Function URL

```bash
# List function keys
az functionapp keys list \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --query functionKeys

# Your function URL will be:
# https://<function-app>.azurewebsites.net/api/resolve_gateway_ips?code=<key>
```

### Using Resolved IPs in Azure

#### Import to Azure IP Group (Azure CLI)

```bash
# Create IP Group from generated file
az network ip-group create \
  --resource-group myResourceGroup \
  --name vpn-gateways \
  --location eastus \
  --ip-addresses $(cat output/ip_list.txt | tr '\n' ' ')
```

#### Import to Azure IP Group (Bicep)

```bash
# Deploy the generated Bicep file
az deployment group create \
  --resource-group myResourceGroup \
  --template-file output/ip_group.bicep
```

#### Import to Azure IP Group (Terraform)

```hcl
# In your Terraform configuration
module "vpn_ip_group" {
  source = "./output"  # Copy ip_group.tf here

  resource_group_name = azurerm_resource_group.main.name
  location           = azurerm_resource_group.main.location
}
```

---

## Teardown Instructions

### Remove Azure Resources

```bash
# Using the teardown script
./infra/teardown.sh

# Or manually
az group delete --name rg-vpn-gateway-resolver --yes
```

### Remove GitHub Repository

```bash
# Archive the repository (keeps history)
gh repo archive owner/pugwips

# Or delete entirely
gh repo delete owner/pugwips --yes
```

---

## Configuration

### Adding/Removing Gateways

Edit `gateways.txt`:
- One hostname per line
- Lines starting with `#` are comments
- Empty lines are ignored

### Changing Update Schedule

Edit `.github/workflows/resolve-gateways.yml`:

```yaml
schedule:
  - cron: '0 */6 * * *'  # Every 6 hours
  # Change to:
  - cron: '0 * * * *'    # Every hour
  - cron: '0 0 * * *'    # Daily at midnight
```

### Azure Function Configuration

Environment variables in Azure Function:
- `GITHUB_OWNER` - GitHub username/org
- `GITHUB_REPO` - Repository name

---

## API Reference

### Azure Function Endpoints

**GET/POST** `/api/resolve_gateway_ips`

Query parameters:
- `format` - Output format: `json` (default), `ips`, `azure`
- `owner` - Override GitHub owner
- `repo` - Override GitHub repo

Examples:
```bash
# Full JSON response
curl "https://func-xxx.azurewebsites.net/api/resolve_gateway_ips?code=xxx"

# Plain IP list
curl "https://func-xxx.azurewebsites.net/api/resolve_gateway_ips?code=xxx&format=ips"

# Azure IP Group format
curl "https://func-xxx.azurewebsites.net/api/resolve_gateway_ips?code=xxx&format=azure"
```

---

## Running Tests

### Local

```bash
pip install -r requirements-dev.txt
pytest -v
```

### Docker

```bash
docker build -f Dockerfile.test -t vpn-resolver-tests .
docker run --rm vpn-resolver-tests
```

### Integration Tests

Integration tests perform actual DNS lookups:

```bash
pytest -v -m integration
```

---

## Output Formats

| File | Description | Use Case |
|------|-------------|----------|
| `ip_list.txt` | Plain IP list, one per line | Shell scripts, simple imports |
| `resolved_gateways.json` | Full JSON with hostnames and IPs | Programmatic access, debugging |
| `azure_ip_group.json` | Azure IP Group ARM format | ARM template deployments |
| `ip_group.bicep` | Azure Bicep template | Bicep deployments |
| `ip_group.tf` | Terraform configuration | Terraform deployments |

---

## Troubleshooting

### Workflow not running
- Check Actions are enabled in repository settings
- Verify workflow permissions allow write access

### DNS resolution failures
- Some hostnames may be temporarily unavailable
- Check the `resolved_gateways.json` for error details
- Failed resolutions are logged but don't stop the process

### Azure Function errors
- Check Application Insights for detailed logs
- Verify the GitHub repository is public or function has access

---

## License

MIT
