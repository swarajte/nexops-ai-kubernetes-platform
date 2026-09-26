data "aws_availability_zones" "available" {
  count = var.enable_eks ? 1 : 0
  state = "available"
}

module "vpc" {
  count   = var.enable_eks ? 1 : 0
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.16.0"

  name = var.name
  cidr = "10.20.0.0/16"

  azs            = slice(data.aws_availability_zones.available[0].names, 0, 2)
  public_subnets = ["10.20.1.0/24", "10.20.2.0/24"]

  # No NAT gateway. A NAT gateway would add about $1/day before any traffic.
  # Worker nodes sit in public subnets and pull images directly from ECR.
  enable_nat_gateway   = false
  enable_dns_hostnames = true
  enable_dns_support   = true

  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }
}
