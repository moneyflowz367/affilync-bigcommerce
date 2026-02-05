import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Settings as SettingsIcon,
  Link2,
  Unlink,
  Save,
  RefreshCw,
  Check,
} from 'lucide-react';
import { useBigCommerceFetch, StoreInfo } from '../hooks/useBigCommerceFetch';
import { useToast } from '../components/ui/use-toast';

interface SettingsProps {
  store: StoreInfo | null;
  setStore: (store: StoreInfo) => void;
}

export function Settings({ store, setStore }: SettingsProps) {
  const [brandId, setBrandId] = useState('');
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState({
    auto_sync_products: store?.settings.auto_sync_products ?? false,
    cookie_duration_days: store?.settings.cookie_duration_days ?? 30,
    attribution_model: store?.settings.attribution_model ?? 'last_click',
  });
  const { post, put, get } = useBigCommerceFetch();
  const { toast } = useToast();

  const handleConnect = async () => {
    if (!brandId.trim()) {
      toast({
        title: 'Error',
        description: 'Please enter a Brand ID',
        variant: 'destructive',
      });
      return;
    }

    setConnecting(true);
    try {
      await post('/api/store/connect', { brand_id: brandId });
      const updatedStore = await get<StoreInfo>('/api/store');
      setStore(updatedStore);
      toast({
        title: 'Connected',
        description: 'Successfully connected to Affilync',
      });
      setBrandId('');
    } catch (err) {
      toast({
        title: 'Connection Failed',
        description: err instanceof Error ? err.message : 'Unknown error',
        variant: 'destructive',
      });
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    setDisconnecting(true);
    try {
      await post('/api/store/disconnect');
      const updatedStore = await get<StoreInfo>('/api/store');
      setStore(updatedStore);
      toast({
        title: 'Disconnected',
        description: 'Disconnected from Affilync',
      });
    } catch (err) {
      toast({
        title: 'Error',
        description: err instanceof Error ? err.message : 'Unknown error',
        variant: 'destructive',
      });
    } finally {
      setDisconnecting(false);
    }
  };

  const handleSaveSettings = async () => {
    setSaving(true);
    try {
      await put('/api/store/settings', settings);
      const updatedStore = await get<StoreInfo>('/api/store');
      setStore(updatedStore);
      toast({
        title: 'Settings Saved',
        description: 'Your settings have been updated',
      });
    } catch (err) {
      toast({
        title: 'Error',
        description: err instanceof Error ? err.message : 'Unknown error',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-8 space-y-8 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-white mb-2">Settings</h1>
        <p className="text-slate-400">Manage your app configuration</p>
      </div>

      {/* Connection Section */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-slate-900/50 border border-slate-800 rounded-xl p-6"
      >
        <div className="flex items-center gap-3 mb-6">
          <Link2 className="w-5 h-5 text-blue-400" />
          <h2 className="text-lg font-semibold text-white">Affilync Connection</h2>
        </div>

        {store?.is_connected ? (
          <div className="space-y-4">
            <div className="flex items-center gap-3 p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
              <Check className="w-5 h-5 text-green-400" />
              <div>
                <p className="text-green-400 font-medium">Connected</p>
                <p className="text-slate-400 text-sm">
                  Brand ID: {store.brand_id}
                </p>
              </div>
            </div>
            <button
              onClick={handleDisconnect}
              disabled={disconnecting}
              className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-slate-700 text-white rounded-lg transition-colors"
            >
              {disconnecting ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Unlink className="w-4 h-4" />
              )}
              {disconnecting ? 'Disconnecting...' : 'Disconnect'}
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-slate-400">
              Enter your Affilync Brand ID to connect your store and start tracking affiliate conversions.
            </p>
            <div className="flex gap-3">
              <input
                type="text"
                value={brandId}
                onChange={(e) => setBrandId(e.target.value)}
                placeholder="Enter Brand ID (UUID)"
                className="flex-1 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
              <button
                onClick={handleConnect}
                disabled={connecting}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 text-white rounded-lg transition-colors"
              >
                {connecting ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Link2 className="w-4 h-4" />
                )}
                {connecting ? 'Connecting...' : 'Connect'}
              </button>
            </div>
            <p className="text-slate-500 text-sm">
              Find your Brand ID in your Affilync dashboard under Brand Settings.
            </p>
          </div>
        )}
      </motion.div>

      {/* Sync Settings */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-slate-900/50 border border-slate-800 rounded-xl p-6"
      >
        <div className="flex items-center gap-3 mb-6">
          <SettingsIcon className="w-5 h-5 text-purple-400" />
          <h2 className="text-lg font-semibold text-white">Sync Settings</h2>
        </div>

        <div className="space-y-6">
          {/* Auto Sync Products */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-white font-medium">Auto-sync Products</p>
              <p className="text-slate-400 text-sm">
                Automatically sync new and updated products to Affilync
              </p>
            </div>
            <button
              onClick={() =>
                setSettings((s) => ({ ...s, auto_sync_products: !s.auto_sync_products }))
              }
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                settings.auto_sync_products ? 'bg-blue-600' : 'bg-slate-700'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  settings.auto_sync_products ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {/* Cookie Duration */}
          <div>
            <label className="block text-white font-medium mb-2">
              Cookie Duration (days)
            </label>
            <p className="text-slate-400 text-sm mb-3">
              How long to track affiliate attribution after a click
            </p>
            <select
              value={settings.cookie_duration_days}
              onChange={(e) =>
                setSettings((s) => ({
                  ...s,
                  cookie_duration_days: parseInt(e.target.value),
                }))
              }
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
            >
              <option value={7}>7 days</option>
              <option value={14}>14 days</option>
              <option value={30}>30 days</option>
              <option value={60}>60 days</option>
              <option value={90}>90 days</option>
            </select>
          </div>

          {/* Attribution Model */}
          <div>
            <label className="block text-white font-medium mb-2">
              Attribution Model
            </label>
            <p className="text-slate-400 text-sm mb-3">
              How to attribute conversions when multiple affiliates are involved
            </p>
            <select
              value={settings.attribution_model}
              onChange={(e) =>
                setSettings((s) => ({ ...s, attribution_model: e.target.value }))
              }
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
            >
              <option value="last_click">Last Click</option>
              <option value="first_click">First Click</option>
              <option value="linear">Linear (Split equally)</option>
            </select>
          </div>

          {/* Save Button */}
          <button
            onClick={handleSaveSettings}
            disabled={saving}
            className="flex items-center gap-2 px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 text-white rounded-lg transition-colors"
          >
            {saving ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </motion.div>

      {/* Store Info */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-slate-900/50 border border-slate-800 rounded-xl p-6"
      >
        <h2 className="text-lg font-semibold text-white mb-4">Store Information</h2>
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-400">Store Hash</span>
            <span className="text-white font-mono">{store?.store_hash}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Store Name</span>
            <span className="text-white">{store?.store_name || 'N/A'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Domain</span>
            <span className="text-white">{store?.store_domain || 'N/A'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Installed</span>
            <span className="text-white">
              {store?.installed_at
                ? new Date(store.installed_at).toLocaleDateString()
                : 'N/A'}
            </span>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
