variable "cluster_name" {
  type    = string
  default = "onchain-agent"
}

variable "kind_node_image" {
  description = "kindest/node image. Empty = the default bundled with the kind provider's kind library. Do NOT pin to a newer kind CLI's image: kubeadm init fails when the node is newer than the library (seen with v1.37.0 on provider 0.11)."
  type        = string
  default     = ""
}

variable "use_local_images" {
  description = "true: build-and-load images (values-local.yaml). false: pull from GHCR (values.yaml defaults)."
  type        = bool
  default     = true
}

variable "image_tag" {
  description = "Image tag for the GHCR images when use_local_images = false."
  type        = string
  default     = "latest"
}

variable "ollama_base_url" {
  type    = string
  default = "http://host.docker.internal:11434"
}

variable "monitoring_enabled" {
  description = "Install kube-prometheus-stack. Needs roughly 1 GB of extra memory in the Docker VM."
  type        = bool
  default     = true
}

# --- Secrets: provide via TF_VAR_* env vars, never via a committed tfvars file ---

variable "grafana_admin_password" {
  type      = string
  sensitive = true
  default   = "admin"
}

variable "litellm_master_key" {
  type      = string
  sensitive = true
  default   = "sk-local-dev-change-me"
}

variable "etherscan_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "anthropic_api_key" {
  type      = string
  sensitive = true
  default   = ""
}
