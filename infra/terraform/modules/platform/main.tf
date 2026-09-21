# Platform layer (ADR-0005): everything that runs *on* a cluster, independent of where the
# cluster came from. Consumed by infra/terraform/local (kind) and infra/terraform/aws-eks.

locals {
  secret_name = "${var.release_name}-platform-secrets"
}

resource "kubernetes_namespace_v1" "app" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/part-of" = "onchain-agent-platform"
    }
  }
}

# Secrets are created here, not by the chart, so the chart never holds credential values
# and the same Secret object can later be owned by External Secrets / SOPS without a chart
# change. Values arrive through TF_VAR_* and do land in Terraform state (see LEARNING.md).
resource "kubernetes_secret_v1" "platform" {
  metadata {
    name      = local.secret_name
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels = {
      "app.kubernetes.io/part-of"    = "onchain-agent-platform"
      "app.kubernetes.io/managed-by" = "terraform"
    }
  }
  type = "Opaque"
  data = var.secrets
}

resource "helm_release" "ingress_nginx" {
  count = var.ingress_nginx_enabled ? 1 : 0

  name             = "ingress-nginx"
  repository       = "https://kubernetes.github.io/ingress-nginx"
  chart            = "ingress-nginx"
  version          = var.ingress_nginx_chart_version
  namespace        = "ingress-nginx"
  create_namespace = true
  wait             = true
  timeout          = var.helm_timeout_seconds

  values = var.ingress_nginx_values == "" ? [] : [var.ingress_nginx_values]
}

resource "helm_release" "app" {
  name      = var.release_name
  chart     = var.chart_path
  namespace = kubernetes_namespace_v1.app.metadata[0].name
  wait      = true
  timeout   = var.helm_timeout_seconds

  # Order: chart defaults < values files < inline overrides < module-owned settings.
  values = concat(
    [for f in var.app_values_files : file(f)],
    [yamlencode(var.app_values)],
    [yamlencode({
      secrets = {
        create         = false
        existingSecret = kubernetes_secret_v1.platform.metadata[0].name
      }
      ollama = {
        baseUrl = var.ollama_base_url
      }
      litellm = {
        config = var.litellm_config
      }
    })],
  )

  # The Ingress needs an IngressClass to exist before the app's readiness gates matter.
  depends_on = [helm_release.ingress_nginx, kubernetes_secret_v1.platform]
}
