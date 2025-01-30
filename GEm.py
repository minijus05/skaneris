import asyncio
import sys
import nest_asyncio
import logging
from dataclasses import dataclass
from dataclasses import fields
from datetime import datetime, timezone, timedelta
import time 
from typing import List, Dict, Optional, Union
import re
import pandas as pd
import numpy as np
from telethon import TelegramClient, events
from telethon.tl.types import Message
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import aiohttp
from sklearn.model_selection import cross_val_score


# Current settings
CURRENT_UTC_TIME = "2025-01-29 15:53:31"


class Config:
    """
    Configuration class for GemFinder application.
    Last Updated: 2025-01-29 17:41:09
    """
    # Base constants (no dependencies)
    MAX_SNIPER_PERCENTAGE = 10
    MIN_SUCCESS_PROBABILITY = 0.6
    FIRST_20_FRESH_MIN = 10

    # Telegram settings
    TELEGRAM_API_ID = '25425140'
    TELEGRAM_API_HASH = 'bd0054bc5393af360bc3930a27403c33'
    TELEGRAM_SOURCE_CHATS = ['@solearlytrending', '@botubotass']
    TELEGRAM_DEST_CHAT = '@smartas1'

    # Scanner group and bots
    SCANNER_GROUP = '@skaneriss'  # https://t.me/skaneriss
    SOUL_SCANNER_BOT = 6872314605  # Vietoj '@soul_scanner_bot'
    GMGN_BOT = 6344329830  # Vietoj '@GMGNAI_bot'
    
    
    

    # GEM kriterijai pagal visų ekspertų rekomendacijas
    GEM_CRITERIA = {
        'MARKET_CAP': {
            'MICRO': {'MIN': 1000, 'MAX': 100000},     # $1K - $100K
            'SMALL': {'MIN': 100000, 'MAX': 500000},   # $100K - $500K
            'MEDIUM': {'MIN': 500000, 'MAX': 2000000}, # $500K - $2M
            'OPTIMAL_RANGE': {'MIN': 5000, 'MAX': 300000}  # Optimali zona
        },
        'LIQUIDITY': {
            'MIN': 5000,     # Minimum $5K
            'MAX': 50000,    # Maximum $50K
            'SOL_MIN': 15,   # Minimum SOL amount
            'OPTIMAL_RATIO': 0.1  # Liquidity/MCap ratio
        },
        'HOLDERS': {
            'MIN_COUNT': 40,
            'MAX_TOP_HOLDER': 2,     # %
            'MIN_UNIQUE_BUYERS': 30,
            'DISTRIBUTION': {
                'TOP_1': 2,          # Max % for top holder
                'TOP_5': 8,          # Max % for top 5
                'TOP_10': 15,        # Max % for top 10
                'TEAM_MAX': 5        # Max % for team
            }
        },
        'AGE_AND_TIMING': {
            'MIN_HOURS': 1,
            'MAX_DAYS': 7,
            'OPTIMAL_HOURS': 24,
            'BEST_ENTRY_TIMES': ['DIP_AFTER_ATH', 'SIDEWAYS_CONSOLIDATION', 'EARLY_UPTREND']
        },
        'VOLUME': {
            'MIN_24H': 1000,         # $1K minimum daily volume
            'MIN_LIQUIDITY_RATIO': 0.1, # Volume/Liquidity ratio
            'HEALTHY_GROWTH': {
                'MIN': 20,           # % minimum growth
                'MAX': 300           # % maximum growth (avoid pump&dumps)
            }
        },
        'SOCIAL_METRICS': {
            'TELEGRAM': {
                'MIN_MEMBERS': 100,
                'GROWTH_RATE': 10,   # % daily growth
                'ACTIVITY_SCORE': 7   # 1-10 scale
            },
            'TWITTER': {
                'MIN_FOLLOWERS': 100,
                'MIN_ENGAGEMENT': 5,  # % engagement rate
                'ACCOUNT_AGE': 30     # days
            },
            'WEBSITE': {
                'REQUIRED': True,
                'SSL_REQUIRED': True,
                'CONTENT_QUALITY': 7  # 1-10 scale
            }
        }
    }
    
    # Trading kriterijai
    TRADING_CRITERIA = {
        'TAXES': {
            'BUY_MAX': 10,    # %
            'SELL_MAX': 10,   # %
            'TOTAL_MAX': 15   # %
        },
        'LP_REQUIREMENTS': {
            'MIN_LOCKED': 95,         # %
            'MIN_LOCK_TIME': 30,      # days
            'BURN_ACCEPTABLE': True
        },
        'CHART_PATTERNS': {
            'BULLISH': [
                'HIGHER_LOWS',
                'CUP_AND_HANDLE',
                'BULL_FLAG',
                'ASCENDING_TRIANGLE'
            ],
            'ENTRY_POINTS': [
                'SUPPORT_BOUNCE',
                'GOLDEN_POCKET',
                'BREAK_AND_RETEST'
            ]
        }
    }
    
    # Security checks ir red flags
    SECURITY_CHECKS = {
        'CONTRACT_RED_FLAGS': {
            'MINT_ENABLED': True,
            'FREEZE_ENABLED': True,
            'HIDDEN_OWNER': True,
            'PROXY_CONTRACT': True,
            'HONEYPOT_POTENTIAL': True,
            'HIGH_TOP_HOLDERS': True
        },
        'TRADING_RED_FLAGS': {
            'EXCESSIVE_BUYING_TAX': 10,  # %
            'EXCESSIVE_SELLING_TAX': 10, # %
            'TRADING_COOL_DOWN': 60,     # seconds
            'MAX_TRANSACTION_LIMIT': 1,  # % of supply
            'MAX_WALLET_LIMIT': 2        # % of supply
        },
        'DEVELOPER_CHECKS': {
            'KNOWN_DEVELOPER': {
                'REQUIRED': False,
                'REPUTATION_CHECK': True
            },
            'PREVIOUS_PROJECTS': {
                'CHECK_HISTORY': True,
                'MIN_SUCCESS_RATE': 0.5
            },
            'WALLET_ANALYSIS': {
                'CHECK_AGE': True,
                'MIN_SOL_BALANCE': 0.5,
                'CHECK_TRANSACTIONS': True
            }
        },
        'LIQUIDITY_CHECKS': {
            'MIN_LP_TOKENS_BURNT': 95,   # %
            'OR_MIN_LOCK_TIME': 180,     # days
            'MAX_UNLOCKED': 5,           # %
            'CHECK_LOCK_CONTRACT': True
        }
    }

    # Rinkos analizės reikalavimai
    MARKET_ANALYSIS = {
        'TIMING': {
            'SOL_TREND': 'BULLISH',
            'MARKET_SENTIMENT': 'NEUTRAL_TO_BULLISH',
            'SECTOR_PERFORMANCE': 'POSITIVE'
        },
        'COMPARISON_METRICS': {
            'SIMILAR_TOKENS': 5,          # Number of tokens to compare
            'SECTOR_ANALYSIS': True,
            'COMPETITION_CHECK': True
        },
        'GROWTH_POTENTIAL': {
            'MIN_UPSIDE': 2,              # 2x minimum potential
            'REALISTIC_TARGET': 5,         # 5x realistic target
            'MAXIMUM_TARGET': 20           # 20x maximum target
        },
        'MOMENTUM_INDICATORS': {
            'RSI': {'OVERSOLD': 30, 'OVERBOUGHT': 70},
            'MACD': 'POSITIVE_CROSSOVER',
            'VOLUME_TREND': 'INCREASING'
        }
    }

    # Risk levels
    RISK_LEVELS = {
        'LOW': {
            'score': 80,
            'position_size': 0.1,
            'stop_loss': 0.10,
            'take_profit': 0.30
        },
        'MEDIUM': {
            'score': 65,
            'position_size': 0.05,
            'stop_loss': 0.15,
            'take_profit': 0.45
        },
        'HIGH': {
            'score': 50,
            'position_size': 0.02,
            'stop_loss': 0.20,
            'take_profit': 0.60
        }
    }

    # Entry strategijos
    ENTRY_STRATEGIES = {
        'SCALING': {
            'ENTRY_POINTS': [0.25, 0.25, 0.5],  # 25% + 25% + 50%
            'PRICE_LEVELS': ['INITIAL', 'DIP_10', 'DIP_20']
        },
        'POSITION_SIZING': {
            'MAX_PORTFOLIO_RISK': 0.02,  # 2% max risk per trade
            'MAX_POSITION_SIZE': 0.10    # 10% max position size
        }
    }

    # Derived constants (must be after all dictionaries)
    MIN_LIQUIDITY = GEM_CRITERIA['LIQUIDITY']['MIN']
    MIN_HOLDERS = GEM_CRITERIA['HOLDERS']['MIN_COUNT']
    MIN_LP_BURNT = SECURITY_CHECKS['LIQUIDITY_CHECKS']['MIN_LP_TOKENS_BURNT']
    

# Logging configuration with simplified formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s UTC | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


@dataclass
class TokenMetrics:
    # Basic info (required fields)
    address: str
    name: str
    symbol: str
    creation_date: datetime
    
    # Price metrics (required fields)
    price: float
    market_cap: float
    liquidity: float
    volume_24h: float
    price_change_24h: float
    
    # Security metrics (required fields)
    mint_enabled: bool
    freeze_enabled: bool
    lp_burnt_percentage: float
    
    # Holder metrics (required fields)
    holders_count: int
    top_holder_percentage: float
    top_10_holders: List[Dict]
    
    # Trading metrics (required fields)
    sniper_count: int
    sniper_percentage: float
    first_20_fresh: int
    first_70_status: Dict[str, int]
    
    # Optional fields (with default values)
    ath_market_cap: float = 0
    ath_multiplier: float = 1.0
    owner_renounced: bool = False
    telegram_members: Optional[int] = None
    twitter_followers: Optional[int] = None
    website_url: Optional[str] = None
    dev_wallet: Optional[str] = None
    dev_sol_balance: float = 0
    dev_token_percentage: float = 0


    telegram_url: Optional[str] = None  # Pakeista iš telegram_members
    twitter_url: Optional[str] = None   # Pakeista iš twitter_followers

