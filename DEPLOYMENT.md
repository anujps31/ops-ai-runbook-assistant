# Docker Deployment Guide

## Quick Start with Docker Compose

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- 8GB+ RAM (for Ollama qwen3:8b model)
- 20GB+ disk space

### Step 1: Start Services
```bash
# Navigate to project directory
cd ops-ai-runbook-assistant

# Start all services (API, UI, Ollama)
docker-compose up -d

# View logs
docker-compose logs -f

# Check service status
docker-compose ps
```

### Step 2: Initialize Ollama Model
```bash
# Pull the qwen3:8b model (one-time operation)
docker-compose exec ollama ollama pull qwen3:8b

# Verify model is loaded
docker-compose exec ollama ollama list
```

### Step 3: Access Services

| Service | URL | Purpose |
|---------|-----|---------|
| **FastAPI** | http://localhost:8000 | REST API with Swagger docs |
| **API Docs** | http://localhost:8000/docs | Interactive API documentation |
| **Streamlit UI** | http://localhost:8501 | Web dashboard for incident analysis |
| **Ollama API** | http://localhost:11434 | LLM inference endpoint |

### Step 4: Test API
```bash
# Health check
curl http://localhost:8000/health

# Analyze incident (example)
curl -X POST http://localhost:8000/api/v1/incidents/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "incident": "Production API returning 503 errors. Symptoms: customers unable to login, increased latency, multiple pods restarting."
  }'
```

---

## Docker Compose Configuration

### Services

#### 1. FastAPI API Service
- **Port**: 8000
- **Health Check**: Every 30s
- **Volumes**:
  - `./data`: Shared data/runbooks
  - `./app`: Application code (for development)
  - `./logs`: Application logs
- **Dependencies**: Ollama service
- **Environment**: `OLLAMA_BASE_URL=http://ollama:11434`

#### 2. Streamlit UI Service
- **Port**: 8501
- **Dependencies**: API service
- **Volumes**: Same as API
- **Access**: Browser at http://localhost:8501

#### 3. Ollama LLM Service
- **Port**: 11434
- **Image**: `ollama/ollama:latest`
- **Volume**: `ollama-data` (persistent model storage)
- **Memory**: 8GB+ recommended
- **GPU Support**: Optional (see GPU section below)

### Network
- **Type**: Bridge network `ops-ai-network`
- **Communication**: Services use service names (e.g., `http://ollama:11434`)

---

## Advanced Configuration

### GPU Support (CUDA/ROCm)

#### NVIDIA GPU
```yaml
# Add to ollama service in docker-compose.yml
services:
  ollama:
    image: ollama/ollama:latest
    runtime: nvidia  # Requires nvidia-docker
    environment:
      - CUDA_VISIBLE_DEVICES=0
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

#### AMD GPU
```yaml
services:
  ollama:
    image: ollama/ollama:latest
    environment:
      - ROCM_VISIBLE_DEVICES=0
```

### Custom Configuration

#### Environment Variables
```bash
# Create .env file
OLLAMA_BASE_URL=http://ollama:11434
LOG_LEVEL=DEBUG
HOST=0.0.0.0
PORT=8000
```

#### Volume Customization
```yaml
services:
  api:
    volumes:
      - /custom/path/data:/app/data
      - /custom/path/logs:/app/logs
```

#### Resource Limits
```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
  
  ollama:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 6G
```

---

## Build Custom Images

### Build from Dockerfile
```bash
# Build image
docker build -t ops-ai-runbook:latest .

# Tag for registry
docker tag ops-ai-runbook:latest myregistry.azurecr.io/ops-ai-runbook:latest

# Push to registry
docker push myregistry.azurecr.io/ops-ai-runbook:latest
```

### Multi-stage Build Details

**Stage 1: Builder**
- Installs build tools
- Generates Python wheels
- Keeps wheel layer separate

**Stage 2: Runtime**
- Minimal Python base image
- Only copies wheels (smaller layer)
- Non-root user for security
- ~500MB final image size

---

## Kubernetes Deployment

### Create Namespace
```bash
kubectl create namespace ops-ai
```

### Deploy with Helm (Optional)

```bash
# Create values.yaml
helm install ops-ai ./helm \
  -n ops-ai \
  --values values.yaml
