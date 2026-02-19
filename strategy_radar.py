#!/usr/bin/env python3
"""
策略雷达监控模块
整合 RSS 和 Playwright 实现零成本的 X/Twitter 数据采集
"""

import os
from pathlib import Path
import sys
import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional, Union
from dataclasses import dataclass, asdict
import requests
from dotenv import load_dotenv

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent.resolve()))

# 导入新模块
try:
    from x_rss_scanner import XRSSScanner, TweetItem as RSSTweet
    from x_playwright_scraper import XPlaywrightScraper, TweetItem as PWTweet
    RSS_AVAILABLE = True
except ImportError as e:
    RSS_AVAILABLE = False
    logger.warning(f"新模块导入失败: {e}")

# 加载配置
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent / 'logs' / 'radar.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('strategy_radar')

@dataclass
class StrategyCandidate:
    """策略候选"""
    source: str  # 来源：twitter_rss/twitter_playwright/reddit
    author: str  # 作者
    url: str  # 原文链接
    title: str  # 标题
    content: str  # 原始内容
    extracted_logic: str  # 提取的策略逻辑
    discovered_at: str
    keywords: List[str]
    data_source: str = "rss"  # 数据源类型

class StrategyRadar:
    """策略雷达主类"""
    
    def __init__(self):
        self.config_file = Path(__file__).parent / 'monitored_accounts.json'
        self.strategies_file = Path(__file__).parent / 'strategies.json'
        self.rss_scanner = None
        self.playwright_scraper = None
        
        # 初始化扫描器
        if RSS_AVAILABLE:
            try:
                self.rss_scanner = XRSSScanner(self.config_file)
                logger.info("✅ RSS 扫描器已初始化")
            except Exception as e:
                logger.error(f"❌ RSS 扫描器初始化失败: {e}")
            
            try:
                self.playwright_scraper = XPlaywrightScraper(self.config_file)
                logger.info("✅ Playwright 抓取器已初始化")
            except Exception as e:
                logger.error(f"❌ Playwright 抓取器初始化失败: {e}")
        else:
            logger.warning("⚠️ 新扫描模块不可用，使用传统方式")
        
        # 传统 Reddit 扫描器
        self.reddit_scanner = RedditScanner()
    
    def _extract_strategy_logic(self, content: str) -> Optional[str]:
        """从内容中提取策略逻辑"""
        # 策略关键词模式
        strategy_patterns = [
            r'(?:buy|long|sell|short)\s+(?:when|if|on|at)\s+\S+',
            r'(?:moving average|ma|ema|sma)\s*\d*',
            r'(?:rsi|macd|bollinger|support|resistance)',
            r'(?:stop[- ]?loss|take[- ]?profit|tp|sl)',
            r'(?:breakout|pullback|reversal)',
            r'(?:entry|exit|target|setup)',
            r'(?:long\s+(?:position|entry)|short\s+(?:position|entry))',
            r'\d+%\s*(?:gain|profit|return|move)',
        ]
        
        for pattern in strategy_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                # 获取上下文
                start = max(0, match.start() - 30)
                end = min(len(content), match.end() + 50)
                return content[start:end].strip()
        
        return content[:100] if content else None
    
    def _convert_rss_tweet(self, tweet: RSSTweet) -> StrategyCandidate:
        """转换 RSS 推文为策略候选"""
        return StrategyCandidate(
            source="twitter_rss",
            author=tweet.author,
            url=tweet.url,
            title=tweet.title,
            content=tweet.content,
            extracted_logic=self._extract_strategy_logic(tweet.content),
            discovered_at=datetime.now().isoformat(),
            keywords=[],
            data_source="rss"
        )
    
    def _convert_pw_tweet(self, tweet: PWTweet) -> StrategyCandidate:
        """转换 Playwright 推文为策略候选"""
        return StrategyCandidate(
            source="twitter_playwright",
            author=tweet.author,
            url=tweet.url,
            title=tweet.title,
            content=tweet.content,
            extracted_logic=self._extract_strategy_logic(tweet.content),
            discovered_at=datetime.now().isoformat(),
            keywords=[],
            data_source="playwright"
        )
    
    def scan_via_rss(self) -> List[StrategyCandidate]:
        """通过 RSS 扫描"""
        if not self.rss_scanner:
            logger.warning("RSS 扫描器不可用")
            return []
        
        try:
            results = self.rss_scanner.scan_all()
            candidates = []
            
            for username, tweets in results.items():
                for tweet in tweets:
                    candidate = self._convert_rss_tweet(tweet)
                    if candidate.extracted_logic:
                        candidates.append(candidate)
                        logger.info(f"📰 RSS 发现策略: @{username} - {candidate.extracted_logic[:50]}...")
            
            logger.info(f"✅ RSS 扫描完成，发现 {len(candidates)} 个策略")
            return candidates
            
        except Exception as e:
            logger.error(f"❌ RSS 扫描失败: {e}")
            return []
    
    def scan_via_playwright(self) -> List[StrategyCandidate]:
        """通过 Playwright 扫描"""
        if not self.playwright_scraper:
            logger.warning("Playwright 抓取器不可用")
            return []
        
        try:
            results = self.playwright_scraper.scan_all()
            candidates = []
            
            for username, tweets in results.items():
                for tweet in tweets:
                    candidate = self._convert_pw_tweet(tweet)
                    if candidate.extracted_logic:
                        candidates.append(candidate)
                        logger.info(f"📰 Playwright 发现策略: @{username} - {candidate.extracted_logic[:50]}...")
            
            logger.info(f"✅ Playwright 扫描完成，发现 {len(candidates)} 个策略")
            return candidates
            
        except Exception as e:
            logger.error(f"❌ Playwright 扫描失败: {e}")
            return []
    
    def load_existing_strategies(self) -> set:
        """加载已存在的策略URL"""
        try:
            with open(self.strategies_file, 'r') as f:
                data = json.load(f)
                return {s.get('url') for s in data.get('strategies', [])}
        except FileNotFoundError:
            return set()
    
    def save_strategy_candidate(self, candidate: StrategyCandidate):
        """保存策略候选到待验证列表"""
        try:
            # 读取现有数据
            with open(self.strategies_file, 'r') as f:
                data = json.load(f)
            
            # 检查是否已存在
            for strategy in data['strategies']:
                if strategy.get('url') == candidate.url:
                    logger.info(f"策略已存在，跳过: {candidate.url}")
                    return
            
            # 添加新策略
            new_strategy = {
                'id': len(data['strategies']) + 1,
                'source': candidate.source,
                'author': candidate.author,
                'url': candidate.url,
                'title': candidate.title,
                'content': candidate.content,
                'extracted_logic': candidate.extracted_logic,
                'discovered_at': candidate.discovered_at,
                'validated_at': None,
                'status': 'pending',  # pending, passed, rejected
                'backtest_result': None,
                'keywords': candidate.keywords,
                'data_source': candidate.data_source
            }
            
            data['strategies'].append(new_strategy)
            data['metadata']['total_scanned'] += 1
            data['metadata']['last_updated'] = datetime.now().isoformat()
            data['metadata']['sources_used'].append(candidate.source) if candidate.source not in data['metadata']['sources_used'] else None
            
            # 保存
            with open(self.strategies_file, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 策略已保存: {candidate.title}")
            
        except Exception as e:
            logger.error(f"❌ 保存策略失败: {e}")
    
    def scan_all(self) -> List[StrategyCandidate]:
        """执行全量扫描（RSS + Playwright）"""
        logger.info("=" * 60)
        logger.info("🚀 开始策略雷达扫描（零成本方案）...")
        logger.info("=" * 60)
        
        all_candidates = []
        existing_urls = self.load_existing_strategies()
        
        # 1. RSS 扫描（优先，更轻量）
        logger.info("\n📡 阶段 1: RSS 扫描...")
        rss_candidates = self.scan_via_rss()
        for candidate in rss_candidates:
            if candidate.url not in existing_urls:
                all_candidates.append(candidate)
        
        # 2. Playwright 扫描（针对无 RSS 的账号）
        logger.info("\n🌐 阶段 2: Playwright 扫描...")
        pw_candidates = self.scan_via_playwright()
        for candidate in pw_candidates:
            if candidate.url not in existing_urls:
                all_candidates.append(candidate)
        
        # 3. Reddit 扫描（传统方式）
        logger.info("\n📺 阶段 3: Reddit 扫描...")
        reddit_candidates = self.reddit_scanner.scan()
        for candidate in reddit_candidates:
            if candidate.url not in existing_urls:
                all_candidates.append(candidate)
        
        # 保存新发现的策略
        for candidate in all_candidates:
            self.save_strategy_candidate(candidate)
        
        logger.info("\n" + "=" * 60)
        logger.info(f"📊 扫描完成")
        logger.info(f"   RSS 策略: {len(rss_candidates)}")
        logger.info(f"   Playwright 策略: {len(pw_candidates)}")
        logger.info(f"   Reddit 策略: {len(reddit_candidates)}")
        logger.info(f"   新策略总数: {len(all_candidates)}")
        logger.info("=" * 60)
        
        return all_candidates
    
    def get_source_stats(self) -> Dict:
        """获取数据源统计"""
        stats = {
            "rss_accounts": 0,
            "playwright_accounts": 0,
            "total_accounts": 0
        }
        
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
                accounts = data.get('accounts', [])
                
                stats["total_accounts"] = len(accounts)
                stats["rss_accounts"] = len([a for a in accounts if a.get('source') == 'rss'])
                stats["playwright_accounts"] = len([a for a in accounts if a.get('source') == 'playwright'])
                
        except Exception as e:
            logger.error(f"获取统计失败: {e}")
        
        return stats


class RedditScanner:
    """Reddit 扫描器（传统方式，保留备用）"""
    
    def __init__(self):
        self.client_id = os.getenv('REDDIT_CLIENT_ID')
        self.client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        self.user_agent = os.getenv('REDDIT_USER_AGENT', 'StrategyMiner')
        self.subreddits = ['CryptoMoonShots', 'CryptoCurrency', 'Bitcoin', 'ethfinance']
        self.base_url = "https://www.reddit.com"
    
    def fetch_hot_posts(self, subreddit: str) -> List[Dict]:
        """获取热门帖子"""
        if not self.client_id:
            logger.warning("Reddit API 未配置，跳过")
            return []
        
        try:
            headers = {"User-Agent": self.user_agent}
            auth = (self.client_id, self.client_secret)
            params = {"limit": 20, "sort": "hot"}
            
            response = requests.get(
                f"{self.base_url}/r/{subreddit}/new.json",
                headers=headers, auth=auth, params=params, timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get('data', {}).get('children', [])
            return []
            
        except Exception as e:
            logger.error(f"Reddit 获取失败: {e}")
            return []
    
    def extract_strategy_logic(self, post: Dict) -> Optional[str]:
        """从帖子中提取策略逻辑"""
        title = post.get('title', '')
        self_text = post.get('selftext', '')
        full_text = f"{title} {self_text}"
        
        strategy_patterns = [
            r'(?:buy|long|sell|short)\s+(?:when|if|on|at)\s+\S+',
            r'(?:moving average|ma|ema|sma|rsi|macd|bollinger)',
            r'(?:stop[- ]?loss|take[- ]?profit|tp|sl)',
            r'(?:strategy|method|approach|technique)',
            r'\d+%\s*(?:gain|profit|return|stop)',
        ]
        
        for pattern in strategy_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                start = max(0, match.start() - 30)
                end = min(len(full_text), match.end() + 50)
                return full_text[start:end].strip()
        
        return None
    
    def scan(self) -> List[StrategyCandidate]:
        """执行扫描"""
        candidates = []
        
        for subreddit in self.subreddits:
            logger.info(f"扫描 Reddit: r/{subreddit}")
            posts = self.fetch_hot_posts(subreddit)
            
            for post in posts:
                post_data = post.get('data', {})
                logic = self.extract_strategy_logic(post_data)
                
                if logic:
                    candidate = StrategyCandidate(
                        source="reddit",
                        author=post_data.get('author', 'unknown'),
                        url=f"https://reddit.com{post_data.get('permalink', '')}",
                        title=post_data.get('title', '')[:100],
                        content=f"{post_data.get('title', '')} {post_data.get('selftext', '')}",
                        extracted_logic=logic,
                        discovered_at=datetime.now().isoformat(),
                        keywords=[subreddit],
                        data_source="reddit"
                    )
                    candidates.append(candidate)
        
        logger.info(f"Reddit 扫描完成，发现 {len(candidates)} 个策略")
        return candidates


if __name__ == "__main__":
    # 确保logs目录存在
    os.makedirs(Path(__file__).parent / 'logs', exist_ok=True)
    
    radar = StrategyRadar()
    
    # 显示数据源统计
    stats = radar.get_source_stats()
    print("\n" + "="*60)
    print("🔔 策略雷达（零成本数据采集方案）")
    print("="*60)
    print(f"📊 数据源统计:")
    print(f"   RSS 账号: {stats['rss_accounts']}")
    print(f"   Playwright 账号: {stats['playwright_accounts']}")
    print(f"   总计: {stats['total_accounts']}")
    
    # 执行扫描
    candidates = radar.scan_all()
    
    print(f"\n📈 发现 {len(candidates)} 个新策略候选:")
    for i, c in enumerate(candidates[:5], 1):  # 只显示前5个
        print(f"{i}. [{c.source}] @{c.author}")
        print(f"   逻辑: {c.extracted_logic[:80]}...")
    
    if len(candidates) > 5:
        print(f"... 还有 {len(candidates) - 5} 个策略")
