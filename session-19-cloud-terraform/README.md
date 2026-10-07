# Session 19 – Cloud Computing with Terraform Homework

**Name:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

> **Note – LocalStack instead of a real AWS account:** I did not have an AWS account available, so this project was
> applied against **LocalStack 3.8**, a local AWS emulator running in Docker (`localstack/localstack:3.8`, exposed on
> `http://localhost:31866`). Terraform uses the real `hashicorp/aws` provider and verification uses the real AWS CLI –
> only the endpoint URL is different. In LocalStack community edition **EC2 is mocked**: the API returns real-looking
> instance IDs/IPs and tracks state, but no virtual machine actually boots (so the nginx `user_data` does not run).
> The LocalStack-only settings are isolated in [`provider.tf`](./terraform-vpc-ec2-s3/provider.tf) with a comment on how
> to switch to real AWS. **All command output below is real.**

## Goal

Build an end-to-end Terraform project that demonstrates **providers, variables, resources, outputs, dependencies
(implicit + explicit), AWS infrastructure, state, plan, apply and destroy**. Based on the instructor's
`session19-cloud-terraform/08-mini-project` (VPC + subnet + IGW + route table + SG), extended with an **EC2 instance**
and an **S3 bucket**.

## Architecture

```mermaid
flowchart TB
    user(["Internet / User"])
    subgraph region["AWS Region ap-south-1 (LocalStack)"]
        igw["Internet Gateway<br/>s19-mini-igw"]
        subgraph vpc["VPC s19-mini-vpc · 10.20.0.0/16"]
            rt["Route Table s19-mini-public-rt<br/>10.20.0.0/16 → local<br/>0.0.0.0/0 → IGW"]
            subgraph az["AZ ap-south-1a"]
                subgraph subnet["Public Subnet 10.20.1.0/24<br/>(map_public_ip_on_launch)"]
                    subgraph sg["Security Group s19-mini-web-sg<br/>in: 80, 22 · out: all"]
                        ec2["EC2 s19-mini-web<br/>t2.micro · ami-df5de72bdb3b<br/>nginx user_data"]
                    end
                end
            end
        end
        s3[("S3 bucket<br/>saniya-24bcs10246-s19-assets<br/>versioning on · info.txt")]
    end
    user -- "HTTP :80 / SSH :22" --> igw
    igw --> rt
    rt -. "route table association" .-> subnet
    ec2 -. "instance id written into info.txt" .-> s3
```

Text version:

```text
Internet ──► Internet Gateway ──► Route table (0.0.0.0/0 → IGW) ──assoc──► Public subnet 10.20.1.0/24
                                                                               │
VPC 10.20.0.0/16 ─────────────────────────────────────────────────────────────┘
                                                                     Security group (80, 22 in)
                                                                               │
                                                                      EC2 t2.micro (public IP)
S3 bucket saniya-24bcs10246-s19-assets  ◄── info.txt object (contains the EC2 instance id)
```

## Project structure

```text
terraform-vpc-ec2-s3/
├── provider.tf          # terraform{} + required_providers, provider "aws" (LocalStack endpoints), default_tags
├── variables.tf         # 9 typed input variables
├── terraform.tfvars     # values for this deployment
├── vpc.tf               # VPC, public subnet, IGW, route table + association, security group
├── ec2.tf               # EC2 instance (explicit depends_on)
├── s3.tf                # S3 bucket, versioning, object
├── outputs.tf           # 9 outputs
└── .terraform.lock.hcl  # provider version lock (committed)
```
`.terraform/` and `terraform.tfstate*` are excluded by [`.gitignore`](./.gitignore) and are not in the repo.

## Concepts demonstrated

| Concept | Where | Details |
|---|---|---|
| **Provider** | [`provider.tf`](./terraform-vpc-ec2-s3/provider.tf) | `hashicorp/aws ~> 5.0` pinned in `required_providers`; region from a variable; `default_tags` adds `Project/ManagedBy/Owner` to every resource |
| **Variables** | [`variables.tf`](./terraform-vpc-ec2-s3/variables.tf), [`terraform.tfvars`](./terraform-vpc-ec2-s3/terraform.tfvars) | typed variables with descriptions/defaults; `ami_id` and `bucket_name` have no default so they must come from tfvars |
| **Resources** | `vpc.tf`, `ec2.tf`, `s3.tf` | 10 resources: `aws_vpc`, `aws_subnet`, `aws_internet_gateway`, `aws_route_table`, `aws_route_table_association`, `aws_security_group`, `aws_instance`, `aws_s3_bucket`, `aws_s3_bucket_versioning`, `aws_s3_object` |
| **Outputs** | [`outputs.tf`](./terraform-vpc-ec2-s3/outputs.tf) | VPC id/CIDR, subnet id, IGW id, SG id, instance id + public/private IP, bucket name |
| **Implicit dependency** | e.g. `vpc_id = aws_vpc.main.id` | referencing another resource's attribute makes Terraform create it first |
| **Explicit dependency** | `depends_on = [aws_route_table_association.public]` in `ec2.tf` | the instance doesn't reference the association, but must wait until the subnet has an internet route |
| **State** | `terraform state list / show` | `terraform.tfstate` maps every resource address to its real ID |
| **Plan / Apply / Destroy** | workflow below | full lifecycle captured |

## Code

