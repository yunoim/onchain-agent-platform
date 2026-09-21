output "cluster_name" {
  value = kind_cluster.this.name
}

output "kubeconfig_context" {
  value = "kind-${kind_cluster.this.name}"
}

output "agent_url" {
  value = "http://agent.localtest.me"
}

output "grafana_url" {
  value = var.monitoring_enabled ? "http://grafana.localtest.me (user: admin)" : null
}

output "prometheus_url" {
  value = var.monitoring_enabled ? "http://prometheus.localtest.me" : null
}

output "namespace" {
  value = module.platform.namespace
}

output "secret_name" {
  value = module.platform.secret_name
}
