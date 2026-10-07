# Session 18 – Terraform & Infrastructure as Code Homework

**Name:** Saniya Sanjiv Patil · **Roll No:** 24bcs10246 · **Batch:** B

> **Note – LocalStack instead of a real AWS account:** I did not have an AWS account available, so all Terraform and
> AWS CLI commands in this session were run against **LocalStack 3.8**, a local AWS emulator running in Docker
> (`localstack/localstack:3.8`, exposed on `http://localhost:31866`). Terraform uses the real `hashicorp/aws` provider
> and the real AWS CLI – only the endpoint URL points to LocalStack. The LocalStack-only settings live in
> [`terraform-s3-demo/provider.tf`](./terraform-s3-demo/provider.tf), with a comment describing how to switch to real AWS
> (delete the `endpoints` block and fake keys, then `aws configure`). All command output in this folder is real.

## Contents

| Task | Folder | What's inside |
|---|---|---|
| 1 | [`terraform-s3-demo/`](./terraform-s3-demo/README.md) | Terraform project creating an S3 bucket (versioning + tags), full workflow init → destroy with real output |
| 2 | [`aws-services/01-iam/`](./aws-services/01-iam/README.md) | IAM notes + sample least-privilege policy + CLI demo (user, group, policy) |
| 2 | [`aws-services/02-ec2/`](./aws-services/02-ec2/README.md) | EC2 notes + CLI demo (key pair, SG, instance lifecycle) |
| 2 | [`aws-services/03-s3/`](./aws-services/03-s3/README.md) | S3 notes + CLI demo (versioning, encryption, lifecycle, storage class) |
| 2 | [`aws-services/04-vpc/`](./aws-services/04-vpc/README.md) | VPC notes (CIDR, subnets, route tables, IGW, NAT, SG vs NACL) |
| 2 | [`aws-services/05-dynamodb-rds/`](./aws-services/05-dynamodb-rds/README.md) | DynamoDB notes + CLI demo (table, put/get/query) and RDS notes |

---

## Task 1 – Terraform S3 bucket

**Goal:** provision an S3 bucket `saniya-24bcs10246-demo-bucket` with versioning and tags using Terraform, then walk
through the full workflow. Adapted from the instructor's `session18-terraform-iac/terraform-s3-demo`.

**Files** (in [`terraform-s3-demo/`](./terraform-s3-demo/)):

| File | Purpose |
|---|---|
| [`provider.tf`](./terraform-s3-demo/provider.tf) | `terraform {}` block pinning `hashicorp/aws ~> 5.0` + `provider "aws"` (LocalStack endpoints, clearly commented) |
| [`variables.tf`](./terraform-s3-demo/variables.tf) | `aws_region`, `bucket_name`, `environment`, `enable_versioning` |
| [`terraform.tfvars`](./terraform-s3-demo/terraform.tfvars) | values: `ap-south-1`, `saniya-24bcs10246-demo-bucket`, `dev`, `true` |
| [`main.tf`](./terraform-s3-demo/main.tf) | `aws_s3_bucket.demo` (tags, `force_destroy`) + `aws_s3_bucket_versioning.demo` |
| [`outputs.tf`](./terraform-s3-demo/outputs.tf) | `bucket_name`, `bucket_arn`, `bucket_region`, `versioning_status` |

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