**provider.tf**
```hcl
# -----------------------------------------------------------------------------
# Provider configuration
#
# NOTE: No AWS account was available, so this project is applied against
# LocalStack (local AWS emulator) on http://localhost:31866. EC2 in LocalStack
# community edition is *mocked*: the API calls succeed and return real-looking
# IDs, but no actual virtual machine is booted.
#
# To run against REAL AWS instead:
#   1. Remove access_key / secret_key, the three skip_* flags,
#      s3_use_path_style and the whole `endpoints { ... }` block.
#   2. Run `aws configure` (or export AWS_PROFILE) with real credentials.
#   3. Set `ami_id` in terraform.tfvars to a real AMI for your region
#      (e.g. the latest Amazon Linux 2023 AMI) and use a unique bucket name.
# -----------------------------------------------------------------------------
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  # ---- LocalStack only (remove for real AWS) ----
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  s3_use_path_style           = true

  endpoints {
    ec2 = "http://localhost:31866"
    s3  = "http://localhost:31866"
    sts = "http://localhost:31866"
    iam = "http://localhost:31866"
  }
  # ---- end LocalStack only ----

  # Tags added automatically to every resource this provider creates
  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "Terraform"
      Owner     = "saniya-24bcs10246"
    }
  }
}
```

**variables.tf**
```hcl
variable "aws_region" {
  type        = string
  description = "AWS region to deploy into."
  default     = "ap-south-1"
}

variable "project_name" {
  type        = string
  description = "Prefix used in Name tags."
  default     = "s19-mini"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block of the VPC."
  default     = "10.20.0.0/16"
}

variable "public_subnet_cidr" {
  type        = string
  description = "CIDR block of the public subnet."
  default     = "10.20.1.0/24"
}

variable "availability_zone" {
  type        = string
  description = "AZ for the public subnet."
  default     = "ap-south-1a"
}

variable "allowed_ssh_cidr" {
  type        = string
  description = "CIDR allowed to SSH into the instance (use your own IP/32 in real AWS)."
  default     = "0.0.0.0/0"
}

variable "ami_id" {
  type        = string
  description = "AMI ID for the EC2 instance."
}

variable "instance_type" {
  type        = string
  description = "EC2 instance type."
  default     = "t2.micro"
}

variable "bucket_name" {
  type        = string
  description = "Name of the S3 bucket for app assets."
}
```

**terraform.tfvars**
```hcl
aws_region         = "ap-south-1"
project_name       = "s19-mini"
vpc_cidr           = "10.20.0.0/16"
public_subnet_cidr = "10.20.1.0/24"
availability_zone  = "ap-south-1a"
allowed_ssh_cidr   = "0.0.0.0/0"
ami_id             = "ami-df5de72bdb3b" # an AMI id LocalStack accepts; replace for real AWS
instance_type      = "t2.micro"
bucket_name        = "saniya-24bcs10246-s19-assets"
```

**vpc.tf**
```hcl
# Networking layer – adapted from devops-heros/session19-cloud-terraform/08-mini-project

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${var.project_name}-vpc" }
}

# IMPLICIT dependency: references aws_vpc.main.id, so Terraform creates the VPC first
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidr
  availability_zone       = var.availability_zone
  map_public_ip_on_launch = true

  tags = { Name = "${var.project_name}-public-subnet" }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "${var.project_name}-igw" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = { Name = "${var.project_name}-public-rt" }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "web" {
  name        = "${var.project_name}-web-sg"
  description = "Allow HTTP and SSH in, all traffic out"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-web-sg" }
}
```

**ec2.tf**
```hcl
resource "aws_instance" "web" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id        # implicit dependency
  vpc_security_group_ids = [aws_security_group.web.id] # implicit dependency

  user_data = <<-EOT
    #!/bin/bash
    yum install -y nginx
    echo "Hello from Saniya (24bcs10246) - Session 19" > /usr/share/nginx/html/index.html
    systemctl enable --now nginx
  EOT

  # EXPLICIT dependency: nothing in this block references the route table
  # association, but the instance should only launch once the subnet actually
  # has a route to the Internet Gateway (so user_data can reach package repos).
  depends_on = [aws_route_table_association.public]

  tags = { Name = "${var.project_name}-web" }
}
```

**s3.tf**
```hcl
resource "aws_s3_bucket" "assets" {
  bucket        = var.bucket_name
  force_destroy = true

  tags = { Name = var.bucket_name }
}

resource "aws_s3_bucket_versioning" "assets" {
  bucket = aws_s3_bucket.assets.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Upload a small object so the bucket isn't empty
resource "aws_s3_object" "readme" {
  bucket       = aws_s3_bucket.assets.id
  key          = "info.txt"
  content      = "Provisioned by Terraform for ${var.project_name}. EC2 instance: ${aws_instance.web.id}\n"
  content_type = "text/plain"
}
```

**outputs.tf**
```hcl
output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.main.id
}

output "vpc_cidr" {
  description = "CIDR block of the VPC."
  value       = aws_vpc.main.cidr_block
}

output "public_subnet_id" {
  description = "ID of the public subnet."
  value       = aws_subnet.public.id
}

output "internet_gateway_id" {
  description = "ID of the Internet Gateway."
  value       = aws_internet_gateway.igw.id
}

output "security_group_id" {
  description = "ID of the web security group."
  value       = aws_security_group.web.id
}

output "instance_id" {
  description = "ID of the EC2 instance."
  value       = aws_instance.web.id
}

output "instance_public_ip" {
  description = "Public IP of the EC2 instance."
  value       = aws_instance.web.public_ip
}

output "instance_private_ip" {
  description = "Private IP of the EC2 instance."
  value       = aws_instance.web.private_ip
}

output "bucket_name" {
  description = "Name of the S3 bucket."
  value       = aws_s3_bucket.assets.bucket
}
```

