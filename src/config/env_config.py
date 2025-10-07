#!/usr/bin/env python3
"""
环境变量配置加载器
支持从 .env 文件加载配置参数，并提供默认值
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta


def load_env_file(env_file_path: str = None) -> Dict[str, str]:
    """
    加载 .env 文件
    
    Args:
        env_file_path: .env 文件路径，如果为None则在项目根目录查找
    
    Returns:
        环境变量字典
    """
    env_vars = {}
    
    # 确定 .env 文件路径
    if env_file_path is None:
        # 在项目根目录查找
        project_root = Path(__file__).parent.parent.parent
        env_file_path = project_root / ".env"
    else:
        env_file_path = Path(env_file_path)
    
    # 如果文件存在则加载
    if env_file_path.exists():
        try:
            with open(env_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释行
                    if not line or line.startswith('#'):
                        continue
                    
                    # 解析键值对
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # 移除引号
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        
                        env_vars[key] = value
        except Exception as e:
            print(f"⚠️ 加载 .env 文件失败: {e}")
    
    return env_vars


def get_env_value(key: str, default: Any = None, value_type: type = str, env_vars: Dict[str, str] = None) -> Any:
    """
    获取环境变量值，支持类型转换
    
    Args:
        key: 环境变量名
        default: 默认值
        value_type: 期望的数据类型
        env_vars: 环境变量字典，如果为None则从系统环境变量获取
    
    Returns:
        转换后的值
    """
    # 优先从传入的env_vars获取，再从系统环境变量获取
    if env_vars is not None:
        value = env_vars.get(key)
    else:
        value = os.getenv(key)
    
    if value is None or value == '':
        return default
    
    # 类型转换
    try:
        if value_type == bool:
            return value.lower() in ('true', '1', 'yes', 'on')
        elif value_type == int:
            return int(value)
        elif value_type == float:
            return float(value)
        elif value_type == list:
            # 假设是逗号分隔的字符串
            return [item.strip() for item in value.split(',') if item.strip()]
        else:
            return value
    except (ValueError, TypeError):
        print(f"⚠️ 环境变量 {key} 的值 '{value}' 无法转换为 {value_type.__name__}，使用默认值")
        return default


class MultiDayConfig:
    """多日策略配置类"""
    
    def __init__(self, env_file_path: str = None):
        """初始化配置"""
        self.env_vars = load_env_file(env_file_path)
        self.load_config()
    
    def load_config(self):
        """加载配置参数"""
        # 基础配置
        self.tickers = get_env_value('TICKERS', default=[], value_type=list, env_vars=self.env_vars)
        self.output_dir = get_env_value('OUTPUT_DIR', default='./analysis_results_logs', env_vars=self.env_vars)
        self.verbose = get_env_value('VERBOSE', default=False, value_type=bool, env_vars=self.env_vars)
        
        # 日期配置
        self.start_date = get_env_value('START_DATE', default=None, env_vars=self.env_vars)
        self.end_date = get_env_value('END_DATE', default=None, env_vars=self.env_vars)
        
        # 功能开关
        self.disable_communications = get_env_value('DISABLE_COMMUNICATIONS', default=False, value_type=bool, env_vars=self.env_vars)
        self.disable_notifications = get_env_value('DISABLE_NOTIFICATIONS', default=False, value_type=bool, env_vars=self.env_vars)
        self.disable_data_prefetch = get_env_value('DISABLE_DATA_PREFETCH', default=False, value_type=bool, env_vars=self.env_vars)
        self.enable_okr = get_env_value('ENABLE_OKR', default=False, value_type=bool, env_vars=self.env_vars)
        self.show_reasoning = get_env_value('SHOW_REASONING', default=False, value_type=bool, env_vars=self.env_vars)
        self.dry_run = get_env_value('DRY_RUN', default=False, value_type=bool, env_vars=self.env_vars)
        
        # 数值配置
        self.max_comm_cycles = get_env_value('MAX_COMM_CYCLES', default=3, value_type=int, env_vars=self.env_vars)
        
        # 如果未设置日期，使用默认值
        if not self.end_date:
            self.end_date = datetime.now().strftime("%Y-%m-%d")
        
        if not self.start_date:
            end_date_obj = datetime.strptime(self.end_date, "%Y-%m-%d")
            self.start_date = (end_date_obj - timedelta(days=30)).strftime("%Y-%m-%d")
    
    def override_with_args(self, args):
        """用命令行参数覆盖环境变量配置"""
        if hasattr(args, 'tickers') and args.tickers:
            self.tickers = [ticker.strip().upper() for ticker in args.tickers.split(",") if ticker.strip()]
        
        if hasattr(args, 'start_date') and args.start_date:
            self.start_date = args.start_date
        
        if hasattr(args, 'end_date') and args.end_date:
            self.end_date = args.end_date
        
        if hasattr(args, 'output_dir') and args.output_dir:
            self.output_dir = args.output_dir
        
        if hasattr(args, 'disable_communications') and args.disable_communications:
            self.disable_communications = args.disable_communications
        
        if hasattr(args, 'disable_notifications') and args.disable_notifications:
            self.disable_notifications = args.disable_notifications
        
        if hasattr(args, 'disable_data_prefetch') and args.disable_data_prefetch:
            self.disable_data_prefetch = args.disable_data_prefetch
        
        if hasattr(args, 'enable_okr') and args.enable_okr:
            self.enable_okr = args.enable_okr
        
        if hasattr(args, 'show_reasoning') and args.show_reasoning:
            self.show_reasoning = args.show_reasoning
        
        if hasattr(args, 'dry_run') and args.dry_run:
            self.dry_run = args.dry_run
        
        if hasattr(args, 'verbose') and args.verbose:
            self.verbose = args.verbose
        
        if hasattr(args, 'max_comm_cycles') and args.max_comm_cycles:
            self.max_comm_cycles = args.max_comm_cycles


class LiveTradingConfig:
    """Live交易系统配置类"""
    
    def __init__(self, env_file_path: str = None):
        """初始化配置"""
        self.env_vars = load_env_file(env_file_path)
        self.load_config()
    
    def load_config(self):
        """加载配置参数"""
        # 基础配置
        self.tickers = get_env_value('TICKERS', default=[], value_type=list, env_vars=self.env_vars)
        self.base_dir = get_env_value('LIVE_BASE_DIR', default=None, env_vars=self.env_vars)
        
        # 日期配置
        self.backfill_start_date = get_env_value('BACKFILL_START_DATE', default='2025-01-01', env_vars=self.env_vars)
        self.target_date = get_env_value('TARGET_DATE', default=None, env_vars=self.env_vars)
        
        # 功能开关
        self.force_run = get_env_value('FORCE_RUN', default=False, value_type=bool, env_vars=self.env_vars)
        
        # 数值配置
        self.max_comm_cycles = get_env_value('LIVE_MAX_COMM_CYCLES', default=2, value_type=int, env_vars=self.env_vars)
    
    def override_with_args(self, args):
        """用命令行参数覆盖环境变量配置"""
        if hasattr(args, 'tickers') and args.tickers:
            self.tickers = [ticker.strip().upper() for ticker in args.tickers.split(",") if ticker.strip()]
        
        if hasattr(args, 'base_dir') and args.base_dir:
            self.base_dir = args.base_dir
        
        if hasattr(args, 'start_date') and args.start_date:
            self.backfill_start_date = args.start_date
        
        if hasattr(args, 'date') and args.date:
            self.target_date = args.date
        
        if hasattr(args, 'force_run') and args.force_run:
            self.force_run = args.force_run
        
        if hasattr(args, 'max_comm_cycles') and args.max_comm_cycles:
            self.max_comm_cycles = args.max_comm_cycles




if __name__ == "__main__":
   
    
    # 测试配置加载
    print("\n测试多日策略配置:")
    multi_config = MultiDayConfig()
    print(f"  默认股票: {multi_config.tickers}")
    print(f"  输出目录: {multi_config.output_dir}")
    print(f"  最大沟通轮数: {multi_config.max_comm_cycles}")
    
    print("\n测试Live交易配置:")
    live_config = LiveTradingConfig()
    print(f"  默认股票: {live_config.tickers}")
    print(f"  回填开始日期: {live_config.backfill_start_date}")
    print(f"  最大沟通轮数: {live_config.max_comm_cycles}")
