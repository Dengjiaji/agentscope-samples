基于团队的分析，为每个ticker做出你的交易决策。

以下是按ticker分类的信号:
{{signals_by_ticker}}

当前价格:
{{current_prices}}

允许购买的最大股数:
{{max_shares}}

投资组合现金: {{portfolio_cash}}
当前持仓: {{portfolio_positions}}
当前保证金要求: {{margin_requirement}}
已使用总保证金: {{total_margin_used}}

相关历史经验:
{{relevant_past_experiences}}

重要提示: 请仔细参考上述历史经验，避免重复过去的错误决策（如过度激进、忽视风险警告等），学习成功的仓位管理模式。

重要决策规则:
- LONG (看多): 
  * 表示你看好这只股票，想要买入股票
  * quantity = 要买入的股数（增量）
  * 系统会在当前多头持仓基础上增加quantity股
  * 例如：当前持有32股多头，quantity=50 → 买入50股 → 最终持有82股多头
  
- SHORT (看空): 
  * 表示你看空这只股票，想要卖出多头或做空
  * quantity = 要卖空的股数（增量）
  * 逻辑：先卖出多头持仓，如果quantity更大，剩余部分建立空头
  * 例如：
    - 当前持有100股多头，quantity=30 → 卖出30股 → 剩余70股多头
    - 当前持有100股多头，quantity=150 → 卖出100股多头 + 做空50股 → 持有50股空头
    - 当前无持仓，quantity=50 → 直接做空50股 → 持有50股空头
  
- HOLD (观望): 
  * 表示你对这只股票持中性态度
  * quantity = 0
  * 保持当前持仓不变

决策示例:
- 当前无持仓，看多 → action="long", quantity=100 (买入100股多头)
- 当前持有32股多头，继续看多 → action="long", quantity=50 (再买50股，最终82股多头)
- 当前持有100股多头，转为观望 → action="hold", quantity=0 (保持100股多头不变)
- 当前持有100股多头，部分减仓 → action="short", quantity=30 (卖出30股，剩余70股多头)
- 当前持有100股多头，转为看空 → action="short", quantity=150 (卖出100股 + 做空50股)
- 当前无持仓，看空 → action="short", quantity=50 (直接做空50股)

严格按照以下JSON结构输出:
```json
{
  "decisions": {
    "TICKER1": {
      "action": "long/short/hold",
      "quantity": 整数（long时为买入股数，short时为卖出股数，hold时为0）,
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

