# MT5 Auto Trading Bot with Gemini AI
# Requirements: pip install MetaTrader5 pandas numpy google-generativeai ta python-dotenv python-telegram-bot beautifulsoup4 requests lxml

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import google.generativeai as genai
import json
import time
from datetime import datetime, timedelta, timezone
import logging
from typing import Dict, List, Optional, Tuple
import ta  # Technical Analysis library
import os
from dotenv import load_dotenv
import asyncio
from telegram import Bot
from telegram.error import TelegramError
import threading
import requests
from bs4 import BeautifulSoup
import pytz
from urllib.parse import urljoin

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Telegram Notification System"""
    
    def __init__(self, bot_token: str, chat_id: str):
        """
        Initialize Telegram Bot
        bot_token: Token from BotFather
        chat_id: Your Telegram chat ID or group ID
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.bot = Bot(token=bot_token)
        self.enabled = bool(bot_token and chat_id)
        
        if self.enabled:
            # Test connection
            try:
                asyncio.run(self._test_connection())
                logger.info("Telegram notifier initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Telegram notifier: {e}")
                self.enabled = False
        else:
            logger.info("Telegram notifier disabled (no token/chat_id)")
    
    async def _test_connection(self):
        """Test Telegram connection"""
        await self.bot.send_message(
            chat_id=self.chat_id,
            text="🤖 MT5 Trading Bot Started\n"
                 "━━━━━━━━━━━━━━━━━━━\n"
                 f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                 "Status: Connected ✅"
        )
    
    def send_message(self, message: str, parse_mode: str = 'HTML'):
        """Send message to Telegram"""
        if not self.enabled:
            return
        
        try:
            asyncio.run(self._send_async(message, parse_mode))
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
    
    async def _send_async(self, message: str, parse_mode: str):
        """Async send message"""
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=message,
            parse_mode=parse_mode
        )
    
    def send_trade_alert(self, trade_type: str, signal: Dict, symbol: str, 
                         lot_size: float = None, result: Dict = None):
        """Send formatted trade alert"""
        if not self.enabled:
            return
        
        if trade_type == 'SIGNAL':
            message = self._format_signal_message(signal, symbol)
        elif trade_type == 'OPENED':
            message = self._format_opened_message(signal, symbol, lot_size, result)
        elif trade_type == 'CLOSED':
            message = self._format_closed_message(symbol, result)
        elif trade_type == 'MODIFIED':
            message = self._format_modified_message(symbol, result)
        elif trade_type == 'ERROR':
            message = self._format_error_message(symbol, result)
        else:
            return
        
        self.send_message(message)
    
    def _format_signal_message(self, signal: Dict, symbol: str) -> str:
        """Format signal detection message"""
        emoji = "📈" if signal['decision'] == 'BUY' else "📉" if signal['decision'] == 'SELL' else "⏸"
        
        message = f"""
{emoji} <b>SIGNAL DETECTED</b>
━━━━━━━━━━━━━━━━━━━
📊 Symbol: <b>{symbol}</b>
📍 Signal: <b>{signal['decision']}</b>
💯 Confidence: <b>{signal.get('confidence', 0)}%</b>
💰 Entry: <b>{signal.get('entry_price', 0):.5f}</b>
🛑 Stop Loss: <b>{signal.get('stop_loss', 0):.5f}</b>
🎯 Take Profit: <b>{signal.get('take_profit_1', 0):.5f}</b>
⏰ Time: {datetime.now().strftime('%H:%M:%S')}

📝 <i>Reasoning: {signal.get('reasoning', 'N/A')[:200]}</i>
        """
        return message
    
    def _format_opened_message(self, signal: Dict, symbol: str, 
                               lot_size: float, result: Dict) -> str:
        """Format trade opened message"""
        emoji = "🟢" if signal['decision'] == 'BUY' else "🔴"
        
        # Calculate risk and reward
        if result and 'price' in result:
            entry = result['price']
            sl = signal.get('stop_loss', 0)
            tp = signal.get('take_profit_1', 0)
            
            risk_pips = abs(entry - sl) * 10000 if 'JPY' not in symbol else abs(entry - sl) * 100
            reward_pips = abs(tp - entry) * 10000 if 'JPY' not in symbol else abs(tp - entry) * 100
            rr_ratio = reward_pips / risk_pips if risk_pips > 0 else 0
        else:
            risk_pips = reward_pips = rr_ratio = 0
        
        message = f"""
{emoji} <b>TRADE OPENED</b> {emoji}
━━━━━━━━━━━━━━━━━━━
📊 Symbol: <b>{symbol}</b>
📍 Type: <b>{signal['decision']}</b>
📦 Volume: <b>{lot_size} lots</b>
💰 Entry: <b>{result.get('price', 0):.5f}</b>
🛑 SL: <b>{signal.get('stop_loss', 0):.5f}</b> ({risk_pips:.1f} pips)
🎯 TP: <b>{signal.get('take_profit_1', 0):.5f}</b> ({reward_pips:.1f} pips)
📊 R:R Ratio: <b>1:{rr_ratio:.1f}</b>
🎫 Ticket: <b>#{result.get('order', 'N/A')}</b>
⏰ Time: {datetime.now().strftime('%H:%M:%S')}

💯 Confidence: {signal.get('confidence', 0)}%
        """
        return message
    
    def _format_closed_message(self, symbol: str, result: Dict) -> str:
        """Format trade closed message"""
        profit = result.get('profit', 0)
        emoji = "💰" if profit > 0 else "💸" if profit < 0 else "➖"
        status_emoji = "✅" if profit > 0 else "❌" if profit < 0 else "⚪"
        
        message = f"""
{status_emoji} <b>TRADE CLOSED</b> {status_emoji}
━━━━━━━━━━━━━━━━━━━
📊 Symbol: <b>{symbol}</b>
💵 P/L: <b>${profit:.2f}</b> {emoji}
📍 Close Price: <b>{result.get('price', 0):.5f}</b>
🎫 Ticket: <b>#{result.get('order', 'N/A')}</b>
⏰ Time: {datetime.now().strftime('%H:%M:%S')}

{self._get_pl_bar(profit)}
        """
        return message
    
    def _format_modified_message(self, symbol: str, result: Dict) -> str:
        """Format position modified message"""
        message = f"""
🔧 <b>POSITION MODIFIED</b>
━━━━━━━━━━━━━━━━━━━
📊 Symbol: <b>{symbol}</b>
🛑 New SL: <b>{result.get('sl', 0):.5f}</b>
🎯 New TP: <b>{result.get('tp', 0):.5f}</b>
🎫 Ticket: <b>#{result.get('ticket', 'N/A')}</b>
⏰ Time: {datetime.now().strftime('%H:%M:%S')}
📝 Trailing stop activated
        """
        return message
    
    def _format_error_message(self, symbol: str, result: Dict) -> str:
        """Format error message"""
        message = f"""
⚠️ <b>TRADE ERROR</b> ⚠️
━━━━━━━━━━━━━━━━━━━
📊 Symbol: <b>{symbol}</b>
❌ Error: <b>{result.get('error', 'Unknown error')}</b>
💬 Details: {result.get('comment', 'N/A')}
⏰ Time: {datetime.now().strftime('%H:%M:%S')}
        """
        return message
    
    def _get_pl_bar(self, profit: float) -> str:
        """Create visual P/L bar"""
        if profit > 0:
            bars = min(int(profit / 10), 10)
            return "🟩" * bars + "⬜" * (10 - bars) + f" (+${profit:.2f})"
        elif profit < 0:
            bars = min(int(abs(profit) / 10), 10)
            return "🟥" * bars + "⬜" * (10 - bars) + f" (-${abs(profit):.2f})"
        else:
            return "⬜" * 10 + " ($0.00)"
    
    def send_account_summary(self, account_info, positions):
        """Send daily account summary"""
        if not self.enabled:
            return
        
        total_profit = sum(pos.profit for pos in positions) if positions else 0
        profit_emoji = "📈" if total_profit > 0 else "📉" if total_profit < 0 else "➖"
        
        message = f"""
📊 <b>ACCOUNT SUMMARY</b>
━━━━━━━━━━━━━━━━━━━
💰 Balance: <b>${account_info.balance:.2f}</b>
💵 Equity: <b>${account_info.equity:.2f}</b>
📈 Profit: <b>${account_info.profit:.2f}</b> {profit_emoji}
💳 Free Margin: <b>${account_info.margin_free:.2f}</b>
📊 Margin Level: <b>{account_info.margin_level:.2f}%</b>

📍 <b>Open Positions: {len(positions) if positions else 0}</b>
"""
        
        if positions:
            message += "━━━━━━━━━━━━━━━━━━━\n"
            for pos in positions[:5]:  # Show max 5 positions
                emoji = "🟢" if pos.type == 0 else "🔴"
                pl_emoji = "💰" if pos.profit > 0 else "💸"
                message += f"{emoji} {pos.symbol}: {pos.volume} lots | P/L: ${pos.profit:.2f} {pl_emoji}\n"
            
            if len(positions) > 5:
                message += f"... and {len(positions) - 5} more positions\n"
        
        message += f"""
━━━━━━━━━━━━━━━━━━━
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        self.send_message(message)
    
    def send_risk_alert(self, alert_type: str, details: Dict):
        """Send risk management alerts"""
        if not self.enabled:
            return
        
        if alert_type == 'DAILY_LOSS_LIMIT':
            message = f"""
🚨 <b>DAILY LOSS LIMIT REACHED</b> 🚨
━━━━━━━━━━━━━━━━━━━
📉 Daily Loss: <b>{details.get('loss_percent', 0):.2f}%</b>
💰 Current Balance: <b>${details.get('balance', 0):.2f}</b>
🛑 Trading Stopped for Today
⏰ Resume Tomorrow

⚠️ Risk Management Activated
        """
        elif alert_type == 'WEEKLY_LOSS_LIMIT':
            message = f"""
🚨 <b>WEEKLY LOSS LIMIT REACHED</b> 🚨
━━━━━━━━━━━━━━━━━━━
📉 Weekly Loss: <b>{details.get('loss_percent', 0):.2f}%</b>
💰 Current Balance: <b>${details.get('balance', 0):.2f}</b>
🛑 Trading Paused
⏰ Review Strategy Required

⚠️ Risk Management Activated
        """
        elif alert_type == 'HIGH_DRAWDOWN':
            message = f"""
