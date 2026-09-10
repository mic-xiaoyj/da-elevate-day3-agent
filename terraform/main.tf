terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. Service Account for Agent Runtime
resource "google_service_account" "agent_sa" {
  account_id   = "cymbal-operations-agent-sa"
  display_name = "Cymbal Operations Agent Service Account"
}

# 2. Secret Manager Secret for Bigtable Database Toolbox Config
resource "google_secret_manager_secret" "bigtable_mcp_config" {
  secret_id = "bigtable-mcp-tools-secret"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "bigtable_mcp_config_version" {
  secret      = google_secret_manager_secret.bigtable_mcp_config.id
  secret_data = file("${path.module}/../tools.yaml")
}

# Grant Agent SA access to Secret
resource "google_secret_manager_secret_iam_member" "secret_access" {
  secret_id = google_secret_manager_secret.bigtable_mcp_config.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agent_sa.email}"
}

# 3. Cloud Run MCP Microservice (Database Toolbox)
resource "google_cloud_run_v2_service" "mcp_toolbox" {
  name     = "mcp-toolbox-bigtable"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.agent_sa.email

    containers {
      image = "us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:latest"
      args  = ["--tools-file=/etc/secrets/tools.yaml"]

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      volume_mounts {
        name       = "secret-tools-vol"
        mount_path = "/etc/secrets"
      }
    }

    volumes {
      name = "secret-tools-vol"
      secret {
        secret = google_secret_manager_secret.bigtable_mcp_config.secret_id
        items {
          version = "latest"
          path    = "tools.yaml"
        }
      }
    }
  }
}

# 4. IAM Bindings for BigQuery, Vertex AI, and Bigtable
resource "google_project_iam_member" "bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

resource "google_project_iam_member" "bq_data_viewer" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

resource "google_project_iam_member" "bigtable_reader" {
  project = var.project_id
  role    = "roles/bigtable.reader"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

resource "google_project_iam_member" "vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}
