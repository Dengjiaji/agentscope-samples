# 记忆框架快速开始

## 🚀 5分钟快速上手

### 方式 1: 使用 Mem0（推荐，无需额外安装）

```bash
# 1. 在 .env 文件中设置（或不设置，默认使用mem0）
echo "MEMORY_FRAMEWORK=mem0" >> .env

# 2. 运行系统
python live_trading_thinking_fund.py \
  --config_name my_config \
  --date 2025-01-15 \
  --tickers AAPL,MSFT

# 看到这个提示说明成功
# ✅ 记忆系统已初始化: mem0
```

### 方式 2: 使用 ReMe（需要安装）

```bash
# 1. 安装 ReMe 依赖
pip install flowllm

# 2. 在 .env 文件中设置
echo "MEMORY_FRAMEWORK=reme" >> .env

# 3. 运行系统
python live_trading_thinking_fund.py \
  --config_name my_config \
  --date 2025-01-15 \
  --tickers AAPL,MSFT

# 看到这个提示说明成功
# ✅ 记忆系统已初始化: reme
```

## 🧪 快速测试

```bash
# 测试 Mem0
python test_memory_framework.py --framework mem0

# 测试 ReMe
python test_memory_framework.py --framework reme

# 测试所有框架
python test_memory_framework.py --all
```

## 📋 环境变量配置速查

在 `.env` 文件中添加：

```bash
# ===== 记忆框架选择 =====
MEMORY_FRAMEWORK=mem0           # 或 reme

# ===== 共享配置 =====
MEMORY_EMBEDDING_MODEL=text-embedding-v4
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=your_url

# ===== ReMe 特定配置（仅当使用 reme 时需要）=====
REME_EMBEDDING_DIMENSIONS=1024
```

## 💡 代码示例

### 初始化记忆系统

```python
from src.memory.memory_factory import initialize_memory_system

# 初始化（自动根据环境变量选择框架）
memory = initialize_memory_system(base_dir="my_config")
print(f"当前框架: {memory.get_framework_name()}")
```

### 基本操作

```python
# 添加记忆
memory.add(
    messages="技术分析显示AAPL处于上升趋势",
    user_id="technical_analyst",
    metadata={"stock": "AAPL", "date": "2025-01-15"}
)

# 搜索记忆
results = memory.search(
    query="AAPL技术分析",
    user_id="technical_analyst",
    top_k=5
)

for item in results['results']:
    print(f"记忆: {item['memory']}")
    print(f"相似度: {item.get('score', 'N/A')}")
```

## 🔄 切换框架

### 临时切换（单次运行）

```bash
# 使用 Mem0
MEMORY_FRAMEWORK=mem0 python your_script.py

# 使用 ReMe
MEMORY_FRAMEWORK=reme python your_script.py
```

### 永久切换（修改 .env）

```bash
# 方法 1: 直接编辑 .env 文件
vim .env
# 修改: MEMORY_FRAMEWORK=reme

# 方法 2: 使用命令行
sed -i 's/MEMORY_FRAMEWORK=mem0/MEMORY_FRAMEWORK=reme/' .env
```

## ❓ 常见问题

### Q1: 两个框架的数据能互通吗？
**A**: 不能。每个框架使用独立的存储格式，切换框架后之前的记忆数据不会自动迁移。

### Q2: 应该选择哪个框架？
**A**: 
- **生产环境**: 推荐 Mem0（稳定、轻量、无需额外安装）
- **研究实验**: 可以尝试 ReMe（支持更多高级功能）

### Q3: 如何查看当前使用的框架？
**A**: 
```python
from src.memory.memory_factory import get_current_framework_name
print(get_current_framework_name())
```

### Q4: ReMe 安装失败怎么办？
**A**: 如果 `pip install flowllm` 失败，请使用 Mem0 框架（默认选项）。

## 📚 完整文档

详见 [MEMORY_FRAMEWORK_GUIDE.md](./MEMORY_FRAMEWORK_GUIDE.md)

---

**提示**: 首次使用建议先用 Mem0 框架测试，确保系统正常运行后再考虑是否切换到 ReMe。