```

### Manual Kubernetes Manifests

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ops-ai-api
  namespace: ops-ai
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ops-ai-api
  template:
    metadata:
      labels:
        app: ops-ai-api
    spec:
      containers:
      - name: api
        image: myregistry.azurecr.io/ops-ai-runbook:latest
        env:
        - name: SERVICE
          value: "api"
        - name: OLLAMA_BASE_URL
          value: "http://ollama-service:11434"
        ports:
        - containerPort: 8000
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 2000m
            memory: 2Gi

---
apiVersion: v1
kind: Service
metadata:
  name: ops-ai-api
  namespace: ops-ai
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8000
  selector:
    app: ops-ai-api
```

### Deploy to Kubernetes
```bash
# Apply manifests
kubectl apply -f deployment.yaml

# Check deployment status
kubectl rollout status deployment/ops-ai-api -n ops-ai

# View pods
kubectl get pods -n ops-ai

# View logs
kubectl logs -f deployment/ops-ai-api -n ops-ai
```

---

## Production Deployment

### Best Practices

1. **Use Health Checks**
   ```yaml
   healthcheck:
     test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
     interval: 30s
     timeout: 10s
     retries: 3
     start_period: 10s
   ```

2. **Set Resource Limits**
   - API: 1-2 CPU, 1-2GB RAM
   - Ollama: 4+ CPU, 8GB+ RAM
   - Streamlit: 1 CPU, 512MB RAM

3. **Use Volume Mounts**
   - Persistent storage for ChromaDB
   - Persistent storage for logs
   - Read-only runbooks volume

4. **Logging**
   - Driver: json-file
   - Max size: 10m
   - Max files: 3

5. **Monitoring**
   - Export `/metrics` endpoint
   - Monitor `/health` endpoint
   - Set up alerts on failures

6. **Networking**
   - Use reverse proxy (nginx, Traefik)
   - Enable CORS for production domains
   - Rate limit at proxy layer
   - Use HTTPS/TLS

7. **Security**
   - Non-root container user
   - Read-only filesystem where possible
   - Network policies
   - Secret management for .env

### Docker Stack/Swarm (Alternatives to Compose)

```bash
# Deploy with Docker Stack
docker stack deploy -c docker-compose.yml ops-ai
```

---

## Troubleshooting

### Service Not Starting
```bash
# Check logs
docker-compose logs api

# Inspect container
docker-compose ps
docker inspect ops-ai-api

# Restart service
docker-compose restart api
```

### Memory Issues
```bash
# Check memory usage
docker stats

# Increase Docker memory limit
# Edit Docker Desktop settings or docker daemon config

# Increase specific service memory in compose
services:
  ollama:
    environment:
      - OLLAMA_NUM_GPU=1
```

### Network Connectivity
```bash
# Test service communication
docker-compose exec api curl http://ollama:11434/api/tags

# Inspect network
docker network ls
docker network inspect ops-ai-network
```

### Ollama Model Issues
```bash
# List loaded models
docker-compose exec ollama ollama list

# Pull model again
docker-compose exec ollama ollama pull qwen3:8b

# Check Ollama logs
docker-compose logs ollama
```

---

## Performance Tuning

### API Performance
- Use `uvicorn` with `--workers` parameter
- Enable caching for RAG results
- Use connection pooling

### LLM Performance
- Pre-load models on startup
- Batch requests where possible
- Monitor token generation speed

### Database Performance
- Regular ChromaDB maintenance
- Index optimization
- Query result caching

---

## Maintenance

### Backup

```bash
# Backup ChromaDB data
docker-compose exec api tar czf - /app/data/chroma | \
  gzip > chroma_backup_$(date +%Y%m%d).tar.gz

# Backup Ollama models
docker run --rm \
  -v ollama-data:/backup \
  ubuntu tar czf - /backup | \
  gzip > ollama_backup_$(date +%Y%m%d).tar.gz
```

### Updates

```bash
# Pull latest images
docker-compose pull

# Rebuild if Dockerfile changed
docker-compose build --no-cache

# Restart services
docker-compose restart
```

### Cleanup

```bash
# Remove stopped containers
docker-compose down

# Remove volumes (CAUTION: deletes data!)
docker-compose down -v

# Remove unused images
docker image prune -a
```

---

## References

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Ollama Docker Guide](https://github.com/ollama/ollama/tree/main/docker)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)

---

**Version**: 0.1.0  
**Last Updated**: 2026-06-24
