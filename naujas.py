import asyncio
import json
import re
import math  
import time
from datetime import datetime, timezone, timedelta
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier

from dataclasses import dataclass
from typing import Optional, Dict, List
from telethon import TelegramClient, events
import logging
logger = logging.getLogger(__name__)

import aiosqlite
import sqlite3


# Nustatome logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)



class AsyncDatabase:
    def __init__(self):
        self.db_path = Config.DB_PATH
        self.conn = None
        self.setup_done = False
                
    async def connect(self):
        if not self.conn:
            try:
                self.conn = await aiosqlite.connect(self.db_path)
                self.conn.row_factory = aiosqlite.Row
                if not self.setup_done:
                    await self._setup_database()
                    self.setup_done = True
                logger.info(f"[{datetime.now(timezone.utc)}] Connected to database: {self.db_path}")
            except Exception as e:
                logger.error(f"[{datetime.now(timezone.utc)}] Database connection error: {e}")
                raise
                
    async def _setup_database(self):
        """Sukuria reikalingas lenteles jei jų nėra"""
        if self.setup_done:
            return
                    
        try:
            # Token pradinė būsena
            await self.execute("""
                CREATE TABLE IF NOT EXISTS token_initial_states (
                    address TEXT PRIMARY KEY,
                    name TEXT,
                    symbol TEXT,
                    age TEXT,
                    market_cap REAL,
                    liquidity REAL,
                    volume_1h REAL,
                    volume_24h REAL,
                    price_change_1h REAL,
                    price_change_24h REAL,
                    mint_enabled BOOLEAN,
                    freeze_enabled BOOLEAN,
                    lp_burnt_percentage REAL,
                    holders_count INTEGER,
                    top_holder_percentage REAL,
                    sniper_count INTEGER,
                    sniper_percentage REAL,
                    first_20_fresh INTEGER,
                    ath_market_cap REAL,
                    ath_multiplier REAL,
                    owner_renounced BOOLEAN,
                    telegram_url TEXT,
                    twitter_url TEXT,
                    website_url TEXT,
                    dev_sol_balance REAL,
                    dev_token_percentage REAL,
                    first_seen TIMESTAMP,
                    status TEXT,
                    sniper_wallets JSON
                )
            """)
            
                        
            # 1. Sniper wallets lentelė
            await self.execute("""
                CREATE TABLE IF NOT EXISTS sniper_wallets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL UNIQUE,
                    type TEXT NOT NULL,
                    success_rate REAL DEFAULT 0.0,
                    total_trades INTEGER DEFAULT 0,
                    last_active TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Token updates lentelė
            await self.execute("""
                CREATE TABLE IF NOT EXISTS token_updates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL,
                    all_metrics TEXT NOT NULL,
                    timestamp TIMESTAMP,
                    current_multiplier REAL,
                    update_number INTEGER DEFAULT 0,
                    FOREIGN KEY(address) REFERENCES token_initial_states(address)
                )
            """)

            # Successful tokens lentelė 
            await self.execute("""
                CREATE TABLE IF NOT EXISTS successful_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL UNIQUE,
                    initial_parameters TEXT NOT NULL,
                    time_to_10x INTEGER,
                    discovery_timestamp TIMESTAMP,
                    update_number INTEGER DEFAULT 0,
                    FOREIGN KEY(address) REFERENCES token_initial_states(address)
                )
            """)

            # 4. Failed tokens lentelė
            await self.execute("""
                CREATE TABLE IF NOT EXISTS failed_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL UNIQUE,
                    initial_parameters TEXT NOT NULL,
                    failure_reason TEXT,
                    discovery_timestamp TIMESTAMP,
                    FOREIGN KEY(address) REFERENCES token_initial_states(address)
                )
            """)

            # Security lentelė - PRIDĖTI ČIA
            await self.execute("""
                CREATE TABLE IF NOT EXISTS token_security (
                    address TEXT PRIMARY KEY,
                    security_risk REAL,
                    check_time DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            
            
            # Indeksai
            await self.execute("CREATE INDEX IF NOT EXISTS idx_token_updates_address ON token_updates(address)")
            await self.execute("CREATE INDEX IF NOT EXISTS idx_token_updates_timestamp ON token_updates(timestamp)")
            
            self.setup_done = True
            logger.info(f"[2025-01-31 13:22:07] Database setup completed")
            
        except Exception as e:
            logger.error(f"[2025-01-31 13:22:07] Database setup error: {e}")
            raise
            
    async def execute(self, query: str, *args):
        """Vykdo SQL užklausą"""
        if not self.conn:
            await self.connect()
            
        try:
            # Jei args yra tuple viename tuple, išpakuojame jį
            if len(args) == 1 and isinstance(args[0], tuple):
                args = args[0]
                
            async with self.conn.execute(query, args) as cursor:
                await self.conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"[2025-01-31 14:00:32] Query execution error: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Args: {args}")
            raise
            
    async def fetch_all(self, query: str, *args):
        """Gauna visus rezultatus iš užklausos"""
        if not self.conn:
            await self.connect()
            
        try:
            async with self.conn.execute(query, args) as cursor:
                return await cursor.fetchall()
        except Exception as e:
            logger.error(f"[2025-01-31 13:22:07] Fetch all error: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Args: {args}")
            raise
            
    async def fetch_one(self, query: str, *args):
        """Gauna vieną rezultatą iš užklausos"""
        if not self.conn:
            await self.connect()
            
        try:
            # Jei args yra tuple viename tuple, išpakuojame jį
            if len(args) == 1 and isinstance(args[0], tuple):
                args = args[0]
                
            async with self.conn.execute(query, args) as cursor:
                return await cursor.fetchone()
        except Exception as e:
            logger.error(f"[2025-01-31 13:22:07] Fetch one error: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Args: {args}")
            raise
            
    async def close(self):
        """Uždaro duomenų bazės prisijungimą"""
        if self.conn:
            await self.conn.close()
            self.conn = None
            logger.info(f"[2025-01-31 13:22:07] Database connection closed")


class Config:
    # Telegram settings
    TELEGRAM_API_ID = '25425140'
    TELEGRAM_API_HASH = 'bd0054bc5393af360bc3930a27403c33'
    TELEGRAM_SOURCE_CHATS = ['@solearlytrending', '@botubotass']
    TELEGRAM_DEST_CHAT = '@smartas1'
    TELEGRAM_DEST_CHAT1 = '@testasmano'
    
    # Scanner settings
    SCANNER_GROUP = '@skaneriss'
    SOUL_SCANNER_BOT = 6872314605
    
    # ML settings
    MIN_TRAINING_SAMPLES = 10
    RETRAIN_INTERVAL = 12
    
    # Database settings
    DB_PATH = 'gem_finder.db'
    
    # Gem detection settings
    MIN_GEM_PROBABILITY = 0.1
    MIN_MC_FOR_GEM = 20000
    MAX_MC_FOR_GEM = 1000000
    
    # ML modelio parametrai
    ML_SETTINGS = {
        'min_gem_multiplier': 5.0,
        'update_interval': 60,  # sekundės
        'confidence_threshold': 0.7,
        'training_data_limit': 2000  # kiek istorinių gem naudoti apmokymui
    }
    
    # Token stebėjimo parametrai
    MONITORING = {
        'max_tracking_time': 7 * 24 * 60 * 60,  # 7 dienos sekundėmis
        'update_frequency': 60,  # sekundės
        'max_active_tokens': 1000
    }

    # Update analysis settings
    UPDATE_ANALYSIS = {
        'analyze_first_update': True,
        'analyze_second_update': False, 
        'analyze_third_update': False
    }
    
    # Duomenų bazės parametrai
    DB_SETTINGS = {
        'max_connections': 20,
        'timeout': 30,
        'retry_attempts': 3
    }

@dataclass
class TokenMetrics:
    # Basic info
    address: str
    name: str
    symbol: str
    age: str  # format: "1h", "2d", etc.
    
    # Price metrics
    market_cap: float
    liquidity: float
    volume_1h: float
    volume_24h: float
    price_change_1h: float
    price_change_24h: float
    ath_market_cap: float
    
    lp_burnt_percentage: float
    holders_count: int
    top_holder_percentage: float
    sniper_count: int
    sniper_percentage: float
    first_20_fresh: int
    
    

    mint_enabled: int = 0      # Vietoj bool = False
    freeze_enabled: int = 0    # Vietoj bool = False
    owner_renounced: int = 0
    total_scans: int = 0      # Vietoj bool = False
    
    # Optional fields with default values
    ath_multiplier: float = 1.0
    dev_wallet: Optional[str] = None
    sniper_wallets: List[Dict] = None
    dev_sol_balance: float = 0.0
    dev_token_percentage: float = 0.0
    telegram_url: Optional[str] = None
    twitter_url: Optional[str] = None
    website_url: Optional[str] = None
    

    def to_dict(self) -> Dict:
        """Konvertuoja objektą į žodyną"""
        return {
            'address': self.address,
            'name': self.name,
            'symbol': self.symbol,
            'age': self.age,
            'market_cap': self.market_cap,
            'liquidity': self.liquidity,
            'volume_1h': self.volume_1h,
            'volume_24h': self.volume_24h,
            'price_change_1h': self.price_change_1h,
            'price_change_24h': self.price_change_24h,
            'ath_market_cap': self.ath_market_cap,
            'lp_burnt_percentage': self.lp_burnt_percentage,
            'holders_count': self.holders_count,
            'top_holder_percentage': self.top_holder_percentage,
            'sniper_count': self.sniper_count,
            'sniper_percentage': self.sniper_percentage,
            'first_20_fresh': self.first_20_fresh,
            'mint_enabled': self.mint_enabled,
            'freeze_enabled': self.freeze_enabled,
            'owner_renounced': self.owner_renounced,
            'ath_multiplier': self.ath_multiplier,
            'dev_wallet': self.dev_wallet,
            'sniper_wallets': self.sniper_wallets,
            'dev_sol_balance': self.dev_sol_balance,
            'dev_token_percentage': self.dev_token_percentage,
            'telegram_url': self.telegram_url,
            'twitter_url': self.twitter_url,
            'website_url': self.website_url
        }
    
@dataclass
class TokenUpdate:
    """Token update data structure"""
    address: str
    timestamp: datetime
    market_cap: float
    liquidity: float
    volume_1h: float
    volume_24h: float
    price_change_1h: float
    price_change_24h: float
    holders_count: int
    top_holder_percentage: float
    sniper_count: int
    sniper_percentage: float
    current_multiplier: float
    all_metrics: Dict
    
    # Pridedami trūkstami laukai
    name: str
    symbol: str
    age: str
    mint_enabled: int = 0
    freeze_enabled: int = 0
    lp_burnt_percentage: float = 0.0
    first_20_fresh: int = 0
    ath_market_cap: float = 0.0
    ath_multiplier: float = 1.0
    owner_renounced: int = 0
    telegram_url: Optional[str] = None
    twitter_url: Optional[str] = None
    website_url: Optional[str] = None
    dev_sol_balance: float = 0.0
    dev_token_percentage: float = 0.0
    sniper_wallets: Optional[List[Dict]] = None
    has_24h_data: bool = False
    
    def to_dict(self) -> dict:
        """Konvertuoja į žodyną"""
        return self.__dict__

    def to_tuple(self) -> tuple:
        """Konvertuoja į tuple DB įrašymui"""
        return (
            self.address, self.name, self.symbol, self.age,
            self.market_cap, self.liquidity, self.volume_1h, self.volume_24h,
            self.price_change_1h, self.price_change_24h,
            self.mint_enabled, self.freeze_enabled, self.lp_burnt_percentage,
            self.holders_count, self.top_holder_percentage,
            self.sniper_count, self.sniper_percentage, self.first_20_fresh,
            self.ath_market_cap, self.ath_multiplier,
            self.owner_renounced, self.telegram_url, self.twitter_url, self.website_url,
            self.dev_sol_balance, self.dev_token_percentage,
            self.has_24h_data,
            json.dumps(self.sniper_wallets) if self.sniper_wallets else None
            
        )
    def __post_init__(self):
        """Nustatome has_24h_data po inicializacijos"""
        self.has_24h_data = (self.volume_24h > 0 or self.price_change_24h != 0)

    
