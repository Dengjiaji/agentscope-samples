import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { ASSETS, SCENE_NATIVE, AGENT_SEATS, AGENTS, ASSET_BASE_URL } from '../config/constants';
import AgentCard from './AgentCard';
import { getModelIcon } from '../utils/modelIcons';

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
    // Reset image state when backend changes
    setImg(null);
    const image = new Image();
    image.src = src;
    image.onload = () => setImg(image);
    image.onerror = () => {
      console.error(`Failed to load image: ${src}`);
      setImg(null);
    };
    // Cleanup: cancel loading if backend changes
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
 * Supports replay mode for reviewing past trading day decisions
 */
export default function RoomView({ bubbles, bubbleFor, leaderboard, marketStatus, wsClient, onReplayRequest }) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  
  // Agent selection and hover state
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [hoveredAgent, setHoveredAgent] = useState(null);
  const [isClosing, setIsClosing] = useState(false);
  const hoverTimerRef = useRef(null);
  const closeTimerRef = useRef(null);
  
  // Replay state (must be defined before using in useMemo)
  const [isReplaying, setIsReplaying] = useState(false);
  const [replayData, setReplayData] = useState(null);
  const [replayBubbles, setReplayBubbles] = useState({});
  const [isLoadingReplay, setIsLoadingReplay] = useState(false);
  const replayTimerRef = useRef(null);
  const replayTimeoutsRef = useRef([]);
  const replayCallbackRef = useRef(null);
  
  // Select background image based on market status and replay state
  const roomBgSrc = useMemo(() => {
    const status = marketStatus?.status;
    
    // During replay, always use light background with roles
    if (isReplaying) {
      return ASSETS.roomBg; // full_room_with_roles_tech_style.png
    }
    
    // Check if market is closed (handle both 'close' and 'closed')
    if (marketStatus && (status === 'close' || status === 'closed')) {
      // return `${ASSET_BASE_URL}/full_room_dark.png`;
      return ASSETS.roomBg;
    }
    
    // Default to light background (market open or no status)
    return ASSETS.roomBg; // full_room_with_roles_tech_style.png
  }, [marketStatus?.status, isReplaying]);
  
  const bgImg = useImage(roomBgSrc);
  
  // Calculate scale to fit canvas in container (80% of available space)
  const [scale, setScale] = useState(0.8);
  
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
      // Clean up replay timers
      if (replayTimerRef.current) {
        clearTimeout(replayTimerRef.current);
      }
      replayTimeoutsRef.current.forEach(timeoutId => clearTimeout(timeoutId));
      replayTimeoutsRef.current = [];
    };
  }, []);
  
  // Determine if replay button should be shown (only when market is closed)
  const showReplayButton = useMemo(() => {
    const status = marketStatus?.status;
    return (status === 'close' || status === 'closed') && !isReplaying;
  }, [marketStatus?.status, isReplaying]);
  
  // Request replay data from server
  const handleReplayClick = useCallback(() => {
    if (!wsClient || isLoadingReplay) return;
    
    try {
      setIsLoadingReplay(true);
      
      // Store callback for when data is received
      replayCallbackRef.current = (data, error) => {
        if (error) {
          console.error('❌ Replay error:', error);
          alert(`Replay loading failed: ${error}`);
          setIsLoadingReplay(false);
          replayCallbackRef.current = null;
        } else if (data) {
          console.log('📦 Received replay data:', data);
          setReplayData(data);
          startReplay(data);
          setIsLoadingReplay(false);
          replayCallbackRef.current = null;
        }
      };
      
      // Notify parent to handle replay request
      if (onReplayRequest) {
        onReplayRequest(replayCallbackRef.current);
      }
      
      // Send request via wsClient
      const success = wsClient.send({
        type: 'get_replay_data'
      });
      
      if (success) {
        console.log('📤 Sent replay data request');
      } else {
        console.error('Failed to send replay request');
        setIsLoadingReplay(false);
        replayCallbackRef.current = null;
        alert('Failed to send replay request');
      }
      
    } catch (error) {
      console.error('Replay request failed:', error);
      alert('Replay request failed');
      setIsLoadingReplay(false);
      replayCallbackRef.current = null;
    }
  }, [wsClient, isLoadingReplay, onReplayRequest]);
  
  // Start replay with data
  const startReplay = useCallback((data) => {
    if (!data || !data.events || data.events.length === 0) {
      alert('没有可回放的数据');
      return;
    }
    
    console.log(`🎬 Starting replay for ${data.date} with ${data.event_count} events`);
    
    setIsReplaying(true);
    setReplayBubbles({});
    
    // Clear any existing timeouts
    replayTimeoutsRef.current.forEach(timeoutId => clearTimeout(timeoutId));
    replayTimeoutsRef.current = [];
    
    // Schedule all events
    const events = data.events;
    
    events.forEach((event, index) => {
      const delay = event.timestamp;
      
      // Show bubble
      const showTimeout = setTimeout(() => {
        const bubbleId = `replay_${event.agent_id}_${index}`;
        
        setReplayBubbles(prev => ({
          ...prev,
          [bubbleId]: {
            id: bubbleId,
            agentId: event.agent_id,
            agentName: event.agent_name,
            text: event.text,
            timestamp: Date.now(),
            phase: event.phase
          }
        }));
        
        // Remove bubble after 5 seconds
        const hideTimeout = setTimeout(() => {
          setReplayBubbles(prev => {
            const newBubbles = { ...prev };
            delete newBubbles[bubbleId];
            return newBubbles;
          });
        }, 5000);
        
        replayTimeoutsRef.current.push(hideTimeout);
      }, delay);
      
      replayTimeoutsRef.current.push(showTimeout);
    });
    
    // End replay after all events complete
    const totalDuration = data.total_duration + 6000; // Add 6 seconds buffer
    const endTimeout = setTimeout(() => {
      console.log('✅ Replay completed');
      setIsReplaying(false);
      setReplayBubbles({});
      replayTimeoutsRef.current = [];
    }, totalDuration);
    
    replayTimeoutsRef.current.push(endTimeout);
    
  }, []);
  
  // Stop replay
  const stopReplay = useCallback(() => {
    console.log('⏹️ Stopping replay');
    
    // Clear all timeouts
    replayTimeoutsRef.current.forEach(timeoutId => clearTimeout(timeoutId));
    replayTimeoutsRef.current = [];
    
    if (replayTimerRef.current) {
      clearTimeout(replayTimerRef.current);
      replayTimerRef.current = null;
    }
    
    setIsReplaying(false);
    setReplayBubbles({});
  }, []);
  
  // Get bubble for specific agent (supports both live and replay mode)
  const getBubbleForAgent = useCallback((agentName) => {
    if (isReplaying) {
      // Find replay bubble for this agent
      const bubble = Object.values(replayBubbles).find(b => {
        const agent = AGENTS.find(a => a.id === b.agentId);
        return agent && agent.name === agentName;
      });
      return bubble || null;
    } else {
      // Use normal bubbleFor function
      return bubbleFor(agentName);
    }
  }, [isReplaying, replayBubbles, bubbleFor]);
  
  return (
    <div className="room-view">
      {/* Agents Indicator Bar */}
      <div className="room-agents-indicator">
        {AGENTS.map(agent => {
          const rank = getAgentRank(agent.id);
          const medal = rank ? getRankMedal(rank) : null;
          const agentData = getAgentData(agent.id);
          const modelInfo = getModelIcon(agentData?.modelName, agentData?.modelProvider);
          
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
                {modelInfo.logoPath && (
                  <img 
                    src={modelInfo.logoPath}
                    alt={modelInfo.provider}
                    className="agent-model-badge"
                    style={{
                      position: 'absolute',
                      top: -12,
                      right: -12,
                      width: 25,
                      height: 25,
                      borderRadius: '50%',
                      border: '2px solid #ffffff',
                      background: '#ffffff',
                      objectFit: 'contain',
                      padding: 2,
                      boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                      pointerEvents: 'none'
                    }}
                  />
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
              const bubble = getBubbleForAgent(agent.name);
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
        
        {/* Replay Button - Only shown when market is closed and not replaying */}
        {showReplayButton && (
          <div className="replay-button-container">
            <button 
              className="replay-button"
              onClick={handleReplayClick}
              disabled={isLoadingReplay}
              title="Replay latest trading day decisions"
            >
              <span className="replay-icon">{isLoadingReplay ? '⏳' : '⏮'}</span>
              <span>{isLoadingReplay ? 'LOADING...' : 'REPLAY'}</span>
            </button>
          </div>
        )}
        
        {/* Replay Indicator - Shown during replay */}
        {isReplaying && (
          <div className="replay-indicator">
            <span className="replay-status">
              ▶ REPLAYING {replayData?.date}
            </span>
            <button 
              className="stop-replay-button"
              onClick={stopReplay}
            >
              ■ STOP
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

