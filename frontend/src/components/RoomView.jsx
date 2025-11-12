import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ASSETS, SCENE_NATIVE, AGENT_SEATS, AGENTS } from '../config/constants';
import AgentCard from './AgentCard';

/**
 * Custom hook to load an image
 */
function useImage(src) {
  const [img, setImg] = useState(null);
  useEffect(() => {
    if (!src) return;
    const image = new Image();
    image.src = src;
    image.onload = () => setImg(image);
  }, [src]);
  return img;
}

/**
 * Get rank medal/trophy for display
 */
function getRankMedal(rank) {
  if (rank === 1) return '🏆';
  if (rank === 2) return '🥈';
  if (rank === 3) return '🥉';
  return null;
}

/**
 * Room View Component
 * Displays the conference room with agents, speech bubbles, and agent cards
 * Supports click and hover (1.5s) to show agent performance cards
 */
export default function RoomView({ bubbles, bubbleFor, leaderboard }) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const bgImg = useImage(ASSETS.roomBg);
  
  // Calculate scale to fit canvas in container (80% of available space)
  const [scale, setScale] = useState(0.8);
  
  // Agent selection and hover state
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [hoveredAgent, setHoveredAgent] = useState(null);
  const [isClosing, setIsClosing] = useState(false);
  const hoverTimerRef = useRef(null);
  
  useEffect(() => {
    const updateScale = () => {
      const container = containerRef.current;
      if (!container) return;
      
      const { clientWidth, clientHeight } = container;
      if (clientWidth <= 0 || clientHeight <= 0) return;
      
      const scaleX = clientWidth / SCENE_NATIVE.width;
      const scaleY = clientHeight / SCENE_NATIVE.height;
      const newScale = Math.min(scaleX, scaleY, 1.0) * 0.8; // Scale to 80% of original size
      setScale(Math.max(0.3, newScale));
    };
    
    updateScale();
    const resizeObserver = new ResizeObserver(updateScale);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }
    window.addEventListener('resize', updateScale);
    
    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', updateScale);
    };
  }, []);
  
  // Set canvas size
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    canvas.width = SCENE_NATIVE.width;
    canvas.height = SCENE_NATIVE.height;
    
    const displayWidth = Math.round(SCENE_NATIVE.width * scale);
    const displayHeight = Math.round(SCENE_NATIVE.height * scale);
    canvas.style.width = `${displayWidth}px`;
    canvas.style.height = `${displayHeight}px`;
  }, [scale]);
  
  // Draw room background
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !bgImg) return;
    
    const ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(bgImg, 0, 0, SCENE_NATIVE.width, SCENE_NATIVE.height);
    };
    
    draw();
  }, [bgImg, scale]);
  
  // Determine which agents are speaking
  const speakingAgents = useMemo(() => {
    const speaking = {};
    AGENTS.forEach(agent => {
      const bubble = bubbleFor(agent.name);
      speaking[agent.id] = !!bubble;
    });
    return speaking;
  }, [bubbles, bubbleFor]);
  
  // Find agent data from leaderboard
  const getAgentData = (agentId) => {
    const agent = AGENTS.find(a => a.id === agentId);
    if (!agent) return null;
    
    // If no leaderboard data, return agent with default stats
    if (!leaderboard || !Array.isArray(leaderboard)) {
      return {
        ...agent,
        bull: { n: 0, win: 0, unknown: 0 },
        bear: { n: 0, win: 0, unknown: 0 },
        winRate: null,
        signals: [],
        rank: null
      };
    }
    
    const leaderboardData = leaderboard.find(lb => lb.agentId === agentId);
    
    // If agent not in leaderboard, return agent with default stats
    if (!leaderboardData) {
      return {
        ...agent,
        bull: { n: 0, win: 0, unknown: 0 },
        bear: { n: 0, win: 0, unknown: 0 },
        winRate: null,
        signals: [],
        rank: null
      };
    }
    
    // Merge data but preserve the correct avatar from AGENTS config
    return {
      ...agent,
      ...leaderboardData,
      avatar: agent.avatar  // Always use the frontend's avatar URL
    };
  };
  
  // Get agent rank for display
  const getAgentRank = (agentId) => {
    const agentData = getAgentData(agentId);
    return agentData?.rank || null;
  };
  
  // Handle agent click
  const handleAgentClick = (agentId) => {
    const agentData = getAgentData(agentId);
    if (agentData) {
      setSelectedAgent(agentData);
    }
  };
  
  // Handle agent hover
  const handleAgentMouseEnter = (agentId) => {
    setHoveredAgent(agentId);
    // Clear any existing timer
    if (hoverTimerRef.current) {
      clearTimeout(hoverTimerRef.current);
    }
    // Set new timer for 1.5 seconds
    hoverTimerRef.current = setTimeout(() => {
      const agentData = getAgentData(agentId);
      if (agentData) {
        setSelectedAgent(agentData);
      }
    }, 1500);
  };
  
  const handleAgentMouseLeave = () => {
    setHoveredAgent(null);
    // Clear timer if mouse leaves before 1.5 seconds
    if (hoverTimerRef.current) {
      clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }
  };
  
  // Handle closing with animation
  const handleClose = () => {
    setIsClosing(true);
    // Wait for animation to complete before removing
    setTimeout(() => {
      setSelectedAgent(null);
      setIsClosing(false);
    }, 200); // Match the slideUp animation duration
  };
  
  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (hoverTimerRef.current) {
        clearTimeout(hoverTimerRef.current);
      }
    };
  }, []);
  
  return (
    <div className="room-view" style={{ position: 'relative' }}>
      {/* Agents Indicator Bar */}
      <div className="room-agents-indicator">
        {AGENTS.map(agent => {
          const rank = getAgentRank(agent.id);
          const medal = rank ? getRankMedal(rank) : null;
          
          return (
            <div 
              key={agent.id}
              className={`agent-indicator ${speakingAgents[agent.id] ? 'speaking' : ''} ${hoveredAgent === agent.id ? 'hovered' : ''}`}
              onClick={() => handleAgentClick(agent.id)}
              onMouseEnter={() => handleAgentMouseEnter(agent.id)}
              onMouseLeave={handleAgentMouseLeave}
              style={{ cursor: 'pointer', position: 'relative' }}
            >
              <div className="agent-avatar-wrapper">
                <img 
                  src={agent.avatar} 
                  alt={agent.name}
                  className="agent-avatar"
                />
                <span className="agent-indicator-dot"></span>
                {medal && (
                  <span style={{
                    position: 'absolute',
                    top: -4,
                    right: -4,
                    fontSize: 16,
                    lineHeight: 1,
                    filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.3))',
                    zIndex: 10
                  }}>
                    {medal}
                  </span>
                )}
              </div>
              <span className="agent-name">{agent.name}</span>
            </div>
          );
        })}
      </div>
      
      {/* Room Canvas */}
      <div className="room-canvas-container" ref={containerRef}>
        <div className="room-scene">
          <div style={{ position: 'relative', width: Math.round(SCENE_NATIVE.width * scale), height: Math.round(SCENE_NATIVE.height * scale) }}>
            <canvas ref={canvasRef} className="room-canvas" />
            
            {/* Speech Bubbles */}
            {AGENTS.map((agent, idx) => {
              const bubble = bubbleFor(agent.name);
              if (!bubble) return null;
              
              const pos = AGENT_SEATS[idx];
              const left = Math.round((pos.x - 20) * scale);
              const top = Math.round((pos.y - 150) * scale);
              
              // Truncate long text
              const maxLength = 80;
              const displayText = bubble.text.length > maxLength 
                ? bubble.text.substring(0, maxLength) + '...' 
                : bubble.text;
              
              return (
                <div 
                  key={agent.id} 
                  className="room-bubble"
                  style={{ left, top }}
                >
                  <div className="room-bubble-name">{bubble.agentName || agent.name}</div>
                  {displayText}
                </div>
              );
            })}
          </div>
        </div>
        
        {/* Agent Card - Dropdown style below indicator bar */}
        {selectedAgent && (
          <>
            {/* Transparent overlay to close card */}
            <div 
              style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                zIndex: 999
              }}
              onClick={handleClose}
            />
            
            {/* Agent Card */}
            <AgentCard 
              agent={selectedAgent}
              isClosing={isClosing}
              onClose={handleClose}
            />
          </>
        )}
      </div>
    </div>
  );
}