class GemScorer:
    def __init__(self):
        self.score = 0
        logger.info(f"[2025-01-29 16:34:03] GemScorer initialized")

    def evaluate_token(self, token: TokenMetrics, market_analysis: Dict) -> Dict:
        """Pilna token'o įvertinimo analizė pagal visus kriterijus"""
        logger.info(f"[2025-01-29 16:34:03] Starting evaluation for {token.address}")

        # Pagrindiniai įvertinimai
        scores = {
            'market_metrics': self._evaluate_market_metrics(token),
            'security': self._evaluate_security(token),
            'holders': self._evaluate_holders(token),
            'trading': self._evaluate_trading_metrics(token),
            'social': self._evaluate_social_metrics(token),
            'timing': self._evaluate_market_timing(market_analysis)
        }

        # Skaičiuojame bendrą score su svoriais
        weights = {
            'market_metrics': 0.25,
            'security': 0.25,
            'holders': 0.20,
            'trading': 0.15,
            'social': 0.10,
            'timing': 0.05
        }

        total_score = sum(score * weights[key] for key, score in scores.items())

        # Red flags patikrinimas
        red_flags = self._check_red_flags(token)
        
        # Entry points analizė
        entry_strategy = self._analyze_entry_strategy(token, total_score)

        result = {
            'total_score': total_score,
            'detailed_scores': scores,
            'red_flags': red_flags,
            'potential_rating': self._calculate_potential_rating(total_score, red_flags),
            'entry_strategy': entry_strategy,
            'recommendation': self._generate_recommendation(total_score, red_flags)
        }

        logger.info(f"[2025-01-29 16:34:03] Evaluation complete. Score: {total_score:.2f}")
        return result

    def _evaluate_market_metrics(self, token: TokenMetrics) -> float:
        """Market cap ir liquidity įvertinimas"""
        score = 0
        mc_range = Config.GEM_CRITERIA['MARKET_CAP']
        
        # Market Cap check
        if mc_range['OPTIMAL_RANGE']['MIN'] <= token.market_cap <= mc_range['OPTIMAL_RANGE']['MAX']:
            score += 0.4
        elif token.market_cap < mc_range['MICRO']['MAX']:
            score += 0.3
            
        # Liquidity check
        if token.liquidity >= Config.GEM_CRITERIA['LIQUIDITY']['MIN']:
            score += 0.3
            
        # Liquidity/MCap ratio
        if token.liquidity / token.market_cap >= Config.GEM_CRITERIA['LIQUIDITY']['OPTIMAL_RATIO']:
            score += 0.3
            
        return min(1.0, score)

    def _evaluate_security(self, token: TokenMetrics) -> float:
        """Security metrics įvertinimas"""
        score = 0
        
        # Contract security
        if not token.mint_enabled and not token.freeze_enabled:
            score += 0.4
            
        # LP burnt/locked
        if token.lp_burnt_percentage >= Config.SECURITY_CHECKS['LIQUIDITY_CHECKS']['MIN_LP_TOKENS_BURNT']:
            score += 0.4
            
        # Owner analysis
        if token.dev_wallet and token.dev_sol_balance >= Config.SECURITY_CHECKS['DEVELOPER_CHECKS']['WALLET_ANALYSIS']['MIN_SOL_BALANCE']:
            score += 0.2
            
        return score

    def _evaluate_holders(self, token: TokenMetrics) -> float:
        """Holder'ių distribucijos įvertinimas"""
        score = 0
        holder_criteria = Config.GEM_CRITERIA['HOLDERS']
        
        # Minimum holders
        if token.holders_count >= holder_criteria['MIN_COUNT']:
            score += 0.3
            
        # Top holder percentage
        if token.top_holder_percentage <= holder_criteria['DISTRIBUTION']['TOP_1']:
            score += 0.3
            
        # Fresh wallets ratio
        if token.first_20_fresh >= Config.FIRST_20_FRESH_MIN:
            score += 0.2
            
        # Unique buyers
        if token.first_70_status.get('holders', 0) >= holder_criteria['MIN_UNIQUE_BUYERS']:
            score += 0.2
            
        return score

    def _evaluate_trading_metrics(self, token: TokenMetrics) -> float:
        """Įvertina trading metrikas"""
        score = 0
        trading_criteria = Config.TRADING_CRITERIA
        volume_criteria = Config.GEM_CRITERIA['VOLUME']
        
        # Volume check
        if token.volume_24h >= volume_criteria['MIN_24H']:
            score += 0.3
            
        # Volume/Liquidity ratio
        vol_liq_ratio = token.volume_24h / token.liquidity if token.liquidity > 0 else 0
        if vol_liq_ratio >= volume_criteria['MIN_LIQUIDITY_RATIO']:
            score += 0.2
            
        # Growth check
        if 0 < token.price_change_24h <= volume_criteria['HEALTHY_GROWTH']['MAX']:
            score += 0.3
            
        # Tax check
        if (not hasattr(token, 'buy_tax') or token.buy_tax <= trading_criteria['TAXES']['BUY_MAX']) and \
           (not hasattr(token, 'sell_tax') or token.sell_tax <= trading_criteria['TAXES']['SELL_MAX']):
            score += 0.2
            
        return min(1.0, score)

    def _evaluate_social_metrics(self, token: TokenMetrics) -> float:
        """Įvertina socialinius metrikas"""
        score = 0
        social_criteria = Config.GEM_CRITERIA['SOCIAL_METRICS']
        
        # Telegram metrics
        if token.telegram_members and token.telegram_members >= social_criteria['TELEGRAM']['MIN_MEMBERS']:
            score += 0.4
            
        # Twitter metrics
        if token.twitter_followers and token.twitter_followers >= social_criteria['TWITTER']['MIN_FOLLOWERS']:
            score += 0.3
            
        # Website check
        if token.website_url and social_criteria['WEBSITE']['REQUIRED']:
            score += 0.3
            
        return min(1.0, score)

    def _evaluate_market_timing(self, market_analysis: Dict) -> float:
        """Įvertina market timing"""
        score = 0
        timing_criteria = Config.MARKET_ANALYSIS['TIMING']
        
        # Market sentiment check
        if market_analysis['market_sentiment']['overall'] in ['BULLISH', 'VERY_BULLISH']:
            score += 0.4
        elif market_analysis['market_sentiment']['overall'] == 'NEUTRAL':
            score += 0.2
            
        # Sector performance
        if market_analysis.get('sector_performance', {}).get('trend') == timing_criteria['SECTOR_PERFORMANCE']:
            score += 0.3
            
        # SOL trend
        if market_analysis.get('market_sentiment', {}).get('sol_momentum') == timing_criteria['SOL_TREND']:
            score += 0.3
            
        return min(1.0, score)

    def _check_red_flags(self, token: TokenMetrics) -> List[str]:
        """Red flags patikrinimas"""
        red_flags = []
        
        # Contract red flags
        if token.mint_enabled:
            red_flags.append("MINT_ENABLED")
        if token.freeze_enabled:
            red_flags.append("FREEZE_ENABLED")
            
        # Holder concentration
        if token.top_holder_percentage > Config.GEM_CRITERIA['HOLDERS']['MAX_TOP_HOLDER']:
            red_flags.append("HIGH_HOLDER_CONCENTRATION")
            
        # Sniper detection
        if token.sniper_percentage > Config.MAX_SNIPER_PERCENTAGE:
            red_flags.append("HIGH_SNIPER_CONCENTRATION")
            
        # LP security
        if token.lp_burnt_percentage < Config.SECURITY_CHECKS['LIQUIDITY_CHECKS']['MIN_LP_TOKENS_BURNT']:
            red_flags.append("INSUFFICIENT_LP_SECURITY")
            
        return red_flags

    def _analyze_entry_strategy(self, token: TokenMetrics, score: float) -> Dict:
        """Entry strategijos analizė"""
        if score < 0.5:
            return {"recommendation": "NO_ENTRY", "reason": "Low overall score"}
            
        strategy = {
            "type": "SCALING" if score > 0.7 else "SINGLE_ENTRY",
            "position_size": self._calculate_position_size(token, score),
            "entry_points": self._determine_entry_points(token, score)
        }
        
        return strategy

    def _determine_entry_points(self, token: TokenMetrics, score: float) -> List[Dict]:
        """Nustato entry points"""
        entry_strategy = Config.ENTRY_STRATEGIES['SCALING']
        current_price = token.price
        
        if score < 0.6:
            return [{'price': current_price, 'size': 1.0, 'type': 'SINGLE_ENTRY'}]
            
        entry_points = []
        for i, (size, level) in enumerate(zip(entry_strategy['ENTRY_POINTS'], 
                                            entry_strategy['PRICE_LEVELS'])):
            if level == 'INITIAL':
                price = current_price
            elif level == 'DIP_10':
                price = current_price * 0.9
            elif level == 'DIP_20':
                price = current_price * 0.8
                
            entry_points.append({
                'price': price,
                'size': size,
                'type': f'ENTRY_{i+1}'
            })
            
        return entry_points

    def _calculate_position_size(self, token: TokenMetrics, score: float) -> float:
        """Apskaičiuoja rekomenduojamą pozicijos dydį"""
        position_criteria = Config.ENTRY_STRATEGIES['POSITION_SIZING']
        
        # Base position size calculation
        max_position = min(
            token.liquidity * position_criteria['MAX_POSITION_SIZE'],
            token.market_cap * position_criteria['MAX_PORTFOLIO_RISK']
        )
        
        # Adjust based on score
        if score >= 0.8:
            return max_position
        elif score >= 0.6:
            return max_position * 0.7
        elif score >= 0.4:
            return max_position * 0.5
        else:
            return max_position * 0.3

    def _calculate_potential_rating(self, score: float, red_flags: List[str]) -> str:
        """Potencialo įvertinimas"""
        if len(red_flags) > 0:
            return "HIGH_RISK"
        elif score >= 0.8:
            return "STRONG_POTENTIAL"
        elif score >= 0.6:
            return "MODERATE_POTENTIAL"
        else:
            return "LOW_POTENTIAL"

    def _generate_recommendation(self, score: float, red_flags: List[str]) -> str:
        """Rekomendacijos generavimas"""
        if len(red_flags) > 0:
            return f"AVOID - {len(red_flags)} red flags detected"
        elif score >= 0.8:
            return "STRONG BUY - High potential gem detected"
        elif score >= 0.6:
            return "CONSIDER - Moderate potential with acceptable risk"
        else:
            return "PASS - Insufficient criteria met"



