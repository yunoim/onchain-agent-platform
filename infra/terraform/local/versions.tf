terraform {
  required_version = ">= 1.9"

  required_providers {
    kind = {
      source  = "tehcyx/kind"
      version = ">= 0.6, < 1.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.30, < 4.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = ">= 3.0, < 4.0"
    }
  }
}
