#!/bin/bash
# 一键部署和运行脚本
# 
# 使用方法:
#   ./deploy.sh                    # 完整部署并启动所有服务
#   ./deploy.sh --setup-only       # 仅安装依赖，不启动服务
#   ./deploy.sh --backend-only     # 仅启动后端
#   ./deploy.sh --frontend-only    # 仅启动前端
#   ./deploy.sh --mock             # Mock模式启动

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 解析参数
SETUP_ONLY=false
BACKEND_ONLY=false
FRONTEND_ONLY=false
MOCK_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --setup-only)
            SETUP_ONLY=true
            shift
            ;;
        --backend-only)
            BACKEND_ONLY=true
            shift
            ;;
        --frontend-only)
            FRONTEND_ONLY=true
            shift
            ;;
        --mock)
            MOCK_MODE=true
            shift
            ;;
        *)
            echo -e "${RED}⚠️  未知参数: $1${NC}"
            shift
            ;;
    esac
done

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        🚀 IA Trading System - 一键部署脚本             ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# 1. 检查并安装 uv
# ============================================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}📦 步骤 1/5: 检查 Python 包管理器 (uv)${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if command -v uv &> /dev/null; then
    UV_VERSION=$(uv --version)
    echo -e "${GREEN}✅ uv 已安装: $UV_VERSION${NC}"
else
    echo -e "${YELLOW}⚠️  uv 未安装，正在安装...${NC}"
    
    # 检测操作系统
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            echo "   使用 Homebrew 安装 uv..."
            brew install uv
        else
            echo "   使用 curl 安装 uv..."
            curl -LsSf https://astral.sh/uv/install.sh | sh
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        echo "   使用 curl 安装 uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
    else
        echo -e "${RED}❌ 不支持的操作系统: $OSTYPE${NC}"
        echo "   请手动安装 uv: https://github.com/astral-sh/uv"
        exit 1
    fi
    
    # 刷新环境变量
    export PATH="$HOME/.cargo/bin:$PATH"
    
    if command -v uv &> /dev/null; then
        echo -e "${GREEN}✅ uv 安装成功${NC}"
    else
        echo -e "${RED}❌ uv 安装失败，请手动安装${NC}"
        exit 1
    fi
fi

echo ""

# ============================================================================
# 2. 使用 uv 安装 Backend 依赖
# ============================================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}📦 步骤 2/5: 安装 Backend 依赖${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}❌ 错误: requirements.txt 不存在${NC}"
    exit 1
fi

echo "📋 使用 uv 安装 Python 依赖..."
echo "   文件: requirements.txt"
echo ""

# 检查是否存在虚拟环境
if [ ! -d ".venv" ]; then
    echo "🔨 创建虚拟环境..."
    uv venv
    echo -e "${GREEN}✅ 虚拟环境创建成功${NC}"
fi

# 激活虚拟环境并安装依赖
echo "📥 安装依赖包..."
source .venv/bin/activate
uv pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Backend 依赖安装成功${NC}"
else
    echo -e "${RED}❌ Backend 依赖安装失败${NC}"
    exit 1
fi

echo ""

# ============================================================================
# 3. 检查并安装 Node.js 和 npm
# ============================================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}📦 步骤 3/5: 检查 Node.js 和 npm${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✅ Node.js 已安装: $NODE_VERSION${NC}"
else
    echo -e "${RED}❌ Node.js 未安装${NC}"
    echo ""
    echo "请安装 Node.js:"
    echo "  macOS:   brew install node"
    echo "  Ubuntu:  sudo apt install nodejs npm"
    echo "  其他:    https://nodejs.org/"
    exit 1
fi

if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    echo -e "${GREEN}✅ npm 已安装: $NPM_VERSION${NC}"
else
    echo -e "${RED}❌ npm 未安装${NC}"
    echo "请安装 npm (通常随 Node.js 一起安装)"
    exit 1
fi

echo ""

# ============================================================================
# 4. 安装 Frontend 依赖
# ============================================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}📦 步骤 4/5: 安装 Frontend 依赖${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ ! -d "frontend" ]; then
    echo -e "${RED}❌ 错误: frontend 目录不存在${NC}"
    exit 1
fi

cd frontend

if [ ! -f "package.json" ]; then
    echo -e "${RED}❌ 错误: package.json 不存在${NC}"
    exit 1
fi

echo "📥 安装 npm 依赖..."
npm install

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Frontend 依赖安装成功${NC}"
else
    echo -e "${RED}❌ Frontend 依赖安装失败${NC}"
    exit 1
fi

cd ..

echo ""

