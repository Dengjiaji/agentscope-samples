"""
AgentScope 模型包装器

提供与 AgentScope 兼容的模型调用接口，同时保持对现有模型提供商的支持
"""
import os
from typing import Dict, Any, List, Optional, Union
from enum import Enum
import json
from agentscope.model import OpenAIChatModel
import agentscope


class ModelProvider(str, Enum):
    """支持的 LLM 提供商枚举"""
    ALIBABA = "Alibaba"
    ANTHROPIC = "Anthropic"
    DEEPSEEK = "DeepSeek"
    GOOGLE = "Google"
    GROQ = "Groq"
    META = "Meta"
    MISTRAL = "Mistral"
    OPENAI = "OpenAI"
    OLLAMA = "Ollama"
    OPENROUTER = "OpenRouter"
    GIGACHAT = "GigaChat"


class ModelWrapper:
    """
    AgentScope 模型包装器
    
    提供统一的接口来调用不同的 LLM 模型
    兼容 AgentScope 的设计模式
    """
    
    def __init__(
        self,
        model_name: str,
        model_provider: Union[str, ModelProvider],
        api_keys: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        """
        初始化模型包装器
        
        Args:
            model_name: 模型名称
            model_provider: 模型提供商
            api_keys: API 密钥字典
            **kwargs: 其他配置参数
        """
        self.model_name = model_name
        self.model_provider = ModelProvider(model_provider) if isinstance(model_provider, str) else model_provider
        self.api_keys = api_keys or {}
        self.config = kwargs
        
        # 初始化底层模型
        self._init_model()
    
    def _init_model(self):
        """初始化底层模型实例"""
        # 根据提供商初始化相应的模型
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
            raise ValueError(f"不支持的模型提供商: {self.model_provider}")
    
    def _init_openai_model(self):
        """初始化 OpenAI 模型"""
        from openai import OpenAI
        
        api_key = self.api_keys.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_API_BASE")
        
        if not api_key:
            raise ValueError("OpenAI API key not found")
        
        self.client = OpenAI(api_key=api_key, base_url=base_url)
    
    def _init_anthropic_model(self):
        """初始化 Anthropic 模型"""
        from anthropic import Anthropic
        
        api_key = self.api_keys.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Anthropic API key not found")
        
        self.client = Anthropic(api_key=api_key)
    
    def _init_groq_model(self):
        """初始化 Groq 模型"""
        from groq import Groq
        
        api_key = self.api_keys.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Groq API key not found")
        
        self.client = Groq(api_key=api_key)
    
    def _init_deepseek_model(self):
        """初始化 DeepSeek 模型"""
        from openai import OpenAI
        
        api_key = self.api_keys.get("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DeepSeek API key not found")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
    
    def _init_google_model(self):
        """初始化 Google 模型"""
        import google.generativeai as genai
        
        api_key = self.api_keys.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("Google API key not found")
        
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(self.model_name)
    
    def _init_ollama_model(self):
        """初始化 Ollama 模型"""
        from ollama import Client
        
        ollama_host = os.getenv("OLLAMA_HOST", "localhost")
        base_url = os.getenv("OLLAMA_BASE_URL", f"http://{ollama_host}:11434")
        
        self.client = Client(host=base_url)
    
    def _init_openrouter_model(self):
        """初始化 OpenRouter 模型"""
        from openai import OpenAI
        
        api_key = self.api_keys.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OpenRouter API key not found")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )
    
    def _init_gigachat_model(self):
        """初始化 GigaChat 模型"""
        # GigaChat 初始化逻辑
        api_key = self.api_keys.get("GIGACHAT_API_KEY") or os.getenv("GIGACHAT_API_KEY")
        if not api_key:
            raise ValueError("GigaChat API key not found")
        # 这里需要根据 GigaChat 的实际 API 实现
        pass
    
    def __call__(
        self,
        messages: Union[List[Dict[str, Any]], str],
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用模型生成响应
        
        Args:
            messages: 消息列表或单个消息字符串
            max_tokens: 最大 token 数
            temperature: 温度参数
            **kwargs: 其他参数
        
        Returns:
            包含响应内容的字典
        """
        # 标准化消息格式
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        
        # 转换 AgentScope 消息格式到 OpenAI 格式
        formatted_messages = self._format_messages(messages)
        
        # 调用模型
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
            raise ValueError(f"不支持的模型提供商: {self.model_provider}")
    
    def _format_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        格式化消息为标准格式
        
        AgentScope 格式: {"name": str, "content": str, "role": str}
        OpenAI 格式: {"role": str, "content": str}
        """
        formatted = []
        for msg in messages:
            # 如果是 AgentScope 格式
            if "name" in msg and "role" in msg:
                formatted.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            # 如果已经是 OpenAI 格式
            elif "role" in msg and "content" in msg:
                formatted.append(msg)
            else:
                # 默认作为用户消息
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
        """调用 OpenAI 兼容的 API"""
        params = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            params["max_tokens"] = max_tokens
        
        # 添加其他参数
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
        """调用 Anthropic API"""
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
        """调用 Google Gemini API"""
        # Google Gemini 需要特殊的消息格式处理
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
        """调用 Ollama API"""
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
    获取模型实例
    
    Args:
        model_name: 模型名称
        model_provider: 模型提供商
        api_keys: API 密钥字典
        **kwargs: 其他配置参数
    
    Returns:
        AgentScopeModelWrapper 实例
    """
    return ModelWrapper(
        model_name=model_name,
        model_provider=model_provider,
        api_keys=api_keys,
        **kwargs
    )

