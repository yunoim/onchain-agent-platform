variable "aws_region" {
  type    = string
  default = "ap-northeast-2"
}

variable "cluster_name" {
  type    = string
  default = "onchain-agent"
}

variable "kubernetes_version" {
  type    = string
  default = "1.31"
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "node_instance_types" {
  description = "Small on purpose; the workload is three light pods. Ollama is not run here."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "image_tag" {
  description = "GHCR image tag for the two service images."
  type        = string
  default     = "latest"
}

variable "agent_host" {
  description = "Hostname routed to the agent by ingress-nginx. Point a DNS record at the LB."
  type        = string
  default     = "agent.example.com"
}

variable "ollama_base_url" {
  description = "There is no host GPU in EKS. Point this at an in-cluster Ollama Service or an external endpoint, or set LLM_MODEL to a hosted alias."
  type        = string
  default     = "http://ollama.ollama.svc.cluster.local:11434"
}

variable "litellm_master_key" {
  type      = string
  sensitive = true
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

variable "grafana_admin_password" {
  type      = string
  sensitive = true
}

variable "tags" {
  type = map(string)
  default = {
    Project   = "onchain-agent-platform"
    ManagedBy = "terraform"
  }
}
