# ============================================================
# AWS — Sample App Production Infrastructure (Free Tier)
# ============================================================

# 1. Dedicated VPC for Disaster Recovery Testing
resource "aws_vpc" "sample_app_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.common_tags, {
    Name = "sf-dr-sample-app-vpc-${local.env_slug}"
  })
}

# 2. Public Subnet
resource "aws_subnet" "sample_app_public_subnet" {
  vpc_id                  = aws_vpc.sample_app_vpc.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "${var.aws_region}a"

  tags = merge(local.common_tags, {
    Name = "sf-dr-public-subnet-${local.env_slug}"
  })
}

# 3. Internet Gateway
resource "aws_internet_gateway" "sample_app_igw" {
  vpc_id = aws_vpc.sample_app_vpc.id

  tags = merge(local.common_tags, {
    Name = "sf-dr-igw-${local.env_slug}"
  })
}

# 4. Route Table & Association
resource "aws_route_table" "sample_app_public_rt" {
  vpc_id = aws_vpc.sample_app_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.sample_app_igw.id
  }

  tags = merge(local.common_tags, {
    Name = "sf-dr-public-rt-${local.env_slug}"
  })
}

resource "aws_route_table_association" "sample_app_public_assoc" {
  subnet_id      = aws_subnet.sample_app_public_subnet.id
  route_table_id = aws_route_table.sample_app_public_rt.id
}

# 5. Security Group
resource "aws_security_group" "sample_app_sg" {
  name        = "sf-dr-sample-app-sg-${local.env_slug}"
  description = "Allows HTTP 8080 (PaySecure API) and HTTP 80 inbound"
  vpc_id      = aws_vpc.sample_app_vpc.id

  ingress {
    description = "PaySecure Microservice Port"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP Traffic"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH for Administration"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "sf-dr-sample-app-sg-${local.env_slug}"
  })
}

# 6. Current AWS Account Identity & Demo App S3 Dataset Bucket
data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "sample_app_data_bucket" {
  bucket        = "sf-dr-paysecure-appdata-${data.aws_caller_identity.current.account_id}"
  force_destroy = true

  tags = merge(local.common_tags, {
    Name = "sf-dr-paysecure-appdata-${local.env_slug}"
    Role = "PrimaryAppDataset"
  })
}

resource "aws_s3_object" "paysim_dataset_manifest" {
  bucket       = aws_s3_bucket.sample_app_data_bucket.id
  key          = "paysim/paysim_6m_production_manifest.json"
  content_type = "application/json"
  content = jsonencode({
    dataset      = "PaySim_Financial_Ledger_v1"
    total_rows   = 6362620
    fraud_rows   = 8213
    source_app   = "paysecure-api"
    cloud        = "AWS"
    region       = var.aws_region
    storage_type = "S3_THROW_STAGE_AND_SNOWPIPE"
  })
}

# 7. Latest Amazon Linux 2023 AMI (Free Tier)
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

# 8. EC2 Instance running PaySecure API
resource "aws_instance" "sample_app_instance" {
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = "t3.micro" # 100% AWS Free Tier
  subnet_id                   = aws_subnet.sample_app_public_subnet.id
  vpc_security_group_ids      = [aws_security_group.sample_app_sg.id]
  associate_public_ip_address = true

  user_data = <<-EOF
              #!/bin/bash
              cat << 'PYEOF' > /opt/paysecure_server.py
              import json, os, socket, time
              from http.server import BaseHTTPRequestHandler, HTTPServer

              class PaySecureHandler(BaseHTTPRequestHandler):
                  def _send(self, code, payload):
                      body = json.dumps(payload).encode("utf-8")
                      self.send_response(code)
                      self.send_header("Content-Type", "application/json")
                      self.send_header("Access-Control-Allow-Origin", "*")
                      self.send_header("Content-Length", str(len(body)))
                      self.end_headers()
                      self.wfile.write(body)

                  def do_GET(self):
                      if self.path.startswith("/health"):
                          self._send(200, {
                              "status": "healthy",
                              "service": "paysecure-api",
                              "cloud": "AWS",
                              "instance_id": socket.gethostname(),
                              "region": "${var.aws_region}",
                              "dataset_rows": 6362620,
                              "timestamp": time.time(),
                          })
                      else:
                          self._send(200, {"service": "paysecure-api", "status": "ONLINE", "cloud": "AWS"})

                  def do_POST(self):
                      self._send(200, {
                          "status": "PROCESSED",
                          "route": "AWS_PRIMARY_S3_SNOWPIPE",
                          "destination": "Snowflake Anycast",
                          "latency_ms": 11.4,
                          "timestamp": time.time(),
                      })

              if __name__ == "__main__":
                  HTTPServer(("0.0.0.0", 8080), PaySecureHandler).serve_forever()
              PYEOF
              nohup python3 /opt/paysecure_server.py > /var/log/paysecure.log 2>&1 &
              EOF

  tags = merge(local.common_tags, {
    Name = "sf-dr-paysecure-api-primary-${local.env_slug}"
    Role = "PrimaryWorkload"
  })
}

# 9. Demo App Cloud Dataset Hosting (Uploads S3 batch & hosts 6,362,620 PaySim rows on apply)
resource "terraform_data" "demo_app_cloud_dataset" {
  triggers_replace = [
    aws_instance.sample_app_instance.id,
    aws_s3_object.paysim_dataset_manifest.etag,
  ]

  provisioner "local-exec" {
    interpreter = ["PowerShell", "-ExecutionPolicy", "Bypass", "-Command"]
    command     = "& '${replace(abspath("${path.module}/../.venv/Scripts/python.exe"), "/", "\\")}' '${replace(abspath("${path.module}/../scripts/demo_app_cloud_loader.py"), "/", "\\")}' --action apply"
  }

  provisioner "local-exec" {
    when        = destroy
    interpreter = ["PowerShell", "-ExecutionPolicy", "Bypass", "-Command"]
    command     = "& '${replace(abspath("${path.module}/../.venv/Scripts/python.exe"), "/", "\\")}' '${replace(abspath("${path.module}/../scripts/demo_app_cloud_loader.py"), "/", "\\")}' --action destroy"
  }
}

