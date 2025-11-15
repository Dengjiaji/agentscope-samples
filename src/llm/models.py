"""
AgentScope Model Wrapper

Provides AgentScope-compatible model calling interface while maintaining support for existing model providers
"""
import os
from typing import Dict, Any, List, Optional, Union
from enum import Enum
import json
from agentscope.model import OpenAIChatModel
import agentscope


class ModelProvider(str, Enum):
    """Supported LLM provider enumeration"""
    ALIBABA = "ALIBABA"
    ANTHROPIC = "ANTHROPIC"
    DEEPSEEK = "DEEPSEEK"
    GOOGLE = "GOOGLE"
    GROQ = "GROQ"
    META = "META"
    MISTRAL = "MISTRAL"
    OPENAI = "OPENAI"
    OLLAMA = "OLLAMA"
    OPENROUTER = "OPENROUTER"
    GIGACHAT = "GIGACHAT"


class ModelWrapper:
    """
    AgentScope Model Wrapper
    
    Provides unified interface to call different LLM models
    Compatible with AgentScope design patterns
    """
    
    def __init__(
        self,
        model_name: str,
        model_provider: Union[str, ModelProvider],
        api_keys: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        """
        Initialize model wrapper
        
        Args:
            model_name: Model name
            model_provider: Model provider
            api_keys: API keys dictionary
            **kwargs: Other configuration parameters
        """
        self.model_name = model_name
        self.model_provider = ModelProvider(model_provider) if isinstance(model_provider, str) else model_provider
        self.api_keys = api_keys or {}
        self.config = kwargs
        
        # Initialize underlying model
        self._init_model()
    
    def _init_model(self):
        """Initialize underlying model instance"""
        # Initialize corresponding model based on provider
        if self.model_provider == ModelProvider.OPENAI:
            self._init_openai_model()
        elif self.model_provider == ModelProvider.ANTHROPIC:
            self._init_anthropic_model()
        elif self.model_provider == ModelProvider.GROQ:
            self._init_groq_model()
        elif self.model_provider == ModelProvider.DEEPSEEK:
            self._init_deepseek_model()
        elif self.model_provider == ModelProvider.GOOGLE:
            self._init_google_model()
        elif self.model_provider == ModelProvider.OLLAMA:
            self._init_ollama_model()
        elif self.model_provider == ModelProvider.OPENROUTER:
            self._init_openrouter_model()
        elif self.model_provider == ModelProvider.GIGACHAT:
            self._init_gigachat_model()
        else:
            raise ValueError(f"Unsupported model provider: {self.model_provider}")
    
    def _init_openai_model(self):
        """Initialize OpenAI model"""
        from openai import OpenAI
        
        api_key = self.api_keys.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_API_BASE")
        
        if not api_key:
            raise ValueError("OpenAI API key not found")
        
        self.client = OpenAI(api_key=api_key, base_url=base_url)
    
    def _init_anthropic_model(self):
        """Initialize Anthropic model"""
        from anthropic import Anthropic
        
        api_key = self.api_keys.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Anthropic API key not found")
        
        self.client = Anthropic(api_key=api_key)
    
    def _init_groq_model(self):
        """Initialize Groq model"""
        from groq import Groq
        
        api_key = self.api_keys.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Groq API key not found")
        
        self.client = Groq(api_key=api_key)
    
    def _init_deepseek_model(self):
        """Initialize DeepSeek model"""
        from openai import OpenAI
        
        api_key = self.api_keys.get("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DeepSeek API key not found")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
    
    def _init_google_model(self):
        """Initialize Google model"""
        import google.generativeai as genai
        
        api_key = self.api_keys.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("Google API key not found")
        
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(self.model_name)
    
    def _init_ollama_model(self):
        """Initialize Ollama model"""
        from ollama import Client
        
        ollama_host = os.getenv("OLLAMA_HOST", "localhost")
        base_url = os.getenv("OLLAMA_BASE_URL", f"http://{ollama_host}:11434")
        
        self.client = Client(host=base_url)
    
    def _init_openrouter_model(self):
        """Initialize OpenRouter model"""
        from openai import OpenAI
        
        api_key = self.api_keys.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OpenRouter API key not found")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )
    
    def _init_gigachat_model(self):
        """Initialize GigaChat model"""
        # GigaChat initialization logic
        api_key = self.api_keys.get("GIGACHAT_API_KEY") or os.getenv("GIGACHAT_API_KEY")
        if not api_key:
            raise ValueError("GigaChat API key not found")
        # Implementation needed based on GigaChat's actual API
        pass
    
    def __call__(
        self,
        messages: Union[List[Dict[str, Any]], str],
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Call model to generate response
        
        Args:
            messages: Message list or single message string
            max_tokens: Maximum token count
            temperature: Temperature parameter
            **kwargs: Other parameters
        
        Returns:
            Dictionary containing response content
        """
        # Normalize message format
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        
        # Convert AgentScope message format to OpenAI format
        formatted_messages = self._format_messages(messages)
        
        # Call model
        if self.model_provider in [ModelProvider.OPENAI, ModelProvider.GROQ, 
                                     ModelProvider.DEEPSEEK, ModelProvider.OPENROUTER]:
            return self._call_openai_compatible(formatted_messages, max_tokens, temperature, **kwargs)
        elif self.model_provider == ModelProvider.ANTHROPIC:
            return self._call_anthropic(formatted_messages, max_tokens, temperature, **kwargs)
        elif self.model_provider == ModelProvider.GOOGLE:
            return self._call_google(formatted_messages, max_tokens, temperature, **kwargs)
        elif self.model_provider == ModelProvider.OLLAMA:
            return self._call_ollama(formatted_messages, max_tokens, temperature, **kwargs)
        else:
            raise ValueError(f"Unsupported model provider: {self.model_provider}")
    
    def _format_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Format messages to standard format
        
        AgentScope format: {"name": str, "content": str, "role": str}
        OpenAI format: {"role": str, "content": str}
        """
        formatted = []
        for msg in messages:
            # If AgentScope format
            if "name" in msg and "role" in msg:
                formatted.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            # If already OpenAI format
            elif "role" in msg and "content" in msg:
                formatted.append(msg)
            else:
                # Default as user message
                formatted.append({
                    "role": "user",
                    "content": str(msg)
                })
        return formatted
    
    def _call_openai_compatible(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int],
        temperature: float,
        **kwargs
    ) -> Dict[str, Any]:
        """Call OpenAI-compatible API"""
        params = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            params["max_tokens"] = max_tokens
        
        # Add other parameters
        if "response_format" in kwargs:
            params["response_format"] = kwargs["response_format"]
        
        response = self.client.chat.completions.create(**params)
        
        return {
            "content": response.choices[0].message.content,
            "role": "assistant",
            "metadata": {
                "model": self.model_name,
                "usage": response.usage.model_dump() if hasattr(response.usage, 'model_dump') else dict(response.usage)
            }
        }
    
    def _call_anthropic(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int],
        temperature: float,
        **kwargs
    ) -> Dict[str, Any]:
        """Call Anthropic API"""
        response = self.client.messages.create(
            model=self.model_name,
            messages=messages,
            max_tokens=max_tokens or 1024,
            temperature=temperature
        )
        
        return {
            "content": response.content[0].text,
            "role": "assistant",
            "metadata": {
                "model": self.model_name,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                }
            }
        }
    
    def _call_google(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int],
        temperature: float,
        **kwargs
    ) -> Dict[str, Any]:
        """Call Google Gemini API"""
        # Google Gemini requires special message format handling
        prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
        
        response = self.client.generate_content(
            prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens or 1024
            }
        )
        
        return {
            "content": response.text,
            "role": "assistant",
            "metadata": {
                "model": self.model_name
            }
        }
    
    def _call_ollama(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int],
        temperature: float,
        **kwargs
    ) -> Dict[str, Any]:
        """Call Ollama API"""
        response = self.client.chat(
            model=self.model_name,
            messages=messages,
            options={
                "temperature": temperature,
                "num_predict": max_tokens or -1
            }
        )
        
        return {
            "content": response['message']['content'],
            "role": "assistant",
            "metadata": {
                "model": self.model_name
            }
        }


def get_model(
    model_name: str,
    model_provider: Union[str, ModelProvider],
    api_keys: Optional[Dict[str, str]] = None,
    **kwargs
) -> ModelWrapper:
    """
    Get model instance
    
    Args:
        model_name: Model name
        model_provider: Model provider
        api_keys: API keys dictionary
        **kwargs: Other configuration parameters
    
    Returns:
        AgentScopeModelWrapper instance
    """
    print(f"Getting model: {model_name} {model_provider}")
    return ModelWrapper(
        model_name=model_name,
        model_provider=model_provider,
        api_keys=api_keys,
        **kwargs
    )

