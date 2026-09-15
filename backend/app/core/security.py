import hashlib
import hmac
import secrets
from datetime import timedelta
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.models import User, now

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    value = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 180000).hex()
    return f'{salt}${value}'


def verify_password(password: str, stored: str) -> bool:
    return hmac.compare_digest(hash_password(password, stored.split('$')[0]), stored)


def issue_token(user: User) -> str:
    return jwt.encode({'sub': user.id, 'exp': now() + timedelta(hours=8), 'iat': now()}, settings.signing_key(), algorithm='HS256')


def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(credentials.credentials, settings.signing_key(), algorithms=['HS256'])
        user = db.get(User, payload['sub'])
        if not user:
            raise ValueError('Unknown user')
        return user
    except (jwt.PyJWTError, ValueError, AttributeError, KeyError):
        raise HTTPException(401, 'Please sign in with your demo account')


def officer(user: User = Depends(current_user)) -> User:
    if user.role not in {'PROCUREMENT_OFFICER', 'ADMIN'}:
        raise HTTPException(403, 'A procurement officer must perform this action')
    return user


def admin(user: User = Depends(current_user)) -> User:
    if user.role != 'ADMIN':
        raise HTTPException(403, 'An administrator must edit tender rules')
    return user
