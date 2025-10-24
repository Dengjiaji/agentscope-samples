#!/bin/bash
# Live Trading Thinking Fund - Portfolio模式示例脚本

echo "========================================="
echo "Live Trading Portfolio Mode 使用示例"
echo "========================================="

# 配置名称（必需）
CONFIG_NAME="your_config_name"

# ==========================================
# 示例1：单日Portfolio模式（使用.env配置）
# ==========================================
echo ""
echo "示例1：单日Portfolio模式（从.env读取配置）"
echo "-----------------------------------------"
echo "确保.env文件中已设置："
echo "  MODE=portfolio"
echo "  INITIAL_CASH=100000.0"
echo "  MARGIN_REQUIREMENT=0.0"
echo ""
echo "运行命令："
echo "python live_trading_thinking_fund.py \\"
echo "  --config_name $CONFIG_NAME \\"
echo "  --date 2024-01-15"
echo ""

# ==========================================
# 示例2：单日Portfolio模式（命令行参数）
# ==========================================
echo ""
echo "示例2：单日Portfolio模式（命令行参数覆盖）"
echo "-----------------------------------------"
echo "python live_trading_thinking_fund.py \\"
echo "  --config_name $CONFIG_NAME \\"
echo "  --date 2024-01-15 \\"
echo "  --mode portfolio \\"
echo "  --initial-cash 200000 \\"
echo "  --margin-requirement 0.0 \\"
echo "  --tickers AAPL,MSFT,GOOGL"
echo ""

# ==========================================
# 示例3：多日Portfolio模拟
# ==========================================
echo ""
echo "示例3：多日Portfolio模拟"
echo "-----------------------------------------"
echo "python live_trading_thinking_fund.py \\"
echo "  --config_name $CONFIG_NAME \\"
echo "  --start-date 2024-01-01 \\"
echo "  --end-date 2024-01-31 \\"
echo "  --mode portfolio \\"
echo "  --initial-cash 100000 \\"
echo "  --tickers AAPL,MSFT"
echo ""

# ==========================================
# 示例4：Portfolio模式启用做空
# ==========================================
echo ""
echo "示例4：Portfolio模式启用做空（50%保证金）"
echo "-----------------------------------------"
echo "⚠️  谨慎使用！默认禁用做空（margin_requirement=0.0）"
echo ""
echo "python live_trading_thinking_fund.py \\"
echo "  --config_name $CONFIG_NAME \\"
echo "  --date 2024-01-15 \\"
echo "  --mode portfolio \\"
echo "  --initial-cash 100000 \\"
echo "  --margin-requirement 0.5 \\"  
echo "  --tickers AAPL,MSFT"
echo ""

# ==========================================
# 示例5：Signal模式（传统模式）
# ==========================================
echo ""
echo "示例5：Signal模式（传统信号输出）"
echo "-----------------------------------------"
echo "python live_trading_thinking_fund.py \\"
echo "  --config_name $CONFIG_NAME \\"
echo "  --date 2024-01-15 \\"
echo "  --mode signal \\"
echo "  --tickers AAPL,MSFT"
echo ""

# ==========================================
# .env配置示例
# ==========================================
echo ""
echo "========================================="
echo ".env文件配置示例"
echo "========================================="
cat << 'EOF'
# ==========================================
# 运行模式
# ==========================================
MODE=portfolio  # signal 或 portfolio

# ==========================================
# 股票代码
# ==========================================
TICKERS=AAPL,MSFT,GOOGL

# ==========================================
# Portfolio模式配置
# ==========================================
INITIAL_CASH=100000.0
MARGIN_REQUIREMENT=0.0  # 0.0=禁用做空, 0.5=50%保证金

# ==========================================
# Live Trading配置
# ==========================================
LIVE_MAX_COMM_CYCLES=2
DISABLE_COMMUNICATIONS=false
DISABLE_NOTIFICATIONS=false
FORCE_RUN=false

# ==========================================
# API Keys（根据需要配置）
# ==========================================
OPENAI_API_KEY=your_openai_key
FINANCIAL_DATASETS_API_KEY=your_fd_key

EOF

echo ""
echo "========================================="
echo "预期输出示例"
echo "========================================="
echo ""
echo "Portfolio模式："
echo "  ✅ 记忆系统已初始化: LangChain"
echo "  📊 Live Trading Thinking Fund 配置:"
echo "     运行模式: PORTFOLIO"
echo "     初始现金: \$100,000.00"
echo "     保证金要求: 0.0%"
echo "  开始分析 2024-01-15 的策略... (模式: portfolio)"
echo "  ✅ Risk Manager输出仓位限制"
echo "  ✅ Portfolio Manager输出交易决策（buy/sell + quantity）"
echo "  ✅ 执行交易，更新持仓"
echo ""

echo "========================================="
echo "注意事项"
echo "========================================="
echo "1. 确保已设置必要的API keys"
echo "2. Portfolio模式默认禁用做空（安全）"
echo "3. 如需启用做空，明确设置margin_requirement"
echo "4. 配置文件(.env)和命令行参数可以组合使用"
echo "5. 命令行参数优先级高于.env配置"
echo ""

