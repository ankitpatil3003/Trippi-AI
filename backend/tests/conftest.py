import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Hermetic defaults. A developer .env with LLM_PROVIDER=openrouter and a real key
# would otherwise make every graph test hit the live API, which is slow, costs
# money, and fails offline. os.environ takes precedence over .env in
# pydantic-settings, so assigning here overrides whatever .env holds.
# Individual test modules may still override these before importing app code.
os.environ["LLM_PROVIDER"] = "heuristic"
os.environ.setdefault("MCP_STUB", "true")
os.environ.setdefault("RESEARCH_MCP_STUB", "true")
os.environ.setdefault("DINING_MCP_STUB", "true")
os.environ.setdefault("RESEARCH_MCP_URL", "")
os.environ.setdefault("DINING_MCP_URL", "")
