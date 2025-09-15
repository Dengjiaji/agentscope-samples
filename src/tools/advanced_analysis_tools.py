"""
高级股票分析工具集合
基于现有数据源创造的新分析工具
"""

from langchain_core.tools import tool
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from statistics import median, stdev
import math

from src.tools.api import (
    get_financial_metrics, 
    get_prices, 
    get_insider_trades, 
    get_company_news,
    prices_to_df,
    get_market_cap,
    search_line_items,
)


def safe_float(value, default=0.0):
    """安全转换为浮点数"""
    try:
        if pd.isna(value) or np.isnan(value):
            return default
        return float(value)
    except (ValueError, TypeError, OverflowError):
        return default


# ===================== 高级技术分析工具 =====================

@tool
def analyze_volume_profile(ticker: str, start_date: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """成交量分布分析 - 分析价格与成交量的关系"""
    try:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        extended_start_date = (end_dt - timedelta(days=90)).strftime("%Y-%m-%d")
        
        prices = get_prices(ticker=ticker, start_date=extended_start_date, end_date=end_date, api_key=api_key)
        if not prices:
            return {"error": "No price data found", "signal": "neutral", "confidence": 0}
        
        prices_df = prices_to_df(prices)
        if len(prices_df) < 20:
            return {"error": "数据不足", "signal": "neutral", "confidence": 0}
        
        # 计算成交量指标
        prices_df['volume_sma'] = prices_df['volume'].rolling(window=20).mean()
        prices_df['volume_ratio'] = prices_df['volume'] / prices_df['volume_sma']
        prices_df['price_change'] = prices_df['close'].pct_change()
        prices_df['volume_price_trend'] = prices_df['volume_ratio'] * np.sign(prices_df['price_change'])
        
        # 获取最新数据
        current_volume_ratio = safe_float(prices_df['volume_ratio'].iloc[-1])
        avg_volume_price_trend = safe_float(prices_df['volume_price_trend'].tail(5).mean())
        volume_trend = safe_float(prices_df['volume'].tail(5).mean() / prices_df['volume'].tail(20).mean())
        
        signals = []
        details = []
        
        # 成交量放大信号
        if current_volume_ratio > 2.0:
            signals.append("bullish" if prices_df['price_change'].iloc[-1] > 0 else "bearish")
            details.append(f"✅ 成交量异常放大: {current_volume_ratio:.1f}倍")
        elif current_volume_ratio > 1.5:
            signals.append("neutral")
            details.append(f"⚠️ 成交量适度放大: {current_volume_ratio:.1f}倍")
        else:
            signals.append("neutral")
            details.append(f"⚠️ 成交量正常: {current_volume_ratio:.1f}倍")
        
        # 量价配合度
        if avg_volume_price_trend > 0.5:
            signals.append("bullish")
            details.append("✅ 量价配合良好，上涨有量支撑")
        elif avg_volume_price_trend < -0.5:
            signals.append("bearish")
            details.append("❌ 量价背离，下跌放量")
        else:
            signals.append("neutral")
            details.append("⚠️ 量价关系一般")
        
        # 成交量趋势
        if volume_trend > 1.2:
            signals.append("bullish")
            details.append("✅ 成交量趋势向上")
        elif volume_trend < 0.8:
            signals.append("bearish")
            details.append("❌ 成交量趋势向下")
        else:
            signals.append("neutral")
            details.append("⚠️ 成交量趋势平稳")
        
        bullish_count = signals.count("bullish")
        bearish_count = signals.count("bearish")
        
        final_signal = "bullish" if bullish_count > bearish_count else "bearish" if bearish_count > bullish_count else "neutral"
        confidence = round((max(bullish_count, bearish_count) / len(signals)) * 100)
        
        return {
            "signal": final_signal,
            "confidence": confidence,
            "metrics": {
                "volume_ratio": round(current_volume_ratio, 2),
                "volume_price_trend": round(avg_volume_price_trend, 2),
                "volume_trend": round(volume_trend, 2)
            },
            "details": details,
            "reasoning": f"成交量分析: {bullish_count}个看涨, {bearish_count}个看跌"
        }
    except Exception as e:
        return {"error": str(e), "signal": "neutral", "confidence": 0}


@tool
def analyze_gap_analysis(ticker: str, start_date: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """缺口分析 - 分析价格跳空的意义"""
    try:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        extended_start_date = (end_dt - timedelta(days=60)).strftime("%Y-%m-%d")
        
        prices = get_prices(ticker=ticker, start_date=extended_start_date, end_date=end_date, api_key=api_key)
        if not prices:
            return {"error": "No price data found", "signal": "neutral", "confidence": 0}
        
        prices_df = prices_to_df(prices)
        if len(prices_df) < 10:
            return {"error": "数据不足", "signal": "neutral", "confidence": 0}
        
        # 识别缺口
        prices_df['prev_high'] = prices_df['high'].shift(1)
        prices_df['prev_low'] = prices_df['low'].shift(1)
        prices_df['gap_up'] = prices_df['low'] > prices_df['prev_high']
        prices_df['gap_down'] = prices_df['high'] < prices_df['prev_low']
        prices_df['gap_size'] = np.where(
            prices_df['gap_up'], 
            (prices_df['low'] - prices_df['prev_high']) / prices_df['prev_high'],
            np.where(
                prices_df['gap_down'],
                (prices_df['prev_low'] - prices_df['high']) / prices_df['prev_low'],
                0
            )
        )
        
        # 统计最近的缺口
        recent_gaps = prices_df.tail(20)
        gap_up_count = recent_gaps['gap_up'].sum()
        gap_down_count = recent_gaps['gap_down'].sum()
        avg_gap_size = safe_float(recent_gaps[recent_gaps['gap_size'] != 0]['gap_size'].mean())
        
        # 检查最近是否有重要缺口
        latest_gap = prices_df['gap_size'].iloc[-1] if len(prices_df) > 0 else 0
        has_recent_significant_gap = abs(latest_gap) > 0.02  # 2%以上的缺口
        
        signals = []
        details = []
        
        # 缺口方向信号
        if gap_up_count > gap_down_count and gap_up_count > 2:
            signals.append("bullish")
            details.append(f"✅ 近期向上缺口较多: {gap_up_count}个")
        elif gap_down_count > gap_up_count and gap_down_count > 2:
            signals.append("bearish")
            details.append(f"❌ 近期向下缺口较多: {gap_down_count}个")
        else:
            signals.append("neutral")
            details.append("⚠️ 缺口分布相对均衡")
        
        # 最新缺口信号
        if has_recent_significant_gap:
            if latest_gap > 0:
                signals.append("bullish")
                details.append(f"✅ 最新向上跳空: {latest_gap*100:.1f}%")
            else:
                signals.append("bearish")
                details.append(f"❌ 最新向下跳空: {abs(latest_gap)*100:.1f}%")
        else:
            signals.append("neutral")
            details.append("⚠️ 无显著跳空")
        
        bullish_count = signals.count("bullish")
        bearish_count = signals.count("bearish")
        
        final_signal = "bullish" if bullish_count > bearish_count else "bearish" if bearish_count > bullish_count else "neutral"
        confidence = round((max(bullish_count, bearish_count) / len(signals)) * 100)
        
        return {
            "signal": final_signal,
            "confidence": confidence,
            "metrics": {
                "gap_up_count": int(gap_up_count),
                "gap_down_count": int(gap_down_count),
                "latest_gap_pct": round(latest_gap * 100, 2),
                "avg_gap_size_pct": round(avg_gap_size * 100, 2)
            },
            "details": details,
            "reasoning": f"缺口分析: {bullish_count}个看涨, {bearish_count}个看跌"
        }
    except Exception as e:
        return {"error": str(e), "signal": "neutral", "confidence": 0}


# ===================== 高级基本面分析工具 =====================

@tool
def analyze_efficiency_ratios(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """效率比率分析 - 分析公司资产使用效率"""
    try:
        financial_metrics = get_financial_metrics(ticker=ticker, end_date=end_date, period="ttm", limit=10, api_key=api_key)
        if not financial_metrics:
            return {"error": "No financial metrics found", "signal": "neutral", "confidence": 0}
        
        metrics = financial_metrics[0]
        
        # 效率指标
        asset_turnover = metrics.asset_turnover
        inventory_turnover = metrics.inventory_turnover
        receivables_turnover = metrics.receivables_turnover
        working_capital_turnover = metrics.working_capital_turnover
        
        score = 0
        details = []
        
        # 资产周转率
        if asset_turnover and asset_turnover > 1.0:
            score += 1
            details.append(f"✅ 资产周转率良好: {asset_turnover:.2f}")
        else:
            details.append(f"❌ 资产周转率偏低: {asset_turnover:.2f}" if asset_turnover else "❌ 资产周转率: N/A")
        
        # 存货周转率
        if inventory_turnover and inventory_turnover > 6:
            score += 1
            details.append(f"✅ 存货周转快: {inventory_turnover:.1f}次/年")
        else:
            details.append(f"❌ 存货周转慢: {inventory_turnover:.1f}次/年" if inventory_turnover else "❌ 存货周转率: N/A")
        
        # 应收账款周转率
        if receivables_turnover and receivables_turnover > 8:
            score += 1
            details.append(f"✅ 应收账款周转快: {receivables_turnover:.1f}次/年")
        else:
            details.append(f"❌ 应收账款周转慢: {receivables_turnover:.1f}次/年" if receivables_turnover else "❌ 应收账款周转率: N/A")
        
        # 营运资本周转率
        if working_capital_turnover and working_capital_turnover > 4:
            score += 1
            details.append(f"✅ 营运资本效率高: {working_capital_turnover:.1f}")
        else:
            details.append(f"❌ 营运资本效率低: {working_capital_turnover:.1f}" if working_capital_turnover else "❌ 营运资本周转率: N/A")
        
        signal = "bullish" if score >= 3 else "bearish" if score <= 1 else "neutral"
        confidence = round((score / 4) * 100)
        
        return {
            "signal": signal,
            "confidence": confidence,
            "metrics": {
                "asset_turnover": asset_turnover,
                "inventory_turnover": inventory_turnover,
                "receivables_turnover": receivables_turnover,
                "working_capital_turnover": working_capital_turnover
            },
            "details": details,
            "reasoning": f"效率分析评分: {score}/4"
        }
    except Exception as e:
        return {"error": str(e), "signal": "neutral", "confidence": 0}


@tool
def analyze_quality_metrics(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """质量指标分析 - 分析公司盈利质量"""
    try:
        financial_metrics = get_financial_metrics(ticker=ticker, end_date=end_date, period="ttm", limit=8, api_key=api_key)
        if not financial_metrics:
            return {"error": "No financial metrics found", "signal": "neutral", "confidence": 0}
        
        current = financial_metrics[0]
        
        # 获取现金流数据
        line_items = search_line_items(
            ticker=ticker,
            line_items=["operating_cash_flow", "net_income", "free_cash_flow"],
            end_date=end_date,
            period="ttm",
            limit=2,
            api_key=api_key,
        )
        
        if not line_items:
            return {"error": "No cash flow data found", "signal": "neutral", "confidence": 0}
        
        ocf = line_items[0].operating_cash_flow
        net_income = line_items[0].net_income
        fcf = line_items[0].free_cash_flow
        
        score = 0
        details = []
        
        # 现金流与净利润比较
        if ocf and net_income and ocf > net_income * 0.9:
            score += 1
            details.append(f"✅ 经营现金流质量好: OCF/NI = {ocf/net_income:.2f}")
        else:
            details.append("❌ 经营现金流质量差")
        
        # 自由现金流质量
        if fcf and net_income and fcf > net_income * 0.7:
            score += 1
            details.append(f"✅ 自由现金流充足: FCF/NI = {fcf/net_income:.2f}")
        else:
            details.append("❌ 自由现金流不足")
        
        # ROE与ROA的关系
        roe = current.return_on_equity
        roa = current.return_on_assets
        if roe and roa and roe > roa and roa > 0.05:
            score += 1
            details.append(f"✅ 杠杆使用合理: ROE({roe:.2%}) > ROA({roa:.2%})")
        else:
            details.append("❌ 杠杆使用效果不佳")
        
        # 毛利率稳定性
        if len(financial_metrics) >= 4:
            gross_margins = [m.gross_margin for m in financial_metrics[:4] if m.gross_margin]
            if len(gross_margins) >= 3:
                margin_stability = stdev(gross_margins) / abs(sum(gross_margins) / len(gross_margins))
                if margin_stability < 0.1:  # 变异系数小于10%
                    score += 1
                    details.append(f"✅ 毛利率稳定: 变异系数 {margin_stability:.2%}")
                else:
                    details.append(f"❌ 毛利率波动大: 变异系数 {margin_stability:.2%}")
        
        signal = "bullish" if score >= 3 else "bearish" if score <= 1 else "neutral"
        confidence = round((score / 4) * 100)
        
        return {
            "signal": signal,
            "confidence": confidence,
            "metrics": {
                "ocf_to_ni_ratio": round(ocf/net_income, 2) if ocf and net_income else None,
                "fcf_to_ni_ratio": round(fcf/net_income, 2) if fcf and net_income else None,
                "roe": roe,
                "roa": roa
            },
            "details": details,
            "reasoning": f"盈利质量评分: {score}/4"
        }
    except Exception as e:
        return {"error": str(e), "signal": "neutral", "confidence": 0}


# ===================== 高级情绪分析工具 =====================

@tool
def analyze_insider_sentiment_trend(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """内部人情绪趋势分析 - 分析内部交易的时间趋势"""
    try:
        # 获取过去6个月的内部交易数据
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=180)
        start_date = start_dt.strftime("%Y-%m-%d")
        
        insider_trades = get_insider_trades(ticker=ticker, end_date=end_date, start_date=start_date, limit=1000, api_key=api_key)
        
        if not insider_trades:
            return {"signal": "neutral", "confidence": 0, "details": ["无内部交易数据"], "reasoning": "内部人情绪趋势: 无数据"}
        
        # 转换为DataFrame并按时间排序
        trades_data = []
        for trade in insider_trades:
            if trade.transaction_shares and trade.transaction_date:
                trades_data.append({
                    'date': trade.transaction_date,
                    'shares': trade.transaction_shares,
                    'value': trade.transaction_value or 0,
                    'is_director': trade.is_board_director or False
                })
        
        if not trades_data:
            return {"signal": "neutral", "confidence": 0, "details": ["交易数据无效"], "reasoning": "内部人情绪趋势: 数据无效"}
        
        trades_df = pd.DataFrame(trades_data)
        trades_df['date'] = pd.to_datetime(trades_df['date'])
        trades_df = trades_df.sort_values('date')
        
        # 按月统计
        trades_df['month'] = trades_df['date'].dt.to_period('M')
        monthly_sentiment = trades_df.groupby('month').agg({
            'shares': ['sum', 'count'],
            'value': 'sum'
        }).reset_index()
        
        # 计算趋势
        if len(monthly_sentiment) >= 3:
            recent_months = monthly_sentiment.tail(3)
            early_months = monthly_sentiment.head(3)
            
            recent_net_shares = recent_months[('shares', 'sum')].sum()
            early_net_shares = early_months[('shares', 'sum')].sum()
            
            signals = []
            details = []
            
            # 净买卖趋势
            if recent_net_shares > 0 and early_net_shares <= 0:
                signals.append("bullish")
                details.append("✅ 内部人从卖出转为买入")
            elif recent_net_shares < 0 and early_net_shares >= 0:
                signals.append("bearish")
                details.append("❌ 内部人从买入转为卖出")
            elif recent_net_shares > early_net_shares * 1.5:
                signals.append("bullish")
                details.append("✅ 内部人买入力度增强")
            elif recent_net_shares < early_net_shares * 0.5:
                signals.append("bearish")
                details.append("❌ 内部人卖出力度增强")
            else:
                signals.append("neutral")
                details.append("⚠️ 内部人交易趋势平稳")
            
            # 董事交易分析
            director_trades = trades_df[trades_df['is_director'] == True]
            if len(director_trades) > 0:
                director_net = director_trades['shares'].sum()
                if director_net > 0:
                    signals.append("bullish")
                    details.append("✅ 董事净买入")
                elif director_net < 0:
                    signals.append("bearish")
                    details.append("❌ 董事净卖出")
                else:
                    signals.append("neutral")
                    details.append("⚠️ 董事交易中性")
            
            bullish_count = signals.count("bullish")
            bearish_count = signals.count("bearish")
            
            final_signal = "bullish" if bullish_count > bearish_count else "bearish" if bearish_count > bullish_count else "neutral"
            confidence = round((max(bullish_count, bearish_count) / len(signals)) * 100) if signals else 0
            
            return {
                "signal": final_signal,
                "confidence": confidence,
                "metrics": {
                    "recent_net_shares": float(recent_net_shares),
                    "early_net_shares": float(early_net_shares),
                    "total_trades": len(trades_df),
                    "director_trades": len(director_trades)
                },
                "details": details,
                "reasoning": f"内部人情绪趋势: {bullish_count}个看涨, {bearish_count}个看跌"
            }
        else:
            return {"signal": "neutral", "confidence": 0, "details": ["历史数据不足"], "reasoning": "内部人情绪趋势: 数据不足"}
            
    except Exception as e:
        return {"error": str(e), "signal": "neutral", "confidence": 0}


@tool
def analyze_news_momentum(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """新闻动量分析 - 分析新闻频率和情绪变化趋势"""
    try:
        # 获取过去30天的新闻
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=30)
        start_date = start_dt.strftime("%Y-%m-%d")
        
        company_news = get_company_news(ticker=ticker, end_date=end_date, start_date=start_date, limit=100, api_key=api_key)
        
        if not company_news:
            return {"signal": "neutral", "confidence": 0, "details": ["无新闻数据"], "reasoning": "新闻动量分析: 无数据"}
        
        # 转换为DataFrame
        news_data = []
        for news in company_news:
            news_data.append({
                'date': pd.to_datetime(news.date),
                'sentiment': news.sentiment,
                'source': news.source
            })
        
        news_df = pd.DataFrame(news_data)
        news_df = news_df.sort_values('date')
        
        # 按周统计
        news_df['week'] = news_df['date'].dt.to_period('W')
        
        signals = []
        details = []
        
        # 新闻频率分析
        weekly_counts = news_df.groupby('week').size()
        if len(weekly_counts) >= 2:
            recent_week_count = weekly_counts.iloc[-1]
            avg_count = weekly_counts.mean()
            
            if recent_week_count > avg_count * 1.5:
                signals.append("bullish")
                details.append(f"✅ 新闻关注度上升: 本周{recent_week_count}篇 vs 平均{avg_count:.1f}篇")
            elif recent_week_count < avg_count * 0.5:
                signals.append("bearish")
                details.append(f"❌ 新闻关注度下降: 本周{recent_week_count}篇 vs 平均{avg_count:.1f}篇")
            else:
                signals.append("neutral")
                details.append(f"⚠️ 新闻关注度正常: 本周{recent_week_count}篇")
        
        # 情绪变化趋势
        sentiment_scores = {'positive': 1, 'neutral': 0, 'negative': -1}
        news_df['sentiment_score'] = news_df['sentiment'].map(sentiment_scores).fillna(0)
        
        if len(news_df) >= 10:
            # 前半段vs后半段情绪对比
            mid_point = len(news_df) // 2
            early_sentiment = news_df.iloc[:mid_point]['sentiment_score'].mean()
            recent_sentiment = news_df.iloc[mid_point:]['sentiment_score'].mean()
            
            if recent_sentiment > early_sentiment + 0.2:
                signals.append("bullish")
                details.append("✅ 新闻情绪趋势向好")
            elif recent_sentiment < early_sentiment - 0.2:
                signals.append("bearish")
                details.append("❌ 新闻情绪趋势转差")
            else:
                signals.append("neutral")
                details.append("⚠️ 新闻情绪趋势平稳")
        
        # 消息源多样性
        unique_sources = news_df['source'].nunique()
        total_news = len(news_df)
        source_diversity = unique_sources / total_news if total_news > 0 else 0
        
        if source_diversity > 0.5:
            signals.append("bullish")
            details.append(f"✅ 消息源多样化: {unique_sources}个来源")
        else:
            signals.append("neutral")
            details.append(f"⚠️ 消息源集中: {unique_sources}个来源")
        
        bullish_count = signals.count("bullish")
        bearish_count = signals.count("bearish")
        
        final_signal = "bullish" if bullish_count > bearish_count else "bearish" if bearish_count > bullish_count else "neutral"
        confidence = round((max(bullish_count, bearish_count) / len(signals)) * 100) if signals else 0
        
        return {
            "signal": final_signal,
            "confidence": confidence,
            "metrics": {
                "total_news": total_news,
                "unique_sources": unique_sources,
                "avg_sentiment": round(news_df['sentiment_score'].mean(), 2),
                "source_diversity": round(source_diversity, 2)
            },
            "details": details,
            "reasoning": f"新闻动量分析: {bullish_count}个看涨, {bearish_count}个看跌"
        }
        
    except Exception as e:
        return {"error": str(e), "signal": "neutral", "confidence": 0}


# ===================== 综合风险分析工具 =====================

@tool
def analyze_comprehensive_risk(ticker: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """综合风险分析 - 评估多维度风险指标"""
    try:
        # 获取财务数据
        financial_metrics = get_financial_metrics(ticker=ticker, end_date=end_date, period="ttm", limit=8, api_key=api_key)
        if not financial_metrics:
            return {"error": "No financial metrics found", "signal": "neutral", "confidence": 0}
        
        current = financial_metrics[0]
        
        # 获取价格数据计算波动率
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=252)  # 一年数据
        start_date = start_dt.strftime("%Y-%m-%d")
        
        prices = get_prices(ticker=ticker, start_date=start_date, end_date=end_date, api_key=api_key)
        
        risk_score = 0
        risk_factors = []
        
        # 1. 财务风险
        debt_to_equity = current.debt_to_equity
        if debt_to_equity:
            if debt_to_equity > 1.0:
                risk_score += 2
                risk_factors.append(f"❌ 高债务风险: D/E = {debt_to_equity:.2f}")
            elif debt_to_equity > 0.5:
                risk_score += 1
                risk_factors.append(f"⚠️ 中等债务风险: D/E = {debt_to_equity:.2f}")
            else:
                risk_factors.append(f"✅ 低债务风险: D/E = {debt_to_equity:.2f}")
        
        # 2. 流动性风险
        current_ratio = current.current_ratio
        if current_ratio:
            if current_ratio < 1.0:
                risk_score += 2
                risk_factors.append(f"❌ 流动性风险高: CR = {current_ratio:.2f}")
            elif current_ratio < 1.5:
                risk_score += 1
                risk_factors.append(f"⚠️ 流动性风险中等: CR = {current_ratio:.2f}")
            else:
                risk_factors.append(f"✅ 流动性充足: CR = {current_ratio:.2f}")
        
        # 3. 盈利稳定性风险
        if len(financial_metrics) >= 4:
            net_margins = [m.net_margin for m in financial_metrics[:4] if m.net_margin]
            if len(net_margins) >= 3:
                margin_volatility = stdev(net_margins) / abs(sum(net_margins) / len(net_margins))
                if margin_volatility > 0.3:
                    risk_score += 2
                    risk_factors.append(f"❌ 盈利波动大: 变异系数 {margin_volatility:.2%}")
                elif margin_volatility > 0.15:
                    risk_score += 1
                    risk_factors.append(f"⚠️ 盈利波动中等: 变异系数 {margin_volatility:.2%}")
                else:
                    risk_factors.append(f"✅ 盈利稳定: 变异系数 {margin_volatility:.2%}")
        
        # 4. 价格波动风险
        if prices and len(prices) > 20:
            prices_df = prices_to_df(prices)
            returns = prices_df['close'].pct_change().dropna()
            volatility = returns.std() * np.sqrt(252)  # 年化波动率
            
            if volatility > 0.6:
                risk_score += 2
                risk_factors.append(f"❌ 高价格波动: {volatility*100:.1f}%")
            elif volatility > 0.3:
                risk_score += 1
                risk_factors.append(f"⚠️ 中等价格波动: {volatility*100:.1f}%")
            else:
                risk_factors.append(f"✅ 低价格波动: {volatility*100:.1f}%")
        
        # 5. 估值风险
        pe_ratio = current.price_to_earnings_ratio
        if pe_ratio:
            if pe_ratio > 50:
                risk_score += 2
                risk_factors.append(f"❌ 估值过高风险: P/E = {pe_ratio:.1f}")
            elif pe_ratio > 30:
                risk_score += 1
                risk_factors.append(f"⚠️ 估值偏高风险: P/E = {pe_ratio:.1f}")
            else:
                risk_factors.append(f"✅ 估值合理: P/E = {pe_ratio:.1f}")
        
        # 风险等级判断
        max_risk_score = 10
        risk_level = "低" if risk_score <= 2 else "中" if risk_score <= 5 else "高"
        
        # 生成信号（风险高则bearish）
        if risk_score <= 2:
            signal = "bullish"
        elif risk_score >= 7:
            signal = "bearish"
        else:
            signal = "neutral"
        
        confidence = round((abs(risk_score - 5) / 5) * 100)
        
        return {
            "signal": signal,
            "confidence": confidence,
            "risk_assessment": {
                "risk_score": risk_score,
                "max_score": max_risk_score,
                "risk_level": risk_level,
                "risk_percentage": round((risk_score / max_risk_score) * 100, 1)
            },
            "details": risk_factors,
            "reasoning": f"综合风险评估: {risk_level}风险 ({risk_score}/{max_risk_score}分)"
        }
        
    except Exception as e:
        return {"error": str(e), "signal": "neutral", "confidence": 0}


# ===================== 市场环境分析工具 =====================

@tool
def analyze_market_regime(ticker: str, start_date: str, end_date: str, api_key: str) -> Dict[str, Any]:
    """市场环境分析 - 判断当前市场状态"""
    try:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        extended_start_date = (end_dt - timedelta(days=200)).strftime("%Y-%m-%d")
        
        prices = get_prices(ticker=ticker, start_date=extended_start_date, end_date=end_date, api_key=api_key)
        if not prices:
            return {"error": "No price data found", "signal": "neutral", "confidence": 0}
        
        prices_df = prices_to_df(prices)
        if len(prices_df) < 50:
            return {"error": "数据不足", "signal": "neutral", "confidence": 0}
        
        # 计算技术指标
        prices_df['returns'] = prices_df['close'].pct_change()
        prices_df['sma_50'] = prices_df['close'].rolling(window=50).mean()
        prices_df['sma_200'] = prices_df['close'].rolling(window=200).mean()
        prices_df['volatility_20'] = prices_df['returns'].rolling(window=20).std() * np.sqrt(252)
        
        current_price = safe_float(prices_df['close'].iloc[-1])
        sma_50 = safe_float(prices_df['sma_50'].iloc[-1])
        sma_200 = safe_float(prices_df['sma_200'].iloc[-1])
        current_vol = safe_float(prices_df['volatility_20'].iloc[-1])
        
        # 趋势分析
        trend_signals = []
        regime_details = []
        
        # 1. 长期趋势
        if current_price > sma_200 and sma_50 > sma_200:
            trend_signals.append("bullish")
            regime_details.append("✅ 长期上升趋势")
        elif current_price < sma_200 and sma_50 < sma_200:
            trend_signals.append("bearish")
            regime_details.append("❌ 长期下降趋势")
        else:
            trend_signals.append("neutral")
            regime_details.append("⚠️ 长期趋势不明")
        
        # 2. 短期趋势
        if current_price > sma_50:
            trend_signals.append("bullish")
            regime_details.append("✅ 短期上升趋势")
        elif current_price < sma_50:
            trend_signals.append("bearish")
            regime_details.append("❌ 短期下降趋势")
        else:
            trend_signals.append("neutral")
            regime_details.append("⚠️ 短期趋势不明")
        
        # 3. 波动率环境
        vol_percentile = (prices_df['volatility_20'].rank(pct=True).iloc[-1]) * 100
        if vol_percentile > 80:
            trend_signals.append("bearish")
            regime_details.append(f"❌ 高波动环境: {vol_percentile:.0f}百分位")
        elif vol_percentile < 20:
            trend_signals.append("bullish")
            regime_details.append(f"✅ 低波动环境: {vol_percentile:.0f}百分位")
        else:
            trend_signals.append("neutral")
            regime_details.append(f"⚠️ 中等波动环境: {vol_percentile:.0f}百分位")
        
        # 4. 动量分析
        momentum_20 = (current_price / prices_df['close'].iloc[-21] - 1) if len(prices_df) > 20 else 0
        if momentum_20 > 0.05:
            trend_signals.append("bullish")
            regime_details.append(f"✅ 正动量: 20日涨幅{momentum_20*100:.1f}%")
        elif momentum_20 < -0.05:
            trend_signals.append("bearish")
            regime_details.append(f"❌ 负动量: 20日跌幅{abs(momentum_20)*100:.1f}%")
        else:
            trend_signals.append("neutral")
            regime_details.append(f"⚠️ 动量平稳: 20日变化{momentum_20*100:.1f}%")
        
        bullish_count = trend_signals.count("bullish")
        bearish_count = trend_signals.count("bearish")
        
        # 判断市场环境
        if bullish_count >= 3:
            market_regime = "牛市"
            final_signal = "bullish"
        elif bearish_count >= 3:
            market_regime = "熊市"
            final_signal = "bearish"
        else:
            market_regime = "震荡市"
            final_signal = "neutral"
        
        confidence = round((max(bullish_count, bearish_count) / len(trend_signals)) * 100)
        
        return {
            "signal": final_signal,
            "confidence": confidence,
            "market_regime": market_regime,
            "metrics": {
                "current_price": current_price,
                "sma_50": sma_50,
                "sma_200": sma_200,
                "volatility": round(current_vol * 100, 1),
                "momentum_20d_pct": round(momentum_20 * 100, 1)
            },
            "details": regime_details,
            "reasoning": f"市场环境: {market_regime} ({bullish_count}个看涨, {bearish_count}个看跌)"
        }
        
    except Exception as e:
        return {"error": str(e), "signal": "neutral", "confidence": 0}
