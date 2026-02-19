#!/usr/bin/env python3
"""
飞书通知模块
当策略验证通过时发送飞书消息
"""

import os
from pathlib import Path
import sys
import json
import logging
import requests
from datetime import datetime
from typing import Dict, Optional
from dotenv import load_dotenv

# 加载配置
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent / 'logs' / 'feishu.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('feishu_notify')

class FeishuNotifier:
    """飞书通知器"""
    
    def __init__(self):
        self.app_id = os.getenv('FEISHU_APP_ID')
        self.app_secret = os.getenv('FEISHU_APP_SECRET')
        self.receiver_user_id = os.getenv('FEISHU_RECEIVER_USER_ID')
        self.base_url = "https://open.feishu.cn/open-apis"
        self.access_token = None
        self.token_expires_at = None
    
    def get_access_token(self) -> Optional[str]:
        """获取访问令牌"""
        # 检查缓存的token是否有效
        if self.access_token and self.token_expires_at:
            if datetime.now().timestamp() < self.token_expires_at:
                return self.access_token
        
        if not self.app_id or not self.app_secret:
            logger.warning("飞书 APP 配置未完成")
            return None
        
        try:
            url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
            headers = {"Content-Type": "application/json; charset=utf-8"}
            data = {
                "app_id": self.app_id,
                "app_secret": self.app_secret
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    self.access_token = result['tenant_access_token']
                    # 提前5分钟刷新token
                    self.token_expires_at = datetime.now().timestamp() + result.get('expire', 7200) - 300
                    logger.info("飞书 access_token 获取成功")
                    return self.access_token
                else:
                    logger.error(f"获取 access_token 失败: {result}")
            else:
                logger.error(f"HTTP 错误: {response.status_code}")
                
        except Exception as e:
            logger.error(f"获取 access_token 异常: {e}")
        
        return None
    
    def send_message(self, user_id: str, message: Dict) -> bool:
        """发送消息给用户"""
        access_token = self.get_access_token()
        if not access_token:
            return False
        
        try:
            url = f"{self.base_url}/im/v1/messages"
            params = {"receive_id_type": "open_id"}
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=utf-8"
            }
            
            data = {
                "receive_id": user_id,
                "msg_type": "interactive",
                "card": {
                    "config": {
                        "wide_screen_mode": True,
                        "enable_forward": True
                    },
                    "elements": self._build_card_elements(message)
                }
            }
            
            response = requests.post(url, params=params, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    logger.info("飞书消息发送成功")
                    return True
                else:
                    logger.error(f"发送消息失败: {result}")
            else:
                logger.error(f"HTTP 错误: {response.status_code}")
                
        except Exception as e:
            logger.error(f"发送消息异常: {e}")
        
        return False
    
    def _build_card_elements(self, message: Dict) -> list:
        """构建消息卡片元素"""
        elements = []
        
        # 标题
        elements.append({
            "tag": "div",
            "text": {
                "tag": "plain_text",
                "content": message.get('title', '策略验证通知')
            },
            "extra": {
                "tag": "icon",
                "img": "https://sf3-scmcdn2-sg.ibytedtos.com/goofy/lark/op/open_api/icon/DEFAULT_ID/strategy.png"
            }
        })
        
        # 分隔线
        elements.append({"tag": "hr"})
        
        # 策略信息
        strategy = message.get('strategy', {})
        
        elements.append({
            "tag": "div",
            "fields": [
                {
                    "is_short": True,
                    "text": {"tag": "lark_md", "content": f"**📊 策略标题**\n{strategy.get('title', 'N/A')}"}
                },
                {
                    "is_short": True,
                    "text": {"tag": "lark_md", "content": f"**👤 来源**\n{strategy.get('author', 'N/A')}"}
                },
                {
                    "is_short": True,
                    "text": {"tag": "lark_md", "content": f"**📈 年化收益**\n{message.get('annual_return', 0)}%"}
                },
                {
                    "is_short": True,
                    "text": {"tag": "lark_md", "content": f"**📉 最大回撤**\n{message.get('max_drawdown', 0)}%"}
                },
                {
                    "is_short": True,
                    "text": {"tag": "lark_md", "content": f"**🎯 胜率**\n{message.get('win_rate', 0)}%"}
                },
                {
                    "is_short": True,
                    "text": {"tag": "lark_md", "content": f"**📝 交易数**\n{message.get('total_trades', 0)}"}
                }
            ]
        })
        
        # 分隔线
        elements.append({"tag": "hr"})
        
        # 策略逻辑
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**🔍 策略逻辑**\n{strategy.get('extracted_logic', 'N/A')}"
            }
        })
        
        # 原文链接
        if strategy.get('url'):
            elements.append({
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "📎 查看原文"},
                        "type": "primary",
                        "url": strategy['url']
                    }
                ]
            })
        
        # 时间信息
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"\n⏰ 验证时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
        })
        
        return elements
    
    def notify_strategy_passed(self, strategy: Dict, metrics: Dict):
        """通知策略验证通过"""
        message = {
            'title': '✅ 策略验证通过',
            'strategy': strategy,
            **metrics
        }
        
        if self.receiver_user_id:
            return self.send_message(self.receiver_user_id, message)
        else:
            logger.info(f"策略通过验证: {strategy.get('title')}")
            logger.info(f"年化收益: {metrics.get('annual_return')}%, "
                       f"最大回撤: {metrics.get('max_drawdown')}%, "
                       f"胜率: {metrics.get('win_rate')}%")
            return True
    
    def notify_scan_complete(self, stats: Dict):
        """通知扫描完成"""
        message = {
            'title': '🔍 策略雷达扫描完成',
            'strategy': {
                'title': '扫描统计',
                'author': 'System'
            },
            'annual_return': stats.get('new_candidates', 0),
            'max_drawdown': stats.get('passed', 0),
            'win_rate': stats.get('rejected', 0),
            'total_trades': stats.get('total_scanned', 0)
        }
        
        # 特殊格式化
        message['title'] = f"📊 扫描完成: 发现 {stats.get('new_candidates', 0)} 个新策略"
        
        if self.receiver_user_id:
            return self.send_message(self.receiver_user_id, message)
        else:
            logger.info(f"扫描完成: 发现 {stats.get('new_candidates', 0)} 个新策略")
            return True

def notify(strategy: Dict, metrics: Dict):
    """便捷函数：发送策略通过通知"""
    notifier = FeishuNotifier()
    return notifier.notify_strategy_passed(strategy, metrics)

def notify_scan_stats(stats: Dict):
    """便捷函数：发送扫描统计通知"""
    notifier = FeishuNotifier()
    return notifier.notify_scan_complete(stats)

if __name__ == "__main__":
    # 确保logs目录存在
    os.makedirs(Path(__file__).parent / 'logs', exist_ok=True)
    
    # 测试发送
    notifier = FeishuNotifier()
    
    # 测试策略通知
    test_strategy = {
        'title': 'MA交叉策略',
        'author': '@trader123',
        'url': 'https://twitter.com/user/status/123',
        'extracted_logic': 'When 10-day MA crosses above 20-day MA, buy. Set 5% stop loss.'
    }
    
    test_metrics = {
        'annual_return': 15.5,
        'max_drawdown': 8.2,
        'win_rate': 62.3,
        'total_trades': 150
    }
    
    if notifier.notify_strategy_passed(test_strategy, test_metrics):
        print("✅ 飞书通知测试成功")
        sys.exit(0)
    else:
        print("❌ 飞书通知测试失败 (可能是配置未完成)")
        sys.exit(1)
