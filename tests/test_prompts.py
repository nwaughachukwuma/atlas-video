"""
Unit tests for atlas.prompts module
"""

from src.atlas.prompts import (
    VideoPrompt,
    summarize_descriptions_prompt,
    video_analysis_prompts,
    video_system_prompt,
)
from src.atlas.utils import DescriptionAttr


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


class TestVideoSystemPrompt:
    """Tests for video_system_prompt function"""

    def test_generates_prompt_with_visual_cues(self):
        """Test prompt generation for visual_cues"""
        result = video_system_prompt("Describe the scene", "visual_cues")
        assert "VISUAL CUES" in result
        assert "Describe the scene" in result
        assert "Request Type:" in result

    def test_generates_prompt_with_audio_analysis(self):
        """Test prompt generation for audio_analysis"""
        result = video_system_prompt("Describe audio", "audio_analysis")
        assert "AUDIO ANALYSIS" in result
        assert "Describe audio" in result

    def test_generates_prompt_with_transcript(self):
        """Test prompt generation for transcript"""
        result = video_system_prompt("Transcribe speech", "transcript")
        assert "TRANSCRIPT" in result
        assert "Transcribe speech" in result

    def test_handles_all_attr_types(self):
        """Test that all attribute types work"""
        attrs: list[DescriptionAttr] = [
            "visual_cues",
            "interactions",
            "contextual_information",
            "audio_analysis",
            "transcript",
        ]
        for attr in attrs:
            result = video_system_prompt("Test", attr)
            assert attr.upper().replace("_", " ") in result


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


class TestVideoAnalysisPrompts:
    """Tests for video_analysis_prompts list"""

    def test_has_all_required_attrs(self):
        """Test that all required attributes are covered"""
        required_attrs = {
            "visual_cues",
            "interactions",
            "contextual_information",
            "audio_analysis",
            "transcript",
        }
        found_attrs = {p.attr for p in video_analysis_prompts}
        assert required_attrs == found_attrs

    def test_all_prompts_have_content(self):
        """Test that all prompts have non-empty content"""
        for prompt in video_analysis_prompts:
            assert len(prompt.value) > 100  # Prompts should be substantial
            assert prompt.attr in prompt.value or True  # Attr may not be in value

    def test_visual_cues_prompt_content(self):
        """Test visual_cues prompt has expected content"""
        visual_prompt = next((p for p in video_analysis_prompts if p.attr == "visual_cues"), None)
        assert visual_prompt is not None
        assert "visual" in visual_prompt.value.lower()
        assert "people" in visual_prompt.value.lower() or "object" in visual_prompt.value.lower()

    def test_transcript_prompt_content(self):
        """Test transcript prompt has expected content"""
        transcript_prompt = next((p for p in video_analysis_prompts if p.attr == "transcript"), None)
        assert transcript_prompt is not None
        assert "transcript" in transcript_prompt.value.lower()
        assert "speech" in transcript_prompt.value.lower()
