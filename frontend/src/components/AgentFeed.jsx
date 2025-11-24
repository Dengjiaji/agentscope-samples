import React, { useState, useRef, useImperativeHandle, forwardRef } from 'react';
import { formatTime, calculateDuration } from '../utils/formatters';
import { MESSAGE_COLORS, getAgentColors } from '../config/constants';
import { getModelIcon } from '../utils/modelIcons';

/**
 * Agent Feed Component
 * Displays real-time feed of agent messages and conference updates
 * Minimalist design with color-coded messages
 */
const AgentFeed = forwardRef(({ feed, conferences, leaderboard }, ref) => {
  const feedContentRef = useRef(null);
  const [highlightedId, setHighlightedId] = useState(null);
  
  // Helper to get agent model info from leaderboard
  const getAgentModelInfo = (agentId) => {
    if (!leaderboard || !agentId) return { modelName: null, modelProvider: null };
    
    // Try to match by multiple possible fields (agentName, name, agent, id)
    const agentData = leaderboard.find(lb => 
      lb.name === agentId
    );
    
    return {
      modelName: agentData?.modelName,
      modelProvider: agentData?.modelProvider
    };
  };
  
  // Expose scrollToMessage method to parent
  useImperativeHandle(ref, () => ({
    scrollToMessage: (bubble) => {
      if (!bubble || !feedContentRef.current) return;
      
      // bubble.ts is the timestamp (from App.jsx setBubbles)
      const bubbleTimestamp = bubble.ts || bubble.timestamp;
      
      // Find the message in feed that matches the bubble
      // Try to match by timestamp and agent
      const targetItem = feed.find(item => {
        if (item.type === 'message' && item.data) {
          const msg = item.data;
          // Match by agent and approximate timestamp (within 5 seconds)
          if (msg.agentId === bubble.agentId || msg.agent === bubble.agentName) {
            const timeDiff = Math.abs(msg.timestamp - bubbleTimestamp);
            return timeDiff < 5000;
          }
        }
        return false;
      });
      
      if (targetItem) {
        // Find the element and scroll to it
        const element = document.getElementById(`feed-item-${targetItem.id}`);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'center' });
          
          // Highlight the message briefly
          setHighlightedId(targetItem.id);
          setTimeout(() => setHighlightedId(null), 2000);
        }
      } else {
        // If exact match not found, scroll to the most recent message from this agent
        // Feed is reverse chronological (newest first), so [0] is the latest
        const agentMessages = feed.filter(item => 
          item.type === 'message' && 
          (item.data.agentId === bubble.agentId || item.data.agent === bubble.agentName)
        );
        
        if (agentMessages.length > 0) {
          const latestMessage = agentMessages[0];
          const element = document.getElementById(`feed-item-${latestMessage.id}`);
          if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'center' });
            setHighlightedId(latestMessage.id);
            setTimeout(() => setHighlightedId(null), 2000);
          }
        }
      }
    }
  }), [feed]);
  
  return (
    <div className="agent-feed">
      <div className="feed-header">
        <h3 className="feed-title">Agent Feed</h3>
        <p className="feed-subtitle">
          Watch agents execute and interact in real-time. Review historical conferences and events.
        </p>
      </div>
      
      <div className="feed-content" ref={feedContentRef}>
        {feed.length === 0 && (
          <div className="empty-state">Waiting for system updates...</div>
        )}
        
        {feed.map(item => {
          const isHighlighted = item.id === highlightedId;
          if (item.type === 'conference') {
            return <ConferenceItem key={item.id} conference={item.data} itemId={item.id} isHighlighted={isHighlighted} getAgentModelInfo={getAgentModelInfo} />;
          } else if (item.type === 'memory') {
            return <MemoryItem key={item.id} memory={item.data} itemId={item.id} isHighlighted={isHighlighted} />;
          } else {
            return <MessageItem key={item.id} message={item.data} itemId={item.id} isHighlighted={isHighlighted} getAgentModelInfo={getAgentModelInfo} />;
          }
        })}
      </div>
    </div>
  );
});

AgentFeed.displayName = 'AgentFeed';

export default AgentFeed;

/**
 * Conference Item Component
 */
function ConferenceItem({ conference, itemId, isHighlighted, getAgentModelInfo }) {
  const colors = MESSAGE_COLORS.conference;
  
  return (
    <div 
      id={`feed-item-${itemId}`}
      className="feed-item" 
      style={{ 
        backgroundColor: colors.bg,
        outline: isHighlighted ? '2px solid #615CED' : 'none',
        transition: 'outline 0.3s ease'
      }}
    >
      <div className="feed-item-header">
        <span className="feed-item-title" style={{ color: colors.text }}>
          CONFERENCE
        </span>
        {conference.isLive && <span className="feed-live-badge">● LIVE</span>}
        <span className="feed-item-time">{formatTime(conference.startTime)}</span>
      </div>
      
      <div className="feed-item-subtitle" style={{ color: colors.text }}>
        {conference.title}
      </div>
      
      <div className="conference-messages">
        {conference.messages.map((msg, idx) => (
          <ConferenceMessage key={idx} message={msg} getAgentModelInfo={getAgentModelInfo} />
        ))}
      </div>
    </div>
  );
}

/**
 * Conference Message Component - Individual message with truncation
 */
