from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import require_roles, get_current_user
from app.core.security import decode_token
from app.core.exceptions import NotFoundException
from app.modules.users.models import User
from app.modules.properties.schemas import (
    PropertyResponse,
    PropertyCreate,
    PropertyUpdate,
    ListingStatusUpdate,
    AssignOccupantRequest,
    BedResponse,
)
from app.modules.properties.service import PropertyService
from app.modules.billing.service import feature_listing

router = APIRouter(prefix="/properties", tags=["Properties"])

@router.get("", response_model=List[PropertyResponse], include_in_schema=False)
@router.get("/", response_model=List[PropertyResponse])
async def list_properties(
    city: Optional[str] = Query(None, description="Filter by city name"),
    min_rent: Optional[Decimal] = Query(None, description="Minimum monthly rent in INR"),
    max_rent: Optional[Decimal] = Query(None, description="Maximum monthly rent in INR"),
    property_category: Optional[str] = Query(None, description="apartment, pg, independent_house, hostel, co_living"),
    configuration: Optional[str] = Query(None, description="1RK, 1BHK, 2BHK, 3BHK, 4BHK_plus, studio"),
    bedrooms: Optional[int] = Query(None, description="Minimum bedrooms"),
    q: Optional[str] = Query(None, max_length=300, description="Free text, e.g. 'quiet furnished room near Indiranagar metro'. Results are ordered by relevance."),
    locality: Optional[str] = Query(None, max_length=100, description="Locality name contained in the listing's public address"),
    furnishing_status: Optional[str] = Query(None, description="fully_furnished, semi_furnished, unfurnished"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    service = PropertyService(db)
    return await service.list_properties(
        q=q,
        locality=locality,
        furnishing_status=furnishing_status,
        city=city,
        min_rent=min_rent,
        max_rent=max_rent,
        property_category=property_category,
        configuration=configuration,
        bedrooms=bedrooms,
        limit=limit,
        offset=offset
    )

@router.post("", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    data: PropertyCreate,
    current_user: User = Depends(require_roles(["owner", "pg_operator", "broker", "admin", "super_admin"])),
    db: AsyncSession = Depends(get_db),
):
    service = PropertyService(db)
    return await service.create(current_user.id, data)

@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: UUID,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    viewer_id = None
    is_admin = False
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        payload = decode_token(token)
        if payload and "sub" in payload:
            try:
                viewer_id = UUID(payload["sub"])
                roles = payload.get("app_metadata", {}).get("roles", [])
                if "admin" in roles or "super_admin" in roles:
                    is_admin = True
            except Exception:
                pass

    service = PropertyService(db)
    prop = await service.get_by_id(property_id, viewer_id=viewer_id, is_admin=is_admin)
    if not prop:
        raise NotFoundException("Property not found")
    return prop

@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: UUID,
    data: PropertyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_admin = current_user.role in ["admin", "super_admin"]
    service = PropertyService(db)
    return await service.update(property_id, current_user.id, data, is_admin=is_admin)

@router.patch("/{property_id}/status", response_model=PropertyResponse)
async def update_property_listing_status(
    property_id: UUID,
    data: ListingStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_admin = current_user.role in ["admin", "super_admin"]
    service = PropertyService(db)
    return await service.update_listing_status(property_id, current_user.id, data.listing_status, is_admin=is_admin)

@router.post("/{property_id}/feature", response_model=PropertyResponse)
async def feature_property(
    property_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Owner Pro: show this listing first in search until the owner's paid period ends."""
    await feature_listing(db, current_user.id, property_id, on=True)
    return await PropertyService(db).get_by_id(property_id, viewer_id=current_user.id)


@router.delete("/{property_id}/feature", response_model=PropertyResponse)
async def unfeature_property(
    property_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await feature_listing(db, current_user.id, property_id, on=False)
    return await PropertyService(db).get_by_id(property_id, viewer_id=current_user.id)


@router.post("/beds/{bed_id}/assign", response_model=BedResponse)
async def assign_bed(
    bed_id: UUID,
    data: AssignOccupantRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_admin = current_user.role in ["admin", "super_admin"]
    service = PropertyService(db)
    return await service.assign_bed_occupant(bed_id, data.occupant_id, current_user.id, is_admin=is_admin)

@router.post("/beds/{bed_id}/vacate", response_model=BedResponse)
async def vacate_bed(
    bed_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_admin = current_user.role in ["admin", "super_admin"]
    service = PropertyService(db)
    return await service.vacate_bed(bed_id, current_user.id, is_admin=is_admin)
