output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "region" {
  value = var.aws_region
}

output "kubeconfig_command" {
  value = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

output "namespace" {
  value = module.platform.namespace
}

output "destroy_reminder" {
  value = "Run `terraform destroy` when finished: the control plane, NAT gateway and load balancer bill hourly."
}