function ConferenceMessage({ message, getAgentModelInfo }) {
  const [expanded, setExpanded] = useState(false);
  
  let agentColors;
  if (message.agent === 'System') {
    agentColors = MESSAGE_COLORS.system;
  } else if (message.agent === 'Memory') {
    agentColors = MESSAGE_COLORS.memory;
  } else {
    agentColors = getAgentColors(message.agentId, message.agent);
  }
  
  // Get model icon for agent
  const agentModelData = message.agentId && getAgentModelInfo ? getAgentModelInfo(message.agentId) : { modelName: null, modelProvider: null };
  const modelInfo = getModelIcon(agentModelData.modelName, agentModelData.modelProvider);
  
  // 处理内容 - 如果是对象则转换为 JSON 字符串
  let content = message.content || '';
  if (typeof content === 'object') {
    content = JSON.stringify(content, null, 2);
  } else {
    content = String(content);
  }
  
  const needsTruncation = content.length > 200;
  const MAX_EXPANDED_LENGTH = 10000;
  
  let displayContent = content;
  if (!expanded && needsTruncation) {
    displayContent = content.substring(0, 200) + '...';
  } else if (expanded && content.length > MAX_EXPANDED_LENGTH) {
    displayContent = content.substring(0, MAX_EXPANDED_LENGTH) + '...';
  }
  
  return (
    <div className="conf-message-item">
      <div className="conf-agent-name" style={{ color: agentColors.text, display: 'flex', alignItems: 'center', gap: '6px' }}>
        {modelInfo.logoPath && (
          <img 
            src={modelInfo.logoPath}
            alt={modelInfo.provider}
            style={{
              width: '16px',
              height: '16px',
              borderRadius: '50%',
              objectFit: 'contain'
            }}
          />
        )}
        {message.agent}
      </div>
      <div className="conf-message-content-wrapper">
        <span className="conf-message-content">{displayContent}</span>
        {needsTruncation && (
          <button 
            className="conf-expand-btn"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? '↑' : '↓'}
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * Memory Item Component
 */
function MemoryItem({ memory, itemId, isHighlighted }) {
  const [expanded, setExpanded] = useState(false);
  const colors = MESSAGE_COLORS.memory;
  
  // 处理内容 - 如果是对象则转换为 JSON 字符串
  let content = memory.content || '';
  if (typeof content === 'object') {
    content = JSON.stringify(content, null, 2);
  } else {
    content = String(content);
  }
  
  const needsTruncation = content.length > 200;
  const MAX_EXPANDED_LENGTH = 10000;
  
  let displayContent = content;
  if (!expanded && needsTruncation) {
    displayContent = content.substring(0, 200) + '...';
  } else if (expanded && content.length > MAX_EXPANDED_LENGTH) {
    displayContent = content.substring(0, MAX_EXPANDED_LENGTH) + '...';
  }
  
  return (
    <div 
      id={`feed-item-${itemId}`}
      className="feed-item" 
      style={{ 
        backgroundColor: colors.bg,
        outline: isHighlighted ? '2px solid #615CED' : 'none',
        transition: 'outline 0.3s ease'
      }}
    >
      <div className="feed-item-header">
        <span className="feed-item-title" style={{ color: colors.text }}>
          MEMORY
        </span>
        <span className="feed-item-time">{formatTime(memory.timestamp)}</span>
      </div>
      
      <div className="feed-item-content">{displayContent}</div>
      
      {needsTruncation && (
        <button 
          className="feed-expand-btn"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? '↑ Less' : '↓ More'}
        </button>
      )}
    </div>
  );
}

/**
 * Message Item Component
 */
function MessageItem({ message, itemId, isHighlighted, getAgentModelInfo }) {
  const [expanded, setExpanded] = useState(false);
  
  // Determine colors based on message type
  let colors;
  let title;
  
  if (message.agent === 'System') {
    colors = MESSAGE_COLORS.system;
    title = 'SYSTEM';
  } else if (message.agent === 'Memory') {
    colors = MESSAGE_COLORS.memory;
    title = 'MEMORY';
  } else {
    colors = getAgentColors(message.agentId, message.agent);
    title = message.agent || 'AGENT';
  }
  
  // Get model icon for agent
  const agentModelData = message.agentId && getAgentModelInfo ? getAgentModelInfo(message.agentId) : { modelName: null, modelProvider: null };
  const modelInfo = getModelIcon(agentModelData.modelName, agentModelData.modelProvider);
  
  // 处理内容 - 如果是对象则转换为 JSON 字符串
  let content = message.content || '';
  if (typeof content === 'object') {
    content = JSON.stringify(content, null, 2);
  } else {
    content = String(content);
  }
  
  const needsTruncation = content.length > 200;
  const MAX_EXPANDED_LENGTH = 8000;
  
  let displayContent = content;
  if (!expanded && needsTruncation) {
    displayContent = content.substring(0, 200) + '...';
  } else if (expanded && content.length > MAX_EXPANDED_LENGTH) {
    displayContent = content.substring(0, MAX_EXPANDED_LENGTH) + '...';
  }
  
  return (
    <div 
      id={`feed-item-${itemId}`}
      className="feed-item" 
      style={{ 
        backgroundColor: colors.bg,
        outline: isHighlighted ? '2px solid #615CED' : 'none',
        transition: 'outline 0.3s ease'
      }}
    >
      <div className="feed-item-header">
        <span className="feed-item-title" style={{ color: colors.text, display: 'flex', alignItems: 'center', gap: '6px' }}>
          {modelInfo.logoPath && message.agent !== 'System' && message.agent !== 'Memory' && (
            <img 
              src={modelInfo.logoPath}
              alt={modelInfo.provider}
              style={{
                width: '16px',
                height: '16px',
                borderRadius: '50%',
                objectFit: 'contain'
              }}
            />
          )}
          {title}
        </span>
        <span className="feed-item-time">{formatTime(message.timestamp)}</span>
      </div>
      
      <div className="feed-item-content">{displayContent}</div>
      
      {needsTruncation && (
        <button 
          className="feed-expand-btn"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? '↑ Less' : '↓ More'}
        </button>
      )}
    </div>
  );
}
