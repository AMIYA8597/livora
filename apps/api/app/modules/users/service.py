from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.modules.users.models import User
from app.modules.users.schemas import UserUpdate

class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update(self, user: User, update_data: UserUpdate) -> User:
        if update_data.full_name is not None:
            user.full_name = update_data.full_name
        if update_data.phone_number is not None:
            user.phone_number = update_data.phone_number
        await self.db.commit()
        await self.db.refresh(user)
        return user
