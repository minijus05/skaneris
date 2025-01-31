import asyncio
import json
import re
import time
from datetime import datetime, timezone, timedelta
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
import logging
from dataclasses import dataclass
from typing import Optional, Dict, List
from telethon import TelegramClient, events

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
        """Inicializuoja AsyncDatabase su SQLite"""
        self.db_path = Config.DB_PATH
        self.conn = None
        self.setup_done = False

                
    async def connect(self):
        """Prisijungia prie SQLite duomenų bazės"""
        if not self.conn:
            try:
                self.conn = await aiosqlite.connect(self.db_path)
                self.conn.row_factory = aiosqlite.Row
                await self._setup_database()
                logger.info(f"[2025-01-31 13:22:07] Connected to database: {self.db_path}")
            except Exception as e:
                logger.error(f"[2025-01-31 13:22:07] Database connection error: {e}")
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
            
            # Pridedame sniper_wallets stulpelį jei jo nėra
            try:
                await self.db.execute("""
                    ALTER TABLE token_initial_states 
                    ADD COLUMN sniper_wallets JSON
                """)
            except:
                # Jei stulpelis jau egzistuoja, ignoruojame klaidą
                pass
            
            # Token atnaujinimai
            await self.execute("""
                CREATE TABLE IF NOT EXISTS token_updates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT,
                    all_metrics JSON,
                    timestamp TIMESTAMP,
                    current_multiplier REAL,
                    FOREIGN KEY (address) REFERENCES token_initial_states(address)
                )
            """)
            
            # Sėkmingi tokenai (gems)
            await self.execute("""
                CREATE TABLE IF NOT EXISTS successful_tokens (
                    address TEXT PRIMARY KEY,
                    initial_parameters JSON,
                    time_to_10x INTEGER,
                    discovery_timestamp TIMESTAMP,
                    FOREIGN KEY (address) REFERENCES token_initial_states(address)
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
    TELEGRAM_DEST_CHAT1 = '@botubotass'
    
    # Scanner settings
    SCANNER_GROUP = '@skaneriss'
    SOUL_SCANNER_BOT = 6872314605
    
    # ML settings
    MIN_TRAINING_SAMPLES = 10
    RETRAIN_INTERVAL = 24
    
    # Database settings
    DB_PATH = 'gem_finder.db'
    
    # Gem detection settings
    MIN_GEM_PROBABILITY = 0.7
    MIN_MC_FOR_GEM = 50000
    MAX_MC_FOR_GEM = 1000000
    
    # ML modelio parametrai
    ML_SETTINGS = {
        'min_gem_multiplier': 10.0,
        'update_interval': 60,  # sekundės
        'confidence_threshold': 0.7,
        'training_data_limit': 1000  # kiek istorinių gem naudoti apmokymui
    }
    
    # Token stebėjimo parametrai
    MONITORING = {
        'max_tracking_time': 7 * 24 * 60 * 60,  # 7 dienos sekundėmis
        'update_frequency': 60,  # sekundės
        'max_active_tokens': 1000
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
    owner_renounced: int = 0   # Vietoj bool = False
    
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
            json.dumps(self.sniper_wallets) if self.sniper_wallets else None
        )

    
class TokenHandler:
    def __init__(self, db_manager, ml_analyzer):
        self.db = db_manager
        self.ml = ml_analyzer
        
    async def handle_new_token(self, token_data: TokenMetrics):
        """Apdoroja naują token'ą"""
        try:
            # Išsaugome pradinę būseną
            await self.db.save_initial_state(token_data)
            logger.info(f"[2025-01-31 15:00:10] Saved initial state for: {token_data.address}")
            
            # Gauname ML predikcijas
            initial_prediction = await self.ml.predict_potential(token_data)
            logger.info(f"[2025-01-31 15:00:10] Initial ML prediction for {token_data.address}: {initial_prediction:.2f}")
            
            return initial_prediction
            
        except Exception as e:
            logger.error(f"[2025-01-31 15:00:10] Error handling new token: {e}")
            return 0.0

    async def handle_token_update(self, token_address: str, new_data: TokenMetrics):
        """Apdoroja token'o atnaujinimą"""
        try:
            # Gauname pradinę būseną
            initial_data = await self.db.get_initial_state(token_address)
            if not initial_data:
                logger.info(f"[2025-01-31 15:00:10] Token not found in DB, saving as new: {token_address}")
                await self.db.save_initial_state(new_data)
                return

            # Skaičiuojame multiplikatorių
            current_multiplier = new_data.market_cap / initial_data.market_cap
            
            # Išsaugome atnaujinimą
            await self.db.save_token_update(token_address, new_data)
            
            # Tikriname ar tapo gem (MC padidėjo 10x)
            if current_multiplier >= 10 and not await self.db.is_gem(token_address):
                # Pažymime kaip gem
                await self.db.mark_as_gem(token_address, new_data, current_multiplier)
                
                # Atnaujiname ML modelį su nauju gem
                await self.ml.update_model_with_new_gem(initial_data)
                
                logger.info(f"[2025-01-31 15:00:10] Token marked as gem: {token_address} ({current_multiplier:.2f}X)")
                
                # Siunčiame žinutę apie naują gem
                await self._send_gem_alert(token_address, initial_data, new_data, current_multiplier)
            
            # Gauname naujas ML predikcijas
            new_prediction = await self.ml.predict_potential(new_data)
            logger.info(f"[2025-01-31 15:00:10] Updated ML prediction for {token_address}: {new_prediction:.2f}")

        except Exception as e:
            logger.error(f"[2025-01-31 15:00:10] Error handling token update: {e}")
            
    async def _send_gem_alert(self, token_address: str, initial_data: TokenMetrics, 
                            current_data: TokenMetrics, multiplier: float):
        """Siunčia žinutę apie naują gem"""
        try:
            message = (
                f"🚀 NEW GEM CONFIRMED! 🚀\n\n"
                f"Token: {initial_data.name} (${initial_data.symbol})\n"
                f"Address: {token_address}\n\n"
                f"Performance:\n"
                f"Initial MC: ${initial_data.market_cap:,.0f}\n"
                f"Current MC: ${current_data.market_cap:,.0f}\n"
                f"Multiplier: {multiplier:.1f}x\n\n"
                f"Current Stats:\n"
                f"Holders: {current_data.holders_count}\n"
                f"Volume 1h: ${current_data.volume_1h:,.0f}\n"
                f"Liquidity: ${current_data.liquidity:,.0f}\n\n"
                f"Links:\n"
                f"🐦 Twitter: {current_data.twitter_url or 'N/A'}\n"
                f"🌐 Website: {current_data.website_url or 'N/A'}"
            )
            
            if not self.telegram_client:
                self.telegram_client = TelegramClient('gem_alert_session', 
                                                    Config.TELEGRAM_API_ID, 
                                                    Config.TELEGRAM_API_HASH)
                await self.telegram_client.start()
                
            await self.telegram_client.send_message(Config.TELEGRAM_DEST_CHAT1, message)
            logger.info(f"[2025-01-31 15:00:10] Sent gem alert for: {token_address}")
            
        except Exception as e:
            logger.error(f"[2025-01-31 15:00:10] Error sending gem alert: {e}")

class MLAnalyzer:
    def __init__(self, db_manager, token_analyzer=None):
        self.db = db_manager
        self.token_analyzer = token_analyzer
        self.model = None
        self.historical_data = None
        self.telegram_client = None
        self.scaler = StandardScaler()
        
        # Jei token_analyzer neperduotas, sukuriame naują
        if self.token_analyzer is None:
            self.token_analyzer = TokenAnalyzer(db_manager, self)
        
    async def load_historical_data(self):
        """Užkrauna istorinius duomenis iš duomenų bazės"""
        try:
            # Gauname visus gems
            gems = await self.db.get_all_gems()
            if not gems:
                logger.info("[2025-01-31 13:30:42] No historical data found")
                return

            # Gauname jų pradinius duomenis
            historical_data = []
            for gem in gems:
                initial_state = await self.db.get_initial_state(gem['address'])
                if initial_state:
                    historical_data.append(initial_state)

            self.historical_data = historical_data
            logger.info(f"[2025-01-31 13:30:42] Loaded {len(historical_data)} historical records")

            # Apmokome modelį su istoriniais duomenimis
            if len(historical_data) >= Config.MIN_TRAINING_SAMPLES:
                await self.train_model()
                
        except Exception as e:
            logger.error(f"[2025-01-31 13:30:42] Error loading historical data: {e}")
        
    async def train_model(self):
        """Treniruoja modelį naudojant TIK pradinius sėkmingų tokenų duomenis"""
        try:
            successful_tokens = await self.db.get_all_gems()
            training_data = [await self.db.get_initial_state(token['address']) 
                           for token in successful_tokens]
            X = self._convert_to_features(training_data)
            self.model = self._train_new_model(X)
            logger.info(f"[{datetime.now(timezone.utc)}] Model trained with {len(training_data)} samples")
        except Exception as e:
            logger.error(f"[{datetime.now(timezone.utc)}] Error training model: {e}")
        
    def _convert_to_features(self, tokens_data: List[TokenMetrics]) -> np.array:
        """Konvertuoja TokenMetrics į feature array naudojant TokenAnalyzer"""
        try:
            features = []
            for token in tokens_data:
                # Gauname išanalizuotus features per TokenAnalyzer
                analyzed = self.token_analyzer.prepare_features(token, [])  # Tuščias updates list, nes tai pradinis state
                
                # Konstruojame feature vektorių
                feature_vector = [
                    # 1. Basic metrics
                    analyzed['basic_metrics']['age_hours'],
                    analyzed['basic_metrics']['market_cap_normalized'],
                    analyzed['basic_metrics']['liquidity_ratio'],
                    
                    # 2. Price/Volume metrics
                    token.market_cap,  # Raw market cap
                    token.liquidity,   # Raw liquidity
                    token.volume_1h,   # Raw volume 1h
                    token.volume_24h,  # Raw volume 24h
                    token.price_change_1h,
                    token.price_change_24h,
                    
                    # 3. Holder metrics
                    analyzed['holder_metrics']['holder_distribution'],
                    analyzed['holder_metrics']['value_per_holder'],
                    analyzed['holder_metrics']['top_holder_risk'],
                    
                    # 4. Sniper metrics
                    analyzed['sniper_metrics']['sniper_impact'],
                    analyzed['sniper_metrics']['whale_dominance'],
                    analyzed['sniper_metrics']['fish_ratio'],
                    analyzed['sniper_metrics']['sniper_diversity'],
                    
                    # 5. Dev metrics
                    analyzed['dev_metrics']['dev_commitment'],
                    analyzed['dev_metrics']['owner_risk'],
                    analyzed['dev_metrics']['dev_sol_strength'],
                    analyzed['dev_metrics']['dev_token_risk'],
                    analyzed['dev_metrics']['ownership_score'],
                    
                    # 6. Security metrics
                    analyzed['security_metrics']['contract_security'],
                    analyzed['security_metrics']['lp_security'],
                    analyzed['security_metrics']['mint_risk'],
                    analyzed['security_metrics']['freeze_risk'],
                    analyzed['security_metrics']['overall_security_score'],
                    
                    # 7. Social metrics
                    analyzed['social_metrics']['social_presence'],
                    analyzed['social_metrics']['has_twitter'],
                    analyzed['social_metrics']['has_website'],
                    analyzed['social_metrics']['has_telegram'],
                    analyzed['social_metrics']['social_risk'],
                    
                    # 8. Risk metrics
                    analyzed['risk_assessment']['overall_risk'],
                    analyzed['risk_assessment']['pump_dump_risk'],
                    analyzed['risk_assessment']['security_risk'],
                    analyzed['risk_assessment']['holder_risk'],
                    analyzed['risk_assessment']['dev_risk'],
                    
                    # 9. Contract flags
                    float(token.mint_enabled),
                    float(token.freeze_enabled),
                    float(token.owner_renounced)
                ]
                features.append(feature_vector)
            
            # Konvertuojame į numpy array
            features_array = np.array(features)
            
            # Normalizuojame features
            return self.scaler.fit_transform(features_array)
            
        except Exception as e:
            logger.error(f"[{datetime.now(timezone.utc)}] Error converting features: {e}")
            return np.array([])
            
    def _train_new_model(self, X: np.array):
        """Treniruoja naują modelį"""
        try:
            # Sukuriame "dummy" y (visi 1, nes tai sėkmingi tokenai)
            y = np.ones(X.shape[0])
            
            # Treniruojame modelį
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=5,
                min_samples_split=4,
                min_samples_leaf=2,
                random_state=42
            )
            model.fit(X, y)
            
            return model
            
        except Exception as e:
            logger.error(f"[{datetime.now(timezone.utc)}] Error training model: {e}")
            return None
        
    async def predict_potential(self, token_data: TokenMetrics) -> float:
        """Prognozuoja token'o potencialą tapti gem"""
        try:
            if not self.model:
                await self.train_model()
                if not self.model:
                    return 0.0
                
            features = self._convert_to_features([token_data])
            if len(features) == 0:
                return 0.0
                
            probability = self.model.predict_proba(features)[0][1]  # Imame teigiamos klasės tikimybę
            
            # Jei tikimybė aukšta, siunčiame žinutę
            if probability >= Config.MIN_GEM_PROBABILITY:
                await self._send_potential_gem_alert(token_data, probability)
                
            return probability
            
        except Exception as e:
            logger.error(f"[{datetime.now(timezone.utc)}] Error predicting potential: {e}")
            return 0.0
            
    async def _send_potential_gem_alert(self, token_data: TokenMetrics, probability: float):
        """Siunčia žinutę apie potencialų gem"""
        try:
            if not self.telegram_client:
                self.telegram_client = TelegramClient('ml_alert_session', 
                                                    Config.TELEGRAM_API_ID, 
                                                    Config.TELEGRAM_API_HASH)
                await self.telegram_client.start()
            
            # Formatuojame žinutę
            message = (
                f"🎯 POTENTIAL GEM DETECTED! 🎯\n\n"
                f"Token: {token_data.name} (${token_data.symbol})\n"
                f"Address: {token_data.address}\n\n"
                f"Current Stats:\n"
                f"Market Cap: ${token_data.market_cap:,.0f}\n"
                f"Liquidity: ${token_data.liquidity:,.0f}\n"
                f"Holders: {token_data.holders_count}\n"
                f"Volume 1h: ${token_data.volume_1h:,.0f}\n\n"
                f"ML Confidence: {probability*100:.1f}%\n\n"
                f"Risk Metrics:\n"
                f"• Top Holder %: {token_data.top_holder_percentage:.1f}%\n"
                f"• Sniper Count: {token_data.sniper_count}\n"
                f"• Dev Token %: {token_data.dev_token_percentage:.1f}%\n\n"
                f"Links:\n"
                f"🐦 Twitter: {token_data.twitter_url or 'N/A'}\n"
                f"🌐 Website: {token_data.website_url or 'N/A'}"
            )
            
            await self.telegram_client.send_message(Config.TELEGRAM_DEST_CHAT, message)
            logger.info(f"[{datetime.now(timezone.utc)}] Sent potential gem alert for: {token_data.address}")
            
        except Exception as e:
            logger.error(f"[{datetime.now(timezone.utc)}] Error sending potential gem alert: {e}")
            
    async def update_model_with_new_gem(self, token_data: TokenMetrics):
        """Atnaujina modelį su nauju gem"""
        try:
            if not self.historical_data:
                self.historical_data = []
            
            self.historical_data.append(token_data)
            
            # Jei turime pakankamai duomenų, atnaujiname modelį
            if len(self.historical_data) >= Config.MIN_TRAINING_SAMPLES:
                await self.train_model()
                logger.info(f"[{datetime.now(timezone.utc)}] Model updated with new gem: {token_data.address}")
                
        except Exception as e:
            logger.error(f"[{datetime.now(timezone.utc)}] Error updating model: {e}")

