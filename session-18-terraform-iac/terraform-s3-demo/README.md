# Terraform S3 Demo – Task 1

**Name:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

> **Important – where these resources were created:** I did not have an AWS account available, so every
> command below was run against **[LocalStack](https://github.com/localstack/localstack) 3.8** – a local AWS
> emulator running in Docker (`localstack/localstack:3.8`, container `s18-localstack`, port `31866`).
> Terraform uses the real `hashicorp/aws` provider; only the API endpoint is different. The LocalStack-specific
> settings are isolated in [`provider.tf`](./provider.tf) with a comment explaining how to switch to real AWS
> (remove the endpoints/fake keys and run `aws configure`).

Adapted from the instructor's `devops-heros/session18-terraform-iac/terraform-s3-demo`.

## Project structure

```text
terraform-s3-demo/
├── provider.tf          # terraform{} block (required providers) + aws provider (LocalStack endpoints)
├── variables.tf         # input variables (region, bucket name, environment, versioning flag)
├── terraform.tfvars     # values for the variables
├── main.tf              # aws_s3_bucket + aws_s3_bucket_versioning
├── outputs.tf           # bucket name / ARN / region / versioning status
├── .terraform.lock.hcl  # provider version lock (committed on purpose)
└── README.md
```

## How the files fit together

```text
terraform.tfvars ──► variables.tf ──► main.tf ──► aws_s3_bucket.demo ──► aws_s3_bucket_versioning.demo
                                         ▲                 │
                         provider.tf ────┘                 ▼
                     (aws, LocalStack)                outputs.tf
```

## Code

**provider.tf**
```hcl
# -----------------------------------------------------------------------------
# Provider configuration
#
# NOTE: No AWS account was available for this homework, so this project runs
# against LocalStack (a local AWS emulator) listening on http://localhost:31866.
# The settings marked "LocalStack only" below point the AWS provider at it.
#
# To run against REAL AWS instead:
#   1. Delete access_key / secret_key, the three skip_* flags,
#      s3_use_path_style and the whole `endpoints { ... }` block.
#   2. Configure real credentials with `aws configure` (or AWS_PROFILE / SSO).
#   3. Pick a globally-unique bucket name in terraform.tfvars.
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
    s3  = "http://localhost:31866"
    sts = "http://localhost:31866"
    iam = "http://localhost:31866"
  }
  # ---- end LocalStack only ----
}
```

**variables.tf**
```hcl
variable "aws_region" {
  type        = string
  description = "AWS region where the S3 bucket will be created."
  default     = "ap-south-1"
}

variable "bucket_name" {
  type        = string
  description = "Name of the S3 bucket (must be globally unique on real AWS)."
}

variable "environment" {
  type        = string
  description = "Environment tag value."
  default     = "dev"
}

variable "enable_versioning" {
  type        = bool
  description = "Turn on S3 object versioning."
  default     = true
}
```

**terraform.tfvars**
```hcl
aws_region        = "ap-south-1"
bucket_name       = "saniya-24bcs10246-demo-bucket"
environment       = "dev"
enable_versioning = true
```

**main.tf**
```hcl
# Adapted from devops-heros/session18-terraform-iac/terraform-s3-demo

locals {
  common_tags = {
    Name        = var.bucket_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = "Session18"
    Owner       = "saniya-24bcs10246"
  }
}

resource "aws_s3_bucket" "demo" {
  bucket        = var.bucket_name
  force_destroy = true # allow `terraform destroy` even if objects exist (demo only)

  tags = local.common_tags
}

resource "aws_s3_bucket_versioning" "demo" {
  bucket = aws_s3_bucket.demo.id # implicit dependency on the bucket

  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Suspended"
  }
}
```

**outputs.tf**
```hcl
output "bucket_name" {
  description = "Name of the S3 bucket."
  value       = aws_s3_bucket.demo.bucket
}

output "bucket_arn" {
  description = "ARN of the S3 bucket."
  value       = aws_s3_bucket.demo.arn
}

output "bucket_region" {
  description = "AWS region of the S3 bucket."
  value       = aws_s3_bucket.demo.region
}

output "versioning_status" {
  description = "Versioning status of the bucket."
  value       = aws_s3_bucket_versioning.demo.versioning_configuration[0].status
}
```

## Terraform workflow (real output)

### 0. LocalStack is up

```bash
docker run -d --name s18-localstack -p 31866:4566 localstack/localstack:3.8
```
```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ docker ps --filter name=s18-localstack --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
NAMES            IMAGE                       STATUS                   PORTS
s18-localstack   localstack/localstack:3.8   Up 2 minutes (healthy)   4510-4559/tcp, 5678/tcp, 0.0.0.0:31866->4566/tcp
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ curl -s http://localhost:31866/_localstack/health | python3 -m json.tool | grep -E '"(s3|iam|sts|ec2|dynamodb|edition|version)"'
        "dynamodb": "available",
        "ec2": "running",
        "iam": "available",
        "s3": "running",
        "sts": "running",
    "edition": "community",
    "version": "3.8.1"
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ aws --endpoint-url http://localhost:31866 sts get-caller-identity
{
    "UserId": "AKIAIOSFODNN7EXAMPLE",
    "Account": "000000000000",
    "Arn": "arn:aws:iam::000000000000:root"
}
```

### 1. `terraform init` – download the AWS provider

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ terraform init
Initializing the backend...
Initializing provider plugins...
- Reusing previous version of hashicorp/aws from the dependency lock file
- Installing hashicorp/aws v5.100.0...
- Installed hashicorp/aws v5.100.0 (signed by HashiCorp)

Terraform has been successfully initialized!
```

### 2. `terraform fmt` – canonical formatting

No file names printed = every file was already formatted. `-check` returns exit code 0 when nothing needs changing:

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ terraform fmt
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ terraform fmt -check; echo "exit code: $?"
exit code: 0
```

### 3. `terraform validate` – syntax & type check

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ terraform validate
Success! The configuration is valid.

```

### 4. `terraform plan` – preview

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ terraform plan

Terraform used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  + create

Terraform will perform the following actions:

  # aws_s3_bucket.demo will be created
  + resource "aws_s3_bucket" "demo" {
      + acceleration_status         = (known after apply)
      + acl                         = (known after apply)
      + arn                         = (known after apply)
      + bucket                      = "saniya-24bcs10246-demo-bucket"
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
          + "Environment" = "dev"
          + "ManagedBy"   = "Terraform"
          + "Name"        = "saniya-24bcs10246-demo-bucket"
          + "Owner"       = "saniya-24bcs10246"
          + "Project"     = "Session18"
        }
      + tags_all                    = {
          + "Environment" = "dev"
          + "ManagedBy"   = "Terraform"
          + "Name"        = "saniya-24bcs10246-demo-bucket"
          + "Owner"       = "saniya-24bcs10246"
          + "Project"     = "Session18"
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

  # aws_s3_bucket_versioning.demo will be created
  + resource "aws_s3_bucket_versioning" "demo" {
      + bucket = (known after apply)
      + id     = (known after apply)

      + versioning_configuration {
          + mfa_delete = (known after apply)
          + status     = "Enabled"
        }
    }

Plan: 2 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + bucket_arn        = (known after apply)
  + bucket_name       = "saniya-24bcs10246-demo-bucket"
  + bucket_region     = (known after apply)
  + versioning_status = "Enabled"
```

### 5. `terraform apply -auto-approve` – create the bucket

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ terraform apply -auto-approve

Terraform used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  + create

Terraform will perform the following actions:

  # aws_s3_bucket.demo will be created
  + resource "aws_s3_bucket" "demo" {
      + acceleration_status         = (known after apply)
      + acl                         = (known after apply)
      + arn                         = (known after apply)
      + bucket                      = "saniya-24bcs10246-demo-bucket"
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
          + "Environment" = "dev"
          + "ManagedBy"   = "Terraform"
          + "Name"        = "saniya-24bcs10246-demo-bucket"
          + "Owner"       = "saniya-24bcs10246"
          + "Project"     = "Session18"
        }
      + tags_all                    = {
          + "Environment" = "dev"
          + "ManagedBy"   = "Terraform"
          + "Name"        = "saniya-24bcs10246-demo-bucket"
          + "Owner"       = "saniya-24bcs10246"
          + "Project"     = "Session18"
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

  # aws_s3_bucket_versioning.demo will be created
  + resource "aws_s3_bucket_versioning" "demo" {
      + bucket = (known after apply)
      + id     = (known after apply)

      + versioning_configuration {
          + mfa_delete = (known after apply)
          + status     = "Enabled"
        }
    }

Plan: 2 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + bucket_arn        = (known after apply)
  + bucket_name       = "saniya-24bcs10246-demo-bucket"
  + bucket_region     = (known after apply)
  + versioning_status = "Enabled"
aws_s3_bucket.demo: Creating...
aws_s3_bucket.demo: Creation complete after 0s [id=saniya-24bcs10246-demo-bucket]
aws_s3_bucket_versioning.demo: Creating...
aws_s3_bucket_versioning.demo: Creation complete after 1s [id=saniya-24bcs10246-demo-bucket]

Apply complete! Resources: 2 added, 0 changed, 0 destroyed.

Outputs:

bucket_arn = "arn:aws:s3:::saniya-24bcs10246-demo-bucket"
bucket_name = "saniya-24bcs10246-demo-bucket"
bucket_region = "ap-south-1"
versioning_status = "Enabled"
```

### 6. `terraform show` – what's in the state

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ terraform show
# aws_s3_bucket.demo:
resource "aws_s3_bucket" "demo" {
    acceleration_status         = null
    arn                         = "arn:aws:s3:::saniya-24bcs10246-demo-bucket"
    bucket                      = "saniya-24bcs10246-demo-bucket"
    bucket_domain_name          = "saniya-24bcs10246-demo-bucket.s3.amazonaws.com"
    bucket_prefix               = null
    bucket_regional_domain_name = "saniya-24bcs10246-demo-bucket.s3.ap-south-1.amazonaws.com"
    force_destroy               = true
    hosted_zone_id              = "Z11RGJOFQNVJUP"
    id                          = "saniya-24bcs10246-demo-bucket"
    object_lock_enabled         = false
    policy                      = null
    region                      = "ap-south-1"
    request_payer               = "BucketOwner"
    tags                        = {
        "Environment" = "dev"
        "ManagedBy"   = "Terraform"
        "Name"        = "saniya-24bcs10246-demo-bucket"
        "Owner"       = "saniya-24bcs10246"
        "Project"     = "Session18"
    }
    tags_all                    = {
        "Environment" = "dev"
        "ManagedBy"   = "Terraform"
        "Name"        = "saniya-24bcs10246-demo-bucket"
        "Owner"       = "saniya-24bcs10246"
        "Project"     = "Session18"
    }

    grant {
        id          = "75aa57f09aa0c8caeab4f8c24e99d10f8e7faeebf76c078efc7c6caea54ba06a"
        permissions = [
            "FULL_CONTROL",
        ]
        type        = "CanonicalUser"
        uri         = null
    }

    server_side_encryption_configuration {
        rule {
            bucket_key_enabled = false

            apply_server_side_encryption_by_default {
                kms_master_key_id = null
                sse_algorithm     = "AES256"
            }
        }
    }

    versioning {
        enabled    = false
        mfa_delete = false
    }
}

# aws_s3_bucket_versioning.demo:
resource "aws_s3_bucket_versioning" "demo" {
    bucket                = "saniya-24bcs10246-demo-bucket"
    expected_bucket_owner = null
    id                    = "saniya-24bcs10246-demo-bucket"

    versioning_configuration {
        mfa_delete = null
        status     = "Enabled"
    }
}


Outputs:

bucket_arn = "arn:aws:s3:::saniya-24bcs10246-demo-bucket"
bucket_name = "saniya-24bcs10246-demo-bucket"
bucket_region = "ap-south-1"
versioning_status = "Enabled"
```

### 7. `terraform state list` / `terraform output`

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ terraform state list
aws_s3_bucket.demo
aws_s3_bucket_versioning.demo
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ terraform output
bucket_arn = "arn:aws:s3:::saniya-24bcs10246-demo-bucket"
bucket_name = "saniya-24bcs10246-demo-bucket"
bucket_region = "ap-south-1"
versioning_status = "Enabled"
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ terraform output -raw bucket_arn; echo
arn:aws:s3:::saniya-24bcs10246-demo-bucket
```

### 8. Verify with the AWS CLI (outside Terraform)

The bucket really exists in the (emulated) S3 API, with versioning and tags:

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ aws --endpoint-url http://localhost:31866 s3 ls
2026-10-07 13:39:27 saniya-24bcs10246-demo-bucket
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ aws --endpoint-url http://localhost:31866 s3api head-bucket --bucket saniya-24bcs10246-demo-bucket && echo 'bucket exists'
{
    "BucketRegion": "ap-south-1"
}
bucket exists
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ aws --endpoint-url http://localhost:31866 s3api get-bucket-versioning --bucket saniya-24bcs10246-demo-bucket
{
    "Status": "Enabled"
}
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ aws --endpoint-url http://localhost:31866 s3api get-bucket-tagging --bucket saniya-24bcs10246-demo-bucket
{
    "TagSet": [
        {
            "Key": "Owner",
            "Value": "saniya-24bcs10246"
        },
        {
            "Key": "ManagedBy",
            "Value": "Terraform"
        },
        {
            "Key": "Project",
            "Value": "Session18"
        },
        {
            "Key": "Environment",
            "Value": "dev"
        },
        {
            "Key": "Name",
            "Value": "saniya-24bcs10246-demo-bucket"
        }
    ]
}
```

Versioning in action – upload the same key twice and list the versions:

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ echo 'version 1' > hello.txt && aws --endpoint-url http://localhost:31866 s3 cp hello.txt s3://saniya-24bcs10246-demo-bucket/hello.txt --no-progress
upload: ./hello.txt to s3://saniya-24bcs10246-demo-bucket/hello.txt
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ echo 'version 2' > hello.txt && aws --endpoint-url http://localhost:31866 s3 cp hello.txt s3://saniya-24bcs10246-demo-bucket/hello.txt --no-progress && rm hello.txt
upload: ./hello.txt to s3://saniya-24bcs10246-demo-bucket/hello.txt
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ aws --endpoint-url http://localhost:31866 s3api list-object-versions --bucket saniya-24bcs10246-demo-bucket --query 'Versions[].{Key:Key,VersionId:VersionId,IsLatest:IsLatest,Size:Size}' --output table
-----------------------------------------------------------------------
|                         ListObjectVersions                          |
+----------+------------+-------+-------------------------------------+
| IsLatest |    Key     | Size  |              VersionId              |
+----------+------------+-------+-------------------------------------+
|  True    |  hello.txt |  10   |  FF667Np7hqRuVczJElX6.sPIWLuWBcU0   |
|  False   |  hello.txt |  10   |  pj0CFy0NuvgfPWAlKbv8qGB1kak4ln.P   |
+----------+------------+-------+-------------------------------------+
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ aws --endpoint-url http://localhost:31866 s3 cp s3://saniya-24bcs10246-demo-bucket/hello.txt -
version 2
```

### 9. Destroy

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ terraform plan -destroy
aws_s3_bucket.demo: Refreshing state... [id=saniya-24bcs10246-demo-bucket]
aws_s3_bucket_versioning.demo: Refreshing state... [id=saniya-24bcs10246-demo-bucket]

Terraform used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  - destroy

Terraform will perform the following actions:

  # aws_s3_bucket.demo will be destroyed
  - resource "aws_s3_bucket" "demo" {
      - arn                         = "arn:aws:s3:::saniya-24bcs10246-demo-bucket" -> null
      - bucket                      = "saniya-24bcs10246-demo-bucket" -> null
      - bucket_domain_name          = "saniya-24bcs10246-demo-bucket.s3.amazonaws.com" -> null
      - bucket_regional_domain_name = "saniya-24bcs10246-demo-bucket.s3.ap-south-1.amazonaws.com" -> null
      - force_destroy               = true -> null
      - hosted_zone_id              = "Z11RGJOFQNVJUP" -> null
      - id                          = "saniya-24bcs10246-demo-bucket" -> null
      - object_lock_enabled         = false -> null
      - region                      = "ap-south-1" -> null
      - request_payer               = "BucketOwner" -> null
      - tags                        = {
          - "Environment" = "dev"
          - "ManagedBy"   = "Terraform"
          - "Name"        = "saniya-24bcs10246-demo-bucket"
          - "Owner"       = "saniya-24bcs10246"
          - "Project"     = "Session18"
        } -> null
      - tags_all                    = {
          - "Environment" = "dev"
          - "ManagedBy"   = "Terraform"
          - "Name"        = "saniya-24bcs10246-demo-bucket"
          - "Owner"       = "saniya-24bcs10246"
          - "Project"     = "Session18"
        } -> null
        # (3 unchanged attributes hidden)

      - grant {
          - id          = "75aa57f09aa0c8caeab4f8c24e99d10f8e7faeebf76c078efc7c6caea54ba06a" -> null
          - permissions = [
              - "FULL_CONTROL",
            ] -> null
          - type        = "CanonicalUser" -> null
            # (1 unchanged attribute hidden)
        }

      - server_side_encryption_configuration {
          - rule {
              - bucket_key_enabled = false -> null

              - apply_server_side_encryption_by_default {
                  - sse_algorithm     = "AES256" -> null
                    # (1 unchanged attribute hidden)
                }
            }
        }

      - versioning {
          - enabled    = true -> null
          - mfa_delete = false -> null
        }
    }

  # aws_s3_bucket_versioning.demo will be destroyed
  - resource "aws_s3_bucket_versioning" "demo" {
      - bucket                = "saniya-24bcs10246-demo-bucket" -> null
      - id                    = "saniya-24bcs10246-demo-bucket" -> null
        # (1 unchanged attribute hidden)

      - versioning_configuration {
          - status     = "Enabled" -> null
            # (1 unchanged attribute hidden)
        }
    }

Plan: 0 to add, 0 to change, 2 to destroy.

Changes to Outputs:
  - bucket_arn        = "arn:aws:s3:::saniya-24bcs10246-demo-bucket" -> null
  - bucket_name       = "saniya-24bcs10246-demo-bucket" -> null
  - bucket_region     = "ap-south-1" -> null
  - versioning_status = "Enabled" -> null
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ terraform destroy -auto-approve
aws_s3_bucket.demo: Refreshing state... [id=saniya-24bcs10246-demo-bucket]
aws_s3_bucket_versioning.demo: Refreshing state... [id=saniya-24bcs10246-demo-bucket]

Terraform used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  - destroy

Terraform will perform the following actions:

  # aws_s3_bucket.demo will be destroyed
  - resource "aws_s3_bucket" "demo" {
      - arn                         = "arn:aws:s3:::saniya-24bcs10246-demo-bucket" -> null
      - bucket                      = "saniya-24bcs10246-demo-bucket" -> null
      - bucket_domain_name          = "saniya-24bcs10246-demo-bucket.s3.amazonaws.com" -> null
      - bucket_regional_domain_name = "saniya-24bcs10246-demo-bucket.s3.ap-south-1.amazonaws.com" -> null
      - force_destroy               = true -> null
      - hosted_zone_id              = "Z11RGJOFQNVJUP" -> null
      - id                          = "saniya-24bcs10246-demo-bucket" -> null
      - object_lock_enabled         = false -> null
      - region                      = "ap-south-1" -> null
      - request_payer               = "BucketOwner" -> null
      - tags                        = {
          - "Environment" = "dev"
          - "ManagedBy"   = "Terraform"
          - "Name"        = "saniya-24bcs10246-demo-bucket"
          - "Owner"       = "saniya-24bcs10246"
          - "Project"     = "Session18"
        } -> null
      - tags_all                    = {
          - "Environment" = "dev"
          - "ManagedBy"   = "Terraform"
          - "Name"        = "saniya-24bcs10246-demo-bucket"
          - "Owner"       = "saniya-24bcs10246"
          - "Project"     = "Session18"
        } -> null
        # (3 unchanged attributes hidden)

      - grant {
          - id          = "75aa57f09aa0c8caeab4f8c24e99d10f8e7faeebf76c078efc7c6caea54ba06a" -> null
          - permissions = [
              - "FULL_CONTROL",
            ] -> null
          - type        = "CanonicalUser" -> null
            # (1 unchanged attribute hidden)
        }

      - server_side_encryption_configuration {
          - rule {
              - bucket_key_enabled = false -> null

              - apply_server_side_encryption_by_default {
                  - sse_algorithm     = "AES256" -> null
                    # (1 unchanged attribute hidden)
                }
            }
        }

      - versioning {
          - enabled    = true -> null
          - mfa_delete = false -> null
        }
    }

  # aws_s3_bucket_versioning.demo will be destroyed
  - resource "aws_s3_bucket_versioning" "demo" {
      - bucket                = "saniya-24bcs10246-demo-bucket" -> null
      - id                    = "saniya-24bcs10246-demo-bucket" -> null
        # (1 unchanged attribute hidden)

      - versioning_configuration {
          - status     = "Enabled" -> null
            # (1 unchanged attribute hidden)
        }
    }

Plan: 0 to add, 0 to change, 2 to destroy.

Changes to Outputs:
  - bucket_arn        = "arn:aws:s3:::saniya-24bcs10246-demo-bucket" -> null
  - bucket_name       = "saniya-24bcs10246-demo-bucket" -> null
  - bucket_region     = "ap-south-1" -> null
  - versioning_status = "Enabled" -> null
aws_s3_bucket_versioning.demo: Destroying... [id=saniya-24bcs10246-demo-bucket]
aws_s3_bucket_versioning.demo: Destruction complete after 0s
aws_s3_bucket.demo: Destroying... [id=saniya-24bcs10246-demo-bucket]
aws_s3_bucket.demo: Destruction complete after 0s

Destroy complete! Resources: 2 destroyed.
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ aws --endpoint-url http://localhost:31866 s3 ls; terraform state list; echo "(no resources left in state)"
(no resources left in state)
```

## Observations

- `init` downloaded `hashicorp/aws` and wrote `.terraform.lock.hcl`; `validate` and `fmt` caught nothing because the code is clean.
- `plan` showed **2 to add** (bucket + versioning config). Values such as `arn` are `(known after apply)` because only the provider knows them after the API call.
- `aws_s3_bucket_versioning.demo` refers to `aws_s3_bucket.demo.id`, so Terraform built an **implicit dependency** and created the bucket first (and destroyed it last).
- `terraform show` / `state list` read from `terraform.tfstate` – Terraform's record of what it manages. The AWS CLI confirmed the real bucket, its tags and `"Status": "Enabled"` versioning; uploading the same key twice produced two versions.
- `force_destroy = true` let `terraform destroy` remove the bucket even though it contained objects; afterwards `s3 ls` and `state list` are empty.
- State files and the `.terraform/` directory are **not committed** (see [`../.gitignore`](../.gitignore)). While running I set `TF_DATA_DIR` to a folder outside the repo so `.terraform/` was never created here.
