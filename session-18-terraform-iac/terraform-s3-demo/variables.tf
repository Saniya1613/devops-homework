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
