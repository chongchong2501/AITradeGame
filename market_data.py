"""
Market data module - Binance/CoinGecko integration

English: Provides real-time crypto prices with a short cache and robust fallback.
If external APIs fail temporarily, returns the last successful values instead of
resetting to zeros, ensuring data only updates and never clears.

中文：行情数据模块（Binance/CoinGecko）。
提供短周期缓存与稳健回退机制；当外部接口临时失败时，返回上一次成功值，
避免价格被清零，保证数据只会更新不会清零。
"""
import requests
import time
from typing import Dict, List

class MarketDataFetcher:
    """Fetch real-time market data from Binance API (with CoinGecko fallback)

    English: Fetches current prices with a 1-second cache. On failure, falls back
    to CoinGecko and, if that also fails, returns the last cached successful data
    rather than zeros to prevent resets.

    中文：以 1 秒缓存获取当前价格。失败时回退至 CoinGecko；若仍失败，
    优先返回最近一次成功缓存的数据而非零值，防止数据被清零。
    """
    
    def __init__(self):
        self.binance_base_url = "https://api.binance.com/api/v3"
        self.coingecko_base_url = "https://api.coingecko.com/api/v3"
        
        # Binance symbol mapping
        self.binance_symbols = {
            'BTC': 'BTCUSDT',
            'ETH': 'ETHUSDT',
            'SOL': 'SOLUSDT',
            'BNB': 'BNBUSDT',
            'XRP': 'XRPUSDT',
            'DOGE': 'DOGEUSDT'
        }
        
        # CoinGecko mapping for technical indicators
        self.coingecko_mapping = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
            'SOL': 'solana',
            'BNB': 'binancecoin',
            'XRP': 'ripple',
            'DOGE': 'dogecoin'
        }
        
        self._cache = {}
        self._cache_time = {}
        self._last_prices = {}
        self._cache_duration = 1  # Cache for 1 second to meet 1Hz updates
    
    def get_current_prices(self, coins: List[str]) -> Dict[str, float]:
        """Get current prices with 1s cache and resilient fallback

        English: Tries Binance first. If Binance fails, tries CoinGecko.
        If both fail or return empty values, serves last successful cached
        prices to avoid clearing to zero.

        中文：优先使用 Binance；失败则使用 CoinGecko。
        若两者都失败或返回空数据，则返回最近一次成功缓存的结果，
        避免清零。
        """
        # Check cache
        cache_key = 'prices_' + '_'.join(sorted(coins))
        if cache_key in self._cache:
            if time.time() - self._cache_time[cache_key] < self._cache_duration:
                return self._cache[cache_key]
        
        prices = {}
        
        try:
            # Batch fetch Binance 24h ticker data
            symbols = [self.binance_symbols.get(coin) for coin in coins if coin in self.binance_symbols]
            
            if symbols:
                # Build symbols parameter
                symbols_param = '[' + ','.join([f'"{s}"' for s in symbols]) + ']'
                
                response = requests.get(
                    f"{self.binance_base_url}/ticker/24hr",
                    params={'symbols': symbols_param},
                    timeout=5
                )
                response.raise_for_status()
                data = response.json()
                
                # Parse data
                for item in data:
                    symbol = item['symbol']
                    # Find corresponding coin
                    for coin, binance_symbol in self.binance_symbols.items():
                        if binance_symbol == symbol:
                            prices[coin] = {
                                'price': float(item['lastPrice']),
                                'change_24h': float(item['priceChangePercent'])
                            }
                            break
            
            # If some coins are missing from Binance response, try to fill from last cache
            for coin in coins:
                if coin not in prices:
                    last = self._cache.get(cache_key, {}).get(coin)
                    if last:
                        prices[coin] = last

            # Update caches
            self._cache[cache_key] = prices
            self._cache_time[cache_key] = time.time()
            self._last_prices[cache_key] = prices

            return prices
        
        except Exception as e:
            print(f"[ERROR] Binance API failed: {e}")
            # Fallback to CoinGecko
            fallback = self._get_prices_from_coingecko(coins)

            # If CoinGecko returns valid data, cache and return it
            if fallback and any(v.get('price', 0) for v in fallback.values()):
                self._cache[cache_key] = fallback
                self._cache_time[cache_key] = time.time()
                self._last_prices[cache_key] = fallback
                return fallback

            # As a final resort, return last successful cached prices to avoid reset
            if cache_key in self._cache:
                return self._cache[cache_key]

            # No cache available (e.g., first run) — return fallback (likely zeros)
            return fallback
    
    def _get_prices_from_coingecko(self, coins: List[str]) -> Dict[str, float]:
        """Fallback: Fetch prices from CoinGecko"""
        try:
            coin_ids = [self.coingecko_mapping.get(coin, coin.lower()) for coin in coins]
            
            response = requests.get(
                f"{self.coingecko_base_url}/simple/price",
                params={
                    'ids': ','.join(coin_ids),
                    'vs_currencies': 'usd',
                    'include_24hr_change': 'true'
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            prices = {}
            for coin in coins:
                coin_id = self.coingecko_mapping.get(coin, coin.lower())
                if coin_id in data:
                    prices[coin] = {
                        'price': data[coin_id]['usd'],
                        'change_24h': data[coin_id].get('usd_24h_change', 0)
                    }
            
            return prices
        except Exception as e:
            print(f"[ERROR] CoinGecko fallback also failed: {e}")
            return {coin: {'price': 0, 'change_24h': 0} for coin in coins}
    
    def get_market_data(self, coin: str) -> Dict:
        """Get detailed market data from CoinGecko"""
        coin_id = self.coingecko_mapping.get(coin, coin.lower())
        
        try:
            response = requests.get(
                f"{self.coingecko_base_url}/coins/{coin_id}",
                params={'localization': 'false', 'tickers': 'false', 'community_data': 'false'},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            market_data = data.get('market_data', {})
            
            return {
                'current_price': market_data.get('current_price', {}).get('usd', 0),
                'market_cap': market_data.get('market_cap', {}).get('usd', 0),
                'total_volume': market_data.get('total_volume', {}).get('usd', 0),
                'price_change_24h': market_data.get('price_change_percentage_24h', 0),
                'price_change_7d': market_data.get('price_change_percentage_7d', 0),
                'high_24h': market_data.get('high_24h', {}).get('usd', 0),
                'low_24h': market_data.get('low_24h', {}).get('usd', 0),
            }
        except Exception as e:
            print(f"[ERROR] Failed to get market data for {coin}: {e}")
            return {}
    
    def get_historical_prices(self, coin: str, days: int = 7) -> List[Dict]:
        """Get historical prices from CoinGecko"""
        coin_id = self.coingecko_mapping.get(coin, coin.lower())
        
        try:
            response = requests.get(
                f"{self.coingecko_base_url}/coins/{coin_id}/market_chart",
                params={'vs_currency': 'usd', 'days': days},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            prices = []
            for price_data in data.get('prices', []):
                prices.append({
                    'timestamp': price_data[0],
                    'price': price_data[1]
                })
            
            return prices
        except Exception as e:
            print(f"[ERROR] Failed to get historical prices for {coin}: {e}")
            return []
    
    def calculate_technical_indicators(self, coin: str) -> Dict:
        """Calculate technical indicators"""
        historical = self.get_historical_prices(coin, days=14)
        
        if not historical or len(historical) < 14:
            return {}
        
        prices = [p['price'] for p in historical]
        
        # Simple Moving Average
        sma_7 = sum(prices[-7:]) / 7 if len(prices) >= 7 else prices[-1]
        sma_14 = sum(prices[-14:]) / 14 if len(prices) >= 14 else prices[-1]
        
        # Simple RSI calculation
        changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [c if c > 0 else 0 for c in changes]
        losses = [-c if c < 0 else 0 for c in changes]
        
        avg_gain = sum(gains[-14:]) / 14 if gains else 0
        avg_loss = sum(losses[-14:]) / 14 if losses else 0
        
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        return {
            'sma_7': sma_7,
            'sma_14': sma_14,
            'rsi_14': rsi,
            'current_price': prices[-1],
            'price_change_7d': ((prices[-1] - prices[0]) / prices[0]) * 100 if prices[0] > 0 else 0
        }

