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
  const [expanded, setExpanded] = useState(false);
  const displayMessages = expanded ? conference.messages : conference.messages.slice(0, 3);
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
        {displayMessages.map((msg, idx) => {
          const agentColors = getAgentColors(msg.agentId, msg.agent);
          return (
            <div className="conf-message-item" key={idx}>
              <span className="conf-agent-name" style={{ color: agentColors.text }}>
                {msg.agent}
              </span>
              <span className="conf-message-content">{msg.content}</span>
            </div>
          );
        })}
      </div>
      
      {conference.messages.length > 3 && (
        <button className="feed-expand-btn" onClick={() => setExpanded(!expanded)}>
          {expanded ? '↑ Less' : `↓ ${conference.messages.length - 3} more`}
        </button>
      )}
    </div>
  );
}

/**
 * Memory Item Component
 */
function MemoryItem({ memory }) {
  const [expanded, setExpanded] = useState(false);
  const colors = MESSAGE_COLORS.memory;
  
  const content = memory.content || '';
  const needsTruncation = content.length > 200;
  const MAX_EXPANDED_LENGTH = 1000;
  
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
  } else {
    colors = getAgentColors(message.agentId, message.agent);
    title = message.agent || 'AGENT';
  }
  
  const content = message.content || '';
  const needsTruncation = content.length > 200;
  const MAX_EXPANDED_LENGTH = 1000;
  
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
