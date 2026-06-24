# OPS AI Runbook Assistant

**Enterprise-grade AI-powered incident analysis and triage platform for Kubernetes, cloud infrastructure, and platform operations.**

An intelligent automation system combining FastAPI, Streamlit, Ollama LLM, ChromaDB vector database, and multi-agent architecture to provide real-time incident analysis, root cause diagnosis, and remediation recommendations.

---

## 🎯 Features

- **Multi-Agent Architecture**: Parallel execution of Incident, Root Cause, and Recommendation agents for comprehensive analysis
- **RAG-Powered Intelligence**: Retrieval-Augmented Generation using ChromaDB vector database with 20+ production runbooks
- **Enterprise Runbooks**: Pre-built runbooks covering Kubernetes, AKS, EKS, databases, Redis, Kafka, GitHub Actions, and more
- **Real-time Analysis**: Structured incident analysis with severity classification, confidence scoring, and business impact assessment
- **Parallel Processing**: ThreadPoolExecutor-based agent orchestration for sub-second latency improvements
- **Production-Ready**: Comprehensive logging, health checks, startup verification, and error handling
- **Professional Dashboard**: Streamlit-based UI with metrics, severity badges, and execution insights
- **API-First Design**: FastAPI with OpenAPI documentation, structured response envelopes, and comprehensive error handling

---

## 📋 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit UI (Port 8501)                  │
│  Dashboard | Metrics | Incident Samples | Real-time Metrics  │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/JSON
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Backend (Port 8000)                     │
├─────────────────────────────────────────────────────────────┤
│  POST /api/v1/incidents/analyze                             │
│  GET  /health                                               │
│  GET  /metrics                                              │
└────┬────────────────────────────────────────────────────────┘
     │
     ├─────────────────────────────────────────────────────────┐
     │                 Orchestrator Agent                       │
     │  (Parallel ThreadPoolExecutor: 3 workers)               │
     │                                                          │
     ├──────────────────┬──────────────────┬──────────────────┤
     │                  │                  │                  │
     ▼                  ▼                  ▼                  ▼
  Incident         Root Cause        Recommendation      ChromaDB
  Agent            Agent             Agent               Retrieval
  (RAG)            (RAG)             (RAG)               Service
     │                  │                  │                  │
     └──────────────────┴──────────────────┴──────────────────┘
                         │
                         ▼
              ┌──────────────────────────┐
              │   ChromaDB Vector DB     │
              │  (Persistent Storage)    │
              │  data/chroma/            │
              └──────────────────────────┘
                         │
                         ▼
              ┌──────────────────────────┐
              │   Ollama LLM (qwen3:8b)  │
              │   Port 11434             │
              └──────────────────────────┘
```

---

## 📦 Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **API Framework** | FastAPI | 0.138.0 |
| **UI Framework** | Streamlit | 1.35.0 |
| **LLM Engine** | Ollama (qwen3:8b) | Local |
| **Vector DB** | ChromaDB | 0.4.24 |
| **Python** | Python | 3.11+ |
| **Server** | Uvicorn | 0.49.0 |
| **Data Validation** | Pydantic | 2.13.4 |
| **HTTP Client** | Requests | 2.34.2 |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- pip/virtualenv
- Ollama running locally or accessible at `http://localhost:11434`
- Docker (optional, for containerized deployment)

### Installation

#### 1. Clone the Repository
```bash
git clone https://github.com/anujps31/ops-ai-runbook-assistant.git
cd ops-ai-runbook-assistant
```

#### 2. Create Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\Activate.ps1

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 4. Configure Environment
```bash
# Copy example config
cp .env.example .env

# Update .env with your settings
# OLLAMA_BASE_URL=http://localhost:11434
# LOG_LEVEL=INFO
# HOST=0.0.0.0
# PORT=8000
```

#### 5. Start Ollama
```bash
# If not running in Docker
ollama serve

# In another terminal, pull the model
ollama pull qwen3:8b
```

#### 6. Run FastAPI Backend
```bash
python app/main.py
# or with uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 7. Run Streamlit UI (in another terminal)
```bash
cd ui
streamlit run app.py --server.port=8501
```

---

## 🐳 Docker Deployment

### Build and Run with Docker Compose

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f api
docker-compose logs -f ui
```

### Single Container Build

```bash
# Build image
docker build -t ops-ai-runbook:latest .

# Run container (FastAPI only)
docker run -d \
  -p 8000:8000 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -v $(pwd)/data:/app/data \
  --name ops-ai-api \
  ops-ai-runbook:latest

# Access API
curl http://localhost:8000/health
```

---

## 📚 API Endpoints

### Health & Metrics

#### Health Check
```http
GET /health
```
**Response:**
```json
{
  "status": "healthy",
  "service": "OPS AI Runbook Assistant",
  "version": "0.1.0"
}
```

#### Metrics
```http
GET /metrics
```
**Response:**
```json
{
  "status": "ok",
  "app_version": "0.1.0",
  "ollama_url": "http://localhost:11434"
}
```

