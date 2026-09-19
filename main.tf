terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

locals {
  project_id          = "project-c6caeb96-abbd-4e9c-bfa"
  region              = "asia-south1"
  zone                = "asia-south1-c"
  instance_group_name = "crm-vm-group"
}

provider "google" {
  project = local.project_id
  region  = local.region
}

# 1. Cloud Armor WAF Policy
resource "google_compute_security_policy" "crm_waf" {
  name        = "crm-waf-policy"
  description = "Cloud Armor protection for CRM"

  rule {
    action   = "deny(403)"
    priority = "1000"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["198.51.100.0/24"]
      }
    }
    description = "Deny bad IP range"
  }

  rule {
    action   = "allow"
    priority = "2147483647"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "Default allow"
  }
}

# 2. HTTP Health Check
resource "google_compute_health_check" "crm_health_check" {
  name               = "crm-http-health-check"
  check_interval_sec = 10
  timeout_sec        = 5

  http_health_check {
    port = 80
  }
}

# 3. Backend Service
resource "google_compute_backend_service" "crm_backend" {
  name                  = "crm-backend-service"
  protocol              = "HTTP"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 30
  health_checks         = [google_compute_health_check.crm_health_check.id]
  security_policy       = google_compute_security_policy.crm_waf.id

  backend {
    group = "projects/${local.project_id}/zones/${local.zone}/instanceGroups/${local.instance_group_name}"
  }
}

# 4. URL Map
resource "google_compute_url_map" "crm_url_map" {
  name            = "crm-url-map"
  default_service = google_compute_backend_service.crm_backend.id
}

# 5. Target HTTP Proxy
resource "google_compute_target_http_proxy" "crm_http_proxy" {
  name    = "crm-target-http-proxy"
  url_map = google_compute_url_map.crm_url_map.id
}

# 6. Public IP Reservation
resource "google_compute_global_address" "crm_public_ip" {
  name = "crm-static-ip"
}

# 7. Global Forwarding Rule
resource "google_compute_global_forwarding_rule" "crm_forwarding_rule" {
  name                  = "crm-forwarding-rule"
  ip_protocol           = "TCP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  port_range            = "80"
  target                = google_compute_target_http_proxy.crm_http_proxy.id
  ip_address            = google_compute_global_address.crm_public_ip.id
}

# 8. Firewall Rule
resource "google_compute_firewall" "allow_lb_to_backend" {
  name    = "allow-gcp-lb-to-backend"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["80"]
  }

  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]
}

output "crm_load_balancer_url" {
  value       = "http://${google_compute_global_address.crm_public_ip.address}"
  description = "Access the CRM application through this URL"
}
