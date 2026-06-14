#!/bin/bash
set -euo pipefail

# ===========================================
# MediRide Production Server Setup Script
# ===========================================
# Run this on a fresh Amazon Linux 2023 EC2 instance
# Usage: sudo bash setup-server-prod.sh
#
# Prerequisites:
#   - EC2 instance (t3.xlarge recommended, 16GB RAM)
#   - Security group: ports 22, 80, 443 open
#   - RDS PostgreSQL instance created and accessible from this EC2
#   - S3 bucket created with IAM credentials
#   - DNS: prod-api.getmedigo.com -> instance Elastic IP

DOMAIN="prod-api.getmedigo.com"
APP_DIR="/opt/mediride"

echo "=========================================="
echo "  MediRide Production Server Setup"
echo "  (Amazon Linux 2023)"
echo "=========================================="

# --- 1. System updates ---
echo "[1/7] Updating system packages..."
dnf update -y
dnf install -y \
    git \
    unzip \
    nginx \
    firewalld \
    htop

# --- 2. Install Docker ---
echo "[2/7] Installing Docker..."
if ! command -v docker &>/dev/null; then
    dnf install -y docker
    systemctl enable docker
    systemctl start docker
    usermod -aG docker ec2-user
fi

# Install Docker Compose plugin
echo "Installing Docker Compose plugin..."
DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name"' | cut -d'"' -f4)
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Verify
docker compose version

# --- 3. Install Certbot ---
echo "[3/7] Installing Certbot..."
dnf install -y certbot python3-certbot-nginx

# --- 4. Configure firewall ---
echo "[4/7] Configuring firewall..."
systemctl enable firewalld
systemctl start firewalld
firewall-cmd --permanent --add-service=http
firewall-cmd --permanent --add-service=https
firewall-cmd --permanent --add-service=ssh
firewall-cmd --reload

# --- 5. Setup Nginx ---
echo "[5/7] Configuring Nginx..."

cat > /etc/nginx/conf.d/prod-api.getmedigo.com.conf << 'NGINX_CONF'
upstream mediride_api {
    server 127.0.0.1:8080;
}

limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/s;

server {
    listen 80;
    listen [::]:80;
    server_name prod-api.getmedigo.com;

    client_max_body_size 20M;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # API proxy
    location /api/ {
        limit_req zone=api_limit burst=50 nodelay;

        proxy_pass http://mediride_api/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 30s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Socket.IO WebSocket proxy for tracking
    location /socket.io/tracking/ {
        proxy_pass http://127.0.0.1:8006/socket.io/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # Socket.IO WebSocket proxy for chat
    location /socket.io/chat/ {
        proxy_pass http://127.0.0.1:8007/socket.io/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # Health check
    location /health {
        proxy_pass http://mediride_api/health/live;
        proxy_set_header Host $host;
    }

    location / {
        return 404 '{"error": "Not found"}';
        add_header Content-Type application/json;
    }
}
NGINX_CONF

# Remove default nginx page
rm -f /etc/nginx/conf.d/default.conf

# Test and start Nginx
nginx -t
systemctl enable nginx
systemctl start nginx

# --- 6. Setup application directory ---
echo "[6/7] Setting up application directory..."
mkdir -p "$APP_DIR"
chown ec2-user:ec2-user "$APP_DIR"

# --- 7. SSL Certificate ---
echo "[7/7] SSL certificate..."
echo ""
echo "  IMPORTANT: Make sure DNS for ${DOMAIN} points to this server's Elastic IP first!"
echo ""
read -p "  DNS is configured? (y/n): " dns_ready

if [ "$dns_ready" = "y" ]; then
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email admin@getmedigo.com --redirect
    # Setup auto-renewal
    systemctl enable certbot-renew.timer 2>/dev/null || echo "certbot timer setup skipped"
    echo "SSL certificate installed!"
else
    echo "Skipping SSL. Run this later:"
    echo "  sudo certbot --nginx -d ${DOMAIN} --agree-tos --email admin@getmedigo.com --redirect"
fi

echo ""
echo "=========================================="
echo "  Production server setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Log out and back in (for docker group):  exit && ssh ec2-user@<ip>"
echo "  2. Clone the repo:  cd /opt/mediride && git clone <your-repo-url> ."
echo "  3. Create .env:     cp deploy/env.prod.example .env"
echo "  4. Edit .env:       nano .env  (fill in RDS host, S3 keys, secrets)"
echo "  5. Start services:  docker compose -f deploy/docker-compose.prod.yml up -d"
echo "  6. Run migrations:  bash deploy/run-migrations.sh"
echo ""
echo "AWS checklist:"
echo "  - Elastic IP attached to this instance"
echo "  - RDS security group allows inbound 5432 from this EC2"
echo "  - S3 bucket created with IAM user credentials in .env"
echo "  - RDS databases created (run deploy/init-databases.sql on RDS)"
echo ""
