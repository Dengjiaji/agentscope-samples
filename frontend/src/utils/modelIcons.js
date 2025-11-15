/**
 * Model Icons and Styling Utilities
 * 
 * Provides icon and styling configuration for different LLM models
 */

/**
 * Get model icon and styling based on model name
 * @param {string} modelName - The model name (e.g., "qwen-plus", "gpt-4o")
 * @param {string} modelProvider - The model provider (e.g., "OPENAI", "ANTHROPIC")
 * @returns {object} Icon configuration { logoPath, color, bgColor, label, provider }
 */
export function getModelIcon(modelName, modelProvider) {
  if (!modelName) {
    return {
      logoPath: null,
      color: '#666666',
      bgColor: '#f5f5f5',
      label: 'Default',
      provider: 'Default'
    };
  }

  const name = modelName.toLowerCase();
  const provider = (modelProvider || '').toUpperCase();

  // GLM Models (智谱AI)
  if (name.includes('glm')) {
    return {
      logoPath: '/assets/llm_model_logos/Zhipu AI.png',
      color: '#4A90E2',
      bgColor: '#E3F2FD',
      label: 'GLM-4.6',
      provider: 'Zhipu AI'
    };
  }

  // Qwen Models (阿里云/通义千问)
  if (name.includes('qwen')) {
    return {
      logoPath: '/assets/llm_model_logos/Alibaba.jpeg',
      color: '#FF6A00',
      bgColor: '#FFF3E0',
      label: name.includes('max') ? 'Qwen-Max' : name.includes('plus') ? 'Qwen-Plus' : 'Qwen',
      provider: 'Alibaba'
    };
  }

  // DeepSeek Models
  if (name.includes('deepseek')) {
    return {
      logoPath: '/assets/llm_model_logos/DeepSeek.png',
      color: '#1976D2',
      bgColor: '#E3F2FD',
      label: 'DeepSeek-V3',
      provider: 'DeepSeek'
    };
  }

  // Moonshot/Kimi Models (月之暗面)
  if (name.includes('moonshot') || name.includes('kimi')) {
    return {
      logoPath: '/assets/llm_model_logos/Moonshot.jpeg',
      color: '#7B68EE',
      bgColor: '#F3E5F5',
      label: 'Kimi-K2',
      provider: 'Moonshot'
    };
  }

  // OpenAI Models (fallback for non-specific models)
  if (provider === 'OPENAI' || name.includes('gpt')) {
    return {
      logoPath: '/assets/llm_model_logos/OpenAI.png',
      color: '#10A37F',
      bgColor: '#E8F5E9',
      label: name.includes('4') ? 'GPT-4' : name.includes('3.5') ? 'GPT-3.5' : 'OpenAI',
      provider: 'OpenAI'
    };
  }

  // Anthropic Claude Models
  if (provider === 'ANTHROPIC' || name.includes('claude')) {
    return {
      logoPath: '/assets/llm_model_logos/Anthropic.png',
      color: '#D97706',
      bgColor: '#FEF3C7',
      label: 'Claude',
      provider: 'Anthropic'
    };
  }

  // Google Gemini Models
  if (provider === 'GOOGLE' || name.includes('gemini')) {
    return {
      logoPath: '/assets/llm_model_logos/Google.jpeg',
      color: '#4285F4',
      bgColor: '#E8F0FE',
      label: 'Gemini',
      provider: 'Google'
    };
  }

  // Groq Models
  if (provider === 'GROQ') {
    return {
      logoPath: '/assets/llm_model_logos/Groq.png',
      color: '#DC2626',
      bgColor: '#FEE2E2',
      label: 'Groq',
      provider: 'Groq'
    };
  }

  // Ollama Models
  if (provider === 'OLLAMA') {
    return {
      logoPath: '/assets/llm_model_logos/Ollama.png',
      color: '#000000',
      bgColor: '#F5F5F5',
      label: 'Ollama',
      provider: 'Ollama'
    };
  }

  // OpenRouter Models
  if (provider === 'OPENROUTER') {
    return {
      logoPath: null,
      color: '#8B5CF6',
      bgColor: '#F5F3FF',
      label: 'OpenRouter',
      provider: 'OpenRouter'
    };
  }

  // GigaChat Models
  if (provider === 'GIGACHAT') {
    return {
      logoPath: null,
      color: '#9333EA',
      bgColor: '#FAF5FF',
      label: 'GigaChat',
      provider: 'GigaChat'
    };
  }

  // Default fallback
  return {
    logoPath: null,
    color: '#666666',
    bgColor: '#f5f5f5',
    label: modelName.substring(0, 15),
    provider: provider || 'Unknown'
  };
}

/**
 * Get short model name for display
 * @param {string} modelName - The full model name
 * @returns {string} Short version of the model name
 */
export function getShortModelName(modelName) {
  if (!modelName) return 'N/A';

  const name = modelName.toLowerCase();

  // GLM
  if (name.includes('glm')) return 'GLM-4.6';
  
  // Qwen
  if (name.includes('qwen3-max')) return 'Qwen3-Max';
  if (name.includes('qwen-max')) return 'Qwen-Max';
  if (name.includes('qwen-plus')) return 'Qwen-Plus';
  if (name.includes('qwen-flash')) return 'Qwen-Flash';
  if (name.includes('qwen')) return 'Qwen';
  
  // DeepSeek
  if (name.includes('deepseek-v3.2')) return 'DeepSeek-V3.2';
  if (name.includes('deepseek-v3')) return 'DeepSeek-V3';
  if (name.includes('deepseek')) return 'DeepSeek';
  
  // Moonshot/Kimi
  if (name.includes('kimi-k2')) return 'Kimi-K2';
  if (name.includes('moonshot') || name.includes('kimi')) return 'Kimi';
  
  // OpenAI
  if (name.includes('gpt-4o')) return 'GPT-4o';
  if (name.includes('gpt-4.5')) return 'GPT-4.5';
  if (name.includes('gpt-4')) return 'GPT-4';
  if (name.includes('gpt-3.5')) return 'GPT-3.5';
  
  // Claude
  if (name.includes('claude-opus')) return 'Claude Opus';
  if (name.includes('claude-sonnet')) return 'Claude Sonnet';
  if (name.includes('claude-haiku')) return 'Claude Haiku';
  if (name.includes('claude')) return 'Claude';
  
  // Truncate long names
  if (modelName.length > 20) {
    return modelName.substring(0, 17) + '...';
  }
  
  return modelName;
}

