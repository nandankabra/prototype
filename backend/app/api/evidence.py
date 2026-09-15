"""Focused read endpoints for independently inspectable pipeline outputs."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import current_user
from app.api.bids import get_bid
from app.repositories.review_repository import review

router = APIRouter(prefix='/api')


@router.get('/extraction/{bid_id}', tags=['extraction'])
def extraction(bid_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    result = review(db, get_bid(db, bid_id))
    return {'run_id': result['current_run_id'], 'documents': result['documents'], 'entities': result['entities']}


@router.get('/verification/{bid_id}', tags=['verification'])
def verification(bid_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    result = review(db, get_bid(db, bid_id))
    return {'run_id': result['current_run_id'], 'verifications': result['verifications'], 'is_mock': True}


@router.get('/compliance/{bid_id}', tags=['compliance'])
def compliance(bid_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    result = review(db, get_bid(db, bid_id))
    return {'run_id': result['current_run_id'], 'rules': result['compliance'],
            'score': result['risk']['compliance'] if result['risk'] else None}


@router.get('/risk/{bid_id}', tags=['risk'])
def risk(bid_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    result = review(db, get_bid(db, bid_id))
    return {'run_id': result['current_run_id'], 'risk': result['risk']}


@router.get('/ai/{bid_id}', tags=['ai'])
def ai(bid_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    result = review(db, get_bid(db, bid_id))
    return {'run_id': result['current_run_id'], 'recommendation': result['ai'], 'advisory_only': True}
