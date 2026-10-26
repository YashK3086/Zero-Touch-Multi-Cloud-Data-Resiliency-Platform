# PROJECT MEMORY & STATE TRACKER

## Repository Info
- **Target Repo**: `https://github.com/YashK3086/Zero-Touch-Multi-Cloud-Data-Resiliency-Platform`
- **Project Title**: Automated Multi-Cloud Disaster Recovery and Dynamic Failover Architecture in Snowflake using GitOps

---

## 1. Project Specifications & Objectives
- **Goal**: Production-ready multi-cloud disaster recovery (DR) control plane for Snowflake across AWS (Primary) and Azure (Secondary).
- **Core SLA Targets**:
  - **RTO (Recovery Time Objective)**: < 2 minutes
  - **RPO (Recovery Point Objective)**: ≈ 0 (Continuous Replication via Failover Groups)
  - **Client Connection Failover Latency**: < 60 seconds (Snowflake Client Redirect URL / `CONNECTION` object)
- **Infrastructure Strategy**: 100% Declarative IaC using Terraform, GitOps sync via GitHub Actions.

---

## 2. Strict Zero-Cost Guardrails & Resource Limits
- **Snowflake**:
  - 30-day Free Trial Account ($400 credits) with Business Critical edition enabled for cross-cloud replication & failover groups.
  - Warehouses restricted to `X-Small` size (`AUTO_SUSPEND = 60`, `AUTO_RESUME = TRUE`).
  - Strict 1-day retention limit on temporary stages & queries.
- **AWS**:
  - AWS Free Tier resources only (S3 bucket for state/staging, IAM roles/policies).
- **Azure**:
  - Azure Free Account credits only (Azure Blob Storage for secondary staging).
- **GitHub Actions**:
  - Free Tier runners & minutes.
- **APIs**:
  - Direct SDKs/APIs (Python `snowflake-connector-python`, `boto3`, `azure-storage-blob`). $0 API fees.

---

## 3. Agent Roles & File Mapping Matrix
| Agent Persona | Role Responsibility | Key File / Directory Scope |
|---|---|---|
| **`InfraAgent`** | Infrastructure & Cloud Architect | `/terraform/aws_*.tf`, `/terraform/azure_*.tf` |
| **`SnowflakeAgent`** | Snowflake Data & Security Engineer | `/terraform/snowflake_*.tf`, `/scripts/setup_snowflake.sql` |
| **`AutomationAgent`** | Automation & SRE Lead | `/src/sf_dr_controller/`, `/scripts/inject_simulated_outage.py` |
| **`PipelineAgent`** | DevSecOps & Governance Lead | `/.github/workflows/`, `memory.md`, `/docs/` |

---

## 4. Environment Variables & Credentials Schema
The following secrets are required in local `.env` and GitHub Secrets.
Full template: `.env.example`. Load locally with `. .\scripts\Load-Env.ps1`, which maps
`AZURE_*` -> `ARM_*` (azurerm) and `SNOWFLAKE_*` -> `TF_VAR_snowflake_*` (Terraform).
`terraform.tfvars` now holds **non-secret values only**.

```bash
# Snowflake Credentials (AWS Primary & Azure Secondary)
SNOWFLAKE_ACCOUNT_PRIMARY="<org>-<aws_account_name>"     # AWS Primary Account
SNOWFLAKE_ACCOUNT_SECONDARY="<org>-<azure_account_name>" # Azure Secondary Account
SNOWFLAKE_USER="DR_CONTROLLER_USER"
SNOWFLAKE_PASSWORD="<SecurePassword123!>"
SNOWFLAKE_ROLE="ACCOUNTADMIN"

# Snowflake Client Redirect Configuration
SNOWFLAKE_REDIRECT_CONNECTION_NAME="SF_DR_GLOBAL_REDIRECT"
SNOWFLAKE_FAILOVER_GROUP_NAME="SF_DR_FAILOVER_GROUP"

# Cloud Provider Storage Credentials
AWS_ACCESS_KEY_ID="<AWS_FREE_TIER_KEY>"
AWS_SECRET_ACCESS_KEY="<AWS_FREE_TIER_SECRET>"
AWS_REGION="us-east-1"
AWS_S3_BUCKET="sf-dr-primary-stage-bucket"

AZURE_SUBSCRIPTION_ID="<AZURE_SUB_ID>"
AZURE_TENANT_ID="<AZURE_TENANT_ID>"
AZURE_CLIENT_ID="<AZURE_CLIENT_ID>"
AZURE_CLIENT_SECRET="<AZURE_CLIENT_SECRET>"
AZURE_STORAGE_ACCOUNT="sfdrsecondaryblob"
AZURE_STORAGE_CONTAINER="sf-dr-secondary-stage"
```

---

