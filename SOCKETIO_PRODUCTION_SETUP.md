# Socket.IO Production Setup Guide

## Current Issue

Your Nginx config has **two different Socket.IO routing approaches** that conflict:

### ❌ Current Nginx Config (WRONG)
```nginx
location /socket.io/tracking/ {
    proxy_pass http://127.0.0.1:8006/socket.io/;  # Direct to tracking service
}
location /socket.io/chat/ {
    proxy_pass http://127.0.0.1:8007/socket.io/;  # Direct to notification service
}
```

**Problems:**
- Bypasses API gateway (no centralized auth/logging)
- Strips namespace from URL (won't work with `/tracking` and `/chat` namespaces)
- Direct exposure of backend ports
- Doesn't match your API gateway Socket.IO setup at `/api/v1/ws/socket.io`

---

## ✅ Recommended Solution

### 1. Update Nginx Configuration

Replace `/etc/nginx/conf.d/staging.getmedigo.com.conf` with the updated version:

```bash
# On your server
sudo cp /etc/nginx/conf.d/staging.getmedigo.com.conf /etc/nginx/conf.d/staging.getmedigo.com.conf.backup
sudo nano /etc/nginx/conf.d/staging.getmedigo.com.conf
```

**Add this location block:**

```nginx
# Socket.IO through API Gateway
location /api/v1/ws/socket.io/ {
    proxy_pass http://127.0.0.1:8080/api/v1/ws/socket.io/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Important for Socket.IO long-polling
    proxy_buffering off;
    proxy_read_timeout 86400s;
    proxy_send_timeout 86400s;
    proxy_connect_timeout 86400s;
}
```

**Remove these old location blocks:**
```nginx
# DELETE THESE:
location /socket.io/tracking/ { ... }
location /socket.io/chat/ { ... }
```

### 2. Test and Reload Nginx

```bash
# Test configuration
sudo nginx -t

# If test passes, reload
sudo systemctl reload nginx
```

---

## JavaScript Client Connection

### React/Vue/Angular Application

```javascript
import io from 'socket.io-client';

// Tracking Service
const trackingSocket = io('https://staging.getmedigo.com/tracking', {
    path: '/api/v1/ws/socket.io',
    transports: ['websocket', 'polling'],  // Try WebSocket first, fallback to polling
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionAttempts: 5
});

trackingSocket.on('connect', () => {
    console.log('Connected to tracking service');

    // Join a specific ride room
    trackingSocket.emit('join_ride', {
        ride_id: 'YOUR_RIDE_UUID'
    }, (response) => {
        console.log('Joined room:', response.room);
    });
});

trackingSocket.on('location_update', (data) => {
    console.log('Driver location:', data);
    // Update map marker: map.updateDriver(data.driver_id, data.latitude, data.longitude)
});

trackingSocket.on('disconnect', (reason) => {
    console.warn('Disconnected:', reason);
});

// Chat Service (requires authentication)
const chatSocket = io('https://staging.getmedigo.com/chat', {
    path: '/api/v1/ws/socket.io',
    auth: {
        token: localStorage.getItem('jwt_token')  // Your JWT token
    },
    transports: ['websocket', 'polling']
});

chatSocket.on('connect', () => {
    console.log('Connected to chat service');
});

chatSocket.on('new_message', (message) => {
    console.log('New message:', message);
});
```

### Vanilla JavaScript (CDN)

```html
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
</head>
<body>
    <script>
        const socket = io('https://staging.getmedigo.com/tracking', {
            path: '/api/v1/ws/socket.io'
        });

        socket.on('connect', () => {
            console.log('Connected!');
            socket.emit('join_ride', { ride_id: 'YOUR_RIDE_ID' });
        });

        socket.on('location_update', (data) => {
            console.log('Driver at:', data.latitude, data.longitude);
        });
    </script>
</body>
</html>
```

### React Native

```javascript
import io from 'socket.io-client';

const socket = io('https://staging.getmedigo.com/tracking', {
    path: '/api/v1/ws/socket.io',
    transports: ['websocket'],  // Mobile should use WebSocket only
    jsonp: false
});
```

---

## Testing the Connection

### 1. Test with the HTML Example

Open `socket_client_example.html` in your browser:
1. Select "Staging" environment
2. Click "Connect" for tracking
3. Check the event log for connection status

### 2. Test with Browser Console

```javascript
// Open browser console on your website
const socket = io('https://staging.getmedigo.com/tracking', {
    path: '/api/v1/ws/socket.io'
});

socket.on('connect', () => console.log('Connected!'));
socket.on('disconnect', () => console.log('Disconnected!'));
socket.on('connect_error', (err) => console.error('Error:', err));
```

### 3. Test with curl (Handshake)

```bash
# Test Socket.IO handshake
curl -v "https://staging.getmedigo.com/api/v1/ws/socket.io/?EIO=4&transport=polling"

# Expected response:
# 0{"sid":"xxxxx","upgrades":["websocket"],...}
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client (Browser/Mobile)                  │
│                                                                  │
│  const socket = io('https://staging.getmedigo.com/tracking', {  │
│      path: '/api/v1/ws/socket.io'                               │
│  });                                                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTPS (WSS for WebSocket)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Nginx (Port 443)                         │
│                                                                  │
│  location /api/v1/ws/socket.io/ {                               │
│      proxy_pass http://127.0.0.1:8080/api/v1/ws/socket.io/;     │
│  }                                                               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTP/WebSocket
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API Gateway (Port 8080)                       │
│                                                                  │
│  Socket.IO Bridge/Proxy                                         │
│  - Validates connections                                        │
│  - Routes to backend services based on namespace                │
│                                                                  │
│  Namespaces:                                                    │
│  /tracking → http://tracking-service:8006                       │
│  /chat → http://notification-service:8007                       │
└────────────────┬────────────────────────────┬───────────────────┘
                 │                            │
                 ▼                            ▼
     ┌───────────────────────┐   ┌───────────────────────┐
     │  Tracking Service     │   │  Notification Service │
     │  (Port 8006)          │   │  (Port 8007)          │
     │                       │   │                       │
     │  Socket.IO Server     │   │  Socket.IO Server     │
     │  Namespace: /tracking │   │  Namespace: /chat     │
     └───────────────────────┘   └───────────────────────┘
```

---

## Connection URLs Summary

| Environment | Base URL | Socket.IO Path | Full Example |
|-------------|----------|----------------|--------------|
| **Local** | `http://localhost:8080` | `/api/v1/ws/socket.io` | `io('http://localhost:8080/tracking', {path: '/api/v1/ws/socket.io'})` |
| **Staging** | `https://staging.getmedigo.com` | `/api/v1/ws/socket.io` | `io('https://staging.getmedigo.com/tracking', {path: '/api/v1/ws/socket.io'})` |

---

## Common Issues & Solutions

### Issue: "WebSocket connection failed"

**Cause:** Nginx not properly configured for WebSocket upgrade

**Solution:**
```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```

### Issue: "Namespace '/tracking' not found"

**Cause:** Wrong URL format or path

**Solution:**
```javascript
// CORRECT:
io('https://staging.getmedigo.com/tracking', {
    path: '/api/v1/ws/socket.io'
})

// WRONG:
io('https://staging.getmedigo.com/api/v1/ws/socket.io/tracking')
```

### Issue: "Authentication required" on /chat

**Cause:** Chat namespace requires JWT token

**Solution:**
```javascript
io('https://staging.getmedigo.com/chat', {
    path: '/api/v1/ws/socket.io',
    auth: { token: 'YOUR_JWT_TOKEN' }
})
```

### Issue: Connection works locally but not in production

**Check:**
1. Nginx configuration is updated and reloaded
2. SSL certificates are valid
3. Firewall allows WebSocket connections
4. API gateway is running and accessible

```bash
# Check if API gateway is running
curl https://staging.getmedigo.com/health

# Test Socket.IO endpoint
curl "https://staging.getmedigo.com/api/v1/ws/socket.io/?EIO=4&transport=polling"
```

---

## Deployment Checklist

- [ ] Update Nginx config with `/api/v1/ws/socket.io/` location block
- [ ] Remove old `/socket.io/tracking/` and `/socket.io/chat/` location blocks
- [ ] Test Nginx config: `sudo nginx -t`
- [ ] Reload Nginx: `sudo systemctl reload nginx`
- [ ] Verify API gateway is running on port 8080
- [ ] Test Socket.IO handshake with curl
- [ ] Test client connection with browser console
- [ ] Update frontend code to use correct URL and path
- [ ] Monitor logs: `docker logs -f mediride-api-gateway-1`

---

## Monitoring & Debugging

### Check API Gateway Logs

```bash
# View Socket.IO connection logs
docker logs -f mediride-api-gateway-1 | grep -i "socket\|websocket"

# Expected output:
# Socket.IO bridge established for sid=xxx namespace=/tracking
# INFO: connection open
```

### Check Backend Service Logs

```bash
# Tracking service
docker logs -f mediride-tracking-service-1 | grep -i "socket\|connection"

# Notification service
docker logs -f mediride-notification-service-1 | grep -i "socket\|connection"
```

### Browser DevTools

1. Open DevTools (F12)
2. Go to **Network** tab
3. Filter by **WS** (WebSocket)
4. Look for connections to `/api/v1/ws/socket.io/`
5. Check **Messages** tab to see Socket.IO packets

---

## Next Steps

1. **Update Nginx** with the new configuration
2. **Test locally** with `socket_client_example.html`
3. **Deploy to staging** and test with production URL
4. **Update frontend** applications with correct Socket.IO config
5. **Monitor logs** during initial rollout
