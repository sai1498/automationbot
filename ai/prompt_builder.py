"""
Optimized prompt templates for AI content generation.
Separates prompt logic from engine logic for maintainability.
"""


REFINEMENT_PROMPT = """
SYSTEM: You are a geopolitical financial content engine.

CONTEXT — ORIGINAL CONTENT:
{original_content}

TASK — USER REVISION REQUEST:
{revision_request}

OUTPUT FORMAT:
Rewrite the content according to the revision instructions.
Stay in the exact same JSON format as the original.
"""

TRANSCRIPTION_PROMPT = (
    "Transcribe this audio file accurately and provide a clear summary "
    "of any geopolitical or financial news mentioned."
)

VISION_ANALYSIS_PROMPT = (
    "Analyze this image and describe the geopolitical or financial event, "
    "data, or news it contains. Provide a comprehensive summary that can "
    "be used to generate social media content."
)

IMAGE_STYLE_SUFFIX = (
    ", cinematic, high-fidelity, financial news aesthetic, "
    "professional photography, 8k"
)