⚠️ <b>HIGH DRAWDOWN ALERT</b> ⚠️
━━━━━━━━━━━━━━━━━━━
📉 Drawdown: <b>{details.get('drawdown', 0):.2f}%</b>
💰 Peak Balance: <b>${details.get('peak', 0):.2f}</b>
💵 Current: <b>${details.get('current', 0):.2f}</b>

⚠️ Consider reducing position sizes
        """
        else:
            return
        
        self.send_message(message)

class ForexFactoryNews:
    """Forex Factory News Calendar Integration"""
    
    def __init__(self, telegram_notifier: TelegramNotifier = None):
        self.telegram = telegram_notifier
        self.base_url = "https://www.forexfactory.com"
        self.calendar_url = f"{self.base_url}/calendar"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.high_impact_news = []
        self.last_update = None
        self.bangkok_tz = pytz.timezone('Asia/Bangkok')
        
        # Currency mapping for news filtering
        self.currency_mapping = {
            'USD': ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD', 'AUDUSD', 'NZDUSD', 'XAUUSD', 'US30', 'US500', 'NAS100', 'USOIL'],
            'EUR': ['EURUSD', 'EURGBP', 'EURJPY', 'EURCHF', 'EURAUD', 'EURNZD', 'EURCAD', 'XAUEUR', 'DE30'],
            'GBP': ['GBPUSD', 'EURGBP', 'GBPJPY', 'GBPCHF', 'GBPAUD', 'GBPNZD', 'GBPCAD', 'UK100'],
            'JPY': ['USDJPY', 'EURJPY', 'GBPJPY', 'AUDJPY', 'NZDJPY', 'CADJPY', 'CHFJPY', 'JP225'],
            'CHF': ['USDCHF', 'EURCHF', 'GBPCHF', 'CHFJPY'],
            'CAD': ['USDCAD', 'EURCAD', 'GBPCAD', 'CADJPY', 'AUDCAD', 'NZDCAD', 'USOIL', 'UKOIL'],
            'AUD': ['AUDUSD', 'EURAUD', 'GBPAUD', 'AUDJPY', 'AUDNZD', 'AUDCAD', 'AUDCHF', 'XAUUSD'],
            'NZD': ['NZDUSD', 'EURNZD', 'GBPNZD', 'NZDJPY', 'AUDNZD', 'NZDCAD', 'NZDCHF'],
            'CNY': ['USDCNH', 'CNHJPY'],
        }
        
        # High impact event keywords
        self.high_impact_keywords = [
            'NFP', 'Non-Farm', 'Interest Rate', 'FOMC', 'ECB', 'BOE', 'BOJ', 
            'GDP', 'CPI', 'Inflation', 'Retail Sales', 'Employment', 
            'PMI', 'Central Bank', 'Fed', 'Powell', 'Lagarde', 'Bailey',
            'Unemployment', 'Core PCE', 'PPI', 'ISM', 'Consumer Confidence'
        ]
        
        logger.info("ForexFactory news monitor initialized")
    
    def fetch_calendar(self, date: datetime = None) -> List[Dict]:
        """Fetch news calendar from ForexFactory"""
        try:
            if date is None:
                date = datetime.now()
            
            # Format date for URL (e.g., 'dec19.2024')
            date_str = date.strftime('%b%d.%Y').lower()
            url = f"{self.calendar_url}?day={date_str}"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Find calendar table
            calendar_table = soup.find('table', class_='calendar__table')
            if not calendar_table:
                logger.warning("Calendar table not found")
                return []
            
            news_events = []
            rows = calendar_table.find_all('tr', class_='calendar__row')
            
            current_date = None
            for row in rows:
                # Check if this is a date row
                date_cell = row.find('td', class_='calendar__date')
                if date_cell:
                    date_text = date_cell.get_text(strip=True)
                    if date_text:
                        current_date = self._parse_date(date_text)
                
                # Extract event data
                time_cell = row.find('td', class_='calendar__time')
                currency_cell = row.find('td', class_='calendar__currency')
                impact_cell = row.find('td', class_='calendar__impact')
                event_cell = row.find('td', class_='calendar__event')
                actual_cell = row.find('td', class_='calendar__actual')
                forecast_cell = row.find('td', class_='calendar__forecast')
                previous_cell = row.find('td', class_='calendar__previous')
                
                if time_cell and currency_cell and event_cell:
                    event_time = time_cell.get_text(strip=True)
                    
                    # Skip if no specific time
                    if event_time in ['', 'All Day', 'Tentative']:
                        continue
                    
                    # Parse impact level
                    impact = self._parse_impact(impact_cell) if impact_cell else 'low'
                    
                    event = {
                        'date': current_date,
                        'time': event_time,
                        'datetime': self._combine_datetime(current_date, event_time),
                        'currency': currency_cell.get_text(strip=True),
                        'impact': impact,
                        'event': event_cell.get_text(strip=True),
                        'actual': actual_cell.get_text(strip=True) if actual_cell else '',
                        'forecast': forecast_cell.get_text(strip=True) if forecast_cell else '',
                        'previous': previous_cell.get_text(strip=True) if previous_cell else ''
                    }
                    
                    news_events.append(event)
            
            self.last_update = datetime.now()
            logger.info(f"Fetched {len(news_events)} news events")
            
            return news_events
            
        except Exception as e:
            logger.error(f"Error fetching ForexFactory calendar: {e}")
            return []
    
    def _parse_date(self, date_text: str) -> str:
        """Parse date from ForexFactory format"""
        # ForexFactory uses format like "Thu Dec 19"
        try:
            # Add current year
            year = datetime.now().year
            date_with_year = f"{date_text} {year}"
            parsed_date = datetime.strptime(date_with_year, '%a %b %d %Y')
            return parsed_date.strftime('%Y-%m-%d')
        except:
            return datetime.now().strftime('%Y-%m-%d')
    
    def _parse_impact(self, impact_cell) -> str:
        """Parse impact level from cell"""
        if not impact_cell:
            return 'low'
        
        # Check for impact icons or classes
        impact_spans = impact_cell.find_all('span', class_='icon')
        
        # Count filled icons (high impact usually has 3 red icons)
        red_count = len([s for s in impact_spans if 'icon--red' in s.get('class', [])])
        orange_count = len([s for s in impact_spans if 'icon--orange' in s.get('class', [])])
        yellow_count = len([s for s in impact_spans if 'icon--yellow' in s.get('class', [])])
        
        if red_count >= 2:
            return 'high'
        elif orange_count >= 2 or red_count == 1:
            return 'medium'
        else:
            return 'low'
    
    def _combine_datetime(self, date_str: str, time_str: str) -> datetime:
        """Combine date and time into datetime object"""
        try:
            # Parse time (format: "2:00am" or "14:30")
            if not date_str or not time_str:
                return None
            
            # Combine date and time
            datetime_str = f"{date_str} {time_str}"
            
            # Try different formats
            for fmt in ['%Y-%m-%d %I:%M%p', '%Y-%m-%d %H:%M']:
                try:
                    dt = datetime.strptime(datetime_str, fmt)
                    # Assume EST timezone for ForexFactory
                    est_tz = pytz.timezone('US/Eastern')
                    dt = est_tz.localize(dt)
                    # Convert to Bangkok time
                    return dt.astimezone(self.bangkok_tz)
                except:
                    continue
            
            return None
            
        except Exception as e:
            logger.debug(f"Error parsing datetime: {e}")
            return None
    
    def get_upcoming_high_impact(self, hours_ahead: int = 1) -> List[Dict]:
        """Get upcoming high impact news within specified hours"""
        now = datetime.now(self.bangkok_tz)
        future_time = now + timedelta(hours=hours_ahead)
        
        # Update news if needed (every 30 minutes)
        if not self.last_update or (datetime.now() - self.last_update).seconds > 1800:
            self.high_impact_news = self.fetch_calendar()
        
        upcoming = []
        for event in self.high_impact_news:
            if event['impact'] == 'high' and event['datetime']:
                if now <= event['datetime'] <= future_time:
                    upcoming.append(event)
        
        return upcoming
    
    def check_news_for_symbols(self, symbols: List[str], hours_ahead: int = 1) -> Dict[str, List]:
        """Check if any symbols have upcoming high impact news"""
        affected_symbols = {}
        upcoming_news = self.get_upcoming_high_impact(hours_ahead)
        
        for event in upcoming_news:
            currency = event['currency']
            
            # Find affected symbols
            affected = []
            if currency in self.currency_mapping:
                for symbol in symbols:
                    if symbol in self.currency_mapping[currency]:
                        affected.append(symbol)
            
            # Add to affected symbols dict
            for symbol in affected:
                if symbol not in affected_symbols:
                    affected_symbols[symbol] = []
                affected_symbols[symbol].append(event)
        
        return affected_symbols
    
    def should_avoid_trading(self, symbol: str, minutes_before: int = 30, minutes_after: int = 30) -> Tuple[bool, str]:
        """Check if should avoid trading due to news"""
        now = datetime.now(self.bangkok_tz)
        
        # Get news for the symbol
        upcoming_news = self.get_upcoming_high_impact(hours_ahead=2)
        
        # Check which currencies affect this symbol
        affecting_currencies = []
        for currency, symbols in self.currency_mapping.items():
            if symbol in symbols:
                affecting_currencies.append(currency)
        
        for event in upcoming_news:
            if event['currency'] in affecting_currencies and event['datetime']:
                # Calculate time difference
                time_until = (event['datetime'] - now).total_seconds() / 60
                
                # Check if within avoidance window
                if -minutes_after <= time_until <= minutes_before:
                    return True, f"High impact news: {event['event']} ({event['currency']}) in {int(time_until)} min"
        
        return False, ""
    
    def send_news_alert(self, hours_ahead: int = 1):
        """Send upcoming news alert to Telegram"""
        if not self.telegram:
            return
        
        upcoming_news = self.get_upcoming_high_impact(hours_ahead)
        
        if not upcoming_news:
            return
        
        message = f"""
📰 <b>UPCOMING HIGH IMPACT NEWS</b> 📰
━━━━━━━━━━━━━━━━━━━
"""
        
        for event in upcoming_news[:5]:  # Limit to 5 events
            time_until = (event['datetime'] - datetime.now(self.bangkok_tz)).total_seconds() / 60
            
            if event['impact'] == 'high':
                impact_emoji = "🔴"
            elif event['impact'] == 'medium':
                impact_emoji = "🟠"
            else:
                impact_emoji = "🟡"
            
            message += f"""
{impact_emoji} <b>{event['currency']}</b> - {event['event']}
⏰ Time: {event['datetime'].strftime('%H:%M')} ({int(time_until)} min)
📊 Forecast: {event['forecast'] or 'N/A'}
📈 Previous: {event['previous'] or 'N/A'}
━━━━━━━━━━━━━━━━━━━"""
        
        # Add affected symbols
        all_symbols = set()
        for event in upcoming_news:
            if event['currency'] in self.currency_mapping:
                all_symbols.update(self.currency_mapping[event['currency']])
        
        if all_symbols:
            message += f"""

