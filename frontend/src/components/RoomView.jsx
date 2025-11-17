import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ASSETS, SCENE_NATIVE, AGENT_SEATS, AGENTS, ASSET_BASE_URL } from '../config/constants';
import AgentCard from './AgentCard';

/**
 * Custom hook to load an image
 */
function useImage(src) {
  const [img, setImg] = useState(null);
  useEffect(() => {
    if (!src) {
      setImg(null);
      return;
    }
    // Reset image state when src changes
    setImg(null);
    const image = new Image();
    image.src = src;
    image.onload = () => setImg(image);
    image.onerror = () => {
      console.error(`Failed to load image: ${src}`);
      setImg(null);
    };
    // Cleanup: cancel loading if src changes
    return () => {
      image.onload = null;
      image.onerror = null;
    };
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
export default function RoomView({ bubbles, bubbleFor, leaderboard, marketStatus }) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  
  // Select background image based on market status
  const roomBgSrc = useMemo(() => {
    const status = marketStatus?.status;
    
    // Check if market is closed (handle both 'close' and 'closed')
    if (marketStatus && (status === 'close' || status === 'closed')) {
      return `${ASSET_BASE_URL}/full_room_dark.png`;
    }
    
    // Default to light background (market open or no status)
    return ASSETS.roomBg; // full_room_with_roles_tech_style.png
  }, [marketStatus?.status]);
  
  const bgImg = useImage(roomBgSrc);
  
  // Calculate scale to fit canvas in container (80% of available space)
  const [scale, setScale] = useState(0.8);
  
  // Agent selection and hover state
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [hoveredAgent, setHoveredAgent] = useState(null);
  const [isClosing, setIsClosing] = useState(false);
  const hoverTimerRef = useRef(null);
  const closeTimerRef = useRef(null);
  
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
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    
    // Clear canvas first
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw image if loaded
    if (bgImg) {
      ctx.drawImage(bgImg, 0, 0, SCENE_NATIVE.width, SCENE_NATIVE.height);
    }
  }, [bgImg, scale, roomBgSrc]);
  
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
    // Cancel any closing animation
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    setIsClosing(false);
    
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
      hoverTimerRef.current = null;
    }
    // Cancel any closing animation
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    setIsClosing(false);
    
    // If there's already a selected agent, switch immediately
    // Otherwise, show after a short delay (0ms = immediate)
    const agentData = getAgentData(agentId);
    if (agentData) {
      if (selectedAgent) {
        // Already have a card open, switch immediately
        setSelectedAgent(agentData);
      } else {
        // No card open, show after delay (currently 0ms = immediate)
        hoverTimerRef.current = setTimeout(() => {
          setSelectedAgent(agentData);
          hoverTimerRef.current = null;
        }, 0);
      }
    }
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
    closeTimerRef.current = setTimeout(() => {
      setSelectedAgent(null);
      setIsClosing(false);
      closeTimerRef.current = null;
    }, 200); // Match the slideUp animation duration
  };
  
  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (hoverTimerRef.current) {
        clearTimeout(hoverTimerRef.current);
      }
      if (closeTimerRef.current) {
        clearTimeout(closeTimerRef.current);
      }
    };
  }, []);
  
  return (
    <div className="room-view">
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
            >
              <div className="agent-avatar-wrapper">
                <img 
                  src={agent.avatar} 
                  alt={agent.name}
                  className="agent-avatar"
                />
                <span className="agent-indicator-dot"></span>
                {medal && (
                  <span className="agent-rank-medal">
                    {medal}
                  </span>
                )}
              </div>
              <span className="agent-name">{agent.name}</span>
            </div>
          );
        })}
        
        {/* Hint Text */}
        <div className="agent-hint-text">
          Click avatar to view details
        </div>
      </div>
      
      {/* Room Canvas */}
      <div className="room-canvas-container" ref={containerRef}>
        <div className="room-scene">
          <div className="room-scene-wrapper" style={{ width: Math.round(SCENE_NATIVE.width * scale), height: Math.round(SCENE_NATIVE.height * scale) }}>
            <canvas ref={canvasRef} className="room-canvas" />
            
            {/* Speech Bubbles */}
            {AGENTS.map((agent, idx) => {
              const bubble = bubbleFor(agent.name);
              if (!bubble) return null;
              
              const pos = AGENT_SEATS[idx];
              const left = Math.round((pos.x - 20) * scale);
              const top = Math.round((pos.y - 150) * scale);
              
              // Truncate long text
              const maxLength = 100;
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
              className="agent-card-overlay"
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

