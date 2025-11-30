# PDF Compliance Checker

Check if a report PDF complies with a guideline PDF using RAG (Retrieval-Augmented Generation) and LLMs.

## Features

- Handles large PDFs (200+ MB) efficiently with streaming
- RAG-powered analysis using FAISS vector database
- Extracts and analyzes text and tables from PDFs
- Configurable Gemini models for compliance analysis
- Generates detailed compliance reports with specific issues

## Quick Start

```bash
# 1. Setup
./setup.sh

# 2. Configure API keys
cp .env.example .env
# Edit .env and add your API keys

# 3. Run
source venv/bin/activate
python pdf_compliance_checker.py \
    --guideline guideline.pdf \
    --report report.pdf
```

## Installation

### Prerequisites
- Python 3.8+
- OpenAI API key: https://platform.openai.com/api-keys
- Gemini API key: https://makersuite.google.com/app/apikey

### Setup
```bash
./setup.sh
```

Or manually:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root (copy from `.env.example`):

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```bash
# Required
OPENAI_API_KEY=your-openai-api-key-here
GEMINI_API_KEY=your-gemini-api-key-here

# Optional (defaults to gemini-1.5-flash)
GEMINI_MODEL=gemini-1.5-flash
```

**Model Options:**
- `gemini-1.5-flash` - Fast, low cost (default)
- `gemini-1.5-pro` - Better quality, higher cost
- `gemini-2.0-flash-exp` - Experimental, very fast

## Usage

### Basic
```bash
python pdf_compliance_checker.py \
    --guideline guideline.pdf \
    --report report.pdf
```

**Monitor progress in real-time:**
```bash
# In another terminal, watch results as they stream in
tail -f compliance_report.txt
```

### Advanced Options
```bash
python pdf_compliance_checker.py \
    --guideline guideline.pdf \
    --report report.pdf \
    --chunk_pages 4 \
    --output my_report.txt \
    --rebuild_vectorstore \
    --vectorstore_path custom_vectorstore \
    --openai_api_key YOUR_KEY       # Optional: override env var
    --gemini_api_key YOUR_KEY       # Optional: override env var
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--guideline` | Required | Path to guideline PDF |
| `--report` | Required | Path to report PDF to check |
| `--chunk_pages` | `4` | Pages per report chunk |
| `--output` | `compliance_report.txt` | Output file path |
| `--rebuild_vectorstore` | `False` | Force rebuild of vectorstore |
| `--vectorstore_path` | `guideline_vectorstore` | Vectorstore directory |
| `--openai_api_key` | From env | Override OPENAI_API_KEY |
| `--gemini_api_key` | From env | Override GEMINI_API_KEY |

## How It Works

1. **Guideline Processing** (one-time)
   - Extract text/tables from guideline PDF
   - Chunk content (1000 chars, 200 overlap) **with page tracking**
   - Generate embeddings using OpenAI
   - Store in FAISS index with page metadata

2. **Report Analysis** (per chunk)
   - Extract N pages of report
   - Retrieve top-5 relevant guideline sections **with page numbers**
   - Send to Gemini with guideline page references
   - Parse structured response with specific page citations

3. **Output**
   - Compile all results with **guideline page references**
   - Generate detailed report with issues
   - Show both report and guideline page numbers for verification

## Output Format

**Streaming Output:** Results are written incrementally as each chunk is processed. Monitor progress in real-time with `tail -f compliance_report.txt`.

The compliance report follows this format:

```
# PDF Compliance Check Report

Pages 1-4: Compliant.

Pages 5-8: Non-compliant.
  Issues found (2):
    - Page 6: Value exceeds guideline maximum
      Guideline Reference: Page 12: Section 2, Table 1
      Reasoning: The value 15 exceeds maximum of 10 specified on guideline page 12...

============================================================
SUMMARY: Total issues found: 12
Total chunks analyzed: 63
============================================================
```

## Models

### Embedding Model (OpenAI)
- **Model**: `text-embedding-3-small`
- **Purpose**: Convert text to vectors for similarity search
- **Cost**: ~$0.02 per 1M tokens

### LLM Model (Gemini)
Configure via `GEMINI_MODEL` environment variable:

| Model | Speed | Quality | Cost | Best For |
|-------|-------|---------|------|----------|
| `gemini-1.5-flash` | Fast | Good | Low | Large reports, quick checks |
| `gemini-1.5-pro` | Medium | Better | Medium | Complex compliance |
| `gemini-2.0-flash-exp` | Very Fast | Good | Low | Experimental, fastest |

## Performance

### Memory Efficiency
- Page-by-page extraction (no full PDF in memory)
- Streaming processing
- FAISS vectorstore for fast search

### Processing Time
For 250-page, 194 MB report:
- First run: 15-30 min (includes vectorstore build)
- Subsequent: 10-20 min (reuses vectorstore)

## Troubleshooting

### Out of Memory
```bash
python pdf_compliance_checker.py ... --chunk_pages 2
```

### API Rate Limits
Add delays in code or use rate-limited API wrapper

### PDF Extraction Issues
```python
import pdfplumber
pdf = pdfplumber.open("file.pdf")
pdf.pages[0].extract_text()  # Test
```

### Vectorstore Issues
```bash
python pdf_compliance_checker.py ... --rebuild_vectorstore
```

### Check Logs
```bash
tail -f compliance_checker.log
```

## Project Structure

```
doc-match/
├── pdf_compliance_checker.py      # Main script
├── requirements.txt               # Dependencies
├── setup.sh                       # Setup script
├── .env.example                   # Environment variables template
├── .env                           # Your API keys (create from .env.example)
├── .gitignore                     # Git ignore file
├── README.md                      # This file
├── compliance_report.txt          # Generated output
├── compliance_checker.log         # Generated logs
└── guideline_vectorstore/         # Generated FAISS index
```

## Cost Estimates

**OpenAI (embeddings)**:
- Model: text-embedding-3-small
- ~$0.02 per 1M tokens
- 250-page PDF ≈ $0.50-$2.00

**Gemini (LLM)**:
- gemini-1.5-flash: ~$0.075 per 1M input tokens
- 250-page report ≈ $1-$5 (depends on chunk size)

Check current pricing:
- OpenAI: https://openai.com/api/pricing/
- Gemini: https://ai.google.dev/pricing

## License

Provided as-is for compliance checking.
