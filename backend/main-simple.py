"""
Simple FastAPI backend for testing - minimal dependencies
"""

from fastapi import FastAPI
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="Git Review Assistant API",
    description="AI-powered code review system (Simple Version)",
    version="1.0.0"
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Git Review Assistant API is running!"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0-simple",
        "python_version": "3.13"
    }

@app.get("/test")
async def test_endpoint():
    """Test endpoint to verify API is working"""
    return {
        "message": "API is working correctly!",
        "environment": os.getenv("DEBUG", "not set")
    }

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main-simple:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )