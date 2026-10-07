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