---

## Terraform workflow (real output)

### 0. LocalStack running

```bash
docker run -d --name s18-localstack -p 31866:4566 localstack/localstack:3.8
```
```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ docker ps --filter name=s18-localstack --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
NAMES            IMAGE                       STATUS                    PORTS
s18-localstack   localstack/localstack:3.8   Up 10 seconds (healthy)   4510-4559/tcp, 5678/tcp, 0.0.0.0:31866->4566/tcp
```

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ aws --endpoint-url http://localhost:31866 sts get-caller-identity
{
    "UserId": "AKIAIOSFODNN7EXAMPLE",
    "Account": "000000000000",
    "Arn": "arn:aws:iam::000000000000:root"
}
```

### 1. Init

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ terraform init
Initializing the backend...
Initializing provider plugins...
- Reusing previous version of hashicorp/aws from the dependency lock file
- Installing hashicorp/aws v5.100.0...
- Installed hashicorp/aws v5.100.0 (signed by HashiCorp)

Terraform has been successfully initialized!
```

### 2. Format & validate

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ terraform fmt -check; echo "fmt exit code: $?"
fmt exit code: 0
```

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ terraform validate
Success! The configuration is valid.

```

### 3. Dependency graph

`terraform graph` prints the dependency graph Terraform built from the references (edges `A -> B` mean *A depends on B*;
redundant transitive edges are removed). Note `aws_instance.web -> aws_route_table_association.public` – that one
comes from the explicit `depends_on`; all others are implicit from attribute references.

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ terraform graph | grep -- '->'
  "aws_instance.web" -> "aws_route_table_association.public";
  "aws_instance.web" -> "aws_security_group.web";
  "aws_internet_gateway.igw" -> "aws_vpc.main";
  "aws_route_table.public" -> "aws_internet_gateway.igw";
  "aws_route_table_association.public" -> "aws_route_table.public";
  "aws_route_table_association.public" -> "aws_subnet.public";
  "aws_s3_bucket_versioning.assets" -> "aws_s3_bucket.assets";
  "aws_s3_object.readme" -> "aws_instance.web";
  "aws_s3_object.readme" -> "aws_s3_bucket.assets";
  "aws_security_group.web" -> "aws_vpc.main";
  "aws_subnet.public" -> "aws_vpc.main";
