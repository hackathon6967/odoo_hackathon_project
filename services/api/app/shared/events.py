import asyncio
import json
import logging
from typing import Any, Callable, Dict, List
from dataclasses import dataclass, field
import redis
import os

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# In-process subscriber registry
_subscribers: Dict[str, List[Callable]] = {}


def subscribe(event_type: str):
    """Register a handler for an event type (as a decorator)."""
    def decorator(handler: Callable):
        if event_type not in _subscribers:
            _subscribers[event_type] = []
        _subscribers[event_type].append(handler)
        return handler
    return decorator


async def publish(event_type: str, payload: Dict[str, Any]):
    """Publish an event to all registered in-process handlers."""
    handlers = _subscribers.get(event_type, [])
    for handler in handlers:
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(payload)
            else:
                handler(payload)
        except Exception as e:
            logger.error(f"Event handler error for {event_type}: {e}")

    # Also push to Redis for worker jobs
    try:
        r = redis.from_url(REDIS_URL)
        await asyncio.to_thread(
            r.lpush,
            f"ecosphere:events:{event_type}",
            json.dumps({"type": event_type, "payload": payload})
        )
        await asyncio.to_thread(r.expire, f"ecosphere:events:{event_type}", 3600)
    except Exception as e:
        logger.warning(f"Failed to push event to Redis: {e}")


# ── Event type constants ──────────────────────────────────────────────────────
COMPLIANCE_ISSUE_RAISED = "compliance_issue.raised"
PARTICIPATION_DECISION = "participation.decision"
CHALLENGE_PARTICIPATION_DECISION = "challenge_participation.decision"
POLICY_REMINDER = "policy.reminder"
BADGE_UNLOCKED = "badge.unlocked"
REWARD_REDEEMED = "reward.redeemed"
SCORE_RECOMPUTE_REQUESTED = "score.recompute_requested"
REPORT_GENERATION_REQUESTED = "report.generation_requested"

async def trigger_score_recompute(period: str = None):
    """Dynamically trigger ESG score recomputation when new logs are added."""
    from rq import Queue
    from datetime import datetime, timezone
    if not period:
        period = datetime.now(timezone.utc).strftime("%Y-%m")
    try:
        r = redis.from_url(REDIS_URL)
        q = Queue("ecosphere", connection=r)
        await asyncio.to_thread(q.enqueue, "worker.compute_scores", period)
    except Exception as e:
        logger.warning(f"Failed to trigger score recompute: {e}")
