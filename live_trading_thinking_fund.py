#!/usr/bin/env python3
"""
Live交易思考基金 - 时间Sandbox系统
模拟真实交易日的时间流程：交易前分析 + 交易后复盘

时间点设计：
- 交易日：交易前 + 交易后
- 非交易日：仅交易后

使用方法:
# 运行指定日期的完整模拟
python live_trading_thinking_fund.py --date 2025-01-15 --tickers AAPL,MSFT

# 使用环境变量配置
python live_trading_thinking_fund.py --date 2025-01-15

# 强制运行
python live_trading_thinking_fund.py --date 2025-01-15 --force-run
"""
import pdb
import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from live_trading_system import LiveTradingSystem
from src.config.env_config import LiveTradingConfig
from src.memory.mem0_core import mem0_integration
from src.memory.unified_memory import unified_memory_manager
MEMORY_AVAILABLE = True
from src.utils.llm import call_llm
from src.llm.models import get_model
from langchain_core.messages import HumanMessage
LLM_AVAILABLE = True
from src.tools.memory_management_tools import get_memory_tools
MEMORY_TOOLS_AVAILABLE = True

import json
import re
import pandas_market_calendars as mcal
US_TRADING_CALENDAR_AVAILABLE = True




class LLMMemoryDecisionSystem:
    """基于LLM的记忆管理决策系统 - 使用LangChain tool_call"""
    
    def __init__(self):
        self.memory_tools = []
        
        if LLM_AVAILABLE and MEMORY_TOOLS_AVAILABLE:
            model_name = os.getenv('MEMORY_LLM_MODEL', 'gpt-4o-mini')
            model_provider_str = os.getenv('MEMORY_LLM_PROVIDER', 'OPENAI')
            from src.llm.models import ModelProvider
            
            # 转换为ModelProvider枚举
            if hasattr(ModelProvider, model_provider_str):
                model_provider = getattr(ModelProvider, model_provider_str)
            else:
                print(f"未知的模型提供商: {model_provider_str}，使用默认OPENAI")
                model_provider = ModelProvider.OPENAI
            
            api_keys = {}
            if model_provider == ModelProvider.OPENAI:
                api_keys['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')
            elif model_provider == ModelProvider.ANTHROPIC:
                api_keys['ANTHROPIC_API_KEY'] = os.getenv('ANTHROPIC_API_KEY')
            
            # 获取记忆管理工具
            self.memory_tools = get_memory_tools()
            # 绑定工具到LLM
            self.llm = get_model(model_name, model_provider, api_keys)
            self.llm_with_tools = self.llm.bind_tools(self.memory_tools)
            self.llm_available = True
            print(f"LLM记忆决策系统已启用（{model_provider_str}: {model_name}）")
            print(f"已绑定 {len(self.memory_tools)} 个记忆管理工具")
                
      
            
        
    
    def generate_memory_decision_prompt(self, performance_data: Dict[str, Any], date: str) -> str:
        """生成LLM记忆决策的prompt - LangChain tool_call版本"""
        
        prompt = f"""你是一个专业的Portfolio Manager，负责管理分析师团队的记忆系统。基于{date}的交易复盘结果，请分析分析师的表现并决定是否需要使用记忆管理工具。

# 复盘数据分析

## 分析师信号 vs 实际结果对比

### Portfolio Manager最终决策:
"""
        
        pm_signals = performance_data.get('pm_signals', {})
        actual_returns = performance_data.get('actual_returns', {})
        analyst_signals = performance_data.get('analyst_signals', {})
        tickers = performance_data.get('tickers', [])
        
        # 添加PM信号和实际结果
        for ticker in tickers:
            pm_signal = pm_signals.get(ticker, {})
            actual_return = actual_returns.get(ticker, 0)
            
            prompt += f"\n{ticker}:"
            prompt += f"\n  PM决策: {pm_signal.get('signal', 'N/A')} (置信度: {pm_signal.get('confidence', 'N/A')}%)"
            prompt += f"\n  实际收益: {actual_return:.2%}"
            
        prompt += "\n\n### 各分析师的预测表现:"
        
        # 添加分析师表现
        for analyst, signals in analyst_signals.items():
            prompt += f"\n\n**{analyst}:**"
            total_count = 0            
            for ticker in tickers:
                if ticker in signals and ticker in actual_returns:
                    analyst_signal = signals[ticker]
                    actual_return = actual_returns[ticker]
                    total_count += 1
                                        
                    prompt += f"\n  {ticker}: 预测 {analyst_signal}, 实际 {actual_return:.2%}"
                    
        prompt += f"""

# 记忆管理决策指导

请分析各分析师的表现，并决定是否需要执行记忆管理操作：

- **表现极差** (多个严重错误)：使用search_and_delete_analyst_memory删除严重错误记忆
- **表现不佳** (一个或者多个微小错误)：使用search_and_update_analyst_memory更新错误记忆
- **表现优秀或正常**：无需操作，直接说明分析结果即可

可用的记忆管理工具：
1. **search_and_update_analyst_memory**: 修正更新分析师的相关记忆内容
2. **search_and_delete_analyst_memory**: 删除分析师的相关记忆内容

请先分析各分析师的表现，然后如果需要记忆操作，直接调用相应的工具。如果不需要任何操作，请说明你的分析结果。
"""
        
        return prompt
    
    
    def make_llm_memory_decision_with_tools(self, performance_data: Dict[str, Any], date: str) -> Dict[str, Any]:
        """使用LLM进行记忆管理决策 - LangChain tool_call版本"""
        
        if not self.llm_available:
            print("⚠️ LLM不可用，跳过记忆管理")
            return {'status': 'skipped', 'reason': 'LLM不可用'}
        
        try:
            # 生成prompt
            prompt = self.generate_memory_decision_prompt(performance_data, date)
            
            print(f"\n🤖 正在请求LLM进行记忆管理决策...")
            print(f"📝 Prompt长度: {len(prompt)} 字符")
            
            # 调用绑定了工具的LLM
            messages = [HumanMessage(content=prompt)]
            response = self.llm_with_tools.invoke(messages)
            
            print(f"📥 LLM响应类型: {type(response)}")
            
            # 检查是否有工具调用
            tool_calls = []
            if hasattr(response, 'tool_calls') and response.tool_calls:
                tool_calls = response.tool_calls
                print(f"🛠️ LLM决定执行 {len(tool_calls)} 个工具调用")
                
                # 执行工具调用
                execution_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call['name']
                    tool_args = tool_call['args']
                    
                    print(f"  📞 调用工具: {tool_name}")
                    print(f"     参数: {tool_args}")
                    
                    # 直接调用对应的工具函数
                    tool_function = next(
                        (tool for tool in self.memory_tools if tool.name == tool_name), 
                        None
                    )
                    
                    if tool_function:
                            result = tool_function.invoke(tool_args)
                            execution_results.append({
                                'tool_name': tool_name,
                                'args': tool_args,
                                'result': result
                            })
                            # pdb.set_trace()
              
                    else:
                        print(f"    ❌ 未找到工具: {tool_name}")
                        execution_results.append({
                            'tool_name': tool_name,
                            'args': tool_args,
                            'result': {'status': 'failed', 'error': f'Tool not found: {tool_name}'}
                        })
                
                return {
                    'status': 'success',
                    'mode': 'operations_executed',
                    'operations_count': len(tool_calls),
                    'execution_results': execution_results,
                    'llm_reasoning': response.content,
                    'date': date
                }
            else:
                # 没有工具调用，LLM可能认为不需要操作
                reasoning = response.content if hasattr(response, 'content') else str(response)
                print(f"💭 LLM分析: {reasoning}")
                
                return {
                    'status': 'success',
                    'mode': 'no_action',
                    'reasoning': reasoning,
                    'date': date
                }
                
        except Exception as e:
            print(f"❌ LLM记忆管理决策失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'status': 'failed',
                'error': str(e),
                'date': date
            }
            
    



