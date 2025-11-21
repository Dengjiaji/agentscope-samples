import React, { useState } from 'react';

export default function ContactModal({ onClose }) {
  const [isClosing, setIsClosing] = useState(false);
  
  const handleClose = () => {
    setIsClosing(true);
    setTimeout(() => {
      onClose();
    }, 600);
  };
  
  const overlayStyle = {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: '#ffffff',
    zIndex: 9999,
    animation: isClosing 
      ? 'collapseUp 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards' 
      : 'expandDown 0.6s cubic-bezier(0.4, 0, 0.2, 1)',
    transformOrigin: 'top center',
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column'
  };
  
  const headerStyle = {
    padding: '20px 40px',
    borderBottom: '1px solid #e0e0e0',
    background: '#fff',
    animation: isClosing
      ? 'fadeOutContent 0.4s ease forwards'
      : 'fadeInContent 0.8s ease 0.3s backwards'
  };
  
  const contentStyle = {
    flex: 1,
    display: 'flex',
    gap: '1px',
    background: '#e0e0e0',
    animation: isClosing
      ? 'fadeOutContent 0.4s ease forwards'
      : 'fadeInContent 0.8s ease 0.4s backwards'
  };
  
  const iframeContainerStyle = {
    flex: 1,
    position: 'relative',
    background: '#fff',
    display: 'flex',
    flexDirection: 'column'
  };
  
  const iframeLabelStyle = {
    padding: '12px 20px',
    fontSize: '12px',
    fontFamily: "'IBM Plex Mono', monospace",
    color: '#666',
    borderBottom: '1px solid #e0e0e0',
    background: '#fafafa',
    display: 'flex',
    alignItems: 'center',
    gap: '8px'
  };
  
  const iframeStyle = {
    flex: 1,
    border: 'none',
    width: '100%'
  };
  
  const closeButtonStyle = {
    padding: '8px 16px',
    fontSize: '11px',
    fontFamily: "'IBM Plex Mono', monospace",
    color: '#666',
    background: 'transparent',
    border: '1px solid #e0e0e0',
    borderRadius: '4px',
    cursor: 'pointer',
    transition: 'all 0.2s'
  };
  
  return (
    <>
      <style>{`
        @keyframes expandDown {
          from {
            transform: scaleY(0);
            opacity: 0;
          }
          to {
            transform: scaleY(1);
            opacity: 1;
          }
        }
        
        @keyframes collapseUp {
          from {
            transform: scaleY(1);
            opacity: 1;
          }
          to {
            transform: scaleY(0);
            opacity: 0;
          }
        }
        
        @keyframes fadeInContent {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        
        @keyframes fadeOutContent {
          from {
            opacity: 1;
            transform: translateY(0);
          }
          to {
            opacity: 0;
            transform: translateY(-20px);
          }
        }
      `}</style>
      
      <div style={overlayStyle}>
        {/* Header */}
        <div style={headerStyle}>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between'
          }}>
            <div style={{ 
              fontSize: '14px',
              fontFamily: "'IBM Plex Mono', monospace",
              color: '#000'
            }}>
              <span style={{ fontWeight: 600 }}>Contact Us</span>
              <span style={{ margin: '0 12px', color: '#999' }}>|</span>
              <span style={{ color: '#666' }}>Collaborators' Homepages</span>
            </div>
            <button
              onClick={handleClose}
              style={closeButtonStyle}
              onMouseEnter={(e) => {
                e.target.style.background = '#f5f5f5';
                e.target.style.color = '#000';
              }}
              onMouseLeave={(e) => {
                e.target.style.background = 'transparent';
                e.target.style.color = '#666';
              }}
            >
              Close ✕
            </button>
          </div>
        </div>
        
        {/* Content - Two iframes side by side */}
        <div style={contentStyle}>
          {/* Left iframe */}
          <div style={iframeContainerStyle}>
            <div style={iframeLabelStyle}>
              <span style={{ fontWeight: 600, color: '#615CED' }}></span>
              <span style={{ color: '#999' }}>•</span>
              <a 
                href="https://1mycell.github.io/" 
                target="_blank" 
                rel="noopener noreferrer"
                style={{ 
                  color: '#615CED', 
                  textDecoration: 'none',
                  fontSize: '11px'
                }}
              >
                1mycell.github.io ↗
              </a>
            </div>
            <iframe
              src="https://1mycell.github.io/"
              style={iframeStyle}
              title="Collaborator 1 Homepage"
              sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
            />
          </div>
          
          {/* Right iframe */}
          <div style={iframeContainerStyle}>
            <div style={iframeLabelStyle}>
              <span style={{ fontWeight: 600, color: '#615CED' }}></span>
              <span style={{ color: '#999' }}>•</span>
              <a 
                href="https://dengjiaji.github.io/self/" 
                target="_blank" 
                rel="noopener noreferrer"
                style={{ 
                  color: '#615CED', 
                  textDecoration: 'none',
                  fontSize: '11px'
                }}
              >
                dengjiaji.github.io/self ↗
              </a>
            </div>
            <iframe
              src="https://dengjiaji.github.io/self/"
              style={iframeStyle}
              title="Collaborator 2 Homepage"
              sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
            />
          </div>
        </div>
        
        {/* Footer hint */}
        <div style={{
          padding: '12px',
          textAlign: 'center',
          fontSize: '11px',
          color: '#999',
          fontFamily: "'IBM Plex Mono', monospace",
          borderTop: '1px solid #e0e0e0',
          background: '#fafafa',
          cursor: 'pointer',
          animation: isClosing
            ? 'fadeOutContent 0.4s ease forwards'
            : 'fadeInContent 0.8s ease 0.5s backwards'
        }}
        onClick={handleClose}
        >
          Click here or press ESC to close
        </div>
      </div>
    </>
  );
}

