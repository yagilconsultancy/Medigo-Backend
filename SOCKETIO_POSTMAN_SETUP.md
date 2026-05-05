# Socket.IO Postman Setup Guide

## Quick Setup

### Method 1: Using the Collection (Recommended)
1. Import `postman_socketio_gateway_collection.json` into Postman
2. Select "Connect to Tracking (Guest)" request
3. Click **Connect**

### Method 2: Manual Configuration

#### For Tracking Namespace

**Connection Settings:**
```
Protocol: WebSocket (ws://)
Host: localhost:8080
Path: /api/v1/ws/socket.io    👈 IMPORTANT: Must include leading slash
Namespace: /tracking
```

**Full URL in Postman:**
```
ws://localhost:8080/api/v1/ws/socket.io/tracking
```

#### For Chat Namespace

**Connection Settings:**
```
Protocol: WebSocket (ws://)
Host: localhost:8080
Path: /api/v1/ws/socket.io    👈 IMPORTANT: Must include leading slash
Namespace: /chat
```

## Common Socket.IO Events

### Tracking Namespace Events

**Client → Server (Emit)**
```json
// Event: join_ride
{
  "ride_id": "123e4567-e89b-12d3-a456-426614174000"
}

// Event: leave_ride
{
  "ride_id": "123e4567-e89b-12d3-a456-426614174000"
}

// Event: update_location (drivers only)
{
  "latitude": 43.6532,
  "longitude": -79.3832,
  "heading": 180,
  "speed": 50
}

// Event: join_dispatch_center (admins only)
// No payload needed
```

**Server → Client (Listen)**
```json
// Event: location_update
{
  "ride_id": "...",
  "driver_id": "...",
  "latitude": 43.6532,
  "longitude": -79.3832,
  "heading": 180,
  "speed": 50,
  "timestamp": "2026-05-05T17:57:00Z"
}

// Event: tracking_started
{
  "ride_id": "...",
  "driver_id": "..."
}

// Event: tracking_ended
{
  "ride_id": "...",
  "reason": "ride_completed"
}
```

### Chat Namespace Events

**Client → Server (Emit)**
```json
// Event: join_conversation
{
  "conversation_id": "123e4567-e89b-12d3-a456-426614174000"
}

// Event: send_message
{
  "conversation_id": "...",
  "message": "Hello!"
}

// Event: typing
{
  "conversation_id": "..."
}
```

**Server → Client (Listen)**
```json
// Event: new_message
{
  "id": "...",
  "conversation_id": "...",
  "sender_id": "...",
  "sender_name": "John Doe",
  "message": "Hello!",
  "timestamp": "2026-05-05T17:57:00Z"
}

// Event: user_typing
{
  "user_id": "...",
  "user_name": "John Doe"
}
```

## Authentication (Optional)

For authenticated connections, add auth parameter when connecting:

```json
{
  "token": "your-jwt-token-here"
}
```

In Postman, this goes in the **Authentication** or **Query Params** section depending on the Socket.IO client version.

## Troubleshooting

### 403 Forbidden Error
- **Cause**: Wrong Socket.IO path
- **Fix**: Ensure path is `/api/v1/ws/socket.io` (with leading slash)

### Connection Timeout
- **Cause**: Services not running
- **Fix**: Run `docker-compose up -d` and ensure all services are healthy

### "Invalid namespace" Error
- **Cause**: Namespace doesn't exist or misspelled
- **Fix**: Use `/tracking` or `/chat` (with leading slash)

## Testing Connection with CLI

```bash
# Test using the provided Python script
python3 test_tracking_socketio.py
```

## Service URLs

| Service | Direct URL | Via Gateway |
|---------|-----------|-------------|
| Tracking | `http://localhost:8006/socket.io` | `http://localhost:8080/api/v1/ws/socket.io` |
| Notification (Chat) | `http://localhost:8007/socket.io` | `http://localhost:8080/api/v1/ws/socket.io` |

## Architecture Notes

- **API Gateway** runs at port **8080** and proxies Socket.IO connections
- **Tracking Service** runs at port **8006** with `/tracking` namespace
- **Notification Service** runs at port **8007** with `/chat` namespace
- Gateway uses a bridge pattern to forward events between frontend and backend services
- Backend services have Redis adapters for horizontal scaling
