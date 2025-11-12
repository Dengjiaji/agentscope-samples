#!/bin/bash
# 启动在线交易模式的便捷脚本
# 
# 功能说明：
# 1. 脚本启动后立即开始实时更新股票价格板
# 2. 从指定天数开始回测历史交易日，然后进入今天在线模式
# 3. 在线模式会高频获取实时价格，更新净值曲线、持仓盈亏等
# 4. 如果今天是交易日且在交易时段，系统会等到收盘后才执行交易
# 5. 支持Mock模式，用于非交易时段调试程序
#
# 使用方法:
#   ./start_live_server.sh                    # 正常模式（需要 FINNHUB_API_KEY）
#   ./start_live_server.sh --mock             # Mock模式（测试用虚拟价格）
#   ./start_live_server.sh --lookback-days 3  # 自定义回溯天数（默认: 7天）
#   ./start_live_server.sh --clean            # 清空历史记录重新开始
#   ./start_live_server.sh --help             # 显示帮助信息

set -e

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# ==================== 解析参数 ====================
MODE="live"
MOCK_MODE=false
LOOKBACK_DAYS=0  # 默认0天，不回测历史，直接运行当前交易日
AUTO_CLEAN=false
CONFIG_NAME="live_mode"
HOST="0.0.0.0"
PORT=8765
PAUSE_BEFORE_TRADE=false

show_help() {
    echo "在线交易模式启动脚本"
    echo ""
    echo "使用方法:"
    echo "  $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --mock                 使用Mock模式（虚拟价格，用于测试）"
    echo "  --lookback-days N      回溯天数（默认: 0，即不回测，直接运行今天）"
    echo "  --config-name NAME     配置名称（默认: live_mode）"
    echo "  --clean                清空历史记录"
    echo "  --host HOST            监听地址（默认: 0.0.0.0）"
    echo "  --port PORT            监听端口（默认: 8765"
    echo "  --pause-before-trade   暂停模式：完成分析但不执行交易，仅更新价格"
    echo "  --help                 显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                                    # 正常模式，直接运行今天"
    echo "  $0 --mock                             # Mock模式，直接运行今天"
    echo "  $0 --lookback-days 3                  # 回溯3天（如需历史回测）"
    echo "  $0 --pause-before-trade               # 暂停模式：分析完成后不执行交易"
    echo "  $0 --mock --lookback-days 0 --clean   # Mock模式，直接运行今天，清空历史"
    echo ""
    exit 0
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --mock)
            MOCK_MODE=true
            shift
            ;;
        --lookback-days)
            LOOKBACK_DAYS="$2"
            shift 2
            ;;
        --config-name)
            CONFIG_NAME="$2"
            shift 2
            ;;
        --clean)
            AUTO_CLEAN=true
            shift
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --pause-before-trade)
            PAUSE_BEFORE_TRADE=true
            shift
            ;;
        --help)
            show_help
            ;;
        *)
            echo "❌ 未知参数: $1"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

# ==================== 显示启动信息 ====================
echo ""
echo "=========================================="
if [ "$MOCK_MODE" = true ]; then
    echo "🎭 在线交易模式 - MOCK (虚拟价格测试)"
else
    echo "🚀 在线交易模式 - LIVE (实时价格)"
fi
echo "=========================================="
echo ""

# ==================== 环境检查 ====================
# 正常模式需要检查.env文件和API密钥
if [ "$MOCK_MODE" = false ]; then
    # 检查.env文件
    if [ ! -f ".env" ]; then
        echo "⚠️  .env 文件不存在，从模板复制..."
        cp env.template .env
        echo "✅ 已创建 .env 文件"
        echo ""
        echo "❌ 请编辑 .env 文件并设置以下必需的API密钥："
        echo "   - FINNHUB_API_KEY: 用于获取实时股票价格"
        echo ""
        echo "📝 获取 Finnhub API Key (免费):"
        echo "   1. 访问: https://finnhub.io/register"
        echo "   2. 注册账号"
        echo "   3. 复制 API Key 到 .env 文件"
        echo ""
        exit 1
    fi
    
    # 检查 FINNHUB_API_KEY
    source .env
    if [ -z "$FINNHUB_API_KEY" ] || [ "$FINNHUB_API_KEY" = "your-finnhub-api-key-here" ]; then
        echo "❌ 未设置有效的 FINNHUB_API_KEY"
        echo ""
        echo "请在 .env 文件中设置 FINNHUB_API_KEY"
        echo ""
        echo "📝 获取 Finnhub API Key (免费):"
        echo "   1. 访问: https://finnhub.io/register"
        echo "   2. 注册账号"
        echo "   3. 复制 API Key 到 .env 文件中的 FINNHUB_API_KEY 变量"
        echo ""
        exit 1
    fi
    
    echo "✅ FINNHUB_API_KEY 已配置"