```

### 4. Plan

Save the plan to a file so that `apply` executes exactly what was reviewed:

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ terraform plan -out=tfplan

Terraform used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  + create

Terraform will perform the following actions:

  # aws_instance.web will be created
  + resource "aws_instance" "web" {
      + ami                                  = "ami-df5de72bdb3b"
      + arn                                  = (known after apply)
      + associate_public_ip_address          = (known after apply)
      + availability_zone                    = (known after apply)
      + cpu_core_count                       = (known after apply)
      + cpu_threads_per_core                 = (known after apply)
      + disable_api_stop                     = (known after apply)
      + disable_api_termination              = (known after apply)
      + ebs_optimized                        = (known after apply)
      + enable_primary_ipv6                  = (known after apply)
      + get_password_data                    = false
      + host_id                              = (known after apply)
      + host_resource_group_arn              = (known after apply)
      + iam_instance_profile                 = (known after apply)
      + id                                   = (known after apply)
      + instance_initiated_shutdown_behavior = (known after apply)
      + instance_lifecycle                   = (known after apply)
      + instance_state                       = (known after apply)
      + instance_type                        = "t2.micro"
      + ipv6_address_count                   = (known after apply)
      + ipv6_addresses                       = (known after apply)
      + key_name                             = (known after apply)
      + monitoring                           = (known after apply)
      + outpost_arn                          = (known after apply)
      + password_data                        = (known after apply)
      + placement_group                      = (known after apply)
      + placement_partition_number           = (known after apply)
      + primary_network_interface_id         = (known after apply)
      + private_dns                          = (known after apply)
      + private_ip                           = (known after apply)
      + public_dns                           = (known after apply)
      + public_ip                            = (known after apply)
      + secondary_private_ips                = (known after apply)
      + security_groups                      = (known after apply)
      + source_dest_check                    = true
      + spot_instance_request_id             = (known after apply)
      + subnet_id                            = (known after apply)
      + tags                                 = {
          + "Name" = "s19-mini-web"
        }
      + tags_all                             = {
          + "ManagedBy" = "Terraform"
          + "Name"      = "s19-mini-web"
          + "Owner"     = "saniya-24bcs10246"
          + "Project"   = "s19-mini"
        }
      + tenancy                              = (known after apply)
      + user_data                            = "c0db8f6f37938866acddfa4c61aa4138562443ec"
      + user_data_base64                     = (known after apply)
      + user_data_replace_on_change          = false
      + vpc_security_group_ids               = (known after apply)

      + capacity_reservation_specification (known after apply)

      + cpu_options (known after apply)

      + ebs_block_device (known after apply)

      + enclave_options (known after apply)

      + ephemeral_block_device (known after apply)

      + instance_market_options (known after apply)

      + maintenance_options (known after apply)

      + metadata_options (known after apply)

      + network_interface (known after apply)

      + private_dns_name_options (known after apply)

      + root_block_device (known after apply)
    }

  # aws_internet_gateway.igw will be created
  + resource "aws_internet_gateway" "igw" {
      + arn      = (known after apply)
      + id       = (known after apply)
      + owner_id = (known after apply)
      + tags     = {
          + "Name" = "s19-mini-igw"
        }
      + tags_all = {
          + "ManagedBy" = "Terraform"
          + "Name"      = "s19-mini-igw"
          + "Owner"     = "saniya-24bcs10246"
          + "Project"   = "s19-mini"
        }
      + vpc_id   = (known after apply)
    }

  # aws_route_table.public will be created
  + resource "aws_route_table" "public" {
      + arn              = (known after apply)
      + id               = (known after apply)
      + owner_id         = (known after apply)
      + propagating_vgws = (known after apply)
      + route            = [
          + {
              + cidr_block                 = "0.0.0.0/0"
              + gateway_id                 = (known after apply)
                # (11 unchanged attributes hidden)
            },
        ]
      + tags             = {
          + "Name" = "s19-mini-public-rt"
        }
      + tags_all         = {
          + "ManagedBy" = "Terraform"
          + "Name"      = "s19-mini-public-rt"
          + "Owner"     = "saniya-24bcs10246"
          + "Project"   = "s19-mini"
        }
      + vpc_id           = (known after apply)
    }

  # aws_route_table_association.public will be created
  + resource "aws_route_table_association" "public" {
      + id             = (known after apply)
      + route_table_id = (known after apply)
      + subnet_id      = (known after apply)
    }

  # aws_s3_bucket.assets will be created
  + resource "aws_s3_bucket" "assets" {
      + acceleration_status         = (known after apply)
      + acl                         = (known after apply)
      + arn                         = (known after apply)
      + bucket                      = "saniya-24bcs10246-s19-assets"
      + bucket_domain_name          = (known after apply)
      + bucket_prefix               = (known after apply)
      + bucket_regional_domain_name = (known after apply)
      + force_destroy               = true
      + hosted_zone_id              = (known after apply)
      + id                          = (known after apply)
      + object_lock_enabled         = (known after apply)
      + policy                      = (known after apply)
      + region                      = (known after apply)
      + request_payer               = (known after apply)
      + tags                        = {
          + "Name" = "saniya-24bcs10246-s19-assets"
        }
      + tags_all                    = {
          + "ManagedBy" = "Terraform"
          + "Name"      = "saniya-24bcs10246-s19-assets"
          + "Owner"     = "saniya-24bcs10246"
          + "Project"   = "s19-mini"
        }
      + website_domain              = (known after apply)
      + website_endpoint            = (known after apply)

      + cors_rule (known after apply)

      + grant (known after apply)

      + lifecycle_rule (known after apply)

      + logging (known after apply)

      + object_lock_configuration (known after apply)

      + replication_configuration (known after apply)

      + server_side_encryption_configuration (known after apply)

      + versioning (known after apply)

      + website (known after apply)
    }

  # aws_s3_bucket_versioning.assets will be created
  + resource "aws_s3_bucket_versioning" "assets" {
      + bucket = (known after apply)
      + id     = (known after apply)

      + versioning_configuration {
          + mfa_delete = (known after apply)
          + status     = "Enabled"
        }
    }

  # aws_s3_object.readme will be created
  + resource "aws_s3_object" "readme" {
      + acl                    = (known after apply)
      + arn                    = (known after apply)
      + bucket                 = (known after apply)
      + bucket_key_enabled     = (known after apply)
      + checksum_crc32         = (known after apply)
      + checksum_crc32c        = (known after apply)
      + checksum_crc64nvme     = (known after apply)
      + checksum_sha1          = (known after apply)
      + checksum_sha256        = (known after apply)
      + content                = (known after apply)
      + content_type           = "text/plain"
      + etag                   = (known after apply)
      + force_destroy          = false
      + id                     = (known after apply)
      + key                    = "info.txt"
      + kms_key_id             = (known after apply)
      + server_side_encryption = (known after apply)
      + storage_class          = (known after apply)
      + tags_all               = {
          + "ManagedBy" = "Terraform"
          + "Owner"     = "saniya-24bcs10246"
          + "Project"   = "s19-mini"
        }
      + version_id             = (known after apply)
    }

  # aws_security_group.web will be created
  + resource "aws_security_group" "web" {
      + arn                    = (known after apply)
      + description            = "Allow HTTP and SSH in, all traffic out"
      + egress                 = [
          + {
              + cidr_blocks      = [
                  + "0.0.0.0/0",
                ]
              + description      = "All outbound"
              + from_port        = 0
              + ipv6_cidr_blocks = []
              + prefix_list_ids  = []
              + protocol         = "-1"
              + security_groups  = []
              + self             = false
              + to_port          = 0
            },
        ]
      + id                     = (known after apply)
      + ingress                = [
          + {
              + cidr_blocks      = [
                  + "0.0.0.0/0",
                ]
              + description      = "HTTP"
              + from_port        = 80
              + ipv6_cidr_blocks = []
              + prefix_list_ids  = []
              + protocol         = "tcp"
              + security_groups  = []
              + self             = false
              + to_port          = 80
            },
          + {
              + cidr_blocks      = [
                  + "0.0.0.0/0",
                ]
              + description      = "SSH"
              + from_port        = 22
              + ipv6_cidr_blocks = []
              + prefix_list_ids  = []
              + protocol         = "tcp"
              + security_groups  = []
              + self             = false
              + to_port          = 22
            },
        ]
      + name                   = "s19-mini-web-sg"
      + name_prefix            = (known after apply)
      + owner_id               = (known after apply)
      + revoke_rules_on_delete = false
      + tags                   = {
          + "Name" = "s19-mini-web-sg"
        }
      + tags_all               = {
          + "ManagedBy" = "Terraform"
          + "Name"      = "s19-mini-web-sg"
          + "Owner"     = "saniya-24bcs10246"
          + "Project"   = "s19-mini"
        }
      + vpc_id                 = (known after apply)
    }

  # aws_subnet.public will be created
  + resource "aws_subnet" "public" {
      + arn                                            = (known after apply)
      + assign_ipv6_address_on_creation                = false
      + availability_zone                              = "ap-south-1a"
      + availability_zone_id                           = (known after apply)
      + cidr_block                                     = "10.20.1.0/24"
      + enable_dns64                                   = false
      + enable_resource_name_dns_a_record_on_launch    = false
      + enable_resource_name_dns_aaaa_record_on_launch = false
      + id                                             = (known after apply)
      + ipv6_cidr_block_association_id                 = (known after apply)
      + ipv6_native                                    = false
      + map_public_ip_on_launch                        = true
      + owner_id                                       = (known after apply)
      + private_dns_hostname_type_on_launch            = (known after apply)
      + tags                                           = {
          + "Name" = "s19-mini-public-subnet"
        }
      + tags_all                                       = {
          + "ManagedBy" = "Terraform"
          + "Name"      = "s19-mini-public-subnet"
          + "Owner"     = "saniya-24bcs10246"
          + "Project"   = "s19-mini"
        }
      + vpc_id                                         = (known after apply)
    }

  # aws_vpc.main will be created
  + resource "aws_vpc" "main" {
      + arn                                  = (known after apply)
      + cidr_block                           = "10.20.0.0/16"
      + default_network_acl_id               = (known after apply)
      + default_route_table_id               = (known after apply)
      + default_security_group_id            = (known after apply)
      + dhcp_options_id                      = (known after apply)
      + enable_dns_hostnames                 = true
      + enable_dns_support                   = true
      + enable_network_address_usage_metrics = (known after apply)
      + id                                   = (known after apply)
      + instance_tenancy                     = "default"
      + ipv6_association_id                  = (known after apply)
      + ipv6_cidr_block                      = (known after apply)
      + ipv6_cidr_block_network_border_group = (known after apply)
      + main_route_table_id                  = (known after apply)
      + owner_id                             = (known after apply)
      + tags                                 = {
          + "Name" = "s19-mini-vpc"
        }
      + tags_all                             = {
          + "ManagedBy" = "Terraform"
          + "Name"      = "s19-mini-vpc"
          + "Owner"     = "saniya-24bcs10246"
          + "Project"   = "s19-mini"
        }
    }

Plan: 10 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + bucket_name         = "saniya-24bcs10246-s19-assets"
  + instance_id         = (known after apply)
  + instance_private_ip = (known after apply)
  + instance_public_ip  = (known after apply)
  + internet_gateway_id = (known after apply)
  + public_subnet_id    = (known after apply)
  + security_group_id   = (known after apply)
  + vpc_cidr            = "10.20.0.0/16"
  + vpc_id              = (known after apply)
```