# ============================================================================
# 5. 检查环境配置
# ============================================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}📦 步骤 5/5: 检查环境配置${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# 检查后端 .env 文件
if [ ! -f ".env" ]; then
    if [ -f "env.template" ]; then
        echo -e "${YELLOW}⚠️  .env 文件不存在，从模板复制...${NC}"
        cp env.template .env
        echo -e "${GREEN}✅ 已创建 .env 文件${NC}"
        echo -e "${YELLOW}⚠️  请编辑 .env 文件并添加你的API密钥${NC}"
    else
        echo -e "${RED}❌ 警告: .env 和 env.template 文件都不存在${NC}"
    fi
else
    echo -e "${GREEN}✅ Backend .env 文件已存在${NC}"
fi

# 检查前端 .env 文件
if [ ! -f "frontend/.env" ]; then
    if [ -f "frontend/env.template" ]; then
        echo -e "${YELLOW}⚠️  Frontend .env 文件不存在，从模板复制...${NC}"
        cp frontend/env.template frontend/.env
        echo -e "${GREEN}✅ 已创建 Frontend .env 文件${NC}"
    fi
else
    echo -e "${GREEN}✅ Frontend .env 文件已存在${NC}"
fi

echo ""

# ============================================================================
# 部署完成
# ============================================================================
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              🎉 部署完成！                                ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# 如果只是安装依赖，到此结束
if [ "$SETUP_ONLY" = true ]; then
    echo -e "${BLUE}ℹ️  仅安装依赖模式，未启动服务${NC}"
    echo ""
    echo "要启动服务，运行："
    echo "  ./deploy.sh                  # 启动所有服务"
    echo "  ./deploy.sh --backend-only   # 仅启动后端"
    echo "  ./deploy.sh --frontend-only  # 仅启动前端"
    exit 0
fi

# ============================================================================
# 启动服务
# ============================================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🚀 启动服务${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 激活虚拟环境
source .venv/bin/activate

if [ "$FRONTEND_ONLY" = true ]; then
    # 仅启动前端
    echo -e "${BLUE}🌐 启动前端服务...${NC}"
    echo "   访问: http://localhost:5173"
    echo "   按 Ctrl+C 停止服务"
    echo ""
    cd frontend
    npm run dev
    
elif [ "$BACKEND_ONLY" = true ]; then
    # 仅启动后端
    echo -e "${BLUE}🖥️  启动后端服务...${NC}"
    echo "   WebSocket: ws://localhost:8765"
    echo "   按 Ctrl+C 停止服务"
    echo ""
    
    if [ "$MOCK_MODE" = true ]; then
        sh start_server.sh --mock
    else
        sh start_server.sh
    fi
    
else
    # 启动所有服务（在后台启动后端，前台启动前端）
    echo -e "${BLUE}🖥️  启动后端服务（后台运行）...${NC}"
    
    # 创建日志目录
    mkdir -p logs
    
    # 启动后端（后台运行）
    if [ "$MOCK_MODE" = true ]; then
        nohup sh start_server.sh --mock > logs/backend.log 2>&1 &
    else
        nohup sh start_server.sh > logs/backend.log 2>&1 &
    fi
    BACKEND_PID=$!
    
    echo -e "${GREEN}✅ 后端服务已启动 (PID: $BACKEND_PID)${NC}"
    echo "   WebSocket: ws://localhost:8765"
    echo "   日志文件: logs/backend.log"
    echo ""
    
    # 等待后端启动
    echo "⏳ 等待后端服务启动..."
    sleep 5
    
    # 检查后端是否成功启动
    if kill -0 $BACKEND_PID 2>/dev/null; then
        echo -e "${GREEN}✅ 后端服务运行正常${NC}"
    else
        echo -e "${RED}❌ 后端服务启动失败，请检查日志文件${NC}"
        cat logs/backend.log
        exit 1
    fi
    
    echo ""
    echo -e "${BLUE}🌐 启动前端服务...${NC}"
    echo "   访问: http://localhost:5173"
    echo "   按 Ctrl+C 停止所有服务"
    echo ""
    
    # 设置清理函数
    cleanup() {
        echo ""
        echo -e "${YELLOW}🛑 正在停止服务...${NC}"
        if kill -0 $BACKEND_PID 2>/dev/null; then
            kill $BACKEND_PID
            echo -e "${GREEN}✅ 后端服务已停止${NC}"
        fi
        exit 0
    }
    
    # 捕获 Ctrl+C 信号
    trap cleanup INT TERM
    
    # 启动前端（前台运行）
    cd frontend
    npm run dev
    
    # 如果前端退出，清理后端
    cleanup
fi

