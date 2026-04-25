output "service_url" {
  description = "HTTPS URL assigned to the Cloud Run service."
  value       = google_cloud_run_v2_service.this.uri
}

output "service_name" {
  description = "Cloud Run service name."
  value       = google_cloud_run_v2_service.this.name
}

output "service_id" {
  description = "Fully qualified Cloud Run service resource ID."
  value       = google_cloud_run_v2_service.this.id
}