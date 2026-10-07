resource "aws_instance" "web" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id        # implicit dependency
  vpc_security_group_ids = [aws_security_group.web.id] # implicit dependency

  user_data = <<-EOT
    #!/bin/bash
    yum install -y nginx
    echo "Hello from Saniya (24bcs10246) - Session 19" > /usr/share/nginx/html/index.html
    systemctl enable --now nginx
  EOT

  # EXPLICIT dependency: nothing in this block references the route table
  # association, but the instance should only launch once the subnet actually
  # has a route to the Internet Gateway (so user_data can reach package repos).
  depends_on = [aws_route_table_association.public]

  tags = { Name = "${var.project_name}-web" }
}
