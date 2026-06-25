import logging
import time
import uuid as uuid_module
from typing import Optional, Any, Dict

import pandas as pd

from app.tasks.celery_app import celery_app, _SyncSession
from app.models.backtest import BacktestStatus

logger = logging.getLogger(__name__)


def _update_backtest_status(
    backtest_id: str, status: str, result: Optional[dict] = None,
    metrics: Optional[dict] = None, error_message: Optional[str] = None,
    runtime_seconds: Optional[float] = None,
) -> None:
    """Update backtest record in database synchronously."""
    from sqlalchemy import update, func
    from app.models.backtest import Backtest

    session = _SyncSession()
    try:
        stmt = (
            update(Backtest)
            .where(Backtest.id == uuid_module.UUID(backtest_id))
            .values(
                status=status,
                result=result,
                metrics=metrics,
                error_message=error_message,
                runtime_seconds=runtime_seconds,
                completed_at=func.now() if status in ("completed", "failed", "cancelled") else None,
                updated_at=func.now(),
            )
        )
        session.execute(stmt)
        session.commit()
    except Exception as exc:
        logger.exception("Failed to update backtest status: %s", exc)
        session.rollback()
    finally:
        session.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, queue="backtest")
def run_backtest_task(self, backtest_id: str, strategy_id: str, config: dict) -> dict:
    """Execute backtest engine task.

    Steps:
        1. Load strategy IR from DB
        2. Load market data
        3. Run EventDrivenBacktester
        4. Save results to DB
        5. Update progress via Celery state
    """
    start_time = time.time()
    logger.info(
        "Starting backtest task: backtest_id=%s, strategy_id=%s", backtest_id, strategy_id
    )

    self.update_state(state="RUNNING", meta={"progress": 0, "stage": "initializing"})

    try:
        # 1. Load strategy IR from DB
        self.update_state(state="RUNNING", meta={"progress": 10, "stage": "loading_strategy"})

        from sqlalchemy import select
        from app.models.strategy import Strategy

        session = _SyncSession()
        try:
            result = session.execute(
                select(Strategy).where(Strategy.id == uuid_module.UUID(strategy_id))
            )
            strategy = result.scalar_one_or_none()
            if strategy is None or not strategy.ir_json:
                raise ValueError(f"Strategy {strategy_id} not found or has no IR")
            ir_data = strategy.ir_json
        finally:
            session.close()

        # 2. Parse IR
        from engine.strategy_builder.strategy_ir import StrategyIR

        strategy_ir = StrategyIR.from_dict(ir_data)
        errors = strategy_ir.validate()
        if errors:
            raise ValueError(f"IR validation failed: {errors}")

        self.update_state(state="RUNNING", meta={"progress": 20, "stage": "loading_data"})

        # 3. Load market data (stub - replace with actual data loader)
        # TODO: integrate with data storage or downloader
        symbol = config.get("symbol", "000001.SZ")
        timeframe = config.get("timeframe", "1d")
        start_date = config.get("start_date", "2020-01-01")
        end_date = config.get("end_date", "2024-01-01")

        # Generate placeholder data for now
        dates = pd.date_range(start=start_date, end=end_date, freq="B")
        data = pd.DataFrame({
            "timestamp": dates,
            "open": 10.0 + pd.Series(range(len(dates))) * 0.01,
            "high": 10.5 + pd.Series(range(len(dates))) * 0.01,
            "low": 9.8 + pd.Series(range(len(dates))) * 0.01,
            "close": 10.3 + pd.Series(range(len(dates))) * 0.01,
            "volume": 100000.0,
            "symbol": symbol,
            "limit_up": 11.0,
            "limit_down": 9.0,
            "suspended": False,
            "adjustment_factor": 1.0,
        })

        self.update_state(state="RUNNING", meta={"progress": 40, "stage": "running_backtest"})

        # 4. Run backtest engine
        from engine.backtest.engine import EventDrivenBacktester, BacktestConfig

        backtest_cfg = BacktestConfig(
            initial_capital=config.get("initial_capital", 1_000_000.0),
            commission_rate=config.get("commission_rate", 0.0003),
            slippage=config.get("slippage", 0.001),
            position_sizing=config.get("position_sizing", "fixed_value"),
            max_positions=config.get("max_positions", 10),
            freq="daily",
        )

        backtester = EventDrivenBacktester()
        backtest_result = backtester.run(strategy_ir, data, backtest_cfg)

        self.update_state(state="RUNNING", meta={"progress": 80, "stage": "saving_results"})

        # 5. Convert result to serializable dict
        equity_records = []
        if not backtest_result.equity_curve.empty:
            for _, row in backtest_result.equity_curve.iterrows():
                equity_records.append({
                    "timestamp": row["timestamp"].isoformat() if hasattr(row["timestamp"], "isoformat") else str(row["timestamp"]),
                    "equity": float(row["equity"]),
                    "cash": float(row["cash"]),
                    "market_value": float(row["market_value"]),
                })

        trades = []
        for t in backtest_result.trades:
            trades.append({
                "trade_id": t.trade_id,
                "timestamp": t.timestamp.isoformat() if hasattr(t.timestamp, "isoformat") else str(t.timestamp),
                "symbol": t.symbol,
                "signal": int(t.signal),
                "price": float(t.price),
                "shares": t.shares,
                "commission": float(t.commission),
                "slippage": float(t.slippage),
                "reason": t.reason,
            })

        result_dict = {
            "equity_curve": equity_records,
            "trades": trades,
            "n_trades": len(trades),
        }
        metrics_dict = backtest_result.metrics

        runtime = time.time() - start_time

        _update_backtest_status(
            backtest_id=backtest_id,
            status=BacktestStatus.COMPLETED.value,
            result=result_dict,
            metrics=metrics_dict,
            runtime_seconds=runtime,
        )

        self.update_state(state="SUCCESS", meta={"progress": 100, "stage": "completed"})

        return {
            "backtest_id": backtest_id,
            "status": "completed",
            "runtime_seconds": runtime,
            "n_trades": len(trades),
        }

    except Exception as exc:
        logger.exception("Backtest task failed: %s", exc)
        runtime = time.time() - start_time
        _update_backtest_status(
            backtest_id=backtest_id,
            status=BacktestStatus.FAILED.value,
            error_message=str(exc),
            runtime_seconds=runtime,
        )
        self.update_state(
            state="FAILURE",
            meta={"progress": 0, "stage": "failed", "error": str(exc)},
        )
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30, queue="robustness")
def run_monte_carlo_task(
    self, strategy_id: str, backtest_id: Optional[str], method: str, config: dict
) -> dict:
    """Run Monte Carlo simulation task."""
    logger.info("Starting Monte Carlo task: strategy_id=%s", strategy_id)
    self.update_state(state="RUNNING", meta={"progress": 0, "stage": "initializing"})

    try:
        # TODO: load strategy and backtest result, run Monte Carlo
        self.update_state(state="RUNNING", meta={"progress": 50, "stage": "simulating"})
        # Placeholder
        self.update_state(state="SUCCESS", meta={"progress": 100, "stage": "completed"})
        return {"status": "completed", "message": "Monte Carlo simulation done"}
    except Exception as exc:
        logger.exception("Monte Carlo task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30, queue="robustness")
def run_walk_forward_task(
    self, strategy_id: str, data_config: dict, wfo_config: dict
) -> dict:
    """Run Walk-Forward Analysis task."""
    logger.info("Starting Walk-Forward task: strategy_id=%s", strategy_id)
    self.update_state(state="RUNNING", meta={"progress": 0, "stage": "initializing"})

    try:
        self.update_state(state="RUNNING", meta={"progress": 50, "stage": "analyzing"})
        # Placeholder
        self.update_state(state="SUCCESS", meta={"progress": 100, "stage": "completed"})
        return {"status": "completed", "message": "Walk-Forward analysis done"}
    except Exception as exc:
        logger.exception("Walk-Forward task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30, queue="robustness")
def run_overfitting_task(
    self, strategy_id: str, backtest_id: Optional[str], n_splits: int
) -> dict:
    """Run overfitting detection (PBO/DSR/PSR) task."""
    logger.info("Starting overfitting detection task: strategy_id=%s", strategy_id)
    self.update_state(state="RUNNING", meta={"progress": 0, "stage": "initializing"})

    try:
        self.update_state(state="RUNNING", meta={"progress": 50, "stage": "computing"})
        # Placeholder
        self.update_state(state="SUCCESS", meta={"progress": 100, "stage": "completed"})
        return {"status": "completed", "message": "Overfitting detection done"}
    except Exception as exc:
        logger.exception("Overfitting detection task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30, queue="optimizer")
def run_optimizer_task(
    self, strategy_id: str, data_config: dict, opt_config: dict
) -> dict:
    """Run parameter optimization task using Optuna."""
    logger.info("Starting optimizer task: strategy_id=%s", strategy_id)
    self.update_state(state="RUNNING", meta={"progress": 0, "stage": "initializing"})

    try:
        self.update_state(state="RUNNING", meta={"progress": 50, "stage": "optimizing"})
        # Placeholder
        self.update_state(state="SUCCESS", meta={"progress": 100, "stage": "completed"})
        return {
            "status": "completed",
            "message": "Optimization done",
            "best_params": {},
            "best_metric": 0.0,
        }
    except Exception as exc:
        logger.exception("Optimizer task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30, queue="optimizer")
def run_walk_forward_opt_task(
    self, strategy_id: str, data_config: dict, wfo_config: dict
) -> dict:
    """Run Walk-Forward optimization task."""
    logger.info("Starting WFO optimization task: strategy_id=%s", strategy_id)
    self.update_state(state="RUNNING", meta={"progress": 0, "stage": "initializing"})

    try:
        self.update_state(state="RUNNING", meta={"progress": 50, "stage": "optimizing"})
        # Placeholder
        self.update_state(state="SUCCESS", meta={"progress": 100, "stage": "completed"})
        return {
            "status": "completed",
            "message": "WFO optimization done",
            "optimal_params_trajectory": [],
        }
    except Exception as exc:
        logger.exception("WFO optimization task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(queue="backtest")
def cleanup_old_results() -> dict:
    """Periodic cleanup of expired results."""
    logger.info("Running cleanup of old results")
    # TODO: implement cleanup logic
    return {"status": "completed", "cleaned": 0}
