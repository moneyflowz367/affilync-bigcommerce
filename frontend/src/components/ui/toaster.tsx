import { useToast } from './use-toast';
import { X } from 'lucide-react';

export function Toaster() {
  const { toasts, dismiss } = useToast();

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`flex items-start gap-3 p-4 rounded-lg shadow-lg min-w-[300px] max-w-md animate-in slide-in-from-right ${
            toast.variant === 'destructive'
              ? 'bg-red-500/10 border border-red-500/20 text-red-400'
              : 'bg-slate-900 border border-slate-800 text-white'
          }`}
        >
          <div className="flex-1">
            {toast.title && (
              <p className="font-medium mb-1">{toast.title}</p>
            )}
            {toast.description && (
              <p className="text-sm text-slate-400">{toast.description}</p>
            )}
          </div>
          <button
            onClick={() => dismiss(toast.id)}
            className="text-slate-500 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
