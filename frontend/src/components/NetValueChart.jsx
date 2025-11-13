import React, { useMemo, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { formatNumber, formatFullNumber } from '../utils/formatters';

/**
 * Net Value Chart Component
 * Displays portfolio value over time with multiple strategy comparisons
 */
export default function NetValueChart({ equity, baseline, baseline_vw, momentum, strategies }) {
  const [activePoint, setActivePoint] = useState(null);
  const [stableYRange, setStableYRange] = useState(null);
  
  const chartData = useMemo(() => {
    if (!equity || equity.length === 0) return [];
    
    return equity.map((d, idx) => {
      const date = new Date(d.t);
      return {
        index: idx,
        time: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + 
              ' ' + date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
        timestamp: d.t,
        portfolio: d.v,
        baseline: baseline?.[idx]?.v || null,
        baseline_vw: baseline_vw?.[idx]?.v || null,
        momentum: momentum?.[idx]?.v || null,
        strategy: strategies?.[idx]?.v || null
      };
    });
  }, [equity, baseline, baseline_vw, momentum, strategies]);
  
  const { yMin, yMax, xTickIndices } = useMemo(() => {
    if (chartData.length === 0) return { yMin: 0, yMax: 1, xTickIndices: [] };
    
    // Calculate min and max from all series
    const allValues = chartData.flatMap(d => 
      [d.portfolio, d.baseline, d.baseline_vw, d.momentum, d.strategy].filter(v => v !== null && isFinite(v))
    );
    
    if (allValues.length === 0) {
      return { yMin: 0, yMax: 1000000, xTickIndices: [] };
    }
    
    const dataMin = Math.min(...allValues);
    const dataMax = Math.max(...allValues);
    const range = dataMax - dataMin || 1;
    
    // Calculate standard deviation for variance-based padding
    const mean = allValues.reduce((sum, v) => sum + v, 0) / allValues.length;
    const variance = allValues.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / allValues.length;
    const stdDev = Math.sqrt(variance);
    
    const relativeStdDev = stdDev / mean;
    let paddingFactor;
    if (relativeStdDev < 0.01) {
      paddingFactor = stdDev * 0.5;
    } else if (relativeStdDev < 0.05) {
      paddingFactor = stdDev * 0.2;
    } else {
      paddingFactor = range * 0.1;
    }
    
    let yMinCalc = dataMin - paddingFactor;
    let yMaxCalc = dataMax + paddingFactor;
    
    // Smart rounding based on magnitude
    const magnitude = Math.max(Math.abs(yMinCalc), Math.abs(yMaxCalc));
    let roundTo;
    if (magnitude >= 1e6) {
      roundTo = 10000;
    } else if (magnitude >= 1e5) {
      roundTo = 5000;
    } else if (magnitude >= 1e4) {
      roundTo = 1000;
    } else {
      roundTo = 100;
    }
    
    yMinCalc = Math.floor(yMinCalc / roundTo) * roundTo;
    yMaxCalc = Math.ceil(yMaxCalc / roundTo) * roundTo;
    
    // Stable range to prevent frequent updates
    if (stableYRange) {
      const { min: stableMin, max: stableMax } = stableYRange;
      const stableRange = stableMax - stableMin;
      const threshold = stableRange * 0.05;
      
      const needsUpdate = 
        dataMin < (stableMin + threshold) || 
        dataMax > (stableMax - threshold);
      
      if (!needsUpdate) {
        yMinCalc = stableMin;
        yMaxCalc = stableMax;
      } else {
        setStableYRange({ min: yMinCalc, max: yMaxCalc });
      }
    } else {
      setStableYRange({ min: yMinCalc, max: yMaxCalc });
    }
    
    // Calculate x-axis tick indices
    const safeLength = Math.min(chartData.length, 10000);
    const targetTicks = Math.min(8, Math.max(5, Math.floor(safeLength / 10)));
    const step = Math.max(1, Math.floor(safeLength / (targetTicks - 1)));
    
    const indices = [];
    for (let i = 0; i < safeLength && indices.length < 100; i += step) {
      indices.push(i);
    }
    
    if (safeLength > 0 && indices[indices.length - 1] !== safeLength - 1) {
      indices.push(safeLength - 1);
    }
    
    return { yMin: yMinCalc, yMax: yMaxCalc, xTickIndices: indices };
  }, [chartData, stableYRange]);

  if (!equity || equity.length === 0) {
    return (
      <div style={{ 
        width: '100%', 
        height: '100%', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        color: '#cccccc',
        fontFamily: '"Courier New", monospace',
        fontSize: '12px'
      }}>
        NO DATA AVAILABLE
      </div>
    );
  }

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      return (
        <div style={{
          background: '#000000',
          border: '1px solid #333333',
          padding: '10px 14px',
          fontFamily: '"Courier New", monospace',
          fontSize: '10px',
          color: '#ffffff'
        }}>
          <div style={{ fontWeight: 700, marginBottom: '6px', fontSize: '11px' }}>
            {payload[0].payload.time}
          </div>
          {payload.map((entry, index) => (
            <div key={index} style={{ color: entry.color, marginTop: '2px' }}>
              <span style={{ fontWeight: 700 }}>{entry.name}:</span> ${formatNumber(entry.value)}
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  const CustomDot = ({ dataKey, ...props }) => {
    const { cx, cy, payload, index } = props;
    const isActive = activePoint === index;
    const isLastPoint = index === chartData.length - 1;
    
    // Only show dot for the last point
    if (!isLastPoint) {
      return null;
    }
    const colors = {
      portfolio: '#00C853',
      baseline: '#FF6B00',
      baseline_vw: '#9C27B0',
      momentum: '#2196F3',
      strategy: '#795548'
    };
    
    return (
      <circle
        cx={cx}
        cy={cy}
        r={isActive ? 6 : 8}
        fill={colors[dataKey]}
        stroke="#ffffff"
        strokeWidth={2}
        style={{ cursor: 'pointer' }}
        onMouseEnter={() => setActivePoint(index)}
        onMouseLeave={() => setActivePoint(null)}
        onClick={() => console.log('Clicked point:', { dataKey, ...payload })}
      />
    );
  };
  
  const CustomXAxisTick = ({ x, y, payload }) => {
    const shouldShow = xTickIndices.includes(payload.index);
    if (!shouldShow) return null;
    
    return (
      <g transform={`translate(${x},${y})`}>
        <text
          x={0}
          y={0}
          dy={16}
          textAnchor="middle"
          fill="#666666"
          fontSize="10px"
          fontFamily='"Courier New", monospace'
          fontWeight="700"
        >
          {payload.value}
        </text>
      </g>
    );
  };

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart 
        data={chartData} 
        margin={{ top: 20, right: 30, bottom: 50, left: 60 }}
      >
        <XAxis 
          dataKey="time" 
          stroke="#666666"
          tick={<CustomXAxisTick />}
          interval={0}
        />
        <YAxis 
          domain={[yMin, yMax]}
          stroke="#000000"
          style={{ fontFamily: '"Courier New", monospace', fontSize: '11px', fontWeight: 700 }}
          tick={{ fill: '#000000' }}
          tickFormatter={(value) => formatFullNumber(value)}
          width={75}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend 
          wrapperStyle={{
            fontFamily: '"Courier New", monospace',
            fontSize: '11px',
            fontWeight: 700
          }}
        />
        
        {/* Portfolio line */}
        <Line 
          type="linear" 
          dataKey="portfolio" 
          name="Portfolio"
          stroke="#00C853" 
          strokeWidth={2.5}
          dot={(props) => <CustomDot {...props} dataKey="portfolio" />}
          activeDot={{ r: 6, stroke: '#ffffff', strokeWidth: 2 }}
          isAnimationActive={false}
        />
        
        {/* Baseline Equal Weight */}
        {baseline && baseline.length > 0 && (
          <Line 
            type="linear" 
            dataKey="baseline" 
            name="Buy & Hold (EW)"
            stroke="#FF6B00" 
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={(props) => <CustomDot {...props} dataKey="baseline" />}
            activeDot={{ r: 6, stroke: '#ffffff', strokeWidth: 2 }}
            isAnimationActive={false}
          />
        )}
        
        {/* Baseline Value Weighted */}
        {baseline_vw && baseline_vw.length > 0 && (
          <Line 
            type="linear" 
            dataKey="baseline_vw" 
            name="Buy & Hold (VW)"
            stroke="#9C27B0" 
            strokeWidth={2}
            strokeDasharray="8 4"
            dot={(props) => <CustomDot {...props} dataKey="baseline_vw" />}
            activeDot={{ r: 6, stroke: '#ffffff', strokeWidth: 2 }}
            isAnimationActive={false}
          />
        )}
        
        {/* Momentum Strategy */}
        {momentum && momentum.length > 0 && (
          <Line 
            type="linear" 
            dataKey="momentum" 
            name="Momentum"
            stroke="#2196F3" 
            strokeWidth={2}
            strokeDasharray="3 3"
            dot={(props) => <CustomDot {...props} dataKey="momentum" />}
            activeDot={{ r: 6, stroke: '#ffffff', strokeWidth: 2 }}
            isAnimationActive={false}
          />
        )}
        
        {/* Other Strategies */}
        {strategies && strategies.length > 0 && (
          <Line 
            type="linear" 
            dataKey="strategy" 
            name="Strategy"
            stroke="#795548" 
            strokeWidth={2}
            dot={(props) => <CustomDot {...props} dataKey="strategy" />}
            activeDot={{ r: 6, stroke: '#ffffff', strokeWidth: 2 }}
            isAnimationActive={false}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}