## 5. Cloud Cost & Credit Balance Tracker
| Platform | Plan / Tier | Allocated Budget | Used to Date | Current Balance | Status |
|---|---|---|---|---|---|
| **Snowflake Primary (AWS)** | Business Critical (`NNFCDXY-SF_AWS_PRIMARY`) | Capped by `DR_CREDIT_GUARD` (10 credits/mo) | < 0.5 Credits | Active | 🟢 Healthy |
| **Snowflake Secondary (Azure)** | Business Critical (`NNFCDXY-SF_AZURE_DR`) | Capped by `DR_CREDIT_GUARD` (10 credits/mo) | < 0.5 Credits | Active | 🟢 Healthy |
| **Snowflake Org / Billing** | Standard (`NNFCDXY-OZ10928` / Credit Card) | Account creation & Org admin | $0.00 | Active | 🟢 Healthy |
| **AWS** | Free Tier (`621236283472`) | $0.00 (Free Tier S3/IAM) | $0.00 | $0.00 | 🟢 Healthy |
| **Azure** | Pay-As-You-Go (`Subscription 1`) | Pay-per-use (cents for Blob) | $0.00 | Active | 🟢 Healthy |
| **GitHub Actions** | Public Repo Free | 2,000 Mins/mo | 0 Mins | 2,000 Mins | 🟢 Healthy |

---

## 6. 35-40 Day Project Timeline & Sprint Roadmap

| Timeline | Phase & Milestone | Deliverables & Focus | Trial Credit Plan | Status |
|---|---|---|---|---|
| **Days 1–3** | **Phase 0**: Architecture & Repo Setup | Repo layout, `memory.md`, ADRs, IaC scaffolding | $0 (Local/IaC) | 🟢 **COMPLETED** |
| **Days 4–9 (Week 1)** | **Phase 1**: Multi-Cloud Storage & Compute | AWS S3, Azure Blob, Snowflake DB/WH/Schema via Terraform | $0 (Free Tiers) | 🟢 **COMPLETED (All 14 resources deployed)** |
| **Days 10–18 (Week 2)** | **Phase 2**: Multi-Cloud Replication & Redirect | Failover Group `SF_DR_FAILOVER_GROUP`, Client Redirect `SF_DR_GLOBAL_REDIRECT` | ~$10–$20 Credits | 🟢 **COMPLETED (Live Replication & Switchover Verified)** |
| **Days 19–26 (Week 3)** | **Phase 3**: Python Health Controller | `sf_dr_controller` package: probes, state machine, failover/failback, CLI, tests | ~$5–$10 Credits | 🟢 **COMPLETED (28 unit tests passing, CLI tested)** |
| **Days 27–33 (Week 4)** | **Phase 4**: Chaos Testing & Failover Audit | `inject_simulated_outage.py`, live RTO/RPO benchmarking (<2 min RTO), Failback | ~$15–$25 Credits | 🟢 **BENCHMARKED (RTO 6.85s, Switchover 2.28s, RPO 0)** |
| **Days 34–40 (Week 5-6)** | **Phase 5**: DevSecOps & Portfolio Deliverables | GitHub Actions CI/CD, OPA/tfsec/ZAP scanning, video demo script | $0 (CI/CD Free) | ⏳ Next Up |

---

## 7. Live Account Status (last checked 2026-10-24 02:35 IST)
| Account | Identifier | Region / Edition | Role / Status |
|---|---|---|---|
| AWS | `621236283472` (`admin_user`) | `us-east-1` | S3 remote state intact; stage bucket destroyed ($0 burn) 🟢 Standby |
| Azure | sub `1fbaecf5-392d-4648-9f2e-4d694cfc0b83` | `East US` | RG and Storage Account destroyed ($0 burn) 🟢 Standby |
| Snowflake Primary | `NNFCDXY-SF_AWS_PRIMARY` (`AWC63551`) | AWS `us-east-1` (Business Critical) | DB & WH destroyed; account & key-pair ready for apply 🟢 Standby |
| Snowflake Secondary | `NNFCDXY-SF_AZURE_DR` (`LQB72917`) | Azure `eastus2` (Business Critical) | Replica DB & WH destroyed; account & key-pair ready 🟢 Standby |
| Snowflake Org Admin | `NNFCDXY-OZ10928` (`PP26358`) | AWS `ap-southeast-7` (Standard) | Org management & payment billing anchor 🟢 Active |

---

## 8. Verified Benchmark Metrics
- **PaySim Full Dataset Ingestion**: **6,362,620 rows in 10.76 seconds** ($1.59 Trillion transaction volume).
- **RPO (Recovery Point Objective)**: **0.00 seconds / 0 dropped rows** (Cryptographic hash `-1122128966777340010` 100% identical on AWS & Azure).
- **WAN Cross-Cloud Delta Sync (6.36M rows)**: **17.18 seconds** (AWS us-east-1 -> Azure eastus2).
- **RTO (Recovery Time Objective)**: **4.84 - 5.88 seconds** (Promote Failover Group + Redirect Connection on Azure). SLA Target: < 120s.
- **Failback Time**: **19.37 seconds** (Catch-up refresh + Promote Failover Group + Redirect Connection back to AWS). SLA Target: < 120s.
- **Client Connection Redirect Switchover**: **1.988 seconds** (`nnfcdxy-sf_dr_global_redirect.snowflakecomputing.com`). SLA Target: < 60s.
- **Zero-Cost Clean Teardown**: `terraform destroy -auto-approve` executed successfully ($0.00 ongoing cloud burn).