fi

# ==================== 检查依赖 ====================
echo ""
echo "📦 检查Python依赖..."

# 检查必需的包
REQUIRED_PACKAGES="websocket-client websockets finnhub-python python-dotenv pandas"
pip install -q $REQUIRED_PACKAGES

# Mock模式不需要市场日历
if [ "$MOCK_MODE" = false ]; then
    echo "📦 安装市场日历（用于交易日检测）..."
    pip install -q pandas-market-calendars || {
        echo "⚠️  pandas-market-calendars 安装失败，将使用简化的交易日检测"
    }
fi

echo "✅ 依赖检查完成"

# ==================== 数据更新 ====================
if [ "$MOCK_MODE" = false ]; then
    echo ""
    echo "📊 检查历史数据更新..."
    
    if python -m src.data.ret_data_updater --help &> /dev/null; then
        echo "🔄 正在更新历史数据..."
        
        python -m src.data.ret_data_updater || {
            echo "⚠️  历史数据更新失败（可能是周末或假期），但将继续启动服务器"
            echo "💡 提示: 系统将使用现有历史数据运行"
        }
        
        if [ $? -eq 0 ]; then
            echo "✅ 历史数据更新完成"
        fi
    else
        echo "⚠️  数据更新模块未找到，跳过数据更新"
    fi
    echo ""
fi

# ==================== 历史记录管理 ====================
BASE_DATA_DIR="./logs_and_memory/${CONFIG_NAME}"

# 检查是否存在历史数据
CLEAN_HISTORY=false
if [ -d "$BASE_DATA_DIR" ] && [ "$(ls -A $BASE_DATA_DIR 2>/dev/null)" ]; then
    echo ""
    echo "🔍 检测到以往运行记录:"
    echo "   数据目录: $BASE_DATA_DIR"
    
    # 显示目录大小
    if command -v du &> /dev/null; then
        DIR_SIZE=$(du -sh "$BASE_DATA_DIR" 2>/dev/null | cut -f1)
        echo "   目录大小: $DIR_SIZE"
    fi
    
    # 显示最后修改时间
    if [ -d "$BASE_DATA_DIR/state" ]; then
        LAST_STATE=$(find "$BASE_DATA_DIR/state" -type f -name "*.json" 2>/dev/null | head -1)
        if [ -n "$LAST_STATE" ] && [ -f "$LAST_STATE" ]; then
            LAST_MODIFIED=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$LAST_STATE" 2>/dev/null || stat -c %y "$LAST_MODIFIED" 2>/dev/null | cut -d'.' -f1)
            echo "   最后更新: $LAST_MODIFIED"
        fi
    fi
    
    echo ""
    
    # 如果设置了自动清空，跳过询问
    if [ "$AUTO_CLEAN" = true ]; then
        echo "⚠️  已设置 --clean 参数，将清空历史记录"
        CLEAN_HISTORY=true
    else
        # 询问用户
        # while true; do
            # echo -n "❓ 是否清空历史记录，从头开始运行？(y/n) [默认: n]: "
            # read -r response
        CLEAN_HISTORY=false
    #         # 如果用户直接按回车，使用默认值'n'
    #         if [ -z "$response" ]; then
    #             response="n"
    #         fi
            
    #         case "$response" in
    #             [yY]|[yY][eE][sS])
    #                 CLEAN_HISTORY=true
    #                 break
    #                 ;;
    #             [nN]|[nN][oO])
    #                 CLEAN_HISTORY=false
    #                 break
    #                 ;;
    #             *)
    #                 echo "   ⚠️  无效输入，请输入 y 或 n"
    #                 ;;
    #         esac
        # done
    fi
    
    # 执行清空操作
    if [ "$CLEAN_HISTORY" = true ]; then
        echo ""
        echo "🗑️  正在清空历史记录..."
        
        # 备份重要配置文件（如果存在）
        BACKUP_DIR="${BASE_DATA_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
        if [ -d "$BASE_DATA_DIR" ]; then
            # 只备份配置文件，不备份所有数据
            if [ -f "$BASE_DATA_DIR/.env" ] || [ -f "$BASE_DATA_DIR/config.json" ]; then
                mkdir -p "$BACKUP_DIR"
                [ -f "$BASE_DATA_DIR/.env" ] && cp "$BASE_DATA_DIR/.env" "$BACKUP_DIR/"
                [ -f "$BASE_DATA_DIR/config.json" ] && cp "$BASE_DATA_DIR/config.json" "$BACKUP_DIR/"
                echo "   💾 配置文件已备份到: $BACKUP_DIR"
            fi
            
            # 删除整个目录
            rm -rf "$BASE_DATA_DIR"
            echo "   ✅ 历史记录已清空"
        fi
    else
        echo ""
        echo "📂 将在现有记录基础上继续运行"
    fi
