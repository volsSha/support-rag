import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User


async def test_create_user(async_session: AsyncSession):
    user = User(
        username="testuser",
        hashed_password="hashed_pw",
        is_admin=False,
    )
    async_session.add(user)
    await async_session.commit()

    result = await async_session.get(User, user.id)
    assert result is not None
    assert result.username == "testuser"
    assert result.is_admin is False
    assert result.created_at is not None


async def test_duplicate_username_raises(async_session: AsyncSession):
    user1 = User(username="dup", hashed_password="pw1")
    user2 = User(username="dup", hashed_password="pw2")

    async_session.add(user1)
    await async_session.commit()

    async_session.add(user2)
    with pytest.raises(IntegrityError):
        await async_session.commit()