class MLAnalyzer:
    def __init__(self):
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=None,
            min_samples_split=2,
            min_samples_leaf=1,
            random_state=42
        )
        self.scaler = StandardScaler()
        # Sukuriame DataFrame istoriniams duomenims
        self.historical_data = pd.DataFrame(columns=[
            'address',
            'creation_time',
            'initial_liquidity',
            'initial_holders',
            'initial_price',
            'volume_first_24h',
            'holder_growth_rate',
            'price_volatility',
            'social_score',
            'dev_reputation',
            'success'  # Target variable
        ])
        logger.info(f"[2025-01-29 16:28:24] User minijus05: MLAnalyzer initialized")
        
    def save_historical_data(self):
        """Išsaugome istorinius duomenis į CSV"""
        try:
            self.historical_data.to_csv('gem_historical_data.csv', index=False)
            logger.info(f"[2025-01-29 16:28:24] User minijus05: Historical data saved successfully. Total records: {len(self.historical_data)}")
        except Exception as e:
            logger.error(f"[2025-01-29 16:28:24] User minijus05: Error saving historical data: {e}")
    
    def load_historical_data(self):
        """Užkrauname istorinius duomenis iš CSV"""
        try:
            self.historical_data = pd.read_csv('gem_historical_data.csv')
            logger.info(f"[2025-01-29 16:28:24] User minijus05: Loaded {len(self.historical_data)} historical records")
        except FileNotFoundError:
            logger.warning(f"[2025-01-29 16:28:24] User minijus05: No historical data file found. Starting fresh.")
    
    def add_token_data(self, token: TokenMetrics, success: bool):
        """Pridedame naują token'ą į istorinių duomenų bazę"""
        logger.info(f"[2025-01-29 16:28:24] User minijus05: Adding new token data for {token.address}")
        
        social_score = self._calculate_social_score(token)
        volatility = self._calculate_volatility(token)
        
        new_data = {
            'address': token.address,
            'creation_time': token.creation_date,
            'initial_liquidity': token.liquidity,
            'initial_holders': token.holders_count,
            'initial_price': token.price,
            'volume_first_24h': token.volume_24h,
            'holder_growth_rate': 0,  # Bus atnaujinta vėliau
            'price_volatility': volatility,
            'social_score': social_score,
            'dev_reputation': token.dev_sol_balance,
            'success': 1 if success else 0
        }
        
        self.historical_data = self.historical_data.append(new_data, ignore_index=True)
        logger.info(f"[2025-01-29 16:28:24] User minijus05: Token data added. New dataset size: {len(self.historical_data)}")
        
        # Apmokome modelį jei turime pakankamai duomenų
        if len(self.historical_data) >= 100:
            self.train_model()
    
    def train_model(self):
        """Apmokome ML modelį"""
        logger.info(f"[2025-01-29 16:28:24] User minijus05: Starting model training...")
        try:
            X = self.historical_data.drop(['address', 'creation_time', 'success'], axis=1)
            y = self.historical_data['success']
            
            X_scaled = self.scaler.fit_transform(X)
            self.model.fit(X_scaled, y)
            
            score = self.model.score(X_scaled, y)
            logger.info(f"[2025-01-29 16:28:24] User minijus05: Model trained successfully. Accuracy score: {score:.2f}")
        except Exception as e:
            logger.error(f"[2025-01-29 16:28:24] User minijus05: Error training model: {e}")
    
    def predict_success(self, token: TokenMetrics) -> Dict:
        """Prognozuojame token'o sėkmės tikimybę"""
        logger.info(f"[2025-01-29 16:28:24] User minijus05: Predicting success probability for {token.address}")
        
        # Paruošiame features
        features = self._prepare_features(token)
        
        # Jei neturime pakankamai duomenų modeliui
        if len(self.historical_data) < 100:
            logger.warning(f"[2025-01-29 16:28:24] User minijus05: Insufficient historical data. Using backup scoring system.")
            return self._calculate_backup_score(token)
        
        try:
            # Normalizuojame features
            scaled_features = self.scaler.transform([features])
            
            # Prognozuojame
            probability = self.model.predict_proba(scaled_features)[0][1]
            
            # Gauname svarbiausius features
            feature_importance = dict(zip(self.model.feature_names_in_, self.model.feature_importances_))
            
            result = {
                'success_probability': probability,
                'confidence_score': self._calculate_confidence_score(probability),
                'key_factors': self._get_key_factors(feature_importance, features),
                'prediction_time': "2025-01-29 16:28:24"
            }
            
            logger.info(f"[2025-01-29 16:28:24] User minijus05: Prediction complete: {result['success_probability']:.2f} probability of success")
            return result
            
        except Exception as e:
            logger.error(f"[2025-01-29 16:28:24] User minijus05: Error making prediction: {e}")
            return self._calculate_backup_score(token)
    
    def _calculate_backup_score(self, token: TokenMetrics) -> Dict:
        """Apskaičiuojame bazinį score kai nėra pakankamai istorinių duomenų"""
        logger.info(f"[2025-01-29 16:28:24] User minijus05: Calculating backup score for {token.address}")
        
        score = 0
        factors = []
        
        # Liquidity score (0-25)
        liquidity_score = min(25, (token.liquidity / Config.GEM_CRITERIA['LIQUIDITY']['MIN']) * 10)
        score += liquidity_score
        factors.append(('liquidity', liquidity_score))
        
        # Holders score (0-20)
        holders_score = min(20, (token.holders_count / Config.GEM_CRITERIA['HOLDERS']['MIN_COUNT']) * 10)
        score += holders_score
        factors.append(('holders', holders_score))
        
        # Security score (0-20)
        security_score = 0
        if not token.mint_enabled: security_score += 7
        if not token.freeze_enabled: security_score += 7
        if token.lp_burnt_percentage >= Config.SECURITY_CHECKS['LIQUIDITY_CHECKS']['MIN_LP_TOKENS_BURNT']: 
            security_score += 6
        score += security_score
        factors.append(('security', security_score))
        
        # Trading metrics (0-20)
        trading_score = 0
        if token.volume_24h > Config.GEM_CRITERIA['VOLUME']['MIN_24H']: 
            trading_score += 10
        if token.sniper_percentage < Config.MAX_SNIPER_PERCENTAGE:
            trading_score += 10
        score += trading_score
        factors.append(('trading', trading_score))
        
        # Social score (0-15)
        social_score = 0
        if token.telegram_members and token.telegram_members > Config.GEM_CRITERIA['SOCIAL_METRICS']['TELEGRAM']['MIN_MEMBERS']:
            social_score += 5
        if token.twitter_followers and token.twitter_followers > Config.GEM_CRITERIA['SOCIAL_METRICS']['TWITTER']['MIN_FOLLOWERS']:
            social_score += 5
        if token.website_url and Config.GEM_CRITERIA['SOCIAL_METRICS']['WEBSITE']['REQUIRED']:
            social_score += 5
        score += social_score
        factors.append(('social', social_score))
        
        normalized_score = score / 100
        logger.info(f"[2025-01-29 16:28:24] User minijus05: Backup score calculated: {normalized_score:.2f}")
        
        return {
            'success_probability': normalized_score,
            'confidence_score': 'LOW',
            'key_factors': factors,
            'prediction_time': "2025-01-29 16:28:24"
        }
        
    def _calculate_social_score(self, token: TokenMetrics) -> float:
        """Apskaičiuoja social score pagal naujus kriterijus"""
        logger.info(f"[2025-01-29 16:28:24] User minijus05: Calculating social score for {token.address}")
        
        score = 0
        social_criteria = Config.GEM_CRITERIA['SOCIAL_METRICS']
        
        # Telegram metrics
        if token.telegram_members:
            if token.telegram_members >= social_criteria['TELEGRAM']['MIN_MEMBERS']:
                score += 0.3
            # Growth rate check would be here if we had historical data
            
        # Twitter metrics
        if token.twitter_followers:
            if token.twitter_followers >= social_criteria['TWITTER']['MIN_FOLLOWERS']:
                score += 0.3
                
        # Website check
        if token.website_url and social_criteria['WEBSITE']['REQUIRED']:
            score += 0.4
            
        logger.info(f"[2025-01-29 16:28:24] User minijus05: Social score calculated: {score}")
        return score

    def _calculate_volatility(self, token: TokenMetrics) -> float:
        """Apskaičiuoja token'o volatility score"""
        logger.info(f"[2025-01-29 16:28:24] User minijus05: Calculating volatility for {token.address}")
        
        try:
            # Basic volatility calculation based on price change
            if token.price_change_24h is not None:
                volatility = abs(token.price_change_24h) / 100
                
                # Normalize volatility score between 0 and 1
                normalized_volatility = min(1.0, volatility / Config.GEM_CRITERIA['VOLUME']['HEALTHY_GROWTH']['MAX'])
                
                logger.info(f"[2025-01-29 16:28:24] User minijus05: Volatility calculated: {normalized_volatility:.2f}")
                return normalized_volatility
            return 0.5  # Default medium volatility if no data
            
        except Exception as e:
            logger.error(f"[2025-01-29 16:28:24] User minijus05: Error calculating volatility: {e}")
            return 0.5

    def _prepare_features(self, token: TokenMetrics) -> List[float]:
        """Paruošia features ML modeliui"""
        logger.info(f"[2025-01-29 16:28:24] User minijus05: Preparing features for {token.address}")
        
        features = [
            token.liquidity,
            token.holders_count,
            token.price,
            token.volume_24h,
            0,  # holder_growth_rate (bus atnaujinta vėliau)
            self._calculate_volatility(token),
            self._calculate_social_score(token),
            token.dev_sol_balance
        ]
        
        logger.info(f"[2025-01-29 16:28:24] User minijus05: Features prepared successfully")
        return features

    def _calculate_confidence_score(self, probability: float) -> str:
        """Apskaičiuoja prediction confidence level"""
        if probability >= 0.8:
            return 'VERY_HIGH'
        elif probability >= 0.6:
            return 'HIGH'
        elif probability >= 0.4:
            return 'MEDIUM'
        elif probability >= 0.2:
            return 'LOW'
        return 'VERY_LOW'

    def _get_key_factors(self, feature_importance: Dict, features: List) -> List[str]:
        """Išrenka svarbiausius faktorius"""
        logger.info(f"[2025-01-29 16:28:24] User minijus05: Getting key factors from model")
        
        # Sutvarkome feature importance į list of tuples
        importance_list = [(name, importance) for name, importance in feature_importance.items()]
        
        # Surūšiuojame pagal svarbumą
        importance_list.sort(key=lambda x: x[1], reverse=True)
        
        # Grąžiname top 3 faktorius
        return [factor[0] for factor in importance_list[:3]]

    def update_model_metrics(self):
        """Atnaujina modelio metrikas"""
        logger.info(f"[2025-01-29 16:28:24] User minijus05: Updating model metrics")
        
        try:
            X = self.historical_data.drop(['address', 'creation_time', 'success'], axis=1)
            y = self.historical_data['success']
            
            # Skaičiuojame įvairias metrikas
            scores = cross_val_score(self.model, X, y, cv=5)
            
            metrics = {
                'accuracy_mean': scores.mean(),
                'accuracy_std': scores.std(),
                'total_samples': len(X),
                'feature_importance': dict(zip(X.columns, self.model.feature_importances_))
            }
            
            logger.info(f"[2025-01-29 16:28:24] User minijus05: Model metrics updated: Accuracy = {metrics['accuracy_mean']:.2f}")
            return metrics
            
        except Exception as e:
            logger.error(f"[2025-01-29 16:28:24] User minijus05: Error updating model metrics: {e}")
            return None
        
