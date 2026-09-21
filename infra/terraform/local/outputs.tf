output "cluster_name" {
  value = kind_cluster.this.name
}

output "kubeconfig_context" {
  value = "kind-${kind_cluster.this.name}"
}

output "agent_url" {
  value = "http://agent.localtest.me"
}

output "namespace" {
  value = module.platform.namespace
}

output "secret_name" {
  value = module.platform.secret_name
}
