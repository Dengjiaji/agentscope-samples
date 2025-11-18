import React, { useState } from 'react';

export default function AboutModal({ onClose }) {
  const [isClosing, setIsClosing] = useState(false);
  const [language, setLanguage] = useState('en'); // 'en' or 'zh'
  
  const handleClose = () => {
    setIsClosing(true);
    // Wait for animation to complete before actually closing
    setTimeout(() => {
      onClose();
    }, 600); // Match animation duration
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
    overflowY: 'auto'
  };
  
  const contentStyle = {
    maxWidth: '900px',
    width: '90%',
    margin: '0 auto',
    textAlign: 'left',
    fontFamily: "'IBM Plex Mono', monospace",
    color: '#000000',
    lineHeight: 1.8,
    fontSize: '14px',
    letterSpacing: '0.01em',
    padding: '60px 20px 80px',
    animation: isClosing
      ? 'fadeOutContent 0.4s ease forwards'
      : 'fadeInContent 0.8s ease 0.3s backwards'
  };
  
  const highlight = {
    color: '#615CED',
    fontWeight: 600
  };
  
  const linkStyle = {
    color: '#615CED',
    textDecoration: 'none',
    borderBottom: '1px solid #615CED',
    transition: 'all 0.2s'
  };
  
  const closeHintStyle = {
    marginTop: '50px',
    fontSize: '11px',
    color: '#999',
    cursor: 'pointer',
    textAlign: 'center'
  };
  
  const languageSwitchStyle = {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: '25px',
    marginTop: '10px',
    gap: '0px',
    fontSize: '11px',
    fontFamily: "'IBM Plex Mono', monospace"
  };
  
  const getLangStyle = (isActive) => ({
    padding: '3px 8px',
    cursor: 'pointer',
    transition: 'all 0.2s',
    background: isActive ? '#000' : '#fff',
    color: isActive ? '#fff' : '#000',
    border: 'none'
  });
  
  const content = {
    en: {
      intro: "AI is no longer entering the financial markets as isolated models—it is stepping in as ",
      introHighlight1: "teams",
      introContinue: ", collaborating in one of the most challenging and noise-filled ",
      introHighlight2: "real-time environments",
      introContinue2: ".",
      
      question: "What happens if AI models don't compete with each other, but instead trade like a ",
      questionHighlight: "well-coordinated, high-performance team",
      questionEnd: "?",
      
      point1Highlight: "✦ Complementary skills",
      point1: " - across multiple agents—data analysis, strategy generation, risk management—working together like a real trading desk, exchanging information through notifications and meetings.",
      
      point2Highlight: "✦ An agent system that continually evolves",
      point2: " — with memory modules that retain experience, learn from market feedback, reflect, and develop their own methodology over time.",
      
      point3Highlight: "✦ AI teams interacting with live markets",
      point3: " — learning from real-time data and making immediate decisions, not just theoretical simulations.",
      
      opensource: "Everything is fully open-source. Built on AgentScope, using ReMe for memory management.",
      
      github: "github.com/agentscope-ai/agentscope-samples"
    },
    zh: {
      intro: "如果不是让模型彼此竞争，而是像一支高效协作的团队一样进行实时交易，会发生什么？",
      question: "我们希望Agents不再单打独斗，而是「组团」进入实时金融市场——这一十分困难且充满噪声的环境。",
      
      title1: "✦ 多智能体的技能互补",
      point1: "不同模型、不同角色的智能体像真实的金融团队一样协作，各自承担数据分析、策略生成、风险控制等职责。",
      
      title2: "✦ 能够持续进化的智能体系统",
      point2: "依托「记忆」模块，每个智能体都能跨回合保留经验，不断学习、反思与调整。我们希望能看到在长期实时交易中，Agent形成自己的独特方法论，而不是一次性偶然的推理。",
      
      title3: "✦ 实时参与市场的 AI Agents",
      point3: "Agents从实时行情中学习，并给予即时决策；不是纸上谈兵，而是面对市场的真实波动。",
      
      opensource: "我们已经在github上开源。",
      opensourceSub: "EvoTraders 基于 AgentScope 搭建，并使用其中的 ReMe 作为记忆管理核心。",
      findMore: "你可以在此找到完整项目与示例：",
      
      github: "github.com/agentscope-ai/agentscope-samples"
    }
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
      
      <div style={overlayStyle} onClick={handleClose}>
        {/* Header */}
        <div className="header" style={{ 
          animation: isClosing
            ? 'fadeOutContent 0.4s ease forwards'
            : 'fadeInContent 0.8s ease 0.3s backwards'
        }} onClick={(e) => e.stopPropagation()}>
          <div className="header-title" style={{ flex: '0 1 auto', minWidth: 0 }}>
            <span 
              className="header-link" 
              style={{ padding: '4px 8px', borderRadius: '3px', cursor: 'pointer' }}
              onClick={handleClose}
            >
              EvoTraders <span className="link-arrow">↙</span>
            </span>
            <span style={{
              width: '2px',
              height: '16px',
              background: '#666',
              margin: '0 16px',
              display: 'inline-block',
              verticalAlign: 'middle'
            }} />
            <a href="https://github.com/agentscope-ai" target="_blank" rel="noopener noreferrer" className="header-link">
              About Us <span className="link-arrow">↗</span>
            </a>
            <span style={{
              width: '2px',
              height: '16px',
              background: '#666',
              margin: '0 16px',
              display: 'inline-block',
              verticalAlign: 'middle'
            }} />
            <a href="https://github.com/agentscope-ai/agentscope-samples" target="_blank" rel="noopener noreferrer" className="header-link">
              <svg 
                width="14" 
                height="14" 
                viewBox="0 0 24 24" 
                fill="currentColor" 
                style={{ 
                  display: 'inline-block', 
                  verticalAlign: 'middle', 
                  marginRight: '6px',
                  marginBottom: '2px'
                }}
              >
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
              </svg>
              agentscope-samples <span className="link-arrow">↗</span>
            </a>
            <span style={{
              width: '2px',
              height: '16px',
              background: '#666',
              margin: '0 16px',
              display: 'inline-block',
              verticalAlign: 'middle'
            }} />
            <a href="https://1mycell.github.io/" className="header-link">
              Contact Us <span className="link-arrow">↗</span>
            </a>
          </div>
        </div>
        
        {/* Content */}
        <div style={contentStyle} onClick={(e) => e.stopPropagation()}>
          {/* Language Switch */}
          <div style={languageSwitchStyle}>
            <span 
              style={getLangStyle(language === 'zh')}
              onClick={() => setLanguage('zh')}
            >
              中文
            </span>
            <span style={{ padding: '0 4px', color: '#999' }}>｜</span>
            <span 
              style={getLangStyle(language === 'en')}
              onClick={() => setLanguage('en')}
            >
              EN
            </span>
          </div>
          
          {language === 'en' ? (
            // English Content
            <>
              <div style={{ marginBottom: '30px' }}>
                {content.en.intro}
                <span style={highlight}>{content.en.introHighlight1}</span>
                {content.en.introContinue}
                <span style={highlight}>{content.en.introHighlight2}</span>
                {content.en.introContinue2}
              </div>
              
              <div style={{ marginBottom: '40px', fontSize: '15px', fontWeight: 600 }}>
                {content.en.question}
                <span style={highlight}>{content.en.questionHighlight}</span>
                {content.en.questionEnd}
              </div>
              
              <div style={{ marginBottom: '25px' }}>
                <span style={highlight}>{content.en.point1Highlight}</span>
                {content.en.point1}
              </div>
              
              <div style={{ marginBottom: '25px' }}>
                <span style={highlight}>{content.en.point2Highlight}</span>
                {content.en.point2}
              </div>
              
              <div style={{ marginBottom: '40px' }}>
                <span style={highlight}>{content.en.point3Highlight}</span>
                {content.en.point3}
              </div>
              
              <div style={{ marginBottom: '25px', opacity: 0.7 }}>
                {content.en.opensource}
              </div>
            </>
          ) : (
            // Chinese Content
            <>
              <div style={{ marginBottom: '30px' }}>
                {content.zh.intro}
              </div>
              
              <div style={{ marginBottom: '40px', fontSize: '15px', fontWeight: 600 }}>
                {content.zh.question}
              </div>
              
              <div style={{ marginBottom: '30px', fontSize: '14px', opacity: 0.8 }}>
                {content.zh.trying}
              </div>
              
              <div style={{ marginBottom: '30px' }}>
                <div style={{ ...highlight, marginBottom: '10px' }}>
                  {content.zh.title1}
                </div>
                <div style={{ marginBottom: '10px' }}>
                  {content.zh.point1}
                </div>
                <div style={{ fontSize: '13px', opacity: 0.7 }}>
                  {content.zh.point1Sub}
                </div>
              </div>
              
              <div style={{ marginBottom: '30px' }}>
                <div style={{ ...highlight, marginBottom: '10px' }}>
                  {content.zh.title2}
                </div>
                <div style={{ marginBottom: '10px' }}>
                  {content.zh.point2}
                </div>
                <div style={{ fontSize: '13px', opacity: 0.7 }}>
                  {content.zh.point2Sub}
                </div>
              </div>
              
              <div style={{ marginBottom: '30px' }}>
                <div style={{ ...highlight, marginBottom: '10px' }}>
                  {content.zh.title3}
                </div>
                <div>
                  {content.zh.point3}
                </div>
              </div>
              
              <div style={{ marginBottom: '10px', opacity: 0.7 }}>
                {content.zh.opensource}
              </div>
              <div style={{ marginBottom: '25px', opacity: 0.7 }}>
                {content.zh.opensourceSub}
              </div>
              
              <div style={{ marginBottom: '10px', fontSize: '14px' }}>
                {content.zh.findMore}
              </div>
            </>
          )}
          
          <div style={{ marginTop: '40px' }}>
            <a 
              href="https://github.com/agentscope-ai/agentscope-samples" 
              target="_blank" 
              rel="noopener noreferrer"
              style={linkStyle}
            >
              {language === 'en' ? content.en.github : content.zh.github}
            </a>
          </div>
          
          <div style={closeHintStyle} onClick={handleClose}>
            {language === 'en' ? 'Click here to close' : '点击此处关闭'}
          </div>
        </div>
      </div>
    </>
  );
}

