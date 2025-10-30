# start
## 1.最初的版本，没加live 绩效，没加入memory管理## 1.最初的版本，没加live 绩效，没加入memory管理
## 指定时间范围 注意 api免费数据仅支持AAPL、GOOGL、MSFT、NVDA、TSLA等少数股票

python main_multi_day.py --tickers AAPL,MSFT --start-date 2024-01-01 --end-date 2024-01-04 --max-comm-cycles 1

## 禁用沟通机制（更快）
python main_multi_day.py --tickers GOOGL --disable-communications

## 自定义配置
python main_multi_day.py --tickers AMZN,NVDA --max-comm-cycles 5 --output-dir ./my_results

python main_multi_day.py --tickers AAPL,MSFT --start-date 2024-01-01 --end-date 2024-01-03 --max-comm-cycles 1

## 可以先把communication关了调试（目前关闭PM的communication不会包括关闭前面analyst的notification）
python main_multi_day.py --tickers AAPL,MSFT --start-date 2024-01-01 --end-date 2024-01-03 --max-comm-cycles 1 --disable-communications --disable-notifications

python main_multi_day.py --tickers AAPL,MSFT --start-date 2024-01-01 --end-date 2024-01-03 --max-comm-cycles 2
## 加入--show-reasoning 才显示analyst的详细分析过程




## 打开okr
python main_multi_day.py --tickers AAPL,MSFT --start-date 2024-01-01 --end-date 2024-06-30 --max-comm-cycles 1 --enable-okr

## 2.加入live tradng更新机制，补全从2025-01-01到今天的live trading performance track
python live_trading_system.py backfill --tickers AAPL,MSFT --start-date 2025-01-01

## 3.时间sandbox模拟版本，加入memory管理, memory框架兼容ReMe和Mem0
python live_trading_thinking_fund.py \
    --start-date 2025-10-02 \
    --end-date 2025-10-03 \
    --config_name new_reme 

## 显示界面

### 方法1: 持续运行服务器（推荐）
使用便捷启动脚本：

```bash
# 正常模式 - 启动时会询问是否清空历史记录
./start_continuous_server.sh

# Mock模式 - 测试前端，不需要真实数据
./start_continuous_server.sh --mock

# 自动清空历史记录模式 - 跳过询问，直接清空
./start_continuous_server.sh --clean
```

**使用说明：**
- 首次运行会自动检测历史数据
- 如果检测到以往记录，会显示数据目录大小和最后更新时间
- 用户可选择：
  - `y` - 清空历史记录，从头开始运行
  - `n` - 在现有记录基础上继续运行（默认选项）

### 方法2: 传统方式
先启动后端脚本(根目录下运行）：

```bash
python src/servers/server.py
```

打开新的terminal, 再启动前端脚本(frontend目录下)：
```bash
# 如果没有安装先安装
cd frontend
npm install

# 运行
npm run dev
```

进入 http://localhost:5173/ 即可看到界面，点击 run/replay即可运行（目前都是replay模式，run还没接入），右侧需要选择对应执行的date
对应后端会读取sandbox_logs文件夹下的对应date的log