# 移除旧的解析方法，因为现在使用LangChain的原生tool_call机制


class LiveTradingThinkingFund:
    """Live交易思考基金 - 时间Sandbox系统"""
    
    def __init__(self, base_dir: str = None):
        """初始化思考基金系统"""
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent
        self.sandbox_dir = self.base_dir / "sandbox_logs"
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化Live交易系统
        self.live_system = LiveTradingSystem(base_dir=base_dir)
        
        # 初始化记忆管理系统
        if MEMORY_TOOLS_AVAILABLE:
            self.llm_memory_system = LLMMemoryDecisionSystem()
            print("LLM记忆管理系统已启用")
        else:
            self.llm_memory_system = None
            print("LLM记忆管理系统未启用")
        
        # 时间点定义
        self.PRE_MARKET = "pre_market"    # 交易前
        self.POST_MARKET = "post_market"  # 交易后
        
    def is_trading_day(self, date: str) -> bool:
        """检查是否为交易日"""
        return self.live_system.is_trading_day(date)
    
    def validate_date_format(self, date_str: str) -> bool:
        """验证日期格式"""
        return self.live_system.validate_date_format(date_str)
    
    def should_run_sandbox_analysis(self, date: str, time_point: str, force_run: bool = False) -> bool:
        """判断是否应该运行sandbox分析（独立于live_system的检查逻辑）"""
        if force_run:
            return True
        
        # 检查sandbox日志中是否已有成功的记录
        existing_data = self._load_sandbox_log(date, time_point)
        if existing_data and existing_data.get('status') == 'success':
            return False
        
        return True
    
    def _run_sandbox_analysis(self, tickers: List[str], target_date: str, max_comm_cycles: int = 2) -> Dict[str, Any]:
        """运行sandbox专用的分析（绕过live_system的状态管理）"""
        print(f"\n开始Sandbox策略分析 - {target_date}")
        print(f"监控标的: {', '.join(tickers)}")
        
        try:
            # 1. 运行策略分析（直接调用核心分析方法，绕过should_run_today检查）
            analysis_result = self.live_system.run_single_day_analysis(tickers, target_date, max_comm_cycles)
            
            # 使用defaultdict简化初始化
            live_env = {
                'pm_signals': {},
                'ana_signals': defaultdict(lambda: defaultdict(str)),  # 自动创建嵌套字典，默认值为空字符串
                'real_returns': defaultdict(float)  # 自动创建，默认值为0.0
            }
            
            # 2. 保存交易信号
            pm_signals = analysis_result['signals']
            live_env['pm_signals'] = pm_signals
            
            # 3. 提取分析师信号（现在不需要预先初始化）
            for agent in ['sentiment_analyst', 'technical_analyst', 'fundamentals_analyst', 'valuation_analyst']:
                for ticker in tickers:
                    try:
                        agent_results = analysis_result.get('raw_results', {}).get('results', {}).get('final_analyst_results', {})
                        if agent in agent_results and ticker in agent_results[agent].get('analysis_result', {}):
                            live_env['ana_signals'][agent][ticker] = agent_results[agent]['analysis_result'][ticker]['signal']
                        else:
                            live_env['ana_signals'][agent][ticker] = 'neutral'
                    except Exception as e:
                        print(f"警告: 无法获取 {agent} 对 {ticker} 的信号，使用默认值: {e}")
                        live_env['ana_signals'][agent][ticker] = 'neutral'
                    
            self.live_system.save_daily_signals(target_date, pm_signals)
            print(f"已保存 {len(pm_signals)} 个股票的交易信号")

            # 4. 计算当日收益
            target_date = str(target_date)
            daily_returns = self.live_system.calculate_daily_returns(target_date, pm_signals)
            
            # 现在不需要预先初始化，defaultdict会自动处理
            for ticker in tickers:
                live_env['real_returns'][ticker] = daily_returns[ticker]['daily_return']
                
            # 5. 更新个股收益
            individual_data = self.live_system.update_individual_returns(target_date, daily_returns)
            
            # self.live_system.clean_old_data()
            
            print(f"{target_date} Sandbox分析完成")
            
            # 显示各股票表现
            for ticker, data in daily_returns.items():
                daily_ret = data['daily_return'] * 100
                cum_ret = (individual_data[ticker][target_date]['cumulative_return'] - 1) * 100
                signal = data['signal']
                action = data['action']
                confidence = data['confidence']
                print(f"{ticker}: 日收益 {daily_ret:.2f}%, 累计收益 {cum_ret:.2f}%, "
                      f"信号 {signal}({action}, {confidence}%)")
            
            return {
                'status': 'success',
                'date': target_date,
                'signals': pm_signals,
                'individual_returns': daily_returns,
                'individual_cumulative': individual_data,
                'live_env': live_env
            }
            
        except Exception as e:
            print(f"Sandbox分析失败: {str(e)}")
            return {'status': 'failed', 'reason': str(e)}
    
    def run_pre_market_analysis(self, date: str, tickers: List[str], 
                               max_comm_cycles: int = 2, force_run: bool = False) -> Dict[str, Any]:
        """运行交易前分析（复用live_trading_system）"""
        print(f"\n===== 交易前分析 ({date}) =====")
        print(f"时间点: {self.PRE_MARKET}")
        print(f"分析标的: {', '.join(tickers)}")
        
        try:
            # 使用sandbox专用的检查逻辑
            # if not self.should_run_sandbox_analysis(date, self.PRE_MARKET, force_run):
            #     print(f"📋 {date} 交易前分析已存在，跳过重复运行（使用 --force-run 强制重新运行）")
            #     existing_data = self._load_sandbox_log(date, self.PRE_MARKET)
            #     return existing_data
            
            # 运行sandbox专用的分析（绕过live_system的状态检查）
            result = self._run_sandbox_analysis(tickers, date, max_comm_cycles)
            
            # 记录到sandbox日志
            self._log_sandbox_activity(date, self.PRE_MARKET, {
                'status': result['status'],
                'tickers': tickers,
                'timestamp': datetime.now().isoformat(),
                'details': result
            })
            
            return result
            
        except Exception as e:
            error_result = {
                'status': 'failed',
                'reason': f'交易前分析失败: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
            
            self._log_sandbox_activity(date, self.PRE_MARKET, error_result)
            return error_result
    
    def run_post_market_review(self, date: str, tickers: List[str], live_env: Dict[str, Any]) -> Dict[str, Any]:
        """运行交易后复盘"""
        print(f"\n===== 交易后复盘 ({date}) =====")
        print(f"时间点: {self.POST_MARKET}")
        print(f"复盘标的: {', '.join(tickers)}")
        if live_env != 'Not trading day':
        
            # 交易后复盘逻辑
            result = self._perform_post_market_review(date, tickers,live_env)
            
            # 记录到sandbox日志
            self._log_sandbox_activity(date, self.POST_MARKET, result)
            
            return result
         
    
    def _perform_post_market_review(self, date: str, tickers: List[str], live_env: Dict[str, Any]) -> Dict[str, Any]:
        """执行交易后复盘分析"""
        print("基于交易前分析进行复盘...")
        
        pm_signals = live_env['pm_signals']
        ana_signals = live_env['ana_signals']
        real_returns = live_env['real_returns']
        
        print(f"\nportfolio_manager信号回顾:")
        for ticker in tickers:
            if ticker in pm_signals:
                signal_info = pm_signals[ticker]
                print(f"   {ticker}: {signal_info.get('signal', 'N/A')} "
                      f"({signal_info.get('action', 'N/A')}, "
                      f"置信度: {signal_info.get('confidence', 'N/A')}%)")
            else:
                print(f"   {ticker}: 无信号数据")
        
        print(f"\n实际收益表现:")
        for ticker in tickers:
            if ticker in real_returns:
                daily_ret = real_returns[ticker] * 100
                print(f"   {ticker}: {daily_ret:.2f}% "
                      f"(信号: {pm_signals.get(ticker, {}).get('signal', 'N/A')})")
            else:
                print(f"   {ticker}: 无收益数据")
        
        print(f"\nanalyst信号对比:")
        for agent, agent_signals in ana_signals.items():
            print(f"  {agent}:")
            for ticker in tickers:
                signal = agent_signals.get(ticker, 'N/A')
                print(f"    {ticker}: {signal}")
        
        print(f"\n===== Portfolio Manager 记忆管理决策 =====")
        
        performance_analysis = {}
        execution_results = None
        
        try:
            if self.llm_memory_system:
                performance_data = {
                    'pm_signals': pm_signals,
                    'actual_returns': real_returns,
                    'analyst_signals': ana_signals,
                    'tickers': tickers
                }
                
                # 使用LLM进行记忆管理决策（tool_call模式）
                print("使用LLM tool_call进行智能记忆管理...")
                llm_decision = self.llm_memory_system.make_llm_memory_decision_with_tools(
                    performance_data, date
                )
                
                # 显示LLM决策结果
                if llm_decision['status'] == 'success':
                    if llm_decision['mode'] == 'operations_executed':
                        print(f"\n🛠️ LLM执行了 {llm_decision['operations_count']} 个记忆操作")
                        
                        # 统计执行结果
                        successful = sum(1 for result in llm_decision['execution_results'] 
                                       if result['result']['status'] == 'success')
                        total = len(llm_decision['execution_results'])
                        
                        print(f" 执行统计:")
                        print(f"  成功: {successful}/{total}")
                        
                        # 显示工具调用详情
                        for i, exec_result in enumerate(llm_decision['execution_results'], 1):
                            tool_name = exec_result['tool_name']
                            args = exec_result['args']
                            result = exec_result['result']
                            
                            print(f"  {i}. {tool_name}")
                            print(f"     分析师: {args.get('analyst_id', 'N/A')}")
                            if result['status'] == 'success':
                                print(f"     状态: 成功")
                            else:
                                print(f"     状态: 失败 - {result.get('error', 'Unknown')}")
                        
                        execution_results = llm_decision['execution_results']
                        
                    elif llm_decision['mode'] == 'no_action':
                        print(f" LLM认为无需记忆操作")
                        print(f" LLM理由: {llm_decision['reasoning']}")
                        execution_results = None
                    else:
                        print(f" 未知的LLM决策模式: {llm_decision['mode']}")
                        execution_results = None
                        
                elif llm_decision['status'] == 'skipped':
                    print(f" 记忆管理跳过: {llm_decision['reason']}")
                    execution_results = None
                else:
                    print(f" LLM决策失败: {llm_decision.get('error', 'Unknown error')}")
                    execution_results = None
            else:
                print("LLM记忆管理系统未启用，跳过记忆操作")
                llm_decision = None
                execution_results = None
                
        except Exception as e:
            print(f"记忆管理过程出错: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return {
            'status': 'success',
            'type': 'full_review',
            'pre_market_signals': pm_signals,
            'analyst_signals': ana_signals,
            'actual_returns': real_returns,
            'llm_memory_decision': llm_decision if 'llm_decision' in locals() else None,
            'memory_tool_calls_results': execution_results,
            'timestamp': datetime.now().isoformat()
        } 
    
    
    def run_full_day_simulation(self, date: str, tickers: List[str], 
                               max_comm_cycles: int = 2, force_run: bool = False) -> Dict[str, Any]:
        """运行完整的一天模拟（交易前 + 交易后）"""
        print(f"\n===== 开始 {date} 完整交易日模拟 =====")
        
        results = {
            'date': date,
            'is_trading_day': self.is_trading_day(date),
            'pre_market': None,
            'post_market': None,
            'summary': {}
        }
        
        if results['is_trading_day']:
            print(f"{date} 是交易日，将执行：交易前分析 + 交易后复盘")
            
            # 1. 交易前分析
            results['pre_market'] = self.run_pre_market_analysis(
                date, tickers, max_comm_cycles, force_run
            )
            
            print(f"\n等待交易后时间点...")
            print(f"(实际使用中，这里会等待真实的市场收盘)")
            
            # 2. 交易后复盘
            live_env = results['pre_market'].get('live_env') if results['pre_market'] else None
            results['post_market'] = self.run_post_market_review(date, tickers, live_env)
            
        else:
            print(f"{date} 非交易日，仅执行：交易后总结")
            
            # 非交易日只执行交易后
            results['post_market'] = self.run_post_market_review(date, tickers,'Not trading day')
        
        # 生成日总结
        results['summary'] = self._generate_day_summary(results)
        
        print(f"\n{date} 完整模拟结束")
        self._print_day_summary(results['summary'])
        
        return results
    
    def _generate_day_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """生成日总结"""
        summary = {
            'date': results['date'],
            'is_trading_day': results['is_trading_day'],
            'activities_completed': [],
            'overall_status': 'success'
        }
        
        if results['pre_market']:
            summary['activities_completed'].append('交易前分析')
            if results['pre_market']['status'] != 'success':
                summary['overall_status'] = 'partial_success'
        
        if results['post_market']:
            summary['activities_completed'].append('交易后复盘')
            if results['post_market']['status'] != 'success':
                summary['overall_status'] = 'partial_success'
        
        return summary
    
    def _print_day_summary(self, summary: Dict[str, Any]):
        """打印日总结"""
        print(f"\n===== {summary['date']} 日总结 =====")
        print(f"交易日状态: {'是' if summary['is_trading_day'] else '否'}")
        print(f"完成活动: {', '.join(summary['activities_completed'])}")
        print(f"总体状态: {summary['overall_status']}")
        print("=" * 40)
    
    def _log_sandbox_activity(self, date: str, time_point: str, data: Dict[str, Any]):
        """记录sandbox活动日志"""
        log_file = self.sandbox_dir / f"sandbox_day_{date.replace('-', '_')}.json"
        
        # 加载现有日志
        if log_file.exists():
            import json
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
            except:
                log_data = {}
        else:
            log_data = {}
        
        # 添加新活动
        log_data[time_point] = data
        log_data['last_updated'] = datetime.now().isoformat()
        
        # 保存日志
        import json
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"保存sandbox日志失败: {e}")
    
    def _load_sandbox_log(self, date: str, time_point: str) -> Dict[str, Any]:
        """加载sandbox活动日志"""
        log_file = self.sandbox_dir / f"sandbox_day_{date.replace('-', '_')}.json"
        
        if not log_file.exists():
            return {}
        
        import json
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
            return log_data.get(time_point, {})
        except Exception as e:
            print(f"加载sandbox日志失败: {e}")
            return {}


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Live交易思考基金 - 时间Sandbox系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 运行指定日期的完整模拟
  python live_trading_thinking_fund.py --date 2025-01-15 --tickers AAPL,MSFT
  
  # 使用环境变量中的股票配置
  python live_trading_thinking_fund.py --date 2025-01-15
  
  # 强制运行（忽略各种检查）
  python live_trading_thinking_fund.py --date 2025-01-15 --force-run
  
  # 自定义沟通轮数
  python live_trading_thinking_fund.py --date 2025-01-15 --max-comm-cycles 3
        """
    )
    
    # 必需参数
    parser.add_argument(
        '--date',
        type=str,
        required=True,
        help='指定模拟日期 (YYYY-MM-DD格式)'
    )
    
    # 可选参数
    parser.add_argument(
        '--tickers',
        type=str,
        help='股票代码列表，用逗号分隔 (可选，使用环境变量配置)'
    )
    
    parser.add_argument(
        '--max-comm-cycles',
        type=int,
        default=2,
        help='最大沟通轮数 (默认: 2)'
    )
    
    parser.add_argument(
        '--force-run',
        action='store_true',
        help='强制运行，如果已经是已经运行过的交易日则重新运行'
    )
    
    parser.add_argument(
        '--base-dir',
        type=str,
        help='基础目录'
    )
    
    args = parser.parse_args()
    
    try:
        # 加载配置
        config = LiveTradingConfig()
        config.override_with_args(args)
        thinking_fund = LiveTradingThinkingFund(base_dir=args.base_dir)
        
        if not thinking_fund.validate_date_format(args.date):
            print(f"错误: 日期格式无效: {args.date} (需要 YYYY-MM-DD)")
            sys.exit(1)
            
        # 确定股票代码
        if args.tickers:
            tickers = [ticker.strip().upper() for ticker in args.tickers.split(",") if ticker.strip()]
        elif config.tickers:
            tickers = config.tickers
        else:
            print("错误: 请通过 --tickers 参数或环境变量 TICKERS 提供股票代码")
            sys.exit(1)
        
        if not tickers:
            print("错误: 请提供至少一个有效的股票代码")
            sys.exit(1)
        
        print(f"时间Sandbox模拟设置:")
        print(f"   目标日期: {args.date}")
        print(f"   模拟标的: {', '.join(tickers)}")
        print(f"   沟通轮数: {args.max_comm_cycles}")
        print(f"   强制运行: {'是' if args.force_run else '否'}")
        
        # 运行完整日模拟
        results = thinking_fund.run_full_day_simulation(
            date=args.date,
            tickers=tickers,
            max_comm_cycles=args.max_comm_cycles,
            force_run=args.force_run
        )
        
        print(f"\n{args.date} 时间Sandbox模拟完成!")
        
    except KeyboardInterrupt:
        print("\n用户中断模拟")
        sys.exit(1)
    except Exception as e:
        print(f"\n模拟过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
