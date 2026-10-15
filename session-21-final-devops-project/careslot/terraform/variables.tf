variable "aws_region" {
  description = "AWS region for every resource"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "owner" {
  description = "Tag value so the resources are easy to find in the console"
  type        = string
  default     = "saniya-24bcs10246"
}

variable "cluster_name" {
  type    = string
  default = "careslot-eks"
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version. null = the current AWS default (avoids paid extended support)."
  type        = string
  default     = null
}

variable "vpc_cidr" {
  type    = string
  default = "10.30.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "One public subnet per AZ (load balancers, and worker nodes when NAT is disabled)"
  type        = list(string)
  default     = ["10.30.0.0/20", "10.30.16.0/20"]
}

variable "private_subnet_cidrs" {
  description = "One private subnet per AZ (worker nodes when NAT is enabled)"
  type        = list(string)
  default     = ["10.30.128.0/20", "10.30.144.0/20"]
}

variable "enable_nat_gateway" {
  description = "true = nodes in private subnets behind one NAT gateway (production style, ~USD 1/day extra). false = nodes in public subnets (cheapest for a demo)."
  type        = bool
  default     = false
}

variable "node_instance_types" {
  type    = list(string)
  default = ["t3.medium"]
}

variable "node_capacity_type" {
  description = "ON_DEMAND or SPOT (SPOT is ~60-70% cheaper, fine for a demo)"
  type        = string
  default     = "ON_DEMAND"
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "node_min_size" {
  type    = number
  default = 1
}

variable "node_max_size" {
  type    = number
  default = 3
}

variable "public_access_cidrs" {
  description = "Who may reach the Kubernetes API endpoint. Narrow it to your IP, e.g. [\"203.0.113.7/32\"]."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
