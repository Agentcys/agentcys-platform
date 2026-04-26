locals {
  bucket_name = "${var.resource_name_prefix}-${var.bucket_name_suffix}"
}

##tfsec:ignore:google-storage-bucket-encryption-customer-key Reusable blueprint contract does not accept a KMS key input in v1.0.0.
resource "google_storage_bucket" "this" {
  #checkov:skip=CKV_GCP_62:Reusable blueprint contract does not accept an access logging bucket target in v1.0.0.
  #checkov:skip=CKV_GCP_78:Versioning default is user-specified and intentionally defaults to false per published contract.
  name     = local.bucket_name
  project  = var.project_id
  location = var.region

  storage_class               = var.storage_class
  force_destroy               = var.force_destroy
  uniform_bucket_level_access = var.uniform_bucket_level_access
  public_access_prevention    = "enforced"

  versioning {
    enabled = var.versioning
  }

  dynamic "lifecycle_rule" {
    for_each = var.lifecycle_age_days == null ? [] : [var.lifecycle_age_days]
    content {
      condition {
        age = lifecycle_rule.value
      }

      action {
        type = "Delete"
      }
    }
  }
}