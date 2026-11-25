#!/usr/bin/env bash
# Creates everything the free-tier deployment needs on an Azure for Students subscription, then
# stores the connection details as GitHub secrets. Run it in Azure Cloud Shell (portal.azure.com,
# the >_ button, Bash), which is already signed in to Azure and has git, ssh and gh:
#
#   git clone https://github.com/<owner>/<repo>.git && cd <repo>
#   DNS_LABEL=myflatmate-api bash infrastructure/free-tier/provision-azure.sh
#
# What it creates (one resource group, delete the group to remove it all):
#   - an Ubuntu 24.04 VM, Standard_B2ats_v2 (2 vCPU, 1 GiB), 64 GB premium SSD: the sizes the
#     12-month free offer covers (750 VM hours a month, two 64 GB P6 disks);
#   - a static public IP with a DNS name: <DNS_LABEL>.<region>.cloudapp.azure.com;
#   - firewall rules for SSH, HTTP and HTTPS only;
#   - a private storage account for database backups (blobs deleted after 30 days) and a
#     create-only access link for the backup job, valid one year;
#   - a dedicated SSH key for deploys (kept in Cloud Shell's ~/.ssh).
#
# Azure for Students allows only some regions per subscription, so it tries REGIONS in order.
# Without a credit card there is a hard spending limit: nothing can bill you beyond the credit.
set -euo pipefail

