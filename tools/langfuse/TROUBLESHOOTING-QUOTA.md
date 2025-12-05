# Troubleshooting Azure Quota Limits

## Issue: "Current Limit (Basic VMs): 0"

This error occurs when your Azure subscription doesn't have quota available for the requested VM SKU in the specified region.

## Quick Solutions

### Option 1: Use a Different SKU (Recommended)
Standard (S1) tier typically has better quota availability:

```powershell
.\deploy-azure.ps1 -AppServiceSku S1
```

Or try Premium V3 (newest generation, often better availability):

```powershell
.\deploy-azure.ps1 -AppServiceSku P1v3
```

### Option 2: Use a Different Region
Some regions have better quota availability:

```powershell
.\deploy-azure.ps1 -AppServiceSku S1 -Location westus2
```

Common regions with good availability:
- `westus2`
- `eastus2`
- `westeurope`
- `northeurope`
- `southeastasia`

### Option 3: Request Quota Increase

1. **Via Azure Portal**:
   - Go to [Azure Portal](https://portal.azure.com)
   - Navigate to **Subscriptions** → Select your subscription
   - Click **Usage + quotas**
   - Search for "App Service" or "Standard BS Family vCPUs"
   - Click **Request increase**
   - Fill out the form (usually approved within minutes to hours)

2. **Via Azure CLI**:
   ```powershell
   # Check current quota
   az vm list-usage --location eastus --output table
   
   # Create a support ticket for quota increase
   az support tickets create `
     --ticket-name "AppServiceQuotaIncrease" `
     --title "Request App Service quota increase" `
     --description "Need quota for App Service Basic/Standard tier" `
     --severity "minimal" `
     --problem-classification "/providers/Microsoft.Support/services/quota/problemClassifications/cores"
   ```

## SKU Comparison

| SKU | Cores | RAM | Storage | Price/Month | Quota Usually Available |
|-----|-------|-----|---------|-------------|------------------------|
| B1  | 1     | 1.75GB | 10GB | ~$13 | ⚠️ May be limited |
| S1  | 1     | 1.75GB | 50GB | ~$70 | ✅ Usually available |
| P1v2| 1     | 3.5GB | 250GB | ~$146 | ✅ Usually available |
| P1v3| 2     | 4GB | 250GB | ~$124 | ✅ Usually available |

## Deployment Script Parameters

```powershell
# Full example with all options
.\deploy-azure.ps1 `
  -ResourceGroup "rg-langfuse" `
  -Location "eastus2" `
  -AppServiceSku "S1" `
  -AcrName "myacr" `
  -AppService "my-langfuse-app"
```

## Why This Happens

1. **New Subscriptions**: Free/trial subscriptions often have 0 quota for Basic tier
2. **Cost Control**: Microsoft limits certain SKUs to prevent accidental costs
3. **Regional Capacity**: Some regions may be at capacity for certain SKUs
4. **Subscription Type**: Different subscription types (Free, Pay-As-You-Go, Enterprise) have different default quotas

## Best Practice

For **development/testing**: Use S1 (better quota availability, still affordable for testing)

For **production**: Use P1v3 (better performance, newer infrastructure)

## Still Having Issues?

If you continue to have quota issues:

1. **Check subscription limits**:
   ```powershell
   az vm list-usage --location eastus --output table | Select-String "Standard"
   ```

2. **Try multiple regions**:
   ```powershell
   # Check which regions are available
   az account list-locations --output table
   ```

3. **Contact Azure Support**:
   - Free tier: Community support via forums
   - Paid subscriptions: Create a support ticket in Azure Portal

## Example: Successful Deployment with S1

```powershell
# This usually works without quota issues
.\deploy-azure.ps1 -AppServiceSku S1 -Location eastus2

# Output:
# ✅ App Service Plan created (SKU: S1)
# ✅ Deployment Complete!
```

## Cost Comparison

While S1 is more expensive than B1:
- **B1**: $13/month (if quota available)
- **S1**: $70/month (usually available)

You can always **downgrade** after initial deployment:

```powershell
az appservice plan update `
  --name asp-langfuse `
  --resource-group rg-langfuse `
  --sku B1
```

This way you can deploy with S1, verify everything works, then downgrade to B1 if your quota gets approved.
