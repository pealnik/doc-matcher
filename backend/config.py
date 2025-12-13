import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Environment-based configurations
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ALLOWED_ORIGINS_ENV = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS_ENV.split(",")] if ALLOWED_ORIGINS_ENV else ["*"]

# Directory configurations
UPLOAD_DIR = Path("./uploads")
GUIDELINES_DIR = UPLOAD_DIR / "guidelines" # Now for storing uploaded PDFs (reports)
REPORTS_DIR = UPLOAD_DIR / "reports"
VECTORSTORE_DIR = Path("./vectorstores")
RESULTS_DIR = Path("./results")

# Checklist directory: default to backend/data/guidelines (relative to this file)
# Allow override with CHECKLISTS_DIR env var for flexibility in deployments
CHECKLISTS_DIR_ENV = os.getenv("CHECKLISTS_DIR")
if CHECKLISTS_DIR_ENV:
    CHECKLISTS_DIR = Path(CHECKLISTS_DIR_ENV)
else:
    CHECKLISTS_DIR = Path(__file__).parent / "data" / "guidelines"

# Ensure directories exist
for directory in [GUIDELINES_DIR, REPORTS_DIR, VECTORSTORE_DIR, RESULTS_DIR, CHECKLISTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY not found in environment")
else:
    print(f"✓ OpenAI API key loaded (ends with: ...{OPENAI_API_KEY[-4:]})")
