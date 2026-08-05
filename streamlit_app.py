import asyncio
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agents.graph import create_trading_graph, run_trading_cycle
from src.market.indicators import IndicatorResult, Timeframe
from src.market.signals import SignalEngine, StrategyType


def create_sample_indicators(symbol: str, timeframe: Timeframe) -> IndicatorResult:
    """Return a sample indicator dataset for the selected symbol and timeframe."""
    base_price = {
        "RELIANCE": 2500.0,
        "TCS": 4150.0,
        "HDFCBANK": 1680.0,
        "INFY": 1845.0,
        "SBIN": 785.5,
        "ITC": 465.0,
        "ICICIBANK": 1275.0,
        "BHARTIARTL": 1620.0,
    }.get(symbol, 1000.0)

    # Light variations across timeframes
    timeframe_factor = {
        Timeframe.M1: 1.0,
        Timeframe.M5: 1.01,
        Timeframe.M15: 1.02,
        Timeframe.M30: 1.03,
        Timeframe.H1: 1.05,
        Timeframe.H4: 1.08,
        Timeframe.D1: 1.10,
    }[timeframe]

    close = base_price * timeframe_factor
    return IndicatorResult(
        symbol=symbol,
        timeframe=timeframe,
        open=close * 0.996,
        high=close * 1.008,
        low=close * 0.992,
        close=close,
        volume=1_000_000,
        sma={20: close * 0.98, 50: close * 0.95, 200: close * 0.88},
        ema={9: close * 0.99, 21: close * 0.97, 55: close * 0.92},
        rsi=55.0,
        stoch_k=65.0,
        stoch_d=60.0,
        macd=15.0,
        macd_signal=10.0,
        macd_histogram=5.0,
        adx=32.0,
        plus_di=28.0,
        minus_di=18.0,
        atr=25.0,
        bb_upper=close * 1.03,
        bb_middle=close * 1.00,
        bb_lower=close * 0.97,
        bb_percent=0.72,
        vwap=close * 0.995,
    )


def build_demo_market_data(symbol: str, close: float) -> dict[str, dict[str, float]]:
    return {
        symbol: {
            "close": float(close),
            "change_percent": float((close - (close * 0.99)) / (close * 0.99) * 100),
        }
    }


def run_trading_demo(
    symbol: str,
    timeframe: Timeframe,
    active_strategies: list[StrategyType],
    capital: float,
) -> dict[str, object]:
    indicators = create_sample_indicators(symbol, timeframe)
    signal_engine = SignalEngine()
    signals = signal_engine.generate_signals(indicators, active_strategies)

    market_data = build_demo_market_data(symbol, indicators.close)
    indicator_payload = {symbol: indicators.to_dict()}

    graph = create_trading_graph(with_memory=False, include_support_agents=False)
    final_state = asyncio.run(
        run_trading_cycle(
            graph=graph,
            market_data=market_data,
            indicators=indicator_payload,
            signals=[signal.to_dict() for signal in signals],
            memory_lessons=[],
            portfolio={"capital": capital, "positions": []},
            daily_stats={"trades_count": 0, "profit_loss": 0, "max_drawdown": 0},
            thread_id="streamlit_demo",
        )
    )

    return {
        "indicators": indicators,
        "signals": signals,
        "final_state": final_state,
    }


def display_signal(signal) -> None:
    st.write(
        f"**{signal.signal_type.value}** — {signal.symbol} | {signal.strategy.value} | "
        f"confidence: {signal.confidence:.2f} | entry: Rs. {signal.entry_price:.2f}"
    )
    st.write(f"- reasons: {', '.join(signal.reasons)}")


def main() -> None:
    st.set_page_config(
        page_title="NiftyGraph Demo",
        page_icon="📈",
        layout="wide",
    )

    st.title("NiftyGraph Streamlit Trading Demo")
    st.write(
        "A lightweight demo front end for RakshaQuant. Generate sample signals, run a trading cycle, "
        "and inspect the agentic decision state." 
    )

    symbol = st.sidebar.selectbox(
        "Symbol",
        [
            "RELIANCE",
            "TCS",
            "HDFCBANK",
            "INFY",
            "SBIN",
            "ITC",
            "ICICIBANK",
            "BHARTIARTL",
        ],
        index=0,
    )
    timeframe = st.sidebar.selectbox(
        "Timeframe",
        list(Timeframe),
        format_func=lambda tf: tf.value,
    )
    capital = st.sidebar.number_input("Starting Capital (₹)", value=1_000_000.0, step=50_000.0)
    selected_strategies = st.sidebar.multiselect(
        "Active Strategies",
        [strategy for strategy in StrategyType],
        default=[StrategyType.MOMENTUM, StrategyType.TREND_FOLLOWING],
        format_func=lambda strategy: strategy.value,
    )
    run_button = st.sidebar.button("Run Trading Demo")

    if run_button:
        with st.spinner("Running demo trading cycle..."):
            result = run_trading_demo(symbol, timeframe, selected_strategies, capital)

        st.subheader("Sample Market Indicators")
        ind = result["indicators"]
        st.write(
            {
                "symbol": ind.symbol,
                "timeframe": ind.timeframe.value,
                "close": ind.close,
                "rsi": ind.rsi,
                "macd_histogram": ind.macd_histogram,
                "adx": ind.adx,
                "bb_lower": ind.bb_lower,
                "bb_upper": ind.bb_upper,
            }
        )

        st.subheader("Generated Signals")
        if result["signals"]:
            for signal in result["signals"]:
                display_signal(signal)
        else:
            st.info("No actionable signals were generated for the selected inputs.")

        st.subheader("Trading Cycle Result")
        state = result["final_state"]
        st.write(
            {
                "regime": state.get("regime"),
                "regime_confidence": state.get("regime_confidence"),
                "active_strategies": state.get("active_strategies"),
                "validated_signals": len(state.get("validated_signals", [])),
                "approved_trades": len(state.get("approved_trades", [])),
                "risk_rejected": len(state.get("risk_rejected", [])),
                "errors": state.get("errors", []),
            }
        )

        if state.get("approved_trades"):
            st.subheader("Approved Trades")
            for trade in state.get("approved_trades", []):
                st.write(trade)

        if state.get("risk_rejected"):
            st.subheader("Risk Rejections")
            for trade in state.get("risk_rejected", []):
                st.write(trade)

    else:
        st.info("Adjust the inputs in the sidebar and click \"Run Trading Demo\".")


if __name__ == "__main__":
    main()
