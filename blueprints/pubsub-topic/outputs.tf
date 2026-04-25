output "topic_name" {
  description = "Created Pub/Sub topic name."
  value       = google_pubsub_topic.this.name
}

output "topic_id" {
  description = "Fully qualified Pub/Sub topic ID."
  value       = google_pubsub_topic.this.id
}

output "subscription_name" {
  description = "Created subscription name, or null when subscription creation is disabled."
  value       = var.create_subscription ? google_pubsub_subscription.this[0].name : null
}

output "dead_letter_topic_name" {
  description = "Created dead-letter topic name, or null when dead-lettering is disabled."
  value       = var.create_dead_letter ? google_pubsub_topic.dead_letter[0].name : null
}