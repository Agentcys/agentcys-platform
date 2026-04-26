locals {
  effective_secret_id = "${var.resource_name_prefix}-${var.secret_id}"
}

resource "google_secret_manager_secret" "this" {
  project   = var.project_id
  secret_id = local.effective_secret_id

  replication {
    dynamic "auto" {
      for_each = var.replication == "automatic" ? [1] : []
      content {}
    }

    dynamic "user_managed" {
      for_each = var.replication == "user_managed" ? [1] : []
      content {
        replicas {
          location = var.region
        }
      }
    }
  }
}

resource "google_secret_manager_secret_version" "this" {
  secret      = google_secret_manager_secret.this.id
  secret_data = var.secret_value
}