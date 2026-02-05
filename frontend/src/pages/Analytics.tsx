import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  BarChart3,
  TrendingUp,
  DollarSign,
  MousePointer,
  ShoppingCart,
  Calendar,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { useBigCommerceFetch, StoreInfo, AnalyticsOverview } from '../hooks/useBigCommerceFetch';

interface AnalyticsProps {
  store: StoreInfo | null;
}

export function Analytics({ store }: AnalyticsProps) {
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [period, setPeriod] = useState<'day' | 'week' | 'month'>('month');
  const [loading, setLoading] = useState(true);
  const { get } = useBigCommerceFetch();

  useEffect(() => {
    const fetchAnalytics = async () => {
      if (!store?.is_connected) {
        setLoading(false);
        return;
      }

      setLoading(true);
      try {
        const data = await get<AnalyticsOverview>(`/api/analytics?period=${period}`);
        setAnalytics(data);
      } catch (err) {
        console.error('Failed to fetch analytics:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchAnalytics();
  }, [get, period, store?.is_connected]);

  // Generate mock chart data based on analytics
  const generateChartData = () => {
    const dataPoints = period === 'day' ? 24 : period === 'week' ? 7 : 30;
    const data = [];
    const baseConversions = (analytics?.conversions ?? 0) / dataPoints;
    const baseRevenue = (analytics?.revenue ?? 0) / dataPoints;
    const baseClicks = (analytics?.clicks ?? 0) / dataPoints;

    for (let i = 0; i < dataPoints; i++) {
      const variance = 0.5 + Math.random();
      data.push({
        name: period === 'day' ? `${i}:00` : period === 'week' ? ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][i] : `Day ${i + 1}`,
        conversions: Math.round(baseConversions * variance),
        revenue: Math.round(baseRevenue * variance),
        clicks: Math.round(baseClicks * variance),
      });
    }

    return data;
  };

  const chartData = generateChartData();

  if (!store?.is_connected) {
    return (
      <div className="p-8">
        <div className="text-center py-12">
          <BarChart3 className="w-12 h-12 text-slate-600 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-white mb-2">
            Connect to View Analytics
          </h2>
          <p className="text-slate-400">
            Connect your store to Affilync to view analytics
          </p>
        </div>
      </div>
    );
  }

  const stats = [
    {
      label: 'Total Conversions',
      value: analytics?.conversions ?? 0,
      icon: ShoppingCart,
      color: 'text-green-400',
    },
    {
      label: 'Total Revenue',
      value: `$${(analytics?.revenue ?? 0).toLocaleString()}`,
      icon: DollarSign,
      color: 'text-blue-400',
    },
    {
      label: 'Total Clicks',
      value: analytics?.clicks ?? 0,
      icon: MousePointer,
      color: 'text-purple-400',
    },
    {
      label: 'Conversion Rate',
      value: analytics?.clicks
        ? `${(((analytics?.conversions ?? 0) / analytics.clicks) * 100).toFixed(2)}%`
        : '0%',
      icon: TrendingUp,
      color: 'text-amber-400',
    },
  ];

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white mb-2">Analytics</h1>
          <p className="text-slate-400">Track your affiliate performance</p>
        </div>

        {/* Period Selector */}
        <div className="flex items-center gap-2 bg-slate-900/50 border border-slate-800 rounded-lg p-1">
          {(['day', 'week', 'month'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                period === p
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, index) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            className="bg-slate-900/50 border border-slate-800 rounded-xl p-6"
          >
            <div className="flex items-center gap-3 mb-3">
              <stat.icon className={`w-5 h-5 ${stat.color}`} />
              <span className="text-slate-400 text-sm">{stat.label}</span>
            </div>
            <p className="text-2xl font-bold text-white">
              {loading ? (
                <span className="inline-block w-20 h-8 bg-slate-800 animate-pulse rounded" />
              ) : (
                stat.value
              )}
            </p>
          </motion.div>
        ))}
      </div>

      {/* Revenue Chart */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="bg-slate-900/50 border border-slate-800 rounded-xl p-6"
      >
        <h2 className="text-lg font-semibold text-white mb-6">Revenue Over Time</h2>
        {loading ? (
          <div className="h-[300px] bg-slate-800 animate-pulse rounded" />
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="revenueGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="name" stroke="#64748b" fontSize={12} />
              <YAxis stroke="#64748b" fontSize={12} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: '#f8fafc' }}
              />
              <Area
                type="monotone"
                dataKey="revenue"
                stroke="#3b82f6"
                fill="url(#revenueGradient)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </motion.div>

      {/* Conversions Chart */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="bg-slate-900/50 border border-slate-800 rounded-xl p-6"
      >
        <h2 className="text-lg font-semibold text-white mb-6">Conversions Over Time</h2>
        {loading ? (
          <div className="h-[300px] bg-slate-800 animate-pulse rounded" />
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="conversionsGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="name" stroke="#64748b" fontSize={12} />
              <YAxis stroke="#64748b" fontSize={12} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: '#f8fafc' }}
              />
              <Area
                type="monotone"
                dataKey="conversions"
                stroke="#22c55e"
                fill="url(#conversionsGradient)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </motion.div>
    </div>
  );
}
