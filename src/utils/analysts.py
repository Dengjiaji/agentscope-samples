"""Constants and utilities related to analysts configuration."""



# 使用新架构的核心分析师
from src.agents.analyst_agent import (
    create_fundamental_analyst,
    create_technical_analyst,
    create_sentiment_analyst,
    create_valuation_analyst
)



# 创建兼容的包装函数（保持旧接口）
def intelligent_fundamentals_analyst_agent(state, agent_id="fundamentals_analyst_agent"):
    """基本面分析师 - 使用新架构"""
    agent = create_fundamental_analyst(agent_id=agent_id)
    return agent.execute(state)

def intelligent_technical_analyst_agent(state, agent_id="technical_analyst_agent"):
    """技术分析师 - 使用新架构"""
    agent = create_technical_analyst(agent_id=agent_id)
    return agent.execute(state)

def intelligent_sentiment_analyst_agent(state, agent_id="sentiment_analyst_agent"):
    """情绪分析师 - 使用新架构"""
    agent = create_sentiment_analyst(agent_id=agent_id)
    return agent.execute(state)

def intelligent_valuation_analyst_agent(state, agent_id="valuation_analyst_agent"):
    """估值分析师 - 使用新架构"""
    agent = create_valuation_analyst(agent_id=agent_id)
    return agent.execute(state)

# Define analyst configuration - single source of truth
ANALYST_CONFIG = {
    
    "technical_analyst": {
        "display_name": "Technical Analyst",
        "description": "Chart Pattern Specialist with AI Tool Selection",
        "investing_style": "Uses LLM to intelligently select technical analysis tools, focusing on chart patterns and market trends to make investment decisions through AI-enhanced analysis.",
        "agent_func": intelligent_technical_analyst_agent,
        "type": "analyst",
        "order": 11,
    },
    "fundamentals_analyst": {
        "display_name": "Fundamentals Analyst",
        "description": "Financial Statement Specialist with AI Tool Selection",
        "investing_style": "Uses LLM to intelligently select fundamental analysis tools, delving into financial statements and economic indicators to assess intrinsic value through AI-enhanced analysis.",
        "agent_func": intelligent_fundamentals_analyst_agent,
        "type": "analyst",
        "order": 12,
    },
    "sentiment_analyst": {
        "display_name": "Sentiment Analyst",
        "description": "Market Sentiment Specialist with AI Tool Selection",
        "investing_style": "Uses LLM to intelligently select sentiment analysis tools, gauging market sentiment and investor behavior to predict market movements through AI-enhanced behavioral analysis.",
        "agent_func": intelligent_sentiment_analyst_agent,
        "type": "analyst",
        "order": 13,
    },
    "valuation_analyst": {
        "display_name": "Valuation Analyst",
        "description": "Company Valuation Specialist with AI Tool Selection",
        "investing_style": "Uses LLM to intelligently select valuation analysis tools, specializing in determining fair value of companies using various AI-selected models and financial metrics.",
        "agent_func": intelligent_valuation_analyst_agent,
        "type": "analyst",
        "order": 14,
    },
}

# Derive ANALYST_ORDER from ANALYST_CONFIG for backwards compatibility
ANALYST_ORDER = [(config["display_name"], key) for key, config in sorted(ANALYST_CONFIG.items(), key=lambda x: x[1]["order"])]


def get_analyst_nodes():
    """Get the mapping of analyst keys to their (node_name, agent_func) tuples."""
    return {key: (f"{key}_agent", config["agent_func"]) for key, config in ANALYST_CONFIG.items()}


def get_agents_list():
    """Get the list of agents for API responses."""
    return [
        {
            "key": key,
            "display_name": config["display_name"],
            "description": config["description"],
            "investing_style": config["investing_style"],
            "order": config["order"]
        }
        for key, config in sorted(ANALYST_CONFIG.items(), key=lambda x: x[1]["order"])
    ]
