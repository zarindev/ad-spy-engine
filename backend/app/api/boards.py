"""Swipe file boards: hand-picked ads with per-item notes and tags."""

from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlmodel import func, select

from app.api.serializers import ad_out
from app.db.models import Ad, Board, BoardItem, Client, utcnow
from app.db.session import session_scope

router = APIRouter(prefix="/api/boards", tags=["boards"])

MAX_TAGS = 12


def clean_tags(tags: list[str]) -> list[str]:
    """Trim, lowercase and de-duplicate tags (order kept)."""
    seen: list[str] = []
    for tag in tags:
        t = " ".join(tag.strip().lower().lstrip("#").split())[:32]
        if t and t not in seen:
            seen.append(t)
    return seen[:MAX_TAGS]


class BoardIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(None, max_length=500)
    client_id: int | None = None
    ad_ids: list[int] = Field(default_factory=list)


class BoardPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    description: str | None = Field(None, max_length=500)
    client_id: int | None = None
    clear_client: bool = False


class ItemsIn(BaseModel):
    ad_ids: list[int] = Field(min_length=1, max_length=500)
    note: str | None = Field(None, max_length=2000)
    tags: list[str] = Field(default_factory=list)


class ItemPatch(BaseModel):
    note: str | None = Field(None, max_length=2000)
    tags: list[str] | None = None

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str] | None) -> list[str] | None:
        return clean_tags(v) if v is not None else None


def board_out(session, board: Board, covers: int = 4) -> dict:  # noqa: ANN001
    count = session.exec(select(func.count(BoardItem.id)).where(BoardItem.board_id == board.id)).one()
    cover_ads = session.exec(
        select(Ad)
        .join(BoardItem, BoardItem.ad_id == Ad.id)
        .where(BoardItem.board_id == board.id)
        .order_by(BoardItem.added_at.desc())  # type: ignore[attr-defined]
        .limit(covers)
    ).all()
    client = session.get(Client, board.client_id) if board.client_id else None
    return {
        "id": board.id,
        "name": board.name,
        "description": board.description,
        "client_id": board.client_id,
        "client_name": client.name if client else None,
        "item_count": count or 0,
        "covers": [c for a in cover_ads if (c := ad_out(a)["thumbnail_url"] or ad_out(a)["screenshot_url"])],
        "created_at": board.created_at.isoformat() if board.created_at else None,
        "updated_at": board.updated_at.isoformat() if board.updated_at else None,
    }


def item_out(item: BoardItem, ad: Ad) -> dict:
    return {
        "id": item.id,
        "note": item.note,
        "tags": item.tags or [],
        "added_at": item.added_at.isoformat() if item.added_at else None,
        "ad": ad_out(ad),
    }


def _board(session, board_id: int) -> Board:  # noqa: ANN001
    board = session.get(Board, board_id)
    if board is None:
        raise HTTPException(404, "Board not found")
    return board


def _add_items(
    session, board: Board, ad_ids: list[int], note: str | None, tags: list[str]
) -> int:  # noqa: ANN001
    existing = set(session.exec(select(BoardItem.ad_id).where(BoardItem.board_id == board.id)).all())
    valid = set(session.exec(select(Ad.id).where(Ad.id.in_(ad_ids))).all())  # type: ignore[union-attr]
    added = 0
    for ad_id in dict.fromkeys(ad_ids):
        if ad_id in valid and ad_id not in existing:
            session.add(BoardItem(board_id=board.id, ad_id=ad_id, note=note or None, tags=clean_tags(tags)))
            added += 1
    board.updated_at = utcnow()
    session.add(board)
    return added


@router.get("")
def list_boards(client_id: int | None = None) -> list[dict]:
    with session_scope() as session:
        stmt = select(Board).order_by(Board.updated_at.desc())  # type: ignore[attr-defined]
        if client_id is not None:
            stmt = stmt.where(Board.client_id == client_id)
        return [board_out(session, b) for b in session.exec(stmt).all()]


@router.post("", status_code=201)
def create_board(body: BoardIn) -> dict:
    with session_scope() as session:
        if body.client_id is not None and session.get(Client, body.client_id) is None:
            raise HTTPException(404, "Client not found")
        board = Board(name=body.name.strip(), description=body.description, client_id=body.client_id)
        session.add(board)
        session.commit()
        session.refresh(board)
        if body.ad_ids:
            _add_items(session, board, body.ad_ids, None, [])
            session.commit()
        return board_out(session, board)


