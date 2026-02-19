#!/usr/bin/env python3
"""
Reddit Scraper - 投资策略发现
从 Reddit 投资相关 subreddits 获取讨论并提取策略
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

import requests
from dotenv import load_dotenv

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent.resolve()))

load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent / 'logs' / 'reddit.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('reddit_scraper')

@dataclass
class RedditPost:
    """Reddit 帖子"""
    id: str
    subreddit: str
    author: str
    title: str
    content: str
    url: str
    score: int
    num_comments: int
    created_at: str

class RedditScraper:
    """Reddit 爬虫"""
    
    def __init__(self):
        self.client_id = os.getenv('REDDIT_CLIENT_ID')
        self.client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        self.user_agent = os.getenv('REDDIT_USER_AGENT', 'StrategyMiner/1.0')
        self.subreddits = [
            'investing',
            'stocks',
            'wallstreetbets',
            'SecurityAnalysis',
            'options',
            'cryptomarkets',
            'CryptoMoonShots',
            'CryptoCurrency',
            'Bitcoin',
            'Trading',
            'Forex',
            'Daytrading'
        ]
        self.base_url = "https://www.reddit.com"
        self.auth = (self.client_id, self.client_secret) if self.client_id else None
        self.headers = {"User-Agent": self.user_agent}
    
    def fetch_posts(self, subreddit: str, sort: str = 'hot', limit: int = 50) -> List[Dict]:
        """获取帖子"""
        if not self.auth:
            logger.warning(f"Reddit API 未配置，跳过 r/{subreddit}")
            return []
        
        try:
            params = {"limit": limit, "sort": sort}
            response = requests.get(
                f"{self.base_url}/r/{subreddit}/{sort}.json",
                headers=self.headers,
                auth=self.auth,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('data', {}).get('children', [])
            elif response.status_code == 401:
                logger.error(f"Reddit API 认证失败")
                return []
            else:
                logger.warning(f"Reddit API 返回状态码: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"获取 r/{subreddit} 失败: {e}")
            return []
    
    def extract_strategy_logic(self, title: str, content: str) -> Optional[str]:
        """从帖子中提取策略逻辑"""
        full_text = f"{title} {content}"
        
        # 策略关键词模式
        strategy_patterns = [
            # 交易条件
            r'(?:buy|long|entry)\s+(?:when|if|on|at|above|over)\s+\S+',
            r'(?:sell|short|exit)\s+(?:when|if|on|at|below|under)\s+\S+',
            r'(?:go|long|open)\s+(?:long|short|position)\s+(?:when|if)\s+\S+',
            
            # 技术指标
            r'(?:ma|moving average|sma|ema)\s*\d*',
            r'\d+[- ]?day\s*(?:ma|moving average|sma|ema)',
            r'(?:golden cross|death cross)',
            r'(?:rsi)\s*(?:below|under|<|above|over|>)\s*\d+',
            r'(?:macd)\s*(?:cross|signal|histogram)',
            r'(?:bollinger|bb)\s*(?:bands?|upper|lower|middle)',
            r'(?:volume)\s*(?:spike|surge|expansion)',
            r'(?:support|resistance|support level|resistance level)',
            r'(?:breakout|breakdown|pullback|reversal)',
            
            # 交易规则
            r'(?:stop[- ]?loss|sl)\s*(?:at|to|-)\s*\d+%',
            r'(?:take[- ]?profit|tp)\s*(?:at|to|-)\s*\d+%',
            r'(?:risk:?|reward:?)\s*\d+[:to]+\d+',
            r'(?:position\s*size|size)\s*(?:\d+%|\d+[- ]?percent)',
            
            # 策略类型
            r'(?:momentum|trend[- ]?following|mean[- ]?reversion)',
            r'(?:scalping|swing\s*trading|day\s*trading)',
            r'(?:value\s*investing|growth\s*investing)',
            r'(?:options?\s*(?:strategy|play|call|put))',
            r'(?:straddle|strangle|iron\s*condor|butterfly)',
            
            # 量化规则
            r'(?:backtest|back[- ]?test)\s*(?:showed|revealed|indicated)',
            r'(?:win\s*rate|winning\s*percentage)\s*(?:\d+%|≥|>=)',
            r'(?:profit\s*factor|expectancy)',
            r'(?:indicator|signal|trigger)',
            
            # 具体数值
            r'\d+%\s*(?:gain|profit|return|move|up|down|rally|dip)',
            r'(?:until|until\s*then|then)',
        ]
        
        for pattern in strategy_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                # 获取上下文
                start = max(0, match.start() - 50)
                end = min(len(full_text), match.end() + 80)
                context = full_text[start:end].strip()
                
                # 清理格式
                context = re.sub(r'\s+', ' ', context)
                
                # 如果上下文太短或太长，尝试扩展
                if len(context) < 20:
                    continue
                
                logger.info(f"  提取到策略逻辑: {context[:100]}...")
                return context
        
        return None
    
    def contains_strategy_keywords(self, title: str, content: str) -> bool:
        """检查是否包含策略关键词"""
        keywords = [
            'strategy', 'method', 'approach', 'technique',
            'setup', 'pattern', 'trade', 'trading',
            'indicator', 'signal', 'system',
            'buy when', 'sell when', 'long when', 'short when',
            'entry', 'exit', 'position',
            'backtest', 'results', 'performance',
            'winning', 'profit', 'roi',
            'moving average', 'rsi', 'macd', 'bollinger',
            'stop loss', 'take profit', 'risk reward',
        ]
        
        text = f"{title} {content}".lower()
        matches = sum(1 for kw in keywords if kw in text)
        return matches >= 2  # 至少匹配2个关键词
    
    def analyze_post(self, post_data: Dict) -> Optional[Dict]:
        """分析单个帖子"""
        post = post_data.get('data', {})
        
        title = post.get('title', '')
        content = post.get('selftext', '')
        score = post.get('score', 0)
        num_comments = post.get('num_comments', 0)
        
        # 过滤低质量帖子
        if score < 10:
            return None
        
        if not self.contains_strategy_keywords(title, content):
            return None
        
        # 提取策略逻辑
        logic = self.extract_strategy_logic(title, content)
        
        if not logic:
            return None
        
        return {
            'id': post.get('id'),
            'subreddit': post.get('subreddit', '').replace('r/', ''),
            'author': post.get('author', 'unknown'),
            'title': title[:200],
            'content': f"{title} {content}",
            'url': f"https://reddit.com{post.get('permalink', '')}",
            'score': score,
            'num_comments': num_comments,
            'created_at': datetime.fromtimestamp(post.get('created_utc', 0)).isoformat(),
            'extracted_logic': logic
        }
    
    def scan_subreddit(self, subreddit: str) -> List[Dict]:
        """扫描单个 subreddit"""
        logger.info(f"📺 扫描 r/{subreddit}...")
        
        all_posts = []
        
        # 获取热门帖子
        posts = self.fetch_posts(subreddit, sort='hot', limit=50)
        all_posts.extend(posts)
        
        # 获取新帖子
        posts = self.fetch_posts(subreddit, sort='new', limit=50)
        all_posts.extend(posts)
        
        # 去重
        seen_ids = set()
        unique_posts = []
        for post in all_posts:
            post_id = post.get('data', {}).get('id')
            if post_id and post_id not in seen_ids:
                seen_ids.add(post_id)
                unique_posts.append(post)
        
        logger.info(f"  找到 {len(unique_posts)} 个唯一帖子")
        
        # 分析每个帖子
        strategies = []
        for post in unique_posts:
            analysis = self.analyze_post(post)
            if analysis:
                strategies.append(analysis)
                logger.info(f"  ✅ 发现策略: {analysis['title'][:60]}...")
        
        logger.info(f"  从 r/{subreddit} 发现 {len(strategies)} 个策略")
        return strategies
    
    def scan_all(self) -> List[Dict]:
        """扫描所有 subreddit"""
        logger.info("=" * 60)
        logger.info("🚀 开始 Reddit 策略扫描...")
        logger.info(f"目标 subreddits: {', '.join(self.subreddits)}")
        logger.info("=" * 60)
        
        all_strategies = []
        
        for subreddit in self.subreddits:
            try:
                strategies = self.scan_subreddit(subreddit)
                all_strategies.extend(strategies)
            except Exception as e:
                logger.error(f"扫描 r/{subreddit} 失败: {e}")
        
        # 去重（基于 extracted_logic）
        seen_logics = set()
        unique_strategies = []
        for s in all_strategies:
            logic_key = s['extracted_logic'][:100].lower()
            if logic_key not in seen_logics:
                seen_logics.add(logic_key)
                unique_strategies.append(s)
        
        logger.info("\n" + "=" * 60)
        logger.info(f"📊 Reddit 扫描完成")
        logger.info(f"   总发现: {len(all_strategies)}")
        logger.info(f"   去重后: {len(unique_strategies)}")
        logger.info("=" * 60)
        
        return unique_strategies
    
    def save_strategies(self, strategies: List[Dict]):
        """保存策略到 strategies.json"""
        strategies_file = Path(__file__).parent / 'strategies.json'
        
        try:
            with open(strategies_file, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {"strategies": [], "metadata": {
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "total_scanned": 0,
                "passed": 0,
                "rejected": 0
            }}
        
        existing_urls = {s.get('url') for s in data['strategies']}
        added_count = 0
        
        for strategy in strategies:
            if strategy['url'] in existing_urls:
                continue
            
            new_strategy = {
                'id': len(data['strategies']) + 1,
                'source': 'reddit',
                'author': strategy['author'],
                'url': strategy['url'],
                'title': strategy['title'],
                'content': strategy['content'],
                'extracted_logic': strategy['extracted_logic'],
                'discovered_at': strategy['created_at'],
                'validated_at': None,
                'status': 'pending',
                'backtest_result': None,
                'keywords': [strategy['subreddit']],
                'data_source': 'reddit',
                'score': strategy['score'],
                'num_comments': strategy['num_comments']
            }
            
            data['strategies'].append(new_strategy)
            data['metadata']['total_scanned'] += 1
            data['metadata']['last_updated'] = datetime.now().isoformat()
            added_count += 1
        
        with open(strategies_file, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 保存了 {added_count} 个新策略到 {strategies_file}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Reddit Strategy Scraper')
    parser.add_argument('--subreddit', '-s', type=str, help='Specific subreddit to scan')
    parser.add_argument('--output', '-o', type=str, default='strategies.json', 
                       help='Output file path')
    args = parser.parse_args()
    
    # 确保logs目录存在
    os.makedirs(Path(__file__).parent / 'logs', exist_ok=True)
    
    scraper = RedditScraper()
    
    if args.subreddit:
        # 扫描单个 subreddit
        strategies = scraper.scan_subreddit(args.subreddit)
    else:
        # 扫描所有
        strategies = scraper.scan_all()
    
    # 保存
    scraper.save_strategies(strategies)
    
    # 显示结果
    print(f"\n📈 发现 {len(strategies)} 个策略:")
    for i, s in enumerate(strategies[:10], 1):
        print(f"{i}. [{s['subreddit']}] {s['title'][:60]}...")
        print(f"   逻辑: {s['extracted_logic'][:80]}...")
    
    if len(strategies) > 10:
        print(f"... 还有 {len(strategies) - 10} 个策略")


if __name__ == "__main__":
    main()
