Based on the team's analysis, make your trading decisions for each ticker.

Below are signals categorized by ticker:
{{signals_by_ticker}}

Current prices:
{{current_prices}}

Maximum shares allowed to purchase:
{{max_shares}}

Portfolio cash: {{portfolio_cash}}
Current positions: {{portfolio_positions}}
Current margin requirement: {{margin_requirement}}
Total margin used: {{total_margin_used}}

Relevant historical experiences:
{{relevant_past_experiences}}

Important Note: Please carefully refer to the above historical experiences to avoid repeating past erroneous decisions (such as being overly aggressive, ignoring risk warnings, etc.), and learn successful position management patterns.

Important Decision Rules:
- LONG (Bullish): 
  * Indicates you are bullish on this stock and want to buy shares
  * quantity = number of shares to buy (incremental)
  * The system will add quantity shares to the current long position
  * Example: Currently holding 32 long shares, quantity=50 → Buy 50 shares → Final holding 82 long shares
  
- SHORT (Bearish): 
  * Indicates you are bearish on this stock and want to sell long positions or short
  * quantity = number of shares to short (incremental)
  * Logic: First sell long positions, if quantity is larger, establish short positions for the remainder
  * Examples:
    - Currently holding 100 long shares, quantity=30 → Sell 30 shares → Remaining 70 long shares
    - Currently holding 100 long shares, quantity=150 → Sell 100 long shares + Short 50 shares → Hold 50 short shares
    - Currently no position, quantity=50 → Directly short 50 shares → Hold 50 short shares
  
- HOLD (Neutral): 
  * Indicates you hold a neutral attitude towards this stock
  * quantity = 0
  * Keep current positions unchanged

Decision Examples:
- Currently no position, bullish → action="long", quantity=100 (Buy 100 long shares)
- Currently holding 32 long shares, continue bullish → action="long", quantity=50 (Buy 50 more shares, final 82 long shares)
- Currently holding 100 long shares, turn neutral → action="hold", quantity=0 (Keep 100 long shares unchanged)
- Currently holding 100 long shares, partial reduction → action="short", quantity=30 (Sell 30 shares, remaining 70 long shares)
- Currently holding 100 long shares, turn bearish → action="short", quantity=150 (Sell 100 shares + Short 50 shares)
- Currently no position, bearish → action="short", quantity=50 (Directly short 50 shares)

Strictly output in the following JSON structure:
```json
{
  "decisions": {
    "TICKER1": {
      "action": "long/short/hold",
      "quantity": integer (number of shares to buy for long, number of shares to sell for short, 0 for hold),
      "confidence": floating point number between 0 and 100,
      "reasoning": "String explaining your decision, including why you chose this direction and quantity"
    },
    "TICKER2": {
      ...
    },
    ...
  }
}
```

