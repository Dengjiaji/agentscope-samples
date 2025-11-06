import React from 'react';

/**
 * Performance View Component
 * Displays agent performance leaderboard and signal history
 */
export default function PerformanceView({ leaderboard }) {
  return (
    <div>
      {/* Agent Performance Section */}
      <div className="section">
        <div className="section-header">
          <h2 className="section-title">Agent Performance - Signal Accuracy</h2>
        </div>
        
        {leaderboard.length === 0 ? (
          <div className="empty-state">No leaderboard data available</div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Agent</th>
                  <th>Win Rate</th>
                  <th>Bull Signals</th>
                  <th>Bull Win Rate</th>
                  <th>Bear Signals</th>
                  <th>Bear Win Rate</th>
                  <th>Total Signals</th>
                </tr>
              </thead>
              <tbody>
                {leaderboard.map(agent => {
                  const bullTotal = agent.bull?.n || 0;
                  const bullWins = agent.bull?.win || 0;
                  const bearTotal = agent.bear?.n || 0;
                  const bearWins = agent.bear?.win || 0;
                  const totalSignals = bullTotal + bearTotal;
                  const bullWinRate = bullTotal > 0 ? (bullWins / bullTotal) : 0;
                  const bearWinRate = bearTotal > 0 ? (bearWins / bearTotal) : 0;
                  
                  return (
                    <tr key={agent.agentId}>
                      <td>
                        <span className={`rank-badge ${agent.rank === 1 ? 'first' : agent.rank === 2 ? 'second' : agent.rank === 3 ? 'third' : ''}`}>
                          {agent.rank === 1 ? '★ 1' : agent.rank}
                        </span>
                      </td>
                      <td>
                        <div style={{ fontWeight: 700, color: '#000000' }}>{agent.name}</div>
                        <div style={{ fontSize: 10, color: '#666666' }}>{agent.role}</div>
                      </td>
                      <td style={{ fontWeight: 700, color: agent.winRate >= 0.5 ? '#00C853' : '#FF1744' }}>
                        {(agent.winRate * 100).toFixed(1)}%
                      </td>
                      <td>
                        <div style={{ fontSize: 12 }}>{bullTotal} signals</div>
                        <div style={{ fontSize: 10, color: '#666666' }}>{bullWins} wins</div>
                      </td>
                      <td style={{ color: bullWinRate >= 0.5 ? '#00C853' : '#999999' }}>
                        {bullTotal > 0 ? `${(bullWinRate * 100).toFixed(1)}%` : 'N/A'}
                      </td>
                      <td>
                        <div style={{ fontSize: 12 }}>{bearTotal} signals</div>
                        <div style={{ fontSize: 10, color: '#666666' }}>{bearWins} wins</div>
                      </td>
                      <td style={{ color: bearWinRate >= 0.5 ? '#00C853' : '#999999' }}>
                        {bearTotal > 0 ? `${(bearWinRate * 100).toFixed(1)}%` : 'N/A'}
                      </td>
                      <td style={{ fontWeight: 700 }}>{totalSignals}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
      
      {/* Signal History with Dates */}
      {leaderboard.length > 0 && leaderboard.some(agent => agent.signals && agent.signals.length > 0) && (
        <div className="section" style={{ marginTop: 32 }}>
          <div className="section-header">
            <h2 className="section-title">Signal History</h2>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: 20 }}>
            {leaderboard.map(agent => {
              if (!agent.signals || agent.signals.length === 0) return null;
              
              // Sort by date descending (newest first)
              const sortedSignals = [...agent.signals].sort((a, b) => 
                new Date(b.date).getTime() - new Date(a.date).getTime()
              );
              
              return (
                <div key={agent.agentId} style={{ 
                  border: '1px solid #e0e0e0', 
                  padding: 16,
                  background: '#fafafa'
                }}>
                  <div style={{ 
                    fontWeight: 700, 
                    fontSize: 12, 
                    marginBottom: 12,
                    paddingBottom: 8,
                    borderBottom: '2px solid #000000',
                    letterSpacing: 1,
                    textTransform: 'uppercase'
                  }}>
                    {agent.name}
                  </div>
                  <div style={{ 
                    maxHeight: 500, 
                    overflowY: 'auto',
                    display: 'flex', 
                    flexDirection: 'column', 
                    gap: 8 
                  }}>
                    {sortedSignals.map((signal, idx) => {
                      const signalType = signal.signal.toLowerCase();
                      const isBull = signalType.includes('bull') || signalType === 'long';
                      const isBear = signalType.includes('bear') || signalType === 'short';
                      const isNeutral = signalType.includes('neutral') || signalType === 'hold';
                      const isCorrect = signal.is_correct;
                      
                      return (
                        <div key={idx} style={{ 
                          fontSize: 11, 
                          fontFamily: '"Courier New", monospace',
                          lineHeight: 1.4,
                          padding: '8px 10px',
                          background: '#ffffff',
                          border: '1px solid #e0e0e0',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center'
                        }}>
                          <div style={{ flex: 1 }}>
                            <span style={{ 
                              color: '#666666',
                              fontSize: 10,
                              marginRight: 10,
                              fontWeight: 600
                            }}>
                              {signal.date}
                            </span>
                            <span style={{ 
                              fontWeight: 700,
                              color: isBull ? '#00C853' : isBear ? '#FF1744' : '#999999'
                            }}>
                              {signal.ticker}
                            </span>
                            <span style={{ 
                              marginLeft: 6, 
                              color: isBull ? '#00C853' : isBear ? '#FF1744' : '#999999',
                              fontSize: 12
                            }}>
                              {isBull ? 'Bull' : isBear ? 'Bear' : 'Neutral'}
                            </span>
                            {!isNeutral && (
                              <span style={{ 
                                marginLeft: 8,
                                fontSize: 10,
                                color: signal.real_return >= 0 ? '#00C853' : '#FF1744'
                              }}>
                                {signal.real_return >= 0 ? '+' : ''}{(signal.real_return * 100).toFixed(2)}%
                              </span>
                            )}
                          </div>
                          {!isNeutral && (
                            <span style={{ 
                              fontSize: 14,
                              marginLeft: 10,
                              color: isCorrect ? '#00C853' : '#FF1744'
                            }}>
                              {isCorrect ? '✓' : '✗'}
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  <div style={{
                    marginTop: 10,
                    paddingTop: 8,
                    borderTop: '1px solid #e0e0e0',
                    fontSize: 10,
                    color: '#666666',
                    textAlign: 'center'
                  }}>
                    Total: {sortedSignals.length} signals
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

