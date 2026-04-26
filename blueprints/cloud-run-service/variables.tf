variable "project_id" {
  description = "Google Cloud project ID that owns the Cloud Run service."
  type        = string
}

variable "region" {
  description = "Google Cloud region where the service will be deployed."
  type        = string
}

variable "resource_name_prefix" {
  description = "Cloud Run service name."
  type        = string
}

variable "container_image" {
  description = "OCI image reference for the service container."
  type        = string
}

variable "port" {
  description = "Container port exposed by the application."
  type        = number
  default     = 8080
}

variable "env_vars" {
  description = "Environment variables passed to the container."
  type        = map(string)
  default     = {}
}

variable "min_instances" {
  description = "Minimum number of Cloud Run instances."
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of Cloud Run instances."
  type        = number
  default     = 10
}

variable "cpu" {
  description = "CPU limit assigned to the container."
  type        = string
  default     = "1"
}

variable "memory" {
  description = "Memory limit assigned to the container."
  type        = string
  default     = "512Mi"
}

variable "allow_unauthenticated" {
  description = "When true, grants roles/run.invoker to allUsers."
  type        = bool
  default     = false
}