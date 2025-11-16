import React, { useState } from 'react';
import { formatTime, calculateDuration } from '../utils/formatters';
import { AGENTS, MESSAGE_COLORS, getAgentColors } from '../config/constants';

/**
 * Agent Feed Component
 * Displays real-time feed of agent messages and conference updates
 * Minimalist design with color-coded messages
 */
export default function AgentFeed({ feed, conferences }) {
  return (
    <div className="agent-feed">
      <div className="feed-header">
        <h3 className="feed-title">Agent Feed</h3>
      </div>
      
      <div className="feed-content">
        {feed.length === 0 && (
          <div className="empty-state">Waiting for system updates...</div>
        )}
        
        {feed.map(item => {
          if (item.type === 'conference') {
            return <ConferenceItem key={item.id} conference={item.data} />;
          } else if (item.type === 'memory') {
            return <MemoryItem key={item.id} memory={item.data} />;
          } else {
            return <MessageItem key={item.id} message={item.data} />;
          }
        })}
      </div>
    </div>
  );
}

/**
 * Conference Item Component
 */
function ConferenceItem({ conference }) {
  const colors = MESSAGE_COLORS.conference;
  
  return (
    <div className="feed-item" style={{ backgroundColor: colors.bg }}>
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
          <ConferenceMessage key={idx} message={msg} />
        ))}
      </div>
    </div>
  );
}

/**
 * Conference Message Component - Individual message with truncation
 */
function ConferenceMessage({ message }) {
  const [expanded, setExpanded] = useState(false);
  
  let agentColors;
  if (message.agent === 'System') {
    agentColors = MESSAGE_COLORS.system;
  } else if (message.agent === 'Memory') {
    agentColors = MESSAGE_COLORS.memory;
  } else {
    agentColors = getAgentColors(message.agentId, message.agent);
  }
  
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
      <div className="conf-agent-name" style={{ color: agentColors.text }}>
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
function MemoryItem({ memory }) {
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
    <div className="feed-item" style={{ backgroundColor: colors.bg }}>
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
function MessageItem({ message }) {
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
    <div className="feed-item" style={{ backgroundColor: colors.bg }}>
      <div className="feed-item-header">
        <span className="feed-item-title" style={{ color: colors.text }}>
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