class DatabaseManager:
    def __init__(self):
        self.db = AsyncDatabase()

    async def setup_database(self):
        """Initialize database tables"""
        await self.db.connect()  # Tai automatiškai iškviečia _setup_database()
        
               
        # Tada sukuriame sniper_wallets lentelę
        await self.db.execute("""
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

        # Sukuriame token_updates lentelę
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS token_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                all_metrics TEXT NOT NULL,
                timestamp TIMESTAMP,
                current_multiplier REAL,
                FOREIGN KEY(address) REFERENCES token_initial_states(address)
            )
        """)

        # Sukuriame successful_tokens lentelę
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS successful_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL UNIQUE,
                initial_parameters TEXT NOT NULL,
                time_to_10x INTEGER,
                discovery_timestamp TIMESTAMP,
                FOREIGN KEY(address) REFERENCES token_initial_states(address)
            )
        """)
        
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
            dev_token_percentage=result['dev_token_percentage']
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

    async def save_token_update(self, token_address: str, new_data: TokenMetrics):
        """Išsaugo token'o atnaujinimą"""
        try:
            initial_data = await self.get_initial_state(token_address)
            if not initial_data:
                logger.warning(f"[{datetime.now(timezone.utc)}] No initial state found for token: {token_address}")
                return
                
            current_multiplier = new_data.market_cap / initial_data.market_cap
            
            # Konvertuojame žodyną į JSON string
            metrics_json = json.dumps(new_data.to_dict())
            
            query = """
            INSERT INTO token_updates (
                address, all_metrics, timestamp, current_multiplier
            ) VALUES (?, ?, ?, ?)
            """
            await self.db.execute(query, (
                token_address, 
                metrics_json,  # Dabar perduodame JSON string vietoj žodyno
                datetime.now(timezone.utc),
                current_multiplier
            ))
            
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
        
    async def mark_as_gem(self, token_address: str):
        """Pažymi token'ą kaip gem ir išsaugo į successful_tokens"""
        # 1. Atnaujina statusą
        await self.db.execute(
            "UPDATE token_initial_states SET status = 'gem' WHERE address = ?",
            token_address
        )
        
        # 2. Gauna laiko tarpą iki 10x
        initial_data = await self.get_initial_state(token_address)
        time_to_10x = await self._calculate_time_to_10x(token_address)
        
        # 3. Išsaugo į successful_tokens
        query = """
        INSERT INTO successful_tokens (
            address, initial_parameters, time_to_10x, discovery_timestamp
        ) VALUES (?, ?, ?, ?)
        """
        await self.db.execute(query, (
            token_address,
            initial_data.to_dict(),
            time_to_10x,
            datetime.now(timezone.utc)
        ))
        
    async def get_all_gems(self):
        """Gauna visus sėkmingus tokenus mokymui"""
        try:
            query = """
            SELECT * FROM successful_tokens
            ORDER BY discovery_timestamp DESC
            """
            results = await self.db.fetch_all(query)
            logger.info(f"[{datetime.now(timezone.utc)}] Found {len(results) if results else 0} gems in database")
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
            # Tikriname token_initial_states
            initial_states = await self.db.fetch_all("""
                SELECT COUNT(*) as count, status, COUNT(DISTINCT address) as unique_addresses 
                FROM token_initial_states 
                GROUP BY status
            """)
            for state in initial_states:
                logger.info(f"[{datetime.now(timezone.utc)}] Initial states - Status: {state['status']}, "
                           f"Count: {state['count']}, Unique addresses: {state['unique_addresses']}")

            # Tikriname successful_tokens
            successful = await self.db.fetch_all("""
                SELECT COUNT(*) as count FROM successful_tokens
            """)
            logger.info(f"[{datetime.now(timezone.utc)}] Successful tokens count: {successful[0]['count']}")

            # Tikriname token_updates
            updates = await self.db.fetch_all("""
                SELECT COUNT(*) as count, COUNT(DISTINCT address) as unique_addresses 
                FROM token_updates
            """)
            logger.info(f"[{datetime.now(timezone.utc)}] Updates count: {updates[0]['count']}, "
                       f"Unique addresses: {updates[0]['unique_addresses']}")

        except Exception as e:
            logger.error(f"[{datetime.now(timezone.utc)}] Error checking database: {e}")
    
    async def _calculate_time_to_10x(self, token_address: str) -> int:
        """Apskaičiuoja laiką (sekundėmis) per kurį token'as pasiekė 10x"""
        try:
            # Gauname pradinę būseną
            initial_state = await self.get_initial_state(token_address)
            if not initial_state:
                return 0

            # Gauname visus atnaujinimus, surūšiuotus pagal laiką
            query = """
            SELECT timestamp, current_multiplier 
            FROM token_updates 
            WHERE address = ? 
            ORDER BY timestamp ASC
            """
            updates = await self.db.fetch_all(query, token_address)
            
            if not updates:
                return 0

            # Ieškome pirmo atnaujinimo, kur multiplier >= 10
            initial_time = datetime.fromisoformat(str(initial_state['first_seen']))
            
            for update in updates:
                if update['current_multiplier'] >= 10:
                    update_time = datetime.fromisoformat(str(update['timestamp']))
                    return int((update_time - initial_time).total_seconds())
            
            return 0
            
        except Exception as e:
            logger.error(f"[{datetime.now(timezone.utc)}] Error calculating time to 10x: {e}")
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
            logger.error(f"[2025-01-31 15:29:30] Error showing database contents: {e}")
            logger.error(f"Exception details: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

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

class TokenMonitor:
    def __init__(self, db_manager, ml_analyzer, token_handler):
        self.db = db_manager
        self.ml = ml_analyzer
        self.handler = token_handler
        self.monitoring_tokens = set()
        
    async def start_monitoring(self):
        """Pradeda token'ų stebėjimą"""
        while True:
            try:
                # 1. Gauna visus stebimus tokenus
                active_tokens = await self.db.get_active_tokens()
                
                for token in active_tokens:
                    # 2. Gauna naujausius duomenis
                    current_data = await self._fetch_current_data(token.address)
                    
                    # 3. Apdoroja atnaujinimą
                    await self.handler.handle_token_update(token.address, current_data)
                    
                    # 4. Tikrina ar tapo "gem"
                    initial_data = await self.db.get_initial_state(token.address)
                    multiplier = current_data.market_cap / initial_data.market_cap
                    
                    if multiplier >= 10:
                        await self._handle_new_gem(token.address, initial_data, current_data)
                
                await asyncio.sleep(60)  # Tikrina kas minutę
                
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(10)
                
    async def _handle_new_gem(self, address, initial_data, current_data):
        """Apdoroja naują gem"""
        await self.db.mark_as_gem(address)
        await self.ml.update_model_with_new_gem(initial_data)
        
        success_pattern = {
            'initial_state': initial_data.to_dict(),
            'time_to_gem': (current_data.timestamp - initial_data.timestamp),
            'final_multiplier': current_data.market_cap / initial_data.market_cap
        }
        await self.db.save_success_pattern(address, success_pattern)

class TokenAnalyzer:
    def __init__(self, db_manager, ml_analyzer):
        self.db = db_manager
        self.ml = ml_analyzer

    def prepare_features(self, token: TokenMetrics, updates: List[TokenUpdate]) -> Dict:
        """Paruošia visus features ML modeliui"""
        return {
            # 1. Pagrindinė informacija ir jos analizė
            'basic_metrics': self._analyze_basic_metrics(token),
            
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
            'wallet_behavior': self._analyze_wallets(token.sniper_wallets),
            
            # 10. Rizikos vertinimas
            'risk_assessment': self._calculate_risk_metrics(token)
        }

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
        sniper_types = self._categorize_snipers(token.sniper_wallets)
        return {
            'sniper_impact': token.sniper_percentage / 100,
            'whale_dominance': sniper_types['whale_count'] / max(len(token.sniper_wallets), 1),
            'fish_ratio': sniper_types['fish_count'] / max(len(token.sniper_wallets), 1),
            'sniper_diversity': self._calculate_sniper_diversity(token.sniper_wallets),
            'sniper_behavior_pattern': self._analyze_sniper_patterns(token.sniper_wallets)
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
            # Renkame saugumo faktorius
            contract_security = self._assess_contract_security(token)
            ownership_security = self._calculate_ownership_score(token)
            lp_security = token.lp_burnt_percentage / 100
            
            # Skaičiuojame bendrą security risk
            security_risk = 1.0 - ((contract_security + ownership_security + lp_security) / 3)
            
            # Pridedame papildomą riziką jei yra mint arba freeze
            if token.mint_enabled:
                security_risk += 0.3
            if token.freeze_enabled:
                security_risk += 0.2
                
            return min(security_risk, 1.0)  # Normalizuojame iki 1.0
        except:
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
        """Inicializuojame GemFinder"""
        self.telegram = TelegramClient('gem_finder_session', 
                                     Config.TELEGRAM_API_ID, 
                                     Config.TELEGRAM_API_HASH)
        self.scanner_client = TelegramClient('scanner_session',
                                           Config.TELEGRAM_API_ID,
                                           Config.TELEGRAM_API_HASH)

        
        # Pirma sukuriame db_manager
        self.db_manager = DatabaseManager()
        
        # Tada sukuriame TokenAnalyzer
        self.token_analyzer = TokenAnalyzer(self.db_manager, None)  # Laikinai None
        
        # Tada perduodame token_analyzer į MLAnalyzer
        self.ml_analyzer = MLAnalyzer(self.db_manager, self.token_analyzer)
        
        # Atnaujiname token_analyzer su teisingu ml_analyzer
        self.token_analyzer.ml = self.ml_analyzer

        
        
        # Kiti komponentai
        self.processed_messages = set()
        
        logger.info(f"[2025-01-31 13:19:12] GemFinder initialized")
        
    async def start(self):
        """Paleidžia GemFinder"""
        # Pirma inicializuojame duomenų bazę
        await self.db_manager.setup_database()  # <-- Čia perkeliame!
        await self.telegram.start()
        await self.scanner_client.start()
        logger.info(f"[2025-01-31 13:30:42] GemFinder started")
        
        # Patikriname duomenų bazės būseną
        await self.db_manager.check_database()

        # Parodome duomenų bazės turinį
        await self.db_manager.show_database_contents()
        
        # Užkrauname istorinius duomenis
        await self.ml_analyzer.load_historical_data()
        
        # Registruojame message handler'į
        @self.telegram.on(events.NewMessage(chats=Config.TELEGRAM_SOURCE_CHATS))
        async def message_handler(event):
            await self._handle_message(event)
            
        # Laukiame pranešimų
        await self.telegram.run_until_disconnected()

    async def stop(self):
        """Sustabdo GemFinder"""
        await self.telegram.disconnect()
        await self.scanner_client.disconnect()
        logger.info(f"[2025-01-31 13:08:54] GemFinder stopped")
        
    async def _handle_message(self, event: events.NewMessage.Event):
        """Apdoroja naują pranešimą"""
        try:
            message = event.message.text
            message_id = event.message.id
            
            if message_id in self.processed_messages:
                return
                
            logger.info(f"[2025-01-31 13:08:54] Processing message ID: {message_id}")
            
            if "New" in message:
                await self._handle_new_token(message)
            elif "from" in message:
                await self._handle_token_update(message)
                
            self.processed_messages.add(message_id)
            
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
            logger.info(f"[2025-01-31 13:25:15] Processing new token: {token_address}")

            # Renkame token info
            token_data = await self._collect_token_data(token_address)
            if not token_data:
                return

            # Išsaugome pradinį snapshot
            await self.db_manager.save_initial_state(token_data)
            logger.info(f"[2025-01-31 13:25:15] Saved initial state for: {token_address}")

            


        except Exception as e:
            logger.error(f"[2025-01-31 13:25:15] Error handling new token: {e}")

    async def _handle_token_update(self, message: str):
        """Apdoroja token'o atnaujinimą"""
        try:
            token_addresses = self._extract_token_addresses(message)
            if not token_addresses:
                return

            token_address = token_addresses[0]
            current_data = await self._collect_token_data(token_address)
            if not current_data:
                return

            


            # Patikriname ar token'as jau yra DB
            initial_data = await self.db_manager.get_initial_state(token_address)
            if initial_data:
                # Jei yra, išsaugome atnaujinimą
                logger.info(f"[{datetime.now(timezone.utc)}] Saving update for token: {token_address}")
                await self.db_manager.save_token_update(token_address, current_data)

                # Tikriname ar tapo gem
                current_multiplier = current_data.market_cap / initial_data.market_cap
                if current_multiplier >= 10 and not await self.db_manager.is_gem(token_address):
                    await self.db_manager.mark_as_gem(token_address)
                    logger.info(f"[{datetime.now(timezone.utc)}] Token marked as gem: {token_address} ({current_multiplier:.2f}X)")
            else:
                # Jei nėra, išsaugome kaip naują
                logger.info(f"[{datetime.now(timezone.utc)}] Token not found in DB, saving as new: {token_address}")
                
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
        
        # Pašalinam telegramą ir kitus URL
        cleaned = re.sub(r'\[.*?\]\(https?://[^)]+\)', '', text)
        # Pašalinam Markdown žymėjimą
        cleaned = re.sub(r'\*\*', '', cleaned)
        # Pašalinam likusius [] ir ()
        cleaned = re.sub(r'[\[\]()]', '', cleaned)
        
        # Pašalinam visus specialius simbolius, išskyrus svarbius emoji
        result = ''
        i = 0
        while i < len(cleaned):
            if any(cleaned.startswith(emoji, i) for emoji in important_emoji):
                emoji_found = next(emoji for emoji in important_emoji if cleaned.startswith(emoji, i))
                result += emoji_found
                i += len(emoji_found)
            else:
                if cleaned[i].isalnum() or cleaned[i] in ' .:$%|-':
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
                        mc = re.search(r'\$(\d+\.?\d*)K', clean_line)  # MC visada K
                        
                        # ATH gali būti K arba M
                        ath_k = re.search(r'\$(\d+\.?\d*)K', clean_line)  # Ieškome K
                        ath_m = re.search(r'\$(\d+\.?\d*)M', clean_line)  # Ieškome M
                        
                        if mc:
                            data['market_cap'] = float(mc.group(1)) * 1000
                            
                        # ATH ieškojimas (po 🔝)
                        ath = re.search(r'🔝 \$(\d+\.?\d*)K', clean_line)
                        if ath:
                            data['ath_market_cap'] = float(ath.group(1)) * 1000
                    
                    # Liquidity
                    elif 'Liq:' in line:
                        liq = re.search(r'\$(\d+\.?\d*)K\s*\((\d+)\s*SOL\)', clean_line)
                        if liq:
                            data['liquidity'] = {
                                'usd': float(liq.group(1)) * 1000,
                                'sol': float(liq.group(2))
                            }
                    
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

# Main programos paleidimas
if __name__ == "__main__":
    try:
        gem_finder = GemFinder()
        logger.info(f"[2025-01-31 12:41:51] Starting GemFinder...")
        
        loop = asyncio.get_event_loop()
        loop.run_until_complete(gem_finder.start())
        
    except KeyboardInterrupt:
        logger.info(f"[2025-01-31 12:41:51] Shutting down GemFinder...")
        loop = asyncio.get_event_loop()
        loop.run_until_complete(gem_finder.stop())
    except Exception as e:
        logger.error(f"[2025-01-31 12:41:51] Fatal error: {str(e)}")
        raise                        
