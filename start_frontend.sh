#!/bin/bash
# 启动前端开发服务器
# 
# 使用方法:
#   ./start_frontend.sh                    # 连接到默认端口 8765
#   ./start_frontend.sh --port 9876         # 连接到指定端口 9876
#   ./start_frontend.sh --host              # 允许外部访问（默认只允许 localhost）

set -e

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "$0" )" && pwd )"
cd "$SCRIPT_DIR"

# 默认配置
WS_PORT=8765
HOST_MODE=false

# 解析参数
while [ $# -gt 0 ]; do
    case $1 in
        --port)
            WS_PORT="$2"
            shift 2
            ;;
        --host)
            HOST_MODE=true
            shift
            ;;
        --help)
            echo "前端启动脚本"
            echo ""
            echo "使用方法:"
            echo "  $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --port PORT      WebSocket 服务器端口（默认: 8765）"
            echo "  --host           允许外部访问（默认: 仅 localhost）"
            echo "  --help           显示此帮助信息"
            echo ""
            echo "示例:"
            echo "  $0                           # 连接到端口 8765"
            echo "  $0 --port 9876               # 连接到端口 9876"
            echo "  $0 --port 9876 --host        # 连接到端口 9876，允许外部访问"
            exit 0
            ;;
        *)
            echo "❌ 未知参数: $1"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

# 检查前端目录
FRONTEND_DIR="$SCRIPT_DIR/frontend"
if [ ! -d "$FRONTEND_DIR" ]; then
    echo "❌ 前端目录不存在: $FRONTEND_DIR"
    exit 1
fi

# 检查 node_modules
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "📦 检测到未安装依赖，正在安装..."
    cd "$FRONTEND_DIR"
    npm install
    cd "$SCRIPT_DIR"
fi

# 设置 WebSocket URL 环境变量
export VITE_WS_URL="ws://localhost:${WS_PORT}"

echo ""
echo "=========================================="
echo "🌐 启动前端开发服务器"
echo "=========================================="
echo ""
echo "📊 配置信息:"
echo "   WebSocket 地址: ${VITE_WS_URL}"
echo "   前端端口: 5173 (Vite 默认)"
if [ "$HOST_MODE" = true ]; then
    echo "   访问模式: 允许外部访问"
else
    echo "   访问模式: 仅本地访问"
fi
echo ""
echo "💡 提示:"
echo "   1. 确保后端服务器已启动在端口 ${WS_PORT}"
echo "   2. 前端将在 http://localhost:5173 启动"
if [ "$HOST_MODE" = true ]; then
    echo "   3. 外部可通过本机 IP 访问"
fi
echo "   4. 按 Ctrl+C 停止服务器"
echo ""

# 切换到前端目录并启动
cd "$FRONTEND_DIR"

if [ "$HOST_MODE" = true ]; then
    npm run dev:host
else
    npm run dev
fi

