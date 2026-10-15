terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }

  # Optional remote state (recommended for teams): create the bucket first, then uncomment.
  # backend "s3" {
  #   bucket       = "careslot-tfstate-<your-account-id>"
  #   key          = "eks/terraform.tfstate"
  #   region       = "ap-south-1"
  #   use_lockfile = true
  # }
}

provider "aws" {
  region = var.aws_region
  # Credentials come from `aws configure` / environment variables - never from this repository.
  default_tags {
    tags = {
      Project     = "careslot"
      Environment = var.environment
      Owner       = var.owner
      ManagedBy   = "terraform"
    }
  }
}