DNS_LABEL=${DNS_LABEL:?Set DNS_LABEL, e.g. DNS_LABEL=myflatmate-api (letters, digits and hyphens; unique in the region)}
RG=${RG:-flatmate-rg}
VM=${VM:-flatmate-vm}
SIZE=${SIZE:-Standard_B2ats_v2}
REGIONS=${REGIONS:-"centralindia southindia southeastasia eastasia uaenorth westeurope eastus"}
ADMIN=deploy  # cloud-init.yaml allows SSH for this user only
KEY=${KEY:-$HOME/.ssh/flatmate_deploy}
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=${REPO:-$(git -C "$HERE" remote get-url origin 2>/dev/null | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')}

[[ "$DNS_LABEL" =~ ^[a-z][a-z0-9-]{1,61}[a-z0-9]$ ]] || { echo "DNS_LABEL must be lowercase letters, digits and hyphens"; exit 1; }
az account show >/dev/null || { echo "Sign in first: az login"; exit 1; }
echo "Subscription: $(az account show --query name -o tsv)"

if [ ! -f "$KEY" ]; then
  mkdir -p "$(dirname "$KEY")"
  ssh-keygen -q -t ed25519 -N "" -C "flatmate-deploy" -f "$KEY"
fi

region=""
if az group show -n "$RG" >/dev/null 2>&1 && az vm show -g "$RG" -n "$VM" >/dev/null 2>&1; then
  region=$(az group show -n "$RG" --query location -o tsv)
  echo "The VM already exists in $region; reusing it."
else
  for candidate in $REGIONS; do
    echo "Trying region $candidate ..."
    az group create -n "$RG" -l "$candidate" -o none
    if az vm create -g "$RG" -n "$VM" -l "$candidate" \
        --image Canonical:ubuntu-24_04-lts:server:latest --size "$SIZE" \
        --admin-username "$ADMIN" --ssh-key-values "$KEY.pub" \
        --os-disk-size-gb 64 --storage-sku Premium_LRS \
        --public-ip-sku Standard --public-ip-address-allocation static \
        --public-ip-address-dns-name "$DNS_LABEL" \
        --custom-data "$HERE/cloud-init.yaml" -o none 2> /tmp/vm-create.err; then
      region=$candidate
      break
    fi
    echo "  not available here: $(grep -oE '(RequestDisallowedByAzure|SkuNotAvailable|QuotaExceeded|DnsRecordInUse|[A-Za-z]+Error)' /tmp/vm-create.err | head -1)"
    if grep -q DnsRecordInUse /tmp/vm-create.err; then
      az group delete -n "$RG" --yes -o none
      echo "The DNS name '$DNS_LABEL' is taken in $candidate. Choose another DNS_LABEL."; exit 1
    fi
    az group delete -n "$RG" --yes -o none
  done
  [ -n "$region" ] || { echo "No region in '$REGIONS' allowed $SIZE. Set REGIONS to the ones your subscription allows (Azure portal > Policy > 'Allowed locations')."; exit 1; }
fi

az vm open-port -g "$RG" -n "$VM" --port 80,443 --priority 900 -o none
HOST=$(az network public-ip list -g "$RG" --query "[0].dnsSettings.fqdn" -o tsv)
echo "VM ready: $HOST (region $region)"

echo "Waiting for first-boot setup (updates, Docker, firewall); this takes a few minutes ..."
for _ in $(seq 1 60); do
  ssh-keyscan -t ed25519 "$HOST" 2>/dev/null | grep -q ed25519 && break
  sleep 5
done
KNOWN_HOSTS=$(ssh-keyscan -t ed25519 "$HOST" 2>/dev/null)
echo "$KNOWN_HOSTS" > /tmp/flatmate_known_hosts
ssh -i "$KEY" -o UserKnownHostsFile=/tmp/flatmate_known_hosts -o StrictHostKeyChecking=yes "$ADMIN@$HOST" \
  'sudo cloud-init status --wait >/dev/null; cloud-init status; docker --version; docker compose version; swapon --show; sudo ufw status | head -6'

# Backups: private storage; the job gets a create-only link (it can never read, overwrite or
# delete a backup); backups are deleted after 30 days.
STORAGE=${STORAGE:-$(echo "fm${DNS_LABEL//-/}bk" | cut -c1-24)}
if ! az storage account show -g "$RG" -n "$STORAGE" >/dev/null 2>&1; then
  az storage account create -g "$RG" -n "$STORAGE" -l "$region" --sku Standard_LRS --kind StorageV2 \
    --min-tls-version TLS1_2 --allow-blob-public-access false --https-only true -o none
fi
ACCOUNT_KEY=$(az storage account keys list -g "$RG" -n "$STORAGE" --query "[0].value" -o tsv)
az storage container create --account-name "$STORAGE" --account-key "$ACCOUNT_KEY" -n db-backups -o none
cat > /tmp/lifecycle.json <<'JSON'
{"rules": [{"enabled": true, "name": "expire-backups", "type": "Lifecycle",
  "definition": {"filters": {"blobTypes": ["blockBlob"], "prefixMatch": ["db-backups/"]},
                 "actions": {"baseBlob": {"delete": {"daysAfterModificationGreaterThan": 30}}}}}]}
JSON
az storage account management-policy create -g "$RG" --account-name "$STORAGE" --policy @/tmp/lifecycle.json -o none
EXPIRY=$(date -u -d "+365 days" +%Y-%m-%dT%H:%MZ)
SAS=$(az storage container generate-sas --account-name "$STORAGE" --account-key "$ACCOUNT_KEY" -n db-backups \
  --permissions c --expiry "$EXPIRY" --https-only -o tsv)
BACKUP_URL="https://$STORAGE.blob.core.windows.net/db-backups?$SAS"
unset ACCOUNT_KEY

if command -v gh >/dev/null && gh auth status >/dev/null 2>&1 && [ -n "$REPO" ]; then
  gh secret set FREE_TIER_HOST -R "$REPO" -b "$HOST"
  gh secret set FREE_TIER_SSH_KEY -R "$REPO" < "$KEY"
  gh secret set FREE_TIER_SSH_KNOWN_HOSTS -R "$REPO" -b "$KNOWN_HOSTS"
  gh secret set BACKUP_AZURE_SAS_URL -R "$REPO" -b "$BACKUP_URL"
  echo "Saved FREE_TIER_HOST, FREE_TIER_SSH_KEY, FREE_TIER_SSH_KNOWN_HOSTS and BACKUP_AZURE_SAS_URL to $REPO."
else
  echo
  echo "GitHub CLI isn't signed in, so nothing was saved to GitHub. Run 'gh auth login', then run"
  echo "this script again (it reuses the VM). Don't paste the deploy key into chat or files."
fi

echo
echo "Done. API address: https://$HOST (or point your own domain's A record at $(az network public-ip list -g "$RG" --query '[0].ipAddress' -o tsv))."
echo "The backup link expires $EXPIRY: run this script again before then to renew it."
