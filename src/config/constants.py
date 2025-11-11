ROLE_TO_AGENT = {
    "sentiment_analyst":   "Sentiment Analyst",
    "technical_analyst":   "Technical Analyst",
    "fundamentals_analyst":"Fundamentals Analyst",
    "valuation_analyst":   "Valuation Analyst",
    "portfolio_manager":   "Portfolio Manager",
    "risk_manager":        "Risk Manager",
    "_default":            "Portfolio Manager",
}

ANALYST_TYPES = {
    "fundamentals_analyst": {
        "display_name": "Fundamentals Analyst",
        "agent_id": "fundamentals_analyst",
        "description": "使用LLM智能选择分析工具，专注于财务数据和公司基本面分析",
        "order": 12
    },
    "technical_analyst": {
        "display_name": "Technical Analyst",
        "agent_id": "technical_analyst",
        "description": "使用LLM智能选择分析工具，专注于技术指标和图表分析",
        "order": 11
    },
    "sentiment_analyst": {
        "display_name": "Sentiment Analyst",
        "agent_id": "sentiment_analyst",
        "description": "使用LLM智能选择分析工具，分析市场情绪和新闻舆论",
        "order": 13
    },
    "valuation_analyst": {
        "display_name": "Valuation Analyst",
        "agent_id": "valuation_analyst",
        "description": "使用LLM智能选择分析工具，专注于公司估值和价值评估",
        "order": 14
    },
    # "comprehensive": {
    #     "display_name": "Comprehensive Analyst",
    #     "agent_id": "comprehensive_analyst",
    #     "description": "使用LLM智能选择分析工具，进行全面综合分析",
    #     "order": 15
    # }
}