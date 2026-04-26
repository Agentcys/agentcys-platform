output "database_name" {
  description = "Fully qualified Firestore database name."
  value       = google_firestore_database.this.name
}

output "database_id" {
  description = "Firestore database ID."
  value       = var.database_id
}