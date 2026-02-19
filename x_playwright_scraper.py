#!/usr/bin/env python3
"""
X/Twitter Playwright 抓取器
模拟真实浏览器抓取推文（针对无 RSS 的账号）
零成本、使用 nitter.net 作为备选
"""

import os
from pathlib import Path
import sys
import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass
from playwright.sync_api import sync_playwright

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.resolve()))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('x_playwright_scraper')

@dataclass
class TweetItem:
    """推文数据"""
    author: str
    url: str
    title: str
    content: str
    published_at: str
    source: str = "playwright"

# Nitter 实例列表（按优先级）
NITTER_INSTANCES = [
    "nitter.net",
    "nitter.privacydev.net",
    "nitter.poast.org",
    "nitter.moomoo.me",
    "nitter.tedomum.net",
]

class XPlaywrightScraper:
    """X/Twitter Playwright 抓取器"""
    
    def __init__(self, config_file: str = None):
        self.config_file = config_file or Path(__file__).parent / 'monitored_accounts.json'
        self.accounts = self._load_accounts()
        self.browser = None
        self.context = None
    
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
    
    def _get_nitter_url(self, username: str) -> str:
        """获取 Nitter URL"""
        # 使用第一个可用的 Nitter 实例
        instance = NITTER_INSTANCES[0]
        return f"https://{instance}/{username}"
    
    def _init_browser(self):
        """初始化浏览器"""
        if self.browser:
            return
        
        logger.info("🚀 启动 Playwright 浏览器...")
        
        playwright = sync_playwright().start()
        
        # 启动无头浏览器
        self.browser = playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--window-size=1920,1080',
                '--start-maximized',
            ]
        )
        
        # 创建浏览器上下文
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
        )
        
        self.playwright = playwright
        logger.info("✅ Playwright 浏览器已启动")
    
    def _close_browser(self):
        """关闭浏览器"""
        if self.browser:
            self.browser.close()
            self.playwright.stop()
            self.browser = None
            self.context = None
            logger.info("🔒 Playwright 浏览器已关闭")
    
    def _check_page_loaded(self, page) -> bool:
        """检查页面是否加载完成"""
        try:
            # 等待页面完全加载
            page.wait_for_load_state('networkidle', timeout=10000)
            return True
        except Exception as e:
            logger.warning(f"页面加载超时: {e}")
            return False
    
    def _extract_tweets_from_nitter(self, page) -> List[Dict]:
        """从 Nitter 页面提取推文"""
        tweets = []
        
        try:
            # 使用多种选择器尝试提取推文
            selectors = [
                '.timeline-item',  # Nitter 经典选择器
                '.tweet',          # 通用选择器
                '[class*="tweet"]',  # 包含 tweet 的元素
                'article',         # HTML5 article
            ]
            
            tweet_elements = []
            for selector in selectors:
                elements = page.query_selector_all(selector)
                if elements:
                    tweet_elements = elements
                    logger.info(f"使用选择器 '{selector}' 找到 {len(elements)} 个推文元素")
                    break
            
            for element in tweet_elements[:10]:  # 只取最新10条
                try:
                    # 提取推文内容
                    content_elem = element.query_selector('.tweet-content, .tweet-text, [class*="content"]')
                    content = content_elem.inner_text() if content_elem else element.inner_text()
                    
                    # 提取时间
                    time_elem = element.query_selector('.tweet-date, [class*="date"], time')
                    time_str = time_elem.get_attribute('title') or time_elem.inner_text() if time_elem else datetime.now().isoformat()
                    
                    # 提取链接
                    link_elem = element.query_selector('a.tweet-link, [href*="/status/"]')
                    link = link_elem.get_attribute('href') if link_elem else ''
                    if link and not link.startswith('http'):
                        link = f"https://nitter.net{link}"
                    
                    # 清理内容
                    content = content.strip()[:500] if content else ''
                    
                    if content and len(content) > 10:
                        tweets.append({
                            'content': content,
                            'time': time_str,
                            'link': link or 'https://nitter.net/unknown',
                        })
                        
                except Exception as e:
                    logger.debug(f"提取单个推文失败: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"提取推文失败: {e}")
        
        return tweets
    
    def _is_spam_or_promotion(self, content: str) -> bool:
        """检测是否为垃圾广告或推广内容"""
        spam_patterns = [
            r'(?:DM|dm|私信).*?(?:获取|get|领取)',
            r'(?:免费|free).*?(?:赠送|领取|加微信)',
            r'(?:掃碼|扫码|点击链接)',
            r'(?:代币|token).*?(?:发行|launch|发射)',
            r'(?:空投|airdrop).*?(?:领取|claim)',
            r'https?://t\.co/\S+',  # 短链接
            r'(?:加微信|wechat|微信)',
            r'(?:邀请码|referral).*?(?:免费|free)',
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
            r'^⚠️.*?转发',
            r'^MT @',
        ]
        
        for pattern in rt_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False
    
    def _extract_strategy_content(self, content: str, keywords: List[str]) -> Optional[str]:
        """从推文内容中提取策略相关信息"""
        if not keywords:
            return content[:200] if content else None
        
        content_lower = content.lower()
        keywords_lower = [k.lower() for k in keywords]
        
        for keyword in keywords_lower:
            if keyword in content_lower:
                idx = content_lower.find(keyword)
                start = max(0, idx - 50)
                end = min(len(content), idx + 100)
                return content[start:end].strip()
        
        return None
    
    def fetch_tweets_via_nitter(self, username: str, strategy_keywords: List[str] = None) -> List[TweetItem]:
        """通过 Nitter 获取推文"""
        tweets = []
        nitter_url = self._get_nitter_url(username)
        
        logger.info(f"🌐 访问 Nitter: {nitter_url}")
        
        try:
            self._init_browser()
            page = self.context.new_page()
            
            # 模拟真实访问
            page.goto(nitter_url, wait_until='networkidle')
            
            # 等待页面加载
            if not self._check_page_loaded(page):
                logger.warning(f"页面加载不完整: {username}")
                return []
            
            # 随机延迟，模拟真实用户
            import time
            time.sleep(2)
            
            # 提取推文
            raw_tweets = self._extract_tweets_from_nitter(page)
            
            for raw in raw_tweets:
                content = raw.get('content', '')
                
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
                        continue
                else:
                    strategy_content = content[:200]
                
                tweet = TweetItem(
                    author=username,
                    url=raw.get('link', f'https://nitter.net/{username}'),
                    title=content[:100],
                    content=content,
                    published_at=raw.get('time', datetime.now().isoformat()),
                    source="playwright"
                )
                
                tweets.append(tweet)
                logger.info(f"📰 提取推文: {content[:50]}...")
            
            page.close()
            
        except Exception as e:
            logger.error(f"❌ Nitter 抓取失败: {username} - {e}")
        
        return tweets
    
    def fetch_tweets_via_web(self, username: str, strategy_keywords: List[str] = None) -> List[TweetItem]:
        """备用方案：直接通过 requests 获取网页"""
        logger.info(f"🌐 使用 requests 备用方案: @{username}")
        
        try:
            import requests
            from bs4 import BeautifulSoup
            
            nitter_url = self._get_nitter_url(username)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.get(nitter_url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"请求失败: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            tweet_elements = soup.select('.timeline-item, .tweet')[:10]
            
            tweets = []
            for elem in tweet_elements:
                try:
                    content_elem = elem.select_one('.tweet-content, .tweet-text')
                    content = content_elem.get_text(strip=True) if content_elem else ''
                    
                    if content and not self._is_retweet(content) and not self._is_spam_or_promotion(content):
                        if strategy_keywords:
                            strategy_content = self._extract_strategy_content(content, strategy_keywords)
                            if not strategy_content:
                                continue
                        else:
                            strategy_content = content[:200]
                        
                        tweets.append(TweetItem(
                            author=username,
                            url=f"https://nitter.net/{username}",
                            title=content[:100],
                            content=content,
                            published_at=datetime.now().isoformat(),
                            source="playwright"
                        ))
                except Exception:
                    continue
            
            return tweets
            
        except ImportError:
            logger.warning("BeautifulSoup 不可用，跳过备用方案")
            return []
        except Exception as e:
            logger.error(f"备用方案失败: {e}")
            return []
    
    def scan_account(self, account: Dict) -> List[TweetItem]:
        """扫描单个账号"""
        username = account.get('username')
        strategy_keywords = account.get('strategy_keywords', [])
        
        if not username:
            return []
        
        logger.info(f"\n{'='*50}")
        logger.info(f"🔍 Playwright 扫描账号: @{username}")
        logger.info(f"📊 策略关键词: {strategy_keywords}")
        
        # 优先使用 Nitter（通过 Playwright）
        tweets = self.fetch_tweets_via_nitter(username, strategy_keywords)
        
        if not tweets:
            # 备用：使用 requests
            logger.info("🔄 尝试备用方案...")
            tweets = self.fetch_tweets_via_web(username, strategy_keywords)
        
        logger.info(f"✅ 获取 {len(tweets)} 条策略相关推文")
        return tweets
    
    def scan_all(self) -> Dict[str, List[TweetItem]]:
        """扫描所有配置账号（只扫描配置为 Playwright 的账号）"""
        results = {}
        
        try:
            for account in self.accounts:
                source = account.get('source', 'playwright')
                
                if source != 'playwright':
                    logger.info(f"⏭️ 跳过非 Playwright 账号: @{account.get('username')} (使用 {source})")
                    continue
                
                username = account.get('username')
                tweets = self.scan_account(account)
                
                if tweets:
                    results[username] = tweets
                
        finally:
            self._close_browser()
        
        return results

def main():
    """主函数"""
    scraper = XPlaywrightScraper()
    
    print("\n" + "="*60)
    print("🔔 X/Twitter Playwright 抓取器")
    print("="*60)
    
    # 执行扫描
    results = scraper.scan_all()
    
    print(f"\n📊 Playwright 扫描结果:")
    total_tweets = sum(len(tweets) for tweets in results.values())
    print(f"   总账号数: {len([a for a in scraper.accounts if a.get('source') == 'playwright'])}")
    print(f"   策略推文: {total_tweets}")
    
    return results

if __name__ == "__main__":
    main()