class MarketAnalyzer:
    def __init__(self):
        self.market_data = {}
        self.sector_performance = {}
        self.last_update = None
        logger.info(f"[2025-01-29 17:04:43] MarketAnalyzer initialized")
        
    async def analyze_token_market(self, token: TokenMetrics) -> Dict:
        """Pilna token'o rinkos analizė"""
        logger.info(f"[2025-01-29 17:04:43] Starting market analysis for {token.address}")
        
        # Atnaujiname rinkos duomenis
        await self.update_market_data()
        
        # Vykdome visas analizes parallel
        tasks = [
            self.get_market_sentiment(),
            self.analyze_similar_tokens(token),
            self.analyze_sector_performance(token),
            self.analyze_social_metrics(token),
            self.analyze_trading_metrics(token)
        ]
        
        results = await asyncio.gather(*tasks)
        
        analysis = {
            'market_sentiment': results[0],
            'similar_tokens': results[1],
            'sector_performance': results[2],
            'social_metrics': results[3],
            'trading_metrics': results[4],
            'analysis_time': '2025-01-29 17:04:43'
        }
        
        logger.info(f"[2025-01-29 17:04:43] Market analysis completed for {token.address}")
        return analysis
        
    async def update_market_data(self):
        """Atnaujina rinkos duomenis"""
        try:
            logger.info(f"[2025-01-29 17:04:43] Updating market data...")
            
            async with aiohttp.ClientSession() as session:
                # Solana rinkos duomenys
                async with session.get('https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd&include_24hr_vol=true&include_24hr_change=true') as resp:
                    sol_data = await resp.json()
                    logger.debug(f"[2025-01-29 17:04:43] Received Solana data: {sol_data}")
                
                # Fear & Greed Index
                async with session.get('https://api.alternative.me/fng/') as resp:
                    sentiment_data = await resp.json()
                    logger.debug(f"[2025-01-29 17:04:43] Received Fear & Greed Index: {sentiment_data}")
                
                # DEX duomenys (Raydium)
                async with session.get('https://api.raydium.io/v2/main/pool/24h') as resp:
                    dex_data = await resp.json()
                    logger.debug(f"[2025-01-29 17:04:43] Received DEX data")
                
            self.market_data = {
                'sol_price': sol_data['solana']['usd'],
                'sol_volume_24h': sol_data['solana']['usd_24h_vol'],
                'sol_change_24h': sol_data['solana']['usd_24h_change'],
                'fear_greed_index': sentiment_data['data'][0]['value'],
                'dex_volume_24h': sum(pool['volume'] for pool in dex_data),
                'update_time': '2025-01-29 17:04:43'
            }
            
            logger.info(f"[2025-01-29 17:04:43] Market data updated successfully")
            
        except Exception as e:
            logger.error(f"[2025-01-29 17:04:43] Error updating market data: {e}")
            
    async def get_market_sentiment(self) -> Dict:
        """Analizuoja bendrą rinkos sentimentą"""
        logger.info(f"[2025-01-29 17:04:43] Analyzing market sentiment")
        
        sentiment = {
            'overall': self._calculate_overall_sentiment(),
            'sol_momentum': self._calculate_sol_momentum(),
            'market_phase': self._determine_market_phase(),
            'risk_level': self._assess_market_risk()
        }
        
        logger.info(f"[2025-01-29 17:04:43] Market sentiment analysis complete: {sentiment['overall']}")
        return sentiment
        
    async def analyze_similar_tokens(self, token: TokenMetrics) -> List[Dict]:
        """Ieško ir analizuoja panašius tokenus"""
        logger.info(f"[2025-01-29 17:04:43] Finding similar tokens for {token.address}")
        
        similar_tokens = []
        try:
            async with aiohttp.ClientSession() as session:
                # Ieškome tokenų su panašiu market cap ir liquidity
                async with session.get(f'https://public-api.solscan.io/token/holders/{token.address}') as resp:
                    data = await resp.json()
                    
                    for similar in data.get('similar_tokens', []):
                        token_info = {
                            'address': similar['address'],
                            'name': similar['name'],
                            'liquidity': similar['liquidity'],
                            'market_cap': similar['market_cap'],
                            'price_change_24h': similar['price_change_24h'],
                            'correlation': self._calculate_correlation(token, similar)
                        }
                        similar_tokens.append(token_info)
                        logger.debug(f"[2025-01-29 17:04:43] Found similar token: {token_info['name']}")
                        
            logger.info(f"[2025-01-29 17:04:43] Found {len(similar_tokens)} similar tokens")
            
        except Exception as e:
            logger.error(f"[2025-01-29 17:04:43] Error finding similar tokens: {e}")
            
        return similar_tokens
        
    async def analyze_sector_performance(self, token: TokenMetrics) -> Dict:
        """Analizuoja sektoriaus performansą"""
        logger.info(f"[2025-01-29 17:04:43] Analyzing sector performance")
        
        sector = self._determine_token_sector(token)
        
        performance = {
            'sector': sector,
            'avg_volume_24h': self._calculate_sector_volume(sector),
            'avg_price_change': self._calculate_sector_price_change(sector),
            'liquidity_trend': self._analyze_sector_liquidity(sector),
            'market_dominance': self._calculate_sector_dominance(sector),
            'sector_strength': self._evaluate_sector_strength(sector)
        }
        
        logger.info(f"[2025-01-29 17:04:43] Sector analysis complete for {sector}")
        return performance
        
    async def analyze_social_metrics(self, token: TokenMetrics) -> Dict:
        """Analizuoja socialinių tinklų metrikas"""
        logger.info(f"[2025-01-29 17:04:43] Analyzing social metrics for {token.address}")
        
        metrics = {
            'telegram_growth': self._analyze_telegram_growth(token),
            'twitter_engagement': await self._get_twitter_engagement(token),
            'community_score': self._calculate_community_score(token),
            'social_sentiment': await self._analyze_social_sentiment(token)
        }
        
        logger.info(f"[2025-01-29 17:04:43] Social metrics analysis complete")
        return metrics
        
    async def analyze_trading_metrics(self, token: TokenMetrics) -> Dict:
        """Analizuoja prekybos metrikas"""
        logger.info(f"[2025-01-29 17:04:43] Analyzing trading metrics")
        
        metrics = {
            'volume_analysis': self._analyze_volume_pattern(token),
            'price_action': self._analyze_price_action(token),
            'liquidity_health': self._assess_liquidity_health(token),
            'buy_sell_ratio': self._calculate_buy_sell_ratio(token),
            'volatility': self._calculate_volatility(token)
        }
        
        logger.info(f"[2025-01-29 17:04:43] Trading metrics analysis complete")
        return metrics

    def _calculate_overall_sentiment(self) -> str:
        """Apskaičiuoja bendrą rinkos sentimentą"""
        fear_greed = int(self.market_data['fear_greed_index'])
        sol_change = self.market_data['sol_change_24h']
        
        if fear_greed > 70 and sol_change > 5:
            return "VERY_BULLISH"
        elif fear_greed > 50 and sol_change > 0:
            return "BULLISH"
        elif fear_greed < 30 and sol_change < 0:
            return "BEARISH"
        elif fear_greed < 20 and sol_change < -5:
            return "VERY_BEARISH"
        return "NEUTRAL"

    def _calculate_sol_momentum(self) -> str:
        """Skaičiuoja SOL momentum"""
        sol_change = self.market_data['sol_change_24h']
        
        if sol_change > 5:
            return "STRONG_BULLISH"
        elif sol_change > 0:
            return "BULLISH"
        elif sol_change < -5:
            return "STRONG_BEARISH"
        elif sol_change < 0:
            return "BEARISH"
        return "NEUTRAL"

    def _determine_market_phase(self) -> str:
        """Nustato rinkos fazę"""
        if self.market_data['sol_change_24h'] > 0 and self.market_data['fear_greed_index'] > 50:
            return "EXPANSION"
        elif self.market_data['sol_change_24h'] < 0 and self.market_data['fear_greed_index'] < 50:
            return "CONTRACTION"
        return "CONSOLIDATION"

    def _assess_market_risk(self) -> str:
        """Vertina rinkos riziką"""
        fear_greed = int(self.market_data['fear_greed_index'])
        
        if fear_greed < 20:
            return "HIGH"
        elif fear_greed < 40:
            return "MEDIUM"
        elif fear_greed < 60:
            return "LOW"
        return "VERY_LOW"

    def _calculate_correlation(self, token: TokenMetrics, similar: Dict) -> float:
        """Skaičiuoja koreliaciją tarp tokenų"""
        # TODO: Implementuoti koreliacijos skaičiavimą pagal price_change ir volume
        if token.price_change_24h * similar['price_change_24h'] > 0:
            return 0.7
        return 0.3

    def _determine_token_sector(self, token: TokenMetrics) -> str:
        """Nustato token'o sektorių"""
        # TODO: Implementuoti sektoriaus nustatymą pagal token metrikas
        return "UNKNOWN"

    def _calculate_sector_volume(self, sector: str) -> float:
        """Skaičiuoja sektoriaus volume"""
        # TODO: Implementuoti sektoriaus volume skaičiavimą
        return self.market_data.get('dex_volume_24h', 0) / 100

    def _calculate_sector_price_change(self, sector: str) -> float:
        """Skaičiuoja sektoriaus kainų pokytį"""
        # TODO: Implementuoti sektoriaus kainų pokyčio skaičiavimą
        return self.market_data.get('sol_change_24h', 0)

    def _analyze_sector_liquidity(self, sector: str) -> str:
        """Analizuoja sektoriaus likvidumą"""
        # TODO: Implementuoti sektoriaus likvidumo analizę
        return "STABLE"

    def _calculate_sector_dominance(self, sector: str) -> float:
        """Skaičiuoja sektoriaus dominance"""
        # TODO: Implementuoti sektoriaus dominance skaičiavimą
        return 0.1

    def _evaluate_sector_strength(self, sector: str) -> str:
        """Vertina sektoriaus stiprumą"""
        # TODO: Implementuoti sektoriaus stiprumo vertinimą
        return "NEUTRAL"

    def _analyze_telegram_growth(self, token: TokenMetrics) -> Dict:
        """Analizuoja Telegram grupės augimą"""
        social_criteria = Config.GEM_CRITERIA['SOCIAL_METRICS']['TELEGRAM']
        
        growth_rate = 0
        if token.telegram_members and token.telegram_members > social_criteria['MIN_MEMBERS']:
            growth_rate = social_criteria['GROWTH_RATE']
            
        return {
            'growth_rate': growth_rate,
            'activity_score': social_criteria['ACTIVITY_SCORE'],
            'trend': 'GROWING' if growth_rate > 0 else 'STABLE'
        }

    async def _get_twitter_engagement(self, token: TokenMetrics) -> Dict:
        """Gauna Twitter engagement metrikas"""
        social_criteria = Config.GEM_CRITERIA['SOCIAL_METRICS']['TWITTER']
        
        return {
            'engagement_rate': social_criteria['MIN_ENGAGEMENT'] if token.twitter_followers else 0,
            'followers_growth': 0,
            'sentiment': 'NEUTRAL'
        }

    def _calculate_community_score(self, token: TokenMetrics) -> float:
        """Skaičiuoja community score"""
        social_criteria = Config.GEM_CRITERIA['SOCIAL_METRICS']
        
        score = 0
        max_score = 0
        
        if token.telegram_members:
            max_score += 1
            if token.telegram_members >= social_criteria['TELEGRAM']['MIN_MEMBERS']:
                score += 1
                
        if token.twitter_followers:
            max_score += 1
            if token.twitter_followers >= social_criteria['TWITTER']['MIN_FOLLOWERS']:
                score += 1
                
        if token.website_url:
            max_score += 1
            if social_criteria['WEBSITE']['REQUIRED']:
                score += 1
                
        return score / max_score if max_score > 0 else 0

    async def _analyze_social_sentiment(self, token: TokenMetrics) -> str:
        """Analizuoja socialinių tinklų sentimentą"""
        return "NEUTRAL"

    def _analyze_volume_pattern(self, token: TokenMetrics) -> Dict:
        """Analizuoja volume pattern"""
        volume_criteria = Config.GEM_CRITERIA['VOLUME']
        
        volume_ratio = token.volume_24h / token.liquidity if token.liquidity > 0 else 0
        
        pattern = 'ACCUMULATION' if token.volume_24h > volume_criteria['MIN_24H'] else 'LOW'
        strength = 'HIGH' if volume_ratio > volume_criteria['MIN_LIQUIDITY_RATIO'] * 2 else \
                  'MEDIUM' if volume_ratio > volume_criteria['MIN_LIQUIDITY_RATIO'] else 'LOW'
                  
        return {
            'pattern': pattern,
            'strength': strength,
            'trend': 'INCREASING' if token.volume_24h > volume_criteria['MIN_24H'] else 'STABLE',
            'volume_ratio': volume_ratio,
            'analysis_time': "2025-01-29 17:06:48"
        }

    def _analyze_price_action(self, token: TokenMetrics) -> Dict:
        """Analizuoja price action"""
        chart_patterns = Config.TRADING_CRITERIA['CHART_PATTERNS']
        
        current_trend = 'BULLISH' if token.price_change_24h > 0 else 'BEARISH'
        pattern = self._identify_chart_pattern(token)
        
        return {
            'trend': current_trend,
            'pattern': pattern if pattern in chart_patterns['BULLISH'] else 'NO_PATTERN',
            'strength': 'STRONG' if abs(token.price_change_24h) > 10 else 'MEDIUM',
            'analysis_time': "2025-01-29 17:06:48"
        }

    def _assess_liquidity_health(self, token: TokenMetrics) -> Dict:
        """Vertina liquidity health"""
        liquidity_criteria = Config.GEM_CRITERIA['LIQUIDITY']
        
        health_status = 'HEALTHY' if token.liquidity >= liquidity_criteria['MIN'] else 'UNHEALTHY'
        liquidity_ratio = token.liquidity / token.market_cap if token.market_cap > 0 else 0
        
        return {
            'status': health_status,
            'ratio': liquidity_ratio,
            'stability': 'STABLE' if liquidity_ratio >= liquidity_criteria['OPTIMAL_RATIO'] else 'UNSTABLE',
            'sol_liquidity': token.liquidity / self.market_data['sol_price'],
            'analysis_time': "2025-01-29 17:06:48"
        }

    def _calculate_buy_sell_ratio(self, token: TokenMetrics) -> float:
        """Skaičiuoja buy/sell ratio"""
        try:
            # In a real implementation, this would analyze actual buy/sell transactions
            # For now, we'll use a simplified calculation based on price action
            if token.price_change_24h > 0:
                return 1 + (token.price_change_24h / 100)
            else:
                return 1 / (1 + abs(token.price_change_24h / 100))
        except Exception as e:
            logger.error(f"[2025-01-29 17:06:48] Error calculating buy/sell ratio: {e}")
            return 1.0

    def _calculate_volatility(self, token: TokenMetrics) -> float:
        """Skaičiuoja volatility"""
        try:
            if token.price_change_24h is not None:
                raw_volatility = abs(token.price_change_24h) / 100
                # Normalize to a 0-1 scale based on healthy growth parameters
                max_healthy_growth = Config.GEM_CRITERIA['VOLUME']['HEALTHY_GROWTH']['MAX'] / 100
                return min(1.0, raw_volatility / max_healthy_growth)
            return 0.5  # Default medium volatility if no data
        except Exception as e:
            logger.error(f"[2025-01-29 17:06:48] Error calculating volatility: {e}")
            return 0.5

    def _identify_chart_pattern(self, token: TokenMetrics) -> str:
        """Identifikuoja chart pattern"""
        # In a real implementation, this would analyze price history and identify patterns
        # For now, we'll return a simple pattern based on price action
        if token.price_change_24h > 5:
            return 'HIGHER_LOWS'
        elif token.price_change_24h > 0:
            return 'ASCENDING_TRIANGLE'
        else:
            return 'NO_PATTERN'

    
        
