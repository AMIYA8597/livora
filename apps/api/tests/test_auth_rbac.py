import pytest
from uuid import uuid4
from app.core.security import get_password_hash, verify_password
from app.core.dependencies import require_roles, verify_resource_ownership
from app.core.exceptions import ForbiddenException
from app.modules.users.models import User

def test_password_hashing():
    pwd = "SecurePassword@123"
    hashed = get_password_hash(pwd)
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False

def test_rbac_require_roles_permitted():
    user = User(
        id=uuid4(),
        email="owner@example.in",
        hashed_password="hash",
        full_name="Owner User",
        role="owner",
    )
    guard = require_roles(["owner", "admin"])
    # Should not raise exception
    checked_user = guard(current_user=user)
    assert checked_user.id == user.id

def test_rbac_require_roles_forbidden():
    user = User(
        id=uuid4(),
        email="seeker@example.in",
        hashed_password="hash",
        full_name="Seeker User",
        role="seeker",
    )
    guard = require_roles(["owner", "admin"])
    with pytest.raises(ForbiddenException):
        guard(current_user=user)

def test_resource_ownership_permitted():
    owner_id = uuid4()
    user = User(id=owner_id, email="owner@example.in", hashed_password="hash", full_name="Owner", role="seeker")
    # Must pass without error
    verify_resource_ownership(resource_owner_id=owner_id, current_user=user)

def test_resource_ownership_forbidden_for_other_user():
    owner_id = uuid4()
    other_user_id = uuid4()
    user = User(id=other_user_id, email="attacker@example.in", hashed_password="hash", full_name="Attacker", role="seeker")
    with pytest.raises(ForbiddenException):
        verify_resource_ownership(resource_owner_id=owner_id, current_user=user)

def test_resource_ownership_admin_override():
    owner_id = uuid4()
    admin_id = uuid4()
    admin = User(id=admin_id, email="admin@flatmate.in", hashed_password="hash", full_name="Admin", role="admin")
    # Admin is permitted to access or moderate any resource
    verify_resource_ownership(resource_owner_id=owner_id, current_user=admin, admin_override=True)
