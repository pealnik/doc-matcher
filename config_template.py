"""
Configuration Template for PDF Compliance Checker

Copy this file to 'config.py' and customize settings for your use case.
Then modify pdf_compliance_checker.py to import these settings.
"""

# ============================================================================
# PDF EXTRACTION SETTINGS
# ============================================================================

PDF_EXTRACTION = {
    # Character encoding for text extraction
    "encoding": "utf-8",

    # Whether to extract images from PDFs (requires additional dependencies)
    "extract_images": False,

    # Table extraction settings
    "table_settings": {
        "vertical_strategy": "lines",  # "lines", "text", "explicit"
        "horizontal_strategy": "lines",
        "snap_tolerance": 3,
    }
}

# ============================================================================
# RAG (Retrieval-Augmented Generation) SETTINGS
# ============================================================================

RAG_SETTINGS = {
    # Text chunking parameters
    "chunk_size": 1000,  # Characters per chunk
    "chunk_overlap": 200,  # Overlap between chunks

    # Embedding model (OpenAI - cloud-based, no local processing)
    "embedding_model": "text-embedding-3-small",
    # Alternatives:
    # - "text-embedding-3-large"  # More accurate, more expensive
    # - "text-embedding-ada-002"  # Legacy model

    # Number of guideline chunks to retrieve per report chunk
    "retrieval_k": 5,  # Increase for more context, decrease for speed

    # Vectorstore settings
    "vectorstore_path": "guideline_vectorstore",
    "vectorstore_type": "faiss",  # Currently only FAISS supported
}

# ============================================================================
# LLM (Gemini) SETTINGS
# ============================================================================

LLM_SETTINGS = {
    # Model selection
    "model_name": "gemini-1.5-flash",
    # Alternatives:
    # - "gemini-1.5-pro"  # More capable, slower, more expensive
    # - "gemini-1.0-pro"  # Faster, cheaper, less capable

    # Generation parameters
    "temperature": 0.1,  # Lower = more deterministic, higher = more creative
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 2048,

    # Safety settings (adjust if getting blocked responses)
    "safety_settings": {
        "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
        "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
        "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
    },

    # Rate limiting
    "requests_per_minute": 60,
    "retry_attempts": 3,
    "retry_delay": 2,  # seconds
}

# ============================================================================
# COMPLIANCE CHECKING SETTINGS
# ============================================================================

COMPLIANCE_SETTINGS = {
    # Report chunk size (pages)
    "chunk_pages": 4,

    # Compliance categories
    "compliance_levels": ["compliant", "non-compliant", "partial"],

    # Custom prompt template (optional - overrides default)
    "custom_prompt_template": None,
    # Example custom template:
    """
    You are an expert compliance auditor specializing in [YOUR DOMAIN].

    Guidelines: {guideline_context}
    Report (Pages {start_page}-{end_page}): {report_chunk}

    Analyze for compliance with emphasis on:
    1. Numerical thresholds and limits
    2. Required documentation elements
    3. Format and structure requirements

    Return JSON: {{"compliance": "compliant/non-compliant/partial", "issues": [...]}}
    """,

    # Issue severity levels (for future enhancement)
    "severity_levels": {
        "critical": "Fundamental requirement violation",
        "major": "Important requirement not met",
        "minor": "Recommended practice not followed",
    }
}

# ============================================================================
# OUTPUT SETTINGS
# ============================================================================

OUTPUT_SETTINGS = {
    # Output file path
    "default_output_path": "compliance_report.txt",

    # Output format
    "format": "text",  # "text", "markdown", "html", "json"

    # Include detailed reasoning in output
    "include_reasoning": True,

    # Include retrieved guideline chunks in output
    "include_guideline_context": False,

    # Generate summary statistics
    "generate_summary": True,

    # Color output in terminal (requires colorama)
    "colored_output": False,
}

# ============================================================================
# LOGGING SETTINGS
# ============================================================================

LOGGING_SETTINGS = {
    # Log level
    "level": "INFO",  # DEBUG, INFO, WARNING, ERROR, CRITICAL

    # Log file
    "log_file": "compliance_checker.log",

    # Log format
    "format": "%(asctime)s - %(levelname)s - %(message)s",

    # Log to console
    "console_output": True,

    # Log file rotation
    "max_bytes": 10485760,  # 10MB
    "backup_count": 3,
}

# ============================================================================
# PERFORMANCE SETTINGS
# ============================================================================

PERFORMANCE_SETTINGS = {
    # Enable caching
    "enable_cache": True,

    # Cache directory
    "cache_dir": ".cache",

    # Parallel processing (for future enhancement)
    "max_workers": 4,

    # Memory limits
    "max_memory_mb": 4096,

    # Batch processing
    "batch_size": 10,  # Process N chunks before writing intermediate results
}

# ============================================================================
# DOMAIN-SPECIFIC SETTINGS
# ============================================================================

# Customize these for your specific compliance domain

DOMAIN_SETTINGS = {
    # Financial compliance
    "financial": {
        "focus_areas": ["regulatory requirements", "risk thresholds", "reporting standards"],
        "key_indicators": ["capital ratios", "liquidity metrics", "disclosure requirements"],
    },

    # Healthcare compliance
    "healthcare": {
        "focus_areas": ["patient safety", "privacy regulations", "quality standards"],
        "key_indicators": ["HIPAA compliance", "accreditation standards", "reporting requirements"],
    },

    # Environmental compliance
    "environmental": {
        "focus_areas": ["emission limits", "waste management", "safety protocols"],
        "key_indicators": ["pollutant levels", "permit compliance", "incident reporting"],
    },

    # Quality management
    "quality": {
        "focus_areas": ["ISO standards", "process controls", "documentation"],
        "key_indicators": ["defect rates", "audit findings", "corrective actions"],
    },

    # Default/Generic
    "default": {
        "focus_areas": ["requirements", "thresholds", "standards"],
        "key_indicators": ["compliance metrics", "violations", "gaps"],
    }
}

# Active domain (change to match your use case)
ACTIVE_DOMAIN = "default"

# ============================================================================
# EXPERIMENTAL FEATURES
# ============================================================================

EXPERIMENTAL = {
    # Use multiple LLM models for cross-validation
    "multi_model_validation": False,
    "validation_models": ["gemini-1.5-flash", "gemini-1.5-pro"],

    # Generate explanatory visualizations
    "generate_visualizations": False,

    # Automated report generation
    "auto_generate_summary_report": False,

    # Email notifications (requires email configuration)
    "email_notifications": False,
    "notification_recipients": [],
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_domain_config(domain: str = None):
    """Get domain-specific configuration."""
    domain = domain or ACTIVE_DOMAIN
    return DOMAIN_SETTINGS.get(domain, DOMAIN_SETTINGS["default"])


def get_full_config():
    """Get complete configuration as a dictionary."""
    return {
        "pdf_extraction": PDF_EXTRACTION,
        "rag": RAG_SETTINGS,
        "llm": LLM_SETTINGS,
        "compliance": COMPLIANCE_SETTINGS,
        "output": OUTPUT_SETTINGS,
        "logging": LOGGING_SETTINGS,
        "performance": PERFORMANCE_SETTINGS,
        "domain": get_domain_config(),
        "experimental": EXPERIMENTAL,
    }


def print_config():
    """Print current configuration."""
    import json
    config = get_full_config()
    print(json.dumps(config, indent=2))


if __name__ == "__main__":
    print("Configuration Template")
    print("=" * 60)
    print_config()
