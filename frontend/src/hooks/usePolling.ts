import { useEffect, useRef } from 'react';

type PollingOptions = {
  enabled: boolean;
  intervalMs: number;
};

export function usePolling(callback: () => void, options: PollingOptions) {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    if (!options.enabled) {
      return;
    }

    const timerId = window.setInterval(() => {
      callbackRef.current();
    }, options.intervalMs);

    return () => window.clearInterval(timerId);
  }, [options.enabled, options.intervalMs]);
}
