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

### 🚨 1-Click Emergency Zero-Touch Launch (< 10 seconds)
In case of a production disaster or audit review, any team member can clone and immediately launch the Executive Control Plane:

```bash
# Clone the repository
git clone https://github.com/YashK3086/Zero-Touch-Multi-Cloud-Data-Resiliency-Platform.git
cd Zero-Touch-Multi-Cloud-Data-Resiliency-Platform

# Double-click or run the 1-click bootstrap launcher:
./emergency.bat
# Or in PowerShell:
./emergency.ps1
```

The script automatically boots the containerized control plane on port `8000` and opens the web interface in your browser. From there, you can execute a 1-click failover to Azure in **under 5 seconds**.

---

### 🐳 Containerized Deployment (Docker & Kubernetes)

#### Option 1: Docker Compose
```bash
docker compose up -d --build
# Open http://localhost:8000/
```

#### Option 2: Kubernetes (Local / Minikube / Cloud)
```bash
kubectl apply -f k8s/
# Port-forward the dashboard service:
kubectl port-forward svc/sf-dr-dashboard-service 8000:80
```

---

### 🛠️ Infrastructure Provisioning (Terraform)
1. Load environment variables:
   ```powershell
   . .\scripts\Load-Env.ps1
   ```
2. Run Terraform plan & apply:
   ```powershell
   cd terraform
   terraform init -backend-config=backend.hcl
   terraform plan
   terraform apply
   ```

---

## License
MIT License. Free for open-source and enterprise demonstration.