class RiskAnalyzer:
    def __init__(self):
        self.risk_history = {}
        logger.info(f"[2025-01-29 17:16:26] RiskAnalyzer initialized")

    async def analyze_risk(self, token: TokenMetrics, market_data: Dict, ml_prediction: Dict) -> Dict:
        """Pilna rizikos analizė"""
        logger.info(f"[2025-01-29 17:16:26] Starting risk analysis for {token.address}")
        
        try:
            # Pagrindinė rizikos analizė
            security_risk = self._analyze_security_risk(token)
            market_risk = self._analyze_market_risk(token, market_data)
            volatility_risk = self._calculate_volatility_risk(token)
            liquidity_risk = self._analyze_liquidity_risk(token)
            
            # Bendras rizikos įvertinimas
            overall_risk = self._calculate_overall_risk(
                security_risk,
                market_risk,
                volatility_risk,
                liquidity_risk,
                ml_prediction
            )
            
            # Stop loss ir take profit levels
            risk_levels = self._calculate_risk_levels(token, overall_risk)
            
            # Position sizing rekomendacijos
            position_size = self._calculate_position_size(token, overall_risk)
            
            analysis = {
                'risk_score': overall_risk['score'],
                'risk_level': overall_risk['level'],
                'stop_loss': risk_levels['stop_loss'],
                'take_profit': risk_levels['take_profit'],
                'max_position_size': position_size,
                'risk_factors': {
                    'security': security_risk,
                    'market': market_risk,
                    'volatility': volatility_risk,
                    'liquidity': liquidity_risk
                },
                'recommendations': self._generate_risk_recommendations(overall_risk)
            }
            
            logger.info(f"[2025-01-29 17:16:26] Risk analysis completed for {token.address}")
            return analysis
            
        except Exception as e:
            logger.error(f"[2025-01-29 17:16:26] Error in risk analysis: {e}")
            return self._generate_default_risk_analysis()

    def _analyze_security_risk(self, token: TokenMetrics) -> Dict:
        """Analizuoja saugumo rizikas"""
        logger.info(f"[2025-01-29 17:16:26] Analyzing security risks")
        
        risks = []
        risk_score = 0
        
        # Contract security
        if token.mint_enabled:
            risks.append("Mint function enabled")
            risk_score += 30
        
        if token.freeze_enabled:
            risks.append("Freeze function enabled")
            risk_score += 20
            
        if token.lp_burnt_percentage < Config.SECURITY_CHECKS['LIQUIDITY_CHECKS']['MIN_LP_TOKENS_BURNT']:
            risks.append(f"Low LP burn: {token.lp_burnt_percentage}%")
            risk_score += 25
            
        # Holder distribution risks
        if token.top_holder_percentage > Config.GEM_CRITERIA['HOLDERS']['MAX_TOP_HOLDER']:
            risks.append(f"High concentration: Top holder has {token.top_holder_percentage}%")
            risk_score += 15
            
        return {
            'score': min(risk_score, 100),
            'risks_identified': risks,
            'severity': self._get_risk_severity(risk_score)
        }

    def _analyze_market_risk(self, token: TokenMetrics, market_data: Dict) -> Dict:
        """Analizuoja rinkos riziką"""
        market_timing = Config.MARKET_ANALYSIS['TIMING']
        
        risk_score = 0
        risks = []
        
        # Market sentiment check
        if market_data['market_sentiment']['overall'] != market_timing['MARKET_SENTIMENT']:
            risk_score += 30
            risks.append("Market sentiment mismatch")
            
        # SOL trend check
        if market_data['market_sentiment']['sol_momentum'] != market_timing['SOL_TREND']:
            risk_score += 20
            risks.append("SOL trend mismatch")
            
        # Sector performance check
        if market_data.get('sector_performance', {}).get('trend') != market_timing['SECTOR_PERFORMANCE']:
            risk_score += 15
            risks.append("Sector performance mismatch")
            
        return {
            'score': risk_score,
            'risks_identified': risks,
            'severity': self._get_risk_severity(risk_score)
        }

    def _calculate_volatility_risk(self, token: TokenMetrics) -> Dict:
        """Skaičiuoja volatility riziką"""
        volume_criteria = Config.GEM_CRITERIA['VOLUME']['HEALTHY_GROWTH']
        
        volatility = abs(token.price_change_24h)
        risk_score = 0
        risks = []
        
        if volatility > volume_criteria['MAX']:
            risk_score = 100
            risks.append(f"Extreme volatility: {volatility}%")
        elif volatility < volume_criteria['MIN']:
            risk_score = 50
            risks.append(f"Low volatility: {volatility}%")
            
        return {
            'score': risk_score,
            'risks_identified': risks,
            'severity': self._get_risk_severity(risk_score),
            'current_volatility': volatility
        }

    def _analyze_liquidity_risk(self, token: TokenMetrics) -> Dict:
        """Analizuoja liquidity riziką"""
        liquidity_criteria = Config.GEM_CRITERIA['LIQUIDITY']
        
        risk_score = 0
        risks = []
        
        # Minimum liquidity check
        if token.liquidity < liquidity_criteria['MIN']:
            risk_score += 50
            risks.append(f"Low liquidity: ${token.liquidity:,.2f}")
            
        # Maximum liquidity check
        if token.liquidity > liquidity_criteria['MAX']:
            risk_score += 20
            risks.append(f"Excessive liquidity: ${token.liquidity:,.2f}")
            
        # Liquidity/MCap ratio check
        ratio = token.liquidity / token.market_cap if token.market_cap > 0 else 0
        if ratio < liquidity_criteria['OPTIMAL_RATIO']:
            risk_score += 30
            risks.append(f"Poor liquidity ratio: {ratio:.2%}")
            
        return {
            'score': risk_score,
            'risks_identified': risks,
            'severity': self._get_risk_severity(risk_score),
            'liquidity_ratio': ratio
        }

    def _calculate_overall_risk(self, security_risk: Dict, market_risk: Dict, 
                              volatility_risk: Dict, liquidity_risk: Dict, 
                              ml_prediction: Dict) -> Dict:
        """Skaičiuoja bendrą rizikos įvertinimą"""
        
        # Risk weights
        weights = {
            'security': 0.35,
            'market': 0.25,
            'volatility': 0.20,
            'liquidity': 0.20
        }
        
        # Calculate weighted risk score
        risk_score = (
            security_risk['score'] * weights['security'] +
            market_risk['score'] * weights['market'] +
            volatility_risk['score'] * weights['volatility'] +
            liquidity_risk['score'] * weights['liquidity']
        )
        
        # Adjust based on ML prediction
        if ml_prediction['success_probability'] < 0.3:
            risk_score *= 1.2
        
        return {
            'score': min(100, risk_score),
            'level': self._get_risk_severity(risk_score),
            'confidence': ml_prediction['confidence_score']
        }

    def _calculate_position_size(self, token: TokenMetrics, risk_assessment: Dict) -> float:
        """Apskaičiuoja rekomenduojamą pozicijos dydį"""
        logger.info(f"[2025-01-29 17:16:26] Calculating position size for {token.address}")
        
        base_position = min(
            token.liquidity * Config.ENTRY_STRATEGIES['POSITION_SIZING']['MAX_POSITION_SIZE'],
            token.market_cap * Config.ENTRY_STRATEGIES['POSITION_SIZING']['MAX_PORTFOLIO_RISK']
        )
        
        # Koreguojame pagal rizikos lygį
        risk_multiplier = {
            'LOW': 1.0,
            'MEDIUM': 0.7,
            'HIGH': 0.4,
            'VERY_HIGH': 0.2
        }.get(risk_assessment['level'], 0.1)
        
        position_size = base_position * risk_multiplier
        
        logger.info(f"[2025-01-29 17:16:26] Calculated position size: ${position_size:.2f}")
        return position_size

    def _calculate_risk_levels(self, token: TokenMetrics, risk_assessment: Dict) -> Dict:
        """Apskaičiuoja stop loss ir take profit lygius"""
        logger.info(f"[2025-01-29 17:16:26] Calculating risk levels")
        
        # Get risk parameters from config
        risk_level = risk_assessment['level'].upper()
        risk_params = Config.RISK_LEVELS.get(risk_level, Config.RISK_LEVELS['MEDIUM'])
        
        current_price = token.price
        stop_loss = current_price * (1 - risk_params['stop_loss'])
        take_profit = current_price * (1 + risk_params['take_profit'])
        
        logger.info(f"[2025-01-29 17:16:26] Risk levels calculated - SL: ${stop_loss:.8f}, TP: ${take_profit:.8f}")
        
        return {
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'risk_reward_ratio': risk_params['take_profit'] / risk_params['stop_loss']
        }

    def _get_risk_severity(self, risk_score: float) -> str:
        """Nustato rizikos lygį pagal score"""
        if risk_score >= 80:
            return "VERY_HIGH"
        elif risk_score >= 60:
            return "HIGH"
        elif risk_score >= 40:
            return "MEDIUM"
        elif risk_score >= 20:
            return "LOW"
        return "VERY_LOW"

    def _generate_default_risk_analysis(self) -> Dict:
        """Generuoja default risk analysis kai nepavyksta gauti duomenų"""
        return {
            'risk_score': 100,
            'risk_level': 'VERY_HIGH',
            'stop_loss': None,
            'take_profit': None,
            'max_position_size': 0,
            'risk_factors': {
                'security': {'score': 100, 'level': 'VERY_HIGH', 'risks_identified': ['DATA_UNAVAILABLE']},
                'market': {'score': 100, 'level': 'VERY_HIGH', 'risks_identified': ['DATA_UNAVAILABLE']},
                'volatility': {'score': 100, 'level': 'VERY_HIGH', 'current_volatility': 0},
                'liquidity': {'score': 100, 'level': 'VERY_HIGH', 'liquidity_ratio': 0}
            },
            'recommendations': ['AVOID - Unable to analyze risks']
        }

    def _generate_risk_recommendations(self, risk_assessment: Dict) -> List[str]:
        """Generuoja risk-based rekomendacijas"""
        recommendations = []
        
        if risk_assessment['level'] == 'VERY_HIGH':
            recommendations.extend([
                "AVOID - Risk level too high",
                "Multiple high-risk factors detected",
                "Not suitable for investment"
            ])
        elif risk_assessment['level'] == 'HIGH':
            recommendations.extend([
                "CAUTION - Use minimum position size",
                "Set tight stop loss",
                f"Maximum position: {Config.RISK_LEVELS['HIGH']['position_size'] * 100}% of portfolio"
            ])
        elif risk_assessment['level'] == 'MEDIUM':
            recommendations.extend([
                "MODERATE - Use scaled entry",
                "Set conservative stop loss",
                f"Maximum position: {Config.RISK_LEVELS['MEDIUM']['position_size'] * 100}% of portfolio"
            ])
        else:
            recommendations.extend([
                "ACCEPTABLE - Standard position sizing",
                f"Maximum position: {Config.RISK_LEVELS['LOW']['position_size'] * 100}% of portfolio",
                "Use normal risk management rules"
            ])
            
        return recommendations

