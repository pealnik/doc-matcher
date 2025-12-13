import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config, services
from routers import guidelines, tasks

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Context manager for application startup and shutdown events."""
    logger.info("Application startup...")
    # Load existing guidelines from disk and queue any that need processing
    services.load_existing_guidelines()
    yield
    logger.info("Application shutdown...")

# Initialize FastAPI app
app = FastAPI(
    title="PDF Compliance Checker API",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(guidelines.router, prefix="/api", tags=["Guidelines"])
app.include_router(tasks.router, prefix="/api", tags=["Tasks"])

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "PDF Compliance Checker API is running."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
