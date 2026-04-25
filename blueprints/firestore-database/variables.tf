variable "project_id" {
  description = "Google Cloud project ID that owns the Firestore database."
  type        = string
}

variable "region" {
  description = "Region mapped to the closest supported Firestore location."
  type        = string
}

variable "resource_name_prefix" {
  description = "Reserved naming prefix for catalog consistency."
  type        = string
}

variable "database_id" {
  description = "Firestore database ID."
  type        = string
  default     = "(default)"
}

variable "deletion_protection" {
  description = "Prevents destroy by abandoning the remote database resource."
  type        = bool
  default     = true
}

variable "point_in_time_recovery" {
  description = "Enables point-in-time recovery for supported locations."
  type        = bool
  default     = false
}