# start
## 1.最初的版本，没加live 绩效，没加入memory管理
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

## 3.时间sandbox模拟版本，加入memory管理
python live_trading_thinking_fund.py --date 2025-01-15
python live_trading_thinking_fund.py --start-date 2024-01-05 --end-date 2024-01-08