### 5. Apply

The creation order follows the graph: VPC first, then IGW/subnet/SG in parallel, then route table → association →
**EC2 (waits for the association because of `depends_on`)** → S3 object (needs the instance id). The bucket has no
dependencies so it is created right at the start in parallel with the VPC.

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ terraform apply tfplan
aws_vpc.main: Creating...
aws_s3_bucket.assets: Creating...
aws_s3_bucket.assets: Creation complete after 1s [id=saniya-24bcs10246-s19-assets]
aws_s3_bucket_versioning.assets: Creating...
aws_s3_bucket_versioning.assets: Creation complete after 2s [id=saniya-24bcs10246-s19-assets]
aws_vpc.main: Still creating... [10s elapsed]
aws_vpc.main: Creation complete after 12s [id=vpc-43fa8e0c]
aws_subnet.public: Creating...
aws_internet_gateway.igw: Creating...
aws_security_group.web: Creating...
aws_internet_gateway.igw: Creation complete after 0s [id=igw-dc9fabe0]
aws_route_table.public: Creating...
aws_route_table.public: Creation complete after 0s [id=rtb-d0aba84c]
aws_security_group.web: Creation complete after 0s [id=sg-4b892242970bb33c1]
aws_subnet.public: Still creating... [10s elapsed]
aws_subnet.public: Creation complete after 10s [id=subnet-a230c1af]
aws_route_table_association.public: Creating...
aws_route_table_association.public: Creation complete after 0s [id=rtbassoc-36af8b95]
aws_instance.web: Creating...
aws_instance.web: Still creating... [10s elapsed]
aws_instance.web: Creation complete after 10s [id=i-5f6c4952c61f1f706]
aws_s3_object.readme: Creating...
aws_s3_object.readme: Creation complete after 0s [id=info.txt]

Apply complete! Resources: 10 added, 0 changed, 0 destroyed.

Outputs:

