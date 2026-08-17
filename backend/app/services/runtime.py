from app.core.config import settings
from app.services.ai_advisory_service import AIAdvisoryService

ai_advisory_service = AIAdvisoryService(
    settings.ai_service_url,
    timeout_seconds=settings.ai_timeout_seconds,
    window_seconds=settings.ai_window_seconds,
    min_samples=settings.ai_min_samples,
)
