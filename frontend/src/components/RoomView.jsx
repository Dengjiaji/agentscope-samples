import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ASSETS, SCENE_NATIVE, AGENT_SEATS, AGENTS } from '../config/constants';

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
 * Room View Component
 * Displays the conference room with agents and speech bubbles
 */
export default function RoomView({ bubbles, bubbleFor }) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const bgImg = useImage(ASSETS.roomBg);
  
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
      const bubble = bubbleFor(agent.id);
      speaking[agent.id] = !!bubble;
    });
    return speaking;
  }, [bubbles, bubbleFor]);
  
  return (
    <div className="room-view">
      {/* Agents Indicator Bar */}
      <div className="room-agents-indicator">
        {AGENTS.map(agent => (
          <div 
            key={agent.id} 
            className={`agent-indicator ${speakingAgents[agent.id] ? 'speaking' : ''}`}
          >
            <span className="agent-indicator-dot"></span>
            <span>{agent.name}</span>
          </div>
        ))}
      </div>
      
      {/* Room Canvas */}
      <div className="room-canvas-container" ref={containerRef}>
        <div className="room-scene">
          <div style={{ position: 'relative', width: Math.round(SCENE_NATIVE.width * scale), height: Math.round(SCENE_NATIVE.height * scale) }}>
            <canvas ref={canvasRef} className="room-canvas" />
            
            {/* Speech Bubbles */}
            {AGENTS.map((agent, idx) => {
              const bubble = bubbleFor(agent.id);
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
      </div>
    </div>
  );
}

