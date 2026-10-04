"""Agency mode: client folders that group competitors under a client name."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import func, select

from app.db.models import Board, Client, Competitor
from app.db.session import session_scope

router = APIRouter(prefix="/api/clients", tags=["clients"])


class ClientIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    notes: str | None = Field(None, max_length=2000)
    competitor_ids: list[int] = Field(default_factory=list)


class ClientPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    notes: str | None = Field(None, max_length=2000)


class Assign(BaseModel):
    client_id: int | None


def client_out(session, c: Client) -> dict:  # noqa: ANN001
    ids = session.exec(select(Competitor.id).where(Competitor.client_id == c.id)).all()
    boards = session.exec(select(func.count(Board.id)).where(Board.client_id == c.id)).one()
    return {
        "id": c.id,
        "name": c.name,
        "notes": c.notes,
        "competitor_ids": list(ids),
        "board_count": boards or 0,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _unique_name(session, name: str, exclude: int | None = None) -> str:  # noqa: ANN001
    name = name.strip()
    clash = session.exec(select(Client).where(func.lower(Client.name) == name.lower())).first()
    if clash is not None and clash.id != exclude:
        raise HTTPException(409, f"A client named “{clash.name}” already exists")
    return name


@router.get("")
def list_clients() -> list[dict]:
    with session_scope() as session:
        rows = session.exec(select(Client).order_by(func.lower(Client.name))).all()
        return [client_out(session, c) for c in rows]


@router.post("", status_code=201)
def create_client(body: ClientIn) -> dict:
    with session_scope() as session:
        client = Client(name=_unique_name(session, body.name), notes=body.notes)
        session.add(client)
        session.commit()
        session.refresh(client)
        for comp in session.exec(select(Competitor).where(Competitor.id.in_(body.competitor_ids))).all():  # type: ignore[union-attr]
            comp.client_id = client.id
            session.add(comp)
        session.commit()
        return client_out(session, client)


@router.patch("/{client_id}")
def update_client(client_id: int, body: ClientPatch) -> dict:
    with session_scope() as session:
        client = session.get(Client, client_id)
        if client is None:
            raise HTTPException(404, "Client not found")
        if body.name is not None:
            client.name = _unique_name(session, body.name, exclude=client_id)
        if body.notes is not None:
            client.notes = body.notes or None
        session.add(client)
        session.commit()
        return client_out(session, client)


@router.delete("/{client_id}")
def delete_client(client_id: int) -> dict:
    """Deletes the folder only: its competitors and boards are kept and become unassigned."""
    with session_scope() as session:
        client = session.get(Client, client_id)
        if client is None:
            raise HTTPException(404, "Client not found")
        for model in (Competitor, Board):
            for row in session.exec(select(model).where(model.client_id == client_id)).all():  # type: ignore[attr-defined]
                row.client_id = None
                session.add(row)
        session.flush()
        session.delete(client)
        session.commit()
    return {"ok": True}


@router.put("/assign/{competitor_id}")
def assign_competitor(competitor_id: int, body: Assign) -> dict:
    with session_scope() as session:
        comp = session.get(Competitor, competitor_id)
        if comp is None:
            raise HTTPException(404, "Competitor not found")
        if body.client_id is not None and session.get(Client, body.client_id) is None:
            raise HTTPException(404, "Client not found")
        comp.client_id = body.client_id
        session.add(comp)
        session.commit()
    return {"ok": True, "competitor_id": competitor_id, "client_id": body.client_id}
