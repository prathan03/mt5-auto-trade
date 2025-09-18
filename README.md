
# README.md

# MT5 Trading Bot with Gemini AI 🤖📈

An advanced automated trading system for MetaTrader 5 that uses Google's Gemini AI for market analysis and decision-making, with real-time Telegram notifications and ForexFactory news integration.

## Features ✨

- **AI-Powered Trading**: Uses Gemini AI for intelligent market analysis
- **Multi-Symbol Support**: Trade Forex, Commodities, Indices, and Crypto
- **Risk Management**: Advanced position sizing and loss limits
- **News Integration**: Automatic ForexFactory news checking
- **Telegram Alerts**: Real-time notifications for all trading activities
- **Session-Based Trading**: Optimize trading by market sessions
- **Trailing Stop Loss**: Automatic profit protection

## Prerequisites 📋

- Python 3.8 or higher
- MetaTrader 5 Terminal
- Windows OS (for MT5 connection)
- Gemini API Key
- Telegram Bot Token (optional)

## Installation 🚀

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/mt5-trading-bot.git
cd mt5-trading-bot
```

### 2. Create virtual environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Install TA-Lib (Optional but recommended)

**Windows:**
Download the appropriate .whl file from https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib
```bash
pip install TA_Lib‑0.4.28‑cp38‑cp38‑win_amd64.whl
```

**Linux:**
```bash
sudo apt-get install ta-lib
pip install ta-lib
```

**Mac:**
```bash
brew install ta-lib
pip install ta-lib
```

### 5. Configure environment variables
```bash
cp .env.example .env
# Edit .env file with your credentials
```

## Configuration 🔧

### Getting Gemini API Key
1. Visit https://makersuite.google.com/app/apikey
2. Create a new API key
3. Copy the key to your .env file

### Setting up Telegram Bot
1. Open Telegram and search for @BotFather
2. Send `/newbot` and follow instructions
3. Copy the bot token to your .env file
4. Get your chat ID:
   - Add the bot to your chat
   - Send a message to the bot
   - Visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your chat_id in the response

### MT5 Setup
1. Open MT5 Terminal
2. Enable Auto Trading (Tools -> Options -> Expert Advisors)
3. Allow DLL imports
4. Login to your account
5. Copy account number to .env file

## Usage 💻

### Basic Usage
```bash
python trading_bot.py
```

### With Custom Configuration
```python
# In trading_bot.py, modify custom_config:

custom_config = {
    'symbols': {
        'EURUSD': {'enabled': True, 'max_spread': 20},
        'XAUUSD': {'enabled': True, 'max_spread': 50},
    },
    'risk_config': {
        'max_risk_per_trade': 0.01,  # 1% risk
        'max_daily_loss': 0.03,      # 3% daily loss limit
    }
}
```

### Running in Background (Linux/Mac)
```bash
nohup python trading_bot.py > trading.log 2>&1 &
```

### Running as Windows Service
Use NSSM (Non-Sucking Service Manager) to run as Windows service

## Supported Symbols 📊

### Forex Majors
- EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, AUDUSD, NZDUSD

### Forex Crosses
- EURGBP, EURJPY, GBPJPY, AUDJPY, EURCHF

### Commodities
- XAUUSD (Gold), XAGUSD (Silver), USOIL (WTI), UKOIL (Brent)

### Indices (if supported by broker)
- US30, US500, NAS100, DE30, UK100, JP225

### Crypto (if supported by broker)
- BTCUSD, ETHUSD

## Risk Management ⚠️

### Default Settings (Conservative)
- **Risk per trade**: 1% of account
- **Daily loss limit**: 3%
- **Weekly loss limit**: 5%
- **Max open trades**: 5
- **Min confidence for trade**: 60%

### Position Sizing by Confidence
- 90%+ confidence = 100% of allocated risk
- 80-89% = 75% of allocated risk
- 70-79% = 50% of allocated risk
- 60-69% = 25% of allocated risk

## Monitoring 📱

### Telegram Alerts Include:
- Trade signals detected
- Positions opened/closed
- Stop loss modifications
- Account summary (3x daily)
- High impact news warnings
- Risk management alerts

### Log Files
- `trading_bot.log` - Main application log
- `trades.json` - Trade history

## Troubleshooting 🔨

### Common Issues

**MT5 Connection Failed**
- Ensure MT5 Terminal is running
- Check login credentials
- Verify server name is correct
- Allow automated trading in MT5

**No Trading Signals**
- Check market hours
- Verify symbols are available
- Review spread conditions
- Check for upcoming news events

**Telegram Not Working**
- Verify bot token
- Check chat ID (use negative for groups)
- Ensure bot has message permissions

## Safety Features 🛡️

- Automatic stop loss on all trades
- Daily and weekly loss limits
- Correlation-based position limits
- News event avoidance
- Spread filtering
- Session-based trading optimization

## Backtesting 📈

```python
# Run backtest
python backtest.py --symbol EURUSD --period 1Y
```

## Performance Metrics 📊

The bot tracks:
- Win rate
- Profit factor
- Sharpe ratio
- Maximum drawdown
- Average R:R ratio

## Contributing 🤝

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Disclaimer ⚖️

This bot is for educational purposes. Trading forex/CFDs involves substantial risk. Past performance does not guarantee future results. Always test thoroughly on demo accounts before using real money.

## License 📄

MIT License - see LICENSE file for details

## Support 💬

- Open an issue for bugs
- Join our Discord community
- Check the Wiki for detailed documentation

## Roadmap 🗺️

- [ ] Web dashboard
- [ ] Machine learning optimization
- [ ] Multi-timeframe analysis
- [ ] Sentiment analysis integration
- [ ] Advanced order types
- [ ] Cloud deployment support

---

Made with ❤️ by [Your Name]