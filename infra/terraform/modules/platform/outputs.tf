output "namespace" {
  value = kubernetes_namespace_v1.app.metadata[0].name
}

output "release_name" {
  value = helm_release.app.name
}

output "secret_name" {
  value = kubernetes_secret_v1.platform.metadata[0].name
}

output "ingress_nginx_installed" {
  value = var.ingress_nginx_enabled
}

output "monitoring_namespace" {
  value = var.monitoring_enabled ? kubernetes_namespace_v1.monitoring[0].metadata[0].name : null
}
