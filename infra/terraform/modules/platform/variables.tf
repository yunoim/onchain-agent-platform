variable "namespace" {
  description = "Namespace for the application release."
  type        = string
  default     = "onchain"
}

variable "release_name" {
  description = "Helm release name for the application chart."
  type        = string
  default     = "oap"
}

variable "chart_path" {
  description = "Path to the onchain-agent-platform chart directory."
  type        = string
}

variable "app_values_files" {
  description = "Extra values files applied to the application chart, in order (later wins)."
  type        = list(string)
  default     = []
}

variable "app_values" {
  description = "Inline values map merged last into the application chart (e.g. image tags, ingress hosts)."
  type        = any
  default     = {}
}

variable "litellm_config" {
  description = "Full LiteLLM proxy config (YAML). Injected as litellm.config; canonical file lives in services/gateway/litellm/config.yaml."
  type        = string
}

variable "secrets" {
  description = "Key/value pairs written to the platform Secret. Keys: LITELLM_MASTER_KEY, ETHERSCAN_API_KEY, ANTHROPIC_API_KEY."
  type        = map(string)
  sensitive   = true
}

variable "ollama_base_url" {
  description = "Ollama endpoint as seen from pods."
  type        = string
  default     = "http://host.docker.internal:11434"
}

variable "ingress_nginx_enabled" {
  description = "Install ingress-nginx. Disable when the cluster already has an ingress controller."
  type        = bool
  default     = true
}

variable "ingress_nginx_chart_version" {
  type    = string
  default = "4.15.1"
}

variable "ingress_nginx_values" {
  description = "Values (YAML string) for the ingress-nginx chart. Differs per cluster type: hostPort on kind, LoadBalancer on EKS."
  type        = string
  default     = ""
}

variable "helm_timeout_seconds" {
  type    = number
  default = 600
}
