import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  TrendingUp,
  DollarSign,
  MousePointer,
  ShoppingCart,
  AlertCircle,
  ArrowUpRight,
  Users,
} from 'lucide-react';
import { useBigCommerceFetch, StoreInfo, AnalyticsOverview } from '../hooks/useBigCommerceFetch';

interface DashboardProps {
  store: StoreInfo | null;
}

export function Dashboard({ store }: DashboardProps) {
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const { get } = useBigCommerceFetch();

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        const data = await get<AnalyticsOverview>('/api/analytics?period=month');
        setAnalytics(data);
      } catch (err) {
        console.error('Failed to fetch analytics:', err);
      } finally {
        setLoading(false);
      }
    };

    if (store?.is_connected) {
      fetchAnalytics();
    } else {
      setLoading(false);
    }
  }, [get, store?.is_connected]);

  if (!store?.is_connected) {
    return (
      <div className="p-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-2xl mx-auto text-center"
        >
          <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-8">
            <AlertCircle className="w-12 h-12 text-amber-400 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-white mb-2">
              Connect to Affilync
            </h2>
            <p className="text-slate-400 mb-6">
              Connect your BigCommerce store to Affilync to start tracking affiliate conversions.
              Go to Settings to connect your brand account.
            </p>
            <a
              href="/settings"
              className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
            >
              Go to Settings
              <ArrowUpRight className="w-4 h-4" />
            </a>
          </div>
        </motion.div>
      </div>
    );
  }

  const stats = [
    {
      label: 'Conversions',
      value: analytics?.conversions ?? 0,
      icon: ShoppingCart,
      color: 'from-green-500 to-emerald-600',
      bgColor: 'bg-green-500/10',
    },
    {
      label: 'Revenue',
      value: `$${(analytics?.revenue ?? 0).toLocaleString()}`,
      icon: DollarSign,
      color: 'from-blue-500 to-indigo-600',
      bgColor: 'bg-blue-500/10',
    },
    {
      label: 'Clicks',
      value: analytics?.clicks ?? 0,
      icon: MousePointer,
      color: 'from-purple-500 to-violet-600',
      bgColor: 'bg-purple-500/10',
    },
    {
      label: 'Conversion Rate',
      value: analytics?.clicks
        ? `${(((analytics?.conversions ?? 0) / analytics.clicks) * 100).toFixed(1)}%`
        : '0%',
      icon: TrendingUp,
      color: 'from-amber-500 to-orange-600',
      bgColor: 'bg-amber-500/10',
    },
  ];

  return (
    <div className="p-8 space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white mb-2">Dashboard</h1>
        <p className="text-slate-400">
          Welcome back, {store?.store_name || 'Store Owner'}
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, index) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            className="bg-slate-900/50 border border-slate-800 rounded-xl p-6"
          >
            <div className="flex items-center justify-between mb-4">
              <div className={`p-3 rounded-lg ${stat.bgColor}`}>
                <stat.icon className={`w-5 h-5 bg-gradient-to-r ${stat.color} bg-clip-text text-transparent`} />
              </div>
            </div>
            <p className="text-slate-400 text-sm mb-1">{stat.label}</p>
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

      {/* Top Performers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Affiliates */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="bg-slate-900/50 border border-slate-800 rounded-xl p-6"
        >
          <div className="flex items-center gap-3 mb-6">
            <Users className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-semibold text-white">Top Affiliates</h2>
          </div>
          {loading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-12 bg-slate-800 animate-pulse rounded" />
              ))}
            </div>
          ) : analytics?.top_affiliates?.length ? (
            <div className="space-y-4">
              {analytics.top_affiliates.slice(0, 5).map((affiliate, i) => (
                <div
                  key={affiliate.id}
                  className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-slate-500 text-sm w-6">{i + 1}</span>
                    <span className="text-white">{affiliate.name}</span>
                  </div>
                  <div className="text-right">
                    <p className="text-green-400 font-medium">
                      ${affiliate.revenue.toLocaleString()}
                    </p>
                    <p className="text-slate-500 text-sm">
                      {affiliate.conversions} conversions
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-center py-8">No affiliate data yet</p>
          )}
        </motion.div>

        {/* Top Products */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="bg-slate-900/50 border border-slate-800 rounded-xl p-6"
        >
          <div className="flex items-center gap-3 mb-6">
            <ShoppingCart className="w-5 h-5 text-purple-400" />
            <h2 className="text-lg font-semibold text-white">Top Products</h2>
          </div>
          {loading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-12 bg-slate-800 animate-pulse rounded" />
              ))}
            </div>
          ) : analytics?.top_products?.length ? (
            <div className="space-y-4">
              {analytics.top_products.slice(0, 5).map((product, i) => (
                <div
                  key={product.id}
                  className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-slate-500 text-sm w-6">{i + 1}</span>
                    <span className="text-white truncate max-w-[200px]">
                      {product.title}
                    </span>
                  </div>
                  <div className="text-right">
                    <p className="text-purple-400 font-medium">
                      ${product.revenue.toLocaleString()}
                    </p>
                    <p className="text-slate-500 text-sm">
                      {product.conversions} sales
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-center py-8">No product data yet</p>
          )}
        </motion.div>
      </div>
    </div>
  );
}