class TokenHandler:
    def __init__(self, db_manager, ml_analyzer):
        self.db = db_manager
        self.ml = ml_analyzer
        self.telegram_client = None
        self.token_analyzer = TokenAnalyzer(db_manager, ml_analyzer)  # Inicializuojame TokenAnalyzer
        
    async def handle_new_token(self, token_data: TokenMetrics):
        """Apdoroja naują token'ą"""
        try:
            current_time = "[2025-02-08 16:37:14]"
            
            # Išsaugome pradinę būseną
            await self.db.save_initial_state(token_data)
            logger.info(f"{current_time} Saved initial state for: {token_data.address}")
            
            # Patikriname ar jau turime security patikrinimą DB
            security_check = await self.db.get_security_check(token_data.address)
            
            if not security_check:
                # Atliekame security patikrinimą
                security_risk = self.token_analyzer._assess_security_risk(token_data)
                
                # Išsaugome rezultatą į DB
                await self.db.save_security_check(token_data.address, security_risk)
                
                if security_risk >= 1.0:
                    logger.warning(f"{current_time} Token {token_data.address} failed security checks")
                    return 0.0
            elif security_check['security_risk'] >= 1.0:
                logger.info(f"{current_time} Token {token_data.address} previously failed security checks")
                return 0.0
            
            logger.info(f"{current_time} Token {token_data.address} passed security checks")
            
            # Gauname ML predikcijas
            initial_prediction = await self.ml.predict_potential(token_data)
            logger.info(f"{current_time} Initial ML prediction for {token_data.address}: {initial_prediction:.2f}")
            
            # Tikriname basic kriterijus ir siunčiame pranešimą
            if self._meets_basic_criteria(token_data) and initial_prediction >= Config.MIN_GEM_PROBABILITY:
                logger.info(f"{current_time} Token {token_data.address} meets all criteria - sending notification")
                await self._send_gem_notification(token_data, initial_prediction)
            else:
                logger.info(f"{current_time} Token {token_data.address} does not meet basic criteria or has low prediction")
            
            return initial_prediction
            
        except Exception as e:
            logger.error(f"{current_time} Error handling new token: {e}")
            return 0.0

    async def handle_token_update(self, token_address: str, new_data: TokenMetrics, is_new_token: bool = False):
        """Apdoroja token'o atnaujinimą"""
        try:
            initial_data = await self.db.get_initial_state(token_address)
            if not initial_data:
                if is_new_token:  # Jei tai naujas token'as
                    prediction = await self.ml.predict_potential(new_data, 0)  # Naudojame 0 new token modeliui
                    await self.handle_new_token(new_data)  # Naudojame handle_new_token metodą
                    logger.info(f"[2025-02-05 17:44:04] New token processed via update: {token_address} with prediction: {prediction:.2f}")
                    return
                else:
                    logger.warning(f"[2025-02-05 17:44:04] Skipping update for unknown token: {token_address}")
                    return

            current_multiplier = new_data.market_cap / initial_data.market_cap

            # Gauname update numerį
            update_count = await self.db.get_update_count(token_address)
            current_update = update_count
            logger.info(f"[2025-02-05 17:44:04] Processing update #{current_update} for token {token_address}")
            
            # Išsaugome atnaujinimą
            await self.db.save_token_update(token_address, new_data, current_update)
            logger.info(f"[2025-02-05 17:44:04] Token update saved for {token_address}, current multiplier: {current_multiplier:.2f}x")

            # Tikriname ar reikia analizuoti šį update'ą
            if (current_update == 0 and Config.UPDATE_ANALYSIS['analyze_first_update']) or \
               (current_update == 1 and Config.UPDATE_ANALYSIS['analyze_second_update']) or \
               (current_update == 2 and Config.UPDATE_ANALYSIS['analyze_third_update']):
                
                # Atliekame ML analizę
                prediction = await self.ml.predict_potential(new_data, current_update)
                logger.info(f"[2025-02-05 17:44:04] Update #{current_update} ML prediction for {token_address}: {prediction:.2f}")
                
                # Jei atitinka kriterijus, siunčiame pranešimą
                if self._meets_basic_criteria(new_data) and prediction >= Config.MIN_GEM_PROBABILITY:
                    await self._send_update_notification(new_data, prediction, current_update)
            
            # Tikriname ar tapo gem pagal nustatytą multiplier
            if current_multiplier >= Config.ML_SETTINGS['min_gem_multiplier'] and not await self.db.is_gem(token_address):
                logger.info(f"[2025-02-05 23:05:02] Token reached {Config.ML_SETTINGS['min_gem_multiplier']}x on update #{current_update}: {token_address} ({current_multiplier:.2f}X)")
                
                
                try:
                    # Tada žymime kaip gem ir atnaujiname modelį
                    await self.db.mark_as_gem(token_address, current_update)
                    await self.ml.update_model_with_new_gem(initial_data, current_update)
                    logger.info(f"[2025-02-05 17:44:04] Token marked as gem and model updated: {token_address}")
                except Exception as notification_error:
                    logger.error(f"[2025-02-05 17:44:04] Error in gem notification process: {notification_error}")
                    import traceback
                    logger.error(f"Notification error traceback: {traceback.format_exc()}")
            
        except Exception as e:
            logger.error(f"[2025-02-05 17:44:04] Error handling token update: {e}")
            import traceback
            logger.error(f"Main update error traceback: {traceback.format_exc()}")
            
    def _meets_basic_criteria(self, token_data: TokenMetrics) -> bool:
        """Patikriname ar token'as atitinka basic kriterijus"""
        try:
            logger.info(f"[2025-02-03 14:44:23] Checking criteria for {token_data.address}:")
            logger.info(f"Market Cap: ${token_data.market_cap:,.0f}")
            logger.info(f"Min MC: ${Config.MIN_MC_FOR_GEM:,.0f}")
            logger.info(f"Max MC: ${Config.MAX_MC_FOR_GEM:,.0f}")
            
            if token_data.market_cap < Config.MIN_MC_FOR_GEM:
                logger.info(f"[2025-02-03 14:44:23] Token {token_data.address} MC too low")
                return False
                
            if token_data.market_cap > Config.MAX_MC_FOR_GEM:
                logger.info(f"[2025-02-03 14:44:23] Token {token_data.address} MC too high")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"[2025-02-03 14:44:23] Error in basic criteria check: {e}")
            return False

    async def _send_gem_notification(self, token_data: TokenMetrics, probability: float, security_passed: bool = True) -> None:
        """Siunčia pranešimą apie potencialų gem"""
        try:
            gmgn_url = f"https://gmgn.ai/sol/token/{token_data.address}"
            current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            
            # Pridedame saugumo statusą į pranešimą
            security_status = "✅ SAFE" if security_passed else "⚠️ RISKY"
            
            message = (
                f"🔍 POTENTIAL GEM DETECTED!\n\n"
                f"Token: {token_data.name} (${token_data.symbol})\n"
                f"Address: <code>{token_data.address}</code>\n"
                f"Security Status: {security_status}\n"
                f"Probability: {probability*100:.1f}%\n\n"
                f"Market Cap: ${token_data.market_cap:,.0f}\n"
                f"Liquidity: ${token_data.liquidity:,.0f}\n"
                f"Age: {token_data.age}\n"
                f"Holders: {token_data.holders_count}\n"
                f"Volume 1h: ${token_data.volume_1h:,.0f}\n\n"
                f"Security:\n"
                f"• Mint: {'✅' if not token_data.mint_enabled else '⚠️'}\n"
                f"• Freeze: {'✅' if not token_data.freeze_enabled else '⚠️'}\n"
                f"• Owner: {'✅' if token_data.owner_renounced else '⚠️'}\n"
                f"• LP Lock: {'✅' if token_data.lp_burnt_percentage >= 80 else '⚠️'} ({token_data.lp_burnt_percentage}%)\n\n"
                f"Links:\n"
                f"🔗 <a href='{gmgn_url}'>View on GMGN.AI</a>\n"
                f"----------------------------------------------\n"
                f"🌐 Website: {token_data.website_url or 'N/A'}\n"
                f"🐦 Twitter: {token_data.twitter_url or 'N/A'}\n"
                f"💬 Telegram: {token_data.telegram_url or 'N/A'}\n\n"
                f"⏰ Found at: {current_time} UTC\n"
                f"<i>Tap token address to copy</i>"
            )
            
            await self._send_notification(message, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"[2025-02-08 16:23:51] Error sending gem notification: {e}")

    async def _send_update_notification(self, token_data: TokenMetrics, probability: float, update_number: int) -> None:
        """Siunčia pranešimą apie update'o analizę"""
        try:
            gmgn_url = f"https://gmgn.ai/sol/token/{token_data.address}"
            current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            
            message = (
                f"🔄 UPDATE #{update_number} ANALYSIS\n\n"
                f"Token: {token_data.name} (${token_data.symbol})\n"  # Naudojame token_data
                f"Address: <code>{token_data.address}</code>\n"  # Naudojame token_data
                f"Probability: {probability*100:.1f}%\n\n"
                f"Market Cap: ${token_data.market_cap:,.0f}\n"
                f"Liquidity: ${token_data.liquidity:,.0f}\n"
                f"Age: {token_data.age}\n"
                f"Holders: {token_data.holders_count}\n"
                f"Volume 1h: ${token_data.volume_1h:,.0f}\n\n"
                f"Security:\n"
                f"• Mint: {'✅' if not token_data.mint_enabled else '⚠️'}\n"
                f"• Freeze: {'✅' if not token_data.freeze_enabled else '⚠️'}\n"
                f"• Owner: {'✅' if token_data.owner_renounced else '⚠️'}\n\n"
                f"Links:\n"
                f"🔗 <a href='{gmgn_url}'>View on GMGN.AI</a>\n"
                f"----------------------------------------------\n"
                f"🌐 Website: {token_data.website_url or 'N/A'}\n"
                f"🐦 Twitter: {token_data.twitter_url or 'N/A'}\n"
                f"💬 Telegram: {token_data.telegram_url or 'N/A'}\n\n"
                f"⏰ Found at: {current_time} UTC\n"
                f"<i>Tap token address to copy</i>"
            )
            
            await self._send_notification(message, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"[2025-02-05 15:34:58] Error sending update notification: {e}")

    

    async def _send_notification(self, message: str, parse_mode: str = None) -> None:
        """Siunčia pranešimą į Telegram"""
        try:
            if not self.telegram_client:
                logger.error(f"[{datetime.now(timezone.utc)}] Telegram client not initialized")
                return
                
            await self.telegram_client.send_message(Config.TELEGRAM_DEST_CHAT1, message, parse_mode=parse_mode)
            logger.info(f"[{datetime.now(timezone.utc)}] Sent notification to Telegram")
            
        except Exception as e:
            logger.error(f"[{datetime.now(timezone.utc)}] Error sending notification: {e}")
            logger.error(f"[{datetime.now(timezone.utc)}] Error details: {str(e)}")

    async def check_inactive_tokens(self):
        """Tikrina ir pažymi neaktyvius token'us"""
        try:
            query = "SELECT address, first_seen FROM token_initial_states WHERE status = 'new'"
            tokens = await self.db.fetch_all(query)
            
            current_time = datetime.now(timezone.utc)
            checked_count = 0
            failed_count = 0
            
            for token in tokens:
                try:
                    first_seen = datetime.fromisoformat(str(token['first_seen']))
                    time_difference = current_time - first_seen
                    
                    if time_difference.total_seconds() > 6 * 3600:
                        updates_query = "SELECT COUNT(*) as count FROM token_updates WHERE address = ?"
                        update_count = await self.db.fetch_one(updates_query, (token['address'],))
                        
                        if update_count['count'] == 0:
                            await self.db.mark_as_failed(
                                token['address'],
                                f"No updates for {time_difference.total_seconds() / 3600:.1f} hours"
                            )
                            failed_count += 1
                            logger.info(f"[2025-02-03 14:44:23] Marked {token['address']} as failed - no updates")
                    
                    checked_count += 1
                    
                except Exception as e:
                    logger.error(f"[2025-02-03 14:44:23] Error checking token {token['address']}: {e}")
                    continue
            
            logger.info(f"[2025-02-03 14:44:23] Inactive tokens check completed - Checked: {checked_count}, Failed: {failed_count}")
            
        except Exception as e:
            logger.error(f"[2025-02-03 14:44:23] Error in check_inactive_tokens: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

class MLAnalyzer:
    def __init__(self, db_manager, token_analyzer=None):
        self.db = db_manager
        self.token_analyzer = token_analyzer
        # Pakeičiame vieną modelį į keturis
        self.new_token_model = None
        self.update1_model = None
        self.update2_model = None
        self.update3_model = None
        # Atskiri scaleriai kiekvienam modeliui
        self.new_token_scaler = StandardScaler()
        self.update1_scaler = StandardScaler()
        self.update2_scaler = StandardScaler()
        self.update3_scaler = StandardScaler()
        
        # Performance tracking
        self.predictions_made = 0
        self.successful_predictions = 0
        self.prediction_history = []
        
        if self.token_analyzer is None:
            self.token_analyzer = TokenAnalyzer(db_manager, self)
            
    async def train_model(self, update_number: int = 0):
        """Treniruoja modelį naudojant token'ų duomenis pagal update numerį"""
        try:
            # NAUJAS KODAS: Parenkame tinkamą modelį ir scalerį
            if update_number == 0:
                current_model = self.new_token_model
                current_scaler = self.new_token_scaler
                data_type = "new tokens"
            elif update_number == 1:
                current_model = self.update1_model
                current_scaler = self.update1_scaler
                data_type = "first updates"
            elif update_number == 2:
                current_model = self.update2_model
                current_scaler = self.update2_scaler
                data_type = "second updates"
            elif update_number == 3:
                current_model = self.update3_model
                current_scaler = self.update3_scaler
                data_type = "third updates"
            else:
                logger.error(f"[2025-02-05 16:20:51] Invalid update number: {update_number}")
                return

            # PAKEISTA: Gauname duomenis pagal update numerį
            successful_tokens = await self.db.get_all_gems(update_number)
            failed_tokens = await self.db.get_failed_tokens(update_number)
            
            logger.info(f"[2025-02-05 16:20:51] Starting model training for {data_type} with {len(successful_tokens)} gems and {len(failed_tokens)} failed tokens")
            
            def process_features(token_metrics, features):
                """Helper funkcija feature vektoriaus formavimui"""
                try:
                    feature_vector = []
                    
                    # Basic metrics
                    feature_vector.extend([
                        float(features['basic_metrics']['age_hours']),
                        float(features['basic_metrics']['market_cap_normalized']),
                        float(features['basic_metrics']['liquidity_ratio'])
                    ])
                    
                    # Price/Volume metrics
                    feature_vector.extend([
                        float(token_metrics.market_cap or 0),
                        float(token_metrics.liquidity or 0),
                        float(token_metrics.volume_1h or 0),
                        float(token_metrics.volume_24h or 0),
                        float(token_metrics.price_change_1h or 0),
                        float(token_metrics.price_change_24h or 0)
                    ])
                    
                    # Holder metrics
                    feature_vector.extend([
                        float(features['holder_metrics']['holder_distribution']),
                        float(features['holder_metrics']['value_per_holder']),
                        float(features['holder_metrics']['top_holder_risk'])
                    ])
                    
                    # Sniper metrics
                    feature_vector.extend([
                        float(features['sniper_metrics'].get('sniper_impact', 0)),
                        float(features['sniper_metrics'].get('whale_dominance', 0)),
                        float(features['sniper_metrics'].get('fish_ratio', 0)),
                        float(features['sniper_metrics'].get('sniper_behavior_pattern', 0))
                    ])
                    
                    # Dev metrics
                    feature_vector.extend([
                        float(features['dev_metrics']['dev_commitment']),
                        float(features['dev_metrics']['owner_risk']),
                        float(features['dev_metrics']['dev_sol_strength']),
                        float(features['dev_metrics']['dev_token_risk']),
                        float(features['dev_metrics']['ownership_score'])
                    ])
                    
                    # Security metrics
                    feature_vector.extend([
                        float(features['security_metrics']['contract_security']),
                        float(features['security_metrics']['lp_security']),
                        float(features['security_metrics']['mint_risk']),
                        float(features['security_metrics']['freeze_risk']),
                        float(features['security_metrics']['overall_security_score'])
                    ])

                    # Scan metrics
                    feature_vector.extend([
                        float(features['scan_metrics']['scan_count']),
                        float(features['scan_metrics']['scan_intensity']),
                        float(features['scan_metrics']['scan_momentum'])
                    ])
                    
                    # Social metrics
                    feature_vector.extend([
                        float(features['social_metrics']['social_presence']),
                        float(features['social_metrics']['has_twitter']),
                        float(features['social_metrics']['has_website']),
                        float(features['social_metrics']['has_telegram']),
                        float(features['social_metrics']['social_risk'])
                    ])
                    
                    # Risk assessment
                    feature_vector.extend([
                        float(features['risk_assessment']['overall_risk']),
                        float(features['risk_assessment']['pump_dump_risk']),
                        float(features['risk_assessment']['security_risk']),
                        float(features['risk_assessment']['holder_risk']),
                        float(features['risk_assessment']['dev_risk'])
                    ])
                    
                    # Contract flags
                    feature_vector.extend([
                        float(token_metrics.mint_enabled),
                        float(token_metrics.freeze_enabled),
                        float(token_metrics.owner_renounced)
                    ])
                    
                    return feature_vector
                except Exception as e:
                    logger.error(f"[2025-02-03 13:21:21] Error processing features: {e}")
                    return None

            # Process successful tokens
            X_success = []
            y_success = []
            logger.info(f"[2025-02-05 16:20:51] Processing successful {data_type}...")
            
            for token in successful_tokens:
                try:
                    # Parenkame duomenis pagal update_number
                    if update_number == 0:
                        # Naujiems tokenams naudojame pradinę būseną
                        state_data = json.loads(token['initial_parameters'])
                        token_metrics = TokenMetrics(**state_data)
                    else:
                        # Update atveju gauname update duomenis
                        update_query = """
                            SELECT all_metrics FROM token_updates 
                            WHERE address = ? AND update_number = ? 
                            ORDER BY timestamp DESC LIMIT 1
                        """
                        # PATAISYTA: parametrai perduodami kaip tuple, ne tuple viduje tuple
                        # Perduodame parametrus kaip vieną tuple
                        update = await self.db.fetch_one(update_query, (token['address'], update_number))
                        if not update:
                            logger.warning(f"[2025-02-05 19:13:40] No update {update_number} data found for gem {token['address']}")
                            continue
                            
                        state_data = json.loads(update['all_metrics'])
                        token_metrics = TokenMetrics(**state_data)
                        
                    features = self.token_analyzer.prepare_features(token_metrics, [])
                    if not features:
                        logger.warning(f"[2025-02-05 19:13:40] Failed to prepare features for gem {token['address']}")
                        continue
                        
                    feature_vector = process_features(token_metrics, features)
                    if feature_vector:
                        X_success.append(feature_vector)
                        y_success.append(1)  # 1 = success
                        logger.info(f"[2025-02-05 19:13:40] Processed gem {token['address']} - Update {update_number} - Features: {len(feature_vector)}")
                        
                except Exception as e:
                    logger.error(f"[2025-02-05 19:13:40] Error processing gem {token['address']}: {e}")
                    continue

            # Process failed tokens
            X_failed = []
            y_failed = []
            logger.info(f"[2025-02-05 16:20:51] Processing failed {data_type}...")
            
            for token in failed_tokens:
                try:
                    initial_state = json.loads(token['initial_parameters'])
                    token_metrics = TokenMetrics(**initial_state)
                    features = self.token_analyzer.prepare_features(token_metrics, [])
                    
                    if not features:
                        continue
                        
                    feature_vector = process_features(token_metrics, features)
                    if feature_vector:
                        X_failed.append(feature_vector)
                        y_failed.append(0)  # 0 = failed
                        
                except Exception as e:
                    logger.error(f"[2025-02-05 16:20:51] Error processing failed token {token['address']}: {e}")
                    continue

            # Combine and normalize data
            if not X_success or not X_failed:
                logger.error(f"[2025-02-05 16:20:51] No valid training data for {data_type}")
                return
                
            X = np.vstack([X_success, X_failed])
            y = np.hstack([y_success, y_failed])
            
            # PAKEISTA: Naudojame pasirinktą scalerį
            X_scaled = current_scaler.fit_transform(X)
            
            # PAKEISTA: Sukuriame ir apmokome pasirinktą modelį
            new_model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=4,
                min_samples_leaf=2,
                random_state=42
            )
            
            new_model.fit(X_scaled, y)
            
            # PAKEISTA: Priskiriame naują modelį atitinkamam kintamajam
            if update_number == 0:
                self.new_token_model = new_model
            elif update_number == 1:
                self.update1_model = new_model
            elif update_number == 2:
                self.update2_model = new_model
            else:
                self.update3_model = new_model
            
            # Analyze feature importance
            feature_names = self._get_all_feature_names()
            importances = new_model.feature_importances_
            
            logger.info(f"\n=== FEATURE IMPORTANCE ANALYSIS FOR {data_type.upper()} ===")
            feature_importance = list(zip(feature_names, importances))
            feature_importance.sort(key=lambda x: x[1], reverse=True)
            
            logger.info(f"Top 20 Most Important Features for {data_type}:")
            for name, importance in feature_importance[:20]:
                logger.info(f"{name}: {importance*100:.2f}%")
            
            # Calculate training accuracy
            train_accuracy = new_model.score(X_scaled, y)
            logger.info(f"[2025-02-05 16:20:51] Training Accuracy for {data_type}: {train_accuracy*100:.2f}%")
            logger.info(f"[2025-02-05 16:20:51] Model successfully trained with {len(X)} samples")
            
        except Exception as e:
            logger.error(f"[2025-02-05 16:20:51] Error training model for {data_type}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    async def predict_potential(self, token_data: TokenMetrics, update_number: int = 0) -> float:
        """Prognozuoja token'o potencialą tapti gemu"""
        try:
            if token_data is None:
                logger.error("[2025-02-05 20:19:45] Token data is None")
                return 0.0
            
            # Parenkame tinkamą modelį ir scalerį
            if update_number == 0:
                model = self.new_token_model
                scaler = self.new_token_scaler
            elif update_number == 1:
                model = self.update1_model
                scaler = self.update1_scaler
            elif update_number == 2:
                model = self.update2_model
                scaler = self.update2_scaler
            elif update_number == 3:
                model = self.update3_model
                scaler = self.update3_scaler
            else:
                logger.error(f"[2025-02-05 20:19:45] Invalid update number: {update_number}")
                return 0.0

            if not model:
                logger.error(f"[2025-02-05 20:19:45] Model for update {update_number} not initialized")
                return 0.0

            # PAKEISTAS KODAS: Patikriname ar yra modelis ir apmokome jei reikia
            if not model:
                logger.info(f"[2025-02-05 16:17:12] Model for update {update_number} not found, training...")
                await self.train_model(update_number)
                if update_number == 0:
                    model = self.new_token_model
                elif update_number == 1:
                    model = self.update1_model
                elif update_number == 2:
                    model = self.update2_model
                else:
                    model = self.update3_model
                
                if not model:
                    logger.error(f"[2025-02-05 16:17:12] Failed to train model for update {update_number}")
                    return 0.0

            # Likęs kodas lieka tas pats, tik pakeičiame self.model į model ir self.scaler į scaler
            features = self.token_analyzer.prepare_features(token_data, [])
            if not features:
                logger.error(f"[2025-02-05 16:17:12] Failed to analyze token {token_data.address}")
                return 0.0
                
            feature_vector = []
            
            # Basic metrics
            feature_vector.extend([
                float(features['basic_metrics']['age_hours']),
                float(features['basic_metrics']['market_cap_normalized']),
                float(features['basic_metrics']['liquidity_ratio'])
            ])
            
            # Price/Volume metrics
            feature_vector.extend([
                float(token_data.market_cap or 0),
                float(token_data.liquidity or 0),
                float(token_data.volume_1h or 0),
                float(token_data.volume_24h or 0),
                float(token_data.price_change_1h or 0),
                float(token_data.price_change_24h or 0)
            ])
            
            # Holder metrics
            feature_vector.extend([
                float(features['holder_metrics']['holder_distribution']),
                float(features['holder_metrics']['value_per_holder']),
                float(features['holder_metrics']['top_holder_risk'])
            ])
            
            # Sniper metrics
            feature_vector.extend([
                float(features['sniper_metrics'].get('sniper_impact', 0)),
                float(features['sniper_metrics'].get('whale_dominance', 0)),
                float(features['sniper_metrics'].get('fish_ratio', 0)),
                float(features['sniper_metrics'].get('sniper_behavior_pattern', 0))
            ])
            
            # Dev metrics
            feature_vector.extend([
                float(features['dev_metrics']['dev_commitment']),
                float(features['dev_metrics']['owner_risk']),
                float(features['dev_metrics']['dev_sol_strength']),
                float(features['dev_metrics']['dev_token_risk']),
                float(features['dev_metrics']['ownership_score'])
            ])
            
            # Security metrics
            feature_vector.extend([
                float(features['security_metrics']['contract_security']),
                float(features['security_metrics']['lp_security']),
                float(features['security_metrics']['mint_risk']),
                float(features['security_metrics']['freeze_risk']),
                float(features['security_metrics']['overall_security_score'])
            ])

            # Scan metrics
            feature_vector.extend([
                float(features['scan_metrics']['scan_count']),
                float(features['scan_metrics']['scan_intensity']),
                float(features['scan_metrics']['scan_momentum'])
            ])
            
            # Social metrics
            feature_vector.extend([
                float(features['social_metrics']['social_presence']),
                float(features['social_metrics']['has_twitter']),
                float(features['social_metrics']['has_website']),
                float(features['social_metrics']['has_telegram']),
                float(features['social_metrics']['social_risk'])
            ])
            
            # Risk assessment
            feature_vector.extend([
                float(features['risk_assessment']['overall_risk']),
                float(features['risk_assessment']['pump_dump_risk']),
                float(features['risk_assessment']['security_risk']),
                float(features['risk_assessment']['holder_risk']),
                float(features['risk_assessment']['dev_risk'])
            ])
            
            # Contract flags
            feature_vector.extend([
                float(token_data.mint_enabled),
                float(token_data.freeze_enabled),
                float(token_data.owner_renounced)
            ])

            X = np.array(feature_vector).reshape(1, -1)
            # PAKEISTA: naudojame pasirinktą scalerį
            X_scaled = scaler.transform(X)
            
            if np.isnan(X_scaled).any():
                logger.error("[2025-02-05 16:17:12] NaN values in prediction features")
                return 0.0
                
            # PAKEISTA: naudojame pasirinktą modelį
            probability = model.predict_proba(X_scaled)[0][1]
            return probability
                
        except Exception as e:
            logger.error(f"[2025-02-05 16:17:12] Error predicting potential: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return 0.0

    def _log_detailed_analysis(self, token_data: TokenMetrics, features: Dict, probability: float, X_scaled: np.array):
        """Logina išsamią token'o analizę"""
        try:
            logger.info(f"\n=== TOKEN PREDICTION ANALYSIS ===")
            logger.info(f"Token: {token_data.symbol} ({token_data.address})")
            logger.info(f"Analysis Time: {datetime.now(timezone.utc)}")
            logger.info(f"Gem Probability: {probability*100:.2f}%")
            
            # Bazinė informacija
            logger.info("\n🔍 BASIC METRICS")
            logger.info(f"Age: {token_data.age}")
            logger.info(f"Market Cap: ${token_data.market_cap:,.0f}")
            logger.info(f"Liquidity: ${token_data.liquidity:,.0f}")
            logger.info(f"Volume 1h: ${token_data.volume_1h:,.0f}")
            
            # Holders & Snipers
            logger.info("\n👥 HOLDERS & SNIPERS")
            logger.info(f"Total Holders: {token_data.holders_count}")
            logger.info(f"Top Holder %: {token_data.top_holder_percentage:.1f}%")
            logger.info(f"Sniper Count: {token_data.sniper_count}")
            
            # Security Metrics
            logger.info("\n🔒 SECURITY STATUS")
            logger.info(f"• Contract Security: {features['security_metrics']['contract_security']:.2f}/1.0")
            logger.info(f"• LP Security: {features['security_metrics']['lp_security']:.2f}/1.0")
            logger.info(f"• Overall Security: {features['security_metrics']['overall_security_score']:.2f}/1.0")
            
            # Risk Assessment
            logger.info("\n⚠️ RISK ASSESSMENT")
            for risk_type, risk_value in features['risk_assessment'].items():
                risk_level = "LOW" if risk_value < 0.3 else "MEDIUM" if risk_value < 0.7 else "HIGH"
                logger.info(f"• {risk_type}: {risk_value:.2f} ({risk_level})")
            
            # Feature Impact Analysis
            self._log_feature_impact(X_scaled[0])
            
            # Final Decision
            self._log_decision_summary(probability, features)
            
        except Exception as e:
            logger.error(f"[2025-02-03 12:44:18] Error in detailed analysis: {e}")

    def _log_feature_impact(self, feature_values: np.array):
        """Logina feature'ų įtaką sprendimui"""
        try:
            feature_names = self._get_all_feature_names()
            importances = self.model.feature_importances_
            
            impacts = []
            for name, value, importance in zip(feature_names, feature_values, importances):
                impact = abs(value * importance)
                impacts.append((name, value, importance, impact))
            
            impacts.sort(key=lambda x: x[3], reverse=True)
            
            logger.info("\n📊 FEATURE IMPACT ANALYSIS")
            logger.info("Top 5 Influencing Factors:")
            for name, value, importance, impact in impacts[:5]:
                direction = "POSITIVE" if value > 0 else "NEGATIVE"
                logger.info(f"• {name}:")
                logger.info(f"  - Impact: {impact:.3f} ({direction})")
                logger.info(f"  - Importance: {importance*100:.1f}%")
                
        except Exception as e:
            logger.error(f"[2025-02-03 12:44:18] Error in feature impact analysis: {e}")

    def _log_decision_summary(self, probability: float, features: Dict):
        """Logina galutinį sprendimą"""
        try:
            logger.info("\n🎯 FINAL ASSESSMENT")
            if probability >= Config.MIN_GEM_PROBABILITY:
                logger.info("✅ HIGH POTENTIAL GEM")
                positive_factors = []
                for metric_type, metrics in features.items():
                    for name, value in metrics.items():
                        if isinstance(value, (int, float)) and value > 0.7:
                            positive_factors.append(f"{name} ({value:.2f})")
                logger.info(f"Main positive factors: {', '.join(positive_factors[:3])}")
            else:
                logger.info("❌ LOW POTENTIAL")
                concerns = []
                for metric_type, metrics in features.items():
                    for name, value in metrics.items():
                        if isinstance(value, (int, float)) and value < 0.3:
                            concerns.append(f"{name} ({value:.2f})")
                logger.info(f"Main concerns: {', '.join(concerns[:3])}")
                
        except Exception as e:
            logger.error(f"[2025-02-03 12:44:18] Error in decision summary: {e}")

    async def update_model_with_new_gem(self, token_data: TokenMetrics, update_number: int = 0):
        """Atnaujina modelį su nauju gem"""
        try:
            if token_data is None:
                logger.error(f"[2025-02-05 16:27:26] Cannot update model - token data is None")
                return

            # Parenkame modelį pagal update numerį
            if update_number == 0:
                model_type = "new token model"
            elif update_number == 1:
                model_type = "first update model"
            elif update_number == 2:
                model_type = "second update model"
            elif update_number == 3:
                model_type = "third update model"
            else:
                logger.error(f"[2025-02-05 16:27:26] Invalid update number: {update_number}")
                return

            # Atnaujiname statistiką
            self.successful_predictions += 1
            
            # Retrainuojame specifinį modelį su naujais duomenimis
            await self.train_model(update_number)
            
            # Loginame accuracy
            if self.predictions_made > 0:
                accuracy = (self.successful_predictions / self.predictions_made) * 100
                logger.info(f"[2025-02-05 16:27:26] Current {model_type} accuracy: {accuracy:.2f}%")
                logger.info(f"[2025-02-05 16:27:26] Total predictions for {model_type}: {self.predictions_made}")
                logger.info(f"[2025-02-05 16:27:26] Successful predictions for {model_type}: {self.successful_predictions}")
            
        except Exception as e:
            logger.error(f"[2025-02-05 16:27:26] Error updating {model_type}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    def _get_all_feature_names(self) -> List[str]:
        """Grąžina VISŲ features pavadinimus"""
        feature_names = [
            # Basic Metrics
            'age_hours',
            'market_cap_normalized',
            'liquidity_ratio',
            'market_cap',
            'liquidity', 
            'volume_1h',
            'volume_24h',
            'price_change_1h',
            'price_change_24h',
            'has_24h_data',

            # Holder Metrics
            'holder_distribution',
            'value_per_holder',
            'holder_retention', 
            'top_holder_risk',

            # Sniper Metrics
            'sniper_impact',
            'whale_dominance',
            'fish_ratio',
            'sniper_diversity',
            'sniper_behavior_pattern',

            # Dev Metrics
            'dev_commitment',
            'owner_risk',
            'dev_sol_strength',
            'dev_token_risk',
            'ownership_score',

            # Security Metrics 
            'contract_security',
            'lp_security',
            'mint_risk',
            'freeze_risk',
            'overall_security_score',

            # Social Metrics
            'social_presence',
            'has_twitter',
            'has_website',
            'has_telegram',
            'social_risk',

            # Scan Metrics
            'scan_count',
            'scan_intensity',
            'scan_momentum',

            # Risk Assessment
            'overall_risk',
            'pump_dump_risk', 
            'security_risk',
            'holder_risk',
            'dev_risk',

            # Contract Flags
            'mint_enabled',
            'freeze_enabled',
            'owner_renounced'
        ]

        # Debug info
        logger.info(f"\n=== FEATURE LIST ({len(feature_names)} total) ===")
        for i, feature in enumerate(feature_names):
            logger.info(f"{i+1}. {feature}")

        return feature_names

async def analyze_success_patterns(self):
    """Analizuoja sėkmingų gemų šablonus ir laiko faktorius"""
    try:
        logger.info("[2025-02-03 12:46:07] Starting success pattern analysis...")
        successful_tokens = await self.db.get_all_gems()
        
        # Grupuojame pagal laiką iki 10x
        time_groups = {
            'quick': [],    # < 1 valanda
            'medium': [],   # 1-6 valandos
            'slow': []      # > 6 valandos
        }
        
        patterns = {
            'quick': {},
            'medium': {},
            'slow': {}
        }
        
        for token in successful_tokens:
            try:
                time_to_10x = token['time_to_10x']
                initial_state = json.loads(token['initial_parameters'])
                token_metrics = TokenMetrics(**initial_state)
                
                # Nustatome grupę
                if time_to_10x < 3600:  # < 1h
                    group = 'quick'
                elif time_to_10x < 21600:  # < 6h
                    group = 'medium'
                else:
                    group = 'slow'
                    
                time_groups[group].append(token)
                
                # Analizuojame kiekvienos grupės patterns
                features = self.token_analyzer.prepare_features(token_metrics, [])
                if not features:
                    continue
                    
                if group not in patterns:
                    patterns[group] = {
                        'market_caps': [],
                        'liquidities': [],
                        'holder_counts': [],
                        'sniper_counts': [],
                        'security_scores': [],
                        'social_scores': [],
                        'risk_scores': []
                    }
                    
                patterns[group]['market_caps'].append(token_metrics.market_cap)
                patterns[group]['liquidities'].append(token_metrics.liquidity)
                patterns[group]['holder_counts'].append(token_metrics.holders_count)
                patterns[group]['sniper_counts'].append(token_metrics.sniper_count)
                patterns[group]['security_scores'].append(features['security_metrics']['overall_security_score'])
                patterns[group]['social_scores'].append(features['social_metrics']['social_presence'])
                patterns[group]['risk_scores'].append(features['risk_assessment']['overall_risk'])
                
            except Exception as e:
                logger.error(f"[2025-02-03 12:46:07] Error processing token {token['address']}: {e}")
                continue
        
        logger.info("\n=== GEM SUCCESS PATTERN ANALYSIS ===")
        
        for group in ['quick', 'medium', 'slow']:
            count = len(time_groups[group])
            if count == 0:
                continue
                
            logger.info(f"\n🔍 {group.upper()} GEMS (Time to 10x: {'<1h' if group == 'quick' else '1-6h' if group == 'medium' else '>6h'})")
            logger.info(f"Total Gems in Group: {count}")
            
            p = patterns[group]
            logger.info("\nTypical Characteristics:")
            logger.info(f"• Market Cap: ${np.median(p['market_caps']):,.0f} (median)")
            logger.info(f"• Liquidity: ${np.median(p['liquidities']):,.0f} (median)")
            logger.info(f"• Holders: {np.median(p['holder_counts']):.0f} (median)")
            logger.info(f"• Snipers: {np.median(p['sniper_counts']):.0f} (median)")
            logger.info(f"• Security Score: {np.mean(p['security_scores']):.2f}/1.0")
            logger.info(f"• Social Score: {np.mean(p['social_scores']):.2f}/1.0")
            logger.info(f"• Risk Score: {np.mean(p['risk_scores']):.2f}/1.0")
            
        return patterns
        
    except Exception as e:
        logger.error(f"[2025-02-03 12:46:07] Error analyzing success patterns: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

async def analyze_trend_changes(self):
    """Analizuoja kaip keičiasi gemų šablonai per laiką"""
    try:
        logger.info("[2025-02-03 12:46:07] Starting trend change analysis...")
        successful_tokens = await self.db.get_all_gems()
        
        # Grupuojame pagal mėnesius
        monthly_patterns = {}
        
        for token in successful_tokens:
            try:
                discovery_time = datetime.fromisoformat(str(token['discovery_timestamp']))
                month_key = f"{discovery_time.year}-{discovery_time.month:02d}"
                
                initial_state = json.loads(token['initial_parameters'])
                token_metrics = TokenMetrics(**initial_state)
                features = self.token_analyzer.prepare_features(token_metrics, [])
                
                if not features:
                    continue
                    
                if month_key not in monthly_patterns:
                    monthly_patterns[month_key] = {
                        'count': 0,
                        'avg_market_cap': 0,
                        'avg_liquidity': 0,
                        'avg_holders': 0,
                        'avg_security_score': 0,
                        'avg_social_score': 0,
                        'avg_risk_score': 0,
                        'success_time': []
                    }
                
                p = monthly_patterns[month_key]
                p['count'] += 1
                p['avg_market_cap'] += token_metrics.market_cap
                p['avg_liquidity'] += token_metrics.liquidity
                p['avg_holders'] += token_metrics.holders_count
                p['avg_security_score'] += features['security_metrics']['overall_security_score']
                p['avg_social_score'] += features['social_metrics']['social_presence']
                p['avg_risk_score'] += features['risk_assessment']['overall_risk']
                p['success_time'].append(token['time_to_10x'])
                
            except Exception as e:
                logger.error(f"[2025-02-03 12:46:07] Error processing token {token['address']}: {e}")
                continue
        
        # Skaičiuojame vidurkius ir analizuojame trendus
        logger.info("\n=== GEM TREND ANALYSIS OVER TIME ===")
        
        sorted_months = sorted(monthly_patterns.keys())
        for month in sorted_months:
            p = monthly_patterns[month]
            count = p['count']
            if count == 0:
                continue
                
            # Skaičiuojame vidurkius
            for key in ['avg_market_cap', 'avg_liquidity', 'avg_holders', 'avg_security_score', 
                       'avg_social_score', 'avg_risk_score']:
                p[key] /= count
                
            logger.info(f"\n📅 {month} Analysis (Total Gems: {count})")
            logger.info(f"• Average Market Cap: ${p['avg_market_cap']:,.0f}")
            logger.info(f"• Average Liquidity: ${p['avg_liquidity']:,.0f}")
            logger.info(f"• Average Holders: {p['avg_holders']:.0f}")
            logger.info(f"• Average Security Score: {p['avg_security_score']:.2f}/1.0")
            logger.info(f"• Average Social Score: {p['avg_social_score']:.2f}/1.0")
            logger.info(f"• Average Risk Score: {p['avg_risk_score']:.2f}/1.0")
            logger.info(f"• Median Time to 10x: {np.median(p['success_time'])/3600:.1f}h")
        
        return monthly_patterns
        
    except Exception as e:
        logger.error(f"[2025-02-03 12:46:07] Error analyzing trend changes: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

async def analyze_feature_correlations(self):
    """Analizuoja feature'ų tarpusavio koreliacijas ir jų įtaką gem statusui"""
    try:
        logger.info(f"[2025-02-03 12:46:07] Starting feature correlation analysis...")
        
        successful_tokens = await self.db.get_all_gems()
        failed_tokens = await self.db.get_failed_tokens()
        
        all_features = []
        all_labels = []
        
        # Renkame features iš sėkmingų ir nesėkmingų tokenų
        for token in successful_tokens + failed_tokens:
            try:
                initial_state = json.loads(token['initial_parameters'])
                token_metrics = TokenMetrics(**initial_state)
                features = self.token_analyzer.prepare_features(token_metrics, [])
                
                if not features:
                    continue
                    
                feature_vector = []
                for category in ['basic_metrics', 'price_volume_metrics', 'holder_metrics', 
                               'sniper_metrics', 'dev_metrics', 'social_metrics', 
                               'security_metrics', 'wallet_behavior', 'risk_assessment']:
                    feature_vector.extend(list(features[category].values()))
                
                all_features.append(feature_vector)
                all_labels.append(1 if token in successful_tokens else 0)
                
            except Exception as e:
                logger.error(f"[2025-02-03 12:46:07] Error processing token {token['address']}: {e}")
                continue
        
        if not all_features:
            logger.error("[2025-02-03 12:46:07] No features to analyze")
            return
        
        # Konvertuojame į numpy arrays
        X = np.array(all_features)
        y = np.array(all_labels)
        
        # Skaičiuojame koreliacijas
        feature_names = self._get_all_feature_names()
        correlations = []
        
        for i, feature in enumerate(feature_names):
            correlation = np.corrcoef(X[:, i], y)[0, 1]
            correlations.append((feature, correlation))
        
        # Rūšiuojame pagal absoliučią koreliaciją
        correlations.sort(key=lambda x: abs(x[1]), reverse=True)
        
        logger.info("\n=== FEATURE CORRELATION ANALYSIS ===")
        logger.info("Top 20 Most Correlated Features with Gem Status:")
        
        for feature, correlation in correlations[:20]:
            direction = "POSITIVE" if correlation > 0 else "NEGATIVE"
            logger.info(f"• {feature}: {abs(correlation):.3f} ({direction})")
        
        # Analizuojame feature kombinacijas
        logger.info("\nTop Feature Combinations:")
        
        top_features_idx = [feature_names.index(f[0]) for f in correlations[:5]]
        X_top = X[:, top_features_idx]
        
        success_features = X_top[y == 1]
        fail_features = X_top[y == 0]
        
        logger.info("\nTypical Successful Pattern:")
        for i, feature in enumerate(correlations[:5]):
            avg_success = np.mean(success_features[:, i])
            logger.info(f"• {feature[0]}: {avg_success:.3f}")
        
        logger.info("\nTypical Failed Pattern:")
        for i, feature in enumerate(correlations[:5]):
            avg_fail = np.mean(fail_features[:, i])
            logger.info(f"• {feature[0]}: {avg_fail:.3f}")
        
    except Exception as e:
        logger.error(f"[2025-02-03 12:46:07] Error analyzing feature correlations: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
    

class DatabaseManager:
    def __init__(self):
        self.db = AsyncDatabase()
        self.is_setup = False

    async def setup_database(self):
        """Initialize database tables"""
        if not self.is_setup:
            await self.db.connect()  # Pirma prisijungiame
            self.is_setup = True
            logger.info(f"[{datetime.now(timezone.utc)}] Database setup completed")

    async def fetch_all(self, query: str, params=None):
        """Gauna visus rezultatus iš užklausos"""
        try:
            if not self.db:
                await self.setup_database()
            # Perduodame params tik jei jie yra
            if params is not None:
                return await self.db.fetch_all(query, params)
            return await self.db.fetch_all(query)
        except Exception as e:
            logger.error(f"[2025-02-03 15:17:34] Error in DatabaseManager.fetch_all: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            raise

    async def fetch_one(self, query: str, params=None):
        """Gauna vieną rezultatą iš užklausos"""
        try:
            if not self.db:
                await self.setup_database()
                
            # Išpakuojame tuple jei jis yra dvigubas
            if isinstance(params, tuple) and len(params) == 1 and isinstance(params[0], tuple):
                params = params[0]
            
            # Išpakuojame tuple jei jis yra viengubas su vienu elementu
            if isinstance(params, tuple) and len(params) == 1:
                params = params[0]
                
            return await self.db.fetch_one(query, params)
        except Exception as e:
            logger.error(f"[{datetime.now(timezone.utc)}] Error in DatabaseManager.fetch_one: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            raise

    async def get_update_count(self, token_address: str) -> int:
        """Grąžina kiek update'ų turi token'as"""
        try:
            query = """
            SELECT COUNT(*) as count 
            FROM token_updates 
            WHERE address = ?
            """
            result = await self.db.fetch_one(query, token_address)
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"[2025-02-05 15:34:58] Error getting update count: {e}")
            return 0
                
    async def get_initial_state(self, address: str):
        """Gauna pradinę token'o būseną"""
        query = """
        SELECT * FROM token_initial_states 
        WHERE address = ?
        """
        result = await self.db.fetch_one(query, address)
        if not result:
            return None
            
        # Konvertuojame į TokenMetrics objektą
        return TokenMetrics(
            address=result['address'],
            name=result['name'],
            symbol=result['symbol'],
            age=result['age'],
            market_cap=result['market_cap'],
            liquidity=result['liquidity'],
            volume_1h=result['volume_1h'],
            volume_24h=result['volume_24h'],
            price_change_1h=result['price_change_1h'],
            price_change_24h=result['price_change_24h'],
            mint_enabled=result['mint_enabled'],
            freeze_enabled=result['freeze_enabled'],
            lp_burnt_percentage=result['lp_burnt_percentage'],
            holders_count=result['holders_count'],
            top_holder_percentage=result['top_holder_percentage'],
            sniper_count=result['sniper_count'],
            sniper_percentage=result['sniper_percentage'],
            first_20_fresh=result['first_20_fresh'],
            ath_market_cap=result['ath_market_cap'],
            ath_multiplier=result['ath_multiplier'],
            owner_renounced=result['owner_renounced'],
            telegram_url=result['telegram_url'],
            twitter_url=result['twitter_url'],
            website_url=result['website_url'],
            dev_sol_balance=result['dev_sol_balance'],
            dev_token_percentage=result['dev_token_percentage'],
            sniper_wallets=json.loads(result['sniper_wallets']) if result['sniper_wallets'] else None 
        )
        
    async def save_initial_state(self, token_data: TokenMetrics):
        """Išsaugo pradinį token'o būvį"""
        base_data = (
            token_data.address, token_data.name, token_data.symbol, token_data.age,
            token_data.market_cap, token_data.liquidity, token_data.volume_1h, token_data.volume_24h,
            token_data.price_change_1h, token_data.price_change_24h,
            token_data.mint_enabled, token_data.freeze_enabled, token_data.lp_burnt_percentage,
            token_data.holders_count, token_data.top_holder_percentage,
            token_data.sniper_count, token_data.sniper_percentage, token_data.first_20_fresh,
            token_data.ath_market_cap, token_data.ath_multiplier,
            token_data.owner_renounced, token_data.telegram_url, token_data.twitter_url, token_data.website_url,
            token_data.dev_sol_balance, token_data.dev_token_percentage,
            datetime.now(timezone.utc),  # first_seen
            'new',  # status
            json.dumps(token_data.sniper_wallets) if token_data.sniper_wallets else None  # sniper_wallets
        )

        query = """
        INSERT OR REPLACE INTO token_initial_states (
            address, name, symbol, age,
            market_cap, liquidity, volume_1h, volume_24h,
            price_change_1h, price_change_24h,
            mint_enabled, freeze_enabled, lp_burnt_percentage,
            holders_count, top_holder_percentage,
            sniper_count, sniper_percentage, first_20_fresh,
            ath_market_cap, ath_multiplier,
            owner_renounced, telegram_url, twitter_url, website_url,
            dev_sol_balance, dev_token_percentage,
            first_seen, status, sniper_wallets
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        await self.db.execute(query, base_data)
        
    async def is_gem(self, address: str) -> bool:
        """Tikrina ar token'as jau pažymėtas kaip gem"""
        query = """
        SELECT status FROM token_initial_states 
        WHERE address = ?
        """
        result = await self.db.fetch_one(query, address)
        return result and result['status'] == 'gem'

    async def save_token_update(self, token_address: str, new_data: TokenMetrics, update_number: int = 0):
        """Išsaugo token'o atnaujinimą"""
        try:
            logger.info(f"[{datetime.now(timezone.utc)}] Saving update for token {token_address}")
            initial_data = await self.get_initial_state(token_address)
            if not initial_data:
                logger.warning(f"[{datetime.now(timezone.utc)}] No initial state found for token: {token_address}")
                return

            # Patikriname, ar šis update_number jau egzistuoja
            check_query = """
            SELECT COUNT(*) as count 
            FROM token_updates 
            WHERE address = ? AND update_number = ?
            """
            existing = await self.db.fetch_one(check_query, (token_address, update_number))
            if existing and existing['count'] > 0:
                logger.warning(f"[{datetime.now(timezone.utc)}] Update #{update_number} already exists for token {token_address}")
                return

            # Patikriname ar yra spragų update_number sekoje
            sequence_query = """
            SELECT MAX(update_number) as max_update
            FROM token_updates 
            WHERE address = ?
            """
            max_result = await self.db.fetch_one(sequence_query, token_address)
            max_update = max_result['max_update'] if max_result and max_result['max_update'] is not None else -1

            if update_number > max_update + 1:
                logger.warning(f"[{datetime.now(timezone.utc)}] Gap detected in update sequence for {token_address}. Expected {max_update + 1}, got {update_number}")
                return

            current_multiplier = new_data.market_cap / initial_data.market_cap
            metrics_json = json.dumps(new_data.to_dict())

            # Įterpiame update
            query = """
            INSERT INTO token_updates (
                address, all_metrics, timestamp, current_multiplier, update_number
            ) VALUES (?, ?, ?, ?, ?)
            """
            await self.db.execute(query, (
                token_address,
                metrics_json,
                datetime.now(timezone.utc),
                current_multiplier,
                update_number
            ))

            logger.info(f"[{datetime.now(timezone.utc)}] Successfully saved update #{update_number} for token {token_address}")

        except Exception as e:
            logger.error(f"[{datetime.now(timezone.utc)}] Error saving token update: {e}")
            raise

    async def save_sniper_wallets(self, wallets: List[Dict]):
        """Išsaugo sniper wallet'us į DB"""
        try:
            for wallet in wallets:
                await self.db.execute("""
                    INSERT OR REPLACE INTO sniper_wallets (address, type)
                    VALUES (?, ?)
                """, (wallet['address'], wallet['type']))
                
            logger.info(f"[{datetime.now(timezone.utc)}] Saved {len(wallets)} sniper wallets to DB")
        except Exception as e:
            logger.error(f"Error saving sniper wallets: {e}")
        
    async def mark_as_gem(self, token_address: str, update_number: int = 0):
        """Pažymi token'ą kaip gem ir išsaugo į successful_tokens"""
        try:
            current_time = datetime.now(timezone.utc)
            
            # Patikrinam ar jau ne gem
            if await self.is_gem(token_address):
                logger.info(f"[2025-02-05 16:48:44] Token {token_address} is already marked as gem")
                return False
                
            # Patikriname ar jau yra successful_tokens lentelėje
            check_query = "SELECT address FROM successful_tokens WHERE address = ? AND update_number = ?"
            existing = await self.db.fetch_one(check_query, (token_address, update_number))
            
            if existing:
                logger.info(f"[2025-02-05 16:48:44] Token {token_address} already in successful_tokens")
                return True
                
            # 1. Atnaujina statusą
            await self.db.execute(
                "UPDATE token_initial_states SET status = 'gem' WHERE address = ?",
                token_address
            )
            logger.info(f"[2025-02-05 16:48:44] Updated status to gem for {token_address}")
            
            # 2. Gauna pradinę būseną ir laiką iki 10x
            initial_data = await self.get_initial_state(token_address)
            if not initial_data:
                logger.error(f"[2025-02-05 16:48:44] No initial state found for {token_address}")
                return False
                
            time_to_10x = await self._calculate_time_to_10x(token_address)
            logger.info(f"[2025-02-05 16:48:44] Calculated time to 10x for {token_address}: {time_to_10x} seconds")
            
            try:
                # 3. Išsaugo į successful_tokens su REPLACE INTO vietoj INSERT
                query = """
                REPLACE INTO successful_tokens (
                    address, initial_parameters, time_to_10x, discovery_timestamp, update_number
                ) VALUES (?, ?, ?, ?, ?)
                """
                
                # Konvertuojame į JSON string
                initial_parameters_json = json.dumps(initial_data.to_dict())
                
                await self.db.execute(query, (
                    token_address,
                    initial_parameters_json,
                    time_to_10x,
                    current_time,
                    update_number
                ))
                
                logger.info(f"[2025-02-05 16:48:44] Successfully marked {token_address} as gem")
                return True
                
            except Exception as insert_error:
                logger.error(f"[2025-02-05 16:48:44] Error inserting into successful_tokens: {insert_error}")
                return False
                
        except Exception as e:
            logger.error(f"[2025-02-05 16:48:44] Error marking as gem: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
        
    async def get_all_gems(self, update_number: int = 0):
        """Gauna visus sėkmingus tokenus mokymui pagal update numerį"""
        try:
            # Grąžiname visus gemus, nepriklausomai nuo update_number
            query = """
            SELECT * FROM successful_tokens 
            ORDER BY discovery_timestamp DESC
            """
            results = await self.db.fetch_all(query)
            logger.info(f"[{datetime.now(timezone.utc)}] Found {len(results) if results else 0} gems for update #{update_number} in database")
            return results
            
        except Exception as e:
            logger.error(f"[{datetime.now(timezone.utc)}] Error getting gems: {e}")
            return []
        
    async def get_active_tokens(self):
        """Gauna visus aktyvius stebimus tokenus"""
        query = """
        SELECT * FROM token_initial_states 
        WHERE status = 'new'
        """
        return await self.db.fetch_all(query)

    async def check_database(self):
        """Patikrina duomenų bazės būseną"""
        try:
            current_time = datetime.now(timezone.utc)
            
            # Tikriname token_initial_states
            initial_states = await self.db.fetch_all("""
                SELECT COUNT(*) as count, status, COUNT(DISTINCT address) as unique_addresses 
                FROM token_initial_states 
                GROUP BY status
            """)
            
            # Tikriname nesutapimus tarp lentelių
            inconsistencies = await self.db.fetch_all("""
                SELECT t.address, t.status, 
                    CASE 
                        WHEN t.status = 'gem' AND s.address IS NULL THEN 'Missing from successful_tokens'
                        WHEN t.status = 'failed' AND f.address IS NULL THEN 'Missing from failed_tokens'
                        ELSE NULL 
                    END as issue
                FROM token_initial_states t
                LEFT JOIN successful_tokens s ON t.address = s.address
                LEFT JOIN failed_tokens f ON t.address = f.address
                WHERE (t.status = 'gem' AND s.address IS NULL)
                   OR (t.status = 'failed' AND f.address IS NULL)
            """)
            
            if inconsistencies:
                logger.warning(f"[{current_time}] Found data inconsistencies:")
                for inc in inconsistencies:
                    logger.warning(f"[{current_time}] Address {inc['address']} ({inc['status']}): {inc['issue']}")
                    
                    # Automatiškai pataisome
                    if inc['status'] == 'gem':
                        initial_data = await self.get_initial_state(inc['address'])
                        if initial_data:
                            await self.db.execute("""
                                INSERT INTO successful_tokens (
                                    address, initial_parameters, time_to_10x, discovery_timestamp
                                ) VALUES (?, ?, ?, ?)
                            """, (
                                inc['address'],
                                json.dumps(initial_data.to_dict()),
                                0,
                                current_time
                            ))
                            logger.info(f"[{current_time}] Fixed missing gem: {inc['address']}")

            # Rodyti statistiką
            for state in initial_states:
                logger.info(f"[{current_time}] Initial states - Status: {state['status']}, "
                           f"Count: {state['count']}, Unique addresses: {state['unique_addresses']}")

            # Tikriname successful_tokens
            successful = await self.db.fetch_all("SELECT COUNT(*) as count FROM successful_tokens")
            failed = await self.db.fetch_all("SELECT COUNT(*) as count FROM failed_tokens")  # Pridėta failed tokens statistika
            
            logger.info(f"[{current_time}] Successful tokens count: {successful[0]['count']}")
            logger.info(f"[{current_time}] Failed tokens count: {failed[0]['count']}")  # Naujas log'as

            # Tikriname token_updates
            updates = await self.db.fetch_all("""
                SELECT COUNT(*) as count, COUNT(DISTINCT address) as unique_addresses 
                FROM token_updates
            """)
            logger.info(f"[{current_time}] Updates count: {updates[0]['count']}, "
                       f"Unique addresses: {updates[0]['unique_addresses']}")

            # Patikriname duomenų bazės dydį ir veikimą
            logger.info(f"[{current_time}] Database health check completed successfully")

        except Exception as e:
            logger.error(f"[{current_time}] Error checking database: {e}")
    
    async def _calculate_time_to_10x(self, token_address: str) -> int:
        """Apskaičiuoja laiką (sekundėmis) per kurį token'as pasiekė 10x"""
        try:
            # Gauname first_seen tiesiai iš token_initial_states
            first_seen_query = """
            SELECT first_seen 
            FROM token_initial_states 
            WHERE address = ?
            """
            initial_result = await self.db.fetch_one(first_seen_query, token_address)
            if not initial_result:
                logger.warning(f"[2025-02-01 21:45:44] No initial state found for {token_address}")
                return 0

            initial_time = datetime.fromisoformat(str(initial_result['first_seen']))

            # Gauname atnaujinimus
            updates_query = """
            SELECT timestamp, current_multiplier 
            FROM token_updates 
            WHERE address = ? 
            ORDER BY timestamp ASC
            """
            updates = await self.db.fetch_all(updates_query, token_address)
            
            if not updates:
                return 0

            # Ieškome pirmo 10x
            for update in updates:
                if update['current_multiplier'] >= 10:
                    update_time = datetime.fromisoformat(str(update['timestamp']))
                    return int((update_time - initial_time).total_seconds())
            
            return 0
            
        except Exception as e:
            logger.error(f"[2025-02-01 21:45:44] Error calculating time to 10x: {e}")
            return 0

    async def show_database_contents(self):
        """Parodo VISUS duomenis iš duomenų bazės"""
        try:
            # 1. Parodome token_initial_states su VISAIS stulpeliais
            logger.info("\n=== TOKEN INITIAL STATES (FULL DATA) ===")
            initial_states = await self.db.fetch_all("""
                SELECT * FROM token_initial_states 
                ORDER BY first_seen DESC
            """)
            for token in initial_states:
                logger.info(f"\nToken Details:")
                for column, value in dict(token).items():
                    logger.info(f"{column}: {value}")
                logger.info("------------------------")

            # 2. Parodome successful_tokens su VISAIS duomenimis
            logger.info("\n=== SUCCESSFUL TOKENS (GEMS) - FULL DATA ===")
            successful = await self.db.fetch_all("""
                SELECT * FROM successful_tokens
                ORDER BY discovery_timestamp DESC
            """)
            for gem in successful:
                logger.info(f"\nGem Details:")
                for column, value in dict(gem).items():
                    if column == 'initial_parameters':
                        # Jei JSON, išskaidome į atskiras eilutes
                        params = json.loads(value)
                        logger.info("Initial Parameters:")
                        for param_key, param_value in params.items():
                            logger.info(f"  {param_key}: {param_value}")
                    else:
                        logger.info(f"{column}: {value}")
                logger.info("------------------------")

            # 3. Parodome VISUS token_updates 
            logger.info("\n=== ALL TOKEN UPDATES - FULL DATA ===")
            updates = await self.db.fetch_all("""
                SELECT * FROM token_updates 
                ORDER BY timestamp DESC
            """)
            for update in updates:
                logger.info(f"\nUpdate Details:")
                for column, value in dict(update).items():
                    if column == 'all_metrics':
                        # Jei JSON, išskaidome į atskiras eilutes
                        metrics = json.loads(value)
                        logger.info("All Metrics:")
                        for metric_key, metric_value in metrics.items():
                            logger.info(f"  {metric_key}: {metric_value}")
                    else:
                        logger.info(f"{column}: {value}")
                logger.info("------------------------")

            # 4. ČIAAAAAA pridedame sniper_wallets rodymą! 👇
            logger.info("\n=== SNIPER WALLETS - FULL DATA ===")
            sniper_wallets = await self.db.fetch_all("""
                SELECT * FROM sniper_wallets 
                ORDER BY last_active DESC
            """)
            for wallet in sniper_wallets:
                logger.info(f"\nSniper Wallet Details:")
                for column, value in dict(wallet).items():
                    logger.info(f"{column}: {value}")
                logger.info("------------------------")

        except Exception as e:
            logger.error(f"[{datetime.now(timezone.utc)}] Error showing database contents: {e}")
            logger.error(f"Exception details: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

                
    async def get_failed_tokens(self, update_number: int = 0):
        """Gauna visus nepavykusius tokenus"""
        try:
            query = """
            SELECT * FROM failed_tokens
            ORDER BY discovery_timestamp DESC
            """
            results = await self.db.fetch_all(query)
            logger.info(f"[{datetime.now(timezone.utc)}] Found {len(results)} failed tokens")
            return results
            
        except Exception as e:
            logger.error(f"[{datetime.now(timezone.utc)}] Error getting failed tokens: {e}")
            return []
    
    async def get_latest_token_update(self, token_address: str):
        """Gauna paskutinį token'o atnaujinimą iš DB"""
        try:
            query = """
            SELECT all_metrics 
            FROM token_updates 
            WHERE address = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
            """
            result = await self.db.fetch_one(query, token_address)
            if result:
                return json.loads(result['all_metrics'])
            return None
        except Exception as e:
            logger.error(f"[2025-02-03 18:07:45] Error getting latest token update: {e}")
            return None
            
    async def mark_as_failed(self, token_address: str, reason: str):
        """Pažymi token'ą kaip nepavykusį"""
        try:
            # 1. Gauname pradinę būseną
            initial_data = await self.get_initial_state(token_address)
            if not initial_data:
                return
                
            # 2. Atnaujiname statusą
            await self.db.execute(
                "UPDATE token_initial_states SET status = 'failed' WHERE address = ?",
                token_address
            )
            
            # 3. Įrašome į failed_tokens
            query = """
            INSERT INTO failed_tokens (
                address, initial_parameters, failure_reason, discovery_timestamp
            ) VALUES (?, ?, ?, ?)
            """
            await self.db.execute(query, (
                token_address,
                json.dumps(initial_data.to_dict()),
                reason,
                datetime.now(timezone.utc)
            ))
            
            logger.info(f"[{datetime.now(timezone.utc)}] Token marked as failed: {token_address} - {reason}")
            
        except Exception as e:
            logger.error(f"[{datetime.now(timezone.utc)}] Error marking token as failed: {e}")

    async def check_update_numbers(self):
        """Tikrina update_number pasiskirstymą duomenų bazėje"""
        try:
            logger.info("\n=== UPDATE NUMBERS DISTRIBUTION ===")
            results = await self.db.fetch_all("""
                SELECT update_number, COUNT(*) as count 
                FROM token_updates 
                GROUP BY update_number 
                ORDER BY update_number
            """)
            
            for row in results:
                logger.info(f"Update #{row['update_number']}: {row['count']} records")
                
            # Patikriname ar yra trūkstamų update numerių
            logger.info("\n=== TOKENS WITHOUT UPDATES ===")
            missing_updates = await self.db.fetch_all("""
                SELECT t.address, t.status, 
                       (SELECT COUNT(*) FROM token_updates tu WHERE tu.address = t.address) as update_count
                FROM token_initial_states t
                WHERE t.status = 'gem'
                ORDER BY update_count ASC
            """)
            
            for row in missing_updates:
                logger.info(f"Token {row['address']} (status: {row['status']}) has {row['update_count']} updates")
                
        except Exception as e:
            logger.error(f"[{datetime.now(timezone.utc)}] Error checking update numbers: {e}")

    async def get_security_check(self, address: str):
        """Gauna token'o security patikrinimo rezultatus"""
        query = """
        SELECT security_risk, check_time 
        FROM token_security 
        WHERE address = ?
        """
        return await self.db.fetch_one(query, address)

    async def save_security_check(self, address: str, security_risk: float):
        """Išsaugo token'o security patikrinimo rezultatus"""
        query = """
        INSERT OR REPLACE INTO token_security (
            address, security_risk, check_time
        ) VALUES (?, ?, CURRENT_TIMESTAMP)
        """
        await self.db.execute(query, (address, security_risk))

    

class TokenAnalytics:
    def __init__(self, db_manager):
        self.db = db_manager
        
    async def analyze_success_patterns(self):
        """Analizuoja sėkmingų tokenų šablonus"""
        gems = await self.db.get_all_gems()
        
        patterns = {
            'market_patterns': await self._analyze_market_metrics(gems),
            'security_patterns': await self._analyze_security_metrics(gems),
            'community_patterns': await self._analyze_community_metrics(gems),
            'dev_patterns': await self._analyze_dev_metrics(gems)
        }
        
        return patterns
        
    async def compare_with_successful(self, token_data: TokenMetrics):
        """Lygina naują token'ą su sėkmingais"""
        patterns = await self.analyze_success_patterns()
        similarity_score = self._calculate_similarity(token_data, patterns)
        return similarity_score

    async def _analyze_market_metrics(self, gems):
        """Analizuoja rinkos metrikas"""
        market_metrics = []
        for gem in gems:
            market_metrics.append({
                'liquidity_ratio': gem.liquidity / gem.market_cap if gem.market_cap else 0,
                'volume_ratio': gem.volume_24h / gem.market_cap if gem.market_cap else 0,
                'price_change': gem.price_change_24h
            })
        return market_metrics

    async def _analyze_security_metrics(self, gems):
        """Analizuoja saugumo metrikas"""
        return {
            'mint_enabled_ratio': sum(1 for g in gems if g.mint_enabled) / len(gems),
            'freeze_enabled_ratio': sum(1 for g in gems if g.freeze_enabled) / len(gems),
            'avg_lp_burnt': sum(g.lp_burnt_percentage for g in gems) / len(gems)
        }



class TokenAnalyzer:
    def __init__(self, db_manager, ml_analyzer):
        self.db = db_manager
        self.ml = ml_analyzer

    def prepare_features(self, token: TokenMetrics, updates: List[TokenUpdate]) -> Dict:
        """Paruošia visus features ML modeliui"""
        try:
            if token is None:
                logger.error(f"[2025-02-01 21:17:42] Token is None")
                return None

            try:
                return {
                    # 1. Pagrindinė informacija ir jos analizė
                    'basic_metrics': self._analyze_basic_metrics(token),

                    # Pridedame naują kategoriją
                    'scan_metrics': {
                        'scan_count': token.total_scans,
                        'scan_intensity': token.total_scans / max(self._convert_age_to_hours(token.age), 1),  # Scans per hour
                        'scan_momentum': 1.0 if token.total_scans > 100 else token.total_scans / 100.0  # Normalizuotas scan_count
                    },
                    
                    # 2. Kainų ir volume analizė
                    'price_volume_metrics': self._analyze_price_volume(token, updates),
                    
                    # 3. Holders analizė
                    'holder_metrics': self._analyze_holders(token, updates),
                    
                    # 4. Snipers analizė
                    'sniper_metrics': self._analyze_snipers(token),
                    
                    # 5. Dev/Owner analizė
                    'dev_metrics': self._analyze_dev_metrics(token),
                    
                    # 6. Socialinių metrikų analizė
                    'social_metrics': self._analyze_social_metrics(token),
                    
                    # 7. Saugumo metrikų analizė
                    'security_metrics': self._analyze_security(token),
                    
                    # 8. Laiko serijos analizė
                    'time_series_metrics': self._analyze_time_series(updates),
                    
                    # 9. Wallet'ų elgsenos analizė
                    'wallet_behavior': self._analyze_wallets(token.sniper_wallets if token.sniper_wallets else []),
                    
                    # 10. Rizikos vertinimas
                    'risk_assessment': self._calculate_risk_metrics(token)
                }
                
            except Exception as e:
                logger.error(f"[2025-02-01 21:17:42] Error analyzing features for {token.address}: {str(e)}")
                return None

        except Exception as e:
            logger.error(f"[2025-02-01 21:17:42] Error preparing features: {str(e)}")
            return None

    def _analyze_basic_metrics(self, token: TokenMetrics) -> Dict:
        """Analizuoja pagrindinius metrikus"""
        return {
            'age_hours': self._convert_age_to_hours(token.age),
            'market_cap_normalized': token.market_cap / token.ath_market_cap if token.ath_market_cap else 0,
            'liquidity_ratio': token.liquidity / token.market_cap if token.market_cap else 0
        }

    def _analyze_price_volume(self, token: TokenMetrics, updates: List[TokenUpdate]) -> Dict:
        """Analizuoja kainos ir volume metrikas"""
        return {
            'price_momentum': self._calculate_momentum(updates),
            'volume_trend': self._analyze_volume_trend(updates),
            'price_volatility': self._calculate_volatility(updates),
            'volume_consistency': self._analyze_volume_consistency(updates),
            'mcap_to_volume_ratio': token.market_cap / max(token.volume_24h, 1)
        }

    def _analyze_holders(self, token: TokenMetrics, updates: List[TokenUpdate]) -> Dict:
        """Analizuoja holder'ių metrikas"""
        return {
            'holder_growth_rate': self._calculate_holder_growth(updates),
            'holder_distribution': self._analyze_holder_distribution(token),
            'value_per_holder': token.market_cap / max(token.holders_count, 1),
            'holder_retention': self._calculate_holder_retention(updates),
            'top_holder_risk': self._analyze_top_holder_risk(token)
        }

    def _analyze_snipers(self, token: TokenMetrics) -> Dict:
        """Analizuoja sniperių metrikas"""
        try:
            if token is None or token.sniper_wallets is None:
                token.sniper_wallets = []
                logger.warning(f"[2025-02-01 21:32:03] sniper_wallets is None for {token.address}")

            sniper_types = self._categorize_snipers(token.sniper_wallets)
            wallet_count = len(token.sniper_wallets) if token.sniper_wallets else 1
            
            return {
                'sniper_impact': token.sniper_percentage / 100,
                'whale_dominance': sniper_types['whale_count'] / max(wallet_count, 1),
                'fish_ratio': sniper_types['fish_count'] / max(wallet_count, 1),
                'sniper_diversity': self._calculate_sniper_diversity(token.sniper_wallets),
                'sniper_behavior_pattern': self._analyze_sniper_patterns(token.sniper_wallets)
            }

        except Exception as e:
            logger.error(f"[2025-02-01 21:32:03] Error in _analyze_snipers for {token.address}: {str(e)}")
            return {
                'sniper_impact': 0.0,
                'whale_dominance': 0.0,
                'fish_ratio': 0.0,
                'sniper_diversity': 0.0,
                'sniper_behavior_pattern': 0.0
            }

    def _analyze_dev_metrics(self, token: TokenMetrics) -> Dict:
        """Analizuoja dev/owner metrikas"""
        return {
            'dev_commitment': self._calculate_dev_commitment(token),
            'owner_risk': self._assess_owner_risk(token),
            'dev_sol_strength': self._normalize_sol_balance(token.dev_sol_balance),
            'dev_token_risk': token.dev_token_percentage / 100,
            'ownership_score': self._calculate_ownership_score(token)
        }

    def _analyze_security(self, token: TokenMetrics) -> Dict:
        """Analizuoja saugumo metrikas"""
        return {
            'contract_security': self._assess_contract_security(token),
            'lp_security': token.lp_burnt_percentage / 100,
            'mint_risk': 1 if token.mint_enabled else 0,
            'freeze_risk': 1 if token.freeze_enabled else 0,
            'overall_security_score': self._calculate_security_score(token)
        }

    def _analyze_time_series(self, updates: List[TokenUpdate]) -> Dict:
        """Analizuoja laiko serijos duomenis"""
        return {
            'price_trend': self._calculate_price_trend(updates),
            'volume_pattern': self._identify_volume_pattern(updates),
            'holder_trend': self._analyze_holder_trend(updates),
            'growth_stability': self._calculate_growth_stability(updates),
            'momentum_indicators': self._calculate_momentum_indicators(updates)
        }

    def _analyze_wallets(self, wallets: List[Dict]) -> Dict:
        """Analizuoja wallet'ų elgseną"""
        return {
            'wallet_diversity': self._calculate_wallet_diversity(wallets),
            'interaction_patterns': self._analyze_wallet_interactions(wallets),
            'whale_behavior': self._analyze_whale_behavior(wallets),
            'wallet_age_distribution': self._analyze_wallet_ages(wallets),
            'wallet_risk_score': self._calculate_wallet_risk(wallets)
        }

    def _calculate_risk_metrics(self, token: TokenMetrics) -> Dict:
        """Apskaičiuoja rizikos metrikus"""
        return {
            'overall_risk': self._calculate_overall_risk(token),
            'pump_dump_risk': self._assess_pump_dump_risk(token),
            'security_risk': self._assess_security_risk(token),
            'holder_risk': self._assess_holder_risk(token),
            'dev_risk': self._assess_dev_risk(token)
        }
    def _convert_age_to_hours(self, age: str) -> float:
        """Konvertuoja amžių į valandas"""
        try:
            number = int(''.join(filter(str.isdigit, age)))
            if 'm' in age:
                return number / 60  # minutės į valandas
            elif 'h' in age:
                return number  # jau valandos
            elif 'd' in age:
                return number * 24  # dienos į valandas
            return 0
        except:
            return 0

    def _calculate_momentum(self, updates: List[TokenUpdate]) -> float:
        """Skaičiuoja kainos momentum"""
        if not updates:
            return 0.0
        try:
            # Imame paskutines 5 atnaujinimus
            recent = updates[-5:]
            price_changes = [u.price_change_1h for u in recent]
            return sum(price_changes) / len(price_changes)
        except:
            return 0.0

    def _analyze_volume_trend(self, updates: List[TokenUpdate]) -> float:
        """Analizuoja volume trendą"""
        if not updates:
            return 0.0
        try:
            volumes = [u.volume_1h for u in updates]
            if len(volumes) < 2:
                return 0.0
            # Skaičiuojame volume pokytį
            return (volumes[-1] - volumes[0]) / volumes[0] if volumes[0] > 0 else 0.0
        except:
            return 0.0

    def _calculate_volatility(self, updates: List[TokenUpdate]) -> float:
        """Skaičiuoja kainos volatility"""
        if not updates:
            return 0.0
        try:
            price_changes = [abs(u.price_change_1h) for u in updates]
            return np.std(price_changes) if price_changes else 0.0
        except:
            return 0.0

    def _analyze_volume_consistency(self, updates: List[TokenUpdate]) -> float:
        """Analizuoja volume pastovumą"""
        if not updates:
            return 0.0
        try:
            volumes = [u.volume_1h for u in updates]
            avg_volume = np.mean(volumes)
            std_volume = np.std(volumes)
            return std_volume / avg_volume if avg_volume > 0 else 0.0
        except:
            return 0.0

    def _calculate_holder_growth(self, updates: List[TokenUpdate]) -> float:
        """Skaičiuoja holder'ių augimą"""
        if not updates:
            return 0.0
        try:
            holders = [u.holders_count for u in updates]
            if len(holders) < 2:
                return 0.0
            return (holders[-1] - holders[0]) / max(holders[0], 1)
        except:
            return 0.0

    def _analyze_holder_distribution(self, token: TokenMetrics) -> float:
        """Analizuoja holder'ių pasiskirstymą"""
        try:
            return 1.0 - (token.top_holder_percentage / 100.0)  # Kuo mažesnė koncentracija, tuo geriau
        except:
            return 0.0

    def _calculate_holder_retention(self, updates: List[TokenUpdate]) -> float:
        """Skaičiuoja holder'ių išlaikymą"""
        if not updates:
            return 0.0
        try:
            holder_counts = [u.holders_count for u in updates]
            drops = sum(1 for i in range(1, len(holder_counts)) if holder_counts[i] < holder_counts[i-1])
            return 1.0 - (drops / max(len(updates)-1, 1))
        except:
            return 0.0

    def _categorize_snipers(self, wallets: List[Dict]) -> Dict:
        """Kategorizuoja sniper'ius"""
        result = {'whale_count': 0, 'fish_count': 0}
        if not wallets:
            return result
        try:
            for wallet in wallets:
                if wallet['type'] in ['🐳']:  # Whale emoji
                    result['whale_count'] += 1
                elif wallet['type'] in ['🐟', '🍤']:  # Fish emoji
                    result['fish_count'] += 1
            return result
        except:
            return result

    def _calculate_sniper_diversity(self, wallets: List[Dict]) -> float:
        """Skaičiuoja sniper'ių įvairovę"""
        if not wallets:
            return 0.0
        try:
            types = [w['type'] for w in wallets]
            unique_types = len(set(types))
            return unique_types / len(wallets)
        except:
            return 0.0

    def _analyze_sniper_patterns(self, wallets: List[Dict]) -> float:
        """Analizuoja sniper'ių elgsenos šablonus"""
        if not wallets:
            return 0.0
        try:
            # Skaičiuojame whales/fish santykį
            categories = self._categorize_snipers(wallets)
            total = categories['whale_count'] + categories['fish_count']
            if total == 0:
                return 0.0
            return categories['fish_count'] / total  # Didesnis fish ratio = geriau
        except:
            return 0.0

    def _calculate_dev_commitment(self, token: TokenMetrics) -> float:
        """Vertina dev commitment"""
        try:
            # Vertiname pagal SOL balansą ir token %
            sol_score = min(token.dev_sol_balance / 100, 1.0)  # Normalizuojame iki 100 SOL
            token_score = token.dev_token_percentage / 100
            return (sol_score + token_score) / 2
        except:
            return 0.0

    def _assess_owner_risk(self, token: TokenMetrics) -> float:
        """Vertina owner riziką"""
        try:
            if token.owner_renounced:
                return 0.0  # Mažiausia rizika
            return token.dev_token_percentage / 100  # Rizika proporcinga dev token %
        except:
            return 1.0

    def _normalize_sol_balance(self, balance: float) -> float:
        """Normalizuoja SOL balansą"""
        try:
            return min(balance / 100, 1.0)  # Normalizuojame iki 100 SOL
        except:
            return 0.0

    def _calculate_ownership_score(self, token: TokenMetrics) -> float:
        """Skaičiuoja ownership score"""
        try:
            # Vertiname pagal kelis faktorius
            renounced_score = 1.0 if token.owner_renounced else 0.0
            dev_token_score = 1.0 - (token.dev_token_percentage / 100)
            return (renounced_score + dev_token_score) / 2
        except:
            return 0.0

    def _assess_contract_security(self, token: TokenMetrics) -> float:
        """Vertina kontrakto saugumą"""
        try:
            # Skaičiuojame bendrą saugumo score
            mint_score = 0.0 if token.mint_enabled else 1.0
            freeze_score = 0.0 if token.freeze_enabled else 1.0
            lp_score = token.lp_burnt_percentage / 100
            return (mint_score + freeze_score + lp_score) / 3
        except:
            return 0.0

    def _calculate_security_score(self, token: TokenMetrics) -> float:
        """Skaičiuoja bendrą saugumo score"""
        try:
            contract_security = self._assess_contract_security(token)
            ownership_security = self._calculate_ownership_score(token)
            lp_security = token.lp_burnt_percentage / 100
            return (contract_security + ownership_security + lp_security) / 3
        except:
            return 0.0

    def _analyze_social_metrics(self, token: TokenMetrics) -> Dict:
        """Analizuoja socialinius metrikus"""
        try:
            # Skaičiuojame social presence score
            has_twitter = 1.0 if token.twitter_url else 0.0
            has_website = 1.0 if token.website_url else 0.0
            has_telegram = 1.0 if token.telegram_url else 0.0
            
            social_score = (has_twitter + has_website + has_telegram) / 3
            
            return {
                'social_presence': social_score,
                'has_twitter': has_twitter,
                'has_website': has_website,
                'has_telegram': has_telegram,
                'social_risk': 1.0 - social_score
            }
        except:
            return {
                'social_presence': 0.0,
                'has_twitter': 0.0,
                'has_website': 0.0,
                'has_telegram': 0.0,
                'social_risk': 1.0
            }

    def _analyze_wallet_interactions(self, wallets: List[Dict]) -> Dict:
        """Analizuoja wallet'ų tarpusavio sąveikas"""
        try:
            if not wallets:
                return {'interaction_score': 0.0, 'interaction_pattern': 'none'}
                
            # Skaičiuojame wallet tipų pasiskirstymą
            type_counts = {'🐳': 0, '🐟': 0, '🍤': 0, '🌱': 0}
            for wallet in wallets:
                if wallet['type'] in type_counts:
                    type_counts[wallet['type']] += 1
                    
            total = sum(type_counts.values())
            if total == 0:
                return {'interaction_score': 0.0, 'interaction_pattern': 'none'}
                
            # Vertiname sąveikos šabloną
            whale_ratio = type_counts['🐳'] / total if total > 0 else 0
            fish_ratio = (type_counts['🐟'] + type_counts['🍤']) / total if total > 0 else 0
            
            # Nustatome sąveikos tipą
            if whale_ratio > 0.5:
                pattern = 'whale_dominated'
                score = 0.3  # Rizikinga
            elif fish_ratio > 0.7:
                pattern = 'distributed'
                score = 0.8  # Gerai
            else:
                pattern = 'mixed'
                score = 0.5  # Neutralu
                
            return {
                'interaction_score': score,
                'interaction_pattern': pattern,
                'whale_ratio': whale_ratio,
                'fish_ratio': fish_ratio
            }
        except:
            return {
                'interaction_score': 0.0,
                'interaction_pattern': 'error',
                'whale_ratio': 0.0,
                'fish_ratio': 0.0
            }

    def _calculate_price_trend(self, updates: List[TokenUpdate]) -> float:
        """Skaičiuoja kainos trendą"""
        if not updates:
            return 0.0
        try:
            price_changes = [u.price_change_1h for u in updates]
            return sum(price_changes) / len(price_changes)
        except:
            return 0.0

    def _identify_volume_pattern(self, updates: List[TokenUpdate]) -> float:
        """Identifikuoja volume šabloną"""
        if not updates:
            return 0.0
        try:
            volumes = [u.volume_1h for u in updates]
            if len(volumes) < 3:
                return 0.0
            # Analizuojame volume trendą
            increases = sum(1 for i in range(1, len(volumes)) if volumes[i] > volumes[i-1])
            return increases / (len(volumes) - 1)
        except:
            return 0.0

    def _analyze_holder_trend(self, updates: List[TokenUpdate]) -> float:
        """Analizuoja holder'ių trendą"""
        if not updates:
            return 0.0
        try:
            holders = [u.holders_count for u in updates]
            if len(holders) < 2:
                return 0.0
            return (holders[-1] - holders[0]) / max(holders[0], 1)
        except:
            return 0.0

    def _calculate_growth_stability(self, updates: List[TokenUpdate]) -> float:
        """Skaičiuoja augimo stabilumą"""
        if not updates:
            return 0.0
        try:
            changes = [abs(u.price_change_1h) for u in updates]
            return 1.0 - (np.std(changes) / max(np.mean(changes), 0.0001))
        except:
            return 0.0

    def _calculate_wallet_diversity(self, wallets: List[Dict]) -> float:
        """Skaičiuoja wallet'ų įvairovę"""
        try:
            if not wallets:
                return 0.0
                
            # Skaičiuojame kiekvieno tipo wallet'ų skaičių
            type_counts = {'🐳': 0, '🐟': 0, '🍤': 0, '🌱': 0}
            for wallet in wallets:
                if wallet['type'] in type_counts:
                    type_counts[wallet['type']] += 1
                    
            # Skaičiuojame diversity score
            total_wallets = sum(type_counts.values())
            if total_wallets == 0:
                return 0.0
                
            # Shannon Diversity Index
            proportions = [count/total_wallets for count in type_counts.values() if count > 0]
            diversity = -sum(p * math.log(p) for p in proportions)
            
            # Normalizuojame į [0,1] intervalą
            max_diversity = math.log(len(type_counts))  # Maximum possible diversity
            normalized_diversity = diversity / max_diversity if max_diversity > 0 else 0.0
            
            return normalized_diversity
            
        except Exception as e:
            logger.error(f"[2025-02-01 21:26:24] Error calculating wallet diversity: {str(e)}")
            return 0.0

    def _calculate_momentum_indicators(self, updates: List[TokenUpdate]) -> Dict:
        """Skaičiuoja momentum indikatorius"""
        if not updates:
            return {'momentum': 0.0, 'acceleration': 0.0}
        try:
            price_changes = [u.price_change_1h for u in updates]
            momentum = sum(price_changes) / len(price_changes)
            
            # Skaičiuojame acceleration (pokytis momentum'e)
            if len(price_changes) > 1:
                acc = (price_changes[-1] - price_changes[0]) / len(price_changes)
            else:
                acc = 0.0
                
            return {'momentum': momentum, 'acceleration': acc}
        except:
            return {'momentum': 0.0, 'acceleration': 0.0}

    def _analyze_whale_behavior(self, wallets: List[Dict]) -> Dict:
        """Analizuoja banginių elgseną"""
        try:
            whales = [w for w in wallets if w['type'] == '🐳']
            if not whales:
                return {'whale_activity': 0.0, 'risk_level': 'low'}
                
            whale_ratio = len(whales) / len(wallets)
            
            if whale_ratio > 0.5:
                risk = 'high'
            elif whale_ratio > 0.3:
                risk = 'medium'
            else:
                risk = 'low'
                
            return {
                'whale_activity': whale_ratio,
                'risk_level': risk
            }
        except:
            return {'whale_activity': 0.0, 'risk_level': 'error'}

    def _analyze_wallet_ages(self, wallets: List[Dict]) -> Dict:
        """Analizuoja wallet'ų amžių"""
        try:
            if not wallets:
                return {'avg_age': 0.0, 'new_wallet_ratio': 0.0}
                
            # Šiuo atveju neturime wallet age info, tai grąžiname default
            return {
                'avg_age': 0.0,
                'new_wallet_ratio': 0.0
            }
        except:
            return {'avg_age': 0.0, 'new_wallet_ratio': 0.0}

    def _calculate_wallet_risk(self, wallets: List[Dict]) -> float:
        """Skaičiuoja bendrą wallet riziką"""
        try:
            if not wallets:
                return 1.0  # Aukščiausia rizika jei nėra wallet'ų
                
            # Skaičiuojame risk score
            whale_behavior = self._analyze_whale_behavior(wallets)
            interactions = self._analyze_wallet_interactions(wallets)
            
            risk_score = (
                float(whale_behavior['whale_activity']) * 0.4 +
                (1.0 - float(interactions['interaction_score'])) * 0.6
            )
            
            return risk_score
        except:
            return 1.0

    def _analyze_top_holder_risk(self, token: TokenMetrics) -> float:
        """Analizuoja top holder'ių riziką"""
        try:
            # Kuo didesnė top holder koncentracija, tuo didesnė rizika
            return token.top_holder_percentage / 100
        except:
            return 1.0

    def _assess_dev_risk(self, token: TokenMetrics) -> float:
        """Vertina dev riziką"""
        try:
            # Vertiname pagal kelis faktorius
            token_risk = token.dev_token_percentage / 100
            renounced_bonus = 0.0 if token.owner_renounced else 0.3
            sol_balance_factor = 1.0 - self._normalize_sol_balance(token.dev_sol_balance)
            
            return (token_risk + renounced_bonus + sol_balance_factor) / 3
        except:
            return 1.0

    def _calculate_overall_risk(self, token: TokenMetrics) -> float:
        """Skaičiuoja bendrą rizikos įvertinimą"""
        try:
            # Renkame visus rizikos faktorius
            security_risk = self._assess_security_risk(token)
            holder_risk = self._assess_holder_risk(token)
            dev_risk = self._assess_dev_risk(token)
            pump_dump_risk = self._assess_pump_dump_risk(token)
            
            # Skaičiuojame svertinį vidurkį
            weights = {
                'security': 0.3,
                'holder': 0.2,
                'dev': 0.3,
                'pump_dump': 0.2
            }
            
            overall = (
                security_risk * weights['security'] +
                holder_risk * weights['holder'] +
                dev_risk * weights['dev'] +
                pump_dump_risk * weights['pump_dump']
            )
            
            return overall
        except:
            return 1.0

    def _assess_pump_dump_risk(self, token: TokenMetrics) -> float:
        """Vertina pump&dump riziką"""
        try:
            # Vertiname pagal kelis faktorius
            volume_volatility = token.volume_1h / max(token.volume_24h / 24, 0.0001)
            price_volatility = abs(token.price_change_1h)
            holder_concentration = token.top_holder_percentage / 100
            
            # Skaičiuojame risk score
            risk_factors = [
                volume_volatility > 3.0,  # Staigus volume padidėjimas
                price_volatility > 50.0,  # Didelis kainos svyravimas
                holder_concentration > 0.5  # Didelė holder koncentracija
            ]
            
            return sum(risk_factors) / len(risk_factors)
        except:
            return 1.0

    def _assess_security_risk(self, token: TokenMetrics) -> float:
        """Vertina saugumo riziką"""
        try:
            current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"\n{'='*50}")
            logger.info(f"🔒 SECURITY ASSESSMENT FOR TOKEN:")
            logger.info(f"📝 Name: {token.name} (${token.symbol})")
            logger.info(f"📍 Address: {token.address}")
            logger.info(f"⏰ Time: {current_time}")
            logger.info(f"{'='*50}\n")

            # 1. LP užrakintas >80%
            logger.info("1️⃣ Checking LP Lock Status:")
            if token.lp_burnt_percentage < 80:
                logger.warning(f"❌ FAILED: LP locked only {token.lp_burnt_percentage}% (required >80%)")
                logger.info(f"{'='*50}")
                return 1.0
            logger.info(f"✅ PASSED: LP {token.lp_burnt_percentage}% locked\n")

            # 2. Owner teisės renounced
            logger.info("2️⃣ Checking Owner Rights:")
            if not token.owner_renounced:
                logger.warning("❌ FAILED: Owner rights not renounced")
                logger.info(f"{'='*50}")
                return 1.0
            logger.info("✅ PASSED: Owner rights renounced\n")

            # 3. >1000 holder'ių
            logger.info("3️⃣ Checking Holders Count:")
            if token.holders_count < 500:
                logger.warning(f"❌ FAILED: Only {token.holders_count:,} holders (required >1,000)")
                logger.info(f"{'='*50}")
                return 1.0
            logger.info(f"✅ PASSED: {token.holders_count:,} holders\n")

            # 4. Top holder'iai turi <20%
            logger.info("4️⃣ Checking Top Holders Concentration:")
            if token.top_holder_percentage > 20:
                logger.warning(f"❌ FAILED: Top holders own {token.top_holder_percentage}% (required <20%)")
                logger.info(f"{'='*50}")
                return 1.0
            logger.info(f"✅ PASSED: Top holders own {token.top_holder_percentage}%\n")

            # 5. Stabilūs volume/kainų pokyčiai
            logger.info("5️⃣ Checking Price/Volume Stability:")
            volume_volatility = token.volume_1h / max(token.volume_24h / 24, 0.0001)
            if volume_volatility > 3.0 or abs(token.price_change_1h) > 50.0:
                logger.warning(f"❌ FAILED: High volatility detected")
                logger.warning(f"   • Price Change 1h: {token.price_change_1h}%")
                logger.warning(f"   • Volume 1h: ${token.volume_1h:,.2f}")
                logger.warning(f"   • Volume 24h: ${token.volume_24h:,.2f}")
                logger.info(f"{'='*50}")
                return 1.0
            logger.info(f"✅ PASSED: Stable price and volume movements\n")

            # 6. Dev'ai turi <5% tokenų
            logger.info("6️⃣ Checking Dev Holdings:")
            if token.dev_token_percentage > 5:
                logger.warning(f"❌ FAILED: Devs own {token.dev_token_percentage}% (required <5%)")
                logger.info(f"{'='*50}")
                return 1.0
            logger.info(f"✅ PASSED: Devs own {token.dev_token_percentage}%\n")

            # 7. Nėra mint/freeze teisių
            logger.info("7️⃣ Checking Mint/Freeze Rights:")
            if token.mint_enabled or token.freeze_enabled:
                logger.warning("❌ FAILED: Has mint or freeze rights")
                logger.warning(f"   • Mint Enabled: {token.mint_enabled}")
                logger.warning(f"   • Freeze Enabled: {token.freeze_enabled}")
                logger.info(f"{'='*50}")
                return 1.0
            logger.info("✅ PASSED: No mint or freeze rights\n")

            # Skaičiuojame bendrą security risk
            contract_security = self._assess_contract_security(token)
            ownership_security = self._calculate_ownership_score(token)
            lp_security = token.lp_burnt_percentage / 100
            security_risk = 1.0 - ((contract_security + ownership_security + lp_security) / 3)

            # Final Summary
            logger.info(f"\n{'='*50}")
            logger.info("🎉 TOKEN PASSED ALL SECURITY CHECKS!")
            logger.info("\n📊 FINAL SECURITY METRICS:")
            logger.info(f"• Contract Security Score: {contract_security:.2f}/1.00")
            logger.info(f"• Ownership Security Score: {ownership_security:.2f}/1.00")
            logger.info(f"• LP Security Score: {lp_security:.2f}/1.00")
            logger.info(f"• Overall Security Risk: {security_risk:.2f}/1.00")
            logger.info(f"{'='*50}\n")

            return min(security_risk, 1.0)

        except Exception as e:
            logger.error(f"\n{'='*50}")
            logger.error(f"❌ ERROR in security assessment for {token.address}")
            logger.error(f"Error details: {str(e)}")
            logger.error(f"{'='*50}\n")
            return 1.0

    
    def _assess_holder_risk(self, token: TokenMetrics) -> float:
        """Vertina holder'ių riziką"""
        try:
            # Vertiname pagal kelis faktorius
            concentration_risk = token.top_holder_percentage / 100
            holder_count_factor = 1.0 - min(token.holders_count / 1000, 1.0)  # Normalizuojame iki 1000 holders
            sniper_risk = token.sniper_percentage / 100
            
            # Skaičiuojame svertinį vidurkį
            weights = {'concentration': 0.4, 'count': 0.3, 'sniper': 0.3}
            
            risk_score = (
                concentration_risk * weights['concentration'] +
                holder_count_factor * weights['count'] +
                sniper_risk * weights['sniper']
            )
            
            return min(risk_score, 1.0)
        except:
            return 1.0
                    

class GemFinder:
    def __init__(self):
        self.logger = logger
        self.telegram = None
        self.scanner_client = None
        self.db_manager = None
        self.token_analyzer = None
        self.ml_analyzer = None
        self.token_handler = None
        self.processed_messages = set()

    async def initialize(self):
        """Inicializuoja visus komponentus"""
        try:
            # Sukuriame telegram klientus ir iš karto juos startuojame
            logger.info(f"[2025-02-03 17:21:25] Initializing Telegram clients...")
            
            self.telegram = TelegramClient('gem_finder_session', 
                                         Config.TELEGRAM_API_ID, 
                                         Config.TELEGRAM_API_HASH)
            
            self.scanner_client = TelegramClient('scanner_session',
                                               Config.TELEGRAM_API_ID,
                                               Config.TELEGRAM_API_HASH)
            
            # Sukuriame alert klientą iš karto
            self.alert_client = TelegramClient('gem_alert_session',
                                             Config.TELEGRAM_API_ID,
                                             Config.TELEGRAM_API_HASH)
            
            # Startuojame visus klientus
            await self.telegram.start()
            await self.scanner_client.start()
            await self.alert_client.start()
            
            logger.info(f"[2025-02-03 17:21:25] All Telegram clients initialized")

            # Pirma inicializuojame DB
            self.db_manager = DatabaseManager()
            await self.db_manager.setup_database()
            logger.info(f"[2025-02-03 17:21:25] Database initialized")
            
            # Tada kuriame kitus komponentus
            self.token_analyzer = TokenAnalyzer(self.db_manager, None)
            self.ml_analyzer = MLAnalyzer(self.db_manager, self.token_analyzer)
            self.token_analyzer.ml = self.ml_analyzer
            self.token_handler = TokenHandler(self.db_manager, self.ml_analyzer)

                        
            # Perduodame jau inicializuotą alert klientą
            self.token_handler.telegram_client = self.alert_client
            
            logger.info(f"[2025-02-03 17:21:25] GemFinder initialized")

        except Exception as e:
            logger.error(f"[2025-02-03 17:21:25] Error in initialization: {e}")
            raise

    async def start(self):
        """Paleidžia GemFinder"""
        try:
            # Pirma inicializuojame visus komponentus
            await self.initialize()
            
            logger.info(f"[2025-02-03 17:21:25] GemFinder started")
            
            # Pradedame periodinį neaktyvių tokenų tikrinimą
            asyncio.create_task(self._run_periodic_checks())
            
            # Patikriname duomenų bazės būseną
            await self.db_manager.check_database()

            #await self.db_manager.check_update_numbers()             
            
            
            # Registruojame message handler'į
            @self.telegram.on(events.NewMessage(chats=Config.TELEGRAM_SOURCE_CHATS))
            async def message_handler(event):
                await self._handle_message(event)
                
            # Laukiame pranešimų
            await self.telegram.run_until_disconnected()
            
        except Exception as e:
            logger.error(f"[2025-02-03 17:21:25] Error starting GemFinder: {e}")
            raise

    async def _run_periodic_checks(self):
        """Atnaujina DB ir ML modelį periodiškai"""
        while True:
            try:
                logger.info(f"[2025-02-05 20:37:57] Starting database and ML update...")
                
                # 1. Patikriname ir pažymime neaktyvius tokenus
                await self.token_handler.check_inactive_tokens()
                
                # 2. Gauname visus tokenus iš DB
                active_tokens = await self.db_manager.get_active_tokens()
                successful_tokens = await self.db_manager.get_all_gems()
                failed_tokens = await self.db_manager.get_failed_tokens()
                
                # 3. Patikriname ar aktyvūs tokenai tapo gems
                for token in active_tokens:
                    try:
                        if not await self.db_manager.is_gem(token['address']):
                            # Gauname tik paskutinį atnaujinimą iš DB
                            latest_update = await self.db_manager.get_latest_token_update(token['address'])
                            initial_data = await self.db_manager.get_initial_state(token['address'])
                            
                            if latest_update and initial_data:
                                multiplier = latest_update['market_cap'] / initial_data.market_cap
                                if multiplier >= 10:
                                    await self.db_manager.mark_as_gem(token['address'])
                                    logger.info(f"[2025-02-05 20:37:57] New gem found: {token['address']} ({multiplier:.2f}X)")
                    except Exception as e:
                        logger.error(f"[2025-02-05 20:37:57] Error checking token status: {e}")

                # 4. Periodiškai atnaujiname VISUS ML modelius
                logger.info(f"[2025-02-05 20:37:57] Starting model training for all models...")
                
                # Treniruojame visus modelius (new token ir update modelius)
                await self.ml_analyzer.train_model(0)  # New token modelis
                await self.ml_analyzer.train_model(1)  # Update 1 modelis
                await self.ml_analyzer.train_model(2)  # Update 2 modelis  
                await self.ml_analyzer.train_model(3)  # Update 3 modelis
                
                logger.info(f"[2025-02-05 20:37:57] All models training completed")
                
                # 5. Atnaujiname duomenų bazės būseną
                await self.db_manager.check_database()
                
                # Naudojame RETRAIN_INTERVAL iš Config (valandos į sekundes)
                await asyncio.sleep(Config.RETRAIN_INTERVAL * 3600)
                
            except Exception as e:
                logger.error(f"[2025-02-05 20:37:57] Error in periodic checks: {e}")
                await asyncio.sleep(60)

    async def stop(self):
        """Sustabdo GemFinder"""
        await self.telegram.disconnect()
        await self.scanner_client.disconnect()
        logger.info(f"[2025-01-31 13:08:54] GemFinder stopped")
        
    async def _handle_message(self, event: events.NewMessage.Event):
        try:
            message = event.message.text
            message_id = event.message.id
            
            if message_id in self.processed_messages:
                return
                
            logger.info(f"[2025-01-31 13:08:54] Processing message ID: {message_id}")
            
            # Patikriname ar tai naujas token'as
            is_new_token = bool("🔥" in message and "New Trending" in message)
            
            token_addresses = self._extract_token_addresses(message)
            if not token_addresses:
                return
                
            token_address = token_addresses[0]
            current_data = await self._collect_token_data(token_address)
            if not current_data:
                return
                
            if "New" in message or is_new_token:
                await self.token_handler.handle_new_token(current_data)
            else:
                await self.token_handler.handle_token_update(token_address, current_data, is_new_token=is_new_token)
            
            self.processed_messages.add(message_id)

            # Patikriname ar jau turime security patikrinimą DB
            security_check = await self.db.get_security_check(token_data.address)

            if not security_check:
                # Atliekame security patikrinimą
                security_risk = self.token_analyzer._assess_security_risk(token_data)
                
                # Išsaugome rezultatą į DB
                await self.db.save_security_check(token_data.address, security_risk)
            
        except Exception as e:
            logger.error(f"[2025-01-31 13:08:54] Error handling message: {e}")

    async def _handle_new_token(self, message: str):
        """Apdoroja naują token'ą"""
        try:
            # Ištraukiame token adresą
            token_addresses = self._extract_token_addresses(message)
            if not token_addresses:
                return

            token_address = token_addresses[0]
            logger.info(f"[2025-02-03 14:25:39] Processing new token: {token_address}")

            # Renkame token info
            token_data = await self._collect_token_data(token_address)
            if not token_data:
                return

            
            # Apdorojame naują tokeną per TokenHandler
            initial_prediction = await self.token_handler.handle_new_token(token_data)
            
            
            
            logger.info(f"[2025-02-03 14:25:39] Token {token_address} processed with initial prediction: {initial_prediction:.2f}")

        except Exception as e:
            logger.error(f"[2025-02-03 14:25:39] Error handling new token: {e}")

    async def _handle_token_update(self, message: str):
        try:
            token_addresses = self._extract_token_addresses(message)
            if not token_addresses:
                return

            token_address = token_addresses[0]
            current_data = await self._collect_token_data(token_address)
            if not current_data:
                return

            # Perduodame update'ą TokenHandler'iui
            await self.token_handler.handle_token_update(token_address, current_data)
            logger.info(f"[{datetime.now(timezone.utc)}] Token update handled through TokenHandler: {token_address}")
                
        except Exception as e:
            logger.error(f"[{datetime.now(timezone.utc)}] Error handling token update: {e}")

    def _extract_token_addresses(self, message: str) -> List[str]:
        """Ištraukia token adresus iš žinutės"""
        matches = []
        
        try:
            # Ieškome token adreso URL'uose
            if "from" in message:  # Update žinutė
                # Ieškome soul_scanner_bot URL
                scanner_matches = re.findall(r'soul_scanner_bot/chart\?startapp=([A-Za-z0-9]{32,44})', message)
                if scanner_matches:
                    matches.extend(scanner_matches)
                    
            elif "New" in message:  # Nauja žinutė
                # Ieškome soul_sniper_bot ir soul_scanner_bot URL
                patterns = [
                    r'soul_sniper_bot\?start=\d+_([A-Za-z0-9]{32,44})',
                    r'soul_scanner_bot/chart\?startapp=([A-Za-z0-9]{32,44})'
                ]
                
                for pattern in patterns:
                    url_matches = re.findall(pattern, message)
                    if url_matches:
                        matches.extend(url_matches)
            
            # Pašaliname dublikatus ir filtruojame
            unique_matches = list(set(matches))
            valid_matches = [addr for addr in unique_matches if len(addr) >= 32 and len(addr) <= 44]
            
            if valid_matches:
                logger.info(f"[2025-01-31 13:14:41] Found token address: {valid_matches[0]}")
            
            return valid_matches
            
        except Exception as e:
            logger.error(f"[2025-01-31 13:14:41] Error extracting token address: {e}")
            return []

    async def _collect_token_data(self, token_address: str) -> Optional[TokenMetrics]:
        """Renka informaciją apie token'ą iš visų šaltinių"""
        
        logger.info(f"[2025-01-31 12:39:29] Collecting data for {token_address}")
        
        try:
            # Siunčiame token'ą į scanner grupę
            original_message = await self.scanner_client.send_message(
                Config.SCANNER_GROUP,
                token_address
            )
            logger.info(f"[2025-01-31 12:39:29] Sent token to scanner group: {token_address}")

            # Laukiame atsakymų iš botų
            timeout = 30
            start_time = time.time()
            last_check_time = 0
            soul_data = None
            all_responses = []  # Saugosime visus atsakymus
            
            while time.time() - start_time < timeout:
                if time.time() - last_check_time >= 2:
                    last_check_time = time.time()
                    
                    async for message in self.scanner_client.iter_messages(
                        Config.SCANNER_GROUP,
                        limit=20,
                        min_id=original_message.id
                    ):
                        if message.sender_id == Config.SOUL_SCANNER_BOT:
                            message_text = message.text
                            
                            # Patikrinimas ar žinutėje yra mūsų ieškomas adresas
                            if token_address not in message_text:
                                continue
                            
                            # Pridedame į atsakymų sąrašą
                            all_responses.append(message_text)
                    
                    # Jei turime atsakymų, naudojame paskutinį (naujausią)
                    if all_responses:
                        latest_message = all_responses[-1]
                        logger.info(f"[2025-01-31 12:39:29] Soul Scanner response received (Response {len(all_responses)} of {len(all_responses)})")
                        soul_data = self.parse_soul_scanner_response(latest_message)
                        
                        if soul_data:
                            logger.info(f"[2025-01-31 12:39:29] Soul Scanner data parsed successfully")
                            for key, value in sorted(soul_data.items()):
                                logger.info(f"[2025-01-31 12:39:29] {key}: {value}")
                            
                            # Konstruojame TokenMetrics objektą
                            token_data = TokenMetrics(
                                address=token_address,
                                name=soul_data.get('name', 'Unknown').replace('**', '').replace('\u200e', ''),
                                symbol=soul_data.get('symbol', 'Unknown'),
                                age=soul_data.get('age', '0d'),
                                total_scans=soul_data.get('total_scans', 0),
                                market_cap=soul_data.get('market_cap', 0.0),
                                liquidity=soul_data.get('liquidity', {}).get('usd', 0.0),
                                volume_1h=soul_data.get('volume', {}).get('1h', 0.0),
                                volume_24h=soul_data.get('volume', {}).get('24h', 0.0),
                                price_change_1h=soul_data.get('price_change', {}).get('1h', 0.0),
                                price_change_24h=soul_data.get('price_change', {}).get('24h', 0.0),
                                mint_enabled=1 if soul_data.get('mint_status', False) else 0,     # Pakeista į 1/0
                                freeze_enabled=1 if soul_data.get('freeze_status', False) else 0,  # 
                                lp_burnt_percentage=100 if soul_data.get('lp_status', False) else 0,
                                holders_count=soul_data.get('holders', {}).get('count', 0),
                                top_holder_percentage=soul_data.get('holders', {}).get('top_percentage', 0.0),
                                sniper_wallets=soul_data.get('sniper_wallets', []),
                                sniper_count=soul_data.get('snipers', {}).get('count', 0),
                                sniper_percentage=soul_data.get('snipers', {}).get('percentage', 0.0),
                                first_20_fresh=soul_data.get('first_20', 0),
                                
                                ath_market_cap=soul_data.get('ath_market_cap', 0.0),
                                ath_multiplier=1.0,
                                owner_renounced=1 if soul_data.get('dev', {}).get('token_percentage', 0.0) == 0 else 0,
                                telegram_url=soul_data.get('social_links', {}).get('TG'),
                                twitter_url=soul_data.get('social_links', {}).get('X'),
                                website_url=soul_data.get('social_links', {}).get('WEB'),
                                
                                dev_sol_balance=soul_data.get('dev', {}).get('sol_balance', 0.0),
                                dev_token_percentage=soul_data.get('dev', {}).get('token_percentage', 0.0)
                            )
                            
                            if token_data.market_cap > 0 and token_data.ath_market_cap > 0:
                                token_data.ath_multiplier = token_data.ath_market_cap / token_data.market_cap
                            
                            logger.info(f"[2025-01-31 12:39:29] Successfully created TokenMetrics object")
                            
                            return token_data
                    
                    await asyncio.sleep(2)
            
            logger.error(f"[2025-01-31 12:39:29] Failed to get all responses")
            return None
            
        except Exception as e:
            logger.error(f"[2025-01-31 12:39:29] Error collecting token data: {e}")
            logger.error(f"Exception traceback: {e.__traceback__.tb_lineno}")
            return None

    def clean_line(self, text: str) -> str:
        """
        Išvalo tekstą nuo nereikalingų simbolių, bet palieka svarbius emoji
        """
        
        
        important_emoji = ['💠', '🤍', '✅', '❌', '🔻', '🐟', '🍤', '🐳', '🌱', '🕒', '📈', '⚡️', '👥', '🔗', '🦅', '🔫', '⚠️', '🛠', '🔝', '🔥', '💧']
        
        # Pašalinam Markdown ir URL
        cleaned = re.sub(r'\*\*|\[.*?\]|\(https?://[^)]+\)', '', text)
    
        # Pašalinam visus specialius simbolius, išskyrus svarbius emoji
        result = ''
        i = 0
        while i < len(cleaned):
            if any(cleaned.startswith(emoji, i) for emoji in important_emoji):
                # Jei randame svarbų emoji, jį paliekame
                emoji_found = next(emoji for emoji in important_emoji if cleaned.startswith(emoji, i))
                result += emoji_found
                i += len(emoji_found)
            else:
                # Kitaip tikriname ar tai normalus simbolis
                if cleaned[i].isalnum() or cleaned[i] in ' .:$%|-()':
                    result += cleaned[i]
                i += 1
        
        return result.strip()

    def parse_soul_scanner_response(self, text: str) -> Dict:
        """Parse Soul Scanner message"""
        try:
            data = {}
            lines = text.split('\n')

            
            
            for line in lines:
                try:
                    if not line.strip():
                        continue
                        
                    clean_line = self.clean_line(line)
                    
                    # Basic info 
                    if '💠' in line or '🔥' in line:
                        parts = line.split('$')
                        data['name'] = parts[0].replace('💠', '').replace('🔥', '').replace('•', '').replace('**', '').strip()
                        data['symbol'] = parts[1].replace('**', '').strip()
                            
                    # Contract Address
                    elif len(line.strip()) > 30 and not any(x in line for x in ['https://', '🌊', '🔫', '📈', '🔗', '•', '┗', '┣']):
                        data['contract_address'] = line.strip().replace('`', '')
                    
                    
                    elif 'Age:' in line:
                        try:
                            number = ''.join(c for c in line if c.isdigit())
                            if number:
                                if 'm' in line:  # Jei yra "m"
                                    data['age'] = f"{number}m"  # Pridedame "m"
                                elif 'd' in line:  # Jei "d"
                                    data['age'] = f"{number}d"  # Pridedame "d"
                                elif 'h' in line:  # Jei "h"
                                    data['age'] = f"{number}h"  # Pridedame "h"
                        except Exception as e:
                            print(f"AGE ERROR: {str(e)}")
                        
                    # Market Cap and ATH
                    elif 'MC:' in line:
                        # Market Cap gali būti K arba M
                        mc_k = re.search(r'\$(\d+\.?\d*)K', clean_line)  # Ieškome K
                        mc_m = re.search(r'\$(\d+\.?\d*)M', clean_line)  # Ieškome M
                        
                        if mc_m:  # Jei M (milijonai)
                            data['market_cap'] = float(mc_m.group(1)) * 1000000
                        elif mc_k:  # Jei K (tūkstančiai)
                            data['market_cap'] = float(mc_k.group(1)) * 1000
                                
                        # ATH ieškojimas (po 🔝)
                        ath_m = re.search(r'🔝 \$(\d+\.?\d*)M', clean_line)  # Pirma tikrinam M
                        ath_k = re.search(r'🔝 \$(\d+\.?\d*)K', clean_line)  # Tada K
                        
                        if ath_m:  # Jei M (milijonai)
                            data['ath_market_cap'] = float(ath_m.group(1)) * 1000000
                        elif ath_k:  # Jei K (tūkstančiai)
                            data['ath_market_cap'] = float(ath_k.group(1)) * 1000
                    
                    # Liquidity
                    elif 'Liq:' in line or 'vLiq:' in line:  # Pridėtas vLiq patikrinimas
                        try:
                            if 'vLiq:' in line:
                                liq = re.search(r'\$(\d+\.?\d*)K\s*\((\d+\.?\d*)\s*SOL\)', clean_line)
                            else:
                                liq = re.search(r'\$(\d+\.?\d*)K\s*\((\d+)\s*SOL\)', clean_line)
                                
                            if liq:
                                data['liquidity'] = {
                                    'usd': float(liq.group(1)) * 1000,
                                    'sol': float(liq.group(2))
                                }
                        except Exception as e:
                            print(f"Liquidity error: {str(e)}")
                    
                    # Volume
                    elif 'Vol:' in line:
                        
                        clean_line = self.clean_line(line)
                        
                        try:
                            data['volume'] = {'1h': 0.0, '24h': 0.0}
                            
                            parts = clean_line.split('|')
                            
                            # 1h volume
                            vol_1h = re.search(r'\$(\d+\.?\d*)(K|M)?', parts[0])
                            if vol_1h:
                                value = float(vol_1h.group(1))
                                if vol_1h.group(2) == 'K':
                                    value *= 1000
                                elif vol_1h.group(2) == 'M':
                                    value *= 1000000
                                data['volume']['1h'] = value
                                
                            
                            # 24h volume
                            if len(parts) > 1:
                                vol_24h = re.search(r'\$(\d+\.?\d*)(K|M)?', parts[1])
                                if vol_24h:
                                    value = float(vol_24h.group(1))
                                    if vol_24h.group(2) == 'K':
                                        value *= 1000
                                    elif vol_24h.group(2) == 'M':
                                        value *= 1000000
                                    data['volume']['24h'] = value
                                    
                            
                            
                                
                        except Exception as e:
                            print(f"Volume error: {str(e)}")

                    # Price Changes
                    elif 'Price:' in line:
                        
                        clean_line = self.clean_line(line)
                        
                        try:
                            parts = line.split('|')
                            data['price_change'] = {'1h': 0.0, '24h': 0.0}
                            
                            # 1h price
                            if '🔻' in parts[0]:
                                multiplier = -1
                            else:
                                multiplier = 1
                                
                            price_1h = re.search(r'[+]?([\d.]+)(K)?%', parts[0])
                            if price_1h:
                                value = float(price_1h.group(1))
                                if price_1h.group(2) == 'K':
                                    value *= 1000
                                data['price_change']['1h'] = value * multiplier
                                
                                
                            # 24h price
                            if len(parts) > 1:
                                if '🔻' in parts[1]:
                                    multiplier = -1
                                else:
                                    multiplier = 1
                                    
                                price_24h = re.search(r'[+]?([\d.]+)(K)?%', parts[1])
                                if price_24h:
                                    value = float(price_24h.group(1))
                                    if price_24h.group(2) == 'K':
                                        value *= 1000
                                    data['price_change']['24h'] = value * multiplier
                                    
                                    
                            
                            
                        except Exception as e:
                            print(f"Price error: {str(e)}")
                    
                    # Tikriname visą eilutę su Mint ir Freeze
                    elif '➕ Mint' in line and '🧊 Freeze' in line:
                        mint_part = line.split('|')[0]
                        freeze_part = line.split('|')[1]
                        data['mint_status'] = False if '🤍' in mint_part else True
                        data['freeze_status'] = False if '🤍' in freeze_part else True

                    # LP statusas - GRĮŽTAM PRIE TO KAS VEIKĖ
                    elif 'LP' in line and not 'First' in line:
                        data['lp_status'] = True if '🤍' in line else False

                        
                    # DEX Status
                    elif 'Dex' in line:
                        data['dex_status'] = {
                            'paid': '✅' in line,
                            'ads': not '❌' in line
                        }
                    
                    # Scans
                    elif any(emoji in line for emoji in ['⚡', '⚡️']) and 'Scans:' in line:  # Patikriname abu variantus
                        
                        try:
                            # Pašalinam Markdown formatavimą ir ieškome skaičiaus
                            clean_line = re.sub(r'\*\*', '', line)
                            scans_match = re.search(r'Scans:\s*(\d+)', clean_line)
                            if scans_match:
                                scan_count = int(scans_match.group(1))
                                data['total_scans'] = scan_count
                                
                                
                            # Social links jau veikia teisingai, paliekame kaip yra
                            social_links = {}
                            if 'X' in line:
                                x_match = re.search(r'X\]\((https://[^)]+)\)', line)
                                if x_match:
                                    social_links['X'] = x_match.group(1)

                            if 'TG' in line:
                                tg_match = re.search(r'TG\]\((https://[^)]+)\)', line)
                                if tg_match:
                                    social_links['TG'] = tg_match.group(1)
                            
                            if 'WEB' in line:
                                web_match = re.search(r'WEB\]\((https://[^)]+)\)', line)
                                if web_match:
                                    social_links['WEB'] = web_match.group(1)
                            
                            if social_links:
                                data['social_links'] = social_links
                                
                                
                        except Exception as e:
                            print(f"Scans error: {str(e)}")  # Debug printinam klaidas
                    
                    # Holders
                    elif 'Hodls' in line:
                        
                        try:
                            # Ieškome skaičių su kableliais ir procentų
                            holders = re.search(r':\s*([0-9,]+)\s*•\s*Top:\s*([\d.]+)%', line)
                            if holders:
                                # Pašalinam kablelį iš holder count
                                holder_count = int(holders.group(1).replace(',', ''))
                                top_percent = float(holders.group(2))
                                data['holders'] = {
                                    'count': holder_count,
                                    'top_percentage': top_percent
                                }
                                
                        except Exception as e:
                            print(f"Holders error: {str(e)}")
        
                    # Snipers
                    elif '🔫' in line and 'Snipers:' in line:
                        
                        clean_line = re.sub(r'\*\*', '', line)  # Pašalinam Markdown
                        try:
                            # Ieškome tik skaičių ir procento, ignoruojam ⚠️
                            snipers_match = re.search(r'Snipers:\s*(\d+)\s*•\s*([\d.]+)%', clean_line)
                            if snipers_match:
                                data['snipers'] = {
                                    'count': int(snipers_match.group(1)),
                                    'percentage': float(snipers_match.group(2))
                                }
                                
                        except Exception as e:
                            print(f"Snipers error: {str(e)}")
                    
                    # First 20
                    elif 'First 20' in line:
                        fresh = re.search(r':\s*(\d+)\s*Fresh', clean_line)
                        if fresh:
                            data['first_20'] = int(fresh.group(1))
                    
                    # Sniper Wallets
                    elif any(emoji in line for emoji in ['🐟', '🍤', '🐳', '🌱']):
                        if 'sniper_wallets' not in data:
                            data['sniper_wallets'] = []
                        
                        matches = re.finditer(r'(🐟|🍤|🐳|🌱).*?solscan\.io/account/([A-Za-z0-9]+)', line)
                        for match in matches:
                            data['sniper_wallets'].append({
                                'type': match.group(1),
                                'address': match.group(2)
                            })
                    
                    # Dev Info
                    elif '🛠️ Dev' in line:
                        
                        try:
                            if 'dev' not in data:
                                data['dev'] = {
                                    'sol_balance': 0.0,
                                    'token_percentage': 0.0,
                                    'token_symbol': '',
                                    'sniped_percentage': 0.0,
                                    'sold_percentage': 0.0,
                                    'airdrop_percentage': 0.0,
                                    'tokens_made': 0,
                                    'bonds': 0,
                                    'best_mc': 0.0
                                }
                            
                            # Pašalinam Markdown formatavimą ir URL
                            clean_line = re.sub(r'\*\*|\[|\]|\(https?://[^)]+\)', '', line)
                            
                            
                            # Ieškome SOL ir token info
                            dev_match = re.search(r'Dev:?\s*(\d+)\s*SOL\s*\|\s*(\d+)%\s*\$(\w+)', clean_line)
                            if dev_match:
                                data['dev'].update({
                                    'sol_balance': float(dev_match.group(1)),
                                    'token_percentage': float(dev_match.group(2)),
                                    'token_symbol': dev_match.group(3)
                                })
                                
                                
                        except Exception as e:
                            print(f"Dev main info error: {str(e)}")

                    # Sniped ir Sold info
                    elif 'Sniped:' in line:
                        
                        try:
                            if 'dev' not in data:
                                data['dev'] = {}
                            
                            sniped = re.search(r'Sniped:\s*([\d.]+)%', clean_line)
                            if sniped:
                                data['dev']['sniped_percentage'] = float(sniped.group(1))
                                
                            
                            sold = re.search(r'Sold:\s*([\d.]+)%', clean_line)
                            if sold:
                                data['dev']['sold_percentage'] = float(sold.group(1))
                                
                                
                        except Exception as e:
                            print(f"Sniped/Sold info error: {str(e)}")

                    # Airdrop info
                    elif 'Airdrop:' in line:
                        
                        try:
                            if 'dev' not in data:
                                data['dev'] = {}
                            
                            airdrop = re.search(r'Airdrop:\s*(\d+)%', clean_line)
                            if airdrop:
                                data['dev']['airdrop_percentage'] = float(airdrop.group(1))
                                
                                
                        except Exception as e:
                            print(f"Airdrop info error: {str(e)}")

                    # Made, Bond, Best info
                    elif 'Made:' in line:
                        
                        try:
                            if 'dev' not in data:
                                data['dev'] = {}
                                
                            made = re.search(r'Made:\s*(\d+)', line)
                            bond = re.search(r'Bond:\s*(\d+)', line)
                            best = re.search(r'Best:\s*\$(\d+\.?\d*)M', line)
                            
                            if made and bond and best:
                                data['dev'].update({
                                    'tokens_made': int(made.group(1)),
                                    'bonds': int(bond.group(1)),
                                    'best_mc': float(best.group(1)) * 1000000
                                })
                                
                                
                        except Exception as e:
                            print(f"Made/Bond/Best info error: {str(e)}")
        
                except Exception as e:
                    self.logger.warning(f"Error parsing line: {str(e)}")
                    continue
            
            return data

        except Exception as e:
            self.logger.error(f"Error parsing message: {str(e)}")
            return {}

if __name__ == "__main__":
    try:
        gem_finder = GemFinder()
        logger.info(f"[2025-02-01 12:27:36] Starting GemFinder...")
        
        # Pakeičiame get_event_loop() į run()
        asyncio.run(gem_finder.start())
        
    except KeyboardInterrupt:
        logger.info(f"[2025-02-01 12:27:36] Shutting down GemFinder...")
        # Taip pat pakeičiame ir čia
        asyncio.run(gem_finder.stop())
    except Exception as e:
        logger.error(f"[2025-02-01 12:27:36] Fatal error: {str(e)}")
        raise
