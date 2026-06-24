# Quick Start Guide

Get OPS AI Runbook Assistant running in 5 minutes.

## Prerequisites

- Python 3.11+
- Git
- Ollama (or Docker)

---

## Option 1: Local Development (Fastest)

### 1. Clone & Setup
```bash
# Clone repository
git clone https://github.com/your-org/ops-ai-runbook-assistant.git
cd ops-ai-runbook-assistant

# Create virtual environment
python -m venv .venv

# Activate venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Start Ollama
```bash
# Option A: If installed locally
ollama serve

# In another terminal
ollama pull qwen3:8b
```

### 3. Run Backend (Terminal 1)
```bash
python app/main.py
# Or: uvicorn app.main:app --reload
```

### 4. Run UI (Terminal 2)
```bash
cd ui
streamlit run app.py
```

### 5. Access & Test
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **UI**: http://localhost:8501

**Test**: Submit "Database connection pool exhaustion" in the UI

---

## Option 2: Docker Compose (Recommended)

### 1. One Command Start
```bash
docker-compose up -d
```

### 2. Initialize Model
```bash
docker-compose exec ollama ollama pull qwen3:8b
```

### 3. Access Services
- **API**: http://localhost:8000
- **UI**: http://localhost:8501
- **Ollama**: http://localhost:11434

### 4. View Logs
```bash
docker-compose logs -f
```

---

## First Analysis

### Via API (cURL)
```bash
curl -X POST http://localhost:8000/api/v1/incidents/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "incident": "Production API returning 503 errors. Symptoms: customers unable to login, increased latency, multiple pods restarting."
  }'
```

### Via Streamlit UI
1. Open http://localhost:8501
2. Select or enter incident description
3. Click "Analyze Incident"
4. View severity, root cause, and recommendations

---

## Check Health

```bash
# Health check
curl http://localhost:8000/health

# Metrics
curl http://localhost:8000/metrics

# API docs
open http://localhost:8000/docs
```

---

## Common Issues

| Issue | Solution |
|-------|----------|
| Ollama timeout | Increase `REQUEST_TIMEOUT` to 600 in `app/services/llm_service.py` |
| Port already in use | Change port in `.env` or `docker-compose.yml` |
| Out of memory | Increase Docker memory limit or reduce model size |
| ChromaDB not found | Ensure `data/chroma/` directory exists |
| No runbooks loaded | Run `python scripts/test_loader.py` |

---

## Next Steps

1. **Read Documentation**
   - [README.md](README.md) - Full project overview
   - [DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment guide

2. **Explore Code**
   - `app/agents/` - AI agent implementations
   - `app/services/` - Core services (RAG, LLM, etc.)
   - `app/routes/` - API endpoints
   - `data/runbooks/` - Knowledge base

3. **Add Runbooks**
   - Create `data/runbooks/yourrunbook.md`
   - Follow template in existing runbooks
   - Restart FastAPI to re-index

4. **Customize UI**
   - Edit `ui/app.py`
   - Add your incidents in sample list
   - Deploy with `streamlit run`

5. **Deploy to Production**
   - Follow [DEPLOYMENT.md](DEPLOYMENT.md)
   - Use docker-compose or Kubernetes
   - Setup monitoring and alerts

---

## Key Commands

```bash
# Development
python app/main.py              # Start API
streamlit run ui/app.py         # Start UI
python scripts/test_*.py        # Run tests

# Docker
docker-compose up -d            # Start all services
docker-compose down             # Stop all services
docker-compose logs -f          # View logs
docker build -t ops-ai .        # Build image

# API Testing
curl http://localhost:8000/health
curl http://localhost:8000/docs
```

---

## Architecture

```
User Interface (Streamlit)
         ↓
   FastAPI Backend
         ↓
    Orchestrator Agent
    ├─ Incident Agent    ┐
    ├─ Root Cause Agent  ├─ Parallel Execution
    └─ Recommendation    ┘
         ↓
    RAG Pipeline
         ↓
    ChromaDB (Runbooks)
         ↓
    Ollama LLM
```

---

## Support

- **Issues**: Check GitHub issues
- **Docs**: See README.md and DEPLOYMENT.md
- **Logs**: Check output and `uvicorn` logs
- **Debug**: Set `LOG_LEVEL=DEBUG` in `.env`

---

**Ready to go!** Start with Option 1 or 2 above. 🚀
