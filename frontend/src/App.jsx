import React, { useEffect, useMemo, useRef, useState, useCallback } from "react";

// Configuration and constants
import { AGENTS, INITIAL_TICKERS } from './config/constants';

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
import AboutModal from './components/AboutModal';
import RulesView from './components/RulesView';
import Header from './components/Header.jsx';

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
  const [showAboutModal, setShowAboutModal] = useState(false);
  
  // View toggle: 'rules' | 'room' | 'chart' | 'statistics'
  const [currentView, setCurrentView] = useState('chart'); // Start with chart, then animate to room
  const [isInitialAnimating, setIsInitialAnimating] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [isUpdating, setIsUpdating] = useState(false);
  
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
  
  // Market status
  const [serverMode, setServerMode] = useState(null); // 'live' | 'backtest' | null
  const [marketStatus, setMarketStatus] = useState(null); // { status, status_text, ... }
  const [virtualTime, setVirtualTime] = useState(null); // Virtual time from server (for mock mode)
  
  const clientRef = useRef(null);
  const containerRef = useRef(null);
  
  // Track last virtual time update to calculate increment
  const lastVirtualTimeRef = useRef(null);
  const virtualTimeOffsetRef = useRef(0);
  
  // Replay callback ref
  const replayCallbackRef = useRef(null);
  
  // Set default chart tab based on market status
  useEffect(() => {
    if (marketStatus && marketStatus.status) {
      if (marketStatus.status === 'open') {
        setChartTab('live');
      } else if (marketStatus.status === 'close' || marketStatus.status === 'closed') {
        setChartTab('all');
      }
    }
  }, [marketStatus?.status]);
  
  // Clock - use virtual time if available (for mock mode)
  useEffect(() => {
    if (virtualTime) {
      // In mock mode, calculate offset from real time
      const virtualTimeMs = new Date(virtualTime).getTime();
      const realTimeMs = Date.now();
      virtualTimeOffsetRef.current = virtualTimeMs - realTimeMs;
      lastVirtualTimeRef.current = virtualTimeMs;
      setNow(new Date(virtualTime));
      
      // Update clock every second based on offset
      const id = setInterval(() => {
        const currentRealTime = Date.now();
        const currentVirtualTime = currentRealTime + virtualTimeOffsetRef.current;
        setNow(new Date(currentVirtualTime));
      }, 1000);
      
      return () => clearInterval(id);
    } else {
      // In live mode, use real time
      const id = setInterval(() => setNow(new Date()), 1000);
      return () => clearInterval(id);
    }
  }, [virtualTime]);
  
  // Update clock when virtual time changes (recalculate offset)
  useEffect(() => {
    if (virtualTime) {
      const virtualTimeMs = new Date(virtualTime).getTime();
      const realTimeMs = Date.now();
      virtualTimeOffsetRef.current = virtualTimeMs - realTimeMs;
      lastVirtualTimeRef.current = virtualTimeMs;
      setNow(new Date(virtualTime));
    }
  }, [virtualTime]);
  
  // Track updates with visual feedback
  useEffect(() => {
    setLastUpdate(new Date());
    setIsUpdating(true);
    const timer = setTimeout(() => setIsUpdating(false), 500);
    return () => clearTimeout(timer);
  }, [holdings, stats, trades, portfolioData.netValue]);
  
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
  // Bubbles persist until replaced by ANY new message (cross-role)
  // When any agent sends a new message, all previous bubbles are cleared
  // Can search by agentId or agentName
  const bubbleFor = (idOrName) => {
    // First try direct lookup by id
    let b = bubbles[idOrName];
    if (b) {
      return b;
    }
    
    // If not found, search by agentName
    const agent = AGENTS.find(a => a.name === idOrName || a.id === idOrName);
    if (agent) {
      b = bubbles[agent.id];
      if (b) {
        return b;
      }
    }
    
    return null;
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
          // Don't create message for portfolio updates - they're shown in the ticker bar
          return null;
        
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
                // Use 'ret' from realtime data (relative to open price) if available
                const newChange = (realtimeData.ret !== null && realtimeData.ret !== undefined)
                  ? realtimeData.ret
                  : (ticker.change !== null && ticker.change !== undefined ? ticker.change : 0);
                
                return {
                  ...ticker,
                  price: realtimeData.price,
                  change: newChange,
                  open: realtimeData.open || ticker.open
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
        // Replay data response
        replay_data_response: (e) => {
          console.log('[Replay] Received data response');
          if (replayCallbackRef.current) {
            replayCallbackRef.current(e.data, null);
          }
        },
        
        // Error response (including replay errors and fast forward errors)
        error: (e) => {
          console.error('[Error]', e.message);
          
          // Handle replay errors
          if (replayCallbackRef.current) {
            replayCallbackRef.current(null, e.message);
          }
          
          // Handle fast forward errors
          if (e.message && e.message.includes('fast forward')) {
            console.warn(`⚠️ ${e.message}`);
            handlePushEvent({
              type: 'system',
              content: `⚠️ ${e.message}`,
              timestamp: Date.now()
            });
          }
        },
        
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
            
            // 设置服务器模式和市场状态
            if (state.server_mode) {
              setServerMode(state.server_mode);
            }
            // 检查是否是mock模式
            const isMockMode = state.is_mock_mode === true;
            if (state.market_status) {
              setMarketStatus(state.market_status);
              // 只在Mock模式下，如果市场状态包含虚拟时间，才保存它
              if (isMockMode && state.market_status.current_time) {
                try {
                  const virtualTimeDate = new Date(state.market_status.current_time);
                  setVirtualTime(virtualTimeDate);
                } catch (error) {
                  console.error('Error parsing virtual time from market_status:', error);
                }
              } else {
                // 非Mock模式下清除virtualTime
                setVirtualTime(null);
              }
            }
            
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
        
        // Market status update
        market_status_update: (e) => {
          if (e.market_status) {
            setMarketStatus(e.market_status);
          }
        },
        
        // Real-time price updates
        price_update: (e) => {
          try {
            const { symbol, price, ret, open, portfolio, realtime_prices } = e;
            
            if (!symbol || !price) {
              console.warn('[Price Update] Missing symbol or price:', e);
              return;
            }
            
            console.log(`[Price Update] ${symbol}: $${price} (ret: ${ret !== undefined ? ret.toFixed(2) : 'N/A'}%)`);
            
            // Update ticker price with animation
            setTickers(prevTickers => {
              return prevTickers.map(ticker => {
                if (ticker.symbol === symbol) {
                  const oldPrice = ticker.price;
                  
                  // Use 'ret' from server (relative to open price) if available
                  // Otherwise fallback to calculating change from previous price
                  let newChange = ticker.change;
                  if (ret !== null && ret !== undefined) {
                    // Use server-provided ret (relative to open price)
                    newChange = ret;
                  } else if (oldPrice !== null && oldPrice !== undefined && isFinite(oldPrice)) {
                    // Fallback: calculate change from previous price
                    const priceChange = ((price - oldPrice) / oldPrice) * 100;
                    newChange = (newChange !== null && newChange !== undefined) 
                      ? newChange + priceChange 
                      : priceChange;
                  } else {
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
                    change: newChange,
                    open: open || ticker.open  // Store open price
                  };
                }
                return ticker;
              });
            });
            
            // Update all tickers from realtime_prices if provided
            if (realtime_prices) {
              updateTickersFromPrices(realtime_prices);
            }
            
            // Update portfolio value if provided
            if (portfolio && portfolio.total_value) {
              setPortfolioData(prev => ({
                ...prev,
                netValue: portfolio.total_value,
                pnl: portfolio.pnl_percent || 0,
                equity: portfolio.equity || prev.equity  // Update equity curve
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
          // Clear all previous bubbles and show only the new message (cross-role behavior)
          setBubbles({
            [e.agentId]: {
              text: e.content,
              ts: Date.now(),
              agentName: agent?.name || e.agentName || e.agentId
            }
          });
          
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
          // Update portfolio data silently without creating feed messages
          setPortfolioData(prev => ({
            ...prev,
            netValue: e.balance || prev.netValue,
            pnl: e.pnlPct || 0,
            equity: e.equity || prev.equity,
            baseline: e.baseline || prev.baseline,
            baseline_vw: e.baseline_vw || prev.baseline_vw,
            momentum: e.momentum || prev.momentum
          }));
          
          // Portfolio updates are shown in the ticker bar, no need for feed messages
        },
        
        team_portfolio: (e) => {
          if (e.holdings) setHoldings(e.holdings);
        },
        
        // ✅ 监听 holdings 更新（服务器广播的事件名）
        team_holdings: (e) => {
          if (e.data && Array.isArray(e.data)) {
            setHoldings(e.data);
            console.log(`✅ Holdings updated: ${e.data.length} positions`);
          }
        },
        
        team_trades: (e) => {
          // 支持两种格式：完整列表或单笔交易
          if (e.mode === 'full' && e.data && Array.isArray(e.data)) {
            setTrades(e.data);
            console.log(`✅ Trades updated (full): ${e.data.length} trades`);
          } else if (Array.isArray(e.trades)) {
            setTrades(e.trades);
          } else if (e.trade) {
            setTrades(prev => [e.trade, ...prev].slice(0, 100));
          }
        },
        
        team_stats: (e) => {
          if (e.data) {
            setStats(e.data);
            console.log('✅ Stats updated');
          } else if (e.stats) {
            setStats(e.stats);
          }
        },
        
        team_leaderboard: (e) => {
          // 服务器发送的格式: { type: 'team_leaderboard', data: [...], timestamp: ... }
          if (Array.isArray(e.data)) {
            setLeaderboard(e.data);
            console.log('✅ Leaderboard updated:', e.data.length, 'agents');
          } else if (Array.isArray(e.rows)) {
            setLeaderboard(e.rows);
          } else if (Array.isArray(e.leaderboard)) {
            setLeaderboard(e.leaderboard);
          }
        },
        
        // 虚拟时间更新（Mock模式下的时间广播）
        time_update: (e) => {
          if (e.beijing_time_str) {
            const statusEmoji = {
              'market_open': '📊',
              'off_market': '⏸️',
              'non_trading_day': '📅',
              'trade_execution': '💼'
            };
            
            const emoji = statusEmoji[e.status] || '⏰';
            const isMockMode = e.is_mock_mode === true;
            let logMessage = `${emoji} ${isMockMode ? '虚拟时间' : '时间'}: ${e.beijing_time_str} | 状态: ${e.status}`;
            
            if (e.hours_to_open !== undefined) {
              logMessage += ` | 距离开盘: ${e.hours_to_open}小时`;
            }
            if (e.hours_to_trade !== undefined) {
              logMessage += ` | 距离交易: ${e.hours_to_trade}小时`;
            }
            if (e.trading_date) {
              logMessage += ` | 交易日: ${e.trading_date}`;
            }
            
            console.log(logMessage);
            
            // 只在Mock模式下保存虚拟时间（用于图表过滤和UI显示）
            if (isMockMode && e.beijing_time) {
              try {
                const virtualTimeDate = new Date(e.beijing_time);
                setVirtualTime(virtualTimeDate);
              } catch (error) {
                console.error('Error parsing virtual time:', error);
              }
            } else {
              // 非Mock模式下清除virtualTime
              setVirtualTime(null);
            }
          }
          
          // 更新市场状态（如果包含在time_update中）
          if (e.market_status) {
            setMarketStatus(e.market_status);
          }
        },
        
        // 时间快进事件（Mock模式）
        time_fast_forwarded: (e) => {
          console.log(`⏩ 时间已快进 ${e.minutes} 分钟: ${e.old_time_str} → ${e.new_time_str}`);
          
          // 更新虚拟时间
          if (e.new_time) {
            try {
              const virtualTimeDate = new Date(e.new_time);
              setVirtualTime(virtualTimeDate);
              
              // 添加到feed显示
              handlePushEvent({
                type: 'system',
                content: `⏩ 时间快进 ${e.minutes} 分钟: ${e.old_time_str} → ${e.new_time_str}`,
                timestamp: Date.now()
              });
            } catch (error) {
              console.error('Error parsing fast forwarded time:', error);
            }
          }
        },
        
        // 快进成功响应
        fast_forward_success: (e) => {
          console.log(`✅ ${e.message}`);
        },
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
        <Header
          onEvoTradersClick={() => setShowAboutModal(true)}
          evoTradersLinkStyle="default"
        />
        
        <div className="header-right" style={{ display: 'flex', alignItems: 'center', gap: 24, marginLeft: 'auto', flexWrap: 'wrap', minWidth: 0 }}>
          {/* Mock Mode Indicator */}
          {virtualTime && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '4px 10px',
              borderRadius: 4,
              background: '#FF9800',
              border: '1px solid #FFB74D'
            }}>
              <span style={{ fontSize: '14px' }}></span>
              <span style={{
                fontSize: '11px',
                fontWeight: 600,
                color: '#FFFFFF',
                fontFamily: '"Courier New", monospace',
                letterSpacing: '0.5px'
              }}>
                LIVE MOCK MODE
              </span>
            </div>
          )}
          
          {/* Market Status Indicator */}
          {serverMode && marketStatus && (
            <div className="market-status-indicator" style={{
              background: serverMode === 'backtest' 
                ? '#f5f5f5' 
                : (marketStatus.status === 'open' ? 'rgba(0, 200, 83, 0.1)' : 'rgba(255, 23, 68, 0.1)'),
              borderColor: serverMode === 'backtest' 
                ? '#666666' 
                : (marketStatus.status === 'open' ? '#00C853' : '#FF1744')
            }}>
              <span className="market-status-dot" style={{
                background: serverMode === 'backtest' 
                  ? '#666666' 
                  : (marketStatus.status === 'open' ? '#00C853' : '#FF1744')
              }} />
              <span className="market-status-text" style={{
                color: serverMode === 'backtest' 
                  ? '#666666' 
                  : (marketStatus.status === 'open' ? '#00C853' : '#FF1744')
              }}>
                {marketStatus.status_text || 'Status'}
              </span>
            </div>
          )}
          
          {/* Clock Display (only in Mock mode) */}
          {virtualTime && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8
            }}>
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-end',
                gap: 2,
                padding: '4px 12px',
                borderRadius: 4,
                background: '#1A237E',
                border: '1px solid #3F51B5'
              }}>
                <span style={{
                  fontSize: '11px',
                  color: '#999',
                  fontFamily: '"Courier New", monospace',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px'
                }}>
                  VIRTUAL TIME
                </span>
                <span style={{
                  fontSize: '14px',
                  fontWeight: 700,
                  color: '#FFFFFF',
                  fontFamily: '"Courier New", monospace',
                  letterSpacing: '1px'
                }}>
                  {now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}
                </span>
                <span style={{
                  fontSize: '10px',
                  color: '#999',
                  fontFamily: '"Courier New", monospace'
                }}>
                  {now.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                </span>
              </div>
              
              {/* Fast Forward Button (only in Mock mode) */}
              <button
                onClick={() => {
                  if (clientRef.current) {
                    const success = clientRef.current.send({
                      type: 'fast_forward_time',
                      minutes: 30
                    });
                    if (!success) {
                      console.error('Failed to send fast forward request');
                    }
                  }
                }}
                style={{
                  padding: '6px 12px',
                  borderRadius: 4,
                  background: '#3F51B5',
                  border: '1px solid #5C6BC0',
                  color: '#FFFFFF',
                  fontSize: '12px',
                  fontFamily: '"Courier New", monospace',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px'
                }}
                onMouseEnter={(e) => {
                  e.target.style.background = '#5C6BC0';
                  e.target.style.borderColor = '#7986CB';
                }}
                onMouseLeave={(e) => {
                  e.target.style.background = '#3F51B5';
                  e.target.style.borderColor = '#5C6BC0';
                }}
                title="快进30分钟 (Mock模式)"
              >
                ⏩ +30min
              </button>
            </div>
          )}
          
          {/* Real-time Update Indicator */}
          <div className="header-status">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: isUpdating ? '#4CAF50' : (isConnected ? '#9E9E9E' : '#FF1744'),
                animation: isUpdating ? 'pulse 1s infinite' : 'none'
              }} />
              <span className={`status-indicator ${isConnected ? 'live' : 'disconnected'}`}>
                {isConnected ? (isUpdating ? '⟳ Updating...' : '✓ Live Data') : '○ OFFLINE'}
              </span>
            </div>
            <span className="last-update-text">
              LAST UPDATE: {lastUpdate.toLocaleTimeString()}
            </span>
          </div>
        </div>
      </div>
      
      {/* Main Content */}
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
          {/* Left Panel: Three-View Toggle (Room/Chart/Statistics) */}
          <div className="left-panel" style={{ width: `${leftWidth}%` }}>
            <div className="chart-section">
              <div className="view-container">
                <div className="view-nav-bar">
                  <button
                    className={`view-nav-btn ${currentView === 'rules' ? 'active' : ''}`}
                    onClick={() => setCurrentView('rules')}
                  >
                    Rules
                  </button>
                  
                  <button
                    className={`view-nav-btn ${currentView === 'room' ? 'active' : ''}`}
                    onClick={() => setCurrentView('room')}
                  >
                    Trading Room
                  </button>
                  
                  <button
                    className={`view-nav-btn ${currentView === 'chart' ? 'active' : ''}`}
                    onClick={() => setCurrentView('chart')}
                  >
                    Performance Chart
                  </button>
                  
                  <button
                    className={`view-nav-btn ${currentView === 'statistics' ? 'active' : ''}`}
                    onClick={() => setCurrentView('statistics')}
                  >
                    Statistics
                  </button>
                </div>
                
                {/* Slider container with four views */}
                <div className={`view-slider-four ${currentView === 'rules' ? 'show-rules' : currentView === 'room' ? 'show-room' : currentView === 'statistics' ? 'show-statistics' : 'show-chart'} ${!isInitialAnimating ? 'normal-speed' : ''}`}>
                  {/* Rules View Panel */}
                  <div className="view-panel">
                    <RulesView />
                  </div>
                  
                  {/* Room View Panel */}
                  <div className="view-panel">
                    <RoomView 
                      bubbles={bubbles} 
                      bubbleFor={bubbleFor} 
                      leaderboard={leaderboard}
                      marketStatus={marketStatus}
                      wsClient={clientRef.current}
                      onReplayRequest={(callback) => {
                        replayCallbackRef.current = callback;
                      }}
                    />
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
                          className={`chart-tab ${chartTab === 'live' ? 'active' : ''}`}
                          onClick={() => setChartTab('live')}
                        >
                          LIVE
                        </button>
                      </div>

                      <NetValueChart 
                        equity={portfolioData.equity}
                        baseline={portfolioData.baseline}
                        baseline_vw={portfolioData.baseline_vw}
                        momentum={portfolioData.momentum}
                        strategies={portfolioData.strategies}
                        chartTab={chartTab}
                        virtualTime={virtualTime}
                      />
                    </div>
                  </div>
                  
                  {/* Statistics View Panel */}
                  <div className="view-panel">
                    <StatisticsView
                      trades={trades}
                      holdings={holdings}
                      stats={stats}
                      baseline_vw={portfolioData.baseline_vw}
                      equity={portfolioData.equity}
                    />
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
      
      {/* About Modal */}
      {showAboutModal && <AboutModal onClose={() => setShowAboutModal(false)} />}
    </div>
  );
}
