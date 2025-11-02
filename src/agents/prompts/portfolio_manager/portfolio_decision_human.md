基于团队的分析，为每个ticker做出你的交易决策。

以下是按ticker分类的信号:
{signals_by_ticker}

当前价格:
{current_prices}

允许购买的最大股数:
{max_shares}

投资组合现金: {portfolio_cash}
当前持仓: {portfolio_positions}
当前保证金要求: {margin_requirement}
已使用总保证金: {total_margin_used}


重要决策规则:
- LONG (看多): 
  * 表示你看好这只股票，想要持有多头仓位
  * quantity = 目标多头持仓股数（例如：100表示想持有100股多头）
  * 系统会自动计算需要买入或卖出多少股来达到目标
  * 如果当前有空头持仓，会先平掉空头再建立多头
  
- SHORT (看空): 
  * 表示你看空这只股票，想要持有空头仓位
  * quantity = 目标空头持仓股数（例如：50表示想持有50股空头）
  * 系统会自动计算需要做空或平空多少股来达到目标
  * 如果当前有多头持仓，会先平掉多头再建立空头
  
- HOLD (观望): 
  * 表示你对这只股票持中性态度
  * quantity = 0
  * 保持当前持仓不变（无论是多头、空头还是空仓）

决策示例:
- 当前无持仓，看多 → action="long", quantity=100 (建立100股多头)
- 当前持有50股多头，继续看多 → action="long", quantity=100 (增加到100股多头)
- 当前持有100股多头，转为观望 → action="hold", quantity=0 (保持100股多头不变)
- 当前持有100股多头，转为看空 → action="short", quantity=50 (先平100股多头，再建50股空头)

严格按照以下JSON结构输出:
```json
{
  "decisions": {
    "TICKER1": {
      "action": "long/short/hold",
      "quantity": 整数（long/short时为目标持仓数，hold时为0）,
      "confidence": 0到100之间的浮点数,
      "reasoning": "解释你的决策的字符串，包括为什么选择这个方向和数量"
    },
    "TICKER2": {
      ...
    },
    ...
  }
}
```

