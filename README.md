# Automated Multi-Cloud Disaster Recovery and Dynamic Failover Architecture in Snowflake using GitOps

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Snowflake](https://img.shields.io/badge/Snowflake-Business%20Critical-00A1E0?logo=snowflake&logoColor=white)](https://snowflake.com)
[![AWS](https://img.shields.io/badge/AWS-S3%20Free%20Tier-232F3E?logo=amazon-aws&logoColor=white)](https://aws.amazon.com)
[![Azure](https://img.shields.io/badge/Azure-Blob%20Storage-0089D6?logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com)
[![Terraform](https://img.shields.io/badge/Terraform-1.5%2B-7B42BC?logo=terraform&logoColor=white)](https://terraform.io)

A zero-cost, enterprise-grade multi-cloud disaster recovery (DR) control plane. Continuous cross-cloud replication between **AWS (Primary)** and **Azure (Secondary)** with automated zero-touch failover triggered via a Python SRE health controller and Snowflake Client Redirect URLs.

---

## Key Performance Indicators (KPIs)
- **RTO (Recovery Time Objective)**: `< 2 minutes`
- **RPO (Recovery Point Objective)**: `≈ 0` (Continuous Failover Group async replication)
- **Connection Switchover Time**: `< 60 seconds` (Global Client Redirect URL)
- **Infrastructure Cost**: `$0` (Operates strictly on Snowflake Trial Credits & AWS/Azure Free Tiers)

---

## Architecture Overview

```
                          Global Client Traffic
                                    |
                                    v
                 Snowflake Client Redirect URL (Connection)
                                    |
                  +-----------------+-----------------+
                  | (Primary)                         | (Secondary Standby)
                  v                                   v
         +-----------------+                 +-----------------+
         |   AWS Region    |                 |  Azure Region   |
         | Snowflake (AWS) |===============> | Snowflake (AZ)  |
         +-----------------+  Replication    +-----------------+
                  ^                                   ^
                  |                                   |
                  +------- Python Health Controller ---+
```

---

## Directory Layout
```
├── .github/workflows/   # CI/CD Workflows for GitOps & Validation
├── docs/                # Architecture Diagrams & ADRs
│   ├── adr/             # Architectural Decision Records
│   └── architecture.md  # Detailed System Architecture Blueprint
├── scripts/             # Chaos Testing & Maintenance Scripts
├── src/                 # Python Automated Health & Failover Controller
│   └── sf_dr_controller/
├── terraform/           # IaC for AWS, Azure, & Snowflake
├── memory.md            # Real-time state & credit tracking
├── .gitignore           # Security & secret exclusions
└── README.md            # Project Overview
```

---

## Setup & Quickstart
1. Clone the repository:
   ```bash
   git clone https://github.com/YashK3086/Zero-Touch-Multi-Cloud-Data-Resiliency-Platform.git
   cd Zero-Touch-Multi-Cloud-Data-Resiliency-Platform
   ```
2. Copy sample environment file and configure parameters:
   ```bash
   cp terraform/terraform.tfvars.example terraform/terraform.tfvars
   ```
3. Initialize Terraform:
   ```bash
   cd terraform
   terraform init
   terraform plan
   ```

---

## License
MIT License. Free for open-source and enterprise demonstration.
