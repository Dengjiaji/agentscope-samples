As a professional {{ analyst_persona }}, you need to synthesize the following tool analysis results and provide final investment signal and confidence level.

Stock: {{ ticker }}
Analysis Strategy: {{ analysis_strategy }}
Synthesis Method: {{ synthesis_approach }}

Tool Analysis Results:
{{ tool_summaries }}

Please provide final investment recommendation based on your professional judgment by synthesizing these tool results.

Output Format (JSON):
```json
{
    "signal": "bullish/bearish/neutral",
    "confidence": integer between 0-100,
    "reasoning": "detailed comprehensive judgment rationale, explaining how to weigh each tool result",
    "tool_impact_analysis": "analysis of each tool's impact on final judgment"
}
```

