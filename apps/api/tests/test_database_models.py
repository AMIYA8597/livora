from uuid import uuid4
from datetime import date
from decimal import Decimal
from app.core.database import Base
from app.modules.lifestyle.models import LifestyleProfile, UserDealbreaker  # noqa: F401
from app.modules.properties.models import Property, Room, Bed  # noqa: F401
from app.modules.tenants.models import TenantMembership, ExistingTenantVacancy  # noqa: F401
from app.modules.appointments.models import Appointment  # noqa: F401
from app.modules.professional_domains.models import ProfessionalDomain, Profession, Designation  # noqa: F401
from app.modules.locations.models import Country, State, City, Locality  # noqa: F401
from app.modules.pg_management.models import PGBuilding, PGFloor  # noqa: F401
from app.modules.matching.models import MatchInteraction, MutualMatch  # noqa: F401
from app.modules.subscriptions.models import SubscriptionPlan, Subscription, Payment  # noqa: F401

def test_model_metadata_registry():
    """Verify all critical relational tables are registered in SQLAlchemy Base.metadata."""
    tables = Base.metadata.tables.keys()
    required = [
        "users", "user_roles", "user_privacy_settings",
        "professional_domains", "professions", "designations",
        "countries", "states", "cities", "localities",
        "lifestyle_profiles", "user_dealbreakers",
        "properties", "rooms", "beds", "property_amenities",
        "pg_buildings", "pg_floors",
        "tenant_memberships", "existing_tenant_vacancies",
        "appointments", "mutual_matches", "match_interactions",
        "subscription_plans", "subscriptions", "payments",
    ]
    for table_name in required:
        assert table_name in tables, f"Expected table '{table_name}' to be registered in Base.metadata"

def test_property_and_bed_capacity_attributes():
    """Verify property and room models enforce capacity attributes."""
    prop = Property(
        id=uuid4(),
        owner_id=uuid4(),
        title="2BHK in Indiranagar",
        description="Spacious flat near metro",
        property_category="apartment",
        configuration="2BHK",
        address_display="Indiranagar 100ft Road, Bengaluru",
        address_exact="Flat 201, Green Glen",
        city="Bengaluru",
        postal_code="560038",
        monthly_rent=Decimal("35000.00"),
        security_deposit=Decimal("150000.00"),
        currency="INR",
        max_capacity=4,
        current_occupants=2,
        available_from=date.today(),
    )
    assert prop.current_occupants <= prop.max_capacity
    assert prop.currency == "INR"

def test_lifestyle_profile_normalized_fields():
    """Verify lifestyle model captures 10-dimension compatibility attributes."""
    profile = LifestyleProfile(
        id=uuid4(),
        user_id=uuid4(),
        sleep_schedule="early_bird",
        cleanliness_level=4,
        diet_preference="pure_veg",
        non_veg_cooking_allowed=False,
        smoking="never",
        preference_vector=[0.1] * 64,
    )
    assert profile.cleanliness_level == 4
    assert profile.diet_preference == "pure_veg"
    assert profile.non_veg_cooking_allowed is False
    assert len(profile.preference_vector) == 64
