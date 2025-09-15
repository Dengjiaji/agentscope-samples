"""Constants and utilities related to analysts configuration."""

from src.agents import portfolio_manager
from src.agents.aswath_damodaran import aswath_damodaran_agent
from src.agents.ben_graham import ben_graham_agent
from src.agents.bill_ackman import bill_ackman_agent
from src.agents.cathie_wood import cathie_wood_agent
from src.agents.charlie_munger import charlie_munger_agent
# 使用智能LLM版本的核心分析师
from src.agents.intelligent_analysts import (
    intelligent_fundamentals_analyst_agent,
    intelligent_technical_analyst_agent,
    intelligent_sentiment_analyst_agent,
    intelligent_valuation_analyst_agent
)
from src.agents.michael_burry import michael_burry_agent
from src.agents.phil_fisher import phil_fisher_agent
from src.agents.peter_lynch import peter_lynch_agent
from src.agents.stanley_druckenmiller import stanley_druckenmiller_agent
from src.agents.warren_buffett import warren_buffett_agent
from src.agents.rakesh_jhunjhunwala import rakesh_jhunjhunwala_agent

# Define analyst configuration - single source of truth
ANALYST_CONFIG = {
    "aswath_damodaran": {
        "display_name": "Aswath Damodaran",
        "description": "The Dean of Valuation",
        "investing_style": "Focuses on intrinsic value and financial metrics to assess investment opportunities through rigorous valuation analysis.",
        "agent_func": aswath_damodaran_agent,
        "type": "analyst",
        "order": 0,
    },
    "ben_graham": {
        "display_name": "Ben Graham",
        "description": "The Father of Value Investing",
        "investing_style": "Emphasizes a margin of safety and invests in undervalued companies with strong fundamentals through systematic value analysis.",
        "agent_func": ben_graham_agent,
        "type": "analyst",
        "order": 1,
    },
    "bill_ackman": {
        "display_name": "Bill Ackman",
        "description": "The Activist Investor",
        "investing_style": "Seeks to influence management and unlock value through strategic activism and contrarian investment positions.",
        "agent_func": bill_ackman_agent,
        "type": "analyst",
        "order": 2,
    },
    "cathie_wood": {
        "display_name": "Cathie Wood",
        "description": "The Queen of Growth Investing",
        "investing_style": "Focuses on disruptive innovation and growth, investing in companies that are leading technological advancements and market disruption.",
        "agent_func": cathie_wood_agent,
        "type": "analyst",
        "order": 3,
    },
    "charlie_munger": {
        "display_name": "Charlie Munger",
        "description": "The Rational Thinker",
        "investing_style": "Advocates for value investing with a focus on quality businesses and long-term growth through rational decision-making.",
        "agent_func": charlie_munger_agent,
        "type": "analyst",
        "order": 4,
    },
    "michael_burry": {
        "display_name": "Michael Burry",
        "description": "The Big Short Contrarian",
        "investing_style": "Makes contrarian bets, often shorting overvalued markets and investing in undervalued assets through deep fundamental analysis.",
        "agent_func": michael_burry_agent,
        "type": "analyst",
        "order": 5,
    },
    "peter_lynch": {
        "display_name": "Peter Lynch",
        "description": "The 10-Bagger Investor",
        "investing_style": "Invests in companies with understandable business models and strong growth potential using the 'buy what you know' strategy.",
        "agent_func": peter_lynch_agent,
        "type": "analyst",
        "order": 6,
    },
    "phil_fisher": {
        "display_name": "Phil Fisher",
        "description": "The Scuttlebutt Investor",
        "investing_style": "Emphasizes investing in companies with strong management and innovative products, focusing on long-term growth through scuttlebutt research.",
        "agent_func": phil_fisher_agent,
        "type": "analyst",
        "order": 7,
    },
    "rakesh_jhunjhunwala": {
        "display_name": "Rakesh Jhunjhunwala",
        "description": "The Big Bull Of India",
        "investing_style": "Leverages macroeconomic insights to invest in high-growth sectors, particularly within emerging markets and domestic opportunities.",
        "agent_func": rakesh_jhunjhunwala_agent,
        "type": "analyst",
        "order": 8,
    },
    "stanley_druckenmiller": {
        "display_name": "Stanley Druckenmiller",
        "description": "The Macro Investor",
        "investing_style": "Focuses on macroeconomic trends, making large bets on currencies, commodities, and interest rates through top-down analysis.",
        "agent_func": stanley_druckenmiller_agent,
        "type": "analyst",
        "order": 9,
    },
    "warren_buffett": {
        "display_name": "Warren Buffett",
        "description": "The Oracle of Omaha",
        "investing_style": "Seeks companies with strong fundamentals and competitive advantages through value investing and long-term ownership.",
        "agent_func": warren_buffett_agent,
        "type": "analyst",
        "order": 10,
    },
    "technical_analyst": {
        "display_name": "Technical Analyst (LLM智能选择)",
        "description": "Chart Pattern Specialist with AI Tool Selection",
        "investing_style": "Uses LLM to intelligently select technical analysis tools, focusing on chart patterns and market trends to make investment decisions through AI-enhanced analysis.",
        "agent_func": intelligent_technical_analyst_agent,
        "type": "analyst",
        "order": 11,
    },
    "fundamentals_analyst": {
        "display_name": "Fundamentals Analyst (LLM智能选择)",
        "description": "Financial Statement Specialist with AI Tool Selection",
        "investing_style": "Uses LLM to intelligently select fundamental analysis tools, delving into financial statements and economic indicators to assess intrinsic value through AI-enhanced analysis.",
        "agent_func": intelligent_fundamentals_analyst_agent,
        "type": "analyst",
        "order": 12,
    },
    "sentiment_analyst": {
        "display_name": "Sentiment Analyst (LLM智能选择)",
        "description": "Market Sentiment Specialist with AI Tool Selection",
        "investing_style": "Uses LLM to intelligently select sentiment analysis tools, gauging market sentiment and investor behavior to predict market movements through AI-enhanced behavioral analysis.",
        "agent_func": intelligent_sentiment_analyst_agent,
        "type": "analyst",
        "order": 13,
    },
    "valuation_analyst": {
        "display_name": "Valuation Analyst (LLM智能选择)",
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