### Incident Analysis

#### Analyze Incident
```http
POST /api/v1/incidents/analyze
Content-Type: application/json

{
  "incident": "Production API returning 503 errors. Symptoms: customers unable to login, increased latency, multiple pods restarting."
}
```

**Response:**
```json
{
  "success": true,
  "message": "Incident analysis complete",
  "data": {
    "incident_analysis": {
      "severity": "P1",
      "summary": "Critical production incident affecting customer authentication...",
      "root_cause": "Database connection pool exhaustion due to...",
      "confidence_score": "85%",
      "recommended_actions": [
        "Verify database connection limits",
        "Check pod resource allocation"
      ],
      "affected_components": [
        "API Gateway",
        "Authentication Service",
        "Database"
      ],
      "business_impact": "Direct customer impact - login functionality unavailable",
      "investigation_steps": [
        "kubectl get pods -n production",
        "Check database connection metrics"
      ]
    },
    "root_cause": "Detailed root cause analysis...",
    "recommendations": "Step-by-step remediation steps...",
    "execution_time_seconds": 4.52
  }
}
```

---

## 📁 Project Structure

```
ops-ai-runbook-assistant/
├── app/
│   ├── agents/
│   │   ├── incident_agent.py      # Incident classification & analysis
│   │   ├── root_cause_agent.py    # Root cause diagnosis
│   │   ├── recommendation_agent.py # Fix recommendations
│   │   └── orchestrator_agent.py  # Parallel agent orchestration
│   ├── models/
│   │   ├── incident_models.py     # Pydantic incident schemas
│   │   ├── response_models.py     # API response envelopes
│   │   ├── health_models.py       # Health check models
│   │   └── rag_models.py          # RAG data models
│   ├── routes/
│   │   ├── incident.py            # Incident analysis endpoints
│   │   ├── health.py              # Health check endpoints
│   │   ├── rag.py                 # RAG query endpoints
│   │   └── debug.py               # Debug endpoints
│   ├── services/
│   │   ├── llm_service.py         # Ollama LLM integration with retry logic
│   │   ├── chroma_service.py      # ChromaDB vector database
│   │   ├── retrieval_service.py   # RAG retrieval logic
│   │   ├── embedding_service.py   # Embedding generation
│   │   ├── document_loader.py     # Runbook loading
│   │   ├── chunking_service.py    # Document chunking
│   │   ├── rag_service.py         # End-to-end RAG pipeline
│   │   └── text_cleaner.py        # Text preprocessing
│   ├── prompts/
│   │   ├── incident_prompt.py     # Incident analysis prompts
│   │   └── root_cause_prompt.py   # Root cause analysis prompts
│   ├── utils/
│   │   ├── config.py              # Configuration management
│   │   ├── logger.py              # Structured logging
│   │   ├── exceptions.py          # Error handling
│   │   └── response.py            # Response utilities
│   ├── middleware/                # Custom middleware
│   ├── main.py                    # FastAPI application entry point
│   └── config.py                  # Alternative config location
│
├── ui/
│   └── app.py                     # Streamlit dashboard
│
├── data/
│   ├── runbooks/                  # 20+ production runbooks (Markdown)
│   │   ├── crashloopbackoff.md
│   │   ├── pod-oomkilled.md
│   │   ├── database-deadlock.md
│   │   ├── redis-down.md
│   │   ├── kafka-consumer-lag.md
│   │   └── [17 more...]
│   ├── incidents/                 # Sample incident descriptions
│   ├── sops/                      # Standard operating procedures
│   └── chroma/                    # Vector database storage
│
├── scripts/
│   ├── test_orchestrator_agent.py # Agent testing
│   ├── test_rag.py                # RAG pipeline testing
│   ├── test_chromadb.py           # Vector DB testing
│   └── [5 more test scripts]
│
├── tests/
│   └── fixtures/                  # Test fixtures
│
├── docs/                          # Additional documentation
├── .env.example                   # Environment variables template
├── .gitignore                     # Git ignore rules
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Docker container configuration
├── docker-compose.yml             # Multi-container orchestration
└── README.md                      # This file
```

---

## 🔧 Configuration

Create `.env` file in the project root:

```env
# Application
APP_NAME=OPS AI Runbook Assistant
APP_VERSION=0.1.0
LOG_LEVEL=INFO

# External Services
OLLAMA_BASE_URL=http://localhost:11434

# Server
HOST=0.0.0.0
PORT=8000
```

---

## 📊 Knowledge Base

### Included Runbooks (20+)

| Category | Runbooks |
|----------|----------|
| **Kubernetes** | CrashLoopBackOff, ImagePullBackOff, Pod OOMKilled, Node Not Ready |
| **AKS** | AKS Node Pressure, AKS Pod CrashLoopBackOff |
| **Infrastructure** | High CPU Usage, Memory Leak, Disk Full |
| **Networking** | DNS Resolution Failure, Ingress 502 Errors |
| **Databases** | Connection Pool Issues, Deadlocks, Replication Lag |
| **Message Queues** | Kafka Consumer Lag |
| **Cache** | Redis Down |
| **SSL/TLS** | Certificate Expiration |
| **CI/CD** | GitHub Actions Failures, Terraform State Lock |
| **APIs** | API High Latency |