**Workflow summary** – the complete real output of every command is in
[`terraform-s3-demo/README.md`](./terraform-s3-demo/README.md#terraform-workflow-real-output):

| Step | Command | Result |
|---|---|---|
| 1 | `terraform init` | downloaded `hashicorp/aws` v5.x, created `.terraform.lock.hcl` |
| 2 | `terraform fmt` | no changes – code already in canonical format |
| 3 | `terraform validate` | `Success! The configuration is valid.` |
| 4 | `terraform plan` | `Plan: 2 to add, 0 to change, 0 to destroy.` |
| 5 | `terraform apply -auto-approve` | `Apply complete! Resources: 2 added` + 4 outputs |
| 6 | `terraform show` / `state list` | bucket and versioning resources recorded in state |
| 7 | `terraform output` | bucket name, ARN `arn:aws:s3:::saniya-24bcs10246-demo-bucket`, region `ap-south-1`, versioning `Enabled` |
| 8 | `aws s3 ls`, `s3api head-bucket / get-bucket-versioning / get-bucket-tagging / list-object-versions` | bucket exists, versioning `Enabled`, tags present, two versions of `hello.txt` |
| 9 | `terraform plan -destroy` → `terraform destroy -auto-approve` | `Destroy complete! Resources: 2 destroyed.` |

Final `terraform output` captured during the run:

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ terraform output
bucket_arn = "arn:aws:s3:::saniya-24bcs10246-demo-bucket"
bucket_name = "saniya-24bcs10246-demo-bucket"
bucket_region = "ap-south-1"
versioning_status = "Enabled"
```

```console
saniya@saniya-devops:~/devops-homework/session-18-terraform-iac/terraform-s3-demo$ terraform destroy -auto-approve
...
Destroy complete! Resources: 2 destroyed.
```

**Key learnings**
- **IaC**: the bucket is defined in code, version-controlled and reproducible – `apply` creates it, `destroy` removes it, every time the same way.
- **Declarative**: I describe the desired end state; Terraform's plan computes the diff between code, state and real infrastructure.
- **Variables/tfvars** keep the code reusable (another bucket name = another tfvars file); **outputs** expose values for humans or other modules.
- **State** (`terraform.tfstate`) maps code to real resource IDs – it must never be committed (it can contain secrets); teams use a remote backend (S3 + locking). See [`.gitignore`](./.gitignore).
- **Implicit dependency**: `aws_s3_bucket_versioning` references `aws_s3_bucket.demo.id`, so Terraform orders creation/destruction automatically.

---

## Task 2 – AWS services study notes

| Service | Notes | Topics covered | Demo on LocalStack |
|---|---|---|---|
| IAM | [01-iam/README.md](./aws-services/01-iam/README.md) | what is IAM, users, groups, roles, policies, permissions, least privilege, best practices, use cases, sample JSON policy | ✅ create user, group, policy; attach |
| EC2 | [02-ec2/README.md](./aws-services/02-ec2/README.md) | what is EC2, AMI, instance types, key pairs, security groups, EBS, public vs private IP, lifecycle, use cases | ✅ key pair, SG, run/stop/start/terminate (mocked) |
| S3 | [03-s3/README.md](./aws-services/03-s3/README.md) | what is S3, buckets, objects, storage classes, versioning, lifecycle policies, encryption, bucket policies, use cases | ✅ versioning, SSE, lifecycle, storage class |
| VPC | [04-vpc/README.md](./aws-services/04-vpc/README.md) | what is VPC, CIDR, subnets, route tables, IGW, NAT GW, security groups, NACLs, public vs private subnet | ➡️ built with Terraform in [session 19](../session-19-cloud-terraform/README.md) |
| DynamoDB & RDS | [05-dynamodb-rds/README.md](./aws-services/05-dynamodb-rds/README.md) | NoSQL, tables, items, attributes, partition key, sort key, use cases · relational, engines, DB instances, security, backups, Multi-AZ, read replicas, use cases | ✅ DynamoDB create/put/get/query · ❌ RDS (not in LocalStack community) |

### Quick comparison

| Service | Category | Scope | One-liner |
|---|---|---|---|
| IAM | Security / identity | Global | Who can do what on which resource |
| EC2 | Compute (IaaS) | AZ | Virtual servers |
| S3 | Object storage | Region (global namespace) | Unlimited, 11-nines durable file/object store |
| VPC | Networking | Region (subnets per AZ) | Your private, isolated network |
| DynamoDB | NoSQL database | Region | Serverless key-value DB, ms latency at any scale |
| RDS | Relational database | AZ / Multi-AZ | Managed MySQL/PostgreSQL/Aurora/… |

---

## What was / wasn't executed
- ✅ Terraform init/fmt/validate/plan/apply/show/state/output/destroy – executed against LocalStack.
- ✅ AWS CLI verification and the IAM, EC2, S3 and DynamoDB demos – executed against LocalStack.
- ⚠️ EC2 on LocalStack community is **mocked** (no VM actually boots) and IAM policies are stored but not enforced.
- ❌ RDS – not available in LocalStack community edition and no AWS account, so notes only.
- No real AWS account, credentials or costs involved; LocalStack uses dummy keys `test/test` and account `000000000000`.