bucket_name = "saniya-24bcs10246-s19-assets"
instance_id = "i-5f6c4952c61f1f706"
instance_private_ip = "10.20.1.4"
instance_public_ip = "54.214.127.186"
internet_gateway_id = "igw-dc9fabe0"
public_subnet_id = "subnet-a230c1af"
security_group_id = "sg-4b892242970bb33c1"
vpc_cidr = "10.20.0.0/16"
vpc_id = "vpc-43fa8e0c"
```

### 6. State

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ terraform state list
aws_instance.web
aws_internet_gateway.igw
aws_route_table.public
aws_route_table_association.public
aws_s3_bucket.assets
aws_s3_bucket_versioning.assets
aws_s3_object.readme
aws_security_group.web
aws_subnet.public
aws_vpc.main
```

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ terraform state show aws_vpc.main
# aws_vpc.main:
resource "aws_vpc" "main" {
    arn                                  = "arn:aws:ec2:ap-south-1:000000000000:vpc/vpc-43fa8e0c"
    assign_generated_ipv6_cidr_block     = false
    cidr_block                           = "10.20.0.0/16"
    default_network_acl_id               = "acl-0095c86e"
    default_route_table_id               = "rtb-600a5a7f"
    default_security_group_id            = "sg-907c519f6c702db65"
    dhcp_options_id                      = "default"
    enable_dns_hostnames                 = true
    enable_dns_support                   = true
    enable_network_address_usage_metrics = false
    id                                   = "vpc-43fa8e0c"
    instance_tenancy                     = "default"
    ipv6_association_id                  = null
    ipv6_cidr_block                      = null
    ipv6_cidr_block_network_border_group = null
    ipv6_ipam_pool_id                    = null
    ipv6_netmask_length                  = 0
    main_route_table_id                  = "rtb-600a5a7f"
    owner_id                             = "000000000000"
    tags                                 = {
        "Name" = "s19-mini-vpc"
    }
    tags_all                             = {
        "ManagedBy" = "Terraform"
        "Name"      = "s19-mini-vpc"
        "Owner"     = "saniya-24bcs10246"
        "Project"   = "s19-mini"
    }
}
```

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ terraform state show aws_instance.web
# aws_instance.web:
resource "aws_instance" "web" {
    ami                                  = "ami-df5de72bdb3b"
    arn                                  = "arn:aws:ec2:ap-south-1::instance/i-5f6c4952c61f1f706"
    associate_public_ip_address          = true
    availability_zone                    = "ap-south-1a"
    disable_api_stop                     = false
    disable_api_termination              = false
    ebs_optimized                        = false
    get_password_data                    = false
    hibernation                          = false
    host_id                              = null
    iam_instance_profile                 = null
    id                                   = "i-5f6c4952c61f1f706"
    instance_initiated_shutdown_behavior = "stop"
    instance_lifecycle                   = null
    instance_state                       = "running"
    instance_type                        = "t2.micro"
    ipv6_address_count                   = 0
    ipv6_addresses                       = []
    key_name                             = null
    monitoring                           = false
    outpost_arn                          = null
    password_data                        = null
    placement_group                      = null
    placement_partition_number           = 0
    primary_network_interface_id         = "eni-4cda399d"
    private_dns                          = "ip-10-20-1-4.ap-south-1.compute.internal"
    private_ip                           = "10.20.1.4"
    public_dns                           = "ec2-54-214-127-186.ap-south-1.compute.amazonaws.com"
    public_ip                            = "54.214.127.186"
    secondary_private_ips                = []
    security_groups                      = []
    source_dest_check                    = true
    spot_instance_request_id             = null
    subnet_id                            = "subnet-a230c1af"
    tags                                 = {
        "Name" = "s19-mini-web"
    }
    tags_all                             = {
        "ManagedBy" = "Terraform"
        "Name"      = "s19-mini-web"
        "Owner"     = "saniya-24bcs10246"
        "Project"   = "s19-mini"
    }
    tenancy                              = "default"
    user_data                            = "c0db8f6f37938866acddfa4c61aa4138562443ec"
    user_data_replace_on_change          = false
    vpc_security_group_ids               = [
        "sg-4b892242970bb33c1",
    ]

    root_block_device {
        delete_on_termination = true
        device_name           = "/dev/sda1"
        encrypted             = false
        iops                  = 0
        kms_key_id            = null
        tags                  = {
            "ManagedBy" = "Terraform"
            "Owner"     = "saniya-24bcs10246"
            "Project"   = "s19-mini"
        }
        tags_all              = {
            "ManagedBy" = "Terraform"
            "Owner"     = "saniya-24bcs10246"
            "Project"   = "s19-mini"
        }
        throughput            = 0
        volume_id             = "vol-340cd637"
        volume_size           = 8
        volume_type           = "gp2"
    }
}
```

### 7. Outputs

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ terraform output
bucket_name = "saniya-24bcs10246-s19-assets"
instance_id = "i-5f6c4952c61f1f706"
instance_private_ip = "10.20.1.4"
instance_public_ip = "54.214.127.186"
internet_gateway_id = "igw-dc9fabe0"
public_subnet_id = "subnet-a230c1af"
security_group_id = "sg-4b892242970bb33c1"
vpc_cidr = "10.20.0.0/16"
vpc_id = "vpc-43fa8e0c"
```

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ terraform output -raw instance_public_ip; echo
54.214.127.186
```

### 8. Verify with the AWS CLI