### Vector Database

- **Storage**: ChromaDB (persistent at `data/chroma/`)
- **Embeddings**: Generated from runbook content
- **Retrieval**: Cosine similarity search for relevant runbooks
- **Update**: Automatic on startup if knowledge base changed

---

## 🔄 Agent Orchestration

### Parallel Execution Model

All three agents run in parallel using `ThreadPoolExecutor`:

```python
with ThreadPoolExecutor(max_workers=3) as executor:
    futures = {
        executor.submit(incident_agent.analyze, incident): "incident_analysis",
        executor.submit(root_cause_agent.analyze, incident): "root_cause",
        executor.submit(recommendation_agent.recommend, incident): "recommendations",
    }
```

**Benefits:**
- Reduced total execution time (~60% faster than sequential)
- Independent RAG retrievals per agent perspective
- Fault-tolerant: One agent failure doesn't block others
- Scalable: Can add more agents without sequential overhead

---

## 📈 Performance & Reliability

### Timeout & Retry Strategy

- **Ollama Request Timeout**: 300 seconds (for long LLM generations)
- **Ollama Retry Logic**: 2 automatic retries on timeout
- **Connect Timeout**: 20 seconds
- **Read Timeout**: 300 seconds
- **Fallback**: Returns empty string on persistent failure

### Logging

- **Format**: `[TIMESTAMP] [LEVEL] [MODULE] MESSAGE`
- **Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Output**: Console (configurable via `LOG_LEVEL`)

### Health Checks

**Startup Verification:**
- ✅ Ollama connectivity check
- ✅ ChromaDB availability check
- ✅ Runbook knowledge base validation

**Runtime Monitoring:**
- `/health` endpoint for container orchestrators
- `/metrics` for observability

---

## 🧪 Testing

### Run Tests

```bash
# Test orchestrator agent
python scripts/test_orchestrator_agent.py

# Test RAG pipeline
python scripts/test_rag.py

# Test ChromaDB
python scripts/test_chromadb.py

# Test Ollama LLM
python scripts/test_llm.py

# Test recommendation agent
python scripts/test_recommendation_agent.py
```

---

## 🔐 Security

- **Input Validation**: Pydantic models enforce structure
- **Error Handling**: Comprehensive exception handling without sensitive data exposure
- **Logging**: Sensitive data never logged
- **Environment Variables**: All configs in `.env`
- **CORS**: Configurable for production deployments
- **Rate Limiting**: Implement via reverse proxy (nginx, Traefik)

---

## 📝 Development

### Code Style

- **Python**: 3.11+ compliant
- **Format**: Black, isort
- **Linting**: Pylint, Flake8
- **Type Hints**: Full type annotations

### Adding New Runbooks

1. Create markdown file in `data/runbooks/`
2. Follow the template structure (Problem, Symptoms, Root Causes, etc.)
3. Restart application (or trigger RAG re-indexing)
4. ChromaDB automatically indexes new content

### Adding New Agents

1. Create agent class in `app/agents/`
2. Implement analysis method with RAG retrieval
3. Register in `OrchestratorAgent`
4. Add to ThreadPoolExecutor futures dictionary

---

## 🚨 Troubleshooting

### Ollama Timeout Errors

```
requests.exceptions.ReadTimeout: HTTPConnectionPool... timed out
```

**Solution:**
- Increase `REQUEST_TIMEOUT` in `app/services/llm_service.py`
- Verify Ollama is running: `curl http://localhost:11434/api/tags`
- Check system memory: `free -h` (qwen3:8b requires ~8GB)

### ChromaDB Connection Errors

```
Failed to connect to ChromaDB
```

**Solution:**
- Verify `data/chroma/` directory exists
- Check disk space: `df -h`
- Verify write permissions

### No Runbooks Found

**Solution:**
- Verify runbooks in `data/runbooks/`
- Check `data/chroma/` is populated
- Re-run document loader: `python scripts/test_loader.py`

---

## 📞 Support & Contribution

### Reporting Issues

1. Check existing GitHub issues
2. Provide:
   - Error logs
   - Steps to reproduce
   - Environment details (OS, Python version, etc.)

### Contributing

1. Fork repository
2. Create feature branch: `git checkout -b feature/xyz`
3. Commit changes: `git commit -m "Add xyz"`
4. Push to branch: `git push origin feature/xyz`
5. Open pull request

---

## 📄 License

[Add your license here]

---

## 👨‍💼 Author & Attribution

**Senior SRE, DevOps Architect, Platform Engineer & AIOps Engineer**

Built with production reliability and enterprise operations in mind.

---

## 🔗 References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Ollama Documentation](https://github.com/ollama/ollama)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)

---

**Version**: 0.1.0  
**Last Updated**: 2026-06-24  
**Status**: Production Ready
