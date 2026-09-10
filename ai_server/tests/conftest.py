import os

# Settings are intentionally required in production code. Unit tests install
# isolated values before test modules import ai_server.main.
os.environ["DATABASE_URL"] = (
    "postgresql://ai_service:test-password@localhost:5433/ai_service"
)
os.environ["BUILD_SERVER_TOKEN"] = "test-build-server-token-32-characters"
