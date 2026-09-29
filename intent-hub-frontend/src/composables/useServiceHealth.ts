import { onBeforeUnmount, onMounted, ref } from 'vue';
import { getServiceHealth, type ServiceHealthResponse } from '../api';

// Keep the last result across page changes; share any request already in flight.
const health = ref<ServiceHealthResponse | null>(null);
const unavailable = ref(false);
const intervalMs = 30_000;
let checkedAt = 0;
let pending: Promise<void> | undefined;

function refresh() {
  if (pending) return pending;
  if (Date.now() - checkedAt < intervalMs) return Promise.resolve();
  pending = (async () => {
    try {
      health.value = (await getServiceHealth()).data;
      unavailable.value = false;
    } catch {
      unavailable.value = true;
    } finally {
      checkedAt = Date.now();
      pending = undefined;
    }
  })();
  return pending;
}

export function useServiceHealth() {
  let timer: number | undefined;
  let disposed = false;
  const poll = async () => {
    await refresh();
    if (!disposed) timer = window.setTimeout(poll, Math.max(0, intervalMs - (Date.now() - checkedAt)));
  };
  onMounted(poll);
  onBeforeUnmount(() => {
    disposed = true;
    window.clearTimeout(timer);
  });
  return { health, unavailable };
}
