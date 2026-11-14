"""
Contract Validation Test: Frontend Contracts Sync with Backend Schemas
Ensures that frontend @flatmate/contracts and API specification match the real FastAPI OpenAPI schema.
"""
from app.main import app

def test_openapi_schema_matches_contracts():
    schema = app.openapi()
    schemas = schema["components"]["schemas"]

    # 1. Properties
    assert "PropertyCreate" in schemas
    assert "PropertyResponse" in schemas
    assert "RoomResponse" in schemas
    assert "BedResponse" in schemas

    prop_resp_props = schemas["PropertyResponse"]["properties"]
    assert "id" in prop_resp_props
    assert "property_category" in prop_resp_props
    assert "configuration" in prop_resp_props
    assert "address_display" in prop_resp_props
    assert "currency" in prop_resp_props
    assert "security_deposit" in prop_resp_props
    assert "max_capacity" in prop_resp_props
    assert "furnishing_status" in prop_resp_props
    assert "listing_status" in prop_resp_props

    # 2. Authentication
    assert "TokenResponse" in schemas
    token_props = schemas["TokenResponse"]["properties"]
    assert "access_token" in token_props
    assert "refresh_token" in token_props
    assert "token_type" in token_props
    assert "expires_in" in token_props

    # 3. Groups
    assert "GroupResponse" in schemas
    group_props = schemas["GroupResponse"]["properties"]
    assert "id" in group_props
    assert "creator_id" in group_props
    assert "target_budget_total" in group_props

    # 4. Applications
    assert "ApplicationResponse" in schemas
    app_props = schemas["ApplicationResponse"]["properties"]
    assert "id" in app_props
    assert "property_id" in app_props
    assert "status" in app_props

    # 5. Appointments
    assert "AppointmentResponse" in schemas
    apt_props = schemas["AppointmentResponse"]["properties"]
    assert "id" in apt_props
    assert "property_id" in apt_props
    assert "scheduled_at" in apt_props
    assert "status" in apt_props
