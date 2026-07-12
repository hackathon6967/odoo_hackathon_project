from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import uuid

from app.shared.db import get_db
from app.shared.auth import get_current_user
from app.modules.core.models import User, Notification

router = APIRouter()


@router.get("/")
async def get_notifications(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    notifs = result.scalars().all()
    return [{"id": str(n.id), "type": n.type, "title": n.title, "body": n.body,
             "is_read": n.is_read, "created_at": n.created_at.isoformat()} for n in notifs]


@router.put("/{notif_id}/read")
async def mark_read(notif_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Notification).where(Notification.id == uuid.UUID(notif_id), Notification.user_id == current_user.id)
    )
    notif = result.scalar_one_or_none()
    if notif:
        notif.is_read = True
    return {"message": "Marked as read"}


@router.put("/read-all")
async def mark_all_read(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Notification).where(Notification.user_id == current_user.id, Notification.is_read == False)
    )
    notifs = result.scalars().all()
    for n in notifs:
        n.is_read = True
    return {"message": f"Marked {len(notifs)} as read"}


@router.get("/unread-count")
async def unread_count(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from sqlalchemy import func
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    )
    return {"count": result.scalar() or 0}
