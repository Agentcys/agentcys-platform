output "secret_name" {
  description = "Fully qualified Secret Manager secret name."
  value       = google_secret_manager_secret.this.name
}

output "secret_id" {
  description = "Secret identifier created by the module."
  value       = google_secret_manager_secret.this.secret_id
}

output "version_id" {
  description = "Resource name of the created secret version."
  value       = google_secret_manager_secret_version.this.name
}