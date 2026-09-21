terraform {
  required_version = ">= 1.9"

  required_providers {
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
