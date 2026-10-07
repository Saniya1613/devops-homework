resource "aws_s3_bucket" "assets" {
  bucket        = var.bucket_name
  force_destroy = true

  tags = { Name = var.bucket_name }
}

resource "aws_s3_bucket_versioning" "assets" {
  bucket = aws_s3_bucket.assets.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Upload a small object so the bucket isn't empty
resource "aws_s3_object" "readme" {
  bucket       = aws_s3_bucket.assets.id
  key          = "info.txt"
  content      = "Provisioned by Terraform for ${var.project_name}. EC2 instance: ${aws_instance.web.id}\n"
  content_type = "text/plain"
}
