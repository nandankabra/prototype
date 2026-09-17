from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import current_user
from app.models import VerificationSource
from app.repositories.review_repository import serialize

router = APIRouter(prefix='/api/verification-sources', tags=['verification sources'])


@router.get('')
def sources(db: Session = Depends(get_db), user=Depends(current_user)):
    return [serialize(row) for row in db.scalars(select(VerificationSource).where(VerificationSource.enabled.is_(True)).order_by(VerificationSource.priority))]
