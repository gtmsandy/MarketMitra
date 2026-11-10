from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.dependencies import IdentitySession
from app.api.routes.auth import _authenticated_mutation
from app.identity.access import CurrentIdentity
from app.models.portfolio import (
    HoldingResponse,
    PortfolioCreateRequest,
    PortfolioRenameRequest,
    PortfolioResponse,
    PortfolioSummaryResponse,
    SectorAllocationResponse,
    TransactionCreateRequest,
    TransactionResponse,
    ValuationResponse,
)
from app.services.portfolio_service import (
    ConflictError,
    NotFoundError,
    PortfolioError,
    ValidationError,
    archive_portfolio,
    create_portfolio,
    create_transaction,
    holdings_and_summary,
    list_portfolios,
    rename_portfolio,
    transaction_to_dict,
)


router = APIRouter(prefix="/portfolios", tags=["portfolios"])


def _error(exc: PortfolioError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


def _mutation(request: Request, session: IdentitySession):
    grant = _authenticated_mutation(request, session)
    if isinstance(grant, JSONResponse):
        return grant
    return None


@router.post("", response_model=PortfolioResponse, status_code=201)
def create(payload: PortfolioCreateRequest, request: Request, identity: CurrentIdentity, session: IdentitySession):
    denied = _mutation(request, session)
    if denied is not None:
        return denied
    try:
        portfolio = create_portfolio(session, identity.user.id, payload.name)
        session.commit()
        return portfolio
    except (ConflictError, ValidationError) as exc:
        session.rollback()
        raise _error(exc) from exc


@router.get("", response_model=list[PortfolioResponse])
def list_all(identity: CurrentIdentity, session: IdentitySession):
    return list_portfolios(session, identity.user.id)


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
def get_one(portfolio_id: UUID, identity: CurrentIdentity, session: IdentitySession):
    try:
        from app.services.portfolio_service import _owned
        return _owned(session, identity.user.id, portfolio_id, include_archived=True)
    except NotFoundError as exc:
        raise _error(exc) from exc


@router.patch("/{portfolio_id}", response_model=PortfolioResponse)
def rename(portfolio_id: UUID, payload: PortfolioRenameRequest, request: Request, identity: CurrentIdentity, session: IdentitySession):
    denied = _mutation(request, session)
    if denied is not None:
        return denied
    try:
        portfolio = rename_portfolio(session, identity.user.id, portfolio_id, payload.name)
        session.commit()
        return portfolio
    except (ConflictError, NotFoundError) as exc:
        session.rollback()
        raise _error(exc) from exc


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive(portfolio_id: UUID, request: Request, identity: CurrentIdentity, session: IdentitySession):
    denied = _mutation(request, session)
    if denied is not None:
        return denied
    try:
        archive_portfolio(session, identity.user.id, portfolio_id)
        session.commit()
        return Response(status_code=204)
    except NotFoundError as exc:
        session.rollback()
        raise _error(exc) from exc


@router.post("/{portfolio_id}/transactions", response_model=TransactionResponse)
def add_transaction(portfolio_id: UUID, payload: TransactionCreateRequest, request: Request, identity: CurrentIdentity, session: IdentitySession):
    denied = _mutation(request, session)
    if denied is not None:
        return denied
    try:
        row, created = create_transaction(session, identity.user.id, portfolio_id, payload.model_dump())
        session.commit()
        response = JSONResponse(content=TransactionResponse.model_validate(transaction_to_dict(row)).model_dump(mode="json"), status_code=201 if created else 200)
        return response
    except (ConflictError, NotFoundError, ValidationError) as exc:
        session.rollback()
        raise _error(exc) from exc


@router.get("/{portfolio_id}/transactions", response_model=list[TransactionResponse])
def transactions(portfolio_id: UUID, identity: CurrentIdentity, session: IdentitySession):
    try:
        from app.services.portfolio_service import _accounting_rows, _owned
        portfolio = _owned(session, identity.user.id, portfolio_id, include_archived=True)
        return [transaction_to_dict(row) for row in _accounting_rows(session, portfolio.id)]
    except NotFoundError as exc:
        raise _error(exc) from exc


@router.get("/{portfolio_id}/holdings", response_model=list[HoldingResponse])
def holdings(portfolio_id: UUID, identity: CurrentIdentity, session: IdentitySession, as_of: date | None = None):
    try:
        state, _, _ = holdings_and_summary(session, identity.user.id, portfolio_id, as_of or date.today())
        return [HoldingResponse(symbol=h.symbol, quantity=h.quantity, average_cost=h.average_cost, invested_cost=h.carrying_cost, realized_pnl=state.realized_pnl) for h in state.holdings.values() if h.quantity > 0]
    except (NotFoundError, ValidationError) as exc:
        raise _error(exc) from exc


@router.get("/{portfolio_id}/summary", response_model=PortfolioSummaryResponse)
def summary(portfolio_id: UUID, identity: CurrentIdentity, session: IdentitySession, as_of: date | None = None):
    try:
        state, result, valuations = holdings_and_summary(session, identity.user.id, portfolio_id, as_of or date.today())
        valuation_date = as_of or date.today()
        return PortfolioSummaryResponse(
            holdings=[HoldingResponse(symbol=h.symbol, quantity=h.quantity, average_cost=h.average_cost, invested_cost=h.carrying_cost, realized_pnl=result.realized_pnl) for h in state.holdings.values() if h.quantity > 0],
            cash_flow_cost=result.carrying_cost, market_value=result.market_value, unrealized_pnl=result.unrealized_pnl,
            realized_pnl=result.realized_pnl, total_pnl=result.total_pnl, return_percent=result.return_percent,
            valuation=ValuationResponse(as_of=valuation_date, source="synthetic", freshness="historical", observed_on_by_symbol={symbol: observation.observed_on for symbol, observation in valuations.items()}, complete=result.valuation_status == "complete", missing_symbols=list(result.missing_symbols), stale_symbols=list(result.stale_symbols)),
        )
    except (NotFoundError, ValidationError) as exc:
        raise _error(exc) from exc


@router.get("/{portfolio_id}/sector-allocation", response_model=list[SectorAllocationResponse])
def sector_allocation(portfolio_id: UUID, identity: CurrentIdentity, session: IdentitySession, as_of: date | None = None):
    try:
        _, result, _ = holdings_and_summary(session, identity.user.id, portfolio_id, as_of or date.today())
        return [SectorAllocationResponse(sector=item.sector, market_value=item.market_value, percentage=item.percentage) for item in result.sector_allocation]
    except (NotFoundError, ValidationError) as exc:
        raise _error(exc) from exc
