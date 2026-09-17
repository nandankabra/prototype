from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import current_user, issue_token, verify_password, hash_password
from app.models import User
from app.schemas import LoginRequest, RegistrationRequest
from app.repositories.review_repository import serialize

router = APIRouter(prefix='/api/auth', tags=['auth'])


def session_response(user):
    return {'access_token': issue_token(user), 'token_type': 'bearer', 'user': serialize(user, ('password_hash',))}


@router.post('/login')
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower().strip()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, 'Invalid email or password')
    return session_response(user)


@router.post('/register', status_code=201)
def register_bidder(body: RegistrationRequest, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, 'An account with this email already exists')
    user = User(email=email, name=body.name.strip(), role='BIDDER', password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    return session_response(user)


@router.get('/me')
def me(user=Depends(current_user)):
    return serialize(user, ('password_hash',))
