"""
Prompt Loader - 统一管理和加载 Agent Prompts
支持 Markdown 和 YAML 格式
使用简单的字符串替换，不依赖 Jinja2
"""
import os
import yaml
import re
from pathlib import Path
from typing import Dict, Any, Optional


class PromptLoader:
    """统一的 Prompt 加载器"""
    
    def __init__(self, prompts_dir: Optional[Path] = None):
        """
        初始化 Prompt 加载器
        
        Args:
            prompts_dir: prompts 目录路径，默认为当前文件的 prompts/ 目录
        """
        if prompts_dir is None:
            self.prompts_dir = Path(__file__).parent / "prompts"
        else:
            self.prompts_dir = Path(prompts_dir)
        
        # 缓存已加载的 prompts
        self._prompt_cache: Dict[str, str] = {}
        self._yaml_cache: Dict[str, Dict] = {}
    
    def load_prompt(self, agent_type: str, prompt_name: str, 
                   variables: Optional[Dict[str, Any]] = None) -> str:
        """
        加载并渲染 Prompt
        
        Args:
            agent_type: Agent 类型 (analyst, portfolio_manager, risk_manager)
            prompt_name: Prompt 文件名（不含扩展名）
            variables: 用于渲染 Prompt 的变量字典
        
        Returns:
            渲染后的 prompt 字符串
        
        Examples:
            >>> loader = PromptLoader()
            >>> prompt = loader.load_prompt("analyst", "tool_selection", 
            ...                            {"analyst_persona": "Technical Analyst"})
        """
        cache_key = f"{agent_type}/{prompt_name}"
        
        # 尝试从缓存加载
        if cache_key not in self._prompt_cache:
            prompt_path = self.prompts_dir / agent_type / f"{prompt_name}.md"
            
            if not prompt_path.exists():
                raise FileNotFoundError(
                    f"Prompt file not found: {prompt_path}\n"
                    f"Please create the prompt file or check the path."
                )
            
            with open(prompt_path, 'r', encoding='utf-8') as f:
                self._prompt_cache[cache_key] = f.read()
        
        prompt_template = self._prompt_cache[cache_key]
        
        # 如果提供了变量，使用简单的字符串替换
        if variables:
            rendered = self._render_template(prompt_template, variables)
        else:
            rendered = prompt_template
        
        # 智能转义：只转义 JSON 代码块中的大括号，保留普通文本中的 LangChain 变量占位符
        rendered = self._escape_json_braces(rendered)
        
        return rendered
    
    def _render_template(self, template: str, variables: Dict[str, Any]) -> str:
        """
        使用简单的字符串替换渲染模板
        支持 {{ variable }} 语法（兼容之前的 Jinja2 格式）
        
        Args:
            template: 模板字符串
            variables: 变量字典
        
        Returns:
            渲染后的字符串
        """
        rendered = template
        
        # 替换 {{ variable }} 格式
        for key, value in variables.items():
            # 支持 {{ key }} 和 {{key}} 两种格式
            pattern1 = f"{{{{ {key} }}}}"
            pattern2 = f"{{{{{key}}}}}"
            rendered = rendered.replace(pattern1, str(value))
            rendered = rendered.replace(pattern2, str(value))
        
        return rendered
    
    def _escape_json_braces(self, text: str) -> str:
        """
        转义 JSON 代码块中的大括号，以便 LangChain 将它们视为字面量
        但保留普通文本中的 {variable} 格式（LangChain 变量占位符）
        
        Args:
            text: 待处理的文本
        
        Returns:
            处理后的文本
        """
        def replace_code_block(match):
            code_content = match.group(1)
            # 在代码块内转义所有大括号
            escaped = code_content.replace('{', '{{').replace('}', '}}')
            return f'```json\n{escaped}\n```'
        
        # 替换所有 JSON 代码块中的大括号
        text = re.sub(r'```json\n(.*?)\n```', replace_code_block, text, flags=re.DOTALL)
        return text
    
    def load_yaml_config(self, agent_type: str, config_name: str) -> Dict[str, Any]:
        """
        加载 YAML 配置文件
        
        Args:
            agent_type: Agent 类型
            config_name: 配置文件名（不含扩展名）
        
        Returns:
            配置字典
        
        Examples:
            >>> loader = PromptLoader()
            >>> config = loader.load_yaml_config("analyst", "personas")
        """
        cache_key = f"{agent_type}/{config_name}"
        
        if cache_key not in self._yaml_cache:
            yaml_path = self.prompts_dir / agent_type / f"{config_name}.yaml"
            
            if not yaml_path.exists():
                raise FileNotFoundError(f"YAML config not found: {yaml_path}")
            
            with open(yaml_path, 'r', encoding='utf-8') as f:
                self._yaml_cache[cache_key] = yaml.safe_load(f)
        
        return self._yaml_cache[cache_key]
    
    def clear_cache(self):
        """清空缓存（用于热重载）"""
        self._prompt_cache.clear()
        self._yaml_cache.clear()
    
    def reload_prompt(self, agent_type: str, prompt_name: str):
        """重新加载指定的 prompt（强制刷新缓存）"""
        cache_key = f"{agent_type}/{prompt_name}"
        if cache_key in self._prompt_cache:
            del self._prompt_cache[cache_key]
    
    def reload_config(self, agent_type: str, config_name: str):
        """重新加载指定的配置（强制刷新缓存）"""
        cache_key = f"{agent_type}/{config_name}"
        if cache_key in self._yaml_cache:
            del self._yaml_cache[cache_key]


# 全局单例
_default_loader: Optional[PromptLoader] = None


def get_prompt_loader() -> PromptLoader:
    """获取默认的 Prompt 加载器实例"""
    global _default_loader
    if _default_loader is None:
        _default_loader = PromptLoader()
    return _default_loader


def load_prompt(agent_type: str, prompt_name: str, 
               variables: Optional[Dict[str, Any]] = None) -> str:
    """
    便捷函数：加载 Prompt
    
    Args:
        agent_type: Agent 类型
        prompt_name: Prompt 文件名（不含扩展名）
        variables: 用于渲染的变量字典
    
    Returns:
        渲染后的 prompt 字符串
    """
    return get_prompt_loader().load_prompt(agent_type, prompt_name, variables)


def load_yaml_config(agent_type: str, config_name: str) -> Dict[str, Any]:
    """
    便捷函数：加载 YAML 配置
    
    Args:
        agent_type: Agent 类型
        config_name: 配置文件名（不含扩展名）
    
    Returns:
        配置字典
    """
    return get_prompt_loader().load_yaml_config(agent_type, config_name)
