from colorama import Fore, Style
from tabulate import tabulate
from .analysts import ANALYST_ORDER
import os
import json


def sort_agent_signals(signals):
    """Sort agent signals in a consistent order."""
    # Create order mapping from ANALYST_ORDER
    analyst_order = {display: idx for idx, (display, _) in enumerate(ANALYST_ORDER)}
    analyst_order["Risk Management"] = len(ANALYST_ORDER)  # Add Risk Management at the end

    return sorted(signals, key=lambda x: analyst_order.get(x[0], 999))


def print_trading_output(result: dict) -> None:
    """
    Print formatted trading results with colored tables for multiple tickers.

    Args:
        result (dict): Dictionary containing decisions and analyst signals for multiple tickers
    """
    decisions = result.get("decisions")
    if not decisions:
        print(f"{Fore.RED}No trading decisions available{Style.RESET_ALL}")
        return

    # Print decisions for each ticker
    for ticker, decision in decisions.items():
        print(f"\n{Fore.WHITE}{Style.BRIGHT}Analysis for {Fore.CYAN}{ticker}{Style.RESET_ALL}")
        print(f"{Fore.WHITE}{Style.BRIGHT}{'=' * 50}{Style.RESET_ALL}")

        # Prepare analyst signals table for this ticker
        table_data = []
        for agent, signals in result.get("analyst_signals", {}).items():
            if ticker not in signals:
                continue
                
            # Skip Risk Management agent in the signals section
            if agent == "risk_management_agent":
                continue

            signal = signals[ticker]
            agent_name = agent.replace("_agent", "").replace("_", " ").title()
            signal_type = signal.get("signal", "").upper()
            confidence = signal.get("confidence", 0)

            signal_color = {
                "BULLISH": Fore.GREEN,
                "BEARISH": Fore.RED,
                "NEUTRAL": Fore.YELLOW,
            }.get(signal_type, Fore.WHITE)
            
            # Get reasoning if available
            reasoning_str = ""
            if "reasoning" in signal and signal["reasoning"]:
                reasoning = signal["reasoning"]
                
                # Handle different types of reasoning (string, dict, etc.)
                if isinstance(reasoning, str):
                    reasoning_str = reasoning
                elif isinstance(reasoning, dict):
                    # Convert dict to string representation
                    reasoning_str = json.dumps(reasoning, indent=2)
                else:
                    # Convert any other type to string
                    reasoning_str = str(reasoning)
                
                # Wrap long reasoning text to make it more readable
                wrapped_reasoning = ""
                current_line = ""
                # Use a fixed width of 60 characters to match the table column width
                max_line_length = 60
                for word in reasoning_str.split():
                    if len(current_line) + len(word) + 1 > max_line_length:
                        wrapped_reasoning += current_line + "\n"
                        current_line = word
                    else:
                        if current_line:
                            current_line += " " + word
                        else:
                            current_line = word
                if current_line:
                    wrapped_reasoning += current_line
                
                reasoning_str = wrapped_reasoning

            table_data.append(
                [
                    f"{Fore.CYAN}{agent_name}{Style.RESET_ALL}",
                    f"{signal_color}{signal_type}{Style.RESET_ALL}",
                    f"{Fore.WHITE}{confidence}%{Style.RESET_ALL}",
                    f"{Fore.WHITE}{reasoning_str}{Style.RESET_ALL}",
                ]
            )

        # Sort the signals according to the predefined order
        table_data = sort_agent_signals(table_data)

        print(f"\n{Fore.WHITE}{Style.BRIGHT}AGENT ANALYSIS:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
        print(
            tabulate(
                table_data,
                headers=[f"{Fore.WHITE}Agent", "Signal", "Confidence", "Reasoning"],
                tablefmt="grid",
                colalign=("left", "center", "right", "left"),
            )
        )

        # Print Trading Decision Table
        action = decision.get("action", "").upper()
        action_color = {
            "LONG": Fore.GREEN,
            "SHORT": Fore.RED,
            "HOLD": Fore.YELLOW,
            # 保持向后兼容
            "BUY": Fore.GREEN,
            "SELL": Fore.RED,
            "COVER": Fore.GREEN,
        }.get(action, Fore.WHITE)

        # Get reasoning and format it
        reasoning = decision.get("reasoning", "")
        # Wrap long reasoning text to make it more readable
        wrapped_reasoning = ""
        if reasoning:
            current_line = ""
            # Use a fixed width of 60 characters to match the table column width
            max_line_length = 60
            for word in reasoning.split():
                if len(current_line) + len(word) + 1 > max_line_length:
                    wrapped_reasoning += current_line + "\n"
                    current_line = word
                else:
                    if current_line:
                        current_line += " " + word
                    else:
                        current_line = word
            if current_line:
                wrapped_reasoning += current_line

        # 根据新的决策格式调整显示内容
        if "quantity" in decision:
            # 旧格式：包含数量
            decision_data = [
                ["Action", f"{action_color}{action}{Style.RESET_ALL}"],
                ["Quantity", f"{action_color}{decision.get('quantity')}{Style.RESET_ALL}"],
                [
                    "Confidence",
                    f"{Fore.WHITE}{decision.get('confidence'):.1f}%{Style.RESET_ALL}",
                ],
                ["Reasoning", f"{Fore.WHITE}{wrapped_reasoning}{Style.RESET_ALL}"],
            ]
        else:
            # 新格式：只有方向决策
            decision_data = [
                ["Action", f"{action_color}{action}{Style.RESET_ALL}"],
                [
                    "Confidence",
                    f"{Fore.WHITE}{decision.get('confidence'):.1f}%{Style.RESET_ALL}",
                ],
                ["Reasoning", f"{Fore.WHITE}{wrapped_reasoning}{Style.RESET_ALL}"],
            ]
        
        print(f"\n{Fore.WHITE}{Style.BRIGHT}TRADING DECISION:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
        print(tabulate(decision_data, tablefmt="grid", colalign=("left", "left")))

    # Print Portfolio Summary
    print(f"\n{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY:{Style.RESET_ALL}")
    portfolio_data = []
    
    # Extract portfolio manager reasoning (common for all tickers)
    portfolio_manager_reasoning = None
    for ticker, decision in decisions.items():
        if decision.get("reasoning"):
            portfolio_manager_reasoning = decision.get("reasoning")
            break
            
    for ticker, decision in decisions.items():
        action = decision.get("action", "").upper()
        action_color = {
            "LONG": Fore.GREEN,
            "SHORT": Fore.RED,
            "HOLD": Fore.YELLOW,
            # 保持向后兼容
            "BUY": Fore.GREEN,
            "SELL": Fore.RED,
            "COVER": Fore.GREEN,
        }.get(action, Fore.WHITE)
        
        # 根据新旧格式调整显示内容
        if "quantity" in decision:
            # 旧格式：包含数量
            portfolio_data.append(
                [
                    f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
                    f"{action_color}{action}{Style.RESET_ALL}",
                    f"{action_color}{decision.get('quantity')}{Style.RESET_ALL}",
                    f"{Fore.WHITE}{decision.get('confidence'):.1f}%{Style.RESET_ALL}",
                ]
            )
        else:
            # 新格式：只有方向决策
            portfolio_data.append(
                [
                    f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
                    f"{action_color}{action}{Style.RESET_ALL}",
                    f"{Fore.WHITE}{decision.get('confidence'):.1f}%{Style.RESET_ALL}",
                ]
            )

    # 根据数据格式调整表头
    if portfolio_data and len(portfolio_data[0]) == 4:
        # 旧格式：包含数量列
        headers = [f"{Fore.WHITE}Ticker", "Action", "Quantity", "Confidence"]
        colalign = ("left", "center", "right", "right")
    else:
        # 新格式：只有方向决策
        headers = [f"{Fore.WHITE}Ticker", "Action", "Confidence"]
        colalign = ("left", "center", "right")
    
    # Print the portfolio summary table
    print(
        tabulate(
            portfolio_data,
            headers=headers,
            tablefmt="grid",
            colalign=colalign,
        )
    )
    
    # Print Portfolio Manager's reasoning if available
    if portfolio_manager_reasoning:
        # Handle different types of reasoning (string, dict, etc.)
        reasoning_str = ""
        if isinstance(portfolio_manager_reasoning, str):
            reasoning_str = portfolio_manager_reasoning
        elif isinstance(portfolio_manager_reasoning, dict):
            # Convert dict to string representation
            reasoning_str = json.dumps(portfolio_manager_reasoning, indent=2)
        else:
            # Convert any other type to string
            reasoning_str = str(portfolio_manager_reasoning)
            
        # Wrap long reasoning text to make it more readable
        wrapped_reasoning = ""
        current_line = ""
        # Use a fixed width of 60 characters to match the table column width
        max_line_length = 60
        for word in reasoning_str.split():
            if len(current_line) + len(word) + 1 > max_line_length:
                wrapped_reasoning += current_line + "\n"
                current_line = word
            else:
                if current_line:
                    current_line += " " + word
                else:
                    current_line = word
        if current_line:
            wrapped_reasoning += current_line
            
        print(f"\n{Fore.WHITE}{Style.BRIGHT}Portfolio Strategy:{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{wrapped_reasoning}{Style.RESET_ALL}")


def print_backtest_results(table_rows: list) -> None:
    """Print the backtest results in a nicely formatted table"""
    # Clear the screen
    os.system("cls" if os.name == "nt" else "clear")

    # Split rows into ticker rows and summary rows
    ticker_rows = []
    summary_rows = []

    for row in table_rows:
        if isinstance(row[1], str) and "PORTFOLIO SUMMARY" in row[1]:
            summary_rows.append(row)
        else:
            ticker_rows.append(row)

    
    # Display latest portfolio summary
    if summary_rows:
        latest_summary = summary_rows[-1]
        print(f"\n{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY:{Style.RESET_ALL}")

        # Extract values and remove commas before converting to float
        cash_str = latest_summary[7].split("$")[1].split(Style.RESET_ALL)[0].replace(",", "")
        position_str = latest_summary[6].split("$")[1].split(Style.RESET_ALL)[0].replace(",", "")
        total_str = latest_summary[8].split("$")[1].split(Style.RESET_ALL)[0].replace(",", "")

        print(f"Cash Balance: {Fore.CYAN}${float(cash_str):,.2f}{Style.RESET_ALL}")
        print(f"Total Position Value: {Fore.YELLOW}${float(position_str):,.2f}{Style.RESET_ALL}")
        print(f"Total Value: {Fore.WHITE}${float(total_str):,.2f}{Style.RESET_ALL}")
        print(f"Return: {latest_summary[9]}")
        
        # Display performance metrics if available
        if latest_summary[10]:  # Sharpe ratio
            print(f"Sharpe Ratio: {latest_summary[10]}")
        if latest_summary[11]:  # Sortino ratio
            print(f"Sortino Ratio: {latest_summary[11]}")
        if latest_summary[12]:  # Max drawdown
            print(f"Max Drawdown: {latest_summary[12]}")

    # Add vertical spacing
    print("\n" * 2)

    # Print the table with just ticker rows
    print(
        tabulate(
            ticker_rows,
            headers=[
                "Date",
                "Ticker",
                "Action",
                "Quantity",
                "Price",
                "Shares",
                "Position Value",
                "Bullish",
                "Bearish",
                "Neutral",
            ],
            tablefmt="grid",
            colalign=(
                "left",  # Date
                "left",  # Ticker
                "center",  # Action
                "right",  # Quantity
                "right",  # Price
                "right",  # Shares
                "right",  # Position Value
                "right",  # Bullish
                "right",  # Bearish
                "right",  # Neutral
            ),
        )
    )

    # Add vertical spacing
    print("\n" * 4)


def print_individual_stock_performance(stock_performance: dict) -> None:
    """打印每只股票的单独绩效指标"""
    if not stock_performance:
        print(f"{Fore.YELLOW}没有单只股票绩效数据{Style.RESET_ALL}")
        return
    
    print(f"\n{Fore.WHITE}{Style.BRIGHT}单只股票绩效分析:{Style.RESET_ALL}")
    print(f"{Fore.WHITE}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}")
    
    # 准备表格数据
    table_data = []
    
    for ticker, performance in stock_performance.items():
        if "error" in performance:
            table_data.append([
                f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
                f"{Fore.RED}错误{Style.RESET_ALL}",
                "-", "-", "-", "-", "-", "-", "-"
            ])
            continue
            
        # 格式化绩效数据
        total_return = performance.get("total_return_pct", 0)
        mean_daily_return = performance.get("mean_daily_return_pct", 0)
        volatility = performance.get("volatility_pct", 0)
        sharpe = performance.get("sharpe_ratio", 0)
        max_dd = performance.get("max_drawdown_pct", 0)
        
        # 决策统计
        total_decisions = performance.get("total_decisions", 0)
        long_decisions = performance.get("long_decisions", 0)
        short_decisions = performance.get("short_decisions", 0)
        hold_decisions = performance.get("hold_decisions", 0)
        avg_confidence = performance.get("avg_confidence", 0)
        
        # 颜色编码
        return_color = Fore.GREEN if total_return >= 0 else Fore.RED
        sharpe_color = Fore.GREEN if sharpe >= 0 else Fore.RED
        
        table_data.append([
            f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
            f"{return_color}{total_return:+.2f}%{Style.RESET_ALL}",
            f"{Fore.WHITE}{mean_daily_return:+.4f}%{Style.RESET_ALL}",
            f"{Fore.YELLOW}{volatility:.2f}%{Style.RESET_ALL}",
            f"{sharpe_color}{sharpe:.3f}{Style.RESET_ALL}",
            f"{Fore.RED}{max_dd:.2f}%{Style.RESET_ALL}",
            f"{Fore.WHITE}{total_decisions}{Style.RESET_ALL}",
            f"{Fore.GREEN}{long_decisions}{Style.RESET_ALL}/{Fore.RED}{short_decisions}{Style.RESET_ALL}/{Fore.BLUE}{hold_decisions}{Style.RESET_ALL}",
            f"{Fore.WHITE}{avg_confidence:.1f}%{Style.RESET_ALL}"
        ])
    
    headers = [
        f"{Fore.WHITE}股票",
        "总收益",
        "日均收益",
        "波动率",
        "夏普比率",
        "最大回撤",
        "总决策",
        "Long/Short/Hold",
        "平均信心"
    ]
    
    print(
        tabulate(
            table_data,
            headers=headers,
            tablefmt="grid",
            colalign=(
                "left",   # 股票
                "right",  # 总收益
                "right",  # 日均收益
                "right",  # 波动率
                "right",  # 夏普比率
                "right",  # 最大回撤
                "center", # 总决策
                "center", # Long/Short/Hold
                "right",  # 平均信心
            ),
        )
    )
    
    print(f"\n{Fore.YELLOW}说明:{Style.RESET_ALL}")
    print(f"- 总收益: 整个分析期间的累计收益率")
    print(f"- 日均收益: 平均每日收益率")
    print(f"- 波动率: 年化波动率")
    print(f"- 夏普比率: 风险调整后收益指标")
    print(f"- 最大回撤: 从峰值到谷值的最大跌幅")
    print(f"- Long/Short/Hold: 做多/做空/持有决策次数")
    print(f"- 平均信心: 决策的平均置信度")


def format_backtest_row(
    date: str,
    ticker: str,
    action: str,
    quantity: float,
    price: float,
    shares_owned: float,
    position_value: float,
    bullish_count: int,
    bearish_count: int,
    neutral_count: int,
    is_summary: bool = False,
    total_value: float = None,
    return_pct: float = None,
    cash_balance: float = None,
    total_position_value: float = None,
    sharpe_ratio: float = None,
    sortino_ratio: float = None,
    max_drawdown: float = None,
) -> list[any]:
    """Format a row for the backtest results table"""
    # Color the action
    action_color = {
        "LONG": Fore.GREEN,
        "SHORT": Fore.RED,
        "HOLD": Fore.WHITE,
        # 保持向后兼容
        "BUY": Fore.GREEN,
        "COVER": Fore.GREEN,
        "SELL": Fore.RED,
    }.get(action.upper(), Fore.WHITE)

    if is_summary:
        return_color = Fore.GREEN if return_pct >= 0 else Fore.RED
        return [
            date,
            f"{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY{Style.RESET_ALL}",
            "",  # Action
            "",  # Quantity
            "",  # Price
            "",  # Shares
            f"{Fore.YELLOW}${total_position_value:,.2f}{Style.RESET_ALL}",  # Total Position Value
            f"{Fore.CYAN}${cash_balance:,.2f}{Style.RESET_ALL}",  # Cash Balance
            f"{Fore.WHITE}${total_value:,.2f}{Style.RESET_ALL}",  # Total Value
            f"{return_color}{return_pct:+.2f}%{Style.RESET_ALL}",  # Return
            f"{Fore.YELLOW}{sharpe_ratio:.2f}{Style.RESET_ALL}" if sharpe_ratio is not None else "",  # Sharpe Ratio
            f"{Fore.YELLOW}{sortino_ratio:.2f}{Style.RESET_ALL}" if sortino_ratio is not None else "",  # Sortino Ratio
            f"{Fore.RED}{abs(max_drawdown):.2f}%{Style.RESET_ALL}" if max_drawdown is not None else "",  # Max Drawdown
        ]
    else:
        return [
            date,
            f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
            f"{action_color}{action.upper()}{Style.RESET_ALL}",
            f"{action_color}{quantity:,.0f}{Style.RESET_ALL}",
            f"{Fore.WHITE}{price:,.2f}{Style.RESET_ALL}",
            f"{Fore.WHITE}{shares_owned:,.0f}{Style.RESET_ALL}",
            f"{Fore.YELLOW}{position_value:,.2f}{Style.RESET_ALL}",
            f"{Fore.GREEN}{bullish_count}{Style.RESET_ALL}",
            f"{Fore.RED}{bearish_count}{Style.RESET_ALL}",
            f"{Fore.BLUE}{neutral_count}{Style.RESET_ALL}",
        ]
