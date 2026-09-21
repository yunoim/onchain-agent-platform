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

# --- Observability -------------------------------------------------------------------

resource "kubernetes_namespace_v1" "monitoring" {
  count = var.monitoring_enabled ? 1 : 0

  metadata {
    name = var.monitoring_namespace
    labels = {
      "app.kubernetes.io/part-of" = "onchain-agent-platform"
    }
  }
}

# Grafana reads its admin credentials from this Secret (grafana.admin.existingSecret), so
# the password never appears in Helm values or the release manifest.
resource "kubernetes_secret_v1" "grafana_admin" {
  count = var.monitoring_enabled ? 1 : 0

  metadata {
    name      = "grafana-admin"
    namespace = kubernetes_namespace_v1.monitoring[0].metadata[0].name
  }
  type = "Opaque"
  data = {
    "admin-user"     = var.grafana_admin_user
    "admin-password" = var.grafana_admin_password
  }
}

resource "helm_release" "monitoring" {
  count = var.monitoring_enabled ? 1 : 0

  name       = "monitoring"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  version    = var.monitoring_chart_version
  namespace  = kubernetes_namespace_v1.monitoring[0].metadata[0].name
  wait       = true
  timeout    = var.helm_timeout_seconds

  values = var.monitoring_values == "" ? [] : [var.monitoring_values]

  depends_on = [kubernetes_secret_v1.grafana_admin, helm_release.ingress_nginx]
}

# --- Application -----------------------------------------------------------------------

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

  # The Ingress needs an IngressClass to exist first, and the chart's ServiceMonitor /
  # PrometheusRule templates render only when the Prometheus Operator CRDs are present,
  # so the monitoring stack must be installed before the application chart.
  depends_on = [helm_release.ingress_nginx, helm_release.monitoring, kubernetes_secret_v1.platform]
}
