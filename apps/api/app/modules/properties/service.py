from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, literal_column, select, text
from sqlalchemy.orm import selectinload
from geoalchemy2.elements import WKTElement
from geoalchemy2.shape import to_shape
from app.modules.properties.models import Property, Room, Bed, PropertyAmenity
from app.modules.properties.schemas import PropertyCreate, PropertyUpdate
from app.core.exceptions import NotFoundException, ForbiddenException, BadRequestException, ConflictException
from app.ml.indexing import queue_embedding_refresh
from app.ml.moderation import prescreen
from app.ml.moderation_jobs import ai_moderation_on, queue_property_moderation
from app.ml.search import clean_query, rank_properties
from app.modules.billing.entitlements import ensure_can_publish
from app.modules.locations.service import LocationService, city_condition, distance_km

VALID_LISTING_STATUSES = {"draft", "pending_verification", "published", "paused", "archived"}
# Changes to these refresh the listing's search embedding / trigger a safety review.
SEARCHABLE_FIELDS = {"title", "description", "address_display", "city", "configuration",
                     "property_category", "furnishing_status", "pets_allowed", "smoking_allowed"}
REVIEWED_FIELDS = {"title", "description", "monthly_rent", "security_deposit"}


def queue_listing_review(db: AsyncSession, prop: Property) -> None:
    """AI review of every new or changed listing when Claude is configured; otherwise only
    listings the rule pre-screen flags (they still get an automatic report)."""
    if ai_moderation_on() or prescreen(prop.title + " " + prop.description).level == "high":
        queue_property_moderation(db, prop.id)

class PropertyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _format_property_response(self, prop: Property, viewer_id: Optional[UUID] = None, is_admin: bool = False) -> dict:
        # location is NOT NULL in the schema; a decode failure is a real error, never a default point.
        point = to_shape(prop.location)
        lat, lng = point.y, point.x

        amenity_keys = [a.amenity_key for a in prop.amenities] if prop.amenities else []
        rooms = []
        if prop.rooms:
            for r in prop.rooms:
                beds = []
                if hasattr(r, "beds") and r.beds:
                    for b in r.beds:
                        beds.append({
                            "id": b.id,
                            "room_id": b.room_id,
                            "bed_identifier": b.bed_identifier,
                            "monthly_rent": b.monthly_rent,
                            "available_from": b.available_from,
                            "is_occupied": b.is_occupied,
                            "current_occupant_id": b.current_occupant_id,
                        })
                rooms.append({
                    "id": r.id,
                    "property_id": r.property_id,
                    "room_name": r.room_name,
                    "room_type": r.room_type,
                    "room_rent": r.room_rent,
                    "deposit": r.deposit,
                    "private_bath": r.private_bath,
                    "attached_balcony": r.attached_balcony,
                    "max_beds": r.max_beds,
                    "occupied_beds": r.occupied_beds,
                    "is_available": r.is_available,
                    "available_from": r.available_from,
                    "beds": beds,
                    "created_at": r.created_at or datetime.now(timezone.utc),
                })

        address_exact_val = prop.address_exact
        out_lat = lat
        out_lng = lng
        if not is_admin and (viewer_id is None or viewer_id != prop.owner_id):
            address_exact_val = "[Exact address protected - revealed upon confirmed visit]"
            from app.infrastructure.geospatial import fuzz_coordinates
            out_lat, out_lng = fuzz_coordinates(lat, lng, precision_decimals=2)

        return {
            "id": prop.id,
            "owner_id": prop.owner_id,
            "title": prop.title,
            "description": prop.description,
            "property_category": prop.property_category,
            "configuration": prop.configuration,
            "latitude": out_lat,
            "longitude": out_lng,
            "address_display": prop.address_display,
            "address_exact": address_exact_val,
            "city": prop.city,
            "state": prop.state,
            "postal_code": prop.postal_code,
            "country": prop.country,
            "currency": prop.currency,
            "monthly_rent": prop.monthly_rent,
            "security_deposit": prop.security_deposit,
            "maintenance_monthly": prop.maintenance_monthly,
            "bills_included": prop.bills_included,
            "total_bedrooms": prop.total_bedrooms,
            "total_bathrooms": prop.total_bathrooms,
            "max_capacity": prop.max_capacity,
            "current_occupants": prop.current_occupants,
            "available_from": prop.available_from,
            "is_furnished": prop.is_furnished,
            "furnishing_status": prop.furnishing_status,
            "pets_allowed": prop.pets_allowed,
            "smoking_allowed": prop.smoking_allowed,
            "images": prop.images or [],
            "amenities": amenity_keys,
            "rooms": rooms,
            "listing_status": prop.listing_status,
            "is_featured": bool(prop.featured_until and prop.featured_until > datetime.now(timezone.utc)),
            "is_verified": prop.is_verified,
            "is_active": prop.is_active,
            "created_at": prop.created_at or datetime.now(timezone.utc),
            "updated_at": prop.updated_at or datetime.now(timezone.utc),
        }

    async def get_by_id(self, property_id: UUID, viewer_id: Optional[UUID] = None, is_admin: bool = False) -> Optional[dict]:
        query = (
            select(Property)
            .options(
                selectinload(Property.rooms).selectinload(Room.beds),
                selectinload(Property.amenities)
            )
            .where(Property.id == property_id)
        )
        result = await self.db.execute(query)
        prop = result.scalar_one_or_none()
        if not prop:
            return None
        return self._format_property_response(prop, viewer_id=viewer_id, is_admin=is_admin)

    async def list_properties(
        self,
        city: Optional[str] = None,
        min_rent: Optional[Decimal] = None,
        max_rent: Optional[Decimal] = None,
        property_category: Optional[str] = None,
        configuration: Optional[str] = None,
        bedrooms: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
        q: Optional[str] = None,
        locality: Optional[str] = None,
        furnishing_status: Optional[str] = None,
        near: Optional[tuple] = None,
        radius_km: float = 10.0,
    ) -> List[dict]:
        """`near` is a (lat, lng) point: only listings within `radius_km` of it, nearest first
        (or by relevance when there is free text), each with its distance."""
        conditions = [Property.is_active.is_(True), Property.listing_status == "published"]
        distance = None
        if near is not None:
            # PostGIS on (location::geography), which has a GiST index (migration 004). Metres.
            here = text("ST_SetSRID(ST_MakePoint(:near_lng, :near_lat), 4326)::geography").bindparams(
                near_lng=float(near[1]), near_lat=float(near[0]))
            geog = literal_column("properties.location::geography")
            conditions.append(func.ST_DWithin(geog, here, float(radius_km) * 1000.0))
            distance = func.ST_Distance(geog, here)
        if locality:
            conditions.append(Property.address_display.icontains(locality, autoescape=True))
        if furnishing_status:
            conditions.append(Property.furnishing_status == furnishing_status)
        if city:
            conditions.append(await city_condition(self.db, Property.city, city))
        if min_rent is not None:
            conditions.append(Property.monthly_rent >= min_rent)
        if max_rent is not None:
            conditions.append(Property.monthly_rent <= max_rent)
        if property_category:
            conditions.append(Property.property_category == property_category)
        if configuration:
            conditions.append(Property.configuration == configuration)
        if bedrooms is not None:
            conditions.append(Property.total_bedrooms >= bedrooms)
        query = (
            select(Property)
            .options(
                selectinload(Property.rooms).selectinload(Room.beds),
                selectinload(Property.amenities)
            )
            .where(*conditions)
        )

        text_query = clean_query(q)
        if text_query:
            # Hybrid full-text + embedding search over the filtered set (app/ml/search.py).
            eligible = select(Property.id).where(*conditions)
            ranking = await rank_properties(self.db, text_query, eligible)
            page_ids = ranking.ids[offset:offset + limit]
            if not page_ids:
                return []
            rows = (await self.db.execute(query.where(Property.id.in_(page_ids)))).scalars().all()
            by_id = {p.id: p for p in rows}
            return [self._with_distance(self._format_property_response(by_id[i]), near) for i in page_ids if i in by_id]

        if distance is not None:
            query = query.order_by(distance, Property.id)
        else:
            # Featured (Owner Pro) listings first, then newest.
            featured = func.coalesce(Property.featured_until > func.now(), False)
            query = query.order_by(featured.desc(), Property.created_at.desc())
        result = await self.db.execute(query.limit(limit).offset(offset))
        props = result.scalars().all()
        return [self._with_distance(self._format_property_response(p), near) for p in props]

    @staticmethod
    def _with_distance(item: dict, near: Optional[tuple]) -> dict:
        """Distance to the position the response shows (approximate for everyone but the owner),
        so it reveals nothing the map pin doesn't."""
        if near is not None:
            item["distance_km"] = round(distance_km(near[0], near[1], item["latitude"], item["longitude"]), 1)
        return item

    async def create(self, owner_id: UUID, data: PropertyCreate) -> dict:
        # Invariant: current occupants cannot exceed max capacity
        if data.current_occupants > data.max_capacity:
            raise BadRequestException("Current occupants cannot exceed maximum capacity")
        # Listings are only in catalogue cities, saved under the official name and its state.
        city = await LocationService(self.db).resolve(data.city)
        if city is None or not city.is_active:
            raise BadRequestException(
                f"Listings in {data.city.strip() or 'that city'} aren't open yet. Choose a city from the list.",
                error_code="UNSUPPORTED_CITY",
            )
        await ensure_can_publish(self.db, owner_id)  # new listings are published at once

        wkt_point = f"POINT({data.longitude} {data.latitude})"
        prop = Property(
            owner_id=owner_id,
            title=data.title,
            description=data.description,
            property_category=data.property_category,
            configuration=data.configuration,
            location=WKTElement(wkt_point, srid=4326),
            address_display=data.address_display,
            address_exact=data.address_exact,
            city=city.name,
            state=city.state,
            postal_code=data.postal_code,
            country=data.country,
            currency=data.currency,
            monthly_rent=data.monthly_rent,
            security_deposit=data.security_deposit,
            maintenance_monthly=data.maintenance_monthly,
            bills_included=data.bills_included,
            total_bedrooms=data.total_bedrooms,
            total_bathrooms=data.total_bathrooms,
            max_capacity=data.max_capacity,
            current_occupants=data.current_occupants,
            available_from=data.available_from,
            is_furnished=data.is_furnished,
            furnishing_status=data.furnishing_status,
            pets_allowed=data.pets_allowed,
            smoking_allowed=data.smoking_allowed,
            images=data.images,
            listing_status="published",
            is_active=True,
        )
        self.db.add(prop)
        await self.db.flush()
        queue_embedding_refresh(self.db, "property", prop.id)
        queue_listing_review(self.db, prop)

        # Add amenities
        for amenity in data.amenities:
            self.db.add(PropertyAmenity(property_id=prop.id, amenity_key=amenity))

        # Add rooms & beds
        if data.rooms:
            for r_data in data.rooms:
                if r_data.occupied_beds > r_data.max_beds:
                    raise BadRequestException(f"Room {r_data.room_name} occupied beds cannot exceed max beds")
                room = Room(
                    property_id=prop.id,
                    room_name=r_data.room_name,
                    room_type=r_data.room_type,
                    room_rent=r_data.room_rent,
                    deposit=r_data.deposit,
                    private_bath=r_data.private_bath,
                    attached_balcony=r_data.attached_balcony,
                    max_beds=r_data.max_beds,
                    occupied_beds=r_data.occupied_beds,
                    is_available=r_data.is_available,
                    available_from=r_data.available_from,
                )
                self.db.add(room)
                await self.db.flush()

                if r_data.beds:
                    for b_data in r_data.beds:
                        bed = Bed(
                            room_id=room.id,
                            bed_identifier=b_data.bed_identifier,
                            monthly_rent=b_data.monthly_rent,
                            available_from=b_data.available_from,
                            is_occupied=b_data.is_occupied,
                            current_occupant_id=b_data.current_occupant_id,
                        )
                        self.db.add(bed)

        await self.db.commit()
        res = await self.get_by_id(prop.id)
        if not res:
            raise NotFoundException("Property not found")
        return res

    async def update(self, property_id: UUID, user_id: UUID, data: PropertyUpdate, is_admin: bool = False) -> dict:
        query = select(Property).where(Property.id == property_id)
        result = await self.db.execute(query)
        prop = result.scalar_one_or_none()
        if not prop:
            raise NotFoundException("Property not found")

        if prop.owner_id != user_id and not is_admin:
            raise ForbiddenException("You do not have permission to modify this property")

        update_dict = data.model_dump(exclude_unset=True)

        if "current_occupants" in update_dict:
            new_occupants = update_dict["current_occupants"]
            if new_occupants > prop.max_capacity:
                raise BadRequestException("Current occupants cannot exceed maximum property capacity")

        if "listing_status" in update_dict:
            status_val = update_dict["listing_status"]
            if status_val not in VALID_LISTING_STATUSES:
                raise BadRequestException(f"Invalid listing status: {status_val}")
            await self._check_status_change(prop, status_val, is_admin)

        for key, value in update_dict.items():
            if key not in ("amenities",):
                setattr(prop, key, value)
        if SEARCHABLE_FIELDS & update_dict.keys():
            queue_embedding_refresh(self.db, "property", prop.id)
        if REVIEWED_FIELDS & update_dict.keys():
            queue_listing_review(self.db, prop)

        await self.db.commit()
        res = await self.get_by_id(prop.id)
        if not res:
            raise NotFoundException("Property not found")
        return res

    async def _check_status_change(self, prop: Property, status_val: str, is_admin: bool) -> None:
        """Publishing counts against the owner's plan; leaving "published" frees a featured slot."""
        if status_val == "published" and prop.listing_status != "published" and not is_admin:
            await ensure_can_publish(self.db, prop.owner_id, prop.id)
        if status_val != "published":
            prop.featured_until = None

    async def update_listing_status(self, property_id: UUID, user_id: UUID, status_val: str, is_admin: bool = False) -> dict:
        if status_val not in VALID_LISTING_STATUSES:
            raise BadRequestException(f"Invalid listing status: {status_val}")

        query = select(Property).where(Property.id == property_id)
        result = await self.db.execute(query)
        prop = result.scalar_one_or_none()
        if not prop:
            raise NotFoundException("Property not found")

        if prop.owner_id != user_id and not is_admin:
            raise ForbiddenException("Access denied")

        await self._check_status_change(prop, status_val, is_admin)
        prop.listing_status = status_val
        await self.db.commit()
        res = await self.get_by_id(prop.id)
        if not res:
            raise NotFoundException("Property not found")
        return res

    async def assign_bed_occupant(self, bed_id: UUID, occupant_id: UUID, user_id: UUID, is_admin: bool = False) -> Bed:
        query = (
            select(Bed)
            .options(selectinload(Bed.room).selectinload(Room.property))
            .where(Bed.id == bed_id)
            .with_for_update()
        )
        result = await self.db.execute(query)
        bed = result.scalar_one_or_none()
        if not bed:
            raise NotFoundException("Bed not found")

        prop = bed.room.property
        if prop.owner_id != user_id and not is_admin:
            raise ForbiddenException("Permission denied to assign bed on this property")

        if bed.is_occupied:
            raise ConflictException("Bed is already occupied")

        room = bed.room
        if room.occupied_beds >= room.max_beds:
            raise BadRequestException("Room has reached maximum bed capacity")

        if prop.current_occupants >= prop.max_capacity:
            raise BadRequestException("Property has reached maximum occupant capacity")

        bed.is_occupied = True
        bed.current_occupant_id = occupant_id
        room.occupied_beds += 1
        prop.current_occupants += 1

        await self.db.commit()
        await self.db.refresh(bed)
        return bed

    async def vacate_bed(self, bed_id: UUID, user_id: UUID, is_admin: bool = False) -> Bed:
        query = (
            select(Bed)
            .options(selectinload(Bed.room).selectinload(Room.property))
            .where(Bed.id == bed_id)
            .with_for_update()
        )
        result = await self.db.execute(query)
        bed = result.scalar_one_or_none()
        if not bed:
            raise NotFoundException("Bed not found")

        prop = bed.room.property
        if prop.owner_id != user_id and not is_admin:
            raise ForbiddenException("Permission denied to modify bed on this property")

        if not bed.is_occupied:
            raise BadRequestException("Bed is already vacant")

        room = bed.room
        bed.is_occupied = False
        bed.current_occupant_id = None
        room.occupied_beds = max(0, room.occupied_beds - 1)
        prop.current_occupants = max(0, prop.current_occupants - 1)

        await self.db.commit()
        await self.db.refresh(bed)
        return bed
