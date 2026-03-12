#!/bin/bash
set -euo pipefail

# ===========================================
# MediRide Staging Server Setup Script
# ===========================================
# Run this on a fresh Ubuntu 22.04/24.04 EC2 instance
# Usage: sudo bash setup-server.sh
#
# Prerequisites:
#   - EC2 instance (t3.large recommended, 8GB RAM)
#   - Security group: ports 22, 80, 443 open
#   - DNS: staging.getmedigo.com -> instance public IP

DOMAIN="staging.getmedigo.com"
APP_DIR="/opt/mediride"
DEPLOY_USER="deploy"

echo "=========================================="
echo "  MediRide Staging Server Setup"
echo "=========================================="

# --- 1. System updates ---
echo "[1/8] Updating system packages..."
apt-get update -y
apt-get upgrade -y
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    ufw \
    fail2ban \
    unzip

# --- 2. Create deploy user ---
echo "[2/8] Creating deploy user..."
if ! id "$DEPLOY_USER" &>/dev/null; then
    useradd -m -s /bin/bash "$DEPLOY_USER"
    usermod -aG sudo "$DEPLOY_USER"
    echo "$DEPLOY_USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$DEPLOY_USER
fi

# --- 3. Install Docker ---
echo "[3/8] Installing Docker..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker "$DEPLOY_USER"
fi

# Install Docker Compose plugin
echo "Installing Docker Compose plugin..."
apt-get install -y docker-compose-plugin 2>/dev/null || true

# Start and enable Docker
systemctl enable docker
systemctl start docker

# --- 4. Install Nginx ---
echo "[4/8] Installing Nginx..."
apt-get install -y nginx
systemctl enable nginx

# --- 5. Install Certbot ---
echo "[5/8] Installing Certbot..."
apt-get install -y certbot python3-certbot-nginx

# --- 6. Configure firewall ---
echo "[6/8] Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# --- 7. Setup application directory ---
echo "[7/8] Setting up application directory..."
mkdir -p "$APP_DIR"
chown "$DEPLOY_USER":"$DEPLOY_USER" "$APP_DIR"

# Create Nginx config (HTTP only initially, Certbot adds HTTPS)
cat > /etc/nginx/sites-available/staging.getmedigo.com << 'NGINX_CONF'
upstream mediride_api {
    server 127.0.0.1:8080;
}

limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/s;

server {
    listen 80;
    server_name staging.getmedigo.com;

    client_max_body_size 20M;

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

# Enable the site
ln -sf /etc/nginx/sites-available/staging.getmedigo.com /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test and reload Nginx
nginx -t
systemctl reload nginx

# --- 8. SSL Certificate ---
echo "[8/8] Obtaining SSL certificate..."
echo ""
echo "  IMPORTANT: Make sure DNS for ${DOMAIN} points to this server's IP first!"
echo ""
read -p "  DNS is configured? (y/n): " dns_ready

if [ "$dns_ready" = "y" ]; then
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email admin@getmedigo.com --redirect
    echo "SSL certificate installed!"
else
    echo "Skipping SSL. Run this later:"
    echo "  sudo certbot --nginx -d ${DOMAIN} --agree-tos --email admin@getmedigo.com --redirect"
fi

# Setup certbot auto-renewal
systemctl enable certbot.timer

echo ""
echo "=========================================="
echo "  Server setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Switch to deploy user:  sudo su - deploy"
echo "  2. Clone the repo:         cd /opt/mediride && git clone <your-repo-url> ."
echo "  3. Copy env file:          cp deploy/env.staging.example .env"
echo "  4. Edit .env with real passwords"
echo "  5. Start services:         docker compose -f deploy/docker-compose.staging.yml up -d"
echo "  6. Run migrations:         ./deploy/run-migrations.sh"
echo ""
echo "Or just push to main and let GitHub Actions handle it!"
echo ""
