# -*- coding: utf-8 -*-
ROLE_TO_AGENT = {
    "sentiment_analyst": "Sentiment Analyst",
    "technical_analyst": "Technical Analyst",
    "fundamentals_analyst": "Fundamentals Analyst",
    "valuation_analyst": "Valuation Analyst",
    "portfolio_manager": "Portfolio Manager",
    "risk_manager": "Risk Manager",
    "_default": "Portfolio Manager",
    # "comprehensive_analyst": "Comprehensive Analyst"
}

ANALYST_TYPES = {
    "fundamentals_analyst": {
        "display_name": "Fundamentals Analyst",
        "agent_id": "fundamentals_analyst",
        "description": "Uses LLM to intelligently select analysis tools, focuses on financial data and company fundamental analysis",
        "order": 12,
    },
    "technical_analyst": {
        "display_name": "Technical Analyst",
        "agent_id": "technical_analyst",
        "description": "Uses LLM to intelligently select analysis tools, focuses on technical indicators and chart analysis",
        "order": 11,
    },
    "sentiment_analyst": {
        "display_name": "Sentiment Analyst",
        "agent_id": "sentiment_analyst",
        "description": "Uses LLM to intelligently select analysis tools, analyzes market sentiment and news sentiment",
        "order": 13,
    },
    "valuation_analyst": {
        "display_name": "Valuation Analyst",
        "agent_id": "valuation_analyst",
        "description": "Uses LLM to intelligently select analysis tools, focuses on company valuation and value assessment",
        "order": 14,
    },
    # "comprehensive_analyst": {
    #     "display_name": "Comprehensive Analyst",
    #     "agent_id": "comprehensive_analyst",
    #     "description": "Uses LLM to intelligently select analysis tools, performs comprehensive analysis",
    #     "order": 15
    # }
}
