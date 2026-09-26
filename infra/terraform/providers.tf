provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.tags
  }
}

locals {
  tags = {
    Project = "nexops"
    Stage   = "12"
    Managed = "terraform"
  }
}
