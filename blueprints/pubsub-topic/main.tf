locals {
  effective_topic_name             = "${var.resource_name_prefix}-${var.topic_name}"
  effective_subscription_name      = "${local.effective_topic_name}-sub"
  effective_dead_letter_topic_name = "${local.effective_topic_name}-dlq"
}

resource "google_pubsub_topic" "this" {
  #checkov:skip=CKV_GCP_83:Reusable blueprint contract does not accept a CMEK/CSEK input in v1.0.0.
  project = var.project_id
  name    = local.effective_topic_name
}

resource "google_pubsub_topic" "dead_letter" {
  count   = var.create_dead_letter ? 1 : 0
  project = var.project_id
  name    = local.effective_dead_letter_topic_name
}

resource "google_pubsub_subscription" "this" {
  count   = var.create_subscription ? 1 : 0
  project = var.project_id
  name    = local.effective_subscription_name
  topic   = google_pubsub_topic.this.id

  ack_deadline_seconds = var.subscription_ack_deadline_seconds

  dynamic "dead_letter_policy" {
    for_each = var.create_dead_letter ? [1] : []
    content {
      dead_letter_topic     = google_pubsub_topic.dead_letter[0].id
      max_delivery_attempts = var.dead_letter_max_delivery_attempts
    }
  }
}