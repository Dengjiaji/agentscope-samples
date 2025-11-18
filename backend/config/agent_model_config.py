"""
Agent Model Configuration - Support different models for different agents/roles
"""
import os
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from backend.llm.models import ModelProvider


@dataclass
class AgentModelConfig:
    """Configuration for a single agent's model"""
    model_name: str
    model_provider: ModelProvider
    
    def __post_init__(self):
        """Convert string provider to ModelProvider enum if needed"""
        if isinstance(self.model_provider, str):
            self.model_provider = ModelProvider(self.model_provider)


class AgentModelRequest:
    """
    Request object that provides agent-specific model configuration
    
    Usage:
        # Create request with default model
        request = AgentModelRequest()
        
        # Create request with agent-specific models
        request = AgentModelRequest({
            "sentiment_analyst": AgentModelConfig("qwen-plus", ModelProvider.OPENAI),
            "portfolio_manager": AgentModelConfig("gpt-4o", ModelProvider.OPENAI),
        })
        
        # Add to state
        state["metadata"]["request"] = request
    """
    
    def __init__(self, agent_configs: Optional[Dict[str, AgentModelConfig]] = None):
        """
        Initialize agent model request
        
        Args:
            agent_configs: Dictionary mapping agent_id to AgentModelConfig
        """
        self.agent_configs = agent_configs or {}
        self._load_from_env()
    
    def _load_from_env(self):
        """Load agent model configurations from environment variables"""
        # Load from environment variables with pattern: AGENT_{AGENT_ID}_MODEL_NAME
        # Example: AGENT_SENTIMENT_ANALYST_MODEL_NAME=qwen-plus
        #          AGENT_SENTIMENT_ANALYST_MODEL_PROVIDER=OPENAI
        
        agent_ids = [
            "sentiment_analyst",
            "technical_analyst", 
            "fundamentals_analyst",
            "valuation_analyst",
            "portfolio_manager",
            "risk_manager"
        ]
        
        for agent_id in agent_ids:
            model_name = os.getenv(f"AGENT_{agent_id.upper()}_MODEL_NAME")
            model_provider_str = os.getenv(f"AGENT_{agent_id.upper()}_MODEL_PROVIDER")
            
            if model_name and model_provider_str:
                model_provider = ModelProvider(model_provider_str.upper())
                self.agent_configs[agent_id] = AgentModelConfig(
                    model_name=model_name,
                    model_provider=model_provider
                )
               
    
    def get_agent_model_config(self, agent_name: str) -> Tuple[str, ModelProvider]:
        """
        Get model configuration for a specific agent
        
        Args:
            agent_name: Agent name/ID (e.g., "sentiment_analyst", "portfolio_manager")
        
        Returns:
            Tuple of (model_name, model_provider)
        """
        # Try exact match first
        if agent_name in self.agent_configs:
            config = self.agent_configs[agent_name]
            return config.model_name, config.model_provider
        
        # Try with different naming conventions
        # Map display names to agent IDs
        name_mapping = {
            "Sentiment Analyst": "sentiment_analyst",
            "Technical Analyst": "technical_analyst",
            "Fundamentals Analyst": "fundamentals_analyst",
            "Valuation Analyst": "valuation_analyst",
            "Portfolio Manager": "portfolio_manager",
            "Risk Manager": "risk_manager",
        }
        
        agent_id = name_mapping.get(agent_name, agent_name.lower())
        if agent_id in self.agent_configs:
            config = self.agent_configs[agent_id]
            return config.model_name, config.model_provider
        
        # Return None to indicate no specific config (will use default)
        return None, None
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Dict[str, str]]) -> 'AgentModelRequest':
        """
        Create request from dictionary
        
        Args:
            config_dict: Dictionary mapping agent_id to config dict
                Example: {
                    "sentiment_analyst": {
                        "model_name": "qwen-plus",
                        "model_provider": "OPENAI"
                    }
                }
        
        Returns:
            AgentModelRequest instance
        """
        agent_configs = {}
        for agent_id, config in config_dict.items():
            agent_configs[agent_id] = AgentModelConfig(
                model_name=config["model_name"],
                model_provider=ModelProvider(config["model_provider"])
            )
        return cls(agent_configs)
    
    @classmethod
    def from_env(cls) -> 'AgentModelRequest':
        """
        Create request from environment variables
        
        Environment variable format:
        - AGENT_{AGENT_ID}_MODEL_NAME: Model name
        - AGENT_{AGENT_ID}_MODEL_PROVIDER: Model provider (OPENAI, ANTHROPIC, etc.)
        
        Example:
            AGENT_SENTIMENT_ANALYST_MODEL_NAME=qwen-plus
            AGENT_SENTIMENT_ANALYST_MODEL_PROVIDER=OPENAI
            AGENT_PORTFOLIO_MANAGER_MODEL_NAME=gpt-4o
            AGENT_PORTFOLIO_MANAGER_MODEL_PROVIDER=OPENAI
        
        Returns:
            AgentModelRequest instance
        """
        return cls()


def create_agent_model_request(
    config_dict: Optional[Dict[str, Dict[str, str]]] = None
) -> AgentModelRequest:
    """
    Convenience function to create AgentModelRequest
    
    Args:
        config_dict: Optional dictionary mapping agent_id to config
        
    Returns:
        AgentModelRequest instance (loads from env if config_dict is None)
    """
    if config_dict:
        return AgentModelRequest.from_dict(config_dict)
    else:
        return AgentModelRequest.from_env()