class GemFinder:
    def __init__(self):
        """Inicializuojame GemFinder"""
        self.telegram = TelegramClient('gem_finder_session', 
                                     Config.TELEGRAM_API_ID, 
                                     Config.TELEGRAM_API_HASH)
        self.scanner_client = TelegramClient('scanner_session',
                                           Config.TELEGRAM_API_ID,
                                           Config.TELEGRAM_API_HASH)
        self.ml_analyzer = MLAnalyzer()
        self.market_analyzer = MarketAnalyzer()
        self.risk_analyzer = RiskAnalyzer()
        self.processed_tokens = set()
        self.last_processed_messages = set()
        
        logger.info(f"[2025-01-29 19:06:19] GemFinder initialized")
        
    async def start(self):
        """Paleidžia GemFinder"""
        await self.telegram.start()
        await self.scanner_client.start()
        logger.info(f"[2025-01-29 19:06:19] GemFinder started")
        
        # Užkrauname istorinius duomenis
        self.ml_analyzer.load_historical_data()
        
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
        logger.info(f"[2025-01-29 19:06:19] GemFinder stopped")
        
    async def _handle_message(self, event: events.NewMessage.Event):
        """Apdoroja naują pranešimą"""
        try:
            message = event.message.text
            message_id = event.message.id
            
            if message_id in self.last_processed_messages:
                logger.info(f"[2025-01-29 17:21:51] Message already processed, skipping...")
                return
            
            logger.info(f"[2025-01-29 17:21:51] Processing new message (ID: {message_id})")
            
            # Ieškome token adresų
            token_addresses = self._extract_token_addresses(message)
            
            for token_address in token_addresses:
                if token_address not in self.processed_tokens:
                    logger.info(f"[2025-01-29 17:21:51] New token found: {token_address}")
                    
                    # Renkame token info
                    token_data = await self._collect_token_data(token_address)
                    if not token_data:
                        continue
                        
                    # Analizuojame token'ą
                    analysis = await self._analyze_token(token_data)
                    
                    # Jei token'as atrodo perspektyvus, siunčiame analizę
                    if self._is_potential_gem(analysis):
                        await self._send_analysis(event.message, analysis)
                        self.processed_tokens.add(token_address)
            
            # Pažymime žinutę kaip apdorotą
            self.last_processed_messages.add(message_id)
            
        except Exception as e:
            logger.error(f"[2025-01-29 17:21:51] Error handling message: {e}")

    def _extract_token_addresses(self, message: str) -> List[str]:
        """Ištraukia visus token adresus iš žinutės"""
        matches = []
        
        # Skaidome žinutę į eilutes
        lines = message.split('\n')
        for line in lines:
            # 1. Originalus formatas (🪙 CA: `token`)
            ca_matches = re.findall(r'🪙\s*CA:\s*`([A-Za-z0-9]+)`', line)
            if ca_matches:
                matches.extend(ca_matches)
                
            # 2. Mint: formatas
            mint_matches = re.findall(r'Mint:\s*([A-Za-z0-9]{32,44})', line)
            if mint_matches:
                matches.extend(mint_matches)
            
            # 3. Tiesioginiai token adresai
            direct_matches = re.findall(r'(?:^|\s)[`"\']?([A-Za-z0-9]{32,44})[`"\']?(?:\s|$)', line)
            if direct_matches:
                matches.extend(direct_matches)
                
            # 4. Token adresai iš URL
            cleaned_line = re.sub(r'[*_~`]', '', line)
            if "New" in cleaned_line:
                url_patterns = [
                    r'birdeye\.so/token/([A-Za-z0-9]{32,44})',
                    r'raydium\.io/swap/\?inputCurrency=([A-Za-z0-9]{32,44})',
                    r'dexscreener\.com/solana/([A-Za-z0-9]{32,44})',
                    r'dextools\.io/app/solana/pair-explorer/([A-Za-z0-9]{32,44})',
                    r'gmgn\.ai/sol/token/([A-Za-z0-9]{32,44})',
                    r'soul_sniper_bot\?start=\d+_([A-Za-z0-9]{32,44})',
                    r'soul_scanner_bot/chart\?startapp=([A-Za-z0-9]{32,44})'
                ]
                
                for pattern in url_patterns:
                    url_matches = re.findall(pattern, cleaned_line)
                    if url_matches:
                        matches.extend(url_matches)
        
        # Pašaliname dublikatus ir filtruojame
        unique_matches = list(set(matches))
        valid_matches = [addr for addr in unique_matches if len(addr) >= 32 and len(addr) <= 44]
        
        logger.info(f"[2025-01-29 17:21:51] Found {len(valid_matches)} valid tokens")
        return valid_matches

    

    async def _collect_token_data(self, token_address: str) -> Optional[TokenMetrics]:
        """Renka informaciją apie token'ą iš visų šaltinių"""
        current_time = "2025-01-29 21:58:41"
        current_user = "minijus05"
        
        logger.info(f"{current_time} UTC | INFO | User {current_user}: Collecting data for {token_address}")
        
        try:
            # Siunčiame token'ą į scanner grupę
            original_message = await self.scanner_client.send_message(
                Config.SCANNER_GROUP,
                token_address
            )
            logger.info(f"{current_time} UTC | INFO | User {current_user}: Sent token to scanner group: {token_address}")

            # Laukiame atsakymų iš botų
            timeout = 30
            start_time = time.time()
            last_check_time = 0
            
            soul_data = None
            gmgn_data = None
            
            while time.time() - start_time < timeout:
                current_time = "2025-01-29 21:58:41"  # Atnaujiname laiką kiekvieno ciklo metu
                
                # Tikriname tik kas 2 sekundes
                if time.time() - last_check_time >= 2:
                    last_check_time = time.time()
                    
                    async for message in self.scanner_client.iter_messages(
                        Config.SCANNER_GROUP,
                        limit=20,
                        min_id=original_message.id
                    ):
                        if message.sender_id == 6872314605 and not soul_data:
                            logger.info(f"{current_time} UTC | INFO | User {current_user}: Soul Scanner response received")
                            # Išsaugome žinutės tekstą
                            message_text = message.text
                            logger.info(f"{current_time} UTC | INFO | User {current_user}: Raw Soul Scanner Response:\n{message_text}")
                            
                            soul_data = self.parse_soul_scanner_response(message_text)
                            
                            # Spausdiname Soul Scanner duomenis
                            if soul_data:
                                logger.info(f"{current_time} UTC | INFO | User {current_user}: Soul Scanner data parsed successfully")
                                logger.info(f"{current_time} UTC | INFO | User {current_user}: Soul Scanner Data:")
                                for key, value in sorted(soul_data.items()):
                                    logger.info(f"{current_time} UTC | INFO | User {current_user}: {key}: {value}")
                            
                        elif message.sender_id == 6344329830 and not gmgn_data:
                            logger.info(f"{current_time} UTC | INFO | User {current_user}: GMGN response received")
                            message_text = message.text
                            logger.info(f"{current_time} UTC | INFO | User {current_user}: Raw GMGN Response:\n{message_text}")
                            
                            gmgn_data = self.parse_gmgn_response(message_text)
                            
                            # Spausdiname GMGN duomenis
                            if gmgn_data:
                                logger.info(f"{current_time} UTC | INFO | User {current_user}: GMGN data parsed successfully")
                                logger.info(f"{current_time} UTC | INFO | User {current_user}: GMGN Data:")
                                for key, value in gmgn_data.items():
                                    logger.info(f"{current_time} UTC | INFO | User {current_user}: {key}: {value}")
                        
                        # Jei gavome abu atsakymus IR abu sėkmingai suparsinti
                        if soul_data and gmgn_data:
                            logger.info(f"{current_time} UTC | INFO | User {current_user}: Both responses received and parsed")
                            
                            # Konstruojame TokenMetrics objektą
                            token_data = TokenMetrics(
                                address=token_address,
                                name=soul_data.get('name', 'Unknown').replace('**', '').replace('\u200e', ''),
                                symbol=soul_data.get('symbol', 'Unknown'),
                                creation_date=datetime.now(timezone.utc) - timedelta(hours=int(soul_data.get('age', 0))),
                                price=gmgn_data.get('price', 0.0),
                                market_cap=soul_data.get('market_cap', 0.0),
                                liquidity=soul_data.get('liquidity', 0.0),
                                volume_24h=soul_data.get('volume_24h', 0.0),
                                price_change_24h=soul_data.get('price_change_24h', 0.0),
                                mint_enabled=soul_data.get('mint_enabled', False),
                                freeze_enabled=soul_data.get('freeze_enabled', False),
                                lp_burnt_percentage=soul_data.get('lp_burnt', 0.0),
                                holders_count=soul_data.get('holders_count', 0),
                                top_holder_percentage=soul_data.get('top_holder', 0.0),
                                top_10_holders=gmgn_data.get('top_10_holders', []),
                                sniper_count=soul_data.get('sniper_count', 0),
                                sniper_percentage=soul_data.get('sniper_percentage', 0.0),
                                first_20_fresh=soul_data.get('first_20_fresh', 0),
                                first_70_status=gmgn_data.get('first_70_status', {'current': 0, 'initial': 0}),
                                ath_market_cap=soul_data.get('ath_market_cap', 0.0),
                                ath_multiplier=1.0,  # Bus apskaičiuota žemiau
                                owner_renounced=soul_data.get('dev_token_percentage', 0.0) == 0,
                                telegram_url=soul_data.get('telegram_url'),
                                twitter_url=soul_data.get('twitter_url'),
                                website_url=soul_data.get('website_url'),
                                dev_wallet=soul_data.get('dev_wallet'),
                                dev_sol_balance=soul_data.get('dev_sol_balance', 0.0),
                                dev_token_percentage=soul_data.get('dev_token_percentage', 0.0)
                            )
                            
                            # Apskaičiuojame ATH multiplier
                            if token_data.market_cap > 0 and token_data.ath_market_cap > 0:
                                token_data.ath_multiplier = token_data.ath_market_cap / token_data.market_cap
                            
                            logger.info(f"{current_time} UTC | INFO | User {current_user}: Successfully created TokenMetrics object")
                            
                            # Spausdiname TokenMetrics duomenis
                            for field in fields(token_data):
                                value = getattr(token_data, field.name)
                                logger.info(f"{current_time} UTC | INFO | User {current_user}: {field.name}: {value}")
                            
                            return token_data
                    
                    await asyncio.sleep(2)  # Laukiame 2 sekundes prieš kitą tikrinimą
            
            # Jei neišėjome iš ciklo per return, reiškia negavome visų duomenų
            logger.error(f"{current_time} UTC | ERROR | User {current_user}: Failed to get all responses")
            logger.error(f"{current_time} UTC | ERROR | User {current_user}: Soul Scanner data: {'Received' if soul_data else 'Missing'}")
            logger.error(f"{current_time} UTC | ERROR | User {current_user}: GMGN data: {'Received' if gmgn_data else 'Missing'}")
            return None
            
        except Exception as e:
            logger.error(f"{current_time} UTC | ERROR | User {current_user}: Error collecting token data: {e}")
            logger.error(f"Exception traceback: {e.__traceback__.tb_lineno}")
            return None

    def combine_data(self, soul_data: Dict, gmgn_data: Dict, token_address: str) -> TokenMetrics:
        """Sujungia duomenis iš Soul Scanner ir GMGN į vieną TokenMetrics objektą"""
        try:
            logger.info(f"2025-01-29 21:52:04 UTC | INFO | User minijus05: Combining data from both scanners")
            
            # Sukuriame TokenMetrics objektą, prioritetizuojant Soul Scanner duomenis
            metrics = TokenMetrics(
                address=token_address,
                name=soul_data.get('name', 'Unknown').replace('**', '').replace('\u200e', ''),
                symbol=soul_data.get('symbol', 'Unknown'),
                creation_date=datetime.now(timezone.utc) - timedelta(hours=int(soul_data.get('age', 0) * 24)),  # Soul Scanner age į hours
                price=gmgn_data.get('price', 0.0),  # Tik iš GMGN, nes tikslesnė
                market_cap=soul_data.get('market_cap', 0.0),
                liquidity=soul_data.get('liquidity', 0.0),
                volume_24h=soul_data.get('volume_24h', 0.0),
                price_change_24h=soul_data.get('price_change_24h', 0.0),
                mint_enabled=soul_data.get('mint_enabled', False),
                freeze_enabled=soul_data.get('freeze_enabled', False),
                lp_burnt_percentage=soul_data.get('lp_burnt', 0.0),
                holders_count=soul_data.get('holders_count', 0),
                top_holder_percentage=soul_data.get('top_holder', 0.0),
                top_10_holders=gmgn_data.get('top_10_holders', []),  # Tik iš GMGN
                sniper_count=soul_data.get('sniper_count', 0),
                sniper_percentage=soul_data.get('sniper_percentage', 0.0),
                first_20_fresh=soul_data.get('first_20_fresh', 0),
                first_70_status=gmgn_data.get('first_70_status', {'current': 0, 'initial': 0}),  # Tik iš GMGN
                ath_market_cap=soul_data.get('ath_market_cap', 0.0),
                ath_multiplier=1.0,  # Bus apskaičiuota žemiau
                owner_renounced=soul_data.get('dev_token_percentage', 0.0) == 0,
                telegram_url=soul_data.get('telegram_url'),
                twitter_url=soul_data.get('twitter_url'),
                website_url=soul_data.get('website_url'),
                dev_wallet=soul_data.get('dev_wallet'),
                dev_sol_balance=soul_data.get('dev_sol_balance', 0.0),
                dev_token_percentage=soul_data.get('dev_token_percentage', 0.0)
            )
            
            # Apskaičiuojame ATH multiplier
            if metrics.market_cap > 0 and metrics.ath_market_cap > 0:
                metrics.ath_multiplier = metrics.ath_market_cap / metrics.market_cap
                
            # Loginame sujungtus duomenis
            logger.info(f"2025-01-29 21:52:04 UTC | INFO | User minijus05: Combined TokenMetrics Data:")
            for field in fields(metrics):
                value = getattr(metrics, field.name)
                logger.info(f"2025-01-29 21:52:04 UTC | INFO | User minijus05: {field.name}: {value}")
            
            return metrics
                
        except Exception as e:
            logger.error(f"2025-01-29 21:52:04 UTC | ERROR | User minijus05: Error combining data: {e}")
            raise

    
    async def _get_soul_scanner_data(self, original_message) -> Optional[Dict]:
        """Gauna duomenis iš Soul Scanner boto"""
        try:
            logger.info(f"[2025-01-29 20:26:06] User minijus05: Waiting for Soul Scanner response")
            
            timeout = 30  # Laukimo laikas sekundėmis
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                async for message in self.scanner_client.iter_messages(
                    Config.SCANNER_GROUP,
                    limit=20,
                    min_id=original_message.id
                ):
                    if message.sender_id == Config.SOUL_SCANNER_BOT:
                        logger.info(f"[2025-01-29 20:26:06] User minijus05: Received Soul Scanner response")
                        return self.parse_soul_scanner_response(message.text)
                        
                await asyncio.sleep(1)
                
            logger.warning(f"[2025-01-29 20:26:06] User minijus05: Soul Scanner response timeout")
            return None
                
        except Exception as e:
            logger.error(f"[2025-01-29 20:26:06] User minijus05: Error getting Soul Scanner data: {e}")
            return None

    async def _get_gmgn_data(self, original_message) -> Optional[Dict]:
        """Gauna duomenis iš GMGN boto"""
        try:
            logger.info(f"[2025-01-29 20:26:06] User minijus05: Waiting for GMGN response")
            
            timeout = 30  # Laukimo laikas sekundėmis
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                async for message in self.scanner_client.iter_messages(
                    Config.SCANNER_GROUP,
                    limit=20,
                    min_id=original_message.id
                ):
                    if message.sender_id == Config.GMGN_BOT:
                        logger.info(f"[2025-01-29 20:26:06] User minijus05: Received GMGN response")
                        return self.parse_gmgn_response(message.text)
                        
                await asyncio.sleep(1)
                
            logger.warning(f"[2025-01-29 20:26:06] User minijus05: GMGN response timeout")
            return None
                
        except Exception as e:
            logger.error(f"[2025-01-29 20:26:06] User minijus05: Error getting GMGN data: {e}")
            return None

    def parse_soul_scanner_response(self, text: str) -> Dict:
        """
        Parses SoulScanner response text and returns structured data.
        
        Args:
            text (str): The raw text from SoulScanner response
            
        Returns:
            Dict: Structured data containing all parsed fields
        """
        try:
            current_time = "2025-01-30 08:14:51"
            current_user = "minijus05"
            
            logger.info(f"{current_time} UTC | INFO | User {current_user}: Starting Soul Scanner parse")
            logger.info(f"{current_time} UTC | INFO | User {current_user}: Raw text to parse:\n{text}")
            
            data = {}
            lines = text.split('\n')
            
            # Name and Symbol
            first_line = lines[0] if lines else ""
            if name_match := re.search(r'💠\s*([^•]+)•\s*\$([A-Z0-9]+)', first_line):
                data['name'] = name_match.group(1).strip()
                data['symbol'] = name_match.group(2)
                logger.info(f"{current_time} UTC | INFO | User {current_user}: Found name: {data['name']}, symbol: {data['symbol']}")
            
            # Token Address
            for line in lines:
                if address_match := re.search(r'\n([A-Za-z0-9]{32,})\n', line):
                    data['token_address'] = address_match.group(1)
                    logger.info(f"{current_time} UTC | INFO | User {current_user}: Found address: {data['token_address']}")
                    break
            
            # Market Cap and ATH
            for line in lines:
                if '💰' in line:
                    if mc_match := re.search(r'MC:\s*\$([0-9,.]+)K\s*•\s*🔝\s*\$([0-9,.]+)([KM])', line):
                        data['market_cap'] = float(mc_match.group(1).replace(',', '')) * 1000
                        multiplier = 1000000 if mc_match.group(3) == 'M' else 1000
                        data['ath_market_cap'] = float(mc_match.group(2).replace(',', '')) * multiplier
                        logger.info(f"{current_time} UTC | INFO | User {current_user}: Found market cap: ${data['market_cap']}, ATH: ${data['ath_market_cap']}")
                    break
            
            # Liquidity and SOL pooled
            for line in lines:
                if '💧' in line:
                    if liq_match := re.search(r'Liq:\s*\$([0-9,.]+)K\s*\(([0-9,.]+)\s*SOL\)', line):
                        data['liquidity'] = float(liq_match.group(1).replace(',', '')) * 1000
                        data['sol_pooled'] = float(liq_match.group(2))
                        logger.info(f"{current_time} UTC | INFO | User {current_user}: Found liquidity: ${data['liquidity']}, SOL pooled: {data['sol_pooled']}")
                    break
            
            # Volume (24h)
            for line in lines:
                if 'Vol:' in line and '1d:' in line:
                    if vol_match := re.search(r'1d:\s*\$([0-9,.]+)([KM])', line):
                        amount = float(vol_match.group(1).replace(',', ''))
                        multiplier = 1000000 if vol_match.group(2) == 'M' else 1000
                        data['volume_24h'] = amount * multiplier
                        logger.info(f"{current_time} UTC | INFO | User {current_user}: Found 24h volume: ${data['volume_24h']}")
                    break
            
            # Price Change (24h)
            for line in lines:
                if 'Price:' in line and '1d:' in line:
                    if price_match := re.search(r'1d:\s*([-+]?[0-9.]+)%', line):
                        data['price_change_24h'] = float(price_match.group(1))
                        logger.info(f"{current_time} UTC | INFO | User {current_user}: Found 24h price change: {data['price_change_24h']}%")
                    break
            
            # Age
            for line in lines:
                if '🕒' in line:
                    if age_match := re.search(r'Age:\s*(\d+)(m|h|d)', line):
                        amount = float(age_match.group(1))
                        unit = age_match.group(2)
                        # Convert to hours
                        data['age'] = amount / 60 if unit == 'm' else amount if unit == 'h' else amount * 24
                        logger.info(f"{current_time} UTC | INFO | User {current_user}: Found age: {data['age']} hours")
                    break
            
            # Holders and Top Holder
            for line in lines:
                if 'Hodls' in line:
                    if holders_match := re.search(r'Hodls.*?:\s*([0-9,]+)\s*•\s*Top:\s*([0-9.]+)%', line):
                        data['holders_count'] = int(holders_match.group(1).replace(',', ''))
                        data['top_holder'] = float(holders_match.group(2))
                        logger.info(f"{current_time} UTC | INFO | User {current_user}: Found holders: {data['holders_count']}, top holder: {data['top_holder']}%")
                    break
            
            # LP Status
            data['lp_burnt'] = 100.0 if "100% Burnt" in text else 99.0 if "99% Burnt" in text else 0.0
            logger.info(f"{current_time} UTC | INFO | User {current_user}: Found LP burnt: {data['lp_burnt']}%")
            
            # Mint and Freeze Status
            if 'Mint' in text:
                mint_section = text.split('Mint')[1].split('|')[0]
                data['mint_enabled'] = '🔴' in mint_section
                logger.info(f"{current_time} UTC | INFO | User {current_user}: Mint enabled: {data['mint_enabled']}")
            
            if 'Freeze' in text:
                freeze_section = text.split('Freeze')[1].split('\n')[0]
                data['freeze_enabled'] = '🔴' in freeze_section
                logger.info(f"{current_time} UTC | INFO | User {current_user}: Freeze enabled: {data['freeze_enabled']}")
            
            # Dev info
            if dev_match := re.search(r'Dev.*?:\s*(\d+)\s*SOL\s*\|\s*(\d+)%.*?\nSniped:\s*(\d+)%.*?\nAirdrop:\s*(\d+)%', text, re.DOTALL):
                data['dev_sol_balance'] = float(dev_match.group(1))
                data['dev_token_percentage'] = float(dev_match.group(2))
                data['dev_sniped_percentage'] = float(dev_match.group(3))
                data['dev_airdrop_percentage'] = float(dev_match.group(4))
                logger.info(f"{current_time} UTC | INFO | User {current_user}: Found dev info - SOL: {data['dev_sol_balance']}, Token %: {data['dev_token_percentage']}%")
            
            # Snipers info
            if sniper_match := re.search(r'🔫\s*Snipers:\s*(\d+)\s*•\s*([0-9.]+)%', text):
                data['sniper_count'] = int(sniper_match.group(1))
                data['sniper_percentage'] = float(sniper_match.group(2))
                logger.info(f"{current_time} UTC | INFO | User {current_user}: Found snipers: {data['sniper_count']}, {data['sniper_percentage']}%")
            
            # First 20 info
            if first20_match := re.search(r'First 20.*?:\s*(\d+)\s*Fresh', text):
                data['first_20_fresh'] = int(first20_match.group(1))
                logger.info(f"{current_time} UTC | INFO | User {current_user}: Found fresh wallets: {data['first_20_fresh']}/20")
            
            # Social links
            if 'X (' in text:
                if twitter_match := re.search(r'X \((https://[^)]+)\)', text):
                    data['twitter_url'] = twitter_match.group(1)
                    logger.info(f"{current_time} UTC | INFO | User {current_user}: Found Twitter URL: {data['twitter_url']}")
            
            if 'WEB (' in text:
                if web_match := re.search(r'WEB \((https://[^)]+)\)', text):
                    data['website_url'] = web_match.group(1)
                    logger.info(f"{current_time} UTC | INFO | User {current_user}: Found Website URL: {data['website_url']}")
            
            # Warning flags
            data['warnings'] = []
            
            if 'High Holder' in text:
                data['warnings'].append('high_holder')
            if 'Dev Sniped' in text:
                data['warnings'].append('dev_sniped')
            if 'Abnormal Vol' in text:
                data['warnings'].append('abnormal_volume')
            if 'High Top Ten' in text:
                data['warnings'].append('high_top_ten')
            
            logger.info(f"{current_time} UTC | INFO | User {current_user}: Found {len(data['warnings'])} warnings: {data['warnings']}")
            
            # Final logging
            logger.info(f"{current_time} UTC | INFO | User {current_user}: Parsing completed. Fields parsed: {len(data)}")
            logger.info(f"{current_time} UTC | INFO | User {current_user}: Parsed fields: {list(data.keys())}")
            
            return data
            
        except Exception as e:
            logger.error(f"{current_time} UTC | ERROR | User {current_user}: Error parsing Soul Scanner response: {str(e)}")
            logger.error(f"{current_time} UTC | ERROR | User {current_user}: Error location: {e.__traceback__.tb_lineno}")
            logger.error(f"{current_time} UTC | ERROR | User {current_user}: Raw text that caused error:\n{text}")
            return {}
                    

    def parse_gmgn_response(self, text: str) -> Dict:
        """GMGN boto atsakymo parsinimas"""
        try:
            logger.info(f"[2025-01-29 21:17:19] User minijus05: Parsing GMGN response")
            data = {}
            
            # Market Cap
            if match := re.search(r'MC:\s*\*{0,2}\$([0-9.]+)K\*{0,2}', text):
                data['market_cap'] = float(match.group(1)) * 1000
                
            # Likvidumas ir SOL pooled
            if match := re.search(r'Liq:\s*\*{0,2}\$([0-9.]+)K\*{0,2}\s*/\s*SOL\s*pooled:\s*\*{0,2}([0-9.]+)\*{0,2}', text):
                data['liquidity'] = float(match.group(1)) * 1000
                data['sol_pooled'] = float(match.group(2))
                
            # Price su specialiu formatu $0.0{4}41908
            if match := re.search(r'Price:\s*\*{0,2}\$0\.0{(\d+)}(\d+)\*{0,2}', text):
                zeros = int(match.group(1))
                num = match.group(2)
                data['price'] = float(f"0.{'0' * zeros}{num}")
            
            # Dev info
            if match := re.search(r'Dev current balance:\s*\*{0,2}([0-9.]+)%\*{0,2}', text):
                data['dev_percentage'] = float(match.group(1))
            if match := re.search(r'Dev SOL balance:\s*\*{0,2}([0-9.]+)\s*SOL\*{0,2}', text):
                data['dev_sol'] = float(match.group(1))
                
            # Top10 holding
            if match := re.search(r'Top10 holding:\s*\*{0,2}([0-9.]+)%\*{0,2}', text):
                data['top_10_percentage'] = float(match.group(1))
                
            # First 70 buyers statistika
            if match := re.search(r'Current/Initial:\s*([0-9.]+)%\s*/\s*([0-9.]+)%', text):
                data['first_70_status'] = {
                    'current': float(match.group(1)),
                    'initial': float(match.group(2))
                }
                
            # Social links - saugus patikrinimas
            twitter_match = re.search(r'\[Twitter✅\]\(([^)]+)\)', text)
            if twitter_match:
                data['twitter_url'] = twitter_match.group(1)
                
            telegram_match = re.search(r'\[Telegram✅\]\(([^)]+)\)', text)
            if telegram_match:
                data['telegram_url'] = telegram_match.group(1)
                
            website_match = re.search(r'\[Website✅\]\(([^)]+)\)', text)
            if website_match:
                data['website_url'] = website_match.group(1)
                
            logger.info(f"[2025-01-29 21:17:19] User minijus05: Successfully parsed GMGN data: {data}")
            return data
                
        except Exception as e:
            logger.error(f"[2025-01-29 21:17:19] User minijus05: GMGN parsing error: {e}")
            return {}

    
            
    async def _analyze_token(self, token: TokenMetrics) -> Dict:
            """Atlieka pilną token'o analizę"""
            logger.info(f"[2025-01-29 16:01:47] Starting comprehensive analysis for {token.address}")
            
            try:
                # ML Analysis
                ml_prediction = self.ml_analyzer.predict_success(token)
                logger.info(f"[2025-01-29 16:01:47] ML prediction: {ml_prediction['success_probability']:.2f}")
                
                # Market Analysis
                market_analysis = await self.market_analyzer.analyze_token_market(token)
                logger.info(f"[2025-01-29 16:01:47] Market sentiment: {market_analysis['market_sentiment']['overall']}")
                
                # Risk Analysis
                risk_analysis = await self.risk_analyzer.analyze_risk(token, market_analysis, ml_prediction)
                logger.info(f"[2025-01-29 16:01:47] Risk level: {risk_analysis['risk_level']}")
                
                analysis = {
                    'token_data': token,
                    'ml_prediction': ml_prediction,
                    'market_analysis': market_analysis,
                    'risk_analysis': risk_analysis,
                    'analysis_time': '2025-01-29 16:01:47'
                }
                
                logger.info(f"[2025-01-29 16:01:47] Analysis completed for {token.address}")
                return analysis
                
            except Exception as e:
                logger.error(f"[2025-01-29 16:01:47] Error during token analysis: {e}")
                return None

    def _is_potential_gem(self, analysis: Dict) -> bool:
        """Patikrina ar token'as atitinka GEM kriterijus"""
        if not analysis:
            return False
            
        token = analysis['token_data']
        ml_pred = analysis['ml_prediction']
        risk = analysis['risk_analysis']
        market = analysis['market_analysis']
        
        criteria_met = []
        criteria_failed = []
        
        # Security checks
        if not token.mint_enabled and not token.freeze_enabled:
            criteria_met.append("Security: No mint/freeze ✅")
        else:
            criteria_failed.append("Security: Mint/freeze enabled ❌")
            
        # Liquidity check
        if token.liquidity >= Config.GEM_CRITERIA['LIQUIDITY']['MIN']:
            criteria_met.append(f"Liquidity: ${token.liquidity:,.2f} ✅")
        else:
            criteria_failed.append(f"Liquidity: ${token.liquidity:,.2f} ❌")
            
        # LP burnt check
        if token.lp_burnt_percentage >= Config.MIN_LP_BURNT:
            criteria_met.append(f"LP Burnt: {token.lp_burnt_percentage}% ✅")
        else:
            criteria_failed.append(f"LP Burnt: {token.lp_burnt_percentage}% ❌")
            
        # Holders check
        if token.holders_count >= Config.MIN_HOLDERS:
            criteria_met.append(f"Holders: {token.holders_count} ✅")
        else:
            criteria_failed.append(f"Holders: {token.holders_count} ❌")
            
        # ML prediction check
        if ml_pred['success_probability'] >= Config.MIN_SUCCESS_PROBABILITY:
            criteria_met.append(f"ML Score: {ml_pred['success_probability']:.2f} ✅")
        else:
            criteria_failed.append(f"ML Score: {ml_pred['success_probability']:.2f} ❌")
            
        # Risk level check
        if risk['risk_level'] in ['LOW', 'MEDIUM']:
            criteria_met.append(f"Risk Level: {risk['risk_level']} ✅")
        else:
            criteria_failed.append(f"Risk Level: {risk['risk_level']} ❌")
            
        # Log results
        logger.info(f"[2025-01-29 16:01:47] Gem criteria check for {token.address}:")
        for criterion in criteria_met:
            logger.info(f"[2025-01-29 16:01:47] ✅ {criterion}")
        for criterion in criteria_failed:
            logger.info(f"[2025-01-29 16:01:47] ❌ {criterion}")
            
        # Token qualifies if all main criteria are met
        return len(criteria_failed) == 0

    async def _send_analysis(self, original_message: Message, analysis: Dict):
        """Siunčia analizės rezultatus į destination chat"""
        logger.info(f"[2025-01-29 16:01:47] Preparing to send analysis")
        
        token = analysis['token_data']
        ml_pred = analysis['ml_prediction']
        risk = analysis['risk_analysis']
        market = analysis['market_analysis']
        
        # Formatuojame analizės tekstą
        analysis_text = f"""🔍 GEM Analysis Report
        
💎 Token Info:
├ Name: {token.name}
├ Address: {token.address}
├ Price: ${token.price:.8f}
├ Market Cap: ${token.market_cap:,.2f}
├ Liquidity: ${token.liquidity:,.2f}
└ Age: {self._format_age(token.creation_date)}

🔒 Security:
├ Mint: {'❌' if not token.mint_enabled else '✅'}
├ Freeze: {'❌' if not token.freeze_enabled else '✅'}
├ LP Burnt: {token.lp_burnt_percentage}%
└ Owner: {'Renounced ✅' if token.dev_token_percentage == 0 else f'{token.dev_token_percentage}% ⚠️'}

👥 Holders ({token.holders_count}):
├ Top Holder: {token.top_holder_percentage}%
├ Snipers: {token.sniper_count} ({token.sniper_percentage}%)
└ Fresh Wallets: {token.first_20_fresh}/20

📊 Performance:
├ 24h Volume: ${token.volume_24h:,.2f}
├ 24h Change: {token.price_change_24h:+.2f}%
└ ATH Multiple: {token.ath_multiplier}x

🤖 ML Analysis:
├ Success Probability: {ml_pred['success_probability']:.1%}
├ Confidence: {ml_pred['confidence_score']}
└ Key Factors: {', '.join(ml_pred['key_factors'][:3])}

📈 Market Context:
├ Sentiment: {market['market_sentiment']['overall']}
├ Sector: {market['sector_performance']['sector']}
└ Trend: {market['sector_performance']['trend']}

⚠️ Risk Analysis:
├ Risk Level: {risk['risk_level']}
├ Stop Loss: ${risk['stop_loss']:.8f}
└ Take Profit: ${risk['take_profit']:.8f}

💰 Trade Setup:
├ Position Size: ${risk['max_position_size']:,.2f}
└ Risk/Reward: {risk['risk_factors']['risk_reward_ratio']:.1f}

🔗 Links:
├ Telegram: {token.website_url}
├ Twitter: {token.twitter_followers} followers
└ Website: {token.website_url}"""
        
        try:
            # Siunčiame originalią žinutę ir analizę
            await self.telegram.forward_messages(Config.TELEGRAM_DEST_CHAT, original_message)
            await self.telegram.send_message(Config.TELEGRAM_DEST_CHAT, analysis_text)
            
            logger.info(f"[2025-01-29 16:01:47] Analysis sent successfully")
            
        except Exception as e:
            logger.error(f"[2025-01-29 16:01:47] Error sending analysis: {e}")

    @staticmethod
    def _format_age(creation_date: datetime) -> str:
        """Formatuoja token'o amžių"""
        age = datetime.now(timezone.utc) - creation_date
        if age.days > 0:
            return f"{age.days}d"
        hours = age.seconds // 3600
        return f"{hours}h"

    # Pirma, pakeičiame event loop setup Windows sistemoje:
if sys.platform == 'win32':
    import asyncio
    import nest_asyncio
    from asyncio import WindowsSelectorEventLoopPolicy
    
    asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
    nest_asyncio.apply()

async def main():
    """Main function to run the GemFinder"""
    logger.info(f"[2025-01-29 18:59:03] Starting GemFinder")
    
    try:
        gem_finder = GemFinder()
        await gem_finder.start()
        await gem_finder.process_messages()
    except Exception as e:
        logger.error(f"[2025-01-29 18:59:03] Critical error: {e}")
        raise
    finally:
        await gem_finder.stop()
        logger.info(f"[2025-01-29 18:59:03] GemFinder shutting down")

if __name__ == "__main__":
    asyncio.run(main())
