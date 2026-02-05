import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Dashboard } from './pages/Dashboard';
import { Products } from './pages/Products';
import { Analytics } from './pages/Analytics';
import { Settings } from './pages/Settings';
import { Layout } from './components/Layout';
import { useBigCommerceFetch, StoreInfo } from './hooks/useBigCommerceFetch';
import { Toaster } from './components/ui/toaster';

function App() {
  const [store, setStore] = useState<StoreInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { get, getStoreHash } = useBigCommerceFetch();

  useEffect(() => {
    const fetchStore = async () => {
      const storeHash = getStoreHash();

      if (!storeHash) {
        setError('Store hash not found. Please reinstall the app.');
        setLoading(false);
        return;
      }

      try {
        const storeInfo = await get<StoreInfo>('/api/store');
        setStore(storeInfo);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load store');
      } finally {
        setLoading(false);
      }
    };

    fetchStore();
  }, [get, getStoreHash]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-slate-400">Loading...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-6 max-w-md">
          <h2 className="text-red-400 font-semibold mb-2">Error</h2>
          <p className="text-slate-300">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <Layout store={store}>
        <Routes>
          <Route path="/" element={<Dashboard store={store} />} />
          <Route path="/products" element={<Products store={store} />} />
          <Route path="/analytics" element={<Analytics store={store} />} />
          <Route path="/settings" element={<Settings store={store} setStore={setStore} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
      <Toaster />
    </BrowserRouter>
  );
}

export default App;
