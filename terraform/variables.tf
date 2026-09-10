variable "project_id" {
  description = "Google Cloud project ID"
  type        = string
}

variable "region" {
  description = "Primary GCP region for Cloud Run and regional resources"
  type        = string
  default     = "us-central1"
}

variable "data_agent_id" {
  description = "BigQuery Conversational Data Agent resource ID"
  type        = string
  default     = "cymbal-retail-analytics"
}

variable "bigtable_instance_id" {
  description = "Bigtable instance ID for operations database"
  type        = string
  default     = "operations-db"
}
