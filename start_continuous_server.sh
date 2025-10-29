#!/bin/bash
# 启动持续运行服务器的便捷脚本
# 
# 使用方法:
#   ./start_continuous_server.sh              # 正常模式
#   ./start_continuous_server.sh --mock       # Mock模式（测试前端）

set -e

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 解析参数
MODE="normal"
if [ "$1" = "--mock" ]; then
    MODE="mock"
fi

if [ "$MODE" = "mock" ]; then
    echo "🎭 启动 Mock Mode - 测试模式"
else
    echo "🚀 启动 Live Trading Intelligence System - Continuous Server"
fi
echo "=================================================="

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "❌ 虚拟环境不存在，请先运行: python3 -m venv venv"
    exit 1
fi

# 激活虚拟环境
source venv/bin/activate

# 正常模式需要检查.env文件，mock模式不需要
if [ "$MODE" = "normal" ]; then
    # 检查.env文件
    if [ ! -f ".env" ]; then
        echo "⚠️  .env 文件不存在，从模板复制..."
        cp env.template .env
        echo "✅ 已创建 .env 文件，请编辑并添加你的API密钥"
        exit 1
    fi
fi

# 检查必需的依赖
echo "📦 检查依赖..."
pip install -q websocket-client websockets

# 显示配置信息
echo ""
echo "📊 当前配置:"
if [ "$MODE" = "mock" ]; then
    echo "   模式: 🎭 MOCK (模拟数据)"
    echo "   说明: 用于测试前端，不需要真实数据和API密钥"
else
    echo "   模式: 🚀 NORMAL (真实交易)"
    echo "   配置目录: ${CONFIG_NAME:-continuous}"
fi
echo "   WebSocket端口: 8765"
echo ""

# 启动服务器
echo "🌐 启动服务器..."
echo "   访问: http://localhost:8765"
echo "   按 Ctrl+C 停止服务器"
echo ""

if [ "$MODE" = "mock" ]; then
    python -m src.servers.continuous_server --mock
else
    python -m src.servers.continuous_server
fi

