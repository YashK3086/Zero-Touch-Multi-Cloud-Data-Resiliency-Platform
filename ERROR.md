# Enterprise DR Platform — Incident & Troubleshooting Knowledge Base (ERROR.md)

This living document chronicles all infrastructure, runtime, authentication, and cloud-provider errors encountered across AWS, Azure, Snowflake, and Terraform throughout the development and deployment of the Zero-Touch Multi-Cloud Data Resiliency Platform.

---

## Table of Incidents & Error Catalogue

| Incident ID | Component | Error Code / Name | Severity | Status |
| :--- | :--- | :--- | :--- | :--- |
| **ERR-001** | AWS STS / Terraform | `InvalidClientTokenId` | High | **RESOLVED** |
| **ERR-002** | Snowflake Terraform Provider | `preview_features_enabled (Failover/Stage/Pipe)` | Medium | **RESOLVED** |
| **ERR-003** | Snowflake Snowpipe DDL | `001757 (42601): Table does not exist` | High | **RESOLVED** |
| **ERR-004** | Snowflake Terraform Provider | `preview_features_enabled (snowflake_table_resource)` | Medium | **RESOLVED** |
| **ERR-005** | Snowflake Replication Engine | `003909 (55000): Disabling replication to primary account not allowed` | Critical | **RESOLVED** |
| **ERR-006** | Snowflake Snowpipe Parquet Ingestion | `002019 (0A000): Parquet single-column variant requirement` | High | **RESOLVED** |
| **ERR-007** | GitHub Actions CI / Terraform | `Exit Code 1: Missing Provider Mock Variables & STS Validation in CI` | High | **RESOLVED** |

---

## Detailed Root Cause Analysis (RCA) & Verified Solutions

### ERR-001: AWS STS Caller Identity Token Invalid
* **Component:** AWS IAM / Terraform AWS Provider
* **Error Name:** `InvalidClientTokenId`
* **Raw Error Log:**
  ```text
  Error: validating provider credentials: retrieving caller identity from STS: operation error STS: GetCallerIdentity, 
  https response error StatusCode: 403, RequestID: cbb3c16e-7933-461d-9945-59a344673a6e, 
  api error InvalidClientTokenId: The security token included in the request is invalid.
  ```
* **Description:** Terraform was unable to authenticate with Amazon Web Services when initializing or applying S3 infrastructure. The shell session did not have the active AWS access key variables exported or the keys were stale.
* **Solution:**
  1. Ran `. .\scripts\Load-Env.ps1` to load and map `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_DEFAULT_REGION` directly into the current PowerShell process environment.
  2. Verified STS caller identity via `aws sts get-caller-identity`.

---

### ERR-002: Snowflake Provider V2 Preview Features Guardrail
* **Component:** Snowflake Terraform Provider (`snowflakedb/snowflake` v2.x)
* **Error Name:** `preview_features_enabled Required for Advanced Objects`
* **Raw Error Log:**
  ```text
  Error: snowflake_failover_group_resource is currently a preview feature, and must be enabled by adding snowflake_failover_group_resource to 'preview_features_enabled' in Terraform configuration.
  Error: snowflake_stage_resource is currently a preview feature...
  Error: snowflake_pipe_resource is currently a preview feature...
  ```
* **Description:** In the new major v2 release of the Snowflake Terraform provider, failover groups, external stages, and snowpipes are gated behind explicit feature opt-in flags to prevent unintentional deployment.
* **Solution:**
  Updated `terraform/providers.tf` to explicitly declare `preview_features_enabled` inside both primary and secondary provider blocks:
  ```hcl
  preview_features_enabled = [
    "snowflake_failover_group_resource",
    "snowflake_stage_resource",
    "snowflake_pipe_resource"
  ]
  ```

---

### ERR-003: Snowpipe Target Table Dependency Order
* **Component:** Snowflake Snowpipe / Cloud Ingestion
* **Error Name:** `001757 (42601): SQL Compilation Error - Target Table Does Not Exist`
* **Raw Error Log:**
  ```text
  Error: 001757 (42601): SQL compilation error:
  Table 'SF_DR_DEMO_DB.DR_STAGING.FINANCIAL_TRANSACTIONS' does not exist
  with snowflake_pipe.dr_financial_pipe, on snowpipe_ingestion.tf line 15:
  15: resource "snowflake_pipe" "dr_financial_pipe"
  ```
* **Description:** `snowflake_pipe` compiles its `COPY INTO` statement against the target table at creation time. Because `FINANCIAL_TRANSACTIONS` had not yet been declared as a Terraform resource, Snowflake rejected the creation of the pipe.
* **Solution:**
  1. Created `snowflake_table.dr_financial_table` in `terraform/snowpipe_ingestion.tf` matching the 11-column PaySim financial dataset schema.
  2. Added explicit Terraform dependency `depends_on = [snowflake_table.dr_financial_table]` to the pipe resource.

---

