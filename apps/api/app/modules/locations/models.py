"""
Geographical & PostGIS Location Hierarchy Domain Models
"""
import uuid
from typing import List, Optional
from sqlalchemy import ARRAY, Boolean, String, Integer, ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry
from app.core.database import Base

class Country(Base):
    __tablename__ = "countries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(3), unique=True, nullable=False) # e.g. IND, USA
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    phone_code: Mapped[str] = mapped_column(String(8), default="+91", nullable=False)

    states: Mapped[List["State"]] = relationship("State", back_populates="country", cascade="all, delete-orphan")

class State(Base):
    """A state or union territory (28 + 8 for India, migration 016)."""
    __tablename__ = "states"
    __table_args__ = (UniqueConstraint("country_id", "code", name="uq_states_country_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("countries.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False) # e.g. KA, MH, DL, TS
    kind: Mapped[str] = mapped_column(String(16), nullable=False, server_default="state")  # state, union_territory
    capital_city_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cities.id", ondelete="SET NULL", use_alter=True), nullable=True, index=True)

    country: Mapped["Country"] = relationship("Country", back_populates="states")
    cities: Mapped[List["City"]] = relationship(
        "City", back_populates="state", cascade="all, delete-orphan", foreign_keys="City.state_id")

class City(Base):
    __tablename__ = "cities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    state_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("states.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True) # Bengaluru, Mumbai, Delhi, Hyderabad
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    tier: Mapped[int] = mapped_column(Integer, default=1, nullable=False) # Tier 1, Tier 2
    center_location = mapped_column(Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=True)
    # Other names people search for (Bangalore, Port Blair, Delhi NCR).
    aliases: Mapped[List[str]] = mapped_column(ARRAY(String(100)), nullable=False, server_default=text("'{}'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))  # open for listings

    state: Mapped["State"] = relationship("State", back_populates="cities", foreign_keys=[state_id])
    localities: Mapped[List["Locality"]] = relationship("Locality", back_populates="city", cascade="all, delete-orphan")

class Locality(Base):
    __tablename__ = "localities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cities.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True) # e.g. Koramangala, Indiranagar, HSR Layout, Whitefield
    postal_code: Mapped[str] = mapped_column(String(12), nullable=False, index=True) # Pin code
    center_location = mapped_column(Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False)
    boundary_geojson: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    city: Mapped["City"] = relationship("City", back_populates="localities")
