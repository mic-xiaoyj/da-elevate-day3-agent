output "mcp_service_url" {
  description = "Cloud Run service URL for Bigtable MCP Database Toolbox"
  value       = google_cloud_run_v2_service.mcp_toolbox.uri
}

output "agent_service_account_email" {
  description = "Service Account email for Cymbal Operations Agent"
  value       = google_service_account.agent_sa.email
}
