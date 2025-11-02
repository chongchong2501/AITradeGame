"""
AI Trader module

English: This module defines the AITrader class which is responsible for
building prompts, calling the LLM provider via OpenAI-compatible API, and
parsing the response into structured trading decisions.

中文：该模块定义 AITrader 类，负责构建提示词、通过 OpenAI 兼容 API
调用大模型，并将模型响应解析为结构化的交易决策。
"""

import json
from typing import Dict
from openai import OpenAI, APIConnectionError, APIError

class AITrader:
    """
    English: AITrader encapsulates prompt building, LLM invocation, and
    response parsing for trading decisions.

    中文：AITrader 封装了提示构建、LLM 调用与响应解析，用于生成交易决策。
    """

    def __init__(self, api_key: str, api_url: str, model_name: str):
        """
        English: Initialize the AI trader.
        - api_key: API key for the provider
        - api_url: Base URL for the provider (OpenAI-compatible)
        - model_name: Model identifier

        中文：初始化 AI 交易器。
        - api_key：提供方的 API 密钥
        - api_url：OpenAI 兼容的基础地址
        - model_name：模型名称
        """
        self.api_key = api_key
        self.api_url = api_url
        self.model_name = model_name
        # Keep the last raw response from LLM for conversation display
        # 保存最近一次 LLM 原始响应，用于会话展示
        self.last_raw_response: str = ""
    
    def make_decision(self, market_state: Dict, portfolio: Dict, 
                     account_info: Dict) -> Dict:
        """
        English: Build a prompt from market/portfolio/account info, call the LLM,
        parse its response, and return structured decisions.

        中文：基于市场/持仓/账户信息构建提示，调用 LLM，解析响应并返回结构化决策。
        """
        prompt = self._build_prompt(market_state, portfolio, account_info)
        
        response = self._call_llm(prompt)
        
        decisions = self._parse_response(response)
        
        return decisions
    
    def _build_prompt(self, market_state: Dict, portfolio: Dict, 
                     account_info: Dict) -> str:
        prompt = f"""You are a professional cryptocurrency trader. Analyze the market and make trading decisions.

MARKET DATA:
"""
        for coin, data in market_state.items():
            prompt += f"{coin}: ${data['price']:.2f} ({data['change_24h']:+.2f}%)\n"
            if 'indicators' in data and data['indicators']:
                indicators = data['indicators']
                prompt += f"  SMA7: ${indicators.get('sma_7', 0):.2f}, SMA14: ${indicators.get('sma_14', 0):.2f}, RSI: {indicators.get('rsi_14', 0):.1f}\n"
        
        prompt += f"""
ACCOUNT STATUS:
- Initial Capital: ${account_info['initial_capital']:.2f}
- Total Value: ${portfolio['total_value']:.2f}
- Cash: ${portfolio['cash']:.2f}
- Total Return: {account_info['total_return']:.2f}%

CURRENT POSITIONS:
"""
        if portfolio['positions']:
            for pos in portfolio['positions']:
                prompt += f"- {pos['coin']} {pos['side']}: {pos['quantity']:.4f} @ ${pos['avg_price']:.2f} ({pos['leverage']}x)\n"
        else:
            prompt += "None\n"
        
        prompt += """
TRADING RULES:
1. Signals: buy_to_enter (long), sell_to_enter (short), close_position, hold
2. Risk Management:
   - Max 3 positions
   - Risk 1-5% per trade
   - Use appropriate leverage (1-20x)
3. Position Sizing:
   - Conservative: 1-2% risk
   - Moderate: 2-4% risk
   - Aggressive: 4-5% risk
4. Exit Strategy:
   - Close losing positions quickly
   - Let winners run
   - Use technical indicators

OUTPUT FORMAT (JSON only):
```json
{
  "COIN": {
    "signal": "buy_to_enter|sell_to_enter|hold|close_position",
    "quantity": 0.5,
    "leverage": 10,
    "profit_target": 45000.0,
    "stop_loss": 42000.0,
    "confidence": 0.75,
    "justification": "Brief reason"
  }
}
```

Analyze and output JSON only.
"""
        
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """
        English: Invoke the LLM with the given prompt and return the raw
        message content. Also stores the raw content for later use.

        中文：用给定提示调用大模型，返回原始消息内容，并缓存该内容供后续使用。
        """
        try:
            base_url = self.api_url.rstrip('/')
            if not base_url.endswith('/v1'):
                if '/v1' in base_url:
                    base_url = base_url.split('/v1')[0] + '/v1'
                else:
                    base_url = base_url + '/v1'
            
            client = OpenAI(
                api_key=self.api_key,
                base_url=base_url
            )
            
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional cryptocurrency trader. Output JSON format only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            # Cache raw content for conversation display
            # 缓存原始内容用于会话展示
            self.last_raw_response = content or ""
            return content
            
        except APIConnectionError as e:
            error_msg = f"API connection failed: {str(e)}"
            print(f"[ERROR] {error_msg}")
            raise Exception(error_msg)
        except APIError as e:
            error_msg = f"API error ({e.status_code}): {e.message}"
            print(f"[ERROR] {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"LLM call failed: {str(e)}"
            print(f"[ERROR] {error_msg}")
            import traceback
            print(traceback.format_exc())
            raise Exception(error_msg)
    
    def _parse_response(self, response: str) -> Dict:
        """
        English: Extract JSON content (supporting fenced code blocks) and parse
        into a Python dict of decisions. Returns {} if parsing fails.

        中文：提取 JSON 内容（支持代码块围栏），解析为 Python 字典的决策。
        若解析失败则返回 {}。
        """
        response = response.strip()
        
        if '```json' in response:
            response = response.split('```json')[1].split('```')[0]
        elif '```' in response:
            response = response.split('```')[1].split('```')[0]
        
        try:
            decisions = json.loads(response.strip())
            return decisions
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON parse failed: {e}")
            print(f"[DATA] Response:\n{response}")
            return {}