**VPC**

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ aws --endpoint-url http://localhost:31866 ec2 describe-vpcs --filters Name=tag:Project,Values=s19-mini --query 'Vpcs[].{VpcId:VpcId,Cidr:CidrBlock,State:State,Name:Tags[?Key==`Name`]|[0].Value}' --output table
---------------------------------------------------------------
|                        DescribeVpcs                         |
+--------------+----------------+------------+----------------+
|     Cidr     |     Name       |   State    |     VpcId      |
+--------------+----------------+------------+----------------+
|  10.20.0.0/16|  s19-mini-vpc  |  available |  vpc-43fa8e0c  |
+--------------+----------------+------------+----------------+
```

**Subnet, Internet Gateway, route table**

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ aws --endpoint-url http://localhost:31866 ec2 describe-subnets --filters Name=tag:Project,Values=s19-mini --query 'Subnets[].{SubnetId:SubnetId,Cidr:CidrBlock,AZ:AvailabilityZone,PublicIpOnLaunch:MapPublicIpOnLaunch}' --output table
------------------------------------------------------------------------
|                            DescribeSubnets                           |
+-------------+---------------+--------------------+-------------------+
|     AZ      |     Cidr      | PublicIpOnLaunch   |     SubnetId      |
+-------------+---------------+--------------------+-------------------+
|  ap-south-1a|  10.20.1.0/24 |  True              |  subnet-a230c1af  |
+-------------+---------------+--------------------+-------------------+
```

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ aws --endpoint-url http://localhost:31866 ec2 describe-internet-gateways --filters Name=tag:Project,Values=s19-mini --query 'InternetGateways[].{IGW:InternetGatewayId,AttachedTo:Attachments[0].VpcId,State:Attachments[0].State}' --output table
-----------------------------------------------
|          DescribeInternetGateways           |
+--------------+----------------+-------------+
|  AttachedTo  |      IGW       |    State    |
+--------------+----------------+-------------+
|  vpc-43fa8e0c|  igw-dc9fabe0  |  available  |
+--------------+----------------+-------------+
```

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ aws --endpoint-url http://localhost:31866 ec2 describe-route-tables --filters Name=tag:Project,Values=s19-mini --query 'RouteTables[].Routes[].{Destination:DestinationCidrBlock,Target:GatewayId,State:State}' --output table
--------------------------------------------
|            DescribeRouteTables           |
+---------------+---------+----------------+
|  Destination  |  State  |    Target      |
+---------------+---------+----------------+
|  10.20.0.0/16 |  active |  local         |
|  0.0.0.0/0    |  active |  igw-dc9fabe0  |
+---------------+---------+----------------+
```

**Security group**

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ aws --endpoint-url http://localhost:31866 ec2 describe-security-groups --filters Name=tag:Project,Values=s19-mini --query 'SecurityGroups[].IpPermissions[].{Proto:IpProtocol,From:FromPort,To:ToPort,Cidr:IpRanges[0].CidrIp}' --output table
--------------------------------------
|       DescribeSecurityGroups       |
+------------+-------+---------+-----+
|    Cidr    | From  |  Proto  | To  |
+------------+-------+---------+-----+
|  0.0.0.0/0 |  80   |  tcp    |  80 |
|  0.0.0.0/0 |  22   |  tcp    |  22 |
+------------+-------+---------+-----+
```

**EC2 instance**

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ aws --endpoint-url http://localhost:31866 ec2 describe-instances --filters Name=tag:Project,Values=s19-mini Name=instance-state-name,Values=running --query 'Reservations[].Instances[].{Id:InstanceId,Type:InstanceType,AMI:ImageId,State:State.Name,Subnet:SubnetId,PrivateIP:PrivateIpAddress,PublicIP:PublicIpAddress,SG:SecurityGroups[0].GroupName}' --output table
--------------------------------------
|          DescribeInstances         |
+------------+-----------------------+
|  AMI       |  ami-df5de72bdb3b     |
|  Id        |  i-5f6c4952c61f1f706  |
|  PrivateIP |  10.20.1.4            |
|  PublicIP  |  54.214.127.186       |
|  SG        |  s19-mini-web-sg      |
|  State     |  running              |
|  Subnet    |  subnet-a230c1af      |
|  Type      |  t2.micro             |
+------------+-----------------------+
```

**S3**

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ aws --endpoint-url http://localhost:31866 s3 ls
2026-10-07 13:37:12 saniya-24bcs10246-s19-assets
```

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ aws --endpoint-url http://localhost:31866 s3 ls s3://saniya-24bcs10246-s19-assets/
2026-10-07 13:37:44         73 info.txt
```

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ aws --endpoint-url http://localhost:31866 s3 cp s3://saniya-24bcs10246-s19-assets/info.txt -
Provisioned by Terraform for s19-mini. EC2 instance: i-5f6c4952c61f1f706
```

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ aws --endpoint-url http://localhost:31866 s3api get-bucket-versioning --bucket saniya-24bcs10246-s19-assets
{
    "Status": "Enabled"
}
```

### 9. Idempotency – plan again

Running `plan` again right after apply shows the real infrastructure matches the code and state:

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ terraform plan
aws_vpc.main: Refreshing state... [id=vpc-43fa8e0c]
aws_s3_bucket.assets: Refreshing state... [id=saniya-24bcs10246-s19-assets]
aws_subnet.public: Refreshing state... [id=subnet-a230c1af]
aws_internet_gateway.igw: Refreshing state... [id=igw-dc9fabe0]
aws_security_group.web: Refreshing state... [id=sg-4b892242970bb33c1]
aws_route_table.public: Refreshing state... [id=rtb-d0aba84c]
aws_route_table_association.public: Refreshing state... [id=rtbassoc-36af8b95]
aws_s3_bucket_versioning.assets: Refreshing state... [id=saniya-24bcs10246-s19-assets]
aws_instance.web: Refreshing state... [id=i-5f6c4952c61f1f706]
aws_s3_object.readme: Refreshing state... [id=info.txt]

