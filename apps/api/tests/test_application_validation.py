"""What an application may contain. The web form checks these too, but the API is the line that
holds: a direct call once stored an application proposing a rent of -5."""
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.applications.schemas import ApplicationCreate, ApplicationResponse


def _payload(**overrides):
    base = {
        "property_id": str(uuid4()),
        "introduction": "Working professional, quiet, looking for a long stay.",
        "proposed_rent": "13000",
        "move_in_target": str(date.today() + timedelta(days=10)),
    }
    base.update(overrides)
    return base


def test_a_normal_application_is_accepted():
    app = ApplicationCreate(**_payload(introduction="  Hi, I'm tidy.  "))
    assert app.introduction == "Hi, I'm tidy." and app.proposed_rent == Decimal("13000")


@pytest.mark.parametrize("rent", ["-5", "0", "10000000.01", "12000.555"])
def test_rent_must_be_positive_and_sane(rent):
    with pytest.raises(ValidationError):
        ApplicationCreate(**_payload(proposed_rent=rent))


@pytest.mark.parametrize("intro", ["", "   ", "x" * 2001])
def test_introduction_must_say_something_and_fit(intro):
    with pytest.raises(ValidationError):
        ApplicationCreate(**_payload(introduction=intro))


@pytest.mark.parametrize("days", [-30, -2, 731])
def test_move_in_must_be_from_today_to_two_years_out(days):
    with pytest.raises(ValidationError):
        ApplicationCreate(**_payload(move_in_target=str(date.today() + timedelta(days=days))))


def test_move_in_today_is_accepted():
    assert ApplicationCreate(**_payload(move_in_target=str(date.today()))).move_in_target == date.today()


def test_documents_are_bounded():
    with pytest.raises(ValidationError):
        ApplicationCreate(**_payload(documents=["a"] * 11))
    with pytest.raises(ValidationError):
        ApplicationCreate(**_payload(documents=["a" * 501]))


def test_stored_applications_still_read_back():
    """Responses don't re-apply the submission rules to rows stored before them."""
    now = "2026-01-01T00:00:00Z"
    ApplicationResponse(
        id=uuid4(), applicant_id=uuid4(), status="submitted", submitted_at=now, updated_at=now,
        property_id=uuid4(), introduction="", proposed_rent=Decimal("-5"), move_in_target=date(2020, 1, 1),
    )