---

## 9. Changelog
- **2026-10-23** — Audit: all Phase 1 resources found destroyed (state empty since 2026-08-26). Snowflake trial and Azure free sub expired.
- **2026-10-23** — Refactor: `main.tf` split into `versions/providers/locals/aws_storage/azure_storage/snowflake_core.tf`; providers upgraded (aws ~>6, azurerm ~>5, snowflakedb/snowflake ~>2.22); S3 remote backend + `terraform/bootstrap`; `DR_CREDIT_GUARD` resource monitor; S3/Azure hardening (public-access block, SSE, TLS1.2, 1-day lifecycle on both clouds); credentials moved out of tfvars to env vars.
- **2026-10-23** — Controller: implemented `sf_dr_controller` (config, sql, connection, health, state, failover, CLI, JSON logging) + pytest suite (28 tests passing).
- **2026-10-24** — Phase 1 Deployed: AWS S3, Azure Blob Storage (`sfdrsecstagedrdemo`), Snowflake Primary DB (`SF_DR_DEMO_DB`), WH, Schema, Resource Monitor applied via Terraform into S3 state. Primary RSA JWT auth verified 100% healthy. Cross-account replication parameter enabled via ORGADMIN.
- **2026-10-24** — Multi-Cloud Business Critical Accounts Provisioned: created `SF_AWS_PRIMARY` (AWS us-east-1) and `SF_AZURE_DR` (Azure eastus2) with RSA key-pair authentication.
- **2026-10-24** — Phase 2 & 3 Live Validation: provisioned `SF_DR_FAILOVER_GROUP` and Client Redirect `SF_DR_GLOBAL_REDIRECT`. Executed live failover to Azure (6.85s) and live failback to AWS (19.22s) with 0 data loss.
- **2026-10-24** — Zero-Cost Teardown: executed `terraform destroy` (14/14 resources destroyed, $0 overnight burn). Added `snowflake_replication.tf` and `Deploy-All.ps1` for 1-command 20-resource automated build.
- **2026-10-25** — PaySim Financial Dataset Pre-Staged: pre-staged 6.36M PaySim dataset into 500,000-row baseline and 10 streaming chunks; verified cryptographic checksum & mathematical $RPO = 0$ cross-cloud verifier.
- **2026-10-26** — 100% Native Architecture Shift: deleted all mock simulation scripts (`mock_stream_producer.py`); provisioned AWS S3 -> SQS -> Snowpipe auto-ingestion; built enterprise CI/CD pipeline in `.github/workflows/enterprise_dr_pipeline.yml`.
- **2026-10-26** — Git Push Hook & Auto-Pop UI: implemented `.git/hooks/pre-push` to auto-fetch all remote branches, sync audit logs, and auto-pop the Mission Control Web App with live Git author, SHA, and multi-branch developer tracking table.
- **2026-10-26** — Full 6.36M PaySim Production Verification: successfully bulk-loaded all 6,362,620 transactions ($1.59 Trillion) in 10.76s; replicated to Azure in 17.18s; verified bit-for-bit $RPO = 0$ cryptographic checksum match (`-1122128966777340010`).
- **2026-10-26** — Live Client Anycast Redirection & Failback: executed live failover in 4.84s (Anycast DNS pointer flipped to Azure); executed failback in 19.37s with 0 dropped transactions.
- **2026-10-26** — CI/CD Pipeline Stabilization: resolved provider STS 403 checks across both `enterprise_dr_pipeline.yml` and legacy `ci.yml`, making all GitHub Actions runs 100% green.
- **2026-10-26** — Post-Testing Zero-Cost Cleanup: executed `terraform destroy -auto-approve`, successfully tearing down all 20 cloud resources with $0.00 ongoing cloud burn.
- **2026-10-26** — Error Knowledge Base Established: created `ERROR.md` logging ERR-001 through ERR-009 with root cause analysis and verified solutions.

---

## 10. Operational Protocol & Mandatory Error Logging Rule
- **Mandatory Error Logging**: Every runtime, provider, or DDL error encountered must be immediately logged into `ERROR.md` following the standard schema:
  - Incident ID (`ERR-XXX`)
  - Component (`AWS`, `Azure`, `Snowflake`, `Terraform`, etc.)
  - Error Name & Raw Stack Trace
  - Root Cause Analysis (RCA)
  - Verified Code / Operational Solution
- **Zero Simulation Mandate**: All pipelines, ingestion stages, databases, and global redirect DNS objects must use 100% native cloud services (AWS S3, Amazon SQS, Snowflake Snowpipe, Snowflake Failover Groups, Snowflake Client Redirect Connection). Only external physical disasters are simulated via chaos drill failure injection.
- **Multi-Branch Git Sync**: The local pre-push hook ensures all branches and active developer metadata are synchronized before the Mission Control UI surfaces real-time metrics.


