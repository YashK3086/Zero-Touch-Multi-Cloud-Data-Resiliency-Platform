# ============================================================
# Azure — Secondary Staging Storage (Free / PAYG)      [InfraAgent]
# ============================================================

resource "azurerm_resource_group" "sf_dr_rg" {
  name     = "rg-sf-dr-${local.env_slug}"
  location = var.azure_location
  tags     = local.common_tags
}

resource "azurerm_storage_account" "sf_secondary_storage" {
  name                            = "sfdrsecstage${local.env_compact}"
  resource_group_name             = azurerm_resource_group.sf_dr_rg.name
  location                        = azurerm_resource_group.sf_dr_rg.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS" # Cheapest redundancy tier
  account_kind                    = "StorageV2"
  access_tier                     = "Hot"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false
  tags                            = local.common_tags
}

resource "azurerm_storage_container" "sf_secondary_container" {
  name                  = "sf-dr-secondary-stage"
  storage_account_id    = azurerm_storage_account.sf_secondary_storage.id
  container_access_type = "private"
}

# Mirror of the S3 1-day expiry guardrail
resource "azurerm_storage_management_policy" "sf_secondary_lifecycle" {
  storage_account_id = azurerm_storage_account.sf_secondary_storage.id

  rule {
    name    = "auto-delete-old-blobs"
    enabled = true
    filters {
      blob_types = ["blockBlob"]
    }
    actions {
      base_blob {
        delete_after_days_since_modification_greater_than = 1
      }
    }
  }
}
