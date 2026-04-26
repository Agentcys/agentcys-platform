variable "project_id" {
  description = "Google Cloud project ID that owns the bucket."
  type        = string
}

variable "region" {
  description = "Bucket location."
  type        = string
}

variable "resource_name_prefix" {
  description = "Prefix applied to the bucket name."
  type        = string
}

variable "bucket_name_suffix" {
  description = "Suffix appended to the bucket name."
  type        = string
}

variable "storage_class" {
  description = "Bucket storage class."
  type        = string
  default     = "STANDARD"
}

variable "versioning" {
  description = "Whether to enable bucket object versioning."
  type        = bool
  default     = false
}

variable "uniform_bucket_level_access" {
  description = "Whether to enable uniform bucket-level access."
  type        = bool
  default     = true
}

variable "lifecycle_age_days" {
  description = "Optional lifecycle age threshold in days for object deletion."
  type        = number
  default     = null
  nullable    = true
}

variable "force_destroy" {
  description = "Whether Terraform may delete a non-empty bucket."
  type        = bool
  default     = false
}