⚠️ <b>Affected Symbols:</b>
{', '.join(sorted(all_symbols)[:10])}

💡 <b>Recommendation:</b> 
Avoid new trades 30min before and after
"""
        
        self.telegram.send_message(message)
    
    def get_weekly_calendar(self) -> pd.DataFrame:
        """Get weekly calendar for analysis"""
        events = []
        
        # Fetch for next 7 days
        for i in range(7):
            date = datetime.now() + timedelta(days=i)
            daily_events = self.fetch_calendar(date)
            events.extend(daily_events)
        
        # Convert to DataFrame for analysis
        if events:
            df = pd.DataFrame(events)
            df = df[df['impact'].isin(['medium', 'high'])]
            return df
        
        return pd.DataFrame()

class MT5Connection:
    """MT5 Connection Manager - Supports both login and no-login modes"""

    def __init__(self, login: Optional[int] = None, password: Optional[str] = None, server: Optional[str] = None):
        self.login = login
        self.password = password
        self.server = server
        self.connected = False
        self.use_existing_terminal = (login is None or password is None or server is None)

    def connect(self) -> bool:
        """เชื่อมต่อกับ MT5 - รองรับทั้งแบบ login และไม่ login"""

        # Mode 1: Use existing MT5 terminal (no login required)
        if self.use_existing_terminal:
            logger.info("Connecting to existing MT5 terminal session...")

            # Try to initialize without login
            if not mt5.initialize():
                logger.error(f"MT5 initialize failed: {mt5.last_error()}")
                logger.info("Please ensure MT5 terminal is running and logged in")
                return False

            # Check if already logged in
            account_info = mt5.account_info()
            if account_info is None:
                logger.error("MT5 is not logged in. Please login to MT5 terminal first")
                mt5.shutdown()
                return False

            # Successfully connected to existing session
            self.connected = True
            logger.info(f"✅ Connected to existing MT5 session")
            logger.info(f"Account: {account_info.login}, Server: {account_info.server}")
            logger.info(f"Balance: ${account_info.balance:.2f}, Equity: ${account_info.equity:.2f}")
            return True

        # Mode 2: Login with credentials
        else:
            logger.info("Connecting to MT5 with login credentials...")

            if not mt5.initialize():
                logger.error(f"MT5 initialize failed: {mt5.last_error()}")
                return False

            # Login to MT5
            authorized = mt5.login(
                login=self.login,
                password=self.password,
                server=self.server
            )

            if authorized:
                self.connected = True
                account_info = mt5.account_info()
                logger.info(f"✅ Connected to MT5 with credentials")
                logger.info(f"Account: {account_info.login}, Balance: ${account_info.balance:.2f}")
                return True
            else:
                logger.error(f"Failed to connect: {mt5.last_error()}")
                return False

    def disconnect(self):
        """ตัดการเชื่อมต่อ MT5"""
        mt5.shutdown()
        self.connected = False
        logger.info("Disconnected from MT5")

class MarketDataMT5:
    """ดึงและวิเคราะห์ข้อมูลตลาดจาก MT5 with caching"""

    def __init__(self):
        self.symbols = ['EURUSDc', 'XAUUSDc']  # Broker symbols with 'c' suffix
        # Performance cache
        self._cache = {}
        self._cache_duration = 60  # Cache for 60 seconds
        self._indicator_cache = {}  # Cache calculated indicators
        
    def get_rates(self, symbol: str, timeframe: int, count: int) -> pd.DataFrame:
        """ดึงข้อมูลราคาจาก MT5 with caching"""
        # Create cache key
        cache_key = f"{symbol}_{timeframe}_{count}"
        current_time = time.time()

        # Check cache
        if cache_key in self._cache:
            cached_data, cache_time = self._cache[cache_key]
            if current_time - cache_time < self._cache_duration:
                return cached_data

        # Fetch new data
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)

        if rates is None:
            logger.error(f"Failed to get rates for {symbol}")
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)

        # Cache the data
        self._cache[cache_key] = (df.copy(), current_time)

        return df
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """คำนวณ Technical Indicators with caching"""
        if df.empty:
            return df

        # Create cache key from dataframe hash
        df_hash = pd.util.hash_pandas_object(df.iloc[-1]).values[0]
        cache_key = f"indicators_{df_hash}"

        # Check indicator cache
        if cache_key in self._indicator_cache:
            return self._indicator_cache[cache_key]
            
        # Price changes
        df['change_1h'] = df['close'].pct_change(1) * 100
        df['change_4h'] = df['close'].pct_change(4) * 100
        df['change_24h'] = df['close'].pct_change(24) * 100
        
        # Moving Averages
        df['sma_20'] = ta.trend.sma_indicator(df['close'], window=20)
        df['sma_50'] = ta.trend.sma_indicator(df['close'], window=50)
        df['ema_12'] = ta.trend.ema_indicator(df['close'], window=12)
        df['ema_26'] = ta.trend.ema_indicator(df['close'], window=26)
        
        # RSI
        df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
        
        # MACD
        macd = ta.trend.MACD(df['close'])
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_diff'] = macd.macd_diff()
        
        # Bollinger Bands
        bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2)
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_lower'] = bb.bollinger_lband()
        
        # ATR for stop loss calculation
        df['atr'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=14).average_true_range()
        
        # Stochastic
        stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'])
        df['stoch_k'] = stoch.stoch()
        df['stoch_d'] = stoch.stoch_signal()
        
        # Support and Resistance
        df['support'] = df['low'].rolling(window=20).min()
        df['resistance'] = df['high'].rolling(window=20).max()

        # Cache the calculated indicators
        self._indicator_cache[cache_key] = df.copy()

        # Clean old cache entries if too many
        if len(self._indicator_cache) > 100:
            # Remove oldest 50 entries
            keys_to_remove = list(self._indicator_cache.keys())[:50]
            for key in keys_to_remove:
                del self._indicator_cache[key]

        return df
    
    def get_market_analysis(self, symbol: str) -> Dict:
        """Multi-timeframe market analysis with advanced indicators"""
        # Multi-timeframe analysis (D1, H4, H1, M15, M5)
        df_d1 = self.get_rates(symbol, mt5.TIMEFRAME_D1, 100)
        df_h4 = self.get_rates(symbol, mt5.TIMEFRAME_H4, 100)
        df_h1 = self.get_rates(symbol, mt5.TIMEFRAME_H1, 100)
        df_m15 = self.get_rates(symbol, mt5.TIMEFRAME_M15, 100)
        df_m5 = self.get_rates(symbol, mt5.TIMEFRAME_M5, 100)

        # Calculate indicators for all timeframes
        df_d1 = self.calculate_indicators(df_d1) if not df_d1.empty else df_d1
        df_h4 = self.calculate_indicators(df_h4) if not df_h4.empty else df_h4
        df_h1 = self.calculate_indicators(df_h1) if not df_h1.empty else df_h1
        df_m15 = self.calculate_indicators(df_m15) if not df_m15.empty else df_m15
        df_m5 = self.calculate_indicators(df_m5) if not df_m5.empty else df_m5

        if df_h1.empty or df_m15.empty:
            return {}

        latest_d1 = df_d1.iloc[-1] if not df_d1.empty else None
        latest_h4 = df_h4.iloc[-1] if not df_h4.empty else None
        latest_h1 = df_h1.iloc[-1]
        latest_m15 = df_m15.iloc[-1]
        latest_m5 = df_m5.iloc[-1] if not df_m5.empty else None

        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)

        # Calculate advanced metrics
        market_structure = self._analyze_market_structure(df_h1)
        volume_profile = self._calculate_volume_profile(df_h1)
        key_levels = self._identify_key_levels(df_d1, df_h4, df_h1)
        momentum_score = self._calculate_momentum_score(df_h1, df_m15)

        return {
            'symbol': symbol,
            'current_price': symbol_info.bid,
            'ask': symbol_info.ask,
            'spread': symbol_info.spread,

            # Multi-timeframe data
            'trend_d1': self._determine_trend(df_d1) if not df_d1.empty else 'UNKNOWN',
            'trend_h4': self._determine_trend(df_h4) if not df_h4.empty else 'UNKNOWN',
            'trend_h1': self._determine_trend(df_h1),
            'trend_m15': self._determine_trend(df_m15),

            # RSI multi-timeframe
            'rsi_d1': latest_d1['rsi'] if latest_d1 is not None else 50,
            'rsi_h4': latest_h4['rsi'] if latest_h4 is not None else 50,
            'rsi_h1': latest_h1['rsi'],
            'rsi_m15': latest_m15['rsi'],
            'rsi_m5': latest_m5['rsi'] if latest_m5 is not None else 50,

            # MACD signals
            'macd_signal_h4': 'BUY' if latest_h4 is not None and latest_h4['macd'] > latest_h4['macd_signal'] else 'SELL',
            'macd_signal_h1': 'BUY' if latest_h1['macd'] > latest_h1['macd_signal'] else 'SELL',
            'macd_signal_m15': 'BUY' if latest_m15['macd'] > latest_m15['macd_signal'] else 'SELL',

            # Price changes
            'change_1h': latest_h1['change_1h'],
            'change_4h': latest_h1['change_4h'],
            'change_24h': latest_h1['change_24h'],

            # Volume and volatility
            'volume': latest_h1['tick_volume'],
            'volume_ma': df_h1['tick_volume'].rolling(20).mean().iloc[-1],
            'volume_ratio': latest_h1['tick_volume'] / df_h1['tick_volume'].rolling(20).mean().iloc[-1],
            'atr': latest_h1['atr'],
            'atr_h4': latest_h4['atr'] if latest_h4 is not None else latest_h1['atr'],

            # Support/Resistance
            'support_h1': latest_h1['support'],
            'resistance_h1': latest_h1['resistance'],
            'key_levels': key_levels,

            # Advanced indicators
            'bb_position': self._calculate_bb_position(latest_h1),
            'stoch_k': latest_h1['stoch_k'],
            'stoch_d': latest_h1['stoch_d'],
            'market_structure': market_structure,
            'volume_profile': volume_profile,
            'momentum_score': momentum_score,

            # Session and timing
            'market_session': self._get_market_session(),
            'session_high': df_h1['high'].rolling(24).max().iloc[-1],  # Session high
            'session_low': df_h1['low'].rolling(24).min().iloc[-1],    # Session low
        }
    
    def _calculate_bb_position(self, data) -> str:
        """คำนวณตำแหน่งราคาใน Bollinger Bands"""
        price = data['close']
        if price > data['bb_upper']:
            return 'ABOVE_UPPER'
        elif price < data['bb_lower']:
            return 'BELOW_LOWER'
        else:
            position = (price - data['bb_lower']) / (data['bb_upper'] - data['bb_lower'])
            if position > 0.7:
                return 'NEAR_UPPER'
            elif position < 0.3:
                return 'NEAR_LOWER'
            else:
                return 'MIDDLE'
    
    def _determine_trend(self, df: pd.DataFrame) -> str:
        """กำหนด trend จาก moving averages"""
        latest = df.iloc[-1]
        if latest['sma_20'] > latest['sma_50'] and latest['close'] > latest['sma_20']:
            return 'UPTREND'
        elif latest['sma_20'] < latest['sma_50'] and latest['close'] < latest['sma_20']:
            return 'DOWNTREND'
        else:
            return 'SIDEWAYS'
    
    def _get_market_session(self) -> str:
        """ระบุ market session ปัจจุบัน"""
        now = datetime.now()
        hour = now.hour

        if 7 <= hour < 16:  # Asian Session (Bangkok time)
            return 'ASIAN'
        elif 14 <= hour < 23:  # European Session
            return 'EUROPEAN'
        elif 20 <= hour or hour < 5:  # US Session
            return 'US'
        else:
            return 'INTER_SESSION'

    def _analyze_market_structure(self, df: pd.DataFrame) -> Dict:
        """Analyze market structure (Higher Highs/Lows)"""
        if df.empty or len(df) < 20:
            return {'type': 'UNKNOWN', 'strength': 0}

        # Find swing points
        highs = df['high'].rolling(5).max()
        lows = df['low'].rolling(5).min()

        # Check last 3 swing points
        recent_highs = highs.tail(15).dropna()
        recent_lows = lows.tail(15).dropna()

        # Determine structure
        if len(recent_highs) > 2 and len(recent_lows) > 2:
            if recent_highs.iloc[-1] > recent_highs.iloc[-2] and recent_lows.iloc[-1] > recent_lows.iloc[-2]:
                return {'type': 'BULLISH', 'strength': 0.8}
            elif recent_highs.iloc[-1] < recent_highs.iloc[-2] and recent_lows.iloc[-1] < recent_lows.iloc[-2]:
                return {'type': 'BEARISH', 'strength': 0.8}

        return {'type': 'RANGING', 'strength': 0.5}

    def _calculate_volume_profile(self, df: pd.DataFrame) -> Dict:
        """Calculate volume profile for price levels"""
        if df.empty:
            return {'poc': 0, 'high_volume_zone': []}

        # Price levels
        price_range = df['close'].max() - df['close'].min()
        levels = 20
        step = price_range / levels

        volume_at_price = {}
        for i in range(levels):
            level = df['close'].min() + (i * step)
            mask = (df['close'] >= level) & (df['close'] < level + step)
            volume_at_price[level] = df.loc[mask, 'tick_volume'].sum()

        # Point of Control (POC) - highest volume price
        poc = max(volume_at_price, key=volume_at_price.get)

        return {
            'poc': poc,
            'high_volume_zone': [k for k, v in volume_at_price.items() if v > np.mean(list(volume_at_price.values()))]
        }

    def _identify_key_levels(self, df_d1: pd.DataFrame, df_h4: pd.DataFrame, df_h1: pd.DataFrame) -> List[float]:
        """Identify key support/resistance levels from multiple timeframes"""
        levels = []

        # Daily levels
        if not df_d1.empty and len(df_d1) > 20:
            levels.append(df_d1['high'].rolling(20).max().iloc[-1])
            levels.append(df_d1['low'].rolling(20).min().iloc[-1])
            levels.append(df_d1['close'].rolling(50).mean().iloc[-1])

        # H4 levels
        if not df_h4.empty and len(df_h4) > 20:
            levels.append(df_h4['high'].rolling(20).max().iloc[-1])
            levels.append(df_h4['low'].rolling(20).min().iloc[-1])

        # H1 levels
        if not df_h1.empty and len(df_h1) > 20:
            # Fibonacci levels
            high = df_h1['high'].max()
            low = df_h1['low'].min()
            diff = high - low
            levels.extend([
                low + diff * 0.236,  # 23.6%
                low + diff * 0.382,  # 38.2%
                low + diff * 0.5,    # 50%
                low + diff * 0.618,  # 61.8%
            ])

        # Remove duplicates and sort
        levels = sorted(list(set([round(l, 5) for l in levels if l > 0])))

        return levels

    def _calculate_momentum_score(self, df_h1: pd.DataFrame, df_m15: pd.DataFrame) -> float:
        """Calculate overall momentum score (0-100)"""
        score = 50  # Neutral

        if df_h1.empty or df_m15.empty:
            return score

        latest_h1 = df_h1.iloc[-1]
        latest_m15 = df_m15.iloc[-1]

        # RSI momentum
        if latest_h1['rsi'] > 70:
            score += 15
        elif latest_h1['rsi'] < 30:
            score -= 15
        else:
            score += (latest_h1['rsi'] - 50) * 0.3

        # MACD momentum
        if latest_h1['macd'] > latest_h1['macd_signal']:
            score += 10
        else:
            score -= 10

        # Price vs MA
        if latest_h1['close'] > latest_h1['sma_20']:
            score += 10
        else:
            score -= 10

        # Volume momentum
        vol_ma = df_h1['tick_volume'].rolling(20).mean().iloc[-1]
        if latest_h1['tick_volume'] > vol_ma * 1.5:
            score += 10
        elif latest_h1['tick_volume'] < vol_ma * 0.5:
            score -= 10

        # Clamp between 0-100
        score = max(0, min(100, score))

        return score

class GeminiTradingAI:
    """Gemini AI for Trading Decisions"""
    
    def __init__(self, api_key: str, news_checker: 'ForexFactoryNews' = None):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        self.news_checker = news_checker
        
    def analyze_and_decide(self, market_data: Dict) -> Dict:
        """วิเคราะห์และตัดสินใจเทรดด้วย Gemini"""
        
        # Check for upcoming news if news checker is available
        news_warning = ""
        if self.news_checker:
            avoid_trading, reason = self.news_checker.should_avoid_trading(
                market_data['symbol'], 
                minutes_before=30, 
                minutes_after=30
            )
            if avoid_trading:
                news_warning = f"\nNEWS WARNING: {reason}\nConsider avoiding new trades or reduce position size."
        
        prompt = f"""
        You are an elite forex trader with 20+ years experience analyzing {market_data['symbol']} using multi-timeframe analysis.

        MULTI-TIMEFRAME ANALYSIS:
        Symbol: {market_data['symbol']}
        Current Price: {market_data['current_price']:.5f}
        Spread: {market_data['spread']} points

        TREND ALIGNMENT (D1 → H4 → H1 → M15):
        - Daily Trend: {market_data.get('trend_d1', 'UNKNOWN')}
        - H4 Trend: {market_data.get('trend_h4', 'UNKNOWN')}
        - H1 Trend: {market_data.get('trend_h1', 'UNKNOWN')}
        - M15 Trend: {market_data.get('trend_m15', 'UNKNOWN')}

        RSI DIVERGENCE CHECK:
        - RSI D1: {market_data.get('rsi_d1', 50):.1f}
        - RSI H4: {market_data.get('rsi_h4', 50):.1f}
        - RSI H1: {market_data.get('rsi_h1', 50):.1f}
        - RSI M15: {market_data.get('rsi_m15', 50):.1f}
        - RSI M5: {market_data.get('rsi_m5', 50):.1f}

        MOMENTUM ANALYSIS:
        - MACD H4: {market_data.get('macd_signal_h4', 'NEUTRAL')}
        - MACD H1: {market_data.get('macd_signal_h1', 'NEUTRAL')}
        - MACD M15: {market_data.get('macd_signal_m15', 'NEUTRAL')}
        - Momentum Score: {market_data.get('momentum_score', 50):.0f}/100

        MARKET STRUCTURE:
        - Structure Type: {market_data.get('market_structure', {}).get('type', 'UNKNOWN')}
        - Structure Strength: {market_data.get('market_structure', {}).get('strength', 0)*100:.0f}%
        - Session High: {market_data.get('session_high', 0):.5f}
        - Session Low: {market_data.get('session_low', 0):.5f}

        VOLUME ANALYSIS:
        - Current Volume: {market_data.get('volume', 0)}
        - Volume MA: {market_data.get('volume_ma', 0):.0f}
        - Volume Ratio: {market_data.get('volume_ratio', 1):.2f}x
        - Point of Control: {market_data.get('volume_profile', {}).get('poc', 0):.5f}

        KEY LEVELS:
        - Support H1: {market_data.get('support_h1', 0):.5f}
        - Resistance H1: {market_data.get('resistance_h1', 0):.5f}
        - Fibonacci Levels: {market_data.get('key_levels', [])}

        VOLATILITY:
        - ATR H1: {market_data.get('atr', 0):.5f}
        - ATR H4: {market_data.get('atr_h4', 0):.5f}
        - Bollinger Position: {market_data.get('bb_position', 'MIDDLE')}

        PRICE ACTION:
        - 1H Change: {market_data.get('change_1h', 0):.2f}%
        - 4H Change: {market_data.get('change_4h', 0):.2f}%
        - 24H Change: {market_data.get('change_24h', 0):.2f}%
        - Stochastic: K={market_data.get('stoch_k', 50):.1f}, D={market_data.get('stoch_d', 50):.1f}

        SESSION & TIMING:
        - Current Session: {market_data.get('market_session', 'UNKNOWN')}
        {news_warning}

        ADVANCED TRADING RULES:
        1. TREND ALIGNMENT: All timeframes should align for highest confidence
        2. ENTRY TIMING: Use M5/M15 for precise entry after H1/H4 signal
        3. VOLUME CONFIRMATION: Above-average volume (>1.5x) validates breakouts
        4. STRUCTURE RULES: Only trade with market structure (BULLISH=BUY, BEARISH=SELL)
        5. KEY LEVELS: Respect major support/resistance and fibonacci levels
        6. RISK MANAGEMENT:
           - Conservative: 60-70% confidence = 0.5% risk
           - Standard: 70-85% confidence = 1% risk
           - Aggressive: 85%+ confidence = 1.5% risk
        7. PARTIAL PROFITS:
           - TP1: 1:1 RR (close 50%)
           - TP2: 1:2 RR (close 30%)
           - TP3: 1:3+ RR (runner with trailing)

        CONFLUENCE SCORING (check all that apply):
        ✓ Trend alignment across 3+ timeframes (+20 confidence)
        ✓ RSI divergence/convergence confirmation (+10)
        ✓ Volume above average (+10)
        ✓ Price at key level (+15)
        ✓ Market structure aligned (+15)
        ✓ MACD confirmation on multiple timeframes (+10)
        ✓ Session appropriate for symbol (+10)
        ✓ No conflicting news events (+10)

        Provide your trading decision in JSON format:
        {{
            "decision": "BUY/SELL/HOLD",
            "confidence": 0-100,
            "entry_price": exact_price,
            "stop_loss": based_on_structure_or_atr,
            "take_profit_1": 1:1_risk_reward,
            "take_profit_2": 1:2_risk_reward,
            "take_profit_3": 1:3+_risk_reward,
            "position_size_percent": 0.5-2,
            "reasoning": "Detailed confluence analysis",
            "key_levels": [important_prices],
            "risk_factors": [identified_risks],
            "time_horizon": "SHORT(M5-M15)/MEDIUM(H1-H4)/LONG(D1)",
            "entry_trigger": "Specific condition to enter",
            "invalidation": "What would invalidate this setup"
        }}

        Only suggest trades with 60%+ confluence. If news warning present, require 80%+ confidence.
        """
        
        try:
            response = self.model.generate_content(prompt)
            
            # Extract JSON from response
            json_str = response.text
            if '```json' in json_str:
                json_str = json_str.split('```json')[1].split('```')[0]
            elif '```' in json_str:
                json_str = json_str.split('```')[1].split('```')[0]
            
            decision = json.loads(json_str.strip())
            
            # Validate decision
            if self._validate_decision(decision, market_data):
                return decision
            else:
                logger.warning("Invalid decision from Gemini, returning HOLD")
                return {"decision": "HOLD", "confidence": 0}
                
        except Exception as e:
            logger.error(f"Error in Gemini analysis: {e}")
            return {"decision": "HOLD", "confidence": 0}
    
    def _validate_decision(self, decision: Dict, market_data: Dict) -> bool:
        """ตรวจสอบความถูกต้องของการตัดสินใจ"""
        if decision['decision'] == 'HOLD':
            return True
            
        # Check if all required fields exist
        required_fields = ['decision', 'confidence', 'entry_price', 'stop_loss', 'take_profit_1']
        if not all(field in decision for field in required_fields):
            return False
        
        # Check confidence level
        if decision['confidence'] < 60:
            logger.info(f"Low confidence signal: {decision['confidence']}%")
            return False
        
        # Check risk-reward ratio
        if decision['decision'] in ['BUY', 'SELL']:
            risk = abs(decision['entry_price'] - decision['stop_loss'])
            reward = abs(decision['take_profit_1'] - decision['entry_price'])
            
            if reward < risk * 1.5:  # Minimum 1:1.5 RR ratio
                logger.info(f"Poor risk-reward ratio: {reward/risk:.2f}")
                return False
        
        return True

class RiskManager:
    """Risk Management System"""
    
    def __init__(self, initial_balance: float, config: Dict = None):
        self.initial_balance = initial_balance
        
        # Default risk parameters (Conservative)
        default_config = {
            'max_risk_per_trade': 0.01,  # 1% per trade (ลดจาก 2%)
            'max_daily_loss': 0.03,  # 3% daily loss limit (ลดจาก 6%)
            'max_weekly_loss': 0.05,  # 5% weekly loss limit (เพิ่มใหม่)
            'max_open_trades': 5,  # เพิ่มจาก 3 เป็น 5
            'max_correlation_trades': 2,  # จำกัด trades ที่มี correlation สูง
            'risk_free_profit_lock': 0.5,  # ย้าย SL ที่ break even เมื่อกำไร 50% ของ TP
            'trailing_stop_activation': 1.5,  # เริ่ม trail เมื่อกำไร 1.5:1 RR
            'position_size_by_confidence': {  # ปรับ size ตาม confidence
                90: 1.0,   # 90%+ = full size
                80: 0.75,  # 80-89% = 75% size
                70: 0.5,   # 70-79% = 50% size
                60: 0.25   # 60-69% = 25% size
            }
        }
        
        # Merge with custom config
        if config:
            default_config.update(config)
        
        self.max_risk_per_trade = default_config['max_risk_per_trade']
        self.max_daily_loss = default_config['max_daily_loss']
        self.max_weekly_loss = default_config['max_weekly_loss']
        self.max_open_trades = default_config['max_open_trades']
        self.max_correlation_trades = default_config['max_correlation_trades']
        self.risk_free_profit_lock = default_config['risk_free_profit_lock']
        self.trailing_stop_activation = default_config['trailing_stop_activation']
        self.position_size_by_confidence = default_config['position_size_by_confidence']
        
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.open_trades = {}
        self.correlation_groups = {
            'USD_pairs': ['EURUSD', 'GBPUSD', 'USDCHF', 'USDJPY', 'USDCAD', 'AUDUSD', 'NZDUSD'],
            'EUR_pairs': ['EURUSD', 'EURGBP', 'EURJPY', 'EURCHF', 'EURAUD', 'EURNZD', 'EURCAD'],
            'GOLD': ['XAUUSD', 'XAUEUR'],
            'OIL': ['USOIL', 'UKOIL', 'WTI', 'BRENT'],
            'INDICES': ['US30', 'US500', 'NAS100', 'DE30', 'UK100', 'JP225']
        }
        
    def calculate_lot_size(self, symbol: str, entry: float, stop_loss: float, 
                          confidence: int, account_balance: float) -> float:
        """คำนวณขนาด Lot ตามความเสี่ยง"""
        
        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return 0.0
        
        # Base risk amount
        risk_amount = account_balance * self.max_risk_per_trade
        
        # Adjust by confidence level using tiered system
        confidence_multiplier = 0.25  # Default minimum
        for conf_threshold, multiplier in sorted(self.position_size_by_confidence.items(), reverse=True):
            if confidence >= conf_threshold:
                confidence_multiplier = multiplier
                break
        
        risk_amount *= confidence_multiplier
        
        # Further adjust risk for different asset classes
        if 'XAU' in symbol or 'GOLD' in symbol:
            risk_amount *= 0.7  # ลด risk สำหรับทองคำ (volatility สูง)
        elif symbol in ['US30', 'US500', 'NAS100', 'DE30', 'UK100', 'JP225']:
            risk_amount *= 0.8  # ลด risk สำหรับ indices
        elif symbol in ['USOIL', 'UKOIL', 'WTI', 'BRENT']:
            risk_amount *= 0.6  # ลด risk สำหรับน้ำมัน (volatility สูงมาก)
        elif symbol in ['BTCUSD', 'ETHUSD']:
            risk_amount *= 0.5  # ลด risk สำหรับ crypto
        
        # Calculate pip difference
        point = symbol_info.point
        if 'XAU' in symbol or 'GOLD' in symbol:
            pip_value = point * 10  # Gold pip value
        elif '_' not in symbol and len(symbol) == 6:  # Forex pairs
            pip_value = point * 10
        else:  # Indices, commodities
            pip_value = point
        
        pip_difference = abs(entry - stop_loss) / pip_value
        
        # Calculate lot size
        contract_size = symbol_info.trade_contract_size
        tick_value = symbol_info.trade_tick_value
        
        if pip_difference > 0:
            lot_size = risk_amount / (pip_difference * tick_value)
        else:
            lot_size = symbol_info.volume_min
        
        # Apply symbol-specific limits
        max_lot_by_symbol = {
            'XAUUSD': 0.5,    # Max 0.5 lot for gold
            'XAUEUR': 0.5,
            'US30': 0.3,      # Max 0.3 lot for indices
            'US500': 0.3,
            'NAS100': 0.3,
            'BTCUSD': 0.1,    # Max 0.1 lot for crypto
            'ETHUSD': 0.1,
            'USOIL': 0.3,     # Max 0.3 lot for oil
            'UKOIL': 0.3
        }
        
        if symbol in max_lot_by_symbol:
            lot_size = min(lot_size, max_lot_by_symbol[symbol])
        
        # Apply broker limits
        lot_size = max(symbol_info.volume_min, min(lot_size, symbol_info.volume_max))
        
        # Round to step
        volume_step = symbol_info.volume_step
        lot_size = round(lot_size / volume_step) * volume_step
        
        return round(lot_size, 2)
    
    def check_daily_loss_limit(self) -> bool:
        """ตรวจสอบ daily loss limit"""
        account_info = mt5.account_info()
        current_balance = account_info.balance
        
        daily_loss_percent = (self.initial_balance - current_balance) / self.initial_balance
        
        if daily_loss_percent >= self.max_daily_loss:
            logger.warning(f"Daily loss limit reached: {daily_loss_percent:.2%}")
            return False
        return True
    
    def check_weekly_loss_limit(self) -> bool:
        """ตรวจสอบ weekly loss limit"""
        # This should track weekly P&L properly in production
        # For now, using a simplified check
        account_info = mt5.account_info()
        current_balance = account_info.balance
        
        weekly_loss_percent = (self.initial_balance - current_balance) / self.initial_balance
        
        if weekly_loss_percent >= self.max_weekly_loss:
            logger.warning(f"Weekly loss limit reached: {weekly_loss_percent:.2%}")
            return False
        return True
    
    def check_correlation_limit(self, symbol: str) -> bool:
        """ตรวจสอบ correlation limit"""
        positions = mt5.positions_get()
        if not positions:
            return True
        
        # Find which correlation group this symbol belongs to
        symbol_groups = []
        for group, symbols in self.correlation_groups.items():
            if symbol in symbols:
                symbol_groups.append(group)
        
        # Count positions in the same correlation group
        correlated_positions = 0
        for position in positions:
            for group in symbol_groups:
                if position.symbol in self.correlation_groups.get(group, []):
                    correlated_positions += 1
                    break
        
        if correlated_positions >= self.max_correlation_trades:
            logger.warning(f"Correlation limit reached for {symbol}: {correlated_positions} positions")
            return False
        
        return True
    
    def can_open_trade(self, symbol: str = None) -> Tuple[bool, str]:
        """ตรวจสอบว่าสามารถเปิด trade ใหม่ได้หรือไม่"""
        if not self.check_daily_loss_limit():
            return False, "Daily loss limit reached"
        
        if not self.check_weekly_loss_limit():
            return False, "Weekly loss limit reached"
            
        positions = mt5.positions_get()
        if positions and len(positions) >= self.max_open_trades:
            return False, f"Maximum open trades reached: {len(positions)}"
        
        if symbol and not self.check_correlation_limit(symbol):
            return False, f"Correlation limit reached for {symbol}"
            
        return True, "Can open trade"

class MT5TradingExecutor:
    """Execute trades on MT5"""
    
    def __init__(self, risk_manager: RiskManager, telegram_notifier: TelegramNotifier = None):
        self.risk_manager = risk_manager
        self.telegram = telegram_notifier
        self.magic_number = 234000  # Unique identifier for our trades
        
    def execute_trade(self, signal: Dict, symbol: str) -> bool:
        """Execute trade based on signal"""
        
        if signal['decision'] == 'HOLD':
            logger.info(f"Holding position for {symbol}")
            return False
        
        # Send signal alert to Telegram
        if self.telegram:
            self.telegram.send_trade_alert('SIGNAL', signal, symbol)
        
        # Check if we can open trade with enhanced checks
        can_trade, reason = self.risk_manager.can_open_trade(symbol)
        if not can_trade:
            logger.warning(f"Cannot open trade for {symbol}: {reason}")
            if self.telegram:
                self.telegram.send_message(f"⚠️ Trade rejected for {symbol}: {reason}")
            return False
        
        # Get account info
        account_info = mt5.account_info()
        if not account_info:
            logger.error("Cannot get account info")
            return False
        
        # Calculate lot size
        lot_size = self.risk_manager.calculate_lot_size(
            symbol=symbol,
            entry=signal['entry_price'],
            stop_loss=signal['stop_loss'],
            confidence=signal['confidence'],
            account_balance=account_info.balance
        )
        
        if lot_size <= 0:
            logger.error(f"Invalid lot size: {lot_size}")
            if self.telegram:
                self.telegram.send_trade_alert('ERROR', signal, symbol, 
                                              result={'error': 'Invalid lot size'})
            return False
        
        # Prepare order request
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            logger.error(f"Symbol {symbol} not found")
            return False
        
        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                logger.error(f"Failed to select {symbol}")
                return False
        
        # Determine order type
        order_type = mt5.ORDER_TYPE_BUY if signal['decision'] == 'BUY' else mt5.ORDER_TYPE_SELL
        
        # Get current price
        price = mt5.symbol_info_tick(symbol).ask if signal['decision'] == 'BUY' else mt5.symbol_info_tick(symbol).bid
        
        # Create order request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": order_type,
            "price": price,
            "sl": signal['stop_loss'],
            "tp": signal['take_profit_1'],
            "deviation": 20,
            "magic": self.magic_number,
            "comment": f"Gemini AI Trade - Conf: {signal['confidence']}%",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Send order
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order failed: {result.retcode}, {result.comment}")
            if self.telegram:
                self.telegram.send_trade_alert('ERROR', signal, symbol, lot_size,
                                              {'error': result.comment, 'code': result.retcode})
            return False
        
        logger.info(f"Order executed successfully: {symbol} {signal['decision']} {lot_size} lots")
        logger.info(f"Order details: {result}")
        
        # Send success alert to Telegram
        if self.telegram:
            self.telegram.send_trade_alert('OPENED', signal, symbol, lot_size, 
                                          {'order': result.order, 'price': result.price})
        
        # Log trade details
        self._log_trade(signal, symbol, lot_size, result)
        
        return True
    
    def _log_trade(self, signal: Dict, symbol: str, lot_size: float, result):
        """Log trade details"""
        trade_log = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'decision': signal['decision'],
            'confidence': signal['confidence'],
            'lot_size': lot_size,
            'entry_price': result.price,
            'stop_loss': signal['stop_loss'],
            'take_profit': signal['take_profit_1'],
            'reasoning': signal.get('reasoning', ''),
            'order_ticket': result.order
        }
        
        # Save to file
        with open('trades.json', 'a') as f:
            f.write(json.dumps(trade_log) + '\n')
    
    def manage_open_positions(self, gemini_ai: GeminiTradingAI, market_data_provider: MarketDataMT5):
        """Enhanced position management with partial close and advanced trailing"""
        positions = mt5.positions_get()

        if not positions:
            return

        for position in positions:
            if position.magic != self.magic_number:
                continue

            # Get current price and symbol info
            symbol_info = mt5.symbol_info(position.symbol)
            current_price = mt5.symbol_info_tick(position.symbol).bid if position.type == 0 else mt5.symbol_info_tick(position.symbol).ask

            # Calculate profit metrics
            pip_value = symbol_info.point * 10 if 'JPY' not in position.symbol else symbol_info.point * 100
            pips_profit = (current_price - position.price_open) / pip_value * (1 if position.type == 0 else -1)
            risk_amount = abs(position.price_open - position.sl) / pip_value if position.sl > 0 else 0
            rr_ratio = pips_profit / risk_amount if risk_amount > 0 else 0

            # Check position metadata for partial close tracking
            position_metadata = self._get_position_metadata(position.ticket)

            # PARTIAL CLOSE STRATEGY
            # TP1: Close 50% at 1:1 RR
            if rr_ratio >= 1.0 and not position_metadata.get('tp1_closed', False):
                self._partial_close(position, 0.5, "TP1 - 1:1 RR")
                self._update_position_metadata(position.ticket, 'tp1_closed', True)

            # TP2: Close 30% more at 2:1 RR
            elif rr_ratio >= 2.0 and not position_metadata.get('tp2_closed', False):
                remaining = position.volume * 0.3
                self._partial_close(position, remaining, "TP2 - 2:1 RR")
                self._update_position_metadata(position.ticket, 'tp2_closed', True)

            # TP3: Let 20% run with trailing stop
            elif rr_ratio >= 3.0:
                self._advanced_trail_stop(position, current_price, rr_ratio)

            # BREAK-EVEN MANAGEMENT
            elif rr_ratio >= 0.5 and not position_metadata.get('be_set', False):
                # Move stop loss to break-even when 50% to TP1
                self._set_break_even(position)
                self._update_position_metadata(position.ticket, 'be_set', True)

            # DYNAMIC TRAILING STOP based on ATR
            if pips_profit > 0:
                self._dynamic_trail_stop(position, current_price, market_data_provider)
    
    def _trail_stop_loss(self, position, current_price: float):
        """Trail stop loss for profitable positions"""
        symbol_info = mt5.symbol_info(position.symbol)
        
        # Calculate new stop loss (trail by 50% of profit)
        if position.type == 0:  # BUY
            new_sl = position.price_open + (current_price - position.price_open) * 0.5
            if new_sl > position.sl:
                self._modify_position(position.ticket, new_sl, position.tp)
        else:  # SELL
            new_sl = position.price_open - (position.price_open - current_price) * 0.5
            if new_sl < position.sl:
                self._modify_position(position.ticket, new_sl, position.tp)
    
    def _modify_position(self, ticket: int, sl: float, tp: float):
        """Modify position SL/TP"""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": sl,
            "tp": tp,
        }
        
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Position {ticket} modified: SL={sl}")
            if self.telegram:
                # Get position info for symbol
                position = mt5.positions_get(ticket=ticket)
                symbol = position[0].symbol if position else "Unknown"
                self.telegram.send_trade_alert('MODIFIED', {}, symbol, 
                                              result={'ticket': ticket, 'sl': sl, 'tp': tp})
    
    def _partial_close(self, position, volume_to_close, reason: str) -> bool:
        """Partially close a position"""
        if volume_to_close > position.volume:
            volume_to_close = position.volume

        close_type = mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(position.symbol).bid if position.type == 0 else mt5.symbol_info_tick(position.symbol).ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": round(volume_to_close, 2),
            "type": close_type,
            "position": position.ticket,
            "price": price,
            "deviation": 20,
            "magic": self.magic_number,
            "comment": f"Partial close: {reason}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Partially closed {volume_to_close} lots of position {position.ticket}: {reason}")
            if self.telegram:
                message = f"⚡ PARTIAL CLOSE: {position.symbol}\n"
                message += f"Volume: {volume_to_close} lots\n"
                message += f"Reason: {reason}\n"
                message += f"Profit: ${position.profit * (volume_to_close/position.volume):.2f}"
                self.telegram.send_message(message)
            return True
        return False

    def _set_break_even(self, position) -> bool:
        """Move stop loss to break-even"""
        # Add small buffer for spread/commission
        buffer = mt5.symbol_info(position.symbol).point * 2
        new_sl = position.price_open + buffer if position.type == 0 else position.price_open - buffer

        if (position.type == 0 and new_sl > position.sl) or (position.type == 1 and new_sl < position.sl):
            return self._modify_position(position.ticket, new_sl, position.tp)
        return False

    def _advanced_trail_stop(self, position, current_price: float, rr_ratio: float):
        """Advanced trailing stop based on RR ratio"""
        symbol_info = mt5.symbol_info(position.symbol)
        atr_trail = symbol_info.point * 20  # Default ATR-based trail

        # Dynamic trailing based on RR achieved
        if rr_ratio >= 5:
            trail_distance = (current_price - position.price_open) * 0.7  # Trail 70% of profit
        elif rr_ratio >= 3:
            trail_distance = (current_price - position.price_open) * 0.6  # Trail 60% of profit
        else:
            trail_distance = (current_price - position.price_open) * 0.5  # Trail 50% of profit

        if position.type == 0:  # BUY
            new_sl = current_price - abs(trail_distance)
            if new_sl > position.sl:
                self._modify_position(position.ticket, new_sl, position.tp)
        else:  # SELL
            new_sl = current_price + abs(trail_distance)
            if new_sl < position.sl:
                self._modify_position(position.ticket, new_sl, position.tp)

    def _dynamic_trail_stop(self, position, current_price: float, market_data_provider: MarketDataMT5):
        """Dynamic trailing stop based on ATR"""
        try:
            # Get recent ATR for dynamic trailing
            df = market_data_provider.get_rates(position.symbol, mt5.TIMEFRAME_H1, 50)
            if not df.empty:
                df = market_data_provider.calculate_indicators(df)
                current_atr = df['atr'].iloc[-1]

                # Trail at 2x ATR distance
                trail_distance = current_atr * 2

                if position.type == 0:  # BUY
                    new_sl = current_price - trail_distance
                    if new_sl > position.sl and new_sl > position.price_open:
                        self._modify_position(position.ticket, new_sl, position.tp)
                else:  # SELL
                    new_sl = current_price + trail_distance
                    if new_sl < position.sl and new_sl < position.price_open:
                        self._modify_position(position.ticket, new_sl, position.tp)
        except Exception as e:
            logger.error(f"Error in dynamic trail stop: {e}")

    # Position metadata management
    _position_metadata = {}

    def _get_position_metadata(self, ticket: int) -> Dict:
        """Get metadata for a position"""
        return self._position_metadata.get(ticket, {})

    def _update_position_metadata(self, ticket: int, key: str, value):
        """Update metadata for a position"""
        if ticket not in self._position_metadata:
            self._position_metadata[ticket] = {}
        self._position_metadata[ticket][key] = value

    def close_position(self, position) -> bool:
        """Close a specific position"""
        # Close position
        close_type = mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(position.symbol).bid if position.type == 0 else mt5.symbol_info_tick(position.symbol).ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": close_type,
            "position": position.ticket,
            "price": price,
            "deviation": 20,
            "magic": self.magic_number,
            "comment": "Position closed by bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Closed position {position.ticket}")
            if self.telegram:
                self.telegram.send_trade_alert('CLOSED', {}, position.symbol,
                                              result={'order': position.ticket, 
                                                     'price': price,
                                                     'profit': position.profit})
            return True
        return False

class TradingBot:
    """Main Trading Bot Controller"""

    def __init__(self, mt5_login: Optional[int] = None, mt5_password: Optional[str] = None,
                 mt5_server: Optional[str] = None, gemini_api_key: str = None,
                 telegram_token: str = None, telegram_chat_id: str = None, config: Dict = None):
        # Initialize components - Support no-login mode
        self.mt5_conn = MT5Connection(mt5_login, mt5_password, mt5_server)
        self.market_data = MarketDataMT5()
        
        # Initialize Telegram notifier first
        self.telegram = TelegramNotifier(telegram_token, telegram_chat_id) if telegram_token else None
        
        # Initialize news checker
        self.news_checker = ForexFactoryNews(self.telegram)
        
        # Initialize Gemini AI with news checker
        self.gemini_ai = GeminiTradingAI(gemini_api_key, self.news_checker)
        
        self.risk_manager = None  # Will be initialized after connection
        self.executor = None  # Will be initialized after connection
        
        # Default configuration
        default_config = {
            'symbols': {
                # Major Forex Pairs
                'EURUSDc': {'enabled': True, 'max_spread': 20},  # Broker symbol
                # 'GBPUSD': {'enabled': True, 'max_spread': 30},
                # 'USDJPY': {'enabled': True, 'max_spread': 20},
                # 'USDCHF': {'enabled': True, 'max_spread': 25},
                # 'USDCAD': {'enabled': True, 'max_spread': 25},
                # 'AUDUSD': {'enabled': True, 'max_spread': 25},
                # 'NZDUSD': {'enabled': True, 'max_spread': 30},
                
                # # Cross Pairs
                # 'EURGBP': {'enabled': True, 'max_spread': 30},
                # 'EURJPY': {'enabled': True, 'max_spread': 30},
                # 'GBPJPY': {'enabled': True, 'max_spread': 40},
                # 'AUDJPY': {'enabled': True, 'max_spread': 35},
                # 'EURCHF': {'enabled': False, 'max_spread': 30},
                
                # # Commodities
                'XAUUSDc': {'enabled': True, 'max_spread': 50},  # Gold - Broker symbol
                # 'XAUEUR': {'enabled': False, 'max_spread': 60},  # Gold in EUR
                # 'XAGUSD': {'enabled': True, 'max_spread': 50},  # Silver
                # 'USOIL': {'enabled': True, 'max_spread': 50},   # WTI Oil
                # 'UKOIL': {'enabled': False, 'max_spread': 50},   # Brent Oil
                
                # # Indices (if your broker supports)
                # 'US30': {'enabled': False, 'max_spread': 50},    # Dow Jones
                # 'US500': {'enabled': False, 'max_spread': 30},   # S&P 500
                # 'NAS100': {'enabled': False, 'max_spread': 40},  # Nasdaq
                # 'DE30': {'enabled': False, 'max_spread': 40},    # DAX
                # 'UK100': {'enabled': False, 'max_spread': 40},   # FTSE
                # 'JP225': {'enabled': False, 'max_spread': 50},   # Nikkei
                
                # # Crypto (if your broker supports)
                # 'BTCUSD': {'enabled': False, 'max_spread': 100},
                # 'ETHUSD': {'enabled': False, 'max_spread': 80}
            },
            'check_interval': 300,  # 5 minutes
            'use_news_filter': True,  # Avoid trading during high-impact news
            'max_spread_multiplier': 2.0,  # Don't trade if spread > normal * multiplier
            'trading_sessions': {
                'ASIAN': {'start': 0, 'end': 9, 'volatility_factor': 0.7},
                'EUROPEAN': {'start': 7, 'end': 16, 'volatility_factor': 1.0},
                'US': {'start': 13, 'end': 22, 'volatility_factor': 1.2},
                'enabled': True  # Enable session-based filtering
            },
            'risk_config': {}  # Will be passed to RiskManager
        }
        
        # Merge with custom config
        if config:
            if 'symbols' in config:
                default_config['symbols'].update(config['symbols'])
            if 'risk_config' in config:
                default_config['risk_config'] = config['risk_config']
            for key, value in config.items():
                if key not in ['symbols', 'risk_config']:
                    default_config[key] = value
        
        self.config = default_config
        
        # Get enabled symbols
        self.symbols = [symbol for symbol, settings in self.config['symbols'].items() 
                       if settings.get('enabled', False)]
        
        self.running = False
        
        logger.info(f"Trading Bot configured with {len(self.symbols)} symbols: {', '.join(self.symbols)}")
        
    def start(self):
        """Start the trading bot"""
        logger.info("Starting Trading Bot...")
        logger.info(f"Configuration: Risk per trade: {self.config.get('risk_config', {}).get('max_risk_per_trade', 0.01)*100:.1f}%")
        logger.info(f"Daily loss limit: {self.config.get('risk_config', {}).get('max_daily_loss', 0.03)*100:.1f}%")
        logger.info(f"Active symbols: {', '.join(self.symbols)}")
        
        # Connect to MT5
        if not self.mt5_conn.connect():
            logger.error("Failed to connect to MT5")
            return
        
        # Initialize risk manager with account balance and config
        account_info = mt5.account_info()
        self.risk_manager = RiskManager(account_info.balance, self.config.get('risk_config', {}))
        self.executor = MT5TradingExecutor(self.risk_manager, self.telegram)
        
        self.running = True
        logger.info("Trading Bot started successfully")
        
        try:
            self.run()
        except KeyboardInterrupt:
            logger.info("Stopping bot...")
        except Exception as e:
            logger.error(f"Bot error: {e}")
        finally:
            self.stop()
    
    def run(self):
        """Main trading loop with async support"""
        check_interval = self.config.get('check_interval', 300)  # Default 5 minutes

        while self.running:
            try:
                logger.info(f"Checking markets at {datetime.now()}")

                # Process symbols in parallel using threading for better performance
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    # Submit all symbol analysis tasks
                    futures = []
                    for symbol in self.symbols:
                        future = executor.submit(self._process_symbol, symbol)
                        futures.append((symbol, future))

                    # Collect results
                    for symbol, future in futures:
                        try:
                            result = future.result(timeout=30)
                            if result and result.get('signal'):
                                # Execute trade if signal generated
                                self.executor.execute_trade(result['signal'], symbol)
                        except Exception as e:
                            logger.error(f"Error processing {symbol}: {e}")

                # Manage existing positions
                self.executor.manage_open_positions(self.gemini_ai, self.market_data)

                # Show account status
                self._show_account_status()

                # Send daily summary to Telegram at specific times
                current_hour = datetime.now().hour
                current_minute = datetime.now().minute

                # Check for news alerts every 30 minutes
                if current_minute % 30 == 0:
                    if not hasattr(self, '_last_news_check_minute') or self._last_news_check_minute != current_minute:
                        self.news_checker.send_news_alert(hours_ahead=1)
                        self._last_news_check_minute = current_minute

                # Send account summary at specific times
                if self.telegram and current_hour in [9, 15, 21]:  # 9am, 3pm, 9pm
                    if not hasattr(self, '_last_summary_hour') or self._last_summary_hour != current_hour:
                        account_info = mt5.account_info()
                        positions = mt5.positions_get()
                        self.telegram.send_account_summary(account_info, positions)
                        self._last_summary_hour = current_hour

                # Check for risk alerts
                self._check_risk_alerts()

                # Wait for next check
                logger.info(f"Waiting {check_interval} seconds for next check...")
                time.sleep(check_interval)

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(60)  # Wait before retry

    def _process_symbol(self, symbol: str) -> Dict:
        """Process individual symbol analysis"""
        try:
            # Check if market is open
            if not self._is_market_open(symbol):
                logger.info(f"Market closed for {symbol}")
                return {}

            # Check for upcoming news
            if self.config.get('use_news_filter', True):
                avoid_news, news_reason = self.news_checker.should_avoid_trading(symbol)
                if avoid_news:
                    logger.info(f"Avoiding {symbol} due to news: {news_reason}")
                    if self.telegram:
                        self.telegram.send_message(
                            f"⚠️ Skipping {symbol}\n📰 {news_reason}"
                        )
                    return {}

            # Check spread
            if not self._check_spread(symbol):
                logger.info(f"Spread too high for {symbol}")
                return {}

            # Check trading session if enabled
            if self.config['trading_sessions'].get('enabled', True):
                if not self._is_good_trading_session(symbol):
                    logger.info(f"Not optimal trading session for {symbol}")
                    return {}

            # Get market analysis
            market_data = self.market_data.get_market_analysis(symbol)

            if not market_data:
                logger.warning(f"No market data for {symbol}")
                return {}

            # Get AI decision
            logger.info(f"Analyzing {symbol}...")
            signal = self.gemini_ai.analyze_and_decide(market_data)

            # Return signal for execution
            if signal['decision'] != 'HOLD':
                logger.info(f"Signal for {symbol}: {signal['decision']} with {signal['confidence']}% confidence")
                return {'signal': signal}
            else:
                logger.info(f"No trade signal for {symbol}")
                return {}

        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            return {}
    
    def _check_spread(self, symbol: str) -> bool:
        """Check if spread is acceptable for trading"""
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return False
        
        current_spread = symbol_info.spread
        max_spread = self.config['symbols'].get(symbol, {}).get('max_spread', 50)
        
        # Apply multiplier for volatile conditions
        max_allowed = max_spread * self.config.get('max_spread_multiplier', 2.0)
        
        if current_spread > max_allowed:
            logger.info(f"{symbol} spread too high: {current_spread} > {max_allowed}")
            return False
        
        return True
    
    def _is_good_trading_session(self, symbol: str) -> bool:
        """Check if current session is good for trading this symbol"""
        now = datetime.now()
        hour = now.hour
        
        sessions = self.config['trading_sessions']
        
        # Determine best sessions for each symbol type
        symbol_sessions = {
            'EURUSD': ['EUROPEAN', 'US'],
            'GBPUSD': ['EUROPEAN', 'US'],
            'USDJPY': ['ASIAN', 'US'],
            'AUDUSD': ['ASIAN', 'US'],
            'NZDUSD': ['ASIAN', 'US'],
            'XAUUSD': ['EUROPEAN', 'US'],  # Gold most active in London/NY
            'USOIL': ['US'],
            'US30': ['US'],
            'US500': ['US'],
            'NAS100': ['US'],
            'DE30': ['EUROPEAN'],
            'UK100': ['EUROPEAN'],
            'JP225': ['ASIAN']
        }
        
        # Get preferred sessions for this symbol
        preferred = symbol_sessions.get(symbol, ['EUROPEAN', 'US'])
        
        # Check if we're in a preferred session
        current_session = None
        for session_name, session_info in sessions.items():
            if session_name == 'enabled':
                continue
            if session_info['start'] <= hour < session_info['end']:
                current_session = session_name
                break
        
        if current_session in preferred:
            return True
        
        # Allow trading with reduced confidence outside preferred sessions
        return False  # You can change this to True if you want 24/5 trading
    
    def _is_market_open(self, symbol: str) -> bool:
        """Check if market is open for trading"""
        # Get current time
        now = datetime.now()
        weekday = now.weekday()

        # Forex market is closed on weekends
        if weekday >= 5:  # Saturday = 5, Sunday = 6
            return False

        # Check if symbol is tradeable
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logger.warning(f"Symbol {symbol} not found")
            return False

        # Check if trading is allowed for this symbol
        if not symbol_info.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL:
            return False

        # Simple check: if we can get a tick, market is open
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return False

        # Check if bid and ask are valid (non-zero)
        if tick.bid > 0 and tick.ask > 0:
            return True

        return False
    
    def _show_account_status(self):
        """Display account status"""
        account_info = mt5.account_info()
        positions = mt5.positions_get()
        
        logger.info("=" * 50)
        logger.info(f"Account Balance: ${account_info.balance:.2f}")
        logger.info(f"Account Equity: ${account_info.equity:.2f}")
        logger.info(f"Free Margin: ${account_info.margin_free:.2f}")
        logger.info(f"Profit: ${account_info.profit:.2f}")
        logger.info(f"Open Positions: {len(positions) if positions else 0}")
        
        if positions:
            for pos in positions:
                position_type = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                logger.info(f"  - {pos.symbol}: {position_type} {pos.volume} lots, P/L: ${pos.profit:.2f}")
        
        logger.info("=" * 50)
    
    def stop(self):
        """Stop the trading bot"""
        self.running = False
        
        # Close all positions (optional - comment out if you want to keep positions open)
        # self._close_all_positions()
        
        # Disconnect from MT5
        self.mt5_conn.disconnect()
        logger.info("Trading Bot stopped")
    
    def _check_risk_alerts(self):
        """Check and send risk management alerts"""
        if not self.telegram:
            return
        
        account_info = mt5.account_info()
        current_balance = account_info.balance
        
        # Check daily loss
        daily_loss_percent = (self.risk_manager.initial_balance - current_balance) / self.risk_manager.initial_balance
        if daily_loss_percent >= self.risk_manager.max_daily_loss * 0.8:  # Alert at 80% of limit
            if not hasattr(self, '_daily_loss_alerted'):
                self.telegram.send_risk_alert('DAILY_LOSS_WARNING', {
                    'loss_percent': daily_loss_percent * 100,
                    'balance': current_balance
                })
                self._daily_loss_alerted = True
        
        # Check drawdown
        if not hasattr(self, '_peak_balance'):
            self._peak_balance = current_balance
        else:
            self._peak_balance = max(self._peak_balance, current_balance)
        
        drawdown = (self._peak_balance - current_balance) / self._peak_balance * 100
        if drawdown > 10:  # Alert if drawdown > 10%
            if not hasattr(self, '_last_drawdown_alert') or drawdown - self._last_drawdown_alert > 5:
                self.telegram.send_risk_alert('HIGH_DRAWDOWN', {
                    'drawdown': drawdown,
                    'peak': self._peak_balance,
                    'current': current_balance
                })
                self._last_drawdown_alert = drawdown
    
    def _close_all_positions(self):
        """Close all open positions"""
        positions = mt5.positions_get()
        
        if not positions:
            return
        
        for position in positions:
            if position.magic != self.executor.magic_number:
                continue
            
            # Close position
            close_type = mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(position.symbol).bid if position.type == 0 else mt5.symbol_info_tick(position.symbol).ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": position.volume,
                "type": close_type,
                "position": position.ticket,
                "price": price,
                "deviation": 20,
                "magic": self.executor.magic_number,
                "comment": "Bot shutdown - closing position",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"Closed position {position.ticket}")
                if self.telegram:
                    self.telegram.send_trade_alert('CLOSED', {}, position.symbol,
                                                  result={'order': position.ticket,
                                                         'price': price,
                                                         'profit': position.profit})

# Main execution
if __name__ == "__main__":
    # Mode 1: Use existing MT5 terminal (ไม่ต้องใส่ login/password)
    # เพียงแค่เปิด MT5 และ login ไว้แล้ว
    USE_EXISTING_MT5 = True  # Set to True to use existing MT5 session

    if USE_EXISTING_MT5:
        # ไม่ต้องใส่ข้อมูล login - ใช้ MT5 ที่เปิดอยู่แล้ว
        MT5_LOGIN = None
        MT5_PASSWORD = None
        MT5_SERVER = None
        logger.info("Using existing MT5 terminal session (no login required)")
    else:
        # Mode 2: Login with credentials
        MT5_LOGIN = int(os.getenv('MT5_LOGIN', 12345678))  # Your MT5 account number
        MT5_PASSWORD = os.getenv('MT5_PASSWORD', 'your_password')  # Your MT5 password
        MT5_SERVER = os.getenv('MT5_SERVER', 'YourBroker-Demo')  # Your broker's MT5 server

    # Gemini API Configuration (required)
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'your_gemini_api_key')  # Your Gemini API key

    # Telegram Configuration (Optional)
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', None)  # Token from @BotFather
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', None)  # Your Telegram chat ID
    
    # Advanced Configuration
    custom_config = {
        # เลือก symbols ที่ต้องการเทรด (ตั้ง enabled: True/False)
        'symbols': {
            # Major Forex - เปิดใช้งาน
            'EURUSDc': {'enabled': True, 'max_spread': 20},  # EUR/USD - Broker symbol
            # 'GBPUSD': {'enabled': True, 'max_spread': 30},
            # 'USDJPY': {'enabled': True, 'max_spread': 20},
            # 'AUDUSD': {'enabled': True, 'max_spread': 25},
            
            # # Commodities - เปิดใช้งาน
            'XAUUSDc': {'enabled': True, 'max_spread': 50},  # ทองคำ - Broker symbol
            # 'XAGUSD': {'enabled': True, 'max_spread': 50},  # เงิน
            # 'USOIL': {'enabled': True, 'max_spread': 50},   # น้ำมัน
            
            # # Cross pairs - เปิดบางคู่
            # 'EURJPY': {'enabled': True, 'max_spread': 30},
            # 'GBPJPY': {'enabled': True, 'max_spread': 40},
            
            # # Indices - ปิดไว้ก่อน (เปิดได้ถ้า broker รองรับ)
            # 'US30': {'enabled': False, 'max_spread': 50},
            # 'NAS100': {'enabled': False, 'max_spread': 40},
            
            # # Crypto - ปิดไว้ก่อน (เปิดได้ถ้า broker รองรับ)
            # 'BTCUSD': {'enabled': False, 'max_spread': 100},
        },
        
        # Risk Parameters (Conservative Settings)
        'risk_config': {
            'max_risk_per_trade': 0.01,      # 1% ต่อ trade (จากเดิม 2%)
            'max_daily_loss': 0.03,          # 3% daily loss limit (จากเดิม 6%)
            'max_weekly_loss': 0.05,         # 5% weekly loss limit
            'max_open_trades': 5,            # จำนวน trades พร้อมกันสูงสุด
            'max_correlation_trades': 2,      # trades ที่ correlate กันสูงสุด
            'risk_free_profit_lock': 0.5,    # ย้าย SL ที่ BE เมื่อกำไร 50% ของ TP
            'trailing_stop_activation': 1.5,  # เริ่ม trail เมื่อ 1.5 RR
            'position_size_by_confidence': {  # ปรับ size ตาม confidence
                90: 1.0,   # 90%+ = 100% of risk
                80: 0.75,  # 80-89% = 75% of risk
                70: 0.5,   # 70-79% = 50% of risk
                60: 0.25   # 60-69% = 25% of risk (safer)
            }
        },
        
        # Trading Settings
        'check_interval': 300,  # ตรวจสอบทุก 5 นาที
        'use_news_filter': True,  # หลีกเลี่ยงช่วงข่าว high impact
        'max_spread_multiplier': 2.0,  # ไม่เทรดถ้า spread > ปกติ x 2
        
        # Trading Sessions (Bangkok Time GMT+7)
        'trading_sessions': {
            'ASIAN': {'start': 7, 'end': 16, 'volatility_factor': 0.7},
            'EUROPEAN': {'start': 14, 'end': 23, 'volatility_factor': 1.0},
            'US': {'start': 20, 'end': 5, 'volatility_factor': 1.2},
            'enabled': True  # เปิด/ปิด การกรอง session
        }
    }
    
    # Create and start bot with configuration
    bot = TradingBot(
        mt5_login=MT5_LOGIN,
        mt5_password=MT5_PASSWORD,
        mt5_server=MT5_SERVER,
        gemini_api_key=GEMINI_API_KEY,
        telegram_token=TELEGRAM_BOT_TOKEN,
        telegram_chat_id=TELEGRAM_CHAT_ID,
        config=custom_config
    )
    
    # Start trading
    bot.start()