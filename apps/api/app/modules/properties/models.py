"""
Comprehensive Property & Accommodation Domain Models
Distinguishes Property, Unit, Room, Bed, Pricing, Amenities, and Capacity Constraints.
"""
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import String, Integer, Numeric, Boolean, Text, Date, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry
from app.core.database import Base

class Property(Base):
    __tablename__ = "properties"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    property_category: Mapped[str] = mapped_column(String(50), default="apartment", nullable=False) # apartment, independent_house, pg, hostel, co_living, villa
    configuration: Mapped[str] = mapped_column(String(50), default="2BHK", nullable=False) # 1RK, 1BHK, 2RK, 2BHK, 3BHK, 4BHK_plus, studio
    
    # PostGIS Location (Approximate locality exposed publicly, exact masked)
    location = mapped_column(Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False)
    address_display: Mapped[str] = mapped_column(String(255), nullable=False) # Public locality: "HSR Layout Sector 2, Bengaluru"
    address_exact: Mapped[str] = mapped_column(String(255), nullable=False) # Private building/flat number
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(100), default="India", nullable=False)
    # city (still at the city centre) / locality / postcode (placed by OpenStreetMap) / owner
    # (the owner's own pin) / NULL (saved before migration 017).
    location_precision: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # Financials (INR-first with explicit currency)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    monthly_rent: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, index=True)
    security_deposit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0.00, nullable=False)
    maintenance_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.00, nullable=False)
    bills_included: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Capacity & Verification
    total_bedrooms: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    total_bathrooms: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_capacity: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    current_occupants: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_from: Mapped[date] = mapped_column(Date, nullable=False)
    is_furnished: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    furnishing_status: Mapped[str] = mapped_column(String(32), default="semi_furnished", nullable=False) # fully_furnished, semi_furnished, unfurnished
    pets_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    smoking_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    listing_status: Mapped[str] = mapped_column(String(32), default="published", nullable=False) # draft, pending_verification, published, paused, archived
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    images: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    # Owner Pro: listed first and badged until this time (the end of the owner's paid period).
    featured_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("current_occupants <= max_capacity", name="chk_prop_capacity_overflow"),
        CheckConstraint("monthly_rent >= 0", name="chk_prop_rent_positive"),
    )

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    rooms: Mapped[List["Room"]] = relationship("Room", back_populates="property", cascade="all, delete-orphan")
    amenities: Mapped[List["PropertyAmenity"]] = relationship("PropertyAmenity", back_populates="property", cascade="all, delete-orphan")

class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. "Master Bedroom with Balcony"
    room_type: Mapped[str] = mapped_column(String(50), default="private", nullable=False) # private, 2_sharing, 3_sharing, master_ensuite
    room_rent: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    deposit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0.00, nullable=False)
    private_bath: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attached_balcony: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_beds: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    occupied_beds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    available_from: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("occupied_beds <= max_beds", name="chk_room_bed_capacity"),
    )

    property: Mapped["Property"] = relationship("Property", back_populates="rooms")
    beds: Mapped[List["Bed"]] = relationship("Bed", back_populates="room", cascade="all, delete-orphan")

class Bed(Base):
    __tablename__ = "beds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    bed_identifier: Mapped[str] = mapped_column(String(20), nullable=False) # e.g. "Bed A", "Bed B (Window)"
    is_occupied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    current_occupant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    monthly_rent: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    available_from: Mapped[date] = mapped_column(Date, nullable=False)

    room: Mapped["Room"] = relationship("Room", back_populates="beds")
    current_occupant = relationship("User", foreign_keys=[current_occupant_id])

class PropertyAmenity(Base):
    __tablename__ = "property_amenities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    amenity_key: Mapped[str] = mapped_column(String(50), nullable=False) # power_backup, wifi, ro_water, geyser, security_24x7

    property: Mapped["Property"] = relationship("Property", back_populates="amenities")
