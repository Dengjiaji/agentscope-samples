import React, { useState, useEffect } from 'react';
import StockLogo from './StockLogo';
import { formatNumber, formatDateTime } from '../utils/formatters';

/**
 * Statistics View Component
 * Displays portfolio overview, holdings, and trade history
 */
export default function StatisticsView({ trades, holdings, stats }) {
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;
  
  // Calculate pagination
  const totalPages = Math.ceil(trades.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentTrades = trades.slice(startIndex, endIndex);
  
  // Reset to page 1 when trades change
  useEffect(() => {
    setCurrentPage(1);
  }, [trades.length]);
  
  return (
    <div>
      {/* Overview Section */}
      {stats && (
        <div className="section">
          <div className="section-header">
            <h2 className="section-title">Performance Overview</h2>
          </div>
          
          {/* Stats Cards */}
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-card-label">Total Asset Value</div>
              <div className="stat-card-value">
                ${formatNumber(stats.totalAssetValue || 0)}
              </div>
            </div>
            
            <div className="stat-card">
              <div className="stat-card-label">Total Return</div>
              <div className={`stat-card-value ${(stats.totalReturn || 0) >= 0 ? 'positive' : 'negative'}`}>
                {(stats.totalReturn || 0) >= 0 ? '+' : ''}{(stats.totalReturn || 0).toFixed(2)}%
              </div>
            </div>
            
            <div className="stat-card">
              <div className="stat-card-label">Cash Position</div>
              <div className="stat-card-value">
                ${formatNumber(stats.cashPosition || 0)}
              </div>
            </div>
            
            <div className="stat-card">
              <div className="stat-card-label">Total Trades</div>
              <div className="stat-card-value">{stats.totalTrades || 0}</div>
            </div>
            
            <div className="stat-card">
              <div className="stat-card-label">Win Rate</div>
              <div className={`stat-card-value ${stats.winRate >= 0.5 ? 'positive' : 'negative'}`}>
                {Math.round(stats.winRate * 100)}%
              </div>
            </div>
          </div>
          
          {/* Ticker Weights */}
          {stats.tickerWeights && Object.keys(stats.tickerWeights).length > 0 && (
            <div style={{ marginTop: 24 }}>
              <h3 style={{ 
                fontSize: 14, 
                fontWeight: 700, 
                marginBottom: 12,
                letterSpacing: 1,
                textTransform: 'uppercase'
              }}>
                Ticker Weights
              </h3>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
                {Object.entries(stats.tickerWeights).map(([ticker, weight]) => (
                  <div key={ticker} style={{
                    padding: '8px 12px',
                    border: '1px solid #e0e0e0',
                    background: '#fafafa',
                    fontSize: 11,
                    fontWeight: 700
                  }}>
                    {ticker}: {(weight * 100).toFixed(2)}%
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Portfolio Holdings Section */}
      <div className="section">
        <div className="section-header">
          <h2 className="section-title">Portfolio Holdings</h2>
        </div>
        
        {holdings.length === 0 ? (
          <div className="empty-state">No positions currently held</div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Quantity</th>
                  <th>Current Price</th>
                  <th>Market Value</th>
                  <th>Weight</th>
                </tr>
              </thead>
              <tbody>
                {holdings.map(h => (
                  <tr key={h.ticker}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center' }}>
                        {h.ticker !== 'CASH' && <StockLogo ticker={h.ticker} size={20} />}
                        <span style={{ fontWeight: 700, color: '#000000' }}>{h.ticker}</span>
                      </div>
                    </td>
                    <td>{h.ticker === 'CASH' ? '-' : h.quantity}</td>
                    <td>{h.ticker === 'CASH' ? '-' : `$${Number(h.currentPrice).toFixed(2)}`}</td>
                    <td style={{ fontWeight: 700 }}>${formatNumber(h.marketValue)}</td>
                    <td>{(Number(h.weight) * 100).toFixed(2)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      
      {/* Trade History Section */}
      <div className="section">
        <div className="section-header">
          <h2 className="section-title">Transaction History</h2>
          {trades.length > 0 && (
            <div style={{ 
              fontSize: '11px', 
              color: '#666666',
              fontFamily: '"Courier New", monospace'
            }}>
              Total: {trades.length} trades
            </div>
          )}
        </div>
        
        {trades.length === 0 ? (
          <div className="empty-state">No trades recorded</div>
        ) : (
          <>
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Stock</th>
                    <th>Side</th>
                    <th>Quantity</th>
                    <th>Price</th>
                  </tr>
                </thead>
                <tbody>
                  {currentTrades.map(t => (
                    <tr key={t.id}>
                      <td style={{ fontSize: 11, color: '#666666', fontFamily: '"Courier New", monospace' }}>
                        {formatDateTime(t.timestamp)}
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center' }}>
                          <StockLogo ticker={t.ticker} size={18} />
                          <span style={{ fontWeight: 700, color: '#000000' }}>{t.ticker}</span>
                        </div>
                      </td>
                      <td>
                        <span style={{
                          display: 'inline-block',
                          padding: '2px 8px',
                          fontSize: 10,
                          fontWeight: 700,
                          border: `1px solid ${t.side === 'LONG' ? '#00C853' : t.side === 'SHORT' ? '#FF1744' : '#666666'}`,
                          color: t.side === 'LONG' ? '#00C853' : t.side === 'SHORT' ? '#FF1744' : '#666666'
                        }}>
                          {t.side}
                        </span>
                      </td>
                      <td>{t.qty}</td>
                      <td>${Number(t.price).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            
            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="pagination-controls">
                <button 
                  className="pagination-btn"
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                >
                  ◀ Prev
                </button>
                
                <div className="pagination-info">
                  Page {currentPage} of {totalPages}
                  <span style={{ margin: '0 8px', color: '#e0e0e0' }}>|</span>
                  Showing {startIndex + 1}-{Math.min(endIndex, trades.length)} of {trades.length}
                </div>
                
                <button 
                  className="pagination-btn"
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                >
                  Next ▶
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

