variable "aws_region" {
  description = "AWS region. Stockholm matches the new account console."
  type        = string
  default     = "eu-north-1"
}

variable "name" {
  description = "Short name used for ECR repositories and, later, the EKS cluster."
  type        = string
  default     = "nexops"
}

variable "enable_eks" {
  description = <<-EOT
    Create the VPC and EKS cluster. Leave false until you are ready to spend credits.
    Approximate cost while the cluster is running: EKS control plane about $0.10/hour
    ($2.40/day) plus one t3.medium worker (about $1/day). There is no NAT gateway.
    Run terraform destroy when you are not using the cluster.
  EOT
  type        = bool
  default     = false
}

variable "cluster_version" {
  description = "EKS Kubernetes version. Change this if AWS rejects it for the chosen region."
  type        = string
  default     = "1.33"
}

variable "node_instance_type" {
  description = "Single worker size. t3.medium is the smallest comfortable size for the NexOps chart."
  type        = string
  default     = "t3.medium"
}
