variable "project_id" {
  description = "Google Cloud project ID that owns the Pub/Sub resources."
  type        = string
}

variable "region" {
  description = "Reserved regional hint for catalog consistency."
  type        = string
}

variable "resource_name_prefix" {
  description = "Prefix applied to the topic and subscription names."
  type        = string
}

variable "topic_name" {
  description = "Logical topic name suffix."
  type        = string
}

variable "create_subscription" {
  description = "Whether to create a subscription for the topic."
  type        = bool
  default     = true
}

variable "subscription_ack_deadline_seconds" {
  description = "Ack deadline for the created subscription."
  type        = number
  default     = 10
}

variable "create_dead_letter" {
  description = "Whether to create a dead-letter topic and attach a dead-letter policy."
  type        = bool
  default     = false
}

variable "dead_letter_max_delivery_attempts" {
  description = "Maximum delivery attempts before dead-lettering."
  type        = number
  default     = 5
}