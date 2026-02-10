#!/usr/bin/env python3
"""
主调度器
每小时运行雷达扫描，发现新策略后立即触发验证
"""

import os
import sys
import json
import logging
import time
import schedule
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv

# 加载配置
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/januswing/.openclaw/workspace/strategy_miner/logs/scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('scheduler')

# 添加当前目录到路径
sys.path.insert(0, '/Users/januswing/.openclaw/workspace/strategy_miner')

from strategy_radar import StrategyRadar
from strategy_validator import StrategyValidator
from feishu_notify import notify_strategy_passed, notify_scan_stats

class StrategyMiningScheduler:
    """策略挖掘调度器"""
    
    def __init__(self):
        self.radar = StrategyRadar()
        self.validator = StrategyValidator()
        self.strategies_file = '/Users/januswing/.openclaw/workspace/strategy_miner/strategies.json'
        self.is_running = False
    
    def run_radar_scan(self):
        """执行雷达扫描"""
        if self.is_running:
            logger.warning("上一次扫描尚未完成，跳过本次")
            return
        
        self.is_running = True
        logger.info("=" * 60)
        logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始策略雷达扫描...")
        
        try:
            # 1. 执行雷达扫描
            candidates = self.radar.scan_all()
            new_count = len(candidates)
            
            logger.info(f"扫描完成，发现 {new_count} 个新策略候选")
            
            # 2. 通知扫描结果
            stats = {
                'new_candidates': new_count,
                'total_scanned': 0,
                'passed': 0,
                'rejected': 0
            }
            
            # 获取统计数据
            try:
                with open(self.strategies_file, 'r') as f:
                    data = json.load(f)
                    stats['total_scanned'] = data['metadata'].get('total_scanned', 0)
                    stats['passed'] = data['metadata'].get('passed', 0)
                    stats['rejected'] = data['metadata'].get('rejected', 0)
            except:
                pass
            
            notify_scan_stats(stats)
            
            # 3. 对每个新发现的策略进行验证
            passed_strategies = []
            if new_count > 0:
                logger.info("开始验证新发现的策略...")
                
                # 读取最新策略
                with open(self.strategies_file, 'r') as f:
                    data = json.load(f)
                
                for strategy in data['strategies']:
                    if strategy['status'] == 'pending':
                        logger.info(f"验证策略: {strategy['title'][:50]}...")
                        
                        result = self.validator.validate(strategy['id'])
                        
                        if result and result['passed']:
                            passed_strategies.append({
                                'strategy': strategy,
                                'metrics': result['metrics']
                            })
                            
                            # 发送飞书通知
                            notify_strategy_passed(strategy, result['metrics'])
                            
                            logger.info(f"✅ 策略验证通过: {strategy['title'][:50]}...")
                        else:
                            logger.info(f"❌ 策略验证未通过: {strategy['title'][:50]}...")
                        
                        # 避免请求过于频繁
                        time.sleep(1)
            
            logger.info(f"本轮扫描完成: 发现 {new_count} 个, 通过 {len(passed_strategies)} 个")
            
        except Exception as e:
            logger.error(f"雷达扫描异常: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            self.is_running = False
            logger.info("=" * 60)
    
    def run_pending_validations(self):
        """运行所有待验证的策略"""
        logger.info("=" * 60)
        logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始批量验证待处理策略...")
        
        try:
            results = self.validator.validate_pending()
            
            passed_count = sum(1 for r in results if r['passed'])
            
            logger.info(f"批量验证完成: 处理 {len(results)} 个, 通过 {passed_count} 个")
            
            # 通知通过的策略
            for result in results:
                if result['passed']:
                    notify_strategy_passed(result, result['metrics'])
            
        except Exception as e:
            logger.error(f"批量验证异常: {e}")
        
        logger.info("=" * 60)
    
    def start(self):
        """启动调度器"""
        logger.info("=" * 60)
        logger.info("策略挖掘系统启动")
        logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 立即执行一次扫描
        logger.info("执行首次扫描...")
        self.run_radar_scan()
        
        # 设置定时任务
        schedule.every().hour.do(self.run_radar_scan)
        
        # 每天凌晨2点执行一次全面验证
        schedule.every().day.at("02:00").do(self.run_pending_validations)
        
        logger.info("定时任务已设置:")
        logger.info("  - 每小时: 雷达扫描")
        logger.info("  - 每天 02:00: 全面验证")
        logger.info("=" * 60)
        
        # 运行调度器
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    
    def run_once(self):
        """仅运行一次（用于测试）"""
        logger.info("执行单次扫描...")
        self.run_radar_scan()
        
        logger.info("扫描完成")

def main():
    """主入口"""
    # 确保logs目录存在
    os.makedirs('/Users/januswing/.openclaw/workspace/strategy_miner/logs', exist_ok=True)
    
    scheduler = StrategyMiningScheduler()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        # 仅运行一次
        scheduler.run_once()
    else:
        # 启动调度器
        try:
            scheduler.start()
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在停止...")
            sys.exit(0)

if __name__ == "__main__":
    main()
