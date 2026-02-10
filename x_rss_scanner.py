#!/usr/bin/env python3
"""
X/Twitter RSS 扫描器
使用 Nitter 等第三方 RSS 服务获取推文
零成本、无需 API Key
"""

import os
import sys
import json
import logging
import feedparser
import re
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass
import requests
from urllib.parse import urlparse

# 添加项目根目录到路径
sys.path.insert(0, '/Users/januswing/.openclaw/workspace/strategy_miner')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('x_rss_scanner')

@dataclass
class TweetItem:
    """推文数据"""
    author: str
    url: str
    title: str
    content: str
    published_at: str
    source: str = "rss"

# RSS 服务地址（按优先级排序）
RSS_SERVICES = [
    "https://nitter.net/{username}/rss",
    "https://twitrss.me/user/{username}/rss",
    "https://rss.app/feeds/v1.2/{username}.xml",
]

class XRSSScanner:
    """X/Twitter RSS 扫描器"""
    
    def __init__(self, config_file: str = None):
        self.config_file = config_file or '/Users/januswing/.openclaw/workspace/strategy_miner/monitored_accounts.json'
        self.accounts = self._load_accounts()
        
    def _load_accounts(self) -> List[Dict]:
        """加载监控账号配置"""
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
                return data.get('accounts', [])
        except FileNotFoundError:
            logger.warning(f"配置文件不存在: {self.config_file}")
            return []
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return []
    
    def _get_rss_url(self, username: str) -> str:
        """生成 RSS URL"""
        for service in RSS_SERVICES:
            url = service.format(username=username)
            # 检查是否是 Nitter（最可靠）
            if 'nitter.net' in url:
                return url
        return RSS_SERVICES[0].format(username=username)
    
    def check_rss_available(self, username: str) -> bool:
        """检查 RSS 源是否可用"""
        rss_url = self._get_rss_url(username)
        
        try:
            response = requests.get(rss_url, timeout=10)
            if response.status_code == 200 and 'xml' in response.headers.get('content-type', '').lower():
                logger.info(f"✅ RSS 可用: {username} -> {rss_url}")
                return True
            else:
                logger.warning(f"❌ RSS 不可用: {username} (状态码: {response.status_code})")
                return False
        except Exception as e:
            logger.error(f"❌ RSS 检查失败: {username} - {e}")
            return False
    
    def fetch_feed(self, username: str) -> Optional[feedparser.FeedParserDict]:
        """获取 RSS 订阅源"""
        rss_url = self._get_rss_url(username)
        
        try:
            logger.info(f"获取 RSS 源: {rss_url}")
            feed = feedparser.parse(rss_url)
            
            if feed.bozo:
                logger.warning(f"RSS 解析警告: {username} - {feed.bozo_exception}")
            
            if hasattr(feed, 'entries') and len(feed.entries) > 0:
                logger.info(f"✅ 成功获取 {len(feed.entries)} 条推文: {username}")
                return feed
            
            logger.warning(f"⚠️ 无推文数据: {username}")
            return None
            
        except Exception as e:
            logger.error(f"❌ RSS 获取失败: {username} - {e}")
            return None
    
    def _extract_strategy_content(self, content: str, keywords: List[str]) -> Optional[str]:
        """从推文内容中提取策略相关信息"""
        if not keywords:
            return content[:200] if content else None
        
        # 转换为小写进行匹配
        content_lower = content.lower()
        keywords_lower = [k.lower() for k in keywords]
        
        # 检查是否包含策略关键词
        for keyword in keywords_lower:
            if keyword in content_lower:
                # 找到关键词，返回包含关键词的上下文
                idx = content_lower.find(keyword)
                start = max(0, idx - 50)
                end = min(len(content), idx + 100)
                return content[start:end].strip()
        
        return None
    
    def _is_spam_or_promotion(self, content: str) -> bool:
        """检测是否为垃圾广告或推广内容"""
        spam_patterns = [
            r'(?:DM|dm|私信).*?(?:获取|get|领取)',
            r'(?:免费|free).*?(?:赠送|领取|加微信)',
            r'(?:掃碼|扫码|点击链接)',
            r'(?:代币|token).*?(?:发行|launch|发射)',
            r'(?:空投|airdrop).*?(?:领取|claim)',
            r'https?://t\.co/\S+',  # 短链接通常是推广
        ]
        
        for pattern in spam_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False
    
    def _is_retweet(self, content: str) -> bool:
        """检测是否为转发内容"""
        rt_patterns = [
            r'^RT @',
            r'^转发自',
            r'⚠️.*?转发',
        ]
        
        for pattern in rt_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False
    
    def parse_tweets(self, username: str, feed: feedparser.FeedParserDict, strategy_keywords: List[str] = None) -> List[TweetItem]:
        """解析推文并提取策略内容"""
        tweets = []
        
        for entry in feed.entries[:10]:  # 只取最新10条
            # 获取推文内容
            content = entry.get('summary', '') or entry.get('title', '')
            
            # 跳过转发
            if self._is_retweet(content):
                continue
            
            # 跳过垃圾广告
            if self._is_spam_or_promotion(content):
                continue
            
            # 提取策略内容
            if strategy_keywords:
                strategy_content = self._extract_strategy_content(content, strategy_keywords)
                if not strategy_content:
                    continue  # 没有策略相关内容，跳过
            else:
                strategy_content = content[:200]
            
            # 获取发布时间
            published = entry.get('published', datetime.now().isoformat())
            
            # 生成链接
            link = entry.get('link', f'https://twitter.com/{username}/status/unknown')
            
            tweet = TweetItem(
                author=username,
                url=link,
                title=entry.get('title', content[:100]),
                content=content,
                published_at=published,
                source="rss"
            )
            
            tweets.append(tweet)
            logger.info(f"📰 解析推文: {content[:50]}...")
        
        return tweets
    
    def scan_account(self, account: Dict) -> List[TweetItem]:
        """扫描单个账号"""
        username = account.get('username')
        strategy_keywords = account.get('strategy_keywords', [])
        
        if not username:
            return []
        
        logger.info(f"\n{'='*50}")
        logger.info(f"🔍 RSS 扫描账号: @{username}")
        logger.info(f"📊 策略关键词: {strategy_keywords}")
        
        # 检查 RSS 是否可用
        if not self.check_rss_available(username):
            logger.warning(f"⚠️ RSS 不可用，返回 None 以便使用 Playwright")
            return None  # 返回 None 表示需要使用备选方案
        
        # 获取 RSS 源
        feed = self.fetch_feed(username)
        if not feed:
            return None
        
        # 解析推文
        tweets = self.parse_tweets(username, feed, strategy_keywords)
        logger.info(f"✅ 获取 {len(tweets)} 条策略相关推文")
        
        return tweets
    
    def scan_all(self) -> Dict[str, List[TweetItem]]:
        """扫描所有配置账号（只扫描配置为 RSS 的账号）"""
        results = {}
        
        for account in self.accounts:
            source = account.get('source', 'rss')
            
            if source != 'rss':
                logger.info(f"⏭️ 跳过非 RSS 账号: @{account.get('username')} (使用 {source})")
                continue
            
            username = account.get('username')
            tweets = self.scan_account(account)
            
            if tweets:
                results[username] = tweets
            elif tweets is None:
                # RSS 不可用，记录但不让它失败
                results[username] = []
        
        return results

def main():
    """主函数"""
    scanner = XRSSScanner()
    
    print("\n" + "="*60)
    print("🔔 X/Twitter RSS 扫描器")
    print("="*60)
    
    # 测试 RSS 可用性
    for account in scanner.accounts:
        if account.get('source') == 'rss':
            username = account.get('username')
            available = scanner.check_rss_available(username)
            print(f"@{username}: {'✅ RSS 可用' if available else '❌ RSS 不可用'}")
    
    # 执行扫描
    results = scanner.scan_all()
    
    print(f"\n📊 RSS 扫描结果:")
    total_tweets = sum(len(tweets) for tweets in results.values())
    print(f"   总账号数: {len([a for a in scanner.accounts if a.get('source') == 'rss'])}")
    print(f"   策略推文: {total_tweets}")

if __name__ == "__main__":
    main()
