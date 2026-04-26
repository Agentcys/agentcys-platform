variable "project_id" {
  description = "Google Cloud project ID that owns the secret."
  type        = string
}

variable "region" {
  description = "Region used for user-managed replication."
  type        = string
}

variable "resource_name_prefix" {
  description = "Prefix applied to the secret identifier."
  type        = string
}

variable "secret_id" {
  description = "Logical secret identifier suffix."
  type        = string
}

variable "secret_value" {
  description = "Secret payload stored as the first secret version."
  type        = string
  sensitive   = true
}

variable "replication" {
  description = "Replication strategy for the secret."
  type        = string
  default     = "automatic"

  validation {
    condition     = contains(["automatic", "user_managed"], var.replication)
    error_message = "replication must be one of: automatic, user_managed."
  }
}