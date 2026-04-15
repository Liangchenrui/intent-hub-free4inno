const CACHE_KEY = 'admin_latest_access_codes';

export interface AdminAccessCodeCache {
  byTenant: Record<string, string>;
  byCodeId: Record<string, string>;
}

const emptyCache = (): AdminAccessCodeCache => ({
  byTenant: {},
  byCodeId: {},
});

export const loadAdminAccessCodeCache = (): AdminAccessCodeCache => {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) {
      return emptyCache();
    }
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object' && ('byTenant' in parsed || 'byCodeId' in parsed)) {
      return {
        byTenant: parsed.byTenant && typeof parsed.byTenant === 'object' ? parsed.byTenant : {},
        byCodeId: parsed.byCodeId && typeof parsed.byCodeId === 'object' ? parsed.byCodeId : {},
      };
    }
    // Backward compatibility: old format was { [tenantId]: accessCode }.
    return {
      byTenant: parsed && typeof parsed === 'object' ? parsed : {},
      byCodeId: {},
    };
  } catch {
    return emptyCache();
  }
};

export const saveAdminAccessCodeCache = (cache: AdminAccessCodeCache) => {
  localStorage.setItem(CACHE_KEY, JSON.stringify(cache));
};

export const rememberLatestAccessCode = (params: {
  tenantId?: string;
  codeId?: string;
  accessCode?: string | null;
}): AdminAccessCodeCache => {
  const cache = loadAdminAccessCodeCache();
  const normalizedCode = params.accessCode?.trim();
  if (!normalizedCode) {
    return cache;
  }
  if (params.tenantId) {
    cache.byTenant[params.tenantId] = normalizedCode;
  }
  if (params.codeId) {
    cache.byCodeId[params.codeId] = normalizedCode;
  }
  saveAdminAccessCodeCache(cache);
  return cache;
};

