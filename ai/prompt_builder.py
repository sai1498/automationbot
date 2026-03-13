"""
Optimized prompt templates for AI content generation.
Separates prompt logic from engine logic for maintainability.
"""

SYSTEM_PROMPT = "You are a geopolitical financial content engine."

MAIN_TASK_PROMPT = """
Convert the input news into these formats:
1. LinkedIn post: professional, analytical, institutional tone.
2. Instagram caption: short, emotional, hook-based, trader mindset.
3. Community post: friendly, discussion-driven.
4. 5-Slide Carousel: Enforce < 15 words per slide.
5. 5 Cinematic Image Prompts.
6. Trending Hashtags: 5-10 contextually relevant, high-traffic hashtags.

OUTPUT FORMAT:
Output a JSON object with this structure:
{{
  "is_community_only": {is_community_only},
  "linkedin_post": "...",
  "instagram_caption": "...",
  "community_post": "...",
  "carousel_slides": ["slide 1", ...],
  "image_prompts": ["prompt 1", ...],
  "trending_hashtags": ["#hashtag1", ...]
}}

INPUT NEWS:
{news_input}
"""

COMMUNITY_ONLY_PROMPT = """
[STRICT MODE: COMMUNITY ONLY]
Only generate 'community_post' and 'trending_hashtags'.
Leave all other fields as empty strings or empty lists.

OUTPUT FORMAT:
Output a JSON object with this structure:
{{
  "is_community_only": true,
  "linkedin_post": "",
  "instagram_caption": "",
  "community_post": "...",
  "carousel_slides": [],
  "image_prompts": [],
  "trending_hashtags": ["#hashtag1", ...]
}}

INPUT NEWS:
{news_input}
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
