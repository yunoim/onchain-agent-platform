# Cluster layer for AWS: VPC + EKS from the community modules, then the same platform
# module used locally. PLAN-ONLY by policy: this root is validated in CI and may be
# planned with credentials, but `terraform apply` is a deliberate manual decision.
#
# Rough cost while running (ap-northeast-2, 2026 list prices, check before applying):
#   EKS control plane      ~ $0.10 / h
#   2 x t3.medium nodes    ~ $0.10 / h
#   NAT gateway            ~ $0.06 / h + data
#   Network LB (ingress)   ~ $0.03 / h
#   -> about $0.30 / h, $7 / day. Always `terraform destroy` when done; the NAT gateway
#      and LB keep billing even with zero traffic.

provider "aws" {
  region = var.aws_region
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  repo_root  = abspath("${path.module}/../../..")
  chart_path = "${local.repo_root}/deploy/helm/onchain-agent-platform"
  azs        = slice(data.aws_availability_zones.available.names, 0, 2)
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.13"

  name = "${var.cluster_name}-vpc"
  cidr = var.vpc_cidr
  azs  = local.azs

  private_subnets = [for i, az in local.azs : cidrsubnet(var.vpc_cidr, 4, i)]
  public_subnets  = [for i, az in local.azs : cidrsubnet(var.vpc_cidr, 4, i + 8)]

  enable_nat_gateway = true
  single_nat_gateway = true # one NAT is enough for a demo and halves the NAT bill

  # Tags the AWS load balancer controller / in-tree LB provisioner looks for.
  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }

  tags = var.tags
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.24"

  cluster_name    = var.cluster_name
  cluster_version = var.kubernetes_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Public API endpoint so `terraform apply` from a laptop can reach it; lock down with
  # cluster_endpoint_public_access_cidrs for anything beyond a demo.
  cluster_endpoint_public_access = true

  # Grant the identity running Terraform cluster-admin so the helm/kubernetes providers
  # below can create namespaces and releases.
  enable_cluster_creator_admin_permissions = true

  cluster_addons = {
    coredns    = {}
    kube-proxy = {}
    vpc-cni    = {}
  }

  eks_managed_node_groups = {
    default = {
      instance_types = var.node_instance_types
      min_size       = 1
      max_size       = 3
      desired_size   = var.node_desired_size
    }
  }

  tags = var.tags
}

# Provider configuration from a resource in the same apply: same caveat as the kind root.
data "aws_eks_cluster_auth" "this" {
  name = module.eks.cluster_name
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
  token                  = data.aws_eks_cluster_auth.this.token
}

provider "helm" {
  kubernetes = {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
    token                  = data.aws_eks_cluster_auth.this.token
  }
}

# On EKS the ingress controller sits behind a cloud load balancer instead of hostPort.
locals {
  ingress_nginx_values = yamlencode({
    controller = {
      service = {
        type = "LoadBalancer"
        annotations = {
          "service.beta.kubernetes.io/aws-load-balancer-type"   = "nlb"
          "service.beta.kubernetes.io/aws-load-balancer-scheme" = "internet-facing"
        }
      }
      ingressClassResource = { default = true }
    }
  })
}

module "platform" {
  source = "../modules/platform"

  chart_path = local.chart_path
  app_values = {
    mcpServer = { image = { tag = var.image_tag } }
    agent     = { image = { tag = var.image_tag } }
    ingress = {
      hosts           = { agent = var.agent_host }
      exposeLitellm   = false
      exposeMcpServer = false
    }
  }

  litellm_config  = file("${local.repo_root}/services/gateway/litellm/config.yaml")
  ollama_base_url = var.ollama_base_url

  secrets = {
    LITELLM_MASTER_KEY = var.litellm_master_key
    ETHERSCAN_API_KEY  = var.etherscan_api_key
    ANTHROPIC_API_KEY  = var.anthropic_api_key
  }

  ingress_nginx_enabled = true
  ingress_nginx_values  = local.ingress_nginx_values

  depends_on = [module.eks]
}
