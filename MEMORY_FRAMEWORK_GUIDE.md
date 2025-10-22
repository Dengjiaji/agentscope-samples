# 记忆框架切换指南

本项目现在支持在 **Mem0** 和 **ReMe** 两个记忆框架之间进行切换。

## 📋 目录结构

```
IA/
├── src/
│   └── memory/
│       ├── memory_interface.py      # 统一记忆接口（抽象层）
│       ├── memory_factory.py        # 记忆系统工厂
│       ├── mem0_adapter.py          # Mem0 框架适配器
│       ├── reme_adapter.py          # ReMe 框架适配器
│       ├── mem0_core.py             # Mem0 核心实现（保持不变）
│       └── unified_memory.py        # 统一记忆管理（保持不变）
├── logs_and_memory/{config_name}/
│   └── memory_data/
│       ├── ia_memory_history.db     # Mem0 使用
│       ├── ia_chroma_db/            # Mem0 使用
│       └── reme_vector_store/       # ReMe 使用
└── env.template                     # 环境变量模板
```

## 🔧 配置方法

### 1. 使用 Mem0 框架（默认）

在 `.env` 文件中设置：

```bash
MEMORY_FRAMEWORK=mem0
```

或者不设置该变量（默认使用 mem0）。

**无需额外安装**，Mem0 已包含在项目依赖中。

### 2. 使用 ReMe 框架

#### 步骤 1: 安装 ReMe 依赖

```bash
# 安装 flowllm 包（ReMe 的底层框架）
pip install flowllm
```

#### 步骤 2: 配置环境变量

在 `.env` 文件中设置：

```bash
# 选择 ReMe 框架
MEMORY_FRAMEWORK=reme

# ReMe 专用配置
REME_EMBEDDING_DIMENSIONS=1024

# 共享配置（两个框架都使用）
MEMORY_EMBEDDING_MODEL=text-embedding-v4
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=your_base_url
```

## 🚀 使用方法

### 启动脚本

```bash
# 使用 Mem0 框架
MEMORY_FRAMEWORK=mem0 python live_trading_thinking_fund.py \
  --config_name test_config \
  --date 2025-01-15 \
  --tickers AAPL,MSFT

# 使用 ReMe 框架
MEMORY_FRAMEWORK=reme python live_trading_thinking_fund.py \
  --config_name test_config \
  --date 2025-01-15 \
  --tickers AAPL,MSFT
```

系统会在启动时显示：
```
✅ 记忆系统已初始化: mem0
```
或
```
✅ 记忆系统已初始化: reme
```

## 📊 框架对比

| 特性 | Mem0 | ReMe |
|------|------|------|
| **安装难度** | ✅ 简单（已包含） | ⚠️ 需要安装 flowllm |
| **性能** | ⚡ 快速 | ⚡ 快速 |
| **存储后端** | SQLite + Chroma | Chroma |
| **记忆管理** | 完整支持 | 完整支持 |
| **导入/导出** | 基础支持 | ✨ 高级支持 |
| **适用场景** | 通用、生产环境 | 研究、实验 |

## 🔍 API 接口

两个框架提供统一的接口：

```python
from src.memory.memory_factory import get_memory_instance

# 获取记忆实例
memory = get_memory_instance()

# 添加记忆
memory.add(
    messages="分析内容",
    user_id="technical_analyst",
    metadata={"type": "analysis"}
)

# 搜索记忆
results = memory.search(
    query="技术分析",
    user_id="technical_analyst",
    top_k=5
)

# 更新记忆
memory.update(
    memory_id="memory_123",
    data="更新后的内容"
)

# 删除记忆
memory.delete(memory_id="memory_123")

# 获取所有记忆
all_memories = memory.get_all(user_id="technical_analyst")

# 重置记忆
memory.reset(user_id="technical_analyst")

# 获取当前框架名称
framework = memory.get_framework_name()  # "mem0" 或 "reme"
```

## 🎯 数据存储位置

### Mem0 框架
```
logs_and_memory/{config_name}/memory_data/
├── ia_memory_history.db              # 历史记录数据库
└── ia_chroma_db/                     # 向量存储
    ├── chroma.sqlite3
    └── [collection_files]
```

### ReMe 框架
```
logs_and_memory/{config_name}/memory_data/
└── reme_vector_store/                # 向量存储
    ├── chroma.sqlite3
    └── [workspace_files]
```

## ⚠️ 注意事项

### 1. 框架切换
- ⚠️ 不同框架的数据**不互通**
- 切换框架时，之前的记忆数据不会自动迁移
- 建议在同一个项目中保持使用同一个框架

### 2. ReMe 特定限制
- ❌ `update` 操作需要先 `delete` 再 `add`
- ❌ `delete` 操作需要知道 workspace_id
- ✅ 支持 workspace 级别的导入/导出

### 3. Mem0 特定限制
- ✅ 完整支持所有标准操作
- ⚠️ 重置所有用户需要手动遍历

## 🧪 测试框架切换

```bash
# 1. 测试 Mem0
export MEMORY_FRAMEWORK=mem0
python -c "
from src.memory.memory_factory import initialize_memory_system
memory = initialize_memory_system('test_config')
print(f'框架: {memory.get_framework_name()}')
"

# 2. 测试 ReMe（需要先安装 flowllm）
export MEMORY_FRAMEWORK=reme
python -c "
from src.memory.memory_factory import initialize_memory_system
memory = initialize_memory_system('test_config')
print(f'框架: {memory.get_framework_name()}')
"
```

## 🐛 故障排除

### 问题 1: ReMe 导入错误
```
ImportError: ReMe框架不可用: No module named 'flowllm'
```

**解决方法**：
```bash
pip install flowllm
```

### 问题 2: 记忆系统未初始化
```
WARNING:src.memory.memory_factory:记忆系统尚未初始化
```

**解决方法**：
确保在使用前调用了 `initialize_memory_system(base_dir)`

### 问题 3: 未知的记忆框架
```
WARNING:未知的记忆框架: xxx，使用默认值 mem0
```

**解决方法**：
检查环境变量 `MEMORY_FRAMEWORK` 是否设置为 `mem0` 或 `reme`

## 📚 更多信息

- [Mem0 文档](https://docs.mem0.ai/)
- [ReMe GitHub](https://github.com/tsinghua-fib-lab/ReMe)
- [FlowLLM 文档](https://github.com/tsinghua-fib-lab/flowllm)

## 🤝 贡献

如果需要添加新的记忆框架：

1. 实现 `MemoryInterface` 接口
2. 在 `memory_factory.py` 中注册新框架
3. 更新 `env.template` 添加配置
4. 更新本文档

---

**最后更新**: 2025-01-15

