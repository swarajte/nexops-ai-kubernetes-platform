module "eks" {
  count   = var.enable_eks ? 1 : 0
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.31"

  cluster_name    = var.name
  cluster_version = var.cluster_version

  vpc_id     = module.vpc[0].vpc_id
  subnet_ids = module.vpc[0].public_subnets

  cluster_endpoint_public_access           = true
  cluster_endpoint_private_access          = false
  enable_cluster_creator_admin_permissions = true

  # Control-plane logs go to CloudWatch and add cost. Leave them off for this demo.
  cluster_enabled_log_types = []

  eks_managed_node_groups = {
    demo = {
      name                        = "${var.name}-demo"
      instance_types              = [var.node_instance_type]
      min_size                    = 1
      max_size                    = 1
      desired_size                = 1
      capacity_type               = "ON_DEMAND"
      disk_size                   = 20
      associate_public_ip_address = true
      subnet_ids                  = module.vpc[0].public_subnets
    }
  }
}
