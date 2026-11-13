"""
Search & Discovery Service
Implements PostGIS spatial radius discovery, coordinate fuzzing, and flatmate search.
"""
from typing import List, Optional
from uuid import UUID
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.modules.properties.models import Property
from app.modules.profiles.models import Profile
from app.modules.users.models import User
from app.infrastructure.geospatial import haversine_distance, fuzz_coordinates
from app.modules.search.schemas import (
    PropertySearchFilter,
    PropertySearchResultItem,
    FlatmateSearchFilter,
    FlatmateSearchResultItem,
)

class SearchService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _calc_age(self, birth_date: Optional[date]) -> Optional[int]:
        if not birth_date:
            return None
        today = date.today()
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    async def search_properties(
        self,
        filters: PropertySearchFilter,
        is_authenticated_viewer: bool = False
    ) -> List[PropertySearchResultItem]:
        query = (
            select(Property)
            .where(Property.is_active.is_(True))
            .where(Property.listing_status == "published")
        )

        # Free-text keyword search
        if filters.query:
            term = f"%{filters.query}%"
            query = query.where(
                or_(
                    Property.title.ilike(term),
                    Property.description.ilike(term),
                    Property.address_display.ilike(term),
                    Property.city.ilike(term),
                )
            )

        if filters.city:
            query = query.where(Property.city.ilike(f"%{filters.city}%"))
        if filters.property_category:
            query = query.where(Property.property_category == filters.property_category)
        if filters.configuration:
            query = query.where(Property.configuration == filters.configuration)
        if filters.min_rent is not None:
            query = query.where(Property.monthly_rent >= filters.min_rent)
        if filters.max_rent is not None:
            query = query.where(Property.monthly_rent <= filters.max_rent)
        if filters.furnishing_status:
            query = query.where(Property.furnishing_status == filters.furnishing_status)
        if filters.pets_allowed is not None:
            query = query.where(Property.pets_allowed.is_(filters.pets_allowed))
        if filters.smoking_allowed is not None:
            query = query.where(Property.smoking_allowed.is_(filters.smoking_allowed))

        query = query.limit(filters.limit).offset(filters.offset)
        result = await self.db.execute(query)
        props = result.scalars().all()

        items: List[PropertySearchResultItem] = []
        for prop in props:
            # Extract coordinates from PostGIS or defaults
            lat = 12.9716
            lng = 77.5946
            if hasattr(prop, "location") and prop.location is not None:
                try:
                    from shapely import wkb
                    point = wkb.loads(bytes(prop.location.data))
                    lng, lat = point.x, point.y
                except Exception:
                    pass

            distance_km: Optional[float] = None
            if filters.latitude is not None and filters.longitude is not None:
                distance_km = haversine_distance(filters.latitude, filters.longitude, lat, lng)
                if distance_km > filters.radius_km:
                    continue  # Outside requested search radius

            # Apply coordinate fuzzing for privacy if unauthenticated or not property owner
            is_fuzzed = True
            if is_authenticated_viewer:
                fuzzed_lat, fuzzed_lng = lat, lng
                is_fuzzed = False
            else:
                fuzzed_lat, fuzzed_lng = fuzz_coordinates(lat, lng, precision_decimals=2)

            items.append(PropertySearchResultItem(
                id=prop.id,
                title=prop.title,
                description=prop.description,
                property_category=prop.property_category,
                configuration=prop.configuration,
                address_display=prop.address_display,
                city=prop.city,
                state=prop.state,
                postal_code=prop.postal_code,
                currency=prop.currency or "INR",
                monthly_rent=prop.monthly_rent,
                security_deposit=prop.security_deposit,
                total_bedrooms=prop.total_bedrooms,
                total_bathrooms=prop.total_bathrooms,
                max_capacity=prop.max_capacity,
                current_occupants=prop.current_occupants,
                furnishing_status=prop.furnishing_status,
                images=prop.images or [],
                latitude=fuzzed_lat,
                longitude=fuzzed_lng,
                distance_km=distance_km,
                is_fuzzed_location=is_fuzzed,
            ))

        # Sort by distance if radius query was supplied
        if filters.latitude is not None and filters.longitude is not None:
            items.sort(key=lambda x: x.distance_km if x.distance_km is not None else 999999.0)

        return items

    async def search_flatmates(
        self,
        filters: FlatmateSearchFilter,
        current_user_id: Optional[UUID] = None
    ) -> List[FlatmateSearchResultItem]:
        query = (
            select(Profile, User)
            .join(User, Profile.user_id == User.id)
            .where(User.is_active.is_(True))
        )
        if current_user_id:
            query = query.where(User.id != current_user_id)

        if filters.min_budget is not None:
            query = query.where(Profile.budget_max >= filters.min_budget)
        if filters.max_budget is not None:
            query = query.where(Profile.budget_min <= filters.max_budget)
        if filters.gender:
            query = query.where(Profile.gender == filters.gender)
        if filters.occupation:
            query = query.where(Profile.occupation.ilike(f"%{filters.occupation}%"))

        query = query.limit(filters.limit).offset(filters.offset)
        result = await self.db.execute(query)
        rows = result.all()

        results: List[FlatmateSearchResultItem] = []
        for profile, user in rows:
            traits = profile.lifestyle_traits or {}

            # Locality filtering against preferred_locations list
            if filters.locality:
                loc_match = any(filters.locality.lower() in loc.lower() for loc in (profile.preferred_locations or []))
                if not loc_match:
                    continue

            # Lifestyle filters
            if filters.sleep_schedule and traits.get("sleep_schedule") != filters.sleep_schedule:
                continue
            if filters.diet_preference and traits.get("diet") != filters.diet_preference:
                continue
            if filters.smoking and traits.get("smoking") != filters.smoking:
                continue

            results.append(FlatmateSearchResultItem(
                user_id=user.id,
                display_name=profile.display_name,
                avatar_url=profile.avatar_url,
                bio=profile.bio,
                age=self._calc_age(profile.birth_date),
                occupation=profile.occupation,
                company_name=profile.company_name,
                education_institute=profile.education_institute,
                budget_min=profile.budget_min,
                budget_max=profile.budget_max,
                preferred_locations=profile.preferred_locations or [],
                lifestyle_traits=traits,
                is_verified=user.is_verified,
            ))

        return results
