from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from vetglobal.db import session_dependency
from vetglobal.models import Pet
from vetglobal.schemas import PetCreate, PetResponse

router = APIRouter(prefix="/pets", tags=["pets"])


@router.post("", response_model=PetResponse, status_code=status.HTTP_201_CREATED)
async def create_pet(
    payload: PetCreate,
    session: Annotated[AsyncSession, Depends(session_dependency)],
) -> Pet:
    pet = Pet(name=payload.name, owner_name=payload.owner_name)
    session.add(pet)
    await session.commit()
    await session.refresh(pet)
    return pet