@router.get("/for-ad/{ad_id}")
def boards_for_ad(ad_id: int) -> list[int]:
    """IDs of the boards an ad is saved to (drives the "Save to board" checkmarks)."""
    with session_scope() as session:
        return list(session.exec(select(BoardItem.board_id).where(BoardItem.ad_id == ad_id)).all())


@router.get("/tags")
def all_tags() -> list[dict]:
    with session_scope() as session:
        rows = session.exec(select(BoardItem.tags)).all()
    counts = Counter(t for tags in rows for t in tags or [])
    return [{"name": k, "count": v} for k, v in counts.most_common()]


@router.get("/{board_id}")
def get_board(board_id: int, tag: str | None = None) -> dict:
    with session_scope() as session:
        board = _board(session, board_id)
        rows = session.exec(
            select(BoardItem, Ad)
            .join(Ad, Ad.id == BoardItem.ad_id)
            .where(BoardItem.board_id == board_id)
            .order_by(BoardItem.added_at.desc())  # type: ignore[attr-defined]
        ).all()
        tags = Counter(t for item, _ in rows for t in item.tags or [])
        items = [item_out(i, a) for i, a in rows if tag is None or tag in (i.tags or [])]
        return {
            **board_out(session, board),
            "items": items,
            "tags": [{"name": k, "count": v} for k, v in tags.most_common()],
        }


@router.patch("/{board_id}")
def update_board(board_id: int, body: BoardPatch) -> dict:
    with session_scope() as session:
        board = _board(session, board_id)
        if body.name is not None:
            board.name = body.name.strip()
        if body.description is not None:
            board.description = body.description or None
        if body.clear_client:
            board.client_id = None
        elif body.client_id is not None:
            if session.get(Client, body.client_id) is None:
                raise HTTPException(404, "Client not found")
            board.client_id = body.client_id
        board.updated_at = utcnow()
        session.add(board)
        session.commit()
        return board_out(session, board)


@router.delete("/{board_id}")
def delete_board(board_id: int) -> dict:
    with session_scope() as session:
        board = _board(session, board_id)
        for item in session.exec(select(BoardItem).where(BoardItem.board_id == board_id)).all():
            session.delete(item)
        session.flush()
        session.delete(board)
        session.commit()
    return {"ok": True}


@router.post("/{board_id}/items", status_code=201)
def add_items(board_id: int, body: ItemsIn) -> dict:
    with session_scope() as session:
        board = _board(session, board_id)
        added = _add_items(session, board, body.ad_ids, body.note, body.tags)
        session.commit()
        return {"added": added, "board": board_out(session, board)}


@router.patch("/{board_id}/items/{item_id}")
def update_item(board_id: int, item_id: int, body: ItemPatch) -> dict:
    with session_scope() as session:
        item = session.get(BoardItem, item_id)
        if item is None or item.board_id != board_id:
            raise HTTPException(404, "Item not found")
        if body.note is not None:
            item.note = body.note.strip() or None
        if body.tags is not None:
            item.tags = body.tags
        session.add(item)
        board = _board(session, board_id)
        board.updated_at = utcnow()
        session.add(board)
        session.commit()
        ad = session.get(Ad, item.ad_id)
        return item_out(item, ad)  # type: ignore[arg-type]


@router.delete("/{board_id}/items/{item_id}")
def remove_item(board_id: int, item_id: int) -> dict:
    with session_scope() as session:
        item = session.get(BoardItem, item_id)
        if item is None or item.board_id != board_id:
            raise HTTPException(404, "Item not found")
        session.delete(item)
        session.commit()
    return {"ok": True}


@router.delete("/{board_id}/ads/{ad_id}")
def remove_ad(board_id: int, ad_id: int) -> dict:
    """Remove by ad (used by the "Save to board" toggle, which knows the ad but not the item)."""
    with session_scope() as session:
        item = session.exec(
            select(BoardItem).where(BoardItem.board_id == board_id, BoardItem.ad_id == ad_id)
        ).first()
        if item is not None:
            session.delete(item)
            session.commit()
    return {"ok": True}