No changes. Your infrastructure matches the configuration.

Terraform has compared your real infrastructure against your configuration
and found no differences, so no changes are needed.
```

### 10. Destroy

Destroy runs in **reverse dependency order** (S3 object and EC2 before the network, VPC last). The full plan listing is long, so it is filtered with `grep` to the per-resource lines:

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ terraform destroy -auto-approve | grep -E 'will be destroyed|Plan:|Destroying|Destruction complete|Destroy complete'
Plan: 0 to add, 0 to change, 10 to destroy.
aws_s3_bucket_versioning.assets: Destroying... [id=saniya-24bcs10246-s19-assets]
aws_s3_object.readme: Destroying... [id=info.txt]
aws_s3_bucket_versioning.assets: Destruction complete after 0s
aws_s3_object.readme: Destruction complete after 0s
aws_instance.web: Destroying... [id=i-5f6c4952c61f1f706]
aws_s3_bucket.assets: Destroying... [id=saniya-24bcs10246-s19-assets]
aws_s3_bucket.assets: Destruction complete after 0s
aws_instance.web: Destruction complete after 10s
aws_route_table_association.public: Destroying... [id=rtbassoc-36af8b95]
aws_security_group.web: Destroying... [id=sg-4b892242970bb33c1]
aws_route_table_association.public: Destruction complete after 0s
aws_subnet.public: Destroying... [id=subnet-a230c1af]
aws_route_table.public: Destroying... [id=rtb-d0aba84c]
aws_security_group.web: Destruction complete after 0s
aws_subnet.public: Destruction complete after 0s
aws_route_table.public: Destruction complete after 0s
aws_internet_gateway.igw: Destroying... [id=igw-dc9fabe0]
aws_internet_gateway.igw: Destruction complete after 0s
aws_vpc.main: Destroying... [id=vpc-43fa8e0c]
aws_vpc.main: Destruction complete after 0s
Destroy complete! Resources: 10 destroyed.
```

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ terraform state list | wc -l
0
```

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ aws --endpoint-url http://localhost:31866 ec2 describe-vpcs --filters Name=tag:Project,Values=s19-mini --query 'Vpcs[].VpcId'
[]
```

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ aws --endpoint-url http://localhost:31866 ec2 describe-instances --filters Name=tag:Project,Values=s19-mini --query 'Reservations[].Instances[].[InstanceId,State.Name]' --output text
i-5f6c4952c61f1f706	terminated
```

```console
saniya@saniya-devops:~/devops-homework/session-19-cloud-terraform/terraform-vpc-ec2-s3$ aws --endpoint-url http://localhost:31866 s3 ls; echo "(no buckets)"
(no buckets)
```

## Observations

- **Provider:** `init` downloaded `hashicorp/aws` v5 and recorded it in `.terraform.lock.hcl`, so everyone gets the same provider version.
- **Variables:** changing `terraform.tfvars` (CIDRs, AMI, instance type, bucket name) re-targets the same code to another environment without editing `.tf` files.
- **Implicit dependencies** (attribute references) and the one **explicit** `depends_on` are both visible in `terraform graph` and in the apply log: the instance was created only after `aws_route_table_association.public` finished, and `aws_s3_object.readme` waited for the instance because its content uses `aws_instance.web.id`.
- **State:** `terraform state list` shows the 10 managed addresses; `state show` displays the real IDs and attributes (e.g. the VPC's `vpc-…` id, the instance's private IP from the subnet `10.20.1.0/24`). State is the link between code and real infrastructure – it is git-ignored and in a team would live in a remote backend (S3 + locking).
- **Verification:** the AWS CLI independently confirmed the VPC, subnet, IGW attachment, the `0.0.0.0/0 → igw-…` route, the SG rules, the running instance in the public subnet and the bucket with `info.txt` – everything Terraform reported.
- **Idempotency:** a second `plan` reported *No changes* – Terraform is declarative.
- **Destroy** removed all 10 resources in reverse order; the CLI afterwards finds no VPC or bucket, and the instance is in state `terminated` (AWS keeps terminated instances visible in `describe-instances` for about an hour).
- **LocalStack limitations:** EC2 is mocked (no real VM, so the nginx page can't actually be browsed); everything else (API behaviour, IDs, dependency ordering, state) works the same as on AWS. To run on real AWS: remove the LocalStack block in `provider.tf`, `aws configure`, set a real AMI (e.g. Amazon Linux 2023 for ap-south-1) and a unique bucket name, then `terraform apply` – the nginx page would then be reachable at `http://<instance_public_ip>`.

## Deliverables checklist

| Deliverable | Where |
|---|---|
| Terraform project | [`terraform-vpc-ec2-s3/`](./terraform-vpc-ec2-s3/) |
| AWS resources | created on LocalStack – VPC, subnet, IGW, route table, SG, EC2, S3 (see apply + CLI verification above) |
| Architecture diagram | [Architecture](#architecture) (Mermaid, rendered by GitHub) |
| Terraform commands + outputs | [Terraform workflow](#terraform-workflow-real-output) – init, fmt, validate, graph, plan, apply, state, output, destroy |
| README | this file |
