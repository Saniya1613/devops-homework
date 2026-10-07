output "vpc_id" {
  value = aws_vpc.main.id
}
output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}
output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}
output "app_security_group_id" {
  value = aws_security_group.app.id
}
output "artifacts_bucket" {
  value = aws_s3_bucket.artifacts.bucket
}
output "cluster_name" {
  value = var.create_eks ? aws_eks_cluster.this[0].name : "(EKS not created – create_eks=false)"
}
