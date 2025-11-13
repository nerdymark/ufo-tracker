/**
 * API Response Cache
 * Caches API responses to reduce redundant requests and improve performance
 */

class APICache {
    constructor(defaultTTL = 200) {
        this.cache = new Map();
        this.defaultTTL = defaultTTL; // milliseconds
        this.stats = {
            hits: 0,
            misses: 0,
            sets: 0
        };
    }

    /**
     * Generate cache key from URL and options
     * @private
     */
    _generateKey(url, options = {}) {
        const method = options.method || 'GET';
        const body = options.body || '';
        return `${method}:${url}:${body}`;
    }

    /**
     * Get cached response or fetch from API
     * @param {string} url - API endpoint URL
     * @param {object} options - Fetch options
     * @param {number} ttl - Time to live in milliseconds (override default)
     */
    async fetch(url, options = {}, ttl = null) {
        const key = this._generateKey(url, options);
        const now = Date.now();
        const cacheTTL = ttl !== null ? ttl : this.defaultTTL;

        // Check cache
        if (this.cache.has(key)) {
            const cached = this.cache.get(key);
            const entryTTL = cached.ttl || this.defaultTTL;

            // Check if still valid
            if (now - cached.timestamp < entryTTL) {
                this.stats.hits++;
                return cached.data;
            } else {
                // Expired, remove from cache
                this.cache.delete(key);
            }
        }

        // Cache miss, fetch from API
        this.stats.misses++;

        try {
            const response = await fetch(url, options);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();

            // Store in cache
            this.cache.set(key, {
                data: data,
                timestamp: now,
                ttl: cacheTTL
            });
            this.stats.sets++;

            return data;

        } catch (error) {
            console.error(`APICache: Error fetching ${url}:`, error);
            throw error;
        }
    }

    /**
     * Invalidate cache entry
     * @param {string} url - URL to invalidate
     * @param {object} options - Options used in original request
     */
    invalidate(url, options = {}) {
        const key = this._generateKey(url, options);
        if (this.cache.delete(key)) {
            console.log(`APICache: Invalidated ${key}`);
        }
    }

    /**
     * Invalidate all cache entries matching a pattern
     * @param {RegExp} pattern - Regular expression to match URLs
     */
    invalidatePattern(pattern) {
        let count = 0;
        for (const key of this.cache.keys()) {
            if (pattern.test(key)) {
                this.cache.delete(key);
                count++;
            }
        }
        if (count > 0) {
            console.log(`APICache: Invalidated ${count} entries matching pattern`);
        }
    }

    /**
     * Clear all cache entries
     */
    clear() {
        this.cache.clear();
        console.log('APICache: Cleared all cache entries');
    }

    /**
     * Get cache statistics
     */
    getStats() {
        const totalRequests = this.stats.hits + this.stats.misses;
        const hitRate = totalRequests > 0 ? (this.stats.hits / totalRequests * 100).toFixed(1) : 0;

        return {
            ...this.stats,
            size: this.cache.size,
            hitRate: `${hitRate}%`,
            totalRequests
        };
    }

    /**
     * Clean up expired entries
     */
    cleanup() {
        const now = Date.now();
        let removed = 0;

        for (const [key, value] of this.cache.entries()) {
            const entryTTL = value.ttl || this.defaultTTL;
            if (now - value.timestamp >= entryTTL) {
                this.cache.delete(key);
                removed++;
            }
        }

        if (removed > 0) {
            console.log(`APICache: Cleaned up ${removed} expired entries`);
        }

        return removed;
    }

    /**
     * Set a custom cache entry (manual caching)
     * @param {string} key - Cache key
     * @param {any} data - Data to cache
     * @param {number} ttl - Time to live (optional, uses defaultTTL if not provided)
     */
    set(key, data, ttl = null) {
        const cacheTTL = ttl !== null ? ttl : this.defaultTTL;
        this.cache.set(key, {
            data: data,
            timestamp: Date.now(),
            ttl: cacheTTL
        });
        this.stats.sets++;
    }

    /**
     * Get a cached entry directly
     * @param {string} key - Cache key
     */
    get(key) {
        if (this.cache.has(key)) {
            const cached = this.cache.get(key);
            const now = Date.now();
            const entryTTL = cached.ttl || this.defaultTTL;

            if (now - cached.timestamp < entryTTL) {
                this.stats.hits++;
                return cached.data;
            } else {
                this.cache.delete(key);
            }
        }

        this.stats.misses++;
        return null;
    }
}

// Global instance with 200ms default TTL (optimal for sensor data)
const apiCache = new APICache(200);

// Periodic cleanup every 60 seconds
setInterval(() => apiCache.cleanup(), 60000);

// Helper function for cached fetch with automatic error handling
async function cachedFetch(url, options = {}, ttl = null) {
    try {
        return await apiCache.fetch(url, options, ttl);
    } catch (error) {
        console.error(`Cached fetch failed for ${url}:`, error);
        return null;
    }
}
