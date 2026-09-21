# Cluster layer for local development: a kind cluster, then the platform module on top.
#
#   cd infra/terraform/local
#   terraform init
#   terraform apply          # one command: cluster + ingress-nginx + secret + app chart
#   terraform destroy        # removes everything including the cluster
#
# Images: with use_local_images = true (default) the two service images must exist in the
# host Docker daemon (scripts/kind-load builds them, or `docker compose build`); Terraform
# loads them into the node right after the cluster is up.

locals {
  repo_root  = abspath("${path.module}/../../..")
  chart_path = "${local.repo_root}/deploy/helm/onchain-agent-platform"
}

resource "kind_cluster" "this" {
  name           = var.cluster_name
  node_image     = var.kind_node_image != "" ? var.kind_node_image : null
  wait_for_ready = true

  # Mirrors deploy/kind/cluster.yaml. Kept in HCL (not file()) because the provider
  # exposes the kubeconfig pieces only from its own schema.
  kind_config {
    kind        = "Cluster"
    api_version = "kind.x-k8s.io/v1alpha4"

    node {
      role = "control-plane"

      labels = {
        ingress-ready = "true"
      }

      extra_port_mappings {
        container_port = 80
        host_port      = 80
        protocol       = "TCP"
      }
      extra_port_mappings {
        container_port = 443
        host_port      = 443
        protocol       = "TCP"
      }
    }
  }
}

# Providers configured from a resource created in the same apply. Terraform tolerates
# this for kind because the attributes are known right after the cluster resource is
# created; it is still the sharpest edge in this root (see LEARNING.md, Phase 4).
provider "kubernetes" {
  host                   = kind_cluster.this.endpoint
  client_certificate     = kind_cluster.this.client_certificate
  client_key             = kind_cluster.this.client_key
  cluster_ca_certificate = kind_cluster.this.cluster_ca_certificate
}

provider "helm" {
  kubernetes = {
    host                   = kind_cluster.this.endpoint
    client_certificate     = kind_cluster.this.client_certificate
    client_key             = kind_cluster.this.client_key
    cluster_ca_certificate = kind_cluster.this.cluster_ca_certificate
  }
}

# Copy locally built images into the node (ADR-0006). Re-runs whenever the cluster is
# recreated or the image IDs change.
resource "terraform_data" "kind_load_images" {
  count = var.use_local_images ? 1 : 0

  triggers_replace = [
    kind_cluster.this.id,
    # Changing the tag content on the host does not change these strings; run
    # `terraform apply -replace=terraform_data.kind_load_images[0]` after a rebuild.
    "onchain-mcp-server:dev",
    "onchain-agent:dev",
  ]

  provisioner "local-exec" {
    command = "kind load docker-image onchain-mcp-server:dev onchain-agent:dev --name ${kind_cluster.this.name}"
  }
}

module "platform" {
  source = "../modules/platform"

  chart_path       = local.chart_path
  app_values_files = var.use_local_images ? ["${local.chart_path}/values-local.yaml"] : []
  app_values = var.use_local_images ? {} : {
    mcpServer = { image = { tag = var.image_tag } }
    agent     = { image = { tag = var.image_tag } }
  }

  litellm_config  = file("${local.repo_root}/services/gateway/litellm/config.yaml")
  ollama_base_url = var.ollama_base_url

  secrets = {
    LITELLM_MASTER_KEY = var.litellm_master_key
    ETHERSCAN_API_KEY  = var.etherscan_api_key
    ANTHROPIC_API_KEY  = var.anthropic_api_key
  }

  ingress_nginx_enabled = true
  ingress_nginx_values  = file("${local.repo_root}/deploy/kind/ingress-nginx-values.yaml")

  monitoring_enabled     = var.monitoring_enabled
  monitoring_values      = file("${local.repo_root}/deploy/observability/kube-prometheus-stack-values.yaml")
  grafana_admin_password = var.grafana_admin_password

  depends_on = [kind_cluster.this, terraform_data.kind_load_images]
}
