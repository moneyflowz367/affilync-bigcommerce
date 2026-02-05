import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Package,
  RefreshCw,
  Check,
  X,
  Search,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useBigCommerceFetch, StoreInfo, Product, ProductsResponse } from '../hooks/useBigCommerceFetch';
import { useToast } from '../components/ui/use-toast';

interface ProductsProps {
  store: StoreInfo | null;
}

export function Products({ store }: ProductsProps) {
  const [products, setProducts] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [search, setSearch] = useState('');
  const { get, post } = useBigCommerceFetch();
  const { toast } = useToast();

  const limit = 20;

  useEffect(() => {
    fetchProducts();
  }, [page]);

  const fetchProducts = async () => {
    setLoading(true);
    try {
      const offset = (page - 1) * limit;
      const data = await get<ProductsResponse>(`/api/products?limit=${limit}&offset=${offset}`);
      setProducts(data.products);
      setTotal(data.total);
    } catch (err) {
      console.error('Failed to fetch products:', err);
      toast({
        title: 'Error',
        description: 'Failed to load products',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    if (!store?.is_connected) {
      toast({
        title: 'Not Connected',
        description: 'Connect to Affilync first in Settings',
        variant: 'destructive',
      });
      return;
    }

    setSyncing(true);
    try {
      const result = await post<{ status: string; stats: any }>('/api/products/sync');
      toast({
        title: 'Sync Complete',
        description: `Synced ${result.stats.synced_to_affilync} products`,
      });
      fetchProducts();
    } catch (err) {
      toast({
        title: 'Sync Failed',
        description: err instanceof Error ? err.message : 'Unknown error',
        variant: 'destructive',
      });
    } finally {
      setSyncing(false);
    }
  };

  const filteredProducts = products.filter((p) =>
    p.title.toLowerCase().includes(search.toLowerCase())
  );

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white mb-2">Products</h1>
          <p className="text-slate-400">
            {total} products in your store
          </p>
        </div>
        <button
          onClick={handleSync}
          disabled={syncing || !store?.is_connected}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
          {syncing ? 'Syncing...' : 'Sync All Products'}
        </button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
        <input
          type="text"
          placeholder="Search products..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-3 bg-slate-900/50 border border-slate-800 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
        />
      </div>

      {/* Products Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {[...Array(8)].map((_, i) => (
            <div
              key={i}
              className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 animate-pulse"
            >
              <div className="aspect-square bg-slate-800 rounded-lg mb-4" />
              <div className="h-4 bg-slate-800 rounded w-3/4 mb-2" />
              <div className="h-4 bg-slate-800 rounded w-1/2" />
            </div>
          ))}
        </div>
      ) : filteredProducts.length === 0 ? (
        <div className="text-center py-12">
          <Package className="w-12 h-12 text-slate-600 mx-auto mb-4" />
          <p className="text-slate-400">
            {search ? 'No products match your search' : 'No products found'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filteredProducts.map((product, index) => (
            <motion.div
              key={product.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
              className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 hover:border-slate-700 transition-colors"
            >
              {product.image_url ? (
                <img
                  src={product.image_url}
                  alt={product.title}
                  className="aspect-square object-cover rounded-lg mb-4 bg-slate-800"
                />
              ) : (
                <div className="aspect-square bg-slate-800 rounded-lg mb-4 flex items-center justify-center">
                  <Package className="w-8 h-8 text-slate-600" />
                </div>
              )}
              <h3 className="text-white font-medium truncate mb-1" title={product.title}>
                {product.title}
              </h3>
              <div className="flex items-center justify-between">
                <p className="text-slate-400">
                  {product.price ? `$${product.price.toFixed(2)}` : 'No price'}
                </p>
                <div className="flex items-center gap-1">
                  {product.is_synced ? (
                    <span className="flex items-center gap-1 text-green-400 text-sm">
                      <Check className="w-3 h-3" />
                      Synced
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-slate-500 text-sm">
                      <X className="w-3 h-3" />
                      Not synced
                    </span>
                  )}
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="p-2 bg-slate-900/50 border border-slate-800 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-800 transition-colors"
          >
            <ChevronLeft className="w-5 h-5 text-white" />
          </button>
          <span className="text-slate-400">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="p-2 bg-slate-900/50 border border-slate-800 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-800 transition-colors"
          >
            <ChevronRight className="w-5 h-5 text-white" />
          </button>
        </div>
      )}
    </div>
  );
}
