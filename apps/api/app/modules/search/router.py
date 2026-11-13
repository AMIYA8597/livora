"""
Search & Discovery Router
REST endpoints for PostGIS radius discovery, property search, and flatmate search.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token
from app.modules.search.schemas import (
    PropertySearchFilter,
    PropertySearchResultItem,
    FlatmateSearchFilter,
    FlatmateSearchResultItem,
)
from app.modules.search.service import SearchService

router = APIRouter(prefix="/search", tags=["Search & Geospatial Discovery"])

@router.post("/properties", response_model=List[PropertySearchResultItem])
async def search_properties(
    filters: PropertySearchFilter,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    is_authenticated = False
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        payload = decode_token(token)
        if payload:
            is_authenticated = True

    service = SearchService(db)
    return await service.search_properties(filters, is_authenticated_viewer=is_authenticated)

@router.post("/flatmates", response_model=List[FlatmateSearchResultItem])
async def search_flatmates(
    filters: FlatmateSearchFilter,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    current_user_id = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        payload = decode_token(token)
        if payload and "sub" in payload:
            try:
                from uuid import UUID
                current_user_id = UUID(payload["sub"])
            except Exception:
                pass

    service = SearchService(db)
    return await service.search_flatmates(filters, current_user_id=current_user_id)
