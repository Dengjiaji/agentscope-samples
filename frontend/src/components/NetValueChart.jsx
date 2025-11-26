import React, { useMemo, useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { formatNumber, formatFullNumber } from '../utils/formatters';

/**
 * Helper function to get the start time of the most recent trading session
 * Trading session: 22:30 - next day 05:00
 * @param {Date|null} virtualTime - Virtual time from server (for mock mode), or null to use real time
 */
function getRecentTradingSessionStart(virtualTime = null) {
  // Use virtual time if provided (for mock mode), otherwise use real time
  let now;
  if (virtualTime) {
    // Ensure virtualTime is a valid Date object
    if (virtualTime instanceof Date && !isNaN(virtualTime.getTime())) {
      now = virtualTime;
    } else if (typeof virtualTime === 'string') {
      now = new Date(virtualTime);
      if (isNaN(now.getTime())) {
        console.warn('Invalid virtualTime string, using current time:', virtualTime);
        now = new Date();
      }
    } else {
      console.warn('Invalid virtualTime type, using current time:', typeof virtualTime);
      now = new Date();
    }
  } else {
    now = new Date();
  }

  const currentHour = now.getHours();
  const currentMinute = now.getMinutes();

  // Check if currently in trading session
  const isInTradingSession = (currentHour === 22 && currentMinute >= 30) ||
                              currentHour >= 23 ||
                              (currentHour >= 0 && currentHour < 5) ||
                              (currentHour === 5 && currentMinute === 0);

  let sessionStartTime;
  if (isInTradingSession) {
    // Currently in trading session, find today's 22:30
    sessionStartTime = new Date(now);
    sessionStartTime.setHours(22, 30, 0, 0);
    // If current time is before 22:30, it means yesterday's 22:30
    if (now < sessionStartTime) {
      sessionStartTime.setDate(sessionStartTime.getDate() - 1);
    }
  } else {
    // Not in trading session, find previous session start (yesterday 22:30)
    sessionStartTime = new Date(now);
    sessionStartTime.setDate(sessionStartTime.getDate() - 1);
    sessionStartTime.setHours(22, 30, 0, 0);
  }

  return sessionStartTime;
}

/**
 * Helper function to filter strategy data for live view
 * Returns data matching the structure of filteredEquity (with start point if applicable)
 * strategyData should be an array of { t: timestamp, v: value } objects
 * @param {Date|null} virtualTime - Virtual time from server (for mock mode), or null to use real time
 */
function filterStrategyDataForLive(strategyData, equity, sessionStartTime) {
  if (!strategyData || strategyData.length === 0 || !equity || equity.length === 0) return [];

  try {
    if (!sessionStartTime || isNaN(sessionStartTime.getTime())) {
      console.warn('Invalid sessionStartTime in filterStrategyDataForLive');
      return [];
    }

    const sessionStartTimestamp = sessionStartTime.getTime();

    // Find the last index before session
    let lastDataBeforeSession = null;
    for (let i = equity.length - 1; i >= 0; i--) {
      if (equity[i] && typeof equity[i].t === 'number' && equity[i].t < sessionStartTimestamp) {
        if (strategyData[i] && strategyData[i].v !== undefined && strategyData[i].v !== null) {
          lastDataBeforeSession = strategyData[i];
        }
        break;
      }
    }

    // Find data points in the session
    const sessionData = [];
    for (let i = 0; i < equity.length; i++) {
      if (equity[i] && typeof equity[i].t === 'number' &&
          equity[i].t >= sessionStartTimestamp &&
          strategyData[i] &&
          strategyData[i].v !== undefined && strategyData[i].v !== null) {
        sessionData.push(strategyData[i]);
      }
    }

    // If we have a value before session and session data, add the start point
    // Create a start point with timestamp just before session start
    if (lastDataBeforeSession && sessionData.length > 0) {
      const startPoint = {
        t: sessionStartTimestamp - 1,
        v: lastDataBeforeSession.v
      };
      return [startPoint, ...sessionData];
    }

    return sessionData;
  } catch (error) {
    console.error('Error in filterStrategyDataForLive:', error);
    return [];
  }
}

/**
 * Net Value Chart Component
 * Displays portfolio value over time with multiple strategy comparisons
 */
export default function NetValueChart({ equity, baseline, baseline_vw, momentum, strategies, chartTab = 'all', virtualTime = null }) {
  const [activePoint, setActivePoint] = useState(null);
  const [stableYRange, setStableYRange] = useState(null);
  const [legendTooltip, setLegendTooltip] = useState(null);

  // Legend descriptions
  const legendDescriptions = {
    'EvoTraders': 'EvoTraders is our agents investment strategy',
    'Buy & Hold (EW)': 'Equal Weight: Can be viewed as an equal-weighted index of all invested stocks',
    'Buy & Hold (VW)': 'Value Weighted: Can be viewed as a market-cap weighted index of all invested stocks',
    'Momentum': 'Momentum Strategy: Buy stocks that have performed well in the past',
  };

  // Filter equity data based on chartTab
  const filteredEquity = useMemo(() => {
    if (!equity || equity.length === 0) return [];

    if (chartTab === 'all') {
      // All图：每天只显示最后一个点
      // 逻辑：保留每日22:30以前的最后一个equity值（美国下一个交易日开盘前的最后一个equity value）
      // 22:30之后的数据属于下一个交易日的交易时段，不在此图中显示
      // 时间处理：时间戳(ms) -> UTC -> Asia/Shanghai时区，然后以Asia/Shanghai时间为基准进行分组和判断
      const dailyData = {};

      equity.forEach((d) => {
        // 时间戳是毫秒数，先创建UTC时间，然后转换为Asia/Shanghai时区
        // 等价于: pd.to_datetime(timestamp, unit='ms', utc=True).dt.tz_convert('Asia/Shanghai')
        const utcDate = new Date(d.t); // 时间戳(ms) -> UTC时间

        // 使用Intl API获取Asia/Shanghai时区的日期时间组件
        const formatter = new Intl.DateTimeFormat('en-US', {
          timeZone: 'Asia/Shanghai',
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          hour12: false
        });

        const parts = formatter.formatToParts(utcDate);
        const year = parts.find(p => p.type === 'year').value;
        const month = parts.find(p => p.type === 'month').value;
        const day = parts.find(p => p.type === 'day').value;
        const hour = parseInt(parts.find(p => p.type === 'hour').value);
        const minute = parseInt(parts.find(p => p.type === 'minute').value);

        // 判断是否在22:30之前（Asia/Shanghai时区）
        const isBefore2230 = hour < 22 || (hour === 22 && minute < 30);

        // 只处理22:30之前的数据
        if (isBefore2230) {
          // 使用Asia/Shanghai时区的日期作为key
          const dateKey = `${year}-${month}-${day}`;

          // 如果这一天还没有数据，或者当前数据的时间更晚，则更新
          if (!dailyData[dateKey] || new Date(d.t) > new Date(dailyData[dateKey].t)) {
            dailyData[dateKey] = d;
          }
        }
      });

      // 转换为数组并按时间排序
      return Object.values(dailyData).sort((a, b) => a.t - b.t);
    } else if (chartTab === 'live') {
      // Live图：显示最近一次交易时段（22:30-05:00）的所有更新
      if (equity.length === 0) return [];

      try {
        const sessionStartTime = getRecentTradingSessionStart(virtualTime);

        if (!sessionStartTime || isNaN(sessionStartTime.getTime())) {
          console.warn('Invalid sessionStartTime, returning all equity data');
          return equity;
        }

        const sessionStartTimestamp = sessionStartTime.getTime();

        // 找到上一个交易日最后的net_value（sessionStartTime之前最后一个点）
        let lastValueBeforeSession = null;
        for (let i = equity.length - 1; i >= 0; i--) {
          if (equity[i] && typeof equity[i].t === 'number' && equity[i].t < sessionStartTimestamp) {
            lastValueBeforeSession = equity[i].v;
            break;
          }
        }

        // 如果找不到上一个交易日的值，使用equity的第一个值
        if (lastValueBeforeSession === null && equity.length > 0 && equity[0]) {
          lastValueBeforeSession = equity[0].v;
        }

        // 找到sessionStartTime之后的所有点
        const sessionData = equity.filter(d => d && typeof d.t === 'number' && d.t >= sessionStartTimestamp);

        // 如果有上一个交易日的最后值，在session数据前添加一个起点
        if (lastValueBeforeSession !== null && sessionData.length > 0) {
          // 确保起点的时间在session开始之前
          const startPoint = {
            t: sessionStartTimestamp - 1,
            v: lastValueBeforeSession
          };
          return [startPoint, ...sessionData];
        }

        return sessionData;
      } catch (error) {
        console.error('Error filtering equity for live view:', error);
        // Fallback: return all equity data
        return equity;
      }
    }

    return equity;
  }, [equity, chartTab, virtualTime]);

  // Helper function to get daily indices for 'all' view
  const getDailyIndices = useMemo(() => {
    if (!equity || equity.length === 0) return new Set();
    const dailyIndices = new Set();
    const dailyData = {};

    const formatter = new Intl.DateTimeFormat('en-US', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    });

    equity.forEach((d, idx) => {
      const utcDate = new Date(d.t);
      const parts = formatter.formatToParts(utcDate);
      const hour = parseInt(parts.find(p => p.type === 'hour').value);
      const minute = parseInt(parts.find(p => p.type === 'minute').value);

      // 判断是否在22:30之前（Asia/Shanghai时区）
      const isBefore2230 = hour < 22 || (hour === 22 && minute < 30);

      // 只处理22:30之前的数据
      if (isBefore2230) {
        const year = parts.find(p => p.type === 'year').value;
        const month = parts.find(p => p.type === 'month').value;
        const day = parts.find(p => p.type === 'day').value;
        const dateKey = `${year}-${month}-${day}`;

        if (!dailyData[dateKey] || new Date(d.t) > new Date(dailyData[dateKey].t)) {
          dailyData[dateKey] = { data: d, index: idx };
        }
      }
    });

    Object.values(dailyData).forEach(({ index }) => dailyIndices.add(index));
    return dailyIndices;
  }, [equity]);

  // Filter baseline, baseline_vw, momentum, strategies to match filteredEquity indices
  const filteredBaseline = useMemo(() => {
    if (!baseline || baseline.length === 0 || !equity || equity.length === 0) return [];
    if (chartTab === 'all') {
      return baseline.filter((_, idx) => getDailyIndices.has(idx));
    } else if (chartTab === 'live') {
      const sessionStartTime = getRecentTradingSessionStart(virtualTime);
      return filterStrategyDataForLive(baseline, equity, sessionStartTime);
    }
    return baseline;
  }, [baseline, equity, chartTab, getDailyIndices, virtualTime]);

  const filteredBaselineVw = useMemo(() => {
    if (!baseline_vw || baseline_vw.length === 0 || !equity || equity.length === 0) return [];
    if (chartTab === 'all') {
      return baseline_vw.filter((_, idx) => getDailyIndices.has(idx));
    } else if (chartTab === 'live') {
      const sessionStartTime = getRecentTradingSessionStart(virtualTime);
      return filterStrategyDataForLive(baseline_vw, equity, sessionStartTime);
    }
    return baseline_vw;
  }, [baseline_vw, equity, chartTab, getDailyIndices, virtualTime]);

  const filteredMomentum = useMemo(() => {
    if (!momentum || momentum.length === 0 || !equity || equity.length === 0) return [];
    if (chartTab === 'all') {
      return momentum.filter((_, idx) => getDailyIndices.has(idx));
    } else if (chartTab === 'live') {
      const sessionStartTime = getRecentTradingSessionStart(virtualTime);
      return filterStrategyDataForLive(momentum, equity, sessionStartTime);
    }
    return momentum;
  }, [momentum, equity, chartTab, getDailyIndices, virtualTime]);

  const filteredStrategies = useMemo(() => {
    if (!strategies || strategies.length === 0 || !equity || equity.length === 0) return [];
    if (chartTab === 'all') {
      return strategies.filter((_, idx) => getDailyIndices.has(idx));
    } else if (chartTab === 'live') {
      const sessionStartTime = getRecentTradingSessionStart(virtualTime);
      return filterStrategyDataForLive(strategies, equity, sessionStartTime);
    }
    return strategies;
  }, [strategies, equity, chartTab, getDailyIndices, virtualTime]);

  const chartData = useMemo(() => {
    if (!filteredEquity || filteredEquity.length === 0) return [];

    try {
      return filteredEquity.map((d, idx) => {
        if (!d || typeof d.t !== 'number' || typeof d.v !== 'number') {
          console.warn('Invalid equity data point:', d);
          return null;
        }

        const date = new Date(d.t);
        if (isNaN(date.getTime())) {
          console.warn('Invalid timestamp:', d.t);
          return null;
        }

        // For live view, strategy data might have different timestamps, so we need to match by index
        // For all view, indices should align
        const baselineVal = filteredBaseline?.[idx] ?
          (typeof filteredBaseline[idx] === 'object' ? filteredBaseline[idx].v : filteredBaseline[idx]) : null;
        const baselineVwVal = filteredBaselineVw?.[idx] ?
          (typeof filteredBaselineVw[idx] === 'object' ? filteredBaselineVw[idx].v : filteredBaselineVw[idx]) : null;
        const momentumVal = filteredMomentum?.[idx] ?
          (typeof filteredMomentum[idx] === 'object' ? filteredMomentum[idx].v : filteredMomentum[idx]) : null;
        const strategyVal = filteredStrategies?.[idx] ?
          (typeof filteredStrategies[idx] === 'object' ? filteredStrategies[idx].v : filteredStrategies[idx]) : null;

        return {
          index: idx,
          time: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) +
                ' ' + date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
          timestamp: d.t,
          portfolio: d.v,
          baseline: baselineVal || null,
          baseline_vw: baselineVwVal || null,
          momentum: momentumVal || null,
          strategy: strategyVal || null
        };
      }).filter(item => item !== null); // Remove null entries
    } catch (error) {
      console.error('Error processing chart data:', error);
      return [];
    }
  }, [filteredEquity, filteredBaseline, filteredBaselineVw, filteredMomentum, filteredStrategies]);

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

    // Use a smaller fixed percentage for equity charts to better show changes
    // For equity data, smaller padding allows better visualization of price movements
    const paddingFactor = range * 0.03; // Reduced from 0.1 to 0.03 (3% instead of 10%)

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
      }
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

  // Update stableYRange in useEffect to avoid infinite re-renders
  // Use functional update to avoid dependency on stableYRange
  useEffect(() => {
    if (yMin !== undefined && yMax !== undefined && yMin !== null && yMax !== null && isFinite(yMin) && isFinite(yMax)) {
      setStableYRange(prevRange => {
        if (!prevRange) {
          // Initialize stable range
          return { min: yMin, max: yMax };
        } else {
          // Check if update is needed (5% threshold)
          const stableRange = prevRange.max - prevRange.min;
          const threshold = stableRange * 0.05;
          const needsUpdate =
            yMin < (prevRange.min + threshold) ||
            yMax > (prevRange.max - threshold);

          if (needsUpdate) {
            return { min: yMin, max: yMax };
          }
          // No update needed, return previous range
          return prevRange;
        }
      });
    }
  }, [yMin, yMax]);

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

  const CustomLegend = ({ payload }) => {
    if (!payload || payload.length === 0) return null;

    return (
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '16px',
        padding: '10px 0',
        position: 'relative',
        fontFamily: '"Courier New", monospace',
        fontSize: '11px',
        fontWeight: 700,
        justifyContent: 'center'
      }}>
        {payload.map((entry, index) => {
          const description = legendDescriptions[entry.value] || '';
          const isActive = legendTooltip === entry.value;

          return (
            <div
              key={index}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                cursor: 'pointer',
                position: 'relative',
                padding: '4px 8px',
                borderRadius: '4px',
                backgroundColor: isActive ? '#f0f0f0' : 'transparent',
                transition: 'background-color 0.2s',
                userSelect: 'none'
              }}
              onMouseEnter={() => setLegendTooltip(entry.value)}
              onMouseLeave={() => setLegendTooltip(null)}
              onClick={(e) => {
                e.stopPropagation();
                setLegendTooltip(isActive ? null : entry.value);
              }}
            >
              <div
                style={{
                  width: '14px',
                  height: '3px',
                  backgroundColor: entry.color,
                  border: 'none'
                }}
              />
              <span
                style={{
                  fontFamily: '"Courier New", monospace',
                  fontSize: '11px',
                  fontWeight: 700,
                  color: '#000000'
                }}
              >
                {entry.value}
              </span>
              {isActive && description && (
                <div
                  style={{
                    position: 'absolute',
                    bottom: '100%',
                    left: 0,
                    marginBottom: '8px',
                    padding: '8px 12px',
                    background: '#000000',
                    color: '#ffffff',
                    fontSize: '10px',
                    fontFamily: '"Courier New", monospace',
                    whiteSpace: 'normal',
                    maxWidth: '300px',
                    zIndex: 1000,
                    borderRadius: '4px',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
                    pointerEvents: 'none',
                    lineHeight: 1.4
                  }}
                >
                  {description}
                </div>
              )}
            </div>
          );
        })}
      </div>
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
          content={<CustomLegend />}
        />

        {/* Portfolio line */}
        <Line
          type="linear"
          dataKey="portfolio"
          name="EvoTraders"
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

