# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MT5 Trading Bot - An automated trading system for MetaTrader 5 that uses Google's Gemini AI for market analysis and trading decisions, with Telegram notifications and ForexFactory news integration.

## Key Components

### Main Application (`main.py`)

The application is organized into several key classes:

1. **TelegramNotifier** (lines 39-299): Handles all Telegram notifications for trade alerts and system status
2. **ForexFactoryNews** (lines 301-604): Scrapes and processes ForexFactory calendar for economic news events
3. **MT5Connection** (lines 606-641): Manages MetaTrader 5 terminal connection and authentication
4. **MarketDataMT5** (lines 643-992): Retrieves and processes market data from MT5 (candles, technical indicators)
5. **GeminiTradingAI** (lines 994-1168): Core AI decision engine using Google's Gemini model
6. **RiskManager** (lines 1170-1360): Handles position sizing, risk calculations, and safety limits
7. **MT5TradingExecutor** (lines 1362-1700): Executes trades and manages positions in MT5
8. **TradingBot** (lines 1702+): Main orchestrator that coordinates all components

## Development Commands

### Setup
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirement.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials
```

### Running the Bot
```bash
# Main trading bot
python main.py

# Run in background (Linux/Mac)
nohup python main.py > trading.log 2>&1 &
```

### Testing
```bash
# Run tests (when implemented)
pytest

# Run specific test file
pytest tests/test_risk_manager.py -v
```

## Configuration

The bot uses environment variables from `.env` file:
- **MT5 Credentials**: `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`
- **Gemini AI**: `GEMINI_API_KEY`
- **Telegram**: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- **Risk Settings**: `MAX_RISK_PER_TRADE`, `MAX_DAILY_LOSS`, `MAX_WEEKLY_LOSS`
- **Trading Parameters**: `ENABLED_SYMBOLS`, `MAX_OPEN_TRADES`, session times

## Important Architecture Details

### Trading Flow
1. **Market Analysis**: Bot fetches OHLC data and calculates technical indicators (RSI, MACD, Bollinger Bands, etc.)
2. **AI Decision**: Gemini AI analyzes the data and generates trading signals with confidence scores
3. **Risk Check**: RiskManager validates position size based on account balance and risk limits
4. **News Filter**: Checks ForexFactory for high-impact events before trading
5. **Execution**: Places orders through MT5 with calculated stop loss and take profit levels
6. **Monitoring**: Continuously tracks positions for trailing stops and exit conditions

### Symbol Support
The bot supports multiple asset classes if available on your broker:
- Forex pairs (majors and crosses)
- Commodities (Gold, Silver, Oil)
- Indices (US30, NAS100, etc.)
- Cryptocurrencies (if supported)

### Risk Management Features
- Position sizing based on confidence levels (60-90%)
- Daily and weekly loss limits
- Correlation-based position limits
- Automatic stop loss on all trades
- Trailing stop functionality
- News event avoidance

## Key Files and Directories
- `main.py` - Complete trading bot implementation
- `.env` - Configuration (create from `.env.example`)
- `requirement.txt` - Python dependencies
- `trading_bot.log` - Application log file
- `trades.json` - Trade history (generated at runtime)