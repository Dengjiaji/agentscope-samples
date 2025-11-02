Based on team analysis, make investment direction decisions for each stock.

Analyst signals for each stock:
{signals_by_ticker}

{analyst_weights_info}{analyst_weights_separator}

Decision rules:
- Comprehensively consider signals and confidence levels from all analysts
- Opinions from analysts with higher weights should receive more consideration
- When analysts have significant disagreements, choose hold/neutral
- When majority of analysts agree with high confidence, follow mainstream opinion
- Risk manager's risk assessment information should be used as important reference, high-risk stocks require more cautious decisions

Please strictly output in the following JSON format:
```json
{
  "decisions": {
    "TICKER1": {
      "action": "long/short/hold",
      "confidence": float between 0-100,
      "reasoning": "detailed explanation of your decision rationale, including how you synthesized each analyst's opinion"
    },
    "TICKER2": {
      ...
    },
    ...
  }
}
```

