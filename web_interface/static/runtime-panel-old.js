/**
 * Runtime Server Panel — Bottom-edge resizable dashboard
 *
 * When minimised the user sees only a small tab (engine_tab.png)
 * centred at the bottom of the viewport. Clicking it opens a full-width
 * panel that can be resized to any height via a top-edge drag handle.
 *
 * The panel provides:
 *   • Continuous runtime loop — re-executes engine tabs on a configurable
 *     interval (or on code-change) and streams results via SocketIO.
 *   • Server info dashboard — uptime, connected clients, executor pool
 *     status, execution history chart.
 *   • Live output console — scrolling log fed by SocketIO events.
 *
 * Dependencies: SocketIO (loaded globally), LiveExecutionPanel (window.liveExec).
 */

(function () {
    'use strict';

    /* ══════════════════════════════════════════════════════════════
       CONSTANTS
       ══════════════════════════════════════════════════════════════ */
    const MIN_HEIGHT     = 48;   // collapsed = just the tab
    const DEFAULT_HEIGHT = 420;
    const MAX_HEIGHT_PCT = 0.85; // never cover more than 85 % of the viewport
    const PERSIST_KEY    = 'runtime-panel-height';
    const PERSIST_INT    = 'runtime-panel-interval';
    const DEFAULT_INTERVAL = 5; // seconds

    /* ══════════════════════════════════════════════════════════════
       RUNTIME PANEL CLASS
       ══════════════════════════════════════════════════════════════ */
    class RuntimePanel {
        constructor() {
            /* ── state ── */
            this.isOpen       = false;
            this.isRunning    = false;
            this.isPaused     = false;
            this.intervalSec  = this._restoreInterval();
            this.cycleCount   = 0;
            this.startedAt    = null;
            this._loopTimer   = null;
            this._socket      = null;
            this._history     = [];      // last N execution summaries
            this._maxHistory  = 200;

            /* ── DOM bootstrap ── */
            this._injectHTML();
            this._cacheDOM();
            this._bindEvents();
            this._restoreHeight();
            this._connectSocket();
            this._buildRuntimeMatrix();
            this._tick();  // start the uptime / status clock
        }

        /* ────────────────────────────────────────
           DOM INJECTION
           ──────────────────────────────────────── */
        _injectHTML() {
            const panel = document.createElement('div');
            panel.id = 'runtime-panel';
            panel.className = 'runtime-panel runtime-panel--collapsed';
            panel.innerHTML = `
                <!-- Resize handle (top edge) -->
                <div class="runtime-panel__resize" id="runtime-resize"></div>

                <!-- Tab (visible when collapsed) -->
                <div class="runtime-panel__tab" id="runtime-tab">
                    <img src="/static/images/engine_tab.png" alt="Runtime"
                         class="runtime-panel__tab-img" draggable="false">
                    <span class="runtime-panel__tab-badge" id="runtime-tab-badge"></span>
                </div>

                <!-- Full dashboard (visible when open) -->
                <div class="runtime-panel__body" id="runtime-body">

                    <!-- Top bar -->
                    <div class="runtime-panel__topbar">
                        <div class="runtime-panel__topbar-left">
                            <img src="/static/images/engine_tab.png" alt=""
                                 class="runtime-panel__topbar-icon" draggable="false">
                            <span class="runtime-panel__title">Runtime Server</span>
                            <span class="runtime-panel__status" id="runtime-status">stopped</span>
                        </div>

                        <div class="runtime-panel__topbar-center">
                            <!-- Transport controls -->
                            <button class="runtime-btn runtime-btn--play"  id="runtime-play"  title="Start continuous execution">▶</button>
                            <button class="runtime-btn runtime-btn--pause" id="runtime-pause" title="Pause" disabled>⏸</button>
                            <button class="runtime-btn runtime-btn--stop"  id="runtime-stop"  title="Stop"  disabled>⏹</button>
                            <button class="runtime-btn runtime-btn--once"  id="runtime-once"  title="Run once (single cycle)">⟳</button>

                            <div class="runtime-interval">
                                <label class="runtime-interval__label" for="runtime-interval-input">Interval</label>
                                <input  type="range" id="runtime-interval-input" class="runtime-interval__slider"
                                        min="1" max="60" step="1" value="${this.intervalSec}">
                                <span class="runtime-interval__value" id="runtime-interval-value">${this.intervalSec}s</span>
                            </div>
                        </div>

                        <div class="runtime-panel__topbar-right">
                            <button class="runtime-btn runtime-btn--docs" id="runtime-api-docs" title="API Documentation (Swagger)"><i data-lucide="book-open"></i></button>
                            <button class="runtime-btn runtime-btn--clear" id="runtime-clear-log" title="Clear log"><i data-lucide="trash-2"></i></button>
                            <button class="runtime-btn runtime-btn--min"   id="runtime-minimise" title="Minimise"><i data-lucide="chevron-down"></i></button>
                        </div>
                    </div>

                    <!-- Dashboard grid (adjusts layout on resize via CSS) -->
                    <div class="runtime-panel__dashboard" id="runtime-dashboard">

                        <!-- Stats cards -->
                        <div class="runtime-card runtime-card--stats" id="runtime-stats-card">
                            <div class="runtime-card__title">Server Info</div>
                            <div class="runtime-stats-grid">
                                <div class="runtime-stat">
                                    <div class="runtime-stat__label">Uptime</div>
                                    <div class="runtime-stat__value" id="runtime-uptime">—</div>
                                </div>
                                <div class="runtime-stat">
                                    <div class="runtime-stat__label">Cycles</div>
                                    <div class="runtime-stat__value" id="runtime-cycles">0</div>
                                </div>
                                <div class="runtime-stat">
                                    <div class="runtime-stat__label">Status</div>
                                    <div class="runtime-stat__value" id="runtime-run-state">idle</div>
                                </div>
                                <div class="runtime-stat">
                                    <div class="runtime-stat__label">Engines</div>
                                    <div class="runtime-stat__value" id="runtime-engine-count">—</div>
                                </div>
                                <div class="runtime-stat">
                                    <div class="runtime-stat__label">Last Run</div>
                                    <div class="runtime-stat__value" id="runtime-last-run">—</div>
                                </div>
                                <div class="runtime-stat">
                                    <div class="runtime-stat__label">Pass Rate</div>
                                    <div class="runtime-stat__value" id="runtime-pass-rate">—</div>
                                </div>
                            </div>
                        </div>

                        <!-- Registry Slot Matrix -->
                        <div class="runtime-card runtime-card--matrix" id="runtime-matrix-card">
                            <div class="runtime-card__title">
                                Registry Matrix
                                <span class="runtime-matrix-stats" id="runtime-matrix-stats"></span>
                            </div>
                            <div class="runtime-matrix-body" id="runtime-matrix-body"></div>
                        </div>

                        <!-- Execution timeline / mini-chart -->
                        <div class="runtime-card runtime-card--timeline" id="runtime-timeline-card">
                            <div class="runtime-card__title">Execution Timeline</div>
                            <canvas id="runtime-timeline-canvas" class="runtime-timeline-canvas"></canvas>
                        </div>

                        <!-- Live log console -->
                        <div class="runtime-card runtime-card--log" id="runtime-log-card">
                            <div class="runtime-card__title">Live Output</div>
                            <div class="runtime-log" id="runtime-log"></div>
                        </div>

                        <!-- Active engines list -->
                        <div class="runtime-card runtime-card--engines" id="runtime-engines-card">
                            <div class="runtime-card__title">Engine Pool</div>
                            <div class="runtime-engines-list" id="runtime-engines-list">
                                <div class="runtime-engines-empty">No engines configured</div>
                            </div>
                        </div>

                        <!-- API Documentation (Swagger UI in iframe) -->
                        <div class="runtime-card runtime-card--docs" id="runtime-docs-card" style="display:none;">
                            <div class="runtime-card__title">
                                API Documentation
                                <button class="runtime-docs-pop-out" id="runtime-docs-popout" title="Open in new tab"><i data-lucide="external-link"></i></button>
                                <button class="runtime-docs-close" id="runtime-docs-close" title="Close docs panel"><i data-lucide="x"></i></button>
                            </div>
                            <iframe id="runtime-docs-iframe" class="runtime-docs-iframe"
                                    sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                                    loading="lazy"></iframe>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(panel);
            if (typeof lucide !== 'undefined') lucide.createIcons({ root: panel });
        }

        _cacheDOM() {
            this.panel      = document.getElementById('runtime-panel');
            this.tab        = document.getElementById('runtime-tab');
            this.tabBadge   = document.getElementById('runtime-tab-badge');
            this.body       = document.getElementById('runtime-body');
            this.resizeBar  = document.getElementById('runtime-resize');
            this.dashboard  = document.getElementById('runtime-dashboard');

            // Controls
            this.btnPlay    = document.getElementById('runtime-play');
            this.btnPause   = document.getElementById('runtime-pause');
            this.btnStop    = document.getElementById('runtime-stop');
            this.btnOnce    = document.getElementById('runtime-once');
            this.btnClear   = document.getElementById('runtime-clear-log');
            this.btnMin     = document.getElementById('runtime-minimise');
            this.intervalSlider = document.getElementById('runtime-interval-input');
            this.intervalLabel  = document.getElementById('runtime-interval-value');

            // Stats
            this.elUptime     = document.getElementById('runtime-uptime');
            this.elCycles     = document.getElementById('runtime-cycles');
            this.elRunState   = document.getElementById('runtime-run-state');
            this.elEngineCount= document.getElementById('runtime-engine-count');
            this.elLastRun    = document.getElementById('runtime-last-run');
            this.elPassRate   = document.getElementById('runtime-pass-rate');
            this.elStatus     = document.getElementById('runtime-status');

            // Log & timeline
            this.logEl        = document.getElementById('runtime-log');
            this.timelineCanvas = document.getElementById('runtime-timeline-canvas');
            this.enginesListEl = document.getElementById('runtime-engines-list');

            // Matrix
            this.matrixBody   = document.getElementById('runtime-matrix-body');
            this.matrixStats  = document.getElementById('runtime-matrix-stats');

            // API Docs
            this.docsCard     = document.getElementById('runtime-docs-card');
            this.docsIframe   = document.getElementById('runtime-docs-iframe');
            this.btnDocs      = document.getElementById('runtime-api-docs');
            this.btnDocsPopout = document.getElementById('runtime-docs-popout');
            this.btnDocsClose = document.getElementById('runtime-docs-close');
        }

        /* ────────────────────────────────────────
           EVENTS
           ──────────────────────────────────────── */
        _bindEvents() {
            // Tab click → open
            this.tab.addEventListener('click', () => this.open());

            // Minimise button
            this.btnMin.addEventListener('click', () => this.close());

            // Transport
            this.btnPlay.addEventListener('click',  () => this.start());
            this.btnPause.addEventListener('click', () => this.pause());
            this.btnStop.addEventListener('click',  () => this.stop());
            this.btnOnce.addEventListener('click',  () => this.runOnce());
            this.btnClear.addEventListener('click', () => this._clearLog());

            // API Docs button
            this.btnDocs?.addEventListener('click', () => this._toggleDocs());
            this.btnDocsPopout?.addEventListener('click', () => {
                window.open(`${location.origin}/api/docs`, '_blank');
            });
            this.btnDocsClose?.addEventListener('click', () => this._toggleDocs(false));

            // Interval slider
            this.intervalSlider.addEventListener('input', (e) => {
                this.intervalSec = parseInt(e.target.value, 10);
                this.intervalLabel.textContent = `${this.intervalSec}s`;
                this._persistInterval();
                // If running, restart the loop with the new interval
                if (this.isRunning && !this.isPaused) {
                    this._restartLoop();
                }
            });

            // Resize handle
            this._initResize();

            // Close on Escape
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.isOpen) this.close();
            });
        }

        /* ────────────────────────────────────────
           OPEN / CLOSE
           ──────────────────────────────────────── */
        open() {
            this.isOpen = true;
            this.panel.classList.remove('runtime-panel--collapsed');
            this.panel.classList.add('runtime-panel--open');
            this._refreshEnginePool();
            this._refreshRuntimeMatrix();
            this._drawTimeline();
        }

        close() {
            this.isOpen = false;
            this.panel.classList.remove('runtime-panel--open');
            this.panel.classList.add('runtime-panel--collapsed');
        }

        /* ────────────────────────────────────────
           RESIZE (drag top edge)
           ──────────────────────────────────────── */
        _initResize() {
            let startY = 0;
            let startH = 0;
            let dragging = false;

            const onMove = (e) => {
                if (!dragging) return;
                e.preventDefault();
                const clientY = e.touches ? e.touches[0].clientY : e.clientY;
                const delta = startY - clientY;           // dragging up = positive
                const maxH = window.innerHeight * MAX_HEIGHT_PCT;
                const newH = Math.max(MIN_HEIGHT + 20, Math.min(maxH, startH + delta));
                this.panel.style.height = `${newH}px`;
                this._persistHeight(newH);
                this._onHeightChange(newH);
            };

            const onUp = () => {
                if (!dragging) return;
                dragging = false;
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                this.resizeBar.classList.remove('active');
            };

            this.resizeBar.addEventListener('mousedown', (e) => {
                e.preventDefault();
                dragging = true;
                startY = e.clientY;
                startH = this.panel.offsetHeight;
                document.body.style.cursor = 'ns-resize';
                document.body.style.userSelect = 'none';
                this.resizeBar.classList.add('active');
            });
            this.resizeBar.addEventListener('touchstart', (e) => {
                dragging = true;
                startY = e.touches[0].clientY;
                startH = this.panel.offsetHeight;
                document.body.style.userSelect = 'none';
                this.resizeBar.classList.add('active');
            }, { passive: false });

            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
            document.addEventListener('touchmove', onMove, { passive: false });
            document.addEventListener('touchend', onUp);
        }

        /** Apply responsive layout classes based on panel height */
        _onHeightChange(h) {
            const d = this.dashboard;
            if (!d) return;
            d.classList.toggle('layout-compact', h < 220);
            d.classList.toggle('layout-medium',  h >= 220 && h < 450);
            d.classList.toggle('layout-full',    h >= 450);
        }

        _persistHeight(h) {
            try { localStorage.setItem(PERSIST_KEY, String(Math.round(h))); } catch (_) {}
        }

        _restoreHeight() {
            try {
                const v = localStorage.getItem(PERSIST_KEY);
                if (v) {
                    const h = Math.max(MIN_HEIGHT + 20, Math.min(window.innerHeight * MAX_HEIGHT_PCT, Number(v)));
                    this.panel.style.height = `${h}px`;
                    this._onHeightChange(h);
                } else {
                    this.panel.style.height = `${DEFAULT_HEIGHT}px`;
                    this._onHeightChange(DEFAULT_HEIGHT);
                }
            } catch (_) {
                this.panel.style.height = `${DEFAULT_HEIGHT}px`;
            }
        }

        _persistInterval() {
            try { localStorage.setItem(PERSIST_INT, String(this.intervalSec)); } catch (_) {}
        }

        _restoreInterval() {
            try {
                const v = localStorage.getItem(PERSIST_INT);
                return v ? Math.max(1, Math.min(60, Number(v))) : DEFAULT_INTERVAL;
            } catch (_) { return DEFAULT_INTERVAL; }
        }

        /* ────────────────────────────────────────
           SOCKETIO
           ──────────────────────────────────────── */
        _connectSocket() {
            if (typeof io === 'undefined') {
                console.warn('[RuntimePanel] SocketIO not loaded');
                return;
            }
            // Reuse the global socket if it exists, otherwise create one
            if (window._spokedSocket) {
                this._socket = window._spokedSocket;
            } else {
                this._socket = io();
                window._spokedSocket = this._socket;
            }

            this._socket.on('runtime_cycle_result', (data) => this._onCycleResult(data));
            this._socket.on('runtime_status',       (data) => this._onStatusUpdate(data));
            this._socket.on('runtime_error',         (data) => this._onRuntimeError(data));

            // Snippet lifecycle events (marshal submissions, locks, evictions)
            this._bindSnippetLifecycleEvents();
        }

        /* ────────────────────────────────────────
           CONTINUOUS RUNTIME  — START / PAUSE / STOP
           ──────────────────────────────────────── */
        async start() {
            if (this.isRunning && !this.isPaused) return;

            if (this.isPaused) {
                // Resume from pause
                this.isPaused = false;
                this._updateTransport();
                this._restartLoop();
                this._log('▶ Resumed', 'info');
                this._postRuntimeCommand('resume');
                return;
            }

            this.isRunning  = true;
            this.isPaused   = false;
            this.cycleCount = 0;
            this.startedAt  = Date.now();
            this._history   = [];
            this._updateTransport();
            this._log('▶ Runtime started', 'info');
            this._postRuntimeCommand('start');

            // Run the first cycle immediately, then loop
            await this._executeCycle();
            this._restartLoop();
        }

        pause() {
            if (!this.isRunning || this.isPaused) return;
            this.isPaused = true;
            clearInterval(this._loopTimer);
            this._loopTimer = null;
            this._updateTransport();
            this._log('⏸ Paused', 'warn');
            this._postRuntimeCommand('pause');
        }

        stop() {
            this.isRunning = false;
            this.isPaused  = false;
            clearInterval(this._loopTimer);
            this._loopTimer = null;
            this.startedAt  = null;
            this._updateTransport();
            this._log('⏹ Stopped', 'warn');
            this._postRuntimeCommand('stop');
        }

        async runOnce() {
            this._log('⟳ Single cycle', 'info');
            await this._executeCycle();
        }

        _restartLoop() {
            clearInterval(this._loopTimer);
            this._loopTimer = setInterval(() => this._executeCycle(), this.intervalSec * 1000);
        }

        _updateTransport() {
            const running  = this.isRunning && !this.isPaused;
            const paused   = this.isRunning && this.isPaused;
            const stopped  = !this.isRunning;

            this.btnPlay.disabled  = running;
            this.btnPause.disabled = !running;
            this.btnStop.disabled  = stopped;

            if (running) {
                this.elStatus.textContent = 'running';
                this.elStatus.className   = 'runtime-panel__status runtime-panel__status--running';
                this.elRunState.textContent = 'running';
                this.tabBadge.textContent = '●';
                this.tabBadge.className   = 'runtime-panel__tab-badge runtime-panel__tab-badge--running';
            } else if (paused) {
                this.elStatus.textContent = 'paused';
                this.elStatus.className   = 'runtime-panel__status runtime-panel__status--paused';
                this.elRunState.textContent = 'paused';
                this.tabBadge.textContent = '❚❚';
                this.tabBadge.className   = 'runtime-panel__tab-badge runtime-panel__tab-badge--paused';
            } else {
                this.elStatus.textContent = 'stopped';
                this.elStatus.className   = 'runtime-panel__status runtime-panel__status--stopped';
                this.elRunState.textContent = 'idle';
                this.tabBadge.textContent = '';
                this.tabBadge.className   = 'runtime-panel__tab-badge';
            }
        }

        /* ────────────────────────────────────────
           EXECUTE ONE CYCLE
           ──────────────────────────────────────── */
        async _executeCycle() {
            // Gather tabs from the LiveExecutionPanel
            const liveExec = window.liveExec;
            if (!liveExec) {
                this._log('[!] LiveExecutionPanel not initialized.', 'warn');
                return;
            }

            // ── Auto-hydrate from canvas if no tabs have code ──
            if (!liveExec.engineTabs || liveExec.engineTabs.size === 0 ||
                Array.from(liveExec.engineTabs.values()).every(t => !t.code?.trim())) {
                this._log('[i] No engine tabs — auto-loading from canvas nodes…', 'meta');
                if (typeof liveExec.autoHydrateFromCanvas === 'function') {
                    const created = await liveExec.autoHydrateFromCanvas();
                    if (created === 0) {
                        this._log('[!] No canvas nodes with source code — nothing to execute.', 'warn');
                        return;
                    }
                    this._log(`[+] Auto-loaded ${created} engine tab(s) from canvas`, 'info');
                    this._refreshEnginePool();
                } else {
                    this._log('[!] No engine tabs with code — nothing to execute.', 'warn');
                    return;
                }
            }

            // Save current tab code first
            if (typeof liveExec._saveCurrentTabCode === 'function') {
                liveExec._saveCurrentTabCode();
            }

            const tabs = Array.from(liveExec.engineTabs.values()).filter(t => t.code.trim());
            if (tabs.length === 0) {
                this._log('[!] All engine tabs are empty.', 'warn');
                return;
            }

            this.cycleCount++;
            this.elCycles.textContent = this.cycleCount;
            this._log(`━━━ Cycle #${this.cycleCount}  (${tabs.length} engine${tabs.length > 1 ? 's' : ''}) ━━━`, 'meta');

            try {
                const resp = await fetch('/api/execution/engines/run-simultaneous', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tabs, reset_before: false })
                });
                const data = await resp.json();

                if (data.success && data.results) {
                    let passed = 0, failed = 0;
                    for (const r of data.results) {
                        const tag = r.language?.toUpperCase() || r.engine_letter?.toUpperCase() || '?';
                        if (r.skipped) {
                            this._log(`  [skip] [${tag}] ${r.label}: ${r.skip_reason}`, 'meta');
                        } else {
                            if (r.output) this._log(`  [${tag}] ${r.label}: ${r.output.trim()}`, r.success ? 'output' : 'error');
                            if (r.error)  this._log(`  [ERR] [${tag}] ${r.error}`, 'error');
                            if (r.success && !r.skipped) passed++; else failed++;
                        }
                    }

                    const s = data.summary || {};
                    const total = (s.passed || passed) + (s.failed || failed);
                    const pct = total > 0 ? Math.round(((s.passed || passed) / total) * 100) : 0;
                    this.elPassRate.textContent = `${pct}%`;
                    this.elLastRun.textContent = new Date().toLocaleTimeString();
                    this.elEngineCount.textContent = tabs.length;

                    this._history.push({
                        time:   Date.now(),
                        passed: s.passed || passed,
                        failed: s.failed || failed,
                        ms:     Math.round((s.total_time || 0) * 1000),
                    });
                    if (this._history.length > this._maxHistory) {
                        this._history = this._history.slice(-this._maxHistory);
                    }

                    this._log(`  [+] ${s.passed || passed}/${total} passed, ${Math.round((s.total_time || 0) * 1000)}ms`, 'info');
                    this._drawTimeline();
                } else {
                    this._log(`  [ERR] ${data.error || 'Unknown error'}`, 'error');
                }
            } catch (e) {
                this._log(`  [ERR] Network error: ${e.message}`, 'error');
            }

            this._refreshEnginePool();
            this._refreshRuntimeMatrix();
        }

        /* ────────────────────────────────────────
           RUNTIME BACKEND COMMANDS
           ──────────────────────────────────────── */
        async _postRuntimeCommand(action) {
            try {
                await fetch('/api/runtime/control', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        action,
                        interval: this.intervalSec,
                    })
                });
            } catch (_) { /* non-critical */ }
        }

        /* ────────────────────────────────────────
           SOCKETIO HANDLERS
           ──────────────────────────────────────── */
        _onCycleResult(data) {
            if (data.results) {
                for (const r of data.results) {
                    const tag = r.language?.toUpperCase() || '?';
                    if (r.output) this._log(`  [${tag}] ${r.output.trim()}`, 'output');
                    if (r.error)  this._log(`  [ERR] [${tag}] ${r.error}`, 'error');
                }
            }
        }

        _onStatusUpdate(data) {
            if (data.state === 'running')  this.elRunState.textContent = 'running';
            if (data.state === 'paused')   this.elRunState.textContent = 'paused';
            if (data.state === 'stopped')  this.elRunState.textContent = 'idle';
        }

        _onRuntimeError(data) {
            this._log(`[ERR] Runtime error: ${data.error || 'unknown'}`, 'error');
        }

        /* ────────────────────────────────────────
           LOG CONSOLE
           ──────────────────────────────────────── */
        _log(text, type = 'info') {
            if (!this.logEl) return;
            const line = document.createElement('div');
            line.className = `runtime-log__line runtime-log__line--${type}`;
            const ts = new Date().toLocaleTimeString('en-US', { hour12: false });
            line.textContent = `[${ts}] ${text}`;
            this.logEl.appendChild(line);
            // Auto-scroll
            this.logEl.scrollTop = this.logEl.scrollHeight;
            // Trim
            while (this.logEl.children.length > 500) {
                this.logEl.removeChild(this.logEl.firstChild);
            }
        }

        _clearLog() {
            if (this.logEl) this.logEl.innerHTML = '';
            this._log('Log cleared', 'meta');
        }

        /* ────────────────────────────────────────
           API DOCS (SWAGGER)
           ──────────────────────────────────────── */
        _toggleDocs(forceState) {
            if (!this.docsCard) return;
            const show = forceState !== undefined ? forceState : this.docsCard.style.display === 'none';
            if (show) {
                // Ensure the panel is open first
                if (!this.isOpen) this.open();
                // Build the iframe URL dynamically from the current origin
                // so it works on any host/port after migration or clone
                if (!this.docsIframe.src || this.docsIframe.src === 'about:blank') {
                    this.docsIframe.src = `${location.origin}/api/docs`;
                }
                this.docsCard.style.display = '';
                // Tell the CSS grid to allocate a docs row
                this.dashboard?.classList.add('show-docs');
                this.btnDocs?.classList.add('active');
                // Scroll to make it visible
                this.docsCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            } else {
                this.docsCard.style.display = 'none';
                this.dashboard?.classList.remove('show-docs');
                this.btnDocs?.classList.remove('active');
            }
        }

        /* ────────────────────────────────────────
           UPTIME CLOCK
           ──────────────────────────────────────── */
        _tick() {
            setInterval(() => {
                if (this.startedAt) {
                    const elapsed = Date.now() - this.startedAt;
                    this.elUptime.textContent = this._formatDuration(elapsed);
                }
            }, 1000);
        }

        _formatDuration(ms) {
            const s = Math.floor(ms / 1000);
            const m = Math.floor(s / 60);
            const h = Math.floor(m / 60);
            if (h > 0) return `${h}h ${m % 60}m ${s % 60}s`;
            if (m > 0) return `${m}m ${s % 60}s`;
            return `${s}s`;
        }

        /* ────────────────────────────────────────
           ENGINE POOL DISPLAY
           ──────────────────────────────────────── */
        _refreshEnginePool() {
            const liveExec = window.liveExec;
            if (!liveExec || !liveExec.engineTabs || liveExec.engineTabs.size === 0) {
                this.enginesListEl.innerHTML = '<div class="runtime-engines-empty">No engines configured</div>';
                this.elEngineCount.textContent = '0';
                return;
            }

            let html = '';
            liveExec.engineTabs.forEach((tab) => {
                const lang = (tab.language || '?').toUpperCase();
                const letter = (tab.engine_letter || '?').toUpperCase();
                const hasCode = tab.code && tab.code.trim().length > 0;
                const lines = hasCode ? tab.code.trim().split('\n').length : 0;
                html += `
                    <div class="runtime-engine-item">
                        <span class="runtime-engine-letter">${letter}</span>
                        <span class="runtime-engine-lang" data-lang="${tab.language}">${lang}</span>
                        <span class="runtime-engine-label">${this._esc(tab.label)}</span>
                        <span class="runtime-engine-lines">${lines} lines</span>
                        <span class="runtime-engine-dot ${hasCode ? 'runtime-engine-dot--active' : ''}"></span>
                    </div>`;
            });
            this.enginesListEl.innerHTML = html;
            this.elEngineCount.textContent = liveExec.engineTabs.size;
        }

        /* ────────────────────────────────────────
           TIMELINE CHART (canvas mini-chart)
           ──────────────────────────────────────── */
        _drawTimeline() {
            const canvas = this.timelineCanvas;
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            if (!ctx) return;

            // Resize canvas to container
            const rect = canvas.parentElement.getBoundingClientRect();
            canvas.width  = rect.width  - 16;  // padding
            canvas.height = Math.max(60, rect.height - 32);

            const W = canvas.width;
            const H = canvas.height;
            const data = this._history;

            ctx.clearRect(0, 0, W, H);

            if (data.length < 2) {
                ctx.fillStyle = 'rgba(148,163,184,0.3)';
                ctx.font = '11px system-ui';
                ctx.textAlign = 'center';
                ctx.fillText('Waiting for data…', W / 2, H / 2);
                return;
            }

            // Draw execution time line chart
            const maxMs = Math.max(...data.map(d => d.ms), 1);
            const barW = Math.max(2, (W - 4) / data.length - 1);

            for (let i = 0; i < data.length; i++) {
                const d = data[i];
                const x = 2 + i * (barW + 1);
                const barH = Math.max(2, (d.ms / maxMs) * (H - 16));
                const y = H - 8 - barH;

                // Color: green if all passed, orange if mixed, red if all failed
                const total = d.passed + d.failed;
                const ratio = total > 0 ? d.passed / total : 1;
                if (ratio >= 1)       ctx.fillStyle = 'rgba(34,197,94,0.7)';
                else if (ratio > 0.5) ctx.fillStyle = 'rgba(251,191,36,0.7)';
                else                  ctx.fillStyle = 'rgba(239,68,68,0.7)';

                ctx.fillRect(x, y, barW, barH);
            }

            // Baseline
            ctx.strokeStyle = 'rgba(148,163,184,0.15)';
            ctx.beginPath();
            ctx.moveTo(0, H - 8);
            ctx.lineTo(W, H - 8);
            ctx.stroke();

            // Label
            ctx.fillStyle = 'rgba(148,163,184,0.5)';
            ctx.font = '9px system-ui';
            ctx.textAlign = 'right';
            ctx.fillText(`${maxMs}ms`, W - 4, 12);
        }

        /* ────────────────────────────────────────
           REGISTRY SLOT MATRIX — Interactive Mission Control
           ──────────────────────────────────────── */
        _buildRuntimeMatrix() {
            if (!this.matrixBody) return;

            const NAMES   = window.ENGINE_NAMES   || { a:'Python', b:'JavaScript', c:'TypeScript', d:'Rust', e:'Java', f:'Swift', g:'C++', h:'R', i:'Go', j:'Ruby', k:'C#', l:'Kotlin', m:'C', n:'Bash', o:'Perl' };
            const LETTERS = window.ENGINE_LETTERS  || Object.keys(NAMES);
            const SLOTS   = window.ENGINE_SLOTS    || { a:64, b:16, c:16, d:16, e:16, f:16, g:16, h:16, i:16, j:16, k:16, l:16, m:16, n:16, o:16 };
            const MAX_COLS = 16;

            let html = '';

            for (const letter of LETTERS) {
                const totalSlots = SLOTS[letter] || 16;
                const subRows = Math.ceil(totalSlots / MAX_COLS);

                for (let sr = 0; sr < subRows; sr++) {
                    const startSlot = sr * MAX_COLS + 1;
                    const endSlot   = Math.min((sr + 1) * MAX_COLS, totalSlots);
                    const rowLabel  = subRows > 1
                        ? `${letter}${sr > 0 ? ' ' + startSlot + '-' + endSlot : ''}`
                        : letter;

                    html += `<div class="exec-matrix-row" id="rt-matrix-row-${letter}-${sr}">`;
                    html += `<span class="exec-matrix-engine-label" data-engine="${letter}" title="${NAMES[letter]}${subRows > 1 ? ' [' + startSlot + '-' + endSlot + ']' : ''}">${rowLabel}</span>`;
                    html += '<div class="exec-matrix-slots">';
                    for (let s = startSlot; s <= startSlot + MAX_COLS - 1; s++) {
                        if (s > totalSlots) {
                            html += '<span class="exec-matrix-cell slot-disabled"></span>';
                        } else {
                            const addr = `${letter}${s}`;
                            html += `<span class="exec-matrix-cell slot-empty" id="rt-mcell-${addr}" data-addr="${addr}"></span>`;
                        }
                    }
                    html += '</div></div>';
                }
            }

            this.matrixBody.innerHTML = html;

            // ── Bind interactive events to matrix cells ──
            this._bindMatrixInteractions();
        }

        /**
         * Attach click / dblclick / long-press handlers to every matrix cell.
         *
         *  Single click → Info overlay (provenance, token, code, stats)
         *  Double click → Lock/pin slot indefinitely
         *  Long press   → Eviction confirmation dialog
         */
        _bindMatrixInteractions() {
            if (!this.matrixBody) return;

            // Tracking for long-press detection
            let longPressTimer = null;
            let longPressAddr  = null;
            const LONG_PRESS_MS = 800;

            this.matrixBody.addEventListener('pointerdown', (e) => {
                const cell = e.target.closest('.exec-matrix-cell[data-addr]');
                if (!cell || cell.classList.contains('slot-empty') || cell.classList.contains('slot-disabled')) return;
                longPressAddr = cell.dataset.addr;
                longPressTimer = setTimeout(() => {
                    this._showEvictConfirm(longPressAddr);
                    longPressAddr = null;
                }, LONG_PRESS_MS);
            });

            this.matrixBody.addEventListener('pointerup', () => {
                clearTimeout(longPressTimer);
                longPressTimer = null;
            });
            this.matrixBody.addEventListener('pointerleave', () => {
                clearTimeout(longPressTimer);
                longPressTimer = null;
            });

            // Single click → info overlay
            this.matrixBody.addEventListener('click', (e) => {
                const cell = e.target.closest('.exec-matrix-cell[data-addr]');
                if (!cell || cell.classList.contains('slot-empty') || cell.classList.contains('slot-disabled')) return;
                // Only trigger if the long-press did not fire
                if (longPressAddr !== null) {
                    this._showSlotOverlay(cell.dataset.addr, cell);
                }
            });

            // Double click → lock/unlock
            this.matrixBody.addEventListener('dblclick', (e) => {
                const cell = e.target.closest('.exec-matrix-cell[data-addr]');
                if (!cell || cell.classList.contains('slot-empty') || cell.classList.contains('slot-disabled')) return;
                e.preventDefault();
                this._toggleSlotLock(cell.dataset.addr);
            });
        }

        /**
         * Refreshed matrix using the ENRICHED endpoint that includes
         * provenance, TTL, lock status, and staging pipeline state.
         */
        async _refreshRuntimeMatrix() {
            try {
                const resp = await fetch('/api/registry/matrix/enriched');
                const data = await resp.json();
                if (!data.success) return;

                const SLOTS = window.ENGINE_SLOTS || { a:64, b:16, c:16, d:16, e:16, f:16, g:16, h:16,
                                i:16, j:16, k:16, l:16, m:16, n:16, o:16 };
                const MAX_COLS = 16;
                let committed = 0, hotSwap = 0, locked = 0, apiOrigin = 0, total = 0;

                const engines = data.engines || {};
                for (const engineName of Object.keys(engines)) {
                    const row = engines[engineName];
                    const letter = row.letter;
                    const engineMaxSlots = row.max_slots || SLOTS[letter] || 16;
                    const subRows = Math.ceil(engineMaxSlots / MAX_COLS);
                    let rowHasNodes = false;

                    for (let s = 1; s <= engineMaxSlots; s++) {
                        const addr = `${letter}${s}`;
                        const cell = document.getElementById(`rt-mcell-${addr}`);
                        if (!cell) continue;

                        const slotData = row.slots?.[String(s)];
                        cell.className = 'exec-matrix-cell';
                        cell.title = '';
                        cell.textContent = '';

                        if (!slotData || !slotData.node_id) {
                            cell.classList.add('slot-empty');
                        } else {
                            total++;
                            rowHasNodes = true;
                            const prov = slotData.provenance || {};
                            const isLocked = slotData.locked;
                            const origin = prov.origin || 'live-exec';

                            // Primary state class
                            if (isLocked) {
                                cell.classList.add('slot-locked');
                                locked++;
                            } else if (slotData.needs_swap) {
                                cell.classList.add('slot-hot-swap');
                                hotSwap++;
                            } else {
                                cell.classList.add('slot-committed');
                                committed++;
                            }

                            // Origin indicator (left border accent)
                            if (origin === 'api') {
                                cell.classList.add('origin-api');
                                apiOrigin++;
                            } else if (origin === 'canvas') {
                                cell.classList.add('origin-canvas');
                            } else {
                                cell.classList.add('origin-live');
                            }

                            // Mark as occupied for cursor/hover
                            cell.classList.add('slot-occupied');

                            // Icon: locked = [L], api = ◆, human = ●
                            cell.textContent = isLocked ? '' : (origin === 'api' ? '\u25C6' : '\u25CF');

                            // Tooltip with provenance summary
                            const ttlStr = prov.ttl_remaining > 0
                                ? `TTL ${Math.round(prov.ttl_remaining)}s`
                                : (prov.expired ? 'EXPIRED' : '');
                            const parts = [
                                addr.toUpperCase(),
                                prov.submitter || '',
                                origin === 'api' ? '[API]' : '[HUMAN]',
                                ttlStr,
                                isLocked ? 'LOCKED' : '',
                            ].filter(Boolean);
                            cell.title = parts.join(' \u2014 ');

                            // Store provenance on the cell for the overlay
                            cell.dataset.origin = origin;
                            cell.dataset.locked = isLocked ? '1' : '0';
                        }
                    }

                    for (let sr = 0; sr < subRows; sr++) {
                        const rowEl = document.getElementById(`rt-matrix-row-${letter}-${sr}`);
                        rowEl?.classList.toggle('row-active', rowHasNodes);
                    }
                }

                // ── Render in-flight staging pipeline entries ──
                const inFlight = data.in_flight || [];
                for (const ifr of inFlight) {
                    const cell = document.getElementById(`rt-mcell-${ifr.reserved_address}`);
                    if (!cell) continue;
                    cell.className = 'exec-matrix-cell';
                    const phaseClass = {
                        'queued': 'slot-staged',
                        'speculating': 'slot-speculating',
                        'promoting': 'slot-promoting',
                        'passed': 'slot-speculating',
                    }[ifr.phase] || 'slot-staged';
                    cell.classList.add(phaseClass);
                    cell.textContent = '\u25CB';  // ○ = in-flight
                    cell.title = `${ifr.reserved_address.toUpperCase()} \u2014 ${ifr.label} \u2014 ${ifr.phase.toUpperCase()}`;
                }

                if (this.matrixStats) {
                    const parts = [
                        `${committed} committed`,
                        locked > 0 ? `${locked} locked` : '',
                        hotSwap > 0 ? `${hotSwap} pending` : '',
                        apiOrigin > 0 ? `${apiOrigin} api` : '',
                        `${total} total`,
                    ].filter(Boolean);
                    this.matrixStats.textContent = parts.join(' \u00b7 ');
                }
            } catch (e) {
                console.error('[RuntimePanel] _refreshRuntimeMatrix failed', e);
            }
        }

        /* ────────────────────────────────────────
           SLOT INFO OVERLAY (single-click)
           ──────────────────────────────────────── */
        async _showSlotOverlay(addr, anchorEl) {
            this._closeSlotOverlay();

            try {
                const resp = await fetch(`/api/registry/slot/${addr}/info`);
                const info = await resp.json();
                if (!info.success || !info.occupied) return;

                const prov = info.provenance || {};
                const stg  = info.staging || {};
                const ledg = info.ledger || {};
                const xst  = info.exec_stats || {};
                const origin = info.origin || prov.origin || 'live-exec';
                const isLocked = info.locked;
                const NAMES = window.ENGINE_NAMES || {};
                const engineLang = stg.language || ledg.language || NAMES[addr[0]] || info.engine || '';

                // Position overlay near the cell
                const rect = anchorEl.getBoundingClientRect();
                const overlayX = Math.min(rect.left, window.innerWidth - 360);
                const overlayY = Math.max(8, rect.top - 260);

                // Scrim
                const scrim = document.createElement('div');
                scrim.className = 'slot-info-scrim';
                scrim.addEventListener('click', () => this._closeSlotOverlay());
                document.body.appendChild(scrim);

                // Overlay
                const el = document.createElement('div');
                el.className = 'slot-info-overlay';
                el.id = 'slot-info-overlay';
                el.style.left = `${overlayX}px`;
                el.style.top  = `${overlayY}px`;

                // Origin badge
                const originLabel = origin === 'api' ? 'API AGENT' : (origin === 'canvas' ? 'CANVAS' : 'HUMAN');
                const badgeClass  = origin === 'api' ? 'api' : (origin === 'canvas' ? 'canvas' : 'live');

                // Code to show
                const codeStr = stg.code || ledg.source_code || stg.code_preview || '';
                const label = stg.label || ledg.display_name || info.node_id?.slice(0, 16) || addr.toUpperCase();

                // TTL display
                let ttlHtml = '';
                if (prov.token) {
                    const ttlClass = prov.expired ? 'expired' : 'ttl';
                    const ttlText  = prov.expired ? 'EXPIRED' : `${Math.round(prov.ttl_remaining || 0)}s remaining`;
                    ttlHtml = `
                        <div class="slot-info-overlay__row">
                            <span class="slot-info-overlay__label">Token</span>
                            <span class="slot-info-overlay__value slot-info-overlay__value--token">${this._esc(prov.token)}</span>
                        </div>
                        <div class="slot-info-overlay__row">
                            <span class="slot-info-overlay__label">TTL</span>
                            <span class="slot-info-overlay__value slot-info-overlay__value--${ttlClass}">${ttlText}</span>
                        </div>`;
                }

                el.innerHTML = `
                    <div class="slot-info-overlay__header">
                        <span class="slot-info-overlay__addr">${addr.toUpperCase()}</span>
                        <span class="slot-info-overlay__origin-badge slot-info-overlay__origin-badge--${badgeClass}">${originLabel}</span>
                        <button class="slot-info-overlay__close" id="slot-overlay-close"><i data-lucide="x"></i></button>
                    </div>
                    <div class="slot-info-overlay__body">
                        <div class="slot-info-overlay__section">
                            <div class="slot-info-overlay__section-title">Identity</div>
                            <div class="slot-info-overlay__row">
                                <span class="slot-info-overlay__label">Label</span>
                                <span class="slot-info-overlay__value">${this._esc(label)}</span>
                            </div>
                            <div class="slot-info-overlay__row">
                                <span class="slot-info-overlay__label">Engine</span>
                                <span class="slot-info-overlay__value">${this._esc(engineLang)}</span>
                            </div>
                            <div class="slot-info-overlay__row">
                                <span class="slot-info-overlay__label">Submitter</span>
                                <span class="slot-info-overlay__value">${this._esc(prov.submitter || ledg.display_name || 'Live Execution')}</span>
                            </div>
                            ${prov.agent_id ? `<div class="slot-info-overlay__row">
                                <span class="slot-info-overlay__label">Agent ID</span>
                                <span class="slot-info-overlay__value slot-info-overlay__value--token">${this._esc(prov.agent_id)}</span>
                            </div>` : ''}
                        </div>

                        <div class="slot-info-overlay__section">
                            <div class="slot-info-overlay__section-title">Provenance</div>
                            ${ttlHtml}
                            <div class="slot-info-overlay__row">
                                <span class="slot-info-overlay__label">Status</span>
                                <span class="slot-info-overlay__value ${isLocked ? 'slot-info-overlay__value--locked' : ''}">${isLocked ? 'LOCKED' : (stg.phase || 'committed').toUpperCase()}</span>
                            </div>
                            <div class="slot-info-overlay__row">
                                <span class="slot-info-overlay__label">Node ID</span>
                                <span class="slot-info-overlay__value">${this._esc((info.node_id || '').slice(0, 20))}</span>
                            </div>
                        </div>

                        ${stg.spec_execution_time || ledg.version ? `
                        <div class="slot-info-overlay__section">
                            <div class="slot-info-overlay__section-title">Performance</div>
                            ${stg.spec_execution_time ? `<div class="slot-info-overlay__row">
                                <span class="slot-info-overlay__label">Exec time</span>
                                <span class="slot-info-overlay__value">${(stg.spec_execution_time * 1000).toFixed(1)}ms</span>
                            </div>` : ''}
                            ${stg.spec_success !== undefined ? `<div class="slot-info-overlay__row">
                                <span class="slot-info-overlay__label">Result</span>
                                <span class="slot-info-overlay__value">${stg.spec_success ? 'PASS' : 'FAIL'}</span>
                            </div>` : ''}
                            ${ledg.version ? `<div class="slot-info-overlay__row">
                                <span class="slot-info-overlay__label">Version</span>
                                <span class="slot-info-overlay__value">v${ledg.version}</span>
                            </div>` : ''}
                        </div>` : ''}

                        ${codeStr ? `
                        <div class="slot-info-overlay__section">
                            <div class="slot-info-overlay__section-title">Code</div>
                            <pre class="slot-info-overlay__code">${this._esc(codeStr.slice(0, 500))}</pre>
                        </div>` : ''}

                        ${stg.spec_output_preview ? `
                        <div class="slot-info-overlay__section">
                            <div class="slot-info-overlay__section-title">Last Output</div>
                            <pre class="slot-info-overlay__code">${this._esc(stg.spec_output_preview)}</pre>
                        </div>` : ''}
                    </div>
                    <div class="slot-info-overlay__actions">
                        <button class="slot-info-overlay__btn ${isLocked ? 'slot-info-overlay__btn--unlock' : 'slot-info-overlay__btn--lock'}"
                                id="slot-overlay-lock"><i data-lucide="${isLocked ? 'unlock' : 'lock'}"></i> ${isLocked ? 'Unlock' : 'Lock'}</button>
                        <button class="slot-info-overlay__btn slot-info-overlay__btn--evict"
                                id="slot-overlay-evict"><i data-lucide="trash-2"></i> Evict</button>
                    </div>
                `;

                document.body.appendChild(el);
                if (typeof lucide !== 'undefined') lucide.createIcons({ root: el });

                // Event bindings
                el.querySelector('#slot-overlay-close')?.addEventListener('click', () => this._closeSlotOverlay());
                el.querySelector('#slot-overlay-lock')?.addEventListener('click', () => {
                    this._toggleSlotLock(addr);
                    this._closeSlotOverlay();
                });
                el.querySelector('#slot-overlay-evict')?.addEventListener('click', () => {
                    this._closeSlotOverlay();
                    this._showEvictConfirm(addr);
                });

            } catch (e) {
                console.error('[RuntimePanel] _showSlotOverlay failed', e);
            }
        }

        _closeSlotOverlay() {
            document.getElementById('slot-info-overlay')?.remove();
            document.querySelector('.slot-info-scrim')?.remove();
        }

        /* ────────────────────────────────────────
           SLOT LOCK/PIN (double-click)
           ──────────────────────────────────────── */
        async _toggleSlotLock(addr) {
            const cell = document.getElementById(`rt-mcell-${addr}`);
            if (!cell) return;
            const isLocked = cell.dataset.locked === '1';
            const endpoint = isLocked
                ? `/api/registry/slot/${addr}/unlock`
                : `/api/registry/slot/${addr}/lock`;

            try {
                const resp = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ reason: isLocked ? 'Unpinned from dashboard' : 'Pinned from dashboard' }),
                });
                const data = await resp.json();
                if (data.success) {
                    this._log(`${isLocked ? '[UNLOCK]' : '[LOCK]'} Slot ${addr.toUpperCase()} ${isLocked ? 'unlocked' : 'locked'}`, 'info');
                    this._refreshRuntimeMatrix();
                }
            } catch (e) {
                this._log(`[ERR] Lock toggle failed for ${addr}: ${e.message}`, 'error');
            }
        }

        /* ────────────────────────────────────────
           SLOT EVICTION (long-press → confirm)
           ──────────────────────────────────────── */
        _showEvictConfirm(addr) {
            // Remove any existing dialog
            document.querySelector('.slot-evict-confirm')?.remove();
            document.querySelector('.slot-info-scrim')?.remove();

            const scrim = document.createElement('div');
            scrim.className = 'slot-info-scrim';
            document.body.appendChild(scrim);

            const dlg = document.createElement('div');
            dlg.className = 'slot-evict-confirm';
            dlg.innerHTML = `
                <div class="slot-evict-confirm__title"><i data-lucide="alert-triangle"></i> Evict Slot ${addr.toUpperCase()}?</div>
                <div class="slot-evict-confirm__msg">
                    This will permanently remove the snippet from the server.<br>
                    The code file is preserved for forensics.
                </div>
                <div class="slot-evict-confirm__btns">
                    <button class="slot-evict-confirm__btn slot-evict-confirm__btn--cancel" id="evict-cancel"><i data-lucide="x"></i> Cancel</button>
                    <button class="slot-evict-confirm__btn slot-evict-confirm__btn--confirm" id="evict-confirm"><i data-lucide="trash-2"></i> Evict</button>
                </div>
            `;
            document.body.appendChild(dlg);
            if (typeof lucide !== 'undefined') lucide.createIcons({ root: dlg });

            dlg.querySelector('#evict-cancel').addEventListener('click', () => {
                dlg.remove();
                scrim.remove();
            });
            scrim.addEventListener('click', () => {
                dlg.remove();
                scrim.remove();
            });
            dlg.querySelector('#evict-confirm').addEventListener('click', async () => {
                dlg.remove();
                scrim.remove();
                await this._evictSlot(addr);
            });
        }

        async _evictSlot(addr) {
            try {
                const resp = await fetch(`/api/registry/slot/${addr}/evict`, {
                    method: 'DELETE',
                });
                const data = await resp.json();
                if (data.success) {
                    this._log(`[DEL] Evicted ${addr.toUpperCase()}: ${data.evicted_node}`, 'info');
                    // Flash the cell red then clear it
                    this._flashRuntimeCell(addr, 'error', 1500);
                    setTimeout(() => this._refreshRuntimeMatrix(), 1600);
                } else {
                    this._log(`[ERR] Evict failed: ${data.error}`, 'error');
                }
            } catch (e) {
                this._log(`[ERR] Evict error: ${e.message}`, 'error');
            }
        }

        /* ────────────────────────────────────────
           SNIPPET LIFECYCLE SOCKETIO LISTENER
           ──────────────────────────────────────── */
        _bindSnippetLifecycleEvents() {
            if (!this._socket) return;

            this._socket.on('snippet_lifecycle', (data) => {
                const ev   = data.event;
                const addr = data.address;

                if (ev === 'submitted') {
                    const originIcon = data.origin === 'api' ? '[API]' : '[USR]';
                    this._log(
                        `${originIcon} ${data.submitter || 'Unknown'} \u2192 ${(addr || '??').toUpperCase()} ` +
                        `[${(data.language || '').toUpperCase()}] ${data.label || ''} (${data.phase})`,
                        'info'
                    );
                    if (addr) {
                        this._flashRuntimeCell(addr, 'staged');
                        // Animate through pipeline stages
                        setTimeout(() => this._flashRuntimeCell(addr, 'speculating'), 400);
                        setTimeout(() => {
                            const finalState = data.phase === 'promoted' ? 'success' : 'error';
                            this._flashRuntimeCell(addr, finalState, 3000);
                        }, 1200);
                    }
                    this._refreshRuntimeMatrix();
                } else if (ev === 'locked') {
                    this._log(`[LOCK] Slot ${(addr || '').toUpperCase()} locked`, 'meta');
                    this._refreshRuntimeMatrix();
                } else if (ev === 'unlocked') {
                    this._log(`[UNLOCK] Slot ${(addr || '').toUpperCase()} unlocked`, 'meta');
                    this._refreshRuntimeMatrix();
                } else if (ev === 'evicted') {
                    this._log(`[DEL] Slot ${(addr || '').toUpperCase()} evicted`, 'warn');
                    this._refreshRuntimeMatrix();
                }
            });
        }

        _flashRuntimeCell(addr, state, durationMs = 0) {
            const cell = document.getElementById(`rt-mcell-${addr}`);
            if (!cell) return;
            cell.className = `exec-matrix-cell slot-${state}`;
            if (durationMs > 0) {
                setTimeout(() => {
                    cell.className = 'exec-matrix-cell slot-committed';
                    cell.textContent = '\u25CF';
                }, durationMs);
            }
        }

        /* ────────────────────────────────────────
           HELPERS
           ──────────────────────────────────────── */
        _esc(s) {
            const d = document.createElement('div');
            d.textContent = s || '';
            return d.innerHTML;
        }
    }

    /* ══════════════════════════════════════════════════════════════
       BOOTSTRAP
       ══════════════════════════════════════════════════════════════ */
    document.addEventListener('DOMContentLoaded', () => {
        window.runtimePanel = new RuntimePanel();
    });
})();
