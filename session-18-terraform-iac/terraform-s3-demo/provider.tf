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
