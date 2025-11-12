#!/bin/bash
# 启动持续运行服务器的便捷脚本
# 
# 使用方法:
#   ./start_server.sh              # 正常模式
#   ./start_server.sh --mock       # Mock模式（测试前端）
#   ./start_server.sh --clean      # 正常模式，自动清空历史记录

set -e

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 解析参数
MODE="normal"
AUTO_CLEAN=false
if [ "$1" = "--mock" ]; then
    MODE="mock"
elif [ "$1" = "--clean" ]; then
    AUTO_CLEAN=true
fi

if [ "$MODE" = "mock" ]; then
    echo "🎭 启动 Mock Mode - 测试模式"
else
    echo "🚀 启动 Live Trading Intelligence System - Continuous Server"
fi
echo "=================================================="


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

# 自动更新历史数据（仅在正常模式下）
if [ "$MODE" = "normal" ]; then
    echo ""
    echo "📊 检查历史数据更新..."
    
    # 检查是否需要更新数据
    if python -m src.data.ret_data_updater --help &> /dev/null; then
        echo "🔄 正在更新历史数据..."
        
        # 使用 || true 确保即使更新失败也继续运行
        python -m src.data.ret_data_updater || {
            echo "⚠️  历史数据更新失败（可能是周末或假期），但将继续启动服务器"
            echo "💡 提示: 系统将使用现有历史数据运行"
        }
        
        # 无论更新成功与否，都显示完成信息
        if [ $? -eq 0 ]; then
            echo "✅ 历史数据更新完成"
        fi
    else
        echo "⚠️  数据更新模块未安装，跳过数据更新"
    fi
    echo ""
fi

# 获取CONFIG_NAME（从.env文件或使用默认值）
CONFIG_NAME='mock'

# 正常模式下询问是否清空历史记录
CLEAN_HISTORY=false
if [ "$MODE" = "normal" ]; then
    BASE_DATA_DIR="./logs_and_memory/${CONFIG_NAME}"
    
    # 检查是否存在历史数据
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
                LAST_MODIFIED=$(stat -c %y "$LAST_STATE" 2>/dev/null | cut -d'.' -f1 || stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$LAST_STATE" 2>/dev/null)
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
            while true; do
                echo -n "❓ 是否清空历史记录，从头开始运行？(y/n) [默认: n]: "
                read -r response
                
                # 如果用户直接按回车，使用默认值'n'
                if [ -z "$response" ]; then
                    response="n"
                fi
                
                case "$response" in
                    [yY]|[yY][eE][sS])
                        CLEAN_HISTORY=true
                        break
                        ;;
                    [nN]|[nN][oO])
                        CLEAN_HISTORY=false
                        break
                        ;;
                    *)
                        echo "   ⚠️  无效输入，请输入 y 或 n"
                        ;;
                esac
            done
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
fi

# 显示配置信息
echo ""
echo "📊 当前配置:"
if [ "$MODE" = "mock" ]; then
    echo "   模式: 🎭 MOCK (模拟数据)"
    echo "   说明: 用于测试前端，不需要真实数据和API密钥"
else
    echo "   模式: 🚀 NORMAL (真实交易)"
    echo "   配置目录: ${CONFIG_NAME}"
    if [ "$CLEAN_HISTORY" = true ]; then
        echo "   历史记录: 已清空 🆕"
    else
        echo "   历史记录: 继续使用 📚"
    fi
fi
echo "   WebSocket端口: 8765"
echo ""

# 启动服务器
echo "🌐 启动服务器..."
echo "   访问: http://localhost:8765"
echo "   按 Ctrl+C 停止服务器"
echo ""

if [ "$MODE" = "mock" ]; then
    python -u -m src.servers.server --mock
else
    python -u -m src.servers.server
fi

