"""
Content processing pipeline — coordinates the full input → content → media flow.
Integrates caching, job tracking, and parallel processing.
"""

import json
import logging
from datetime import datetime, timezone

from ai.gemini_engine import GeminiEngine
from media.image_engine import ImageEngine
from media.visual_processor import VisualProcessor
from database.models import Job, ContentCache, Analytics, get_session_factory

logger = logging.getLogger(__name__)

_SessionFactory = None


def _get_factory():
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = get_session_factory()
    return _SessionFactory


class ContentPipeline:
    """
    Full content processing pipeline:
    1. Check cache → 2. Generate content → 3. Generate images → 4. Overlay text
    Tracks job status throughout.
    """

    def __init__(self):
        self.engine = GeminiEngine()
        self.image_engine = ImageEngine()
        self.visual_processor = VisualProcessor()

    def process(self, input_text: str, user_id: int, input_type: str = "text") -> dict:
        """
        Run the full pipeline. Returns dict with 'content', 'image_urls', 'job_id'.
        """
        factory = _get_factory()

        # Create job record
        with factory() as db:
            job = Job(
                user_id=user_id,
                status="processing",
                input_type=input_type,
                input_text=input_text[:2000]  # Truncate for storage
            )
            db.add(job)
            db.commit()
            job_id = job.id

        try:
            # 1. Check cache
            content = self._check_cache(input_text)
            if content:
                logger.info(f"📦 Cache hit for job #{job_id}")
                self._update_job(job_id, "generated", content=content)
            else:
                # 2. Generate content
                content = self.engine.generate_content(input_text)
                self._save_cache(input_text, content)
                self._update_job(job_id, "generated", content=content)

            # 3. Generate images (if not community-only)
            final_media_paths = []
            if not content.get("is_community_only") and content.get("image_prompts"):
                logger.info(f"🎨 Generating images for job #{job_id}...")
                base_image_paths = self.image_engine.generate_carousel_images(content["image_prompts"])

                # 4. Overlay text
                if base_image_paths and content.get("carousel_slides"):
                    logger.info(f"✍️ Overlaying text for job #{job_id}...")
                    final_media_paths = self.visual_processor.process_carousel(
                        base_image_paths, content["carousel_slides"]
                    )

            self._update_job(job_id, "generated")
            return {
                "content": content,
                "image_urls": final_media_paths,
                "job_id": job_id
            }

        except Exception as e:
            self._update_job(job_id, "failed", error=str(e))
            raise

    def _check_cache(self, input_text: str) -> dict | None:
        """Check if we've already processed this input."""
        factory = _get_factory()
        input_hash = ContentCache.hash_input(input_text)
        with factory() as db:
            cached = db.query(ContentCache).filter_by(input_hash=input_hash).first()
            if cached:
                return cached.get_content()
        return None

    def _save_cache(self, input_text: str, content: dict):
        """Cache the generated content."""
        factory = _get_factory()
        input_hash = ContentCache.hash_input(input_text)
        with factory() as db:
            entry = ContentCache(
                input_hash=input_hash,
                content_json=json.dumps(content)
            )
            db.add(entry)
            db.commit()

    def _update_job(self, job_id: int, status: str, content: dict = None, error: str = None):
        """Update job status in database."""
        factory = _get_factory()
        with factory() as db:
            job = db.query(Job).filter_by(id=job_id).first()
            if job:
                job.status = status
                if content:
                    job.set_content(content)
                if error:
                    job.error_logs = (job.error_logs or "") + f"\n{error}"
                db.commit()

    def record_publish(self, job_id: int, platform: str, success: bool, details: str = ""):
        """Record a publishing event in analytics."""
        factory = _get_factory()
        with factory() as db:
            analytics = Analytics(
                job_id=job_id,
                platform=platform,
                action="published" if success else "failed",
                details=details
            )
            db.add(analytics)

            # Update job status
            job = db.query(Job).filter_by(id=job_id).first()
            if job and success:
                job.status = "published"
                job.published_at = datetime.now(timezone.utc)
            db.commit()
