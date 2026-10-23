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
| **Snowflake** | Trial EXPIRED -> converting to On-Demand (billing added) | Capped by `DR_CREDIT_GUARD` (10 credits/mo) | $0.00 | n/a | 🟡 Recovering |
| **AWS** | Free Tier | $0.00 (Free Tier) | $0.00 | $0.00 | 🟢 Healthy |
| **Azure** | Free Account expired -> upgrading to Pay-As-You-Go | Pay-per-use (cents) | $0.00 | n/a | 🟡 Recovering |
| **GitHub Actions** | Public Repo Free | 2,000 Mins/mo | 0 Mins | 2,000 Mins | 🟢 Healthy |

---

## 6. 35-40 Day Project Timeline & Sprint Roadmap

### ⏳ Snowflake Trial Synchronization Rule
> **CRITICAL**: The 30-day Snowflake trial clock starts as soon as the account is created. To maximize value, we align the 30-day trial window with Weeks 1–4 so all replication, failover, and chaos testing take place inside the active trial window.

| Timeline | Phase & Milestone | Deliverables & Focus | Trial Credit Plan | Status |
|---|---|---|---|---|
| **Days 1–3** | **Phase 0**: Architecture & Repo Setup | Repo layout, `memory.md`, ADRs, IaC scaffolding | $0 (Local/IaC) | 🟢 **COMPLETED** |
| **Days 4–9 (Week 1)** | **Phase 1**: Multi-Cloud Storage & Compute | AWS S3, Azure Blob, Snowflake DB/WH/Schema via Terraform | $0 (Free Tiers) | 🟡 **CODE REFACTORED, RE-APPLY PENDING** (destroyed 2026-08-26) |
| **Days 10–18 (Week 2)** | **Phase 2**: Multi-Cloud Replication & Redirect | Provision AWS + Azure Snowflake external stages, Failover Group, Client Redirect URL | ~$10–$20 Credits | ⏳ Next Up (blocked on account recovery) |
| **Days 19–26 (Week 3)** | **Phase 3**: Python Health Controller | `sf_dr_controller` package: probes, state machine, failover/failback, CLI, tests | ~$5–$10 Credits | 🟡 **CODE DONE (unit-tested)**, live validation pending |
| **Days 27–33 (Week 4)** | **Phase 4**: Chaos Testing & Failover Audit | `inject_simulated_outage.py`, live RTO/RPO benchmarking (<2 min RTO), Failback | ~$15–$25 Credits | 📅 Planned |
| **Days 34–40 (Week 5-6)** | **Phase 5**: DevSecOps & Portfolio Deliverables | GitHub Actions CI/CD, OPA/tfsec/ZAP scanning, video demo script | $0 (CI/CD Free) | 📅 Planned |

---

## 7. Live Account Status (last checked 2026-10-23 19:20 IST)
| Account | Identifier | Status | Action |
|---|---|---|---|
| AWS | `621236283472` (`admin_user`) | 🟢 Active | Rotate access key (exposed in agent log 2026-10-23) |
| Azure | sub `5447fc2b-…` | 🔴 SP sees 0 subscriptions | Upgrade to PAYG, re-grant SP Contributor, rotate SP secret |
| Snowflake Primary (AWS) | `NNFCDXY-OZ10928` | 🔴 Trial ended (390913) | Add billing in Snowsight |
| Snowflake Secondary (Azure) | `NNFCDXY-SF_AZURE_SECONDARY` | 🔴 Bad credentials (390100); same org ✅ | Recover admin login or recreate via ORGADMIN |

---

## 8. Changelog
- **2026-10-23** — Audit: all Phase 1 resources found destroyed (state empty since 2026-08-26). Snowflake trial and Azure free sub expired.
- **2026-10-23** — Refactor: `main.tf` split into `versions/providers/locals/aws_storage/azure_storage/snowflake_core.tf`; providers upgraded (aws ~>6, azurerm ~>5, snowflakedb/snowflake ~>2.22); S3 remote backend + `terraform/bootstrap`; `DR_CREDIT_GUARD` resource monitor; S3/Azure hardening (public-access block, SSE, TLS1.2, 1-day lifecycle on both clouds); credentials moved out of tfvars to env vars.
- **2026-10-23** — Controller: implemented `sf_dr_controller` (config, sql, connection, health, state, failover, CLI, JSON logging) + pytest suite.


