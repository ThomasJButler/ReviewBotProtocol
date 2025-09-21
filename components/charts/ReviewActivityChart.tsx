'use client'

import React from 'react'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { TrendingUp, TrendingDown, Minus, Activity } from 'lucide-react'

interface ReviewActivityChartProps {
  data?: any[]
  timeRange?: '7d' | '30d' | '90d'
  onTimeRangeChange?: (range: '7d' | '30d' | '90d') => void
  type?: 'line' | 'bar' | 'area'
  height?: number
  showTrend?: boolean
}

const CHART_COLORS = {
  primary: '#00ff00',
  secondary: '#00ffff',
  danger: '#ff4444',
  warning: '#ffaa00',
  info: '#4444ff',
  success: '#44ff44',
}

export default function ReviewActivityChart({
  data,
  timeRange = '30d',
  onTimeRangeChange,
  type = 'area',
  height = 300,
  showTrend = true,
}: ReviewActivityChartProps) {
  // Generate sample data if none provided
  const chartData = React.useMemo(() => {
    if (data && data.length > 0) return data

    // Generate sample data based on time range
    const days = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : 90
    const sampleData = []

    for (let i = days; i >= 0; i--) {
      const date = new Date()
      date.setDate(date.getDate() - i)

      sampleData.push({
        date: date.toISOString().split('T')[0],
        reviews: Math.floor(Math.random() * 10) + 1,
        score: Math.floor(Math.random() * 30) + 70,
        issues: Math.floor(Math.random() * 20),
        security: Math.floor(Math.random() * 5),
        performance: Math.floor(Math.random() * 8),
        quality: Math.floor(Math.random() * 10),
      })
    }

    return sampleData
  }, [data, timeRange])

  // Calculate trend
  const trend = React.useMemo(() => {
    if (!showTrend || chartData.length < 2) return null

    const halfPoint = Math.floor(chartData.length / 2)
    const firstHalf = chartData.slice(0, halfPoint)
    const secondHalf = chartData.slice(halfPoint)

    const firstAvg =
      firstHalf.reduce((acc, d) => acc + (d.reviews || 0), 0) / firstHalf.length
    const secondAvg =
      secondHalf.reduce((acc, d) => acc + (d.reviews || 0), 0) /
      secondHalf.length

    const percentChange = ((secondAvg - firstAvg) / firstAvg) * 100

    return {
      value: percentChange,
      direction:
        percentChange > 0 ? 'up' : percentChange < 0 ? 'down' : 'neutral',
      icon:
        percentChange > 0 ? (
          <TrendingUp className="h-4 w-4 text-green-400" />
        ) : percentChange < 0 ? (
          <TrendingDown className="h-4 w-4 text-red-400" />
        ) : (
          <Minus className="h-4 w-4 text-gray-400" />
        ),
    }
  }, [chartData, showTrend])

  // Custom tooltip
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-deep-black/90 backdrop-blur-sm border border-matrix-green/30 rounded-lg p-3 shadow-lg">
          <p className="text-white font-semibold mb-2">{label}</p>
          {payload.map((entry: any, index: number) => (
            <p key={index} className="text-sm" style={{ color: entry.color }}>
              {entry.name}: {entry.value}
            </p>
          ))}
        </div>
      )
    }
    return null
  }

  const renderChart = () => {
    switch (type) {
      case 'line':
        return (
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis
              dataKey="date"
              stroke="#666"
              tick={{ fill: '#999', fontSize: 12 }}
              tickFormatter={value => {
                const date = new Date(value)
                return `${date.getMonth() + 1}/${date.getDate()}`
              }}
            />
            <YAxis stroke="#666" tick={{ fill: '#999', fontSize: 12 }} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ color: '#999' }} />
            <Line
              type="monotone"
              dataKey="reviews"
              stroke={CHART_COLORS.primary}
              strokeWidth={2}
              dot={{ fill: CHART_COLORS.primary, r: 3 }}
              activeDot={{ r: 5 }}
              name="Reviews"
            />
            <Line
              type="monotone"
              dataKey="issues"
              stroke={CHART_COLORS.warning}
              strokeWidth={2}
              dot={{ fill: CHART_COLORS.warning, r: 3 }}
              name="Issues"
            />
          </LineChart>
        )

      case 'bar':
        return (
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis
              dataKey="date"
              stroke="#666"
              tick={{ fill: '#999', fontSize: 12 }}
              tickFormatter={value => {
                const date = new Date(value)
                return `${date.getMonth() + 1}/${date.getDate()}`
              }}
            />
            <YAxis stroke="#666" tick={{ fill: '#999', fontSize: 12 }} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ color: '#999' }} />
            <Bar dataKey="reviews" fill={CHART_COLORS.primary} name="Reviews" />
            <Bar dataKey="issues" fill={CHART_COLORS.warning} name="Issues" />
          </BarChart>
        )

      case 'area':
      default:
        return (
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="colorReviews" x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="5%"
                  stopColor={CHART_COLORS.primary}
                  stopOpacity={0.8}
                />
                <stop
                  offset="95%"
                  stopColor={CHART_COLORS.primary}
                  stopOpacity={0.1}
                />
              </linearGradient>
              <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="5%"
                  stopColor={CHART_COLORS.secondary}
                  stopOpacity={0.8}
                />
                <stop
                  offset="95%"
                  stopColor={CHART_COLORS.secondary}
                  stopOpacity={0.1}
                />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis
              dataKey="date"
              stroke="#666"
              tick={{ fill: '#999', fontSize: 12 }}
              tickFormatter={value => {
                const date = new Date(value)
                return `${date.getMonth() + 1}/${date.getDate()}`
              }}
            />
            <YAxis stroke="#666" tick={{ fill: '#999', fontSize: 12 }} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ color: '#999' }} />
            <Area
              type="monotone"
              dataKey="reviews"
              stroke={CHART_COLORS.primary}
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#colorReviews)"
              name="Reviews"
            />
            <Area
              type="monotone"
              dataKey="score"
              stroke={CHART_COLORS.secondary}
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#colorScore)"
              name="Avg Score"
              yAxisId="right"
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              stroke="#666"
              tick={{ fill: '#999', fontSize: 12 }}
              domain={[0, 100]}
            />
          </AreaChart>
        )
    }
  }

  return (
    <Card className="glass-effect">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-white">
            <Activity className="h-5 w-5 text-matrix-green" />
            Review Activity
          </CardTitle>
          <div className="flex items-center gap-4">
            {showTrend && trend && (
              <div className="flex items-center gap-2">
                {trend.icon}
                <span
                  className={`text-sm font-semibold ${
                    trend.direction === 'up'
                      ? 'text-green-400'
                      : trend.direction === 'down'
                        ? 'text-red-400'
                        : 'text-gray-400'
                  }`}
                >
                  {Math.abs(trend.value).toFixed(1)}%
                </span>
              </div>
            )}
            {onTimeRangeChange && (
              <Select
                value={timeRange}
                onValueChange={onTimeRangeChange as any}
              >
                <SelectTrigger className="w-[120px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="7d">Last 7 days</SelectItem>
                  <SelectItem value="30d">Last 30 days</SelectItem>
                  <SelectItem value="90d">Last 90 days</SelectItem>
                </SelectContent>
              </Select>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={height}>
          {renderChart()}
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

// Issue distribution pie chart component
export function IssueDistributionChart({ data }: { data?: any[] }) {
  const pieData = data || [
    { name: 'Security', value: 15, color: CHART_COLORS.danger },
    { name: 'Performance', value: 25, color: CHART_COLORS.warning },
    { name: 'Quality', value: 35, color: CHART_COLORS.info },
    { name: 'Documentation', value: 10, color: CHART_COLORS.secondary },
    { name: 'Testing', value: 15, color: CHART_COLORS.success },
  ]

  return (
    <Card className="glass-effect">
      <CardHeader>
        <CardTitle className="text-white">Issue Distribution</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={250}>
          <PieChart>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              labelLine={false}
              label={({ name, percent }) =>
                `${name} ${(percent * 100).toFixed(0)}%`
              }
              outerRadius={80}
              fill="#8884d8"
              dataKey="value"
            >
              {pieData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}

// Code quality radar chart
export function CodeQualityRadar({ data }: { data?: any }) {
  const radarData = data || [
    { metric: 'Security', value: 85 },
    { metric: 'Performance', value: 75 },
    { metric: 'Maintainability', value: 90 },
    { metric: 'Documentation', value: 60 },
    { metric: 'Testing', value: 70 },
    { metric: 'Complexity', value: 80 },
  ]

  return (
    <Card className="glass-effect">
      <CardHeader>
        <CardTitle className="text-white">Code Quality Metrics</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={250}>
          <RadarChart data={radarData}>
            <PolarGrid stroke="#333" />
            <PolarAngleAxis
              dataKey="metric"
              tick={{ fill: '#999', fontSize: 12 }}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 100]}
              tick={{ fill: '#999', fontSize: 10 }}
            />
            <Radar
              name="Score"
              dataKey="value"
              stroke={CHART_COLORS.primary}
              fill={CHART_COLORS.primary}
              fillOpacity={0.3}
            />
            <Tooltip />
          </RadarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
