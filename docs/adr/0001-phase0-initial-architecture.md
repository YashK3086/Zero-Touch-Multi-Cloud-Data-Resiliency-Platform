# ADR 0001: Multi-Cloud Snowflake DR Architecture & Zero-Cost Control Plane

- **Status**: Approved / Phase 0 Baseline
- **Date**: 2026-07-27
- **Deciders**: Infrastructure & Cloud Architect (`InfraAgent`), Data & Security Engineer (`SnowflakeAgent`), SRE Lead (`AutomationAgent`), DevSecOps Lead (`PipelineAgent`), Lead Engineer (Bro)

---

## Context and Problem Statement
We need a production-grade Disaster Recovery (DR) and automated failover control plane for Snowflake across two distinct cloud regions (AWS primary and Azure secondary). The system must guarantee RTO < 2 minutes and RPO ≈ 0 while operating strictly under **zero-cost / free-tier constraints**.

---

## Architectural Decisions & Trade-Off Matrix

### 1. Connection Routing Mechanism
- **Selected**: **Snowflake Native Client Redirect (`CONNECTION` object)**.
- **Alternative Considered**: Custom DNS routing (AWS Route 53 CNAME failover / Cloudflare DNS API).
- **Rationale**: DNS failover depends on client-side DNS caching and TTL propagation delays (often 5 to 15 minutes), violating the RTO < 2-minute SLA. Snowflake Client Redirect manages global URL routing at Snowflake's edge, updating routing tables in < 60 seconds with 0 DNS caching overhead.
- **Trade-Off**: Requires Business Critical edition trial feature in Snowflake, but costs $0 during the 30-day trial period.

### 2. Multi-Cloud Replication Strategy
- **Selected**: **Snowflake Native `FAILOVER GROUP`**.
- **Alternative Considered**: Custom ETL pipelines (e.g., streaming CDC via Kafka or manual script dump & restore).
- **Rationale**: `FAILOVER GROUP` replicates databases, schemas, tables, users, roles, grants, and warehouse definitions in a unified atomic bundle across cloud providers.
- **Trade-Off**: Continuous cross-cloud replication uses Snowflake credit units for data transfer; guarded by placing minimal sample workloads (`SNOWFLAKE_SAMPLE_DATA` TPC-H) and scheduling replication to run efficiently without waste.

### 3. Storage Layer for Staging
- **Selected**: **AWS S3 Free Tier (us-east-1) & Azure Blob Storage Free Account (East US)**.
- **Alternative Considered**: Single cloud storage provider.
- **Rationale**: Complete cloud isolation. If AWS suffers a regional control-plane outage, secondary ingestion pipelines in Azure can immediately run off Azure Blob Storage without relying on AWS endpoints.
- **Trade-Off**: Managing credentials across two cloud providers, handled declaratively in Terraform.

### 4. Compute & Warehouse Auto-Suspend Guardrails
- **Selected**: **Size `X-Small` with `AUTO_SUSPEND = 60` seconds**.
- **Alternative Considered**: Default 600 seconds (10 minutes) auto-suspend.
- **Rationale**: Standard Snowflake auto-suspend is 10 minutes, which consumes 10 extra minutes of credits after every micro-query. Dropping it to 60 seconds ensures virtual warehouses shut down immediately when idle.
- **Trade-Off**: Virtual warehouse cold-start overhead (~1 to 2 seconds on spin-up), completely acceptable for DR testing and batch analytics.

---

## Validation & Compliance Check
- [x] RTO < 2 minutes achievable via Python Client Redirect API.
- [x] Zero-cost guardrails enforced via `X-Small` warehouses & trial credits.
- [x] Declarative IaC ready via Terraform.
