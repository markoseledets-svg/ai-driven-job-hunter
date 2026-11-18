from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import UUID

from job_hunter.db.base import BaseIndexModel


class BaseRepository[ModelType: BaseIndexModel]:
    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        self._session = session
        self._model = model

    def add(self, **kwargs: Any) -> ModelType:
        model = self._model(**kwargs)
        self._session.add(model)
        return model

    async def add_many(self, entities: Sequence[ModelType]) -> list[ModelType]:
        if not entities:
            return []
        self._session.add_all(entities)
        await self._session.flush()
        return list(entities)

    async def get_by_id(self, entity_id: UUID) -> ModelType | None:
        result = await self._session.execute(select(self._model).where(self._model.id == entity_id))
        return result.scalar_one_or_none()
