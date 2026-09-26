output "ecr_repository_urls" {
  description = "ECR URLs to use in Helm image repositories."
  value       = { for name, repo in aws_ecr_repository.app : name => repo.repository_url }
}

output "eks_cluster_name" {
  description = "EKS cluster name. Empty until enable_eks is true."
  value       = try(module.eks[0].cluster_name, "")
}

output "eks_update_kubeconfig" {
  description = "Command that points kubectl at the cluster after enable_eks is applied."
  value       = var.enable_eks ? "aws eks update-kubeconfig --region ${var.aws_region} --name ${var.name}" : ""
}
