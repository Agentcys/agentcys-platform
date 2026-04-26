locals {
  firestore_locations = {
    "us-central1"             = "nam5"
    "us-east1"                = "nam5"
    "us-east4"                = "nam5"
    "us-west1"                = "nam5"
    "northamerica-northeast1" = "nam5"
    "southamerica-east1"      = "nam5"
    "europe-west1"            = "eur3"
    "europe-west2"            = "eur3"
    "europe-west3"            = "eur3"
    "europe-west4"            = "eur3"
    "europe-west6"            = "eur3"
    "europe-west8"            = "eur3"
    "europe-west9"            = "eur3"
    "europe-north1"           = "eur3"
    "asia-south1"             = "nam5"
    "asia-southeast1"         = "nam5"
  }

  location_id = lookup(local.firestore_locations, var.region, var.region)
}

resource "google_firestore_database" "this" {
  project                           = var.project_id
  name                              = var.database_id
  location_id                       = local.location_id
  type                              = "FIRESTORE_NATIVE"
  deletion_policy                   = var.deletion_protection ? "ABANDON" : "DELETE"
  point_in_time_recovery_enablement = var.point_in_time_recovery ? "POINT_IN_TIME_RECOVERY_ENABLED" : "POINT_IN_TIME_RECOVERY_DISABLED"
}