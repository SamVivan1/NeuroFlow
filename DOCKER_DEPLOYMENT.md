# Neuroflow Docker Deployment Guide

## Quick Start

### Build and run:
```bash
docker-compose up -d
```

### Stop:
```bash
docker-compose down
```

### View logs:
```bash
docker-compose logs -f frontend
```

## Configuration

### Memory Optimization
- **Limit**: 512MB RAM (enforced in docker-compose.yml)
- **Node.js**: --max-old-space-size=256
- **Reservation**: 256MB minimum

### Image Size
Multi-stage build reduces image size:
- Build stage: Node.js 20 Alpine (full build tools)
- Runtime stage: Node.js 20 Alpine (production only)
- Final size: ~300-400MB (with dependencies)

## Production Features

✓ Non-root user (nextjs:nextjs)  
✓ Health checks enabled  
✓ Automatic restart policy  
✓ Signal handling (dumb-init)  
✓ Log rotation (max 10MB per file)  
✓ Alpine Linux (minimal footprint)  

## Scaling

For limited resources (512MB), single container recommended. If you need to scale:

```bash
docker-compose up -d --scale frontend=2  # Not recommended with 512MB limit
```

## Network Access

- Frontend: http://localhost:3000
- MQTT (if enabled): localhost:1883

## Optional MQTT Broker

Uncomment mqtt-broker service in docker-compose.yml to run local MQTT:
- Port 1883: MQTT protocol
- Port 9001: WebSocket

Uses only 128MB when enabled.

## Troubleshooting

### Out of memory errors:
```bash
# Check memory usage
docker stats neuroflow-frontend

# Restart container
docker-compose restart frontend
```

### Build issues:
```bash
# Clear Docker cache and rebuild
docker-compose build --no-cache frontend
```

### Connection issues:
```bash
# Test connectivity
docker-compose exec frontend wget -O- http://localhost:3000
```