else
    echo ""
    echo "📂 未检测到历史记录，将从头开始运行"
fi

# ==================== 显示配置信息 ====================
echo ""
echo "📊 运行配置:"
if [ "$MOCK_MODE" = true ]; then
    echo "   模式: 🎭 MOCK (虚拟价格，用于测试)"
    echo "   说明: 使用随机生成的价格，不需要API密钥"
else
    echo "   模式: 🚀 LIVE (实时价格，使用Finnhub API)"
    echo "   说明: 使用Finnhub Quote API高频获取实时价格"
fi
echo "   配置名称: ${CONFIG_NAME}"
echo "   回溯天数: ${LOOKBACK_DAYS} 天"
echo "   监听地址: ${HOST}:${PORT}"
if [ "$PAUSE_BEFORE_TRADE" = true ]; then
    echo "   交易模式: ⏸️ 暂停 (仅分析，不执行交易)"
else
    echo "   交易模式: ▶️ 正常 (分析后执行交易)"
fi
if [ "$CLEAN_HISTORY" = true ]; then
    echo "   历史记录: 已清空 🆕"
else
    echo "   历史记录: 继续使用 📚"
fi
echo ""

# ==================== 功能说明 ====================
echo "💡 功能说明:"
echo "   ✨ 启动后立即开始实时更新股票价格板"
if [ "$LOOKBACK_DAYS" -eq 0 ]; then
    echo "   1. 系统将直接运行今天的交易日（不回测历史）"
    echo "   2. 立即进行交易决策分析（不立即执行交易）"
else
    echo "   1. 系统将从 ${LOOKBACK_DAYS} 天前开始回测历史交易日"
    echo "   2. 到达今天后，进行交易决策分析（不立即执行交易）"
fi
if [ "$MOCK_MODE" = false ]; then
    echo "   3. 如果今天是交易日且在交易时段，系统会等到收盘后才执行交易"
    echo "   4. 实时价格每10秒更新一次（Finnhub Quote API）"
else
    echo "   3. Mock模式下每5秒生成虚拟价格更新"
fi
echo "   5. 实时更新: 股票价格、return、净值曲线、持仓盈亏"
echo ""

# ==================== 启动服务器 ====================
echo "🌐 启动在线交易服务器..."
echo "   访问: http://localhost:${PORT}"
echo "   按 Ctrl+C 停止服务器"
echo ""

# 构建命令
CMD="python -u src/servers/live_server.py"
CMD="$CMD --config-name $CONFIG_NAME"
CMD="$CMD --lookback-days $LOOKBACK_DAYS"
CMD="$CMD --host $HOST"
CMD="$CMD --port $PORT"

if [ "$MOCK_MODE" = true ]; then
    CMD="$CMD --mock"
fi

if [ "$PAUSE_BEFORE_TRADE" = true ]; then
    CMD="$CMD --pause-before-trade"
fi

# 执行命令
$CMD

