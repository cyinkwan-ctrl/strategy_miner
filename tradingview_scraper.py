#!/usr/bin/env python3
"""
TradingView 策略爬虫
从TradingView公开页面抓取Pinescript策略
"""

import os
import sys
import json
import re
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
import requests
from bs4 import BeautifulSoup

# 配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/januswing/.openclaw/workspace/strategy_miner/logs/tradingview.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('tradingview')


@dataclass
class TradingViewStrategy:
    """TradingView策略"""
    id: str
    title: str
    url: str
    author: str
    description: str
    pinescript_code: Optional[str] = None
    published_at: str = ""
    views: int = 0
    likes: int = 0


class TradingViewScraper:
    """TradingView爬虫"""

    BASE_URL = "https://www.tradingview.com"
    SCRIPTS_URL = f"{BASE_URL}/scripts/"

    # User-Agent模拟浏览器
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def fetch_scripts_page(self, page: int = 1) -> Optional[str]:
        """获取策略列表页面"""
        url = f"{self.SCRIPTS_URL}?sort=recently_published&page={page}"

        try:
            logger.info(f"请求: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"获取页面失败: {e}")
            return None

    def parse_scripts_page(self, html: str) -> List[Dict]:
        """解析策略列表页面"""
        soup = BeautifulSoup(html, 'html.parser')

        strategies = []

        # 查找策略卡片 - TradingView页面结构
        # 注意：实际结构可能变化，需要根据实际页面调整
        cards = soup.find_all('div', class_=re.compile(r'tv-card|script-card', re.I))

        logger.info(f"找到 {len(cards)} 个策略卡片")

        for card in cards:
            try:
                strategy = self._parse_card(card)
                if strategy:
                    strategies.append(strategy)
            except Exception as e:
                logger.warning(f"解析策略卡片失败: {e}")
                continue

        return strategies

    def _parse_card(self, card) -> Optional[Dict]:
        """解析单个策略卡片"""
        # 提取链接和标题
        link = card.find('a', href=True)
        if not link:
            return None

        url = self.BASE_URL + link['href']
        title = link.get_text(strip=True)

        if not title or 'script' not in url.lower():
            return None

        # 提取作者
        author_elem = card.find('a', class_=re.compile(r'author|username', re.I))
        author = author_elem.get_text(strip=True) if author_elem else "Unknown"

        # 提取描述
        desc_elem = card.find('div', class_=re.compile(r'description|summary', re.I))
        description = desc_elem.get_text(strip=True) if desc_elem else ""

        # 提取统计信息
        views_elem = card.find('span', class_=re.compile(r'view', re.I))
        views = self._extract_number(views_elem) if views_elem else 0

        likes_elem = card.find('span', class_=re.compile(r'like|recommend', re.I))
        likes = self._extract_number(likes_elem) if likes_elem else 0

        return {
            'id': self._generate_id(url),
            'title': title,
            'url': url,
            'author': author,
            'description': description[:500],
            'views': views,
            'likes': likes,
            'source': 'tradingview',
            'discovered_at': datetime.now().isoformat(),
        }

    def _extract_number(self, elem) -> int:
        """从元素提取数字"""
        if elem:
            text = elem.get_text(strip=True)
            match = re.search(r'[\d,]+', text)
            if match:
                return int(match.group().replace(',', ''))
        return 0

    def _generate_id(self, url: str) -> str:
        """从URL生成ID"""
        match = re.search(r'/([a-zA-Z0-9-]+)/$', url)
        if match:
            return f"tv_{match.group(1)}"
        return f"tv_{hash(url) % 100000}"

    def fetch_script_details(self, url: str) -> Optional[Dict]:
        """获取单个策略的详细信息"""
        try:
            logger.info(f"获取策略详情: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # 提取Pinescript代码
            script_elem = soup.find('script', type='text/pine-script') or \
                         soup.find('code', class_='pinescript')

            pinescript = ""
            if script_elem:
                pinescript = script_elem.get_text(strip=True)

            # 提取完整描述
            desc_elem = soup.find('div', class_=re.compile(r'description|about', re.I))
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            return {
                'pinescript_code': pinescript,
                'description': description,
            }

        except Exception as e:
            logger.error(f"获取策略详情失败: {url}, {e}")
            return None

    def discover(self, max_pages: int = 3) -> List[Dict]:
        """发现新策略"""
        all_strategies = []

        for page in range(1, max_pages + 1):
            logger.info(f"扫描第 {page}/{max_pages} 页...")

            html = self.fetch_scripts_page(page)
            if not html:
                break

            strategies = self.parse_scripts_page(html)
            all_strategies.extend(strategies)

            # 礼貌性延迟
            time.sleep(1)

        logger.info(f"发现 {len(all_strategies)} 个策略")
        return all_strategies


def main():
    """主函数"""
    scraper = TradingViewScraper()

    # 发现策略
    strategies = scraper.discover(max_pages=2)

    # 输出结果
    print(f"\n发现 {len(strategies)} 个TradingView策略:")
    for s in strategies[:10]:  # 显示前10个
        print(f"\n- {s['title']}")
        print(f"  作者: {s['author']}")
        print(f"  链接: {s['url']}")
        print(f"  描述: {s['description'][:100]}...")

    # 保存到文件
    output_file = '/Users/januswing/.openclaw/workspace/strategy_miner/tradingview_strategies.json'
    with open(output_file, 'w') as f:
        json.dump(strategies, f, indent=2, ensure_ascii=False)

    print(f"\n已保存到: {output_file}")


if __name__ == '__main__':
    main()
