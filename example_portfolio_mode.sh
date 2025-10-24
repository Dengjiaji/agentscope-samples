#!/bin/bash
# Portfolio模式示例脚本

echo "==================================="
echo "Portfolio模式示例"
echo "==================================="
echo ""
echo "本示例将运行Portfolio模式进行为期一周的投资组合管理"
echo ""

# 示例1：基本Portfolio模式运行
echo "示例1：基本Portfolio模式（默认配置）"
echo "命令："
echo "python main_multi_day.py \\"
echo "  --tickers AAPL,MSFT \\"
echo "  --start-date 2024-01-02 \\"
echo "  --end-date 2024-01-08 \\"
echo "  --mode portfolio"
echo ""
read -p "按Enter键运行示例1..."
# python main_multi_day.py --tickers AAPL,MSFT --start-date 2024-01-02 --end-date 2024-01-08 --mode portfolio

echo ""
echo "==================================="
echo ""

# 示例2：自定义初始资金的Portfolio模式
echo "示例2：自定义初始资金（$200,000）"
echo "命令："
echo "python main_multi_day.py \\"
echo "  --tickers AAPL,MSFT,GOOGL \\"
echo "  --start-date 2024-01-02 \\"
echo "  --end-date 2024-01-08 \\"
echo "  --mode portfolio \\"
echo "  --initial-cash 200000"
echo ""
read -p "按Enter键运行示例2..."
# python main_multi_day.py --tickers AAPL,MSFT,GOOGL --start-date 2024-01-02 --end-date 2024-01-08 --mode portfolio --initial-cash 200000

echo ""
echo "==================================="
echo ""

# 示例3：Signal模式对比
echo "示例3：Signal模式（用于对比）"
echo "命令："
echo "python main_multi_day.py \\"
echo "  --tickers AAPL,MSFT \\"
echo "  --start-date 2024-01-02 \\"
echo "  --end-date 2024-01-08 \\"
echo "  --mode signal"
echo ""
read -p "按Enter键运行示例3..."
# python main_multi_day.py --tickers AAPL,MSFT --start-date 2024-01-02 --end-date 2024-01-08 --mode signal

echo ""
echo "==================================="
echo "所有示例命令已准备好"
echo "请取消注释要运行的命令"
echo "==================================="

