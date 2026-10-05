Management Model — Hugging Face Docker Space

Deployment architecture

Your current AI runtime uses llama.cpp plus a GGUF Gemma model. The Windows llama-cli executable
cannot be copied into a Linux Hugging Face container, so the Dockerfile builds llama.cpp for Linux
with CUDA support and expects the model at:

/models/gemma-3-1b-it-q4_0.gguf

Use a Hugging Face model volume for the GGUF file, and a persistent Storage Bucket mounted at
/data for the SQLite database.

Space settings

Create the Space with:

SDK: Docker

App port: 7860

GPU hardware for model inference

Hugging Face Docker Spaces use port 7860 by default, and GPU hardware can be selected from the
Space settings. Storage on Spaces is ephemeral unless you attach persistent storage.

Variables

Set these as Space Variables:

ENVIRONMENT=production
DEBUG=0
HOST=0.0.0.0
PORT=7860
CORS_ORIGINS=https://YOUR-SPACE.hf.space
DATABASE_URL=sqlite:////data/management_model.db
LLAMA_CLI=/app/llama.cpp/build/bin/llama-cli
MODEL_PATH=/models/gemma-3-1b-it-q4_0.gguf
GPU_DEVICE=CUDA0
GPU_LAYERS=99
CONTEXT_SIZE=2048
MAX_TOKENS=256
MODEL_TIMEOUT=120

Do not commit .env or secret values to the repository.

Required code changes before final deployment

Make the parser read LLAMA_CLI and MODEL_PATH from environment variables while preserving
the current local defaults.

Make the SQLAlchemy database URL configurable from DATABASE_URL, preserving the current local
SQLite default.

Make the frontend API base URL configurable for production so it does not call localhost.

Serve the built frontend from the production app or deploy the frontend separately. The current
Dockerfile builds frontend/dist, but your FastAPI app still needs to serve that build if you
want one combined Space.

Validation

Run locally first:

pytest -v

Then, on a Linux/CUDA-capable system:

docker build -t management-model .
docker run --gpus all -p 7860:7860 --env-file .env management-model

Verify:

http://localhost:7860/health
http://localhost:7860/dashboard
http://localhost:7860/planner/

Finally, verify a real AI request through the deployed Space.

Final flow

Local 41-test suite
        ↓
Environment-configurable runtime
        ↓
Docker build
        ↓
Hugging Face Docker Space
        ↓
GPU + model volume
        ↓
Persistent /data volume
        ↓
/health
/dashboard
/planner/
/ai/process