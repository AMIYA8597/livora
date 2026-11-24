from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, Header, Response, status
from pydantic import BaseModel, Field
from typing import Literal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import require_roles, get_current_user, get_optional_user
from app.core.security import decode_token
from app.core.exceptions import BadRequestException, NotFoundException
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
    viewer: Optional[User] = Depends(get_optional_user),
    near_lat: Optional[float] = Query(None, ge=-90, le=90, description="With near_lng: only listings near this point, nearest first"),
    near_lng: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: float = Query(10, ge=1, le=100, description="How far from near_lat/near_lng"),
    sort: Optional[str] = Query(None, description="recommended (for the signed-in viewer, with match_reasons), nearest, newest, price_asc, price_desc. Default: nearest with near_lat/near_lng, else newest"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    if (near_lat is None) != (near_lng is None):
        raise BadRequestException("Send both near_lat and near_lng, or neither.")
    service = PropertyService(db)
    return await service.list_properties(
        near=(near_lat, near_lng) if near_lat is not None else None,
        radius_km=radius_km,
        sort=sort,
        viewer_id=viewer.id if viewer else None,
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

class ListingInteractionIn(BaseModel):
    action: Literal["view", "save", "unsave"]
    position: Optional[int] = Field(default=None, ge=0, le=10000, description="Where it was shown in the results")


@router.post("/{property_id}/interactions", status_code=status.HTTP_204_NO_CONTENT)
async def record_listing_interaction(
    property_id: UUID,
    data: ListingInteractionIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The signed-in person opened, saved or unsaved a listing: used to rank listings for them
    (and, anonymised into features, to train the ranker). Nothing is recorded when they turned
    personalised ranking off in their privacy settings."""
    from app.ml.listing_ranking import record_action
    from app.modules.properties.models import Property

    exists = (await db.execute(select(Property.id).where(
        Property.id == property_id, Property.is_active.is_(True)))).scalar_one_or_none()
    if exists is None:
        raise NotFoundException("Property not found")
    await record_action(db, current_user.id, property_id, data.action, data.position)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
