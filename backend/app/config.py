"""
Global configuration — loads .env and configures the corporate proxy
before any outbound network calls are made.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Corporate proxy (must be set before any LLM / HTTP client init) ──
PROXY = "http://webproxystatic-on.tsl.telus.com:8080"
os.environ["http_proxy"]  = PROXY
os.environ["HTTP_PROXY"]  = PROXY
os.environ["https_proxy"] = PROXY
os.environ["HTTPS_PROXY"] = PROXY

# ── Supabase ─────────────────────────────────────────────────────────
SUPABASE_URL: str  = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str  = os.getenv("SUPABASE_KEY", "")
BUCKET_NAME:  str  = os.getenv("BUCKET_NAME", "clearinghouse-resources")

# ── Fuelix / LLM ─────────────────────────────────────────────────────
FUELIX_API_KEY: str = os.getenv("FUELIX_API_KEY", "")
BASE_URL:       str = os.getenv("BASE_URL", "https://api-beta.fuelix.ai/v1")
MODEL_NAME:     str = os.getenv("MODEL_NAME", "gemini-3-flash-preview")
# ── Google AI Studio (OpenAI-compatible) ───────────────────────
GOOGLE_API_KEY:  str = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_BASE_URL: str = os.getenv("GOOGLE_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
GOOGLE_MODEL:    str = os.getenv("GOOGLE_MODEL_NAME", "gemini-3-flash-preview")

# ── Provider switch ───────────────────────────────────────────
# Set LLM_PROVIDER in .env to switch between providers.
# Accepted values: "fuelix" (default) | "google"
LLM_PROVIDER:    str = os.getenv("LLM_PROVIDER", "fuelix")