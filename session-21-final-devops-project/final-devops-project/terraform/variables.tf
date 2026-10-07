variable "aws_region" {
  type    = string
  default = "ap-south-1"
}
variable "environment" {
  type    = string
  default = "dev"
}
variable "cluster_name" {
  type    = string
  default = "taskboard-eks"
}
variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}
variable "azs" {
  type    = list(string)
  default = ["ap-south-1a", "ap-south-1b"]
}
variable "public_subnets" {
  type    = list(string)
  default = ["10.20.101.0/24", "10.20.102.0/24"]
}
variable "private_subnets" {
  type    = list(string)
  default = ["10.20.1.0/24", "10.20.2.0/24"]
}
variable "create_eks" {
  description = "Create the EKS control plane + node group (real AWS only – not available in LocalStack community)"
  type        = bool
  default     = false
}
variable "use_localstack" {
  type    = bool
  default = true
}
variable "localstack_endpoint" {
  type    = string
  default = "http://localhost:32166"
}
