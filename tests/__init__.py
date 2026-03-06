"""
Tests for Atlas - Multimodal Video Understanding
"""

import os

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-api-key")
os.environ.setdefault("GROQ_API_KEY", "test-groq-api-key")
