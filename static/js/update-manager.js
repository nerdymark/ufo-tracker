/**
 * Consolidated Update Manager
 * Manages all periodic updates in a single timer to reduce overhead
 * and prevent multiple concurrent timers from overloading the system
 */

class UpdateManager {
    constructor() {
        this.updateFunctions = new Map();
        this.interval = 1000; // Base interval: 1 second
        this.ticker = 0;
        this.running = false;
        this.intervalId = null;

        // Performance monitoring
        this.stats = {
            totalUpdates: 0,
            failedUpdates: 0,
            averageUpdateTime: 0
        };
    }

    /**
     * Register an update function to be called at specified intervals
     * @param {string} name - Unique identifier for the update function
     * @param {function} updateFn - Function to call
     * @param {number} intervalSeconds - How often to call (in seconds)
     * @param {boolean} runImmediately - Run on registration
     */
    register(name, updateFn, intervalSeconds = 5, runImmediately = false) {
        const intervalTicks = Math.max(1, Math.round(intervalSeconds * 1000 / this.interval));

        this.updateFunctions.set(name, {
            fn: updateFn,
            interval: intervalTicks,
            lastRun: runImmediately ? -intervalTicks : 0,
            enabled: true,
            errors: 0
        });

        if (runImmediately) {
            this._runUpdate(name);
        }

        console.log(`UpdateManager: Registered '${name}' (interval: ${intervalSeconds}s)`);
    }

    /**
     * Unregister an update function
     * @param {string} name - Name of the function to unregister
     */
    unregister(name) {
        if (this.updateFunctions.delete(name)) {
            console.log(`UpdateManager: Unregistered '${name}'`);
        }
    }

    /**
     * Enable or disable a specific update function
     * @param {string} name - Name of the function
     * @param {boolean} enabled - Enable/disable
     */
    setEnabled(name, enabled) {
        const update = this.updateFunctions.get(name);
        if (update) {
            update.enabled = enabled;
            console.log(`UpdateManager: ${name} ${enabled ? 'enabled' : 'disabled'}`);
        }
    }

    /**
     * Run a specific update immediately (out of schedule)
     * @param {string} name - Name of the function to run
     */
    async runNow(name) {
        await this._runUpdate(name);
    }

    /**
     * Internal function to execute an update
     * @private
     */
    async _runUpdate(name) {
        const update = this.updateFunctions.get(name);
        if (!update || !update.enabled) return;

        const startTime = performance.now();

        try {
            await update.fn();
            this.stats.totalUpdates++;

            const duration = performance.now() - startTime;
            this.stats.averageUpdateTime =
                (this.stats.averageUpdateTime * 0.9) + (duration * 0.1);

        } catch (error) {
            console.error(`UpdateManager: Error in '${name}':`, error);
            update.errors++;
            this.stats.failedUpdates++;

            // Auto-disable if too many errors
            if (update.errors > 10) {
                console.warn(`UpdateManager: Disabling '${name}' due to repeated errors`);
                update.enabled = false;
            }
        }
    }

    /**
     * Main update loop
     * @private
     */
    _tick() {
        this.ticker++;

        for (const [name, update] of this.updateFunctions.entries()) {
            if (!update.enabled) continue;

            // Check if it's time to run this update
            const ticksSinceLastRun = this.ticker - update.lastRun;
            if (ticksSinceLastRun >= update.interval) {
                update.lastRun = this.ticker;
                this._runUpdate(name);
            }
        }
    }

    /**
     * Start the update manager
     */
    start() {
        if (this.running) {
            console.warn('UpdateManager: Already running');
            return;
        }

        this.running = true;
        this.ticker = 0;
        this.intervalId = setInterval(() => this._tick(), this.interval);
        console.log('UpdateManager: Started');
    }

    /**
     * Stop the update manager
     */
    stop() {
        if (!this.running) return;

        clearInterval(this.intervalId);
        this.intervalId = null;
        this.running = false;
        console.log('UpdateManager: Stopped');
    }

    /**
     * Get statistics about update performance
     */
    getStats() {
        return {
            ...this.stats,
            registeredUpdates: this.updateFunctions.size,
            enabledUpdates: Array.from(this.updateFunctions.values())
                .filter(u => u.enabled).length,
            running: this.running
        };
    }

    /**
     * Clear all registered update functions
     */
    clear() {
        this.updateFunctions.clear();
        console.log('UpdateManager: Cleared all update functions');
    }
}

// Global instance
const updateManager = new UpdateManager();

// Auto-start when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log('UpdateManager: DOM ready, starting...');
        updateManager.start();
    });
} else {
    // DOM already loaded
    updateManager.start();
}

// Stop on page unload
window.addEventListener('beforeunload', () => {
    updateManager.stop();
});
