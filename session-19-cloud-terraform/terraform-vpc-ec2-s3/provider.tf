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
