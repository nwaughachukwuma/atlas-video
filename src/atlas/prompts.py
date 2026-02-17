"""
Prompts for video analysis
"""

from dataclasses import dataclass

from atlas.utils import DescriptionAttr


@dataclass
class VideoPrompt:
    """Video analysis prompt"""

    value: str
    attr: DescriptionAttr

    def __str__(self) -> str:
        return self.value


def video_system_prompt(req_prompt: str, attr: DescriptionAttr) -> str:
    """Generate system prompt for video analysis"""
    return f"""You are an advanced language model able to provide a concise and accurate description of a video (or audio) based on its content and overall makeup.
    Your task is to generate a highly detailed and semantically rich, clear and precise 240 characters description of the video (or audio) capturing the main points and key details, based the following:

    Request:
        - Request Type: {" ".join(attr.upper().split("_"))}
        - Request Instruction:{req_prompt}

    Important Information:
        - Be exhaustive in capturing discriminative visual, auditory, textual or contextual signals.
        - Use precise, concrete language: name objects and people, describe colors/textures/materials, quantify movements, specify spatial relationships, and label emotional tones.
        - Anchor key observations within 3 seconds window. If something evolves, describe its trajectory or change.
        - Base your description on whether the Request Type is visual cues, interactions, contextual information, or audio analysis.
        - Focus and Taylor your description around the Request Instruction.
        - If the Request Type is audio analysis provide only the audio description and ignore visuals entirely.
        - Keep the description to 240 characters or less.
        - Focus on WHAT IS HAPPENING and HOW it's happening, not just what objects are present.
        - For instructional, creative, or process-oriented content, prioritize describing techniques, methods, and progressive changes.

    Instructional Content (when applicable):
        - Describe PROCESSES and TECHNIQUES, not just objects
        - Track PROGRESSION and DEVELOPMENT over time
        - Use instructional language: "the instructor demonstrates...", "next, apply..."
        - Identify STEPS that build on each other sequentially
        - Note any specialized tools, materials, or methods being used

    Note: No preambles, just the summary/description.
    """


def summarize_descriptions_prompt(video_descriptions: str) -> str:
    """Generate prompt for summarizing video descriptions"""
    return f"""You're an advanced language model tasked with summarizing a collection of video descriptions comprising the audio analysis, visual cues, contextual information, transcript and interactions.
    
    You will provide one paragraph summary capturing major details and preserving the underlying information and context.

    Your summary must be highly detailed, temporally anchored, and semantically rich, clear and precise.

    The Video Descriptions:
    {video_descriptions}

    Provide no preambles, just the summary.
    """


video_analysis_prompts: list[VideoPrompt] = [
    VideoPrompt(
        """Describe key visual elements and every visible entity (people, objects, animals, structures) by name (John Doe | Qatar National Museum | A Zebra), appearance (color, texture, size, clothing, posture), location, motion trajectory, and notable attributes/states.
        - Example: 'A man (probably JENSEN Huang) in a blue NVIDIA-branded shirt, seated cross-legged, gesturing with right hand, against red curtain, lit from front-left', 'A brown cat (ginger tabby, short-haired) perched on a wooden windowsill, tail curled around paws, gazing outward through slightly open glass panes'.
        - List key entities, their attributes, and salient visual features.
        - For creative/instructional content: describe the WORK BEING CREATED or MODIFIED and how it changes or evolves during throughout
        - For demonstrations or tutorials: identify tools, materials, and supplies being used or prepared
        - Track visible changes, progressions, or developments in the scene e.g., "canvas transitions from blank white to having blue wash in upper portion"
        - Note spatial composition and how elements are positioned or arranged""",
        "visual_cues",
    ),
    VideoPrompt(
        """Analyze the dynamic interactions: describe movements, spatial relationships, gestures, facial expressions, body language, object manipulations, and interpersonal dynamics. 
        - Describe how the relationships between entities evolve throughout the video. Example: 'Person A (Probably John Doe) approaches Person B (Probably Adam Smith) who turns away, and then smiles'.
        - Describe motion vectors, gaze direction, gestures, emotional expressions, proximity changes, and implied intent between subjects, or gestures, and physical actions being performed
        - For instructional or creative content: explain WHAT IS BEING DONE and HOW it's being done (specific techniques, methods, or steps being demonstrated)
        - Identify cause-and-effect relationships e.g., "applying pressure causes the paint to spread"
        - Describe interactions between people, or between people and objects/materials
        - For processes: note sequential actions that build toward an outcome (e.g., "first applies base layer, then blends edges while still wet")
        """,
        "interactions",
    ),
    VideoPrompt(
        """Detail production elements: camera movements (pan, zoom, static), scene transitions, overlays (text, logos, graphics), lighting conditions (bright, dim, dramatic shadows), weather, time of day, indoor/outdoor setting, background ambiance, and overall mood/atmosphere. 
        - Capture stylistic choices (e.g., slow-mo, color grading). Detail lighting quality (e.g., "stage spotlight"), environment context (e.g., "red velvet curtain backdrop"), camera framing, transitions, overlays, or production artifacts.
        - Framing and composition choices (close-up, wide shot, over-the-shoulder, etc.)
        - Scene changes or shifts in location/setting, and Background elements that provide context
        - Setting and atmosphere: indoor/outdoor, formal/casual, studio/on-location
        - Overall mood or tone conveyed through visual styling
        """,
        "contextual_information",
    ),
    VideoPrompt(
        """Describe the audio class and characteristics: speech (speaker identity, emotion, clarity), music (genre, tempo, instrumentation, key), sound effects (type, source, intensity), and ambient noise (crowd, wind, machinery). 
        - Describe acoustic qualities (reverb, distortion, volume shifts) and how they contribute to mood or narrative. 
        - Capture the tonality, rhythm, pace, instrumentation, emotional tone, acoustic traits and speaker characteristics.
        """,
        "audio_analysis",
    ),
    VideoPrompt(
        """Provide a verbatim and precise transcript of the spoken content in the video.
        - Capture every word spoken exactly as said, including filler words (um, uh, like)
        - Note multiple speakers if present (e.g., "Speaker 1: ...", "Speaker 2: ...")
        - Include significant pauses with [pause]
        - Mark inaudible portions with [inaudible]
        - Preserve the natural flow and any grammatical irregularities
        - Do not add punctuation or formatting beyond what's necessary for readability
        
        If there is no speech in this segment, respond with: [No speech detected]""",
        "transcript",
    ),
]
