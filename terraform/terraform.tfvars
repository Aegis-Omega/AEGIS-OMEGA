# AEGIS-Ω Vertex AI Deployment — GCP Project aegisomegav1
# Application Template: projects/aegisomegav1/locations/us-central1/spaces/default-space/applicationTemplates/app-template-1

regional-lb-frontend_project_id        = "aegisomegav1"
regional-lb-frontend_region             = "us-central1"
regional-lb-frontend_name               = "aegis-lb-frontend"
regional-lb-frontend_network            = "default"

memorystore_project_id                  = "aegisomegav1"
memorystore_region                      = "us-central1"
memorystore_name                        = "aegis-chain-store"

frontend-service-cloud-run_project_id   = "aegisomegav1"
frontend-service-cloud-run_location     = "us-central1"
frontend-service-cloud-run_service_name = "aegis-hub"

database-postgresql_project_id          = "aegisomegav1"
database-postgresql_region              = "us-central1"
database-postgresql_name                = "aegis-audit-db"
database-postgresql_database_version    = "POSTGRES_16"

backend-service-cloud-run_project_id    = "aegisomegav1"
backend-service-cloud-run_location      = "us-central1"
backend-service-cloud-run_service_name  = "aegis-constitutional-proxy"

regional-lb-backend_project_id          = "aegisomegav1"
regional-lb-backend_region              = "us-central1"
regional-lb-backend_name                = "aegis-lb-backend"

agent-registry-agent-1_project_id       = "aegisomegav1"
agent-registry-agent-1_location         = "us-central1"

apphub_project_id                        = "aegisomegav1"
apphub_location                          = "us-central1"
apphub_application_id                    = "aegis-omega"
