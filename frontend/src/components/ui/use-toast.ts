import { useState, useCallback, useEffect } from 'react';

interface Toast {
  id: string;
  title?: string;
  description?: string;
  variant?: 'default' | 'destructive';
}

let toastCount = 0;
const toastsStore: Toast[] = [];
const listeners: Set<() => void> = new Set();

function notify() {
  listeners.forEach((listener) => listener());
}

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>(toastsStore);

  useEffect(() => {
    const listener = () => setToasts([...toastsStore]);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);

  const toast = useCallback(
    ({ title, description, variant = 'default' }: Omit<Toast, 'id'>) => {
      const id = String(toastCount++);
      const newToast: Toast = { id, title, description, variant };
      toastsStore.push(newToast);
      notify();

      // Auto dismiss after 5 seconds
      setTimeout(() => {
        const index = toastsStore.findIndex((t) => t.id === id);
        if (index > -1) {
          toastsStore.splice(index, 1);
          notify();
        }
      }, 5000);

      return id;
    },
    []
  );

  const dismiss = useCallback((id: string) => {
    const index = toastsStore.findIndex((t) => t.id === id);
    if (index > -1) {
      toastsStore.splice(index, 1);
      notify();
    }
  }, []);

  return { toast, toasts, dismiss };
}