### ERR-004: Snowflake Table Resource Preview Feature Opt-in
* **Component:** Snowflake Terraform Provider
* **Error Name:** `snowflake_table_resource preview_features_enabled`
* **Raw Error Log:**
  ```text
  Error: snowflake_table_resource is currently a preview feature, and must be enabled by adding snowflake_table_resource to 'preview_features_enabled' in Terraform configuration.
  ```
* **Description:** Similar to ERR-002, when `snowflake_table` was introduced into Terraform configuration, the provider required the table resource type to be included in the preview feature array.
* **Solution:**
  Appended `"snowflake_table_resource"` to `preview_features_enabled` in `terraform/providers.tf` across both AWS and Azure Snowflake providers.

---

### ERR-005: Snowflake Failover Group Primary Account Removal Restriction
* **Component:** Snowflake Cross-Cloud Replication Engine
* **Error Name:** `003909 (55000): Disabling Replication to Primary Account Not Allowed`
* **Raw Error Log:**
  ```text
  Error: error removing allowed accounts for failover group SF_DR_FAILOVER_GROUP err = 003909 (55000): 
  Disabling replication of the replication group to the account in which the primary currently resides is not allowed.
  with snowflake_failover_group.dr_primary_failover_group, on snowflake_replication.tf line 6
  ```
* **Description:** Snowflake failover groups manage multi-account replication topology. Snowflake enforces a strict invariant: the account where the failover group is created (the current Primary) must ALWAYS be present in the `allowed_accounts` list alongside the standby accounts. Defining only the secondary account caused Snowflake to interpret the operation as an attempt to revoke the primary account's own replication membership.
* **Solution:**
  Updated `terraform/snowflake_replication.tf` to explicitly pass both the Primary (AWS) and Secondary (Azure) account identifiers:
  ```hcl
  allowed_accounts = [
    "${local.sf_primary.organization}.${local.sf_primary.account}",
    "${local.sf_secondary.organization}.${local.sf_secondary.account}"
  ]
  ```

### ERR-006: Snowpipe Parquet Multi-Column Mapping Requirement
* **Component:** Snowflake Snowpipe / SQL Engine
* **Error Name:** `002019 (0A000): PARQUET file format can produce one and only one column of type variant`
* **Raw Error Log:**
  ```text
  Error: 002019 (0A000): SQL compilation error:
  PARQUET file format can produce one and only one column of type variant, object, or array. 
  Load data into separate columns using the MATCH_BY_COLUMN_NAME copy option or copy with transformation.
  with snowflake_pipe.dr_financial_pipe, on snowpipe_ingestion.tf line 72
  ```
* **Description:** When executing `COPY INTO` with a multi-column target table from a Parquet external stage, Snowflake by default tries to parse the entire row into a single `VARIANT` column unless explicitly instructed how to map columnar Parquet key names to relational table columns.
* **Solution:**
  Appended `MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE` to the Snowpipe `copy_statement` in `terraform/snowpipe_ingestion.tf`:
  ```sql
  COPY INTO SF_DR_DEMO_DB.DR_STAGING.FINANCIAL_TRANSACTIONS 
  FROM @SF_DR_DEMO_DB.DR_STAGING.SF_PRIMARY_S3_STAGE 
  FILE_FORMAT = (TYPE = 'PARQUET') 
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
  ```

### ERR-007: GitHub Actions CI Runner Missing Provider Credentials on Validate
* **Component:** GitHub Actions CI / Terraform Validation
* **Error Name:** `Exit Code 1: Missing Provider Mock Variables & STS Validation in CI`
* **Raw Error Log:**
  ```text
  Error: validating provider credentials: retrieving caller identity from STS: operation error STS: GetCallerIdentity, 
  https response error StatusCode: 403, api error InvalidClientTokenId: The security token included in the request is invalid.
  Error: Process completed with exit code 1.
  ```
* **Description:** In the GitHub Actions Ubuntu runner, `terraform validate` executes in a clean container without cloud secrets. The AWS Terraform provider by default attempted an STS `GetCallerIdentity` call to retrieve the account ID, which failed and exited with code 1, causing the entire CI workflow to report red.
* **Solution:**
  1. Updated `terraform/providers.tf` to set `skip_credentials_validation = true` and `skip_requesting_account_id = true` on the AWS provider.
  2. In `.github/workflows/enterprise_dr_pipeline.yml`, injected mock CI environment variables (`AWS_ACCESS_KEY_ID`, `ARM_*`, `TF_VAR_snowflake_*`) during the `Terraform Validate` step so that static syntax and configuration analysis passes cleanly without needing live cloud connectivity.

---

## Standard Error Log Entry Template (For Future Incidents)

```markdown
### ERR-XXX: <Short Title>
* **Component:** <AWS | Azure | Snowflake | Terraform | Docker | K8s>
* **Error Name:** `<Exact Error Code / Exception>`
* **Raw Error Log:**
  ```text
  <Paste error traceback>
  ```
* **Description:** <What caused the failure and why>
* **Solution:** <Step-by-step resolution applied>
```