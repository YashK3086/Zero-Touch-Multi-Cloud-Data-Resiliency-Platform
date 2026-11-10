# Cloud-Agnostic Multi-Cloud DR SaaS Platform — Architecture Blueprint

## Executive Overview
This document outlines the architecture for the **Auto Fail-Over SaaS Platform**: an automated, cloud-agnostic disaster recovery and workload hydration control plane spanning **AWS**, **Azure**, and **GCP** using **Snowflake Failover Groups**, **Global Anycast Client Redirect**, and a **4-Part Deciding Engine** for container replica hydration.

---

## 1. End-to-End Multi-Cloud SaaS Topology

```
+==================================================================================================+
|                                    GLOBAL ANYCAST ROUTING LAYER                                  |
|                 Snowflake Connection: sf_dr_global_redirect.snowflakecomputing.com               |
+==================================================================================================+
                                    │                                  ▲
                         (Normal Operations)                 (Disaster Promotion)
                                    ▼                                  │
+───────────────────────────────────────────────+  +───────────────────────────────────────────────+
|            PRIMARY CLOUD (e.g., AWS)          |  |          STANDBY CLOUD (e.g., AZURE)          |
|                  (us-east-1)                  |  |                  (East US 2)                  |
+───────────────────────────────────────────────+  +───────────────────────────────────────────────+
| 1. CUSTOMER WORKLOAD TIER (Terraform Demo):   |  | 1. TRANSLATED WORKLOAD TIER (Pilot-Light):    |
|    - EC2 Instance: t3.micro (Active)          |  |    - Container App: paysecure-api-dr          |
|    - Service: paysecure-api (Port 8080)       |  |    - Standby Replicas: 0 ($0.00/hr Idle Cost) |
|    - Discovered dynamically via Cloud API     |  |    - Hydrated Replicas: 1 (On Failover <15s)  |
|                                               |  |                                               |
| 2. SNOWFLAKE PRIMARY DATA TIER (SaaS Built):  |  | 2. SNOWFLAKE STANDBY REPLICA TIER:            |
|    - DB: SF_DR_DEMO_DB (READ-WRITE)           |  |    - DB: SF_DR_DEMO_DB (READ-ONLY REPLICA)    |
|    - Stage: DR_STAGING.CLOUD_DR_STAGE         |  |    - Promoted to READ-WRITE on Failover       |
|    - Table: FINANCIAL_TRANSACTIONS (6.36M)    |  |    - Failover Group: SF_DR_FAILOVER_GROUP     |
|    - Failover Group: SF_DR_FAILOVER_GROUP     |  |      (AS REPLICA OF Primary)                  |
+───────────────────────────────────────────────+  +───────────────────────────────────────────────+
                         ▲                                                 ▲
                         └───────────────────────┬─────────────────────────┘
                                                 │
                       ┌─────────────────────────────────────────────────────┐
                       │     SAAS CONTROL PLANE & 4-PART DECIDING ENGINE     │
                       │     - Hosted UI (Vercel) + FastAPI Engine (Render)  │
                       │     - 1. WorkloadCataloger (Discovery & Blueprints) │
                       │     - 2. CrossCloudTranslator (AWS <-> Azure <-> GCP│
                       │     - 3. WorkloadHydrator (0 -> 1 Pilot-Light Scale)│
                       │     - 4. Bootstrap & 3-Strike Watchdog Sentry       │
                       └─────────────────────────────────────────────────────┘
```

---

## 2. Clear Separation of Responsibilities

1. **Customer Sample App (`terraform/`):**
   - Deploys **only** the customer company's sample production microservice (`paysecure-api` on AWS EC2 `t3.micro` + VPC `10.0.0.0/16` + Security Group port `8080`).
   - Zero DR storage or secondary cloud resources are created by Terraform.
2. **SaaS 1-Click Onboarding (`OnboardingModal.jsx` ➔ `bootstrap.py`):**
   - Customer links Primary & Secondary Snowflake accounts and Cloud Provider API credentials (ID + Secret).
   - Engine auto-detects cloud providers/regions via Snowflake handshake (`CURRENT_REGION()`).
   - Engine dynamically creates Snowflake Warehouses, Databases, Stages (`CLOUD_DR_STAGE`), seeds **6,362,620 PaySim rows**, and links the Cross-Cloud Failover Group + Anycast Redirect connection.
   - `WorkloadCataloger` & `CrossCloudTranslator` discover the primary microservice and register a `$0` idle Pilot-Light replica (`0 replicas`) on the standby cloud.
3. **Failover & Reverse Delta Catch-Up (`workflows.py`):**
   - **Failover:** Syncs final delta, promotes Standby Snowflake to `PRIMARY (R/W)`, flips Anycast DNS, and hydrates Standby containers (`0 ➔ 1` replica).
   - **Failback:** Runs **Reverse WAN Delta Catch-Up** (replicating any disaster transactions written on Standby back to Primary with `RPO = 0`), restores Primary authority, scales Standby containers back to `0`, and auto-generates the ISO/IEC 27001 PDF Audit Certificate in `reports/`.
