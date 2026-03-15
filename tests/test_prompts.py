"""
Unit tests for atlas.prompts module
"""

from src.atlas.prompts import (
    VideoPrompt,
    summarize_descriptions_prompt,
)


class TestVideoPrompt:
    """Tests for VideoPrompt dataclass"""

    def test_creates_prompt(self):
        """Test VideoPrompt creation"""
        prompt = VideoPrompt(value="Test prompt", attr="visual_cues")
        assert prompt.value == "Test prompt"
        assert prompt.attr == "visual_cues"

    def test_str_returns_value(self):
        """Test that __str__ returns the value"""
        prompt = VideoPrompt(value="Test prompt", attr="visual_cues")
        assert str(prompt) == "Test prompt"


class TestSummarizeDescriptionsPrompt:
    """Tests for summarize_descriptions_prompt function"""

    def test_generates_summary_prompt(self):
        """Test that summary prompt is generated"""
        descriptions = "Video description 1\nVideo description 2"
        result = summarize_descriptions_prompt(descriptions)
        assert "summarizing a collection" in result
        assert descriptions in result
        assert "no preambles" in result.lower()

    def test_includes_all_content(self):
        """Test that all content is included"""
        descriptions = "VISUAL CUES: Test\nINTERACTIONS: Test2"
        result = summarize_descriptions_prompt(descriptions)
        assert "VISUAL CUES: Test" in result
        assert "INTERACTIONS: Test2" in result
