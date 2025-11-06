import React, { useEffect, useMemo, useRef, useState, useCallback } from "react";

// Configuration and constants
import { AGENTS, INITIAL_TICKERS, BUBBLE_LIFETIME_MS } from './config/constants';

// Services
import { ReadOnlyClient } from './services/websocket';

// Styles
import GlobalStyles from './styles/GlobalStyles';

// Components
import RoomView from './components/RoomView';
import NetValueChart from './components/NetValueChart';
import AgentFeed from './components/AgentFeed';
import StockLogo from './components/StockLogo';
import StatisticsView from './components/StatisticsView';
import PerformanceView from './components/PerformanceView';

// Utils
import { formatNumber, formatTickerPrice, calculateDuration } from './utils/formatters';

/**
 * Live Trading Intelligence Platform - Read-Only Dashboard
 * Geek Style - Terminal-inspired, minimal, monochrome
 * 
 */

export default function LiveTradingApp() {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('connecting'); // 'connecting' | 'connected' | 'disconnected'
  const [systemStatus, setSystemStatus] = useState('initializing'); // 'initializing' | 'running' | 'completed'
  const [currentDate, setCurrentDate] = useState(null);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [now, setNow] = useState(() => new Date());
  const [mainTab, setMainTab] = useState('live'); // 'live' | 'statistics' | 'performance'
  
  // View toggle: 'room' or 'chart'
  const [currentView, setCurrentView] = useState('chart'); // Start with chart, then animate to room
  const [isInitialAnimating, setIsInitialAnimating] = useState(true);
  
  // Chart data
  const [chartTab, setChartTab] = useState('all');
  const [portfolioData, setPortfolioData] = useState({
    netValue: 10000,
    pnl: 0,
    equity: [],
    baseline: [], // Baseline strategy (Buy & Hold - Equal Weight)
    baseline_vw: [], // Baseline strategy (Buy & Hold - Value Weighted)
    momentum: [], // Momentum strategy
    strategies: [] // Other strategies
  });
  
  // Feed data
  const [feed, setFeed] = useState([]);
  const [conferences, setConferences] = useState({ active: null, history: [] });
  
  // Statistics data
  const [holdings, setHoldings] = useState([]);
  const [trades, setTrades] = useState([]);
  const [stats, setStats] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  
  // Ticker prices (now from real-time data)
  const [tickers, setTickers] = useState(INITIAL_TICKERS);
  const [rollingTickers, setRollingTickers] = useState({});
  
  // Room bubbles
  const [bubbles, setBubbles] = useState({});
  
  // Resizable panels
  const [leftWidth, setLeftWidth] = useState(70); // percentage
  const [isResizing, setIsResizing] = useState(false);
  
  const clientRef = useRef(null);
  const containerRef = useRef(null);
  
  // Clock
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  
  // Initial animation: show room drawer sliding in
  useEffect(() => {
    // Wait a bit after mount, then trigger slide to room
    const slideTimer = setTimeout(() => {
      setCurrentView('room');
    }, 1200); // Wait 1200ms before starting animation (2x slower)
    
    // Disable animation flag after animation completes
    const completeTimer = setTimeout(() => {
      setIsInitialAnimating(false);
    }, 5000); // 1200ms delay + 1600ms animation duration + 400ms buffer
    
    return () => {
      clearTimeout(slideTimer);
      clearTimeout(completeTimer);
    };
  }, []);
  
  // Helper to check if bubble should still be visible
  const bubbleFor = (id) => {
    const b = bubbles[id];
    if (!b) return null;
    if (Date.now() - b.ts > BUBBLE_LIFETIME_MS) return null;
    return b;
  };
  
  // Auto-connect to server on mount
  useEffect(() => {
    // Define pushEvent inside useEffect to avoid dependency issues
    const handlePushEvent = (evt) => {
      if (!evt) return;
      
      try {
        handleEventInternal(evt);
      } catch (error) {
        console.error('[Event Handler] Error:', error);
      }
    };
    
    // Process historical feed: convert raw events to feed items with conference grouping
    const processHistoricalFeed = (events) => {
      console.log('📋 Historical events:', events);
      const feedItems = [];
      let currentConference = null;
      
      // Reverse to process in chronological order (oldest first)
      const chronologicalEvents = [...events].reverse();
      
      for (const evt of chronologicalEvents) {
        if (!evt || !evt.type) continue;
        
        try {
          if (evt.type === 'conference_start') {
            // Start a new conference
            currentConference = {
              id: evt.conferenceId || `conf-${evt.timestamp}`,
              title: evt.title || 'Team Conference',
              startTime: evt.timestamp || Date.now(),
              endTime: null,
              isLive: false,
              participants: evt.participants || [],
              messages: []
            };
          } else if (evt.type === 'conference_end') {
            // End current conference
            if (currentConference) {
              currentConference.endTime = evt.timestamp || Date.now();
              currentConference.duration = calculateDuration(currentConference.startTime, currentConference.endTime);
              feedItems.push({
                type: 'conference',
                id: currentConference.id,
                data: currentConference
              });
              currentConference = null;
            }
          } else {
            // Process other events
            const message = convertEventToMessage(evt);
            if (message) {
              if (currentConference) {
                // Add to current conference
                currentConference.messages.push(message);
              } else {
                // Add as standalone feed item
                const feedItem = convertEventToFeedItem(evt, message);
                if (feedItem) {
                  feedItems.push(feedItem);
                }
              }
            }
          }
        } catch (error) {
          console.error('Error processing historical event:', evt.type, error);
        }
      }
      
      // If there's an unclosed conference, add it anyway
      if (currentConference) {
        feedItems.push({
          type: 'conference',
          id: currentConference.id,
          data: currentConference
        });
      }
      
      // Reverse back to show newest first
      setFeed(feedItems.reverse());
      console.log(`✅ Processed ${feedItems.length} feed items from ${events.length} events`);
    };
    
    // Convert event to message object
    const convertEventToMessage = (evt) => {
      const agent = AGENTS.find(a => a.id === evt.agentId);
      
      switch (evt.type) {
        case 'system':
        case 'day_start':
        case 'day_complete':
        case 'day_error':
          return {
            id: `${evt.type}-${evt.timestamp || Date.now()}-${Math.random()}`,
            timestamp: evt.timestamp || Date.now(),
            agent: 'System',
            role: 'System',
            content: evt.content || `${evt.type}: ${evt.date || ''}`
          };
        
        case 'agent_message':
          return {
            id: `msg-${evt.timestamp || Date.now()}-${Math.random()}`,
            timestamp: evt.timestamp || Date.now(),
            agentId: evt.agentId,
            agent: agent?.name || evt.agentName || evt.agentId || 'Agent',
            role: agent?.role || evt.role || 'Agent',
            content: evt.content
          };
        
        case 'memory':
          return {
            id: `memory-${evt.timestamp || Date.now()}-${Math.random()}`,
            timestamp: evt.timestamp || Date.now(),
            agent: 'Memory',
            role: 'Memory',
            content: evt.content || evt.text || ''
          };
        
        case 'team_summary':
          return {
            id: `team-summary-${evt.timestamp || Date.now()}-${Math.random()}`,
            timestamp: evt.timestamp || Date.now(),
            agent: 'System',
            role: 'System',
            content: `Portfolio update: $${formatNumber(evt.balance || 0)} (${evt.pnlPct >= 0 ? '+' : ''}${(evt.pnlPct || 0).toFixed(2)}%)`
          };
        
        default:
          return null;
      }
    };
    
    // Convert event to feed item
    const convertEventToFeedItem = (evt, message) => {
      if (evt.type === 'memory') {
        return {
          type: 'memory',
          id: message.id,
          data: {
            timestamp: message.timestamp,
            content: message.content
          }
        };
      } else {
        return {
          type: 'message',
          id: message.id,
          data: message
        };
      }
    };
    
    const handleEventInternal = (evt) => {
      // Helper: Update tickers from realtime prices
      const updateTickersFromPrices = (realtimePrices) => {
        try {
          setTickers(prevTickers => {
            return prevTickers.map(ticker => {
              const realtimeData = realtimePrices[ticker.symbol];
              if (realtimeData && realtimeData.price !== null && realtimeData.price !== undefined) {
                // Initialize change to 0 if this is the first price update
                const newChange = (ticker.price === null || ticker.price === undefined) 
                  ? 0 
                  : ticker.change;
                
                return {
                  ...ticker,
                  price: realtimeData.price,
                  change: newChange
                };
              }
              return ticker;
            });
          });
        } catch (error) {
          console.error('Error updating tickers from prices:', error);
        }
      };
      
      const handlers = {
        // Connection events
        system: (e) => {
          console.log('[System]', e.content);
          if (e.content.includes('Connected')) {
            setConnectionStatus('connected');
            setIsConnected(true);
          } else if (e.content.includes('Disconnected')) {
            setConnectionStatus('disconnected');
            setIsConnected(false);
          }
          
          const message = {
            id: `sys-${Date.now()}-${Math.random()}`,
            timestamp: e.timestamp || Date.now(),
            agent: 'System',
            role: 'System',
            content: e.content
          };
          
          // Add to conference or feed depending on active conference
          setConferences(prev => {
            if (prev.active) {
              const updated = { ...prev.active, messages: [...prev.active.messages, message] };
              setFeed(f => f.map(item => 
                item.type === 'conference' && item.id === prev.active.id ? { ...item, data: updated } : item
              ));
              return { ...prev, active: updated };
            } else {
              setFeed(prevFeed => [{ type: 'message', data: message, id: message.id }, ...prevFeed].slice(0, 200));
              return prev;
            }
          });
        },
        
        // Pong response from server
        pong: (e) => {
          console.log('[Heartbeat] Pong received');
        },
        
        // Initial state from server
        initial_state: (e) => {
          try {
            const state = e.state;
            if (!state) return;
            
            setSystemStatus(state.status || 'initializing');
            setCurrentDate(state.current_date);
            
            if (state.trading_days_total) {
              setProgress({
                current: state.trading_days_completed || 0,
                total: state.trading_days_total
              });
            }
            
            if (state.portfolio) {
              setPortfolioData(prev => ({
                ...prev,
                netValue: state.portfolio.total_value || prev.netValue,
                pnl: state.portfolio.pnl_percent || 0,
                equity: state.portfolio.equity || prev.equity,
                baseline: state.portfolio.baseline || prev.baseline,
                baseline_vw: state.portfolio.baseline_vw || prev.baseline_vw,
                momentum: state.portfolio.momentum || prev.momentum,
                strategies: state.portfolio.strategies || prev.strategies
              }));
            }
            
            if (state.holdings) setHoldings(state.holdings);
            if (state.trades) setTrades(state.trades);
            if (state.stats) setStats(state.stats);
            if (state.leaderboard) setLeaderboard(state.leaderboard);
            if (state.realtime_prices) updateTickersFromPrices(state.realtime_prices);
            
            // Load and process historical feed data
            if (state.feed_history && Array.isArray(state.feed_history)) {
              console.log(`✅ Loading ${state.feed_history.length} historical events`);
              processHistoricalFeed(state.feed_history);
            }
            
            console.log('Initial state loaded');
          } catch (error) {
            console.error('Error loading initial state:', error);
          }
        },
        
        // Real-time price updates
        price_update: (e) => {
          try {
            const { symbol, price, portfolio } = e;
            
            if (!symbol || !price) {
              console.warn('[Price Update] Missing symbol or price:', e);
              return;
            }
            
            // Update ticker price with animation
            setTickers(prevTickers => {
              return prevTickers.map(ticker => {
                if (ticker.symbol === symbol) {
                  const oldPrice = ticker.price;
                  let newChange = ticker.change;
                  
                  // Calculate change if we have a previous price
                  if (oldPrice !== null && oldPrice !== undefined && isFinite(oldPrice)) {
                    const priceChange = ((price - oldPrice) / oldPrice) * 100;
                    // Initialize change if it was null, otherwise accumulate
                    newChange = (newChange !== null && newChange !== undefined) 
                      ? newChange + priceChange 
                      : priceChange;
                  } else if (newChange === null || newChange === undefined) {
                    // First price received, set change to 0
                    newChange = 0;
                  }
                  
                  // Trigger rolling animation only if price actually changed
                  if (oldPrice !== price) {
                    setRollingTickers(prev => ({ ...prev, [symbol]: true }));
                    setTimeout(() => {
                      setRollingTickers(prev => ({ ...prev, [symbol]: false }));
                    }, 500);
                  }
                  
                  return {
                    ...ticker,
                    price: price,
                    change: newChange
                  };
                }
                return ticker;
              });
            });
            
            // Update portfolio value if provided
            if (portfolio && portfolio.total_value) {
              setPortfolioData(prev => ({
                ...prev,
                netValue: portfolio.total_value,
                pnl: portfolio.pnl_percent || 0
              }));
            }
          } catch (error) {
            console.error('[Price Update] Error:', error);
          }
        },
        
        // Day progress events
        day_start: (e) => {
          setCurrentDate(e.date);
          if (e.progress !== undefined) {
            setProgress(prev => ({
              ...prev,
              current: Math.floor(e.progress * (prev.total || 1))
            }));
          }
          setSystemStatus('running');
          
          const message = {
            id: `day-start-${Date.now()}-${Math.random()}`,
            timestamp: e.timestamp || Date.now(),
            agent: 'System',
            role: 'System',
            content: `Starting day: ${e.date}`
          };
          
          setConferences(prev => {
            if (prev.active) {
              const updated = { ...prev.active, messages: [...prev.active.messages, message] };
              setFeed(f => f.map(item => 
                item.type === 'conference' && item.id === prev.active.id ? { ...item, data: updated } : item
              ));
              return { ...prev, active: updated };
            } else {
              setFeed(prevFeed => [{ type: 'message', data: message, id: message.id }, ...prevFeed].slice(0, 200));
              return prev;
            }
          });
        },
        
        day_complete: (e) => {
          // Update from day result
          const result = e.result;
          if (result && typeof result === 'object') {
            // Update portfolio equity if available
            if (result.portfolio_summary) {
              const summary = result.portfolio_summary;
              setPortfolioData(prev => {
                const newEquity = [...prev.equity];
                // Add new data point
                const dateObj = new Date(e.date);
                newEquity.push({
                  t: dateObj.getTime(),
                  v: summary.total_value || summary.cash || prev.netValue
                });
                
                return {
                  ...prev,
                  netValue: summary.total_value || summary.cash || prev.netValue,
                  pnl: summary.pnl_percent || 0,
                  equity: newEquity
                };
              });
            }
          }
          
          const message = {
            id: `day-complete-${Date.now()}-${Math.random()}`,
            timestamp: e.timestamp || Date.now(),
            agent: 'System',
            role: 'System',
            content: `Day completed: ${e.date}`
          };
          
          setConferences(prev => {
            if (prev.active) {
              const updated = { ...prev.active, messages: [...prev.active.messages, message] };
              setFeed(f => f.map(item => 
                item.type === 'conference' && item.id === prev.active.id ? { ...item, data: updated } : item
              ));
              return { ...prev, active: updated };
            } else {
              setFeed(prevFeed => [{ type: 'message', data: message, id: message.id }, ...prevFeed].slice(0, 200));
              return prev;
            }
          });
        },
        
        day_error: (e) => {
          console.error('Day error:', e.date, e.error);
          
          const message = {
            id: `day-error-${Date.now()}-${Math.random()}`,
            timestamp: e.timestamp || Date.now(),
            agent: 'System',
            role: 'System',
            content: `Day error: ${e.date} - ${e.error || 'Unknown error'}`
          };
          
          setConferences(prev => {
            if (prev.active) {
              const updated = { ...prev.active, messages: [...prev.active.messages, message] };
              setFeed(f => f.map(item => 
                item.type === 'conference' && item.id === prev.active.id ? { ...item, data: updated } : item
              ));
              return { ...prev, active: updated };
            } else {
              setFeed(prevFeed => [{ type: 'message', data: message, id: message.id }, ...prevFeed].slice(0, 200));
              return prev;
            }
          });
        },
        
        conference_start: (e) => {
          const conference = {
            id: e.conferenceId,
            title: e.title,
            startTime: e.timestamp || Date.now(),
            endTime: null,
            isLive: true,
            participants: e.participants || [],
            messages: []
          };
          setConferences(prev => ({ ...prev, active: conference }));
          setFeed(prev => [{ type: 'conference', data: conference, id: conference.id }, ...prev]);
        },
        
        conference_end: (e) => {
          setConferences(prev => {
            if (prev.active) {
              const ended = {
                ...prev.active,
                endTime: e.timestamp || Date.now(),
                isLive: false,
                duration: calculateDuration(prev.active.startTime, e.timestamp || Date.now())
              };
              setFeed(f => f.map(item =>
                item.type === 'conference' && item.id === prev.active.id ? { ...item, data: ended } : item
              ));
              return { active: null, history: [ended, ...prev.history] };
            }
            return prev;
          });
        },
        
        agent_message: (e) => {
          const agent = AGENTS.find(a => a.id === e.agentId);
          const message = {
            id: `msg-${Date.now()}-${Math.random()}`,
            timestamp: e.timestamp || Date.now(),
            agentId: e.agentId,
            agent: agent?.name || e.agentName || e.agentId || 'Agent',
            role: agent?.role || e.role || 'Agent',
            content: e.content
          };
          
          // Update bubbles for room view
          setBubbles(prev => ({
            ...prev,
            [e.agentId]: {
              text: e.content,
              ts: Date.now(),
              agentName: agent?.name || e.agentName || e.agentId
            }
          }));
          
          setConferences(prev => {
            if (prev.active) {
              const updated = { ...prev.active, messages: [...prev.active.messages, message] };
              setFeed(f => f.map(item => 
                item.type === 'conference' && item.id === prev.active.id ? { ...item, data: updated } : item
              ));
              return { ...prev, active: updated };
            } else {
              setFeed(prevFeed => [{ type: 'message', data: message, id: message.id }, ...prevFeed].slice(0, 200));
              return prev;
            }
          });
        },
        
        memory: (e) => {
          const memory = {
            id: `memory-${Date.now()}-${Math.random()}`,
            timestamp: e.timestamp || Date.now(),
            content: e.content || e.text || ''
          };
          
          setConferences(prev => {
            if (prev.active) {
              const message = {
                ...memory,
                agent: 'Memory',
                role: 'Memory'
              };
              const updated = { ...prev.active, messages: [...prev.active.messages, message] };
              setFeed(f => f.map(item => 
                item.type === 'conference' && item.id === prev.active.id ? { ...item, data: updated } : item
              ));
              return { ...prev, active: updated };
            } else {
              setFeed(prevFeed => [{ type: 'memory', data: memory, id: memory.id }, ...prevFeed].slice(0, 200));
              return prev;
            }
          });
        },
        
        team_summary: (e) => {
          setPortfolioData(prev => ({
            ...prev,
            netValue: e.balance || prev.netValue,
            pnl: e.pnlPct || 0,
            equity: e.equity || prev.equity,
            baseline: e.baseline || prev.baseline,
            baseline_vw: e.baseline_vw || prev.baseline_vw,
            momentum: e.momentum || prev.momentum
          }));
          
          const message = {
            id: `team-summary-${Date.now()}-${Math.random()}`,
            timestamp: e.timestamp || Date.now(),
            agent: 'System',
            role: 'System',
            content: `Portfolio update: $${formatNumber(e.balance || 0)} (${e.pnlPct >= 0 ? '+' : ''}${(e.pnlPct || 0).toFixed(2)}%)`
          };
          
          setConferences(prev => {
            if (prev.active) {
              const updated = { ...prev.active, messages: [...prev.active.messages, message] };
              setFeed(f => f.map(item => 
                item.type === 'conference' && item.id === prev.active.id ? { ...item, data: updated } : item
              ));
              return { ...prev, active: updated };
            } else {
              setFeed(prevFeed => [{ type: 'message', data: message, id: message.id }, ...prevFeed].slice(0, 200));
              return prev;
            }
          });
        },
        
        team_portfolio: (e) => {
          if (e.holdings) setHoldings(e.holdings);
        },
        
        team_trades: (e) => {
          if (Array.isArray(e.trades)) setTrades(e.trades);
          else if (e.trade) setTrades(prev => [e.trade, ...prev].slice(0, 100));
        },
        
        team_stats: (e) => {
          if (e.stats) setStats(e.stats);
        },
        
        team_leaderboard: (e) => {
          if (Array.isArray(e.rows)) setLeaderboard(e.rows);
          else if (Array.isArray(e.leaderboard)) setLeaderboard(e.leaderboard);
        }
      };
      
      // Call handler or do nothing
      try {
        const handler = handlers[evt.type];
        if (handler) {
          handler(evt);
        } else {
          console.log('[handleEvent] Unknown event type:', evt.type);
        }
      } catch (error) {
        console.error('[handleEvent] Error handling event:', evt.type, error);
      }
    };
    
    // Create and connect WebSocket client
    const client = new ReadOnlyClient(handlePushEvent);
    clientRef.current = client;
    client.connect();
    setConnectionStatus('connecting');
    
    return () => {
      // Cleanup on unmount
      if (clientRef.current) {
        clientRef.current.disconnect();
      }
    };
  }, []); // Empty dependency array - only run once on mount
  
  // Resizing handlers
  const handleMouseDown = (e) => {
    e.preventDefault();
    setIsResizing(true);
  };
  
  useEffect(() => {
    if (!isResizing) return;
    
    const handleMouseMove = (e) => {
      if (!containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const newLeftWidth = ((e.clientX - containerRect.left) / containerRect.width) * 100;
      
      // Limit between 30% and 85%
      if (newLeftWidth >= 30 && newLeftWidth <= 85) {
        setLeftWidth(newLeftWidth);
      }
    };
    
    const handleMouseUp = () => {
      setIsResizing(false);
    };
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  return (
    <div className="app">
      <GlobalStyles />
      
      {/* Header */}
      <div className="header">
        <div className="header-title">
          <span>TRADING INTELLIGENCE</span>
        </div>
        
        <div className="header-tabs">
          <button
            className={`header-tab ${mainTab === 'live' ? 'active' : ''}`}
            onClick={() => setMainTab('live')}
          >
            Live
          </button>
          <button
            className={`header-tab ${mainTab === 'statistics' ? 'active' : ''}`}
            onClick={() => setMainTab('statistics')}
          >
            Statistics
          </button>
          <button
            className={`header-tab ${mainTab === 'performance' ? 'active' : ''}`}
            onClick={() => setMainTab('performance')}
          >
            Agent Performance
          </button>
        </div>

        <div className="header-status">
          <span className={`status-indicator ${isConnected ? 'live' : 'disconnected'}`}>
            {isConnected ? '● LIVE' : '○ OFFLINE'}
          </span>
          {currentDate && (
            <span style={{ fontSize: '11px', color: '#666' }}>
              Trading: {currentDate}
            </span>
          )}
          {progress.total > 0 && (
            <span style={{ fontSize: '11px', color: '#666' }}>
              {progress.current}/{progress.total}
            </span>
          )}
          <span>{now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
        </div>
      </div>
      
      {/* Main Content */}
      {mainTab === 'live' ? (
        <>
          {/* Ticker Bar */}
          <div className="ticker-bar">
            <div className="ticker-track">
              {[0, 1].map((groupIdx) => (
                <div key={groupIdx} className="ticker-group">
                  {tickers.map(ticker => (
                    <div key={`${ticker.symbol}-${groupIdx}`} className="ticker-item">
                      <StockLogo ticker={ticker.symbol} size={16} />
                      <span className="ticker-symbol">{ticker.symbol}</span>
                      <span className="ticker-price">
                        <span className={`ticker-price-value ${rollingTickers[ticker.symbol] ? 'rolling' : ''}`}>
                          {ticker.price !== null && ticker.price !== undefined 
                            ? `$${formatTickerPrice(ticker.price)}` 
                            : '-'}
                        </span>
                      </span>
                      <span className={`ticker-change ${
                        ticker.change === null || ticker.change === undefined 
                          ? '' 
                          : ticker.change >= 0 ? 'positive' : 'negative'
                      }`}>
                        {ticker.change !== null && ticker.change !== undefined
                          ? `${ticker.change >= 0 ? '+' : ''}${ticker.change.toFixed(2)}%`
                          : '-'}
                      </span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
            <div className="portfolio-value">
              <span className="portfolio-label">PORTFOLIO</span>
              <span className="portfolio-amount">${formatNumber(portfolioData.netValue)}</span>
            </div>
          </div>
          
          <div className="main-container" ref={containerRef}>
            {/* Left Panel: Chart/Room Toggle View */}
            <div className="left-panel" style={{ width: `${leftWidth}%` }}>
              <div className="chart-section">
                <div className="view-container">
                  {/* Left toggle button - show when chart is visible */}
                  {currentView === 'chart' && (
                    <button
                      className="view-toggle-btn left"
                      onClick={() => setCurrentView('room')}
                      title="Show Room View"
                    >
                      ▶
                    </button>
                  )}
                  
                  {/* Right toggle button - show when room is visible */}
                  {currentView === 'room' && (
                    <button
                      className="view-toggle-btn right"
                      onClick={() => setCurrentView('chart')}
                      title="Show Chart View"
                    >
                      ◀
                    </button>
                  )}
                  
                  {/* Slider container with both views */}
                  <div className={`view-slider ${currentView === 'room' ? 'show-room' : 'show-chart'} ${!isInitialAnimating ? 'normal-speed' : ''}`}>
                    {/* Room View Panel */}
                    <div className="view-panel">
                      <RoomView bubbles={bubbles} bubbleFor={bubbleFor} />
                    </div>
                    
                    {/* Chart View Panel */}
                    <div className="view-panel">
                      <div className="chart-container">
                        {/* Floating Timeframe Tabs */}
                        <div className="chart-tabs-floating">
                          <button
                            className={`chart-tab ${chartTab === 'all' ? 'active' : ''}`}
                            onClick={() => setChartTab('all')}
                          >
                            ALL
                          </button>
                          <button
                            className={`chart-tab ${chartTab === '30d' ? 'active' : ''}`}
                            onClick={() => setChartTab('30d')}
                          >
                            30D
                          </button>
                        </div>

                        <NetValueChart 
                          equity={portfolioData.equity}
                          baseline={portfolioData.baseline}
                          baseline_vw={portfolioData.baseline_vw}
                          momentum={portfolioData.momentum}
                          strategies={portfolioData.strategies}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Resizer */}
            <div 
              className={`resizer ${isResizing ? 'resizing' : ''}`}
              onMouseDown={handleMouseDown}
            />

            {/* Right Panel: Agent Feed */}
            <div className="right-panel" style={{ width: `${100 - leftWidth}%` }}>
              <AgentFeed feed={feed} conferences={conferences} />
            </div>
          </div>
        </>
      ) : mainTab === 'statistics' ? (
        <div className="leaderboard-page">
          <StatisticsView
            trades={trades}
            holdings={holdings}
            stats={stats}
          />
        </div>
      ) : (
        <div className="performance-page">
          <PerformanceView leaderboard={leaderboard} />
        </div>
      )}
    </div>
  );
}
