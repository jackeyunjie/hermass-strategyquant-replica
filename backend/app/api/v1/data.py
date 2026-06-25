import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.api.deps import get_current_user, get_db
from app.models.data_source import DataSource, DataSourceStatus
from app.models.user import User

router = APIRouter()


class DataDownloadRequest(BaseModel):
    symbols: list[str] = Field(..., min_length=1, max_length=50)
    timeframe: str = Field(default="1d", pattern="^(1d|1m|5m|15m|30m|1h|1w|1M)$")
    start_date: str = Field(..., description="ISO date format YYYY-MM-DD")
    end_date: str = Field(..., description="ISO date format YYYY-MM-DD")
    provider: str = Field(default="tushare", description="Data provider name")


class DataDownloadResponse(BaseModel):
    task_id: str
    status: str
    message: str


class DataStatusResponse(BaseModel):
    symbols: list[str]
    total_records: int
    last_update: Optional[str]
    pending_downloads: list[str]


class DataCoverageItem(BaseModel):
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    records_count: int
    status: str


class DataCoverageResponse(BaseModel):
    items: list[DataCoverageItem]


class DataPreviewRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)


class DataPreviewItem(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class DataPreviewResponse(BaseModel):
    symbol: str
    timeframe: str
    records: list[DataPreviewItem]


@router.post(
    "/download",
    response_model=DataDownloadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Download market data",
    description="Submit async download task for market data. Returns task ID.",
)
async def download_data(
    payload: DataDownloadRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Create data source records for tracking
    for symbol in payload.symbols:
        existing = await db.execute(
            select(DataSource).where(
                DataSource.user_id == current_user.id,
                DataSource.symbol == symbol,
                DataSource.timeframe == payload.timeframe,
            )
        )
        data_source = existing.scalar_one_or_none()
        if data_source is None:
            data_source = DataSource(
                user_id=current_user.id,
                name=f"{symbol}_{payload.timeframe}",
                symbol=symbol,
                timeframe=payload.timeframe,
                status=DataSourceStatus.PENDING,
            )
            db.add(data_source)
    await db.commit()

    # TODO: dispatch to Celery task for actual download
    return DataDownloadResponse(
        task_id="placeholder-task-id",
        status="pending",
        message="Data download queued",
    )


@router.get(
    "/status",
    response_model=DataStatusResponse,
    summary="Data download status",
    description="Get overall data download status and pending items.",
)
async def get_data_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DataSource).where(DataSource.user_id == current_user.id)
    )
    sources = result.scalars().all()

    symbols = [s.symbol for s in sources]
    total_records = sum(s.records_count for s in sources)
    last_update = max(
        (s.updated_at for s in sources if s.updated_at),
        default=None,
    )
    pending = [
        s.symbol for s in sources if s.status == DataSourceStatus.PENDING
    ]

    return DataStatusResponse(
        symbols=symbols,
        total_records=total_records,
        last_update=last_update.isoformat() if last_update else None,
        pending_downloads=pending,
    )


@router.get(
    "/coverage",
    response_model=DataCoverageResponse,
    summary="Data coverage",
    description="Get coverage information for all downloaded data.",
)
async def get_data_coverage(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
):
    query = select(DataSource).where(DataSource.user_id == current_user.id)
    if symbol:
        query = query.where(DataSource.symbol == symbol)
    query = query.order_by(desc(DataSource.updated_at))

    result = await db.execute(query)
    sources = result.scalars().all()

    items = []
    for s in sources:
        items.append(
            DataCoverageItem(
                symbol=s.symbol,
                timeframe=s.timeframe,
                start_date=s.start_date.isoformat() if s.start_date else "",
                end_date=s.end_date.isoformat() if s.end_date else "",
                records_count=s.records_count,
                status=s.status.value,
            )
        )
    return DataCoverageResponse(items=items)


@router.get(
    "/preview/{symbol}",
    response_model=DataPreviewResponse,
    summary="Preview data",
    description="Preview last N K-line records for a symbol.",
)
async def preview_data(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000),
    timeframe: str = Query("1d", pattern="^(1d|1m|5m|15m|30m|1h|1w|1M)$"),
):
    # TODO: integrate with TimescaleDB to fetch actual OHLCV data
    # Stub implementation returning placeholder data
    return DataPreviewResponse(
        symbol=symbol,
        timeframe=timeframe,
        records=[
            DataPreviewItem(
                timestamp="2024-01-01T00:00:00Z",
                open=10.0,
                high=10.5,
                low=9.8,
                close=10.3,
                volume=100000.0,
            )
        ],
    )


@router.delete(
    "/{symbol}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete data",
    description="Delete all data for a specific symbol.",
)
async def delete_data(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    timeframe: Optional[str] = Query(None, description="Optional timeframe filter"),
):
    query = select(DataSource).where(
        DataSource.user_id == current_user.id,
        DataSource.symbol == symbol,
    )
    if timeframe:
        query = query.where(DataSource.timeframe == timeframe)

    result = await db.execute(query)
    sources = result.scalars().all()

    for source in sources:
        await db.delete(source)
    await db.commit()

    # TODO: also delete actual data from TimescaleDB
    return None
