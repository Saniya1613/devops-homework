# ---------------- EKS cluster + managed node group + add-ons ----------------
locals {
  node_subnet_ids = var.enable_nat_gateway ? aws_subnet.private[*].id : aws_subnet.public[*].id
}

# Envelope-encrypt Kubernetes Secrets (DB password) with a customer-managed KMS key.
resource "aws_kms_key" "eks" {
  description             = "${var.cluster_name} Kubernetes secrets encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}

# Accepted risks (documented): the API endpoint is public so kubectl works from a laptop and from
# GitHub Actions. Narrow it with var.public_access_cidrs; the private endpoint is enabled for nodes.
#trivy:ignore:AVD-AWS-0040
#trivy:ignore:AVD-AWS-0041
resource "aws_eks_cluster" "main" {
  name     = var.cluster_name
  version  = var.kubernetes_version
  role_arn = aws_iam_role.cluster.arn

  vpc_config {
    subnet_ids              = concat(aws_subnet.public[*].id, aws_subnet.private[*].id)
    endpoint_public_access  = true
    endpoint_private_access = true
    public_access_cidrs     = var.public_access_cidrs
  }

  # EKS access entries: whoever runs `terraform apply` becomes cluster admin automatically.
  access_config {
    authentication_mode                         = "API_AND_CONFIG_MAP"
    bootstrap_cluster_creator_admin_permissions = true
  }

  encryption_config {
    resources = ["secrets"]
    provider {
      key_arn = aws_kms_key.eks.arn
    }
  }

  enabled_cluster_log_types = ["api", "audit"]

  depends_on = [aws_iam_role_policy_attachment.cluster, aws_iam_role_policy.cluster_kms]
}

# Launch template for the worker nodes: IMDSv2 only, with a hop limit of 2 so pods (EBS CSI
# controller, etc.) can reach the instance metadata service. AL2023 nodes default to 1 hop.
resource "aws_launch_template" "nodes" {
  name_prefix = "${var.cluster_name}-nodes-"

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 20
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }

  tag_specifications {
    resource_type = "instance"
    tags          = { Name = "${var.cluster_name}-node" }
  }
}

resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.cluster_name}-nodes"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = local.node_subnet_ids
  instance_types  = var.node_instance_types
  capacity_type   = var.node_capacity_type

  launch_template {
    id      = aws_launch_template.nodes.id
    version = aws_launch_template.nodes.latest_version
  }

  scaling_config {
    desired_size = var.node_desired_size
    min_size     = var.node_min_size
    max_size     = var.node_max_size
  }

  update_config {
    max_unavailable = 1
  }

  labels = { workload = "careslot" }

  depends_on = [
    aws_iam_role_policy_attachment.node,
    aws_route_table_association.public,
    aws_route_table_association.private,
  ]
}

# Core add-ons managed by EKS. The EBS CSI driver backs PersistentVolumeClaims (PostgreSQL data).
resource "aws_eks_addon" "core" {
  for_each                    = toset(["vpc-cni", "kube-proxy", "coredns", "aws-ebs-csi-driver"])
  cluster_name                = aws_eks_cluster.main.name
  addon_name                  = each.value
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
  depends_on                  = [aws_eks_node_group.main]
}
