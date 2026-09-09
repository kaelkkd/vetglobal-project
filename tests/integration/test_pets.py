from httpx import AsyncClient
from sqlalchemy import create_engine, text


async def test_create_pet_persists_trimmed_fields(
    client: AsyncClient, migrated_database: str
) -> None:
    response = await client.post(
        "/pets",
        json={"name": "  Hank  ", "owner_name": "  John Bergeson  "},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["name"] == "Hank"
    assert body["owner_name"] == "John Bergeson"
    assert body["created_at"].endswith("Z") or body["created_at"].endswith("+00:00")

    engine = create_engine(migrated_database)
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT name, owner_name FROM pets WHERE id = :id"), {"id": body["id"]}
        ).one()
    engine.dispose()
    assert row == ("Hank", "John Bergeson")


async def test_create_pet_rejects_blank_fields(client: AsyncClient) -> None:
    response = await client.post("/pets", json={"name": "   ", "owner_name": "Owner"})

    assert response.status_code == 422


async def test_create_pet_rejects_oversized_and_extra_fields(client: AsyncClient) -> None:
    response = await client.post(
        "/pets",
        json={"name": "x" * 121, "owner_name": "Owner", "tenant_id": 123},
    )

    assert response.status_code == 422
