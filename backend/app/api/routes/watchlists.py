from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import IdentitySession
from app.api.routes.auth import _authenticated_mutation
from app.db.models import DailyPrice, Instrument, Watchlist, WatchlistItem
from app.identity.access import CurrentIdentity
from app.models.watchlist import (
    WatchlistCreateRequest,
    WatchlistItemRequest,
    WatchlistItemResponse,
    WatchlistRenameRequest,
    WatchlistResponse,
)


router = APIRouter(prefix="/watchlists", tags=["watchlists"])


def _owned_watchlist(session: Session, identity: CurrentIdentity, watchlist_id: UUID) -> Watchlist:
    watchlist = session.scalar(
        select(Watchlist).where(
            Watchlist.id == watchlist_id,
            Watchlist.owner_id == identity.user.id,
        )
    )
    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return watchlist


def _response(session: Session, watchlist: Watchlist) -> WatchlistResponse:
    latest_date = (
        select(DailyPrice.symbol, func.max(DailyPrice.date).label("latest_date"))
        .group_by(DailyPrice.symbol)
        .subquery()
    )
    rows = session.execute(
        select(WatchlistItem, Instrument, DailyPrice)
        .join(Instrument, Instrument.symbol == WatchlistItem.symbol)
        .outerjoin(
            latest_date,
            latest_date.c.symbol == WatchlistItem.symbol,
        )
        .outerjoin(
            DailyPrice,
            and_(
                DailyPrice.symbol == WatchlistItem.symbol,
                DailyPrice.date == latest_date.c.latest_date,
            ),
        )
        .where(WatchlistItem.watchlist_id == watchlist.id)
        .order_by(WatchlistItem.created_at, WatchlistItem.symbol)
    ).all()
    return WatchlistResponse(
        id=watchlist.id,
        name=watchlist.name,
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
        items=[
            WatchlistItemResponse(
                symbol=item.symbol,
                company_name=instrument.company_name,
                observation_date=price.date if price else None,
                latest_price=price.close if price else None,
                change_percent=price.change_percent if price else None,
                created_at=item.created_at,
            )
            for item, instrument, price in rows
        ],
    )


@router.get("", response_model=list[WatchlistResponse])
def list_watchlists(identity: CurrentIdentity, session: IdentitySession) -> list[WatchlistResponse]:
    watchlists = session.scalars(
        select(Watchlist)
        .where(Watchlist.owner_id == identity.user.id)
        .order_by(Watchlist.created_at, Watchlist.name)
    ).all()
    return [_response(session, watchlist) for watchlist in watchlists]


@router.post("", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
def create_watchlist(
    payload: WatchlistCreateRequest,
    request: Request,
    identity: CurrentIdentity,
    session: IdentitySession,
) -> WatchlistResponse:
    grant = _authenticated_mutation(request, session)
    if isinstance(grant, JSONResponse):
        return grant  # type: ignore[return-value]
    watchlist = Watchlist(owner_id=identity.user.id, name=payload.name)
    session.add(watchlist)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Watchlist name is already in use") from exc
    session.commit()
    return _response(session, watchlist)


@router.get("/{watchlist_id}", response_model=WatchlistResponse)
def get_watchlist(watchlist_id: UUID, identity: CurrentIdentity, session: IdentitySession) -> WatchlistResponse:
    return _response(session, _owned_watchlist(session, identity, watchlist_id))


@router.patch("/{watchlist_id}", response_model=WatchlistResponse)
def rename_watchlist(
    watchlist_id: UUID,
    payload: WatchlistRenameRequest,
    request: Request,
    identity: CurrentIdentity,
    session: IdentitySession,
) -> WatchlistResponse:
    grant = _authenticated_mutation(request, session)
    if isinstance(grant, JSONResponse):
        return grant  # type: ignore[return-value]
    watchlist = _owned_watchlist(session, identity, watchlist_id)
    watchlist.name = payload.name
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Watchlist name is already in use") from exc
    session.commit()
    return _response(session, watchlist)


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist(
    watchlist_id: UUID,
    request: Request,
    identity: CurrentIdentity,
    session: IdentitySession,
) -> Response:
    grant = _authenticated_mutation(request, session)
    if isinstance(grant, JSONResponse):
        return grant  # type: ignore[return-value]
    watchlist = _owned_watchlist(session, identity, watchlist_id)
    session.delete(watchlist)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{watchlist_id}/items", response_model=WatchlistResponse)
def add_item(
    watchlist_id: UUID,
    payload: WatchlistItemRequest,
    request: Request,
    identity: CurrentIdentity,
    session: IdentitySession,
) -> WatchlistResponse:
    grant = _authenticated_mutation(request, session)
    if isinstance(grant, JSONResponse):
        return grant  # type: ignore[return-value]
    watchlist = _owned_watchlist(session, identity, watchlist_id)
    if session.scalar(select(Instrument).where(Instrument.symbol == payload.symbol)) is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    session.add(WatchlistItem(watchlist_id=watchlist.id, symbol=payload.symbol))
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Instrument is already in this watchlist") from exc
    session.commit()
    return _response(session, watchlist)


@router.delete("/{watchlist_id}/items/{symbol}", response_model=WatchlistResponse)
def remove_item(
    watchlist_id: UUID,
    symbol: str,
    request: Request,
    identity: CurrentIdentity,
    session: IdentitySession,
) -> WatchlistResponse:
    grant = _authenticated_mutation(request, session)
    if isinstance(grant, JSONResponse):
        return grant  # type: ignore[return-value]
    watchlist = _owned_watchlist(session, identity, watchlist_id)
    item = session.scalar(
        select(WatchlistItem).where(
            WatchlistItem.watchlist_id == watchlist.id,
            WatchlistItem.symbol == symbol.strip().upper(),
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    session.delete(item)
    session.commit()
    return _response(session, watchlist)
