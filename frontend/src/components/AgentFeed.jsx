import React, { useState } from 'react';
import { formatTime, calculateDuration } from '../utils/formatters';

/**
 * Agent Feed Component
 * Displays real-time feed of agent messages and conference updates
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
            return <ConferenceCard key={item.id} conference={item.data} />;
          } else {
            return <MessageCard key={item.id} message={item.data} />;
          }
        })}
      </div>
    </div>
  );
}

/**
 * Conference Card Component
 * Displays a conference with messages
 */
function ConferenceCard({ conference }) {
  const [expanded, setExpanded] = useState(false);
  const displayMessages = expanded ? conference.messages : conference.messages.slice(0, 3);
  
  return (
    <div className="feed-card conference-card">
      <div className="card-header">
        <div className="card-title">
          <span className="card-icon">▶</span>
          <span>CONF: {conference.title}</span>
        </div>
        {conference.isLive && <span className="live-badge">● LIVE</span>}
      </div>
      
      <div className="conference-meta">
        <span>{formatTime(conference.startTime)} - {conference.endTime ? formatTime(conference.endTime) : 'now'}</span>
        {conference.duration && <span>({conference.duration})</span>}
        <span>👥 {conference.participants.length}</span>
      </div>
      
      <div className="conference-messages">
        {displayMessages.map((msg, idx) => (
          <div className="conf-message" key={idx}>
            <div className="msg-header">
              <span className="msg-agent">{msg.agent} ({msg.role})</span>
              <span className="msg-time">{formatTime(msg.timestamp)}</span>
            </div>
            <div className="msg-content">{msg.content}</div>
          </div>
        ))}
      </div>
      
      {conference.messages.length > 3 && (
        <button className="expand-btn" onClick={() => setExpanded(!expanded)}>
          {expanded ? '▲ COLLAPSE' : `▼ VIEW ${conference.messages.length - 3} MORE`}
        </button>
      )}
    </div>
  );
}

/**
 * Message Card Component
 * Displays a single agent message
 */
function MessageCard({ message }) {
  const [expanded, setExpanded] = useState(false);
  
  const messageTitle = message.agent === 'System' ? 'SYSTEM' : (message.agent || 'MESSAGE');
  
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
    <div className="feed-card message-card">
      <div className="card-header">
        <div className="card-title">
          <span>{messageTitle}</span>
        </div>
        <span className="card-time">{formatTime(message.timestamp)}</span>
      </div>
      
      <div className="message-content-wrapper">
        <div className="message-text">{displayContent}</div>
        {needsTruncation && (
          <button 
            className="message-expand-btn"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? 'Show less' : 'Show more'}
          </button>
        )}
      </div>
    </div>
  );
}

