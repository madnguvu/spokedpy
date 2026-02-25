/**
 * Runtime Server Panel — Bottom-edge resizable dashboard  (v2)
 *
 * Layout: Two primary columns fill the dashboard area
 *   LEFT  — Registry Matrix (interactive grid with per-cell status)
 *   RIGHT — Live Event Feed (scrolling log with slot addresses + status)
 *
 * Compact stats ribbon sits above the two columns.
 *
 * Each matrix cell shows real-time status:
 *   - Empty (dim)
 *   - Committed (blue border)
 *   - Executing (pulsing glow)
 *   - Passed (green flash, then steady)
 *   - Failed (red flash, holds)
 *   - Locked (gold ring + indicator)
 *   - Staged / Speculating (amber / purple pulse)
 *
 * Dependencies: SocketIO (loaded globally), LiveExecutionPanel (window.liveExec).
 */

(function () {
    'use strict';

    const MIN_HEIGHT     = 48;
    const DEFAULT_HEIGHT = 480;
    const MAX_HEIGHT_PCT = 0.88;
    const PERSIST_KEY    = 'runtime-panel-height';
    const PERSIST_INT    = 'runtime-panel-interval';
    const DEFAULT_INTERVAL = 5;

    // Cell status constants
    const S = {
        EMPTY:       'empty',
        COMMITTED:   'committed',
        EXECUTING:   'executing',
        PASSED:      'passed',
        FAILED:      'failed',
        LOCKED:      'locked',
        STAGED:      'staged',
        SPECULATING: 'speculating',
        PROMOTING:   'promoting',
        HOT_SWAP:    'hot-swap',
        DISABLED:    'disabled',
    };

    class RuntimePanel {
        constructor() {
            this.isOpen       = false;
            this.isRunning    = false;
            this.isPaused     = false;
            this.intervalSec  = this._restoreInterval();
            this.cycleCount   = 0;
            this.startedAt    = null;
            this._loopTimer   = null;
            this._socket      = null;
            this._history     = [];
            this._maxHistory  = 200;

            // Per-slot status for live visualization
            this._slotStatus = {};

            this._injectHTML();
            this._cacheDOM();
            this._bindEvents();
            this._restoreHeight();
            this._connectSocket();
            this._buildRuntimeMatrix();
            this._tick();
        }

        /* ──────────────────────────────────────────
           DOM INJECTION
           ────────────────────────────────────────── */
        _injectHTML() {
            const panel = document.createElement('div');
            panel.id = 'runtime-panel';
            panel.className = 'runtime-panel runtime-panel--collapsed';
            panel.innerHTML = `
                <div class="runtime-panel__resize" id="runtime-resize"></div>

                <div class="runtime-panel__tab" id="runtime-tab">
                    <img src="/static/images/engine_tab.png" alt="Runtime"
                         class="runtime-panel__tab-img" draggable="false">
                    <span class="runtime-panel__tab-badge" id="runtime-tab-badge"></span>
                </div>

                <div class="runtime-panel__body" id="runtime-body">

                    <!-- Top bar: transport + controls -->
                    <div class="runtime-panel__topbar">
                        <div class="runtime-panel__topbar-left">
                            <img src="/static/images/engine_tab.png" alt=""
                                 class="runtime-panel__topbar-icon" draggable="false">
                            <span class="runtime-panel__title">Runtime Server</span>
                            <span class="runtime-panel__status" id="runtime-status">stopped</span>
                        </div>
                        <div class="runtime-panel__topbar-center">
                            <button class="runtime-btn runtime-btn--play"  id="runtime-play"  title="Start"><i data-lucide="play"></i></button>
                            <button class="runtime-btn runtime-btn--pause" id="runtime-pause" title="Pause" disabled><i data-lucide="pause"></i></button>
                            <button class="runtime-btn runtime-btn--stop"  id="runtime-stop"  title="Stop"  disabled><i data-lucide="square"></i></button>
                            <button class="runtime-btn runtime-btn--once"  id="runtime-once"  title="Run once"><i data-lucide="refresh-cw"></i></button>
                            <div class="runtime-interval">
                                <label class="runtime-interval__label" for="runtime-interval-input">Int</label>
                                <input  type="range" id="runtime-interval-input" class="runtime-interval__slider"
                                        min="1" max="60" step="1" value="${this.intervalSec}">
                                <span class="runtime-interval__value" id="runtime-interval-value">${this.intervalSec}s</span>
                            </div>
                        </div>
                        <div class="runtime-panel__topbar-right">
                            <button class="runtime-btn runtime-btn--mesh" id="runtime-mesh-btn" title="Mesh Topology"><i data-lucide="network"></i></button>
                            <button class="runtime-btn runtime-btn--docs" id="runtime-api-docs" title="API Docs"><i data-lucide="book-open"></i></button>
                            <button class="runtime-btn runtime-btn--clear" id="runtime-clear-log" title="Clear feed"><i data-lucide="trash-2"></i></button>
                            <button class="runtime-btn runtime-btn--min"   id="runtime-minimise" title="Minimise"><i data-lucide="chevron-down"></i></button>
                        </div>
                    </div>

                    <!-- Compact stats ribbon -->
                    <div class="runtime-stats-ribbon" id="runtime-stats-ribbon">
                        <div class="rt-chip" title="Uptime"><span class="rt-chip__label">UP</span><span class="rt-chip__val" id="runtime-uptime">--</span></div>
                        <div class="rt-chip" title="Cycles"><span class="rt-chip__label">CYC</span><span class="rt-chip__val" id="runtime-cycles">0</span></div>
                        <div class="rt-chip" title="Engines"><span class="rt-chip__label">ENG</span><span class="rt-chip__val" id="runtime-engine-count">--</span></div>
                        <div class="rt-chip" title="Pass rate"><span class="rt-chip__label">PASS</span><span class="rt-chip__val" id="runtime-pass-rate">--</span></div>
                        <div class="rt-chip" title="Last run"><span class="rt-chip__label">LAST</span><span class="rt-chip__val" id="runtime-last-run">--</span></div>
                        <div class="rt-chip" title="State"><span class="rt-chip__label">STATE</span><span class="rt-chip__val" id="runtime-run-state">idle</span></div>
                        <div class="rt-chip rt-chip--legend">
                            <span class="rt-legend-dot rt-dot--committed"></span>ok
                            <span class="rt-legend-dot rt-dot--passed"></span>pass
                            <span class="rt-legend-dot rt-dot--failed"></span>fail
                            <span class="rt-legend-dot rt-dot--executing"></span>run
                            <span class="rt-legend-dot rt-dot--locked"></span>lock
                            <span class="rt-legend-dot rt-dot--staged"></span>staged
                        </div>
                    </div>

                    <!-- Two-column dashboard -->
                    <div class="runtime-panel__dash" id="runtime-dashboard">
                        <!-- LEFT: Registry Matrix -->
                        <div class="runtime-dash__matrix" id="runtime-matrix-card">
                            <div class="runtime-dash__matrix-head">
                                <span class="runtime-dash__matrix-title">Registry Matrix</span>
                                <span class="runtime-dash__matrix-stats" id="runtime-matrix-stats"></span>
                            </div>
                            <div class="runtime-dash__matrix-body" id="runtime-matrix-body"></div>
                        </div>

                        <!-- RIGHT: Live Event Feed -->
                        <div class="runtime-dash__feed" id="runtime-feed-card">
                            <div class="runtime-dash__feed-head">
                                <span class="runtime-dash__feed-title">Live Event Feed</span>
                                <span class="runtime-dash__feed-count" id="runtime-feed-count">0</span>
                            </div>
                            <div class="runtime-dash__feed-body" id="runtime-log"></div>
                        </div>
                    </div>

                    <!-- API Docs (hidden by default, replaces dashboard) -->
                    <div class="runtime-card runtime-card--docs" id="runtime-docs-card" style="display:none;">
                        <div class="runtime-card__title">
                            API Documentation
                            <button class="runtime-docs-pop-out" id="runtime-docs-popout" title="Open in new tab"><i data-lucide="external-link"></i></button>
                            <button class="runtime-docs-close" id="runtime-docs-close" title="Close docs"><i data-lucide="x"></i></button>
                        </div>
                        <iframe id="runtime-docs-iframe" class="runtime-docs-iframe"
                                sandbox="allow-scripts allow-forms allow-popups"
                                loading="lazy"></iframe>
                    </div>

                    <!-- Mesh Topology (hidden by default, replaces dashboard) -->
                    <div class="runtime-card runtime-card--mesh" id="runtime-mesh-card" style="display:none;">
                        <div class="runtime-card__title">
                            Distributed Mesh Topology
                            <button class="runtime-mesh-close" id="runtime-mesh-close" title="Close mesh view"><i data-lucide="x"></i></button>
                        </div>
                        <div class="runtime-mesh__body" id="runtime-mesh-body">
                            <div class="mesh-local" id="mesh-local"></div>
                            <div class="mesh-fabric" id="mesh-fabric"></div>
                            <div class="mesh-peers" id="mesh-peers"></div>
                        </div>
                        <div class="runtime-mesh__controls" id="runtime-mesh-controls">
                            <button class="runtime-btn runtime-btn--sm" id="mesh-add-peer-btn" title="Add peer"><i data-lucide="plus"></i> Add Peer</button>
                            <button class="runtime-btn runtime-btn--sm" id="mesh-activate-btn" title="Activate mesh"><i data-lucide="power"></i> Activate</button>
                            <button class="runtime-btn runtime-btn--sm" id="mesh-refresh-btn" title="Refresh topology"><i data-lucide="refresh-cw"></i></button>
                            <span class="mesh-instance-badge" id="mesh-instance-badge"></span>
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

            this.btnPlay    = document.getElementById('runtime-play');
            this.btnPause   = document.getElementById('runtime-pause');
            this.btnStop    = document.getElementById('runtime-stop');
            this.btnOnce    = document.getElementById('runtime-once');
            this.btnClear   = document.getElementById('runtime-clear-log');
            this.btnMin     = document.getElementById('runtime-minimise');
            this.intervalSlider = document.getElementById('runtime-interval-input');
            this.intervalLabel  = document.getElementById('runtime-interval-value');

            this.elUptime      = document.getElementById('runtime-uptime');
            this.elCycles      = document.getElementById('runtime-cycles');
            this.elRunState    = document.getElementById('runtime-run-state');
            this.elEngineCount = document.getElementById('runtime-engine-count');
            this.elLastRun     = document.getElementById('runtime-last-run');
            this.elPassRate    = document.getElementById('runtime-pass-rate');
            this.elStatus      = document.getElementById('runtime-status');

            this.logEl         = document.getElementById('runtime-log');
            this.feedCount     = document.getElementById('runtime-feed-count');
            this.matrixBody    = document.getElementById('runtime-matrix-body');
            this.matrixStats   = document.getElementById('runtime-matrix-stats');

            this.docsCard      = document.getElementById('runtime-docs-card');
            this.docsIframe    = document.getElementById('runtime-docs-iframe');
            this.btnDocs       = document.getElementById('runtime-api-docs');
            this.btnDocsPopout = document.getElementById('runtime-docs-popout');
            this.btnDocsClose  = document.getElementById('runtime-docs-close');

            // Mesh topology
            this.meshCard      = document.getElementById('runtime-mesh-card');
            this.meshBody      = document.getElementById('runtime-mesh-body');
            this.meshLocal     = document.getElementById('mesh-local');
            this.meshFabric    = document.getElementById('mesh-fabric');
            this.meshPeers     = document.getElementById('mesh-peers');
            this.meshControls  = document.getElementById('runtime-mesh-controls');
            this.btnMesh       = document.getElementById('runtime-mesh-btn');
            this.btnMeshClose  = document.getElementById('runtime-mesh-close');
            this.btnAddPeer    = document.getElementById('mesh-add-peer-btn');
            this.btnActivate   = document.getElementById('mesh-activate-btn');
            this.btnMeshRefresh = document.getElementById('mesh-refresh-btn');
            this.meshBadge     = document.getElementById('mesh-instance-badge');
        }

        /* ──────────────────────────────────────────
           EVENTS
           ────────────────────────────────────────── */
        _bindEvents() {
            this.tab.addEventListener('click', () => this.open());
            this.btnMin.addEventListener('click', () => this.close());

            this.btnPlay.addEventListener('click',  () => this.start());
            this.btnPause.addEventListener('click', () => this.pause());
            this.btnStop.addEventListener('click',  () => this.stop());
            this.btnOnce.addEventListener('click',  () => this.runOnce());
            this.btnClear.addEventListener('click', () => this._clearLog());

            this.btnDocs?.addEventListener('click', () => this._toggleDocs());
            this.btnDocsPopout?.addEventListener('click', () => {
                window.open(`${location.origin}/api/docs`, '_blank');
            });
            this.btnDocsClose?.addEventListener('click', () => this._toggleDocs(false));

            // Mesh topology bindings
            this.btnMesh?.addEventListener('click', () => this._toggleMesh());
            this.btnMeshClose?.addEventListener('click', () => this._toggleMesh(false));
            this.btnAddPeer?.addEventListener('click', () => this._promptAddPeer());
            this.btnActivate?.addEventListener('click', () => this._toggleMeshActivation());
            this.btnMeshRefresh?.addEventListener('click', () => this._refreshMeshTopology());

            this.intervalSlider.addEventListener('input', (e) => {
                this.intervalSec = parseInt(e.target.value, 10);
                this.intervalLabel.textContent = `${this.intervalSec}s`;
                this._persistInterval();
                if (this.isRunning && !this.isPaused) this._restartLoop();
            });

            this._initResize();
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.isOpen) this.close();
            });
        }

        /* ──────────────────────────────────────────
           OPEN / CLOSE
           ────────────────────────────────────────── */
        open() {
            this.isOpen = true;
            this.panel.classList.remove('runtime-panel--collapsed');
            this.panel.classList.add('runtime-panel--open');
            this._refreshRuntimeMatrix();
        }

        close() {
            this.isOpen = false;
            this.panel.classList.remove('runtime-panel--open');
            this.panel.classList.add('runtime-panel--collapsed');
        }

        /* ──────────────────────────────────────────
           RESIZE (top-edge drag)
           ────────────────────────────────────────── */
        _initResize() {
            let startY = 0, startH = 0, dragging = false;

            const onMove = (e) => {
                if (!dragging) return;
                e.preventDefault();
                const clientY = e.touches ? e.touches[0].clientY : e.clientY;
                const delta = startY - clientY;
                const maxH = window.innerHeight * MAX_HEIGHT_PCT;
                const newH = Math.max(MIN_HEIGHT + 20, Math.min(maxH, startH + delta));
                this.panel.style.height = `${newH}px`;
                this._persistHeight(newH);
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

        _persistHeight(h)  { try { localStorage.setItem(PERSIST_KEY, String(Math.round(h))); } catch (_) {} }
        _persistInterval()  { try { localStorage.setItem(PERSIST_INT, String(this.intervalSec)); } catch (_) {} }

        _restoreHeight() {
            try {
                const v = localStorage.getItem(PERSIST_KEY);
                if (v) {
                    const h = Math.max(MIN_HEIGHT + 20, Math.min(window.innerHeight * MAX_HEIGHT_PCT, Number(v)));
                    this.panel.style.height = `${h}px`;
                } else {
                    this.panel.style.height = `${DEFAULT_HEIGHT}px`;
                }
            } catch (_) {
                this.panel.style.height = `${DEFAULT_HEIGHT}px`;
            }
        }

        _restoreInterval() {
            try {
                const v = localStorage.getItem(PERSIST_INT);
                return v ? Math.max(1, Math.min(60, Number(v))) : DEFAULT_INTERVAL;
            } catch (_) { return DEFAULT_INTERVAL; }
        }

        /* ──────────────────────────────────────────
           SOCKETIO
           ────────────────────────────────────────── */
        _connectSocket() {
            if (typeof io === 'undefined') {
                console.warn('[RuntimePanel] SocketIO not loaded');
                return;
            }
            if (window._spokedSocket) {
                this._socket = window._spokedSocket;
            } else {
                this._socket = io();
                window._spokedSocket = this._socket;
            }

            this._socket.on('runtime_cycle_result', (data) => this._onCycleResult(data));
            this._socket.on('runtime_status',       (data) => this._onStatusUpdate(data));
            this._socket.on('runtime_error',         (data) => this._onRuntimeError(data));
            this._bindSnippetLifecycleEvents();
        }

        /* ──────────────────────────────────────────
           TRANSPORT CONTROLS
           ────────────────────────────────────────── */
        async start() {
            if (this.isRunning && !this.isPaused) return;

            if (this.isPaused) {
                this.isPaused = false;
                this._updateTransport();
                this._restartLoop();
                this._feedEvent('SYS', '--', 'Resumed', 'info');
                this._postRuntimeCommand('resume');
                return;
            }

            this.isRunning  = true;
            this.isPaused   = false;
            this.cycleCount = 0;
            this.startedAt  = Date.now();
            this._history   = [];
            this._updateTransport();
            this._feedEvent('SYS', '--', 'Runtime started', 'info');
            this._postRuntimeCommand('start');

            await this._executeCycle();
            this._restartLoop();
        }

        pause() {
            if (!this.isRunning || this.isPaused) return;
            this.isPaused = true;
            clearInterval(this._loopTimer);
            this._loopTimer = null;
            this._updateTransport();
            this._feedEvent('SYS', '--', 'Paused', 'warn');
            this._postRuntimeCommand('pause');
        }

        stop() {
            this.isRunning = false;
            this.isPaused  = false;
            clearInterval(this._loopTimer);
            this._loopTimer = null;
            this.startedAt  = null;
            this._updateTransport();
            this._feedEvent('SYS', '--', 'Stopped', 'warn');
            this._postRuntimeCommand('stop');
        }

        async runOnce() {
            this._feedEvent('SYS', '--', 'Single cycle triggered', 'info');
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
                this.tabBadge.textContent = '';
                this.tabBadge.className   = 'runtime-panel__tab-badge runtime-panel__tab-badge--running';
            } else if (paused) {
                this.elStatus.textContent = 'paused';
                this.elStatus.className   = 'runtime-panel__status runtime-panel__status--paused';
                this.elRunState.textContent = 'paused';
                this.tabBadge.textContent = '';
                this.tabBadge.className   = 'runtime-panel__tab-badge runtime-panel__tab-badge--paused';
            } else {
                this.elStatus.textContent = 'stopped';
                this.elStatus.className   = 'runtime-panel__status runtime-panel__status--stopped';
                this.elRunState.textContent = 'idle';
                this.tabBadge.textContent = '';
                this.tabBadge.className   = 'runtime-panel__tab-badge';
            }
        }

        /* ──────────────────────────────────────────
           EXECUTE ONE CYCLE
           ────────────────────────────────────────── */
        async _executeCycle() {
            /* ─── Per-Slot Execution ───────────────────────────────────
               Each committed registry slot executes independently via
               its own temp file.  No concatenation, no duplicate main().
               Falls back to engine-tab mode if no registry slots exist.
               ───────────────────────────────────────────────────────── */

            this.cycleCount++;
            this.elCycles.textContent = this.cycleCount;

            // ── Strategy 1: Per-slot execution from registry ──────────
            try {
                const slotResp = await fetch('/api/execution/registry/run-all-slots', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ reset_before: false })
                });
                const slotData = await slotResp.json();

                if (slotData.success && slotData.results && slotData.results.length > 0) {
                    this._feedEvent('SYS', '--',
                        `--- Cycle #${this.cycleCount} (${slotData.results.length} slot${slotData.results.length > 1 ? 's' : ''}) ---`, 'meta');

                    // Mark executing
                    for (const r of slotData.results) {
                        const addr = (r.address || '').toLowerCase();
                        if (addr) this._setCellStatus(addr, S.EXECUTING, r.language, r.label);
                    }

                    let passed = 0, failed = 0;
                    for (const r of slotData.results) {
                        const tag  = (r.language || r.engine_letter || '?').toUpperCase();
                        const addr = (r.address || `${r.engine_letter || '?'}1`).toLowerCase();

                        if (r.skipped) {
                            this._feedEvent(tag, addr.toUpperCase(), `SKIP: ${r.skip_reason}`, 'meta');
                            this._setCellStatus(addr, S.COMMITTED, r.language, r.label);
                        } else {
                            const ok = r.success && !r.error;
                            if (r.output) this._feedEvent(tag, addr.toUpperCase(), r.output.trim(), ok ? 'output' : 'error');
                            if (r.error)  this._feedEvent(tag, addr.toUpperCase(), r.error, 'error');
                            if (ok) { passed++; this._setCellStatus(addr, S.PASSED, r.language, r.label); }
                            else    { failed++; this._setCellStatus(addr, S.FAILED, r.language, r.label); }
                        }
                    }

                    const s = slotData.summary || {};
                    const total = (s.passed || passed) + (s.failed || failed);
                    const pct = total > 0 ? Math.round(((s.passed || passed) / total) * 100) : 0;
                    this.elPassRate.textContent = `${pct}%`;
                    this.elLastRun.textContent = new Date().toLocaleTimeString('en-US', { hour12: false });
                    this.elEngineCount.textContent = slotData.results.length;

                    this._history.push({
                        time: Date.now(),
                        passed: s.passed || passed,
                        failed: s.failed || failed,
                        ms: Math.round((s.total_time || 0) * 1000),
                    });
                    if (this._history.length > this._maxHistory) this._history = this._history.slice(-this._maxHistory);

                    this._feedEvent('SYS', '--', `${s.passed || passed}/${total} passed, ${Math.round((s.total_time || 0) * 1000)}ms`, 'info');
                    this._refreshRuntimeMatrix();
                    return;  // Done — used per-slot path
                }
            } catch (_slotErr) {
                // Fall through to legacy engine-tab path
            }

            // ── Strategy 2: Fallback — engine-tab mode (legacy) ───────
            const liveExec = window.liveExec;
            if (!liveExec) {
                this._feedEvent('SYS', '--', 'No registry slots and LiveExecPanel not available', 'warn');
                return;
            }

            // Auto-hydrate from canvas if needed
            if (!liveExec.engineTabs || liveExec.engineTabs.size === 0 ||
                Array.from(liveExec.engineTabs.values()).every(t => !t.code?.trim())) {
                this._feedEvent('SYS', '--', 'No registry slots -- falling back to canvas auto-hydrate...', 'meta');
                if (typeof liveExec.autoHydrateFromCanvas === 'function') {
                    const created = await liveExec.autoHydrateFromCanvas();
                    if (created === 0) {
                        this._feedEvent('SYS', '--', 'No canvas nodes with source code', 'warn');
                        return;
                    }
                    this._feedEvent('SYS', '--', `Auto-loaded ${created} engine tab(s)`, 'info');
                } else {
                    this._feedEvent('SYS', '--', 'No engine tabs with code', 'warn');
                    return;
                }
            }

            if (typeof liveExec._saveCurrentTabCode === 'function') {
                liveExec._saveCurrentTabCode();
            }

            const tabs = Array.from(liveExec.engineTabs.values()).filter(t => t.code.trim());
            if (tabs.length === 0) {
                this._feedEvent('SYS', '--', 'All engine tabs are empty', 'warn');
                return;
            }

            this._feedEvent('SYS', '--', `--- Cycle #${this.cycleCount} (${tabs.length} engine${tabs.length > 1 ? 's' : ''}, legacy mode) ---`, 'meta');

            // Mark all executing tabs in the matrix
            for (const t of tabs) {
                const letter = (t.engine_letter || '').toLowerCase();
                this._setCellStatus(letter + '1', S.EXECUTING, t.language, t.label);
            }

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
                        const tag  = (r.language || r.engine_letter || '?').toUpperCase();
                        const letter = (r.engine_letter || '').toLowerCase();
                        const addr = letter + (r.slot || '1');

                        if (r.skipped) {
                            this._feedEvent(tag, addr.toUpperCase(), `SKIP: ${r.skip_reason}`, 'meta');
                            this._setCellStatus(addr, S.COMMITTED, r.language, r.label);
                        } else {
                            const ok = r.success && !r.error;
                            if (r.output) this._feedEvent(tag, addr.toUpperCase(), r.output.trim(), ok ? 'output' : 'error');
                            if (r.error)  this._feedEvent(tag, addr.toUpperCase(), r.error, 'error');
                            if (ok) { passed++; this._setCellStatus(addr, S.PASSED, r.language, r.label); }
                            else    { failed++; this._setCellStatus(addr, S.FAILED, r.language, r.label); }
                        }
                    }

                    const s = data.summary || {};
                    const total = (s.passed || passed) + (s.failed || failed);
                    const pct = total > 0 ? Math.round(((s.passed || passed) / total) * 100) : 0;
                    this.elPassRate.textContent = `${pct}%`;
                    this.elLastRun.textContent = new Date().toLocaleTimeString('en-US', { hour12: false });
                    this.elEngineCount.textContent = tabs.length;

                    this._history.push({
                        time: Date.now(),
                        passed: s.passed || passed,
                        failed: s.failed || failed,
                        ms: Math.round((s.total_time || 0) * 1000),
                    });
                    if (this._history.length > this._maxHistory) this._history = this._history.slice(-this._maxHistory);

                    this._feedEvent('SYS', '--', `${s.passed || passed}/${total} passed, ${Math.round((s.total_time || 0) * 1000)}ms`, 'info');
                } else {
                    this._feedEvent('SYS', '--', `Error: ${data.error || 'Unknown'}`, 'error');
                }
            } catch (e) {
                this._feedEvent('SYS', '--', `Network error: ${e.message}`, 'error');
            }

            this._refreshRuntimeMatrix();
        }

        /* ── Runtime backend commands ── */
        async _postRuntimeCommand(action) {
            try {
                await fetch('/api/runtime/control', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action, interval: this.intervalSec })
                });
            } catch (_) { /* non-critical */ }
        }

        /* ──────────────────────────────────────────
           SOCKETIO HANDLERS
           ────────────────────────────────────────── */
        _onCycleResult(data) {
            if (data.results) {
                for (const r of data.results) {
                    const tag = (r.language || '?').toUpperCase();
                    if (r.output) this._feedEvent(tag, '--', r.output.trim(), 'output');
                    if (r.error)  this._feedEvent(tag, '--', r.error, 'error');
                }
            }
        }

        _onStatusUpdate(data) {
            if (data.state === 'running')  this.elRunState.textContent = 'running';
            if (data.state === 'paused')   this.elRunState.textContent = 'paused';
            if (data.state === 'stopped')  this.elRunState.textContent = 'idle';
        }

        _onRuntimeError(data) {
            this._feedEvent('ERR', '--', `Runtime error: ${data.error || 'unknown'}`, 'error');
        }

        /* ──────────────────────────────────────────
           LIVE EVENT FEED
           ────────────────────────────────────────── */
        /**
         * @param {string} engine  - Engine tag (e.g. 'PYTHON', 'SYS')
         * @param {string} addr    - Slot address (e.g. 'A1', '--')
         * @param {string} text    - Event message
         * @param {string} type    - 'info'|'output'|'error'|'warn'|'meta'
         */
        _feedEvent(engine, addr, text, type = 'info') {
            if (!this.logEl) return;

            const line = document.createElement('div');
            line.className = `rt-feed-line rt-feed-line--${type}`;

            const ts = new Date().toLocaleTimeString('en-US', {
                hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit'
            });

            line.innerHTML =
                `<span class="rt-feed-ts">${ts}</span>` +
                `<span class="rt-feed-addr" data-addr="${this._esc(addr)}">${this._esc(addr)}</span>` +
                `<span class="rt-feed-eng">${this._esc(engine)}</span>` +
                `<span class="rt-feed-msg">${this._esc(text)}</span>`;

            this.logEl.appendChild(line);
            this.logEl.scrollTop = this.logEl.scrollHeight;

            // Trim old entries
            while (this.logEl.children.length > 600) {
                this.logEl.removeChild(this.logEl.firstChild);
            }

            if (this.feedCount) {
                this.feedCount.textContent = this.logEl.children.length;
            }
        }

        _clearLog() {
            if (this.logEl) this.logEl.innerHTML = '';
            this._feedEvent('SYS', '--', 'Feed cleared', 'meta');
        }

        /* ── API Docs ── */
        _toggleDocs(forceState) {
            if (!this.docsCard) return;
            const show = forceState !== undefined ? forceState : this.docsCard.style.display === 'none';
            if (show) {
                if (!this.isOpen) this.open();
                if (!this.docsIframe.src || this.docsIframe.src === 'about:blank') {
                    this.docsIframe.src = `${location.origin}/api/docs`;
                }
                this.docsCard.style.display = '';
                this.dashboard.style.display = 'none';
                if (this.meshCard) this.meshCard.style.display = 'none';
                this.btnDocs?.classList.add('active');
                this.btnMesh?.classList.remove('active');
            } else {
                this.docsCard.style.display = 'none';
                this.dashboard.style.display = '';
                this.btnDocs?.classList.remove('active');
            }
        }

        /* ── Mesh Topology ── */
        _toggleMesh(forceState) {
            if (!this.meshCard) return;
            const show = forceState !== undefined ? forceState : this.meshCard.style.display === 'none';
            if (show) {
                if (!this.isOpen) this.open();
                this.meshCard.style.display = '';
                this.dashboard.style.display = 'none';
                if (this.docsCard) this.docsCard.style.display = 'none';
                this.btnMesh?.classList.add('active');
                this.btnDocs?.classList.remove('active');
                this._refreshMeshTopology();
            } else {
                this.meshCard.style.display = 'none';
                this.dashboard.style.display = '';
                this.btnMesh?.classList.remove('active');
            }
        }

        async _refreshMeshTopology() {
            try {
                const resp = await fetch('/api/mesh/topology?include_remote=true');
                const data = await resp.json();
                if (!data.success) return;

                this._renderMeshLocal(data);
                this._renderMeshFabric(data);
                this._renderMeshPeers(data);

                // Update instance badge
                if (this.meshBadge) {
                    this.meshBadge.textContent = `${data.instance_name || data.instance_id}`;
                    this.meshBadge.title = `Instance: ${data.instance_id}`;
                }

                // Update activate button
                if (this.btnActivate) {
                    const isActive = data.mesh_active;
                    this.btnActivate.innerHTML = isActive
                        ? '<i data-lucide="power-off"></i> Deactivate'
                        : '<i data-lucide="power"></i> Activate';
                    if (typeof lucide !== 'undefined') lucide.createIcons({ root: this.btnActivate });
                }
            } catch (e) {
                console.warn('Mesh topology refresh failed:', e);
            }
        }

        _renderMeshLocal(data) {
            if (!this.meshLocal) return;
            const local = data.local || {};
            const fabric = data.fabric || {};
            const engines = local.engines || {};

            // Build local instance view with all engines and slots visible
            let html = `<div class="mesh-section-title">
                <i data-lucide="server"></i> LOCAL: ${data.instance_name || data.instance_id}
                <span class="mesh-stat">${local.occupied || 0}/${local.capacity || 0} slots</span>
            </div>`;

            // Mini matrix — show all engines with slot addresses
            html += '<div class="mesh-mini-matrix">';
            const NAMES = window.ENGINE_NAMES || { a:'Python', b:'JavaScript', c:'TypeScript', d:'Rust', e:'Java', f:'Swift', g:'C++', h:'R', i:'Go', j:'Ruby', k:'C#', l:'Kotlin', m:'C', n:'Bash', o:'Perl' };

            for (const [ename, edata] of Object.entries(engines)) {
                const letter = edata.letter || '?';
                const lang = edata.language || '?';
                const maxS = edata.max_slots || 16;
                const occ = edata.occupied || 0;
                const relayOut = edata.relay_out || 0;
                const relayIn = edata.relay_in || 0;

                // Determine row segments
                let userEnd = maxS;
                let segments = '';

                if (letter === 'a') {
                    // Python: show user/outbound/inbound zones
                    userEnd = 32;
                    segments = `<span class="mesh-zone mesh-zone--user">a1-a32 user</span>`;
                    if (relayOut > 0 || data.mesh_active) {
                        segments += `<span class="mesh-zone mesh-zone--out">a33-a48 OUT</span>`;
                    }
                    if (relayIn > 0 || data.mesh_active) {
                        segments += `<span class="mesh-zone mesh-zone--in">a49-a64 IN</span>`;
                    }
                }

                html += `<div class="mesh-engine-row" data-engine="${letter}">
                    <span class="mesh-engine-label" title="${lang}">${letter.toUpperCase()} ${NAMES[letter] || lang}</span>
                    <span class="mesh-engine-fill">${occ}/${maxS}</span>
                    ${segments}
                </div>`;
            }
            html += '</div>';

            this.meshLocal.innerHTML = html;
            if (typeof lucide !== 'undefined') lucide.createIcons({ root: this.meshLocal });
        }

        _renderMeshFabric(data) {
            if (!this.meshFabric) return;
            const fabric = data.fabric || {};
            const subs = data.subscriptions || {};
            const peers = data.peers || [];

            if (peers.length === 0) {
                this.meshFabric.innerHTML = `<div class="mesh-section-title">
                    <i data-lucide="radio-tower"></i> FABRIC
                    <span class="mesh-stat">No peers registered</span>
                </div>
                <div class="mesh-empty">Add peers to build the distributed mesh.<br>
                Python slots ${fabric.outbound_range || 'a33-a48'} = outbound relay<br>
                Python slots ${fabric.inbound_range || 'a49-a64'} = inbound relay</div>`;
                if (typeof lucide !== 'undefined') lucide.createIcons({ root: this.meshFabric });
                return;
            }

            let html = `<div class="mesh-section-title">
                <i data-lucide="radio-tower"></i> FABRIC
                <span class="mesh-stat">${peers.length} peer(s) | ${Object.keys(subs).length} subscription(s)</span>
            </div>`;

            // Draw connections
            html += '<div class="mesh-connections">';
            for (const peer of peers) {
                const alive = peer.is_alive;
                const dot = alive ? 'mesh-dot--alive' : 'mesh-dot--dead';
                html += `<div class="mesh-connection ${alive ? '' : 'mesh-connection--dead'}">
                    <span class="mesh-dot ${dot}"></span>
                    <span class="mesh-conn-label">${peer.peer_id}</span>
                    <span class="mesh-conn-url">${peer.url}</span>
                    <span class="mesh-conn-lanes">
                        <span class="mesh-lane mesh-lane--out" title="Outbound">${peer.outbound_lane} &rarr;</span>
                        <span class="mesh-lane mesh-lane--in" title="Inbound">&larr; ${peer.inbound_lane}</span>
                    </span>
                    <span class="mesh-conn-latency">${alive ? peer.latency_ms + 'ms' : 'offline'}</span>
                    <span class="mesh-conn-slots">${peer.slot_count || '?'} slots</span>
                </div>`;
            }
            html += '</div>';

            // Subscriptions
            if (Object.keys(subs).length > 0) {
                html += '<div class="mesh-subs-title">Relay Subscriptions</div>';
                html += '<div class="mesh-subs">';
                for (const [addr, peerIds] of Object.entries(subs)) {
                    html += `<div class="mesh-sub">${addr} &rarr; ${peerIds.join(', ')}</div>`;
                }
                html += '</div>';
            }

            this.meshFabric.innerHTML = html;
            if (typeof lucide !== 'undefined') lucide.createIcons({ root: this.meshFabric });
        }

        _renderMeshPeers(data) {
            if (!this.meshPeers) return;
            const remoteMatrices = data.remote_matrices || {};
            const peers = data.peers || [];

            if (peers.length === 0) {
                this.meshPeers.innerHTML = '';
                return;
            }

            let html = `<div class="mesh-section-title">
                <i data-lucide="globe"></i> REMOTE INSTANCES
                <span class="mesh-stat">${Object.keys(remoteMatrices).length} reachable</span>
            </div>`;

            for (const peer of peers) {
                const remote = remoteMatrices[peer.peer_id];
                const alive = peer.is_alive;

                html += `<div class="mesh-remote-instance ${alive ? '' : 'mesh-remote--dead'}">
                    <div class="mesh-remote-header">
                        <span class="mesh-dot ${alive ? 'mesh-dot--alive' : 'mesh-dot--dead'}"></span>
                        <strong>${peer.peer_id}</strong>
                        <span class="mesh-remote-id">${peer.instance_id || '?'}</span>
                    </div>`;

                if (remote && remote.engines) {
                    const engines = remote.engines;
                    html += '<div class="mesh-remote-matrix">';
                    for (const [ename, edata] of Object.entries(engines)) {
                        const letter = edata.letter || '?';
                        const slots = edata.slots || {};
                        const occ = Object.values(slots).filter(v => v !== null).length;
                        const max = edata.max_slots || 16;
                        if (occ > 0) {
                            html += `<span class="mesh-remote-eng" title="${ename}: ${occ}/${max}">${letter.toUpperCase()}:${occ}</span>`;
                        }
                    }
                    html += '</div>';
                } else if (alive) {
                    html += '<div class="mesh-remote-matrix"><span class="mesh-remote-eng">fetching...</span></div>';
                } else {
                    html += '<div class="mesh-remote-matrix"><span class="mesh-remote-eng mesh-remote-eng--dead">unreachable</span></div>';
                }

                html += '</div>';
            }

            this.meshPeers.innerHTML = html;
            if (typeof lucide !== 'undefined') lucide.createIcons({ root: this.meshPeers });
        }

        async _promptAddPeer() {
            const peerId = prompt('Peer ID (e.g., node-2):');
            if (!peerId) return;
            const url = prompt('Peer URL (e.g., http://192.168.1.102:5002):');
            if (!url) return;

            try {
                const resp = await fetch('/api/mesh/peers', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ peer_id: peerId, url: url }),
                });
                const data = await resp.json();
                if (data.success) {
                    this._feedEvent('MESH', '--', `Peer ${peerId} added (${url})`, 'meta');
                    this._refreshMeshTopology();
                } else {
                    alert('Failed to add peer: ' + (data.error || 'unknown'));
                }
            } catch (e) {
                alert('Error: ' + e.message);
            }
        }

        async _toggleMeshActivation() {
            try {
                // Check current status
                const statusResp = await fetch('/api/mesh/status');
                const statusData = await statusResp.json();
                const isActive = statusData.mesh_active;

                const endpoint = isActive ? '/api/mesh/deactivate' : '/api/mesh/activate';
                const resp = await fetch(endpoint, { method: 'POST' });
                const data = await resp.json();

                if (data.success !== false) {
                    const action = isActive ? 'deactivated' : 'activated';
                    this._feedEvent('MESH', '--', `Mesh ${action}`, 'meta');
                    this._refreshMeshTopology();
                }
            } catch (e) {
                console.warn('Mesh activation toggle failed:', e);
            }
        }

        /* ── Uptime clock ── */
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
            if (h > 0) return `${h}h${m % 60}m`;
            if (m > 0) return `${m}m${s % 60}s`;
            return `${s}s`;
        }

        /* ──────────────────────────────────────────
           REGISTRY MATRIX  —  Rich Interactive Grid
           ────────────────────────────────────────── */
        _buildRuntimeMatrix() {
            if (!this.matrixBody) return;

            const NAMES   = window.ENGINE_NAMES  || { a:'Python', b:'JavaScript', c:'TypeScript', d:'Rust', e:'Java', f:'Swift', g:'C++', h:'R', i:'Go', j:'Ruby', k:'C#', l:'Kotlin', m:'C', n:'Bash', o:'Perl' };
            const LETTERS = window.ENGINE_LETTERS || Object.keys(NAMES);
            const SLOTS   = window.ENGINE_SLOTS   || { a:64, b:16, c:16, d:16, e:16, f:16, g:16, h:16, i:16, j:16, k:16, l:16, m:16, n:16, o:16 };
            const MAX_COLS = 16;

            let html = '';

            for (const letter of LETTERS) {
                const totalSlots = SLOTS[letter] || 16;
                const subRows = Math.ceil(totalSlots / MAX_COLS);

                for (let sr = 0; sr < subRows; sr++) {
                    const startSlot = sr * MAX_COLS + 1;
                    const endSlot   = Math.min((sr + 1) * MAX_COLS, totalSlots);

                    html += `<div class="mc-row" id="rt-matrix-row-${letter}-${sr}">`;
                    html += `<span class="mc-engine" data-engine="${letter}" title="${NAMES[letter]}${subRows > 1 ? ' [' + startSlot + '-' + endSlot + ']' : ''}">${NAMES[letter] || letter}</span>`;
                    html += '<div class="mc-slots">';
                    for (let s = startSlot; s <= startSlot + MAX_COLS - 1; s++) {
                        if (s > totalSlots) {
                            html += '<div class="mc-cell mc-cell--disabled"></div>';
                        } else {
                            const addr = `${letter}${s}`;
                            html += `<div class="mc-cell mc-cell--empty" id="rt-mcell-${addr}" data-addr="${addr}">` +
                                    `<div class="mc-cell__inner"></div>` +
                                    `<div class="mc-cell__pulse"></div>` +
                                    `<div class="mc-cell__label"></div>` +
                                    `</div>`;
                        }
                    }
                    html += '</div>';
                    html += `<span class="mc-row-agg" id="rt-row-agg-${letter}-${sr}"></span>`;
                    html += '</div>';
                }
            }

            this.matrixBody.innerHTML = html;
            this._bindMatrixInteractions();
        }

        /** Per-cell status */
        _setCellStatus(addr, status, language, label) {
            addr = addr.toLowerCase();
            this._slotStatus[addr] = { status, language: language || '', label: label || '', ts: Date.now() };

            const cell = document.getElementById(`rt-mcell-${addr}`);
            if (!cell) return;

            cell.className = 'mc-cell mc-cell--' + status;

            const lbl = cell.querySelector('.mc-cell__label');
            if (lbl) {
                lbl.textContent = (label || '').slice(0, 6);
                lbl.title = label || '';
            }
        }

        /** Interactive: click = info, dblclick = lock, long-press = evict */
        _bindMatrixInteractions() {
            if (!this.matrixBody) return;

            let longPressTimer = null;
            let longPressAddr  = null;
            const LONG_PRESS_MS = 800;

            this.matrixBody.addEventListener('pointerdown', (e) => {
                const cell = e.target.closest('.mc-cell[data-addr]');
                if (!cell || cell.classList.contains('mc-cell--empty') || cell.classList.contains('mc-cell--disabled')) return;
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

            this.matrixBody.addEventListener('click', (e) => {
                const cell = e.target.closest('.mc-cell[data-addr]');
                if (!cell || cell.classList.contains('mc-cell--empty') || cell.classList.contains('mc-cell--disabled')) return;
                if (longPressAddr !== null) {
                    this._showSlotOverlay(cell.dataset.addr, cell);
                }
            });

            this.matrixBody.addEventListener('dblclick', (e) => {
                const cell = e.target.closest('.mc-cell[data-addr]');
                if (!cell || cell.classList.contains('mc-cell--empty') || cell.classList.contains('mc-cell--disabled')) return;
                e.preventDefault();
                this._toggleSlotLock(cell.dataset.addr);
            });
        }

        /** Refresh matrix from enriched API */
        async _refreshRuntimeMatrix() {
            try {
                const resp = await fetch('/api/registry/matrix/enriched');
                const data = await resp.json();
                if (!data.success) return;

                const SLOTS = window.ENGINE_SLOTS || { a:64, b:16, c:16, d:16, e:16, f:16, g:16, h:16,
                                i:16, j:16, k:16, l:16, m:16, n:16, o:16 };
                let committed = 0, locked = 0, executing = 0, passed = 0, failed = 0, total = 0;

                const engines = data.engines || {};
                for (const engineName of Object.keys(engines)) {
                    const row = engines[engineName];
                    const letter = row.letter;
                    const engineMaxSlots = row.max_slots || SLOTS[letter] || 16;
                    let rowPassed = 0, rowFailed = 0, rowTotal = 0;

                    for (let s = 1; s <= engineMaxSlots; s++) {
                        const addr = `${letter}${s}`;
                        const cell = document.getElementById(`rt-mcell-${addr}`);
                        if (!cell) continue;

                        const slotData = row.slots?.[String(s)];

                        if (!slotData || !slotData.node_id) {
                            const local = this._slotStatus[addr];
                            if (local && (Date.now() - local.ts) < 30000) {
                                this._setCellStatus(addr, local.status, local.language, local.label);
                            } else {
                                cell.className = 'mc-cell mc-cell--empty';
                                const lbl = cell.querySelector('.mc-cell__label');
                                if (lbl) { lbl.textContent = ''; lbl.title = ''; }
                            }
                            continue;
                        }

                        total++; rowTotal++;
                        const prov = slotData.provenance || {};
                        const isLocked = slotData.locked;
                        const origin = prov.origin || 'live-exec';

                        // Determine status from local tracking or server state
                        const local = this._slotStatus[addr];
                        let status;
                        if (local && local.status === S.EXECUTING) {
                            status = S.EXECUTING; executing++;
                        } else if (local && local.status === S.PASSED && (Date.now() - local.ts) < 10000) {
                            status = S.PASSED; passed++; rowPassed++;
                        } else if (local && local.status === S.FAILED && (Date.now() - local.ts) < 15000) {
                            status = S.FAILED; failed++; rowFailed++;
                        } else if (isLocked) {
                            status = S.LOCKED; locked++;
                        } else if (slotData.needs_swap) {
                            status = S.HOT_SWAP;
                        } else {
                            status = S.COMMITTED; committed++;
                        }

                        cell.className = 'mc-cell mc-cell--' + status;
                        if (origin === 'api')        cell.classList.add('mc-origin-api');
                        else if (origin === 'canvas') cell.classList.add('mc-origin-canvas');
                        else                         cell.classList.add('mc-origin-live');
                        cell.classList.add('mc-cell--occupied');

                        // Tooltip
                        const ttlStr = prov.ttl_remaining > 0
                            ? `TTL ${Math.round(prov.ttl_remaining)}s`
                            : (prov.expired ? 'EXPIRED' : '');
                        cell.title = [
                            addr.toUpperCase(),
                            slotData.label || prov.submitter || '',
                            origin === 'api' ? 'API' : 'HUMAN',
                            ttlStr,
                            isLocked ? 'LOCKED' : '',
                            status.toUpperCase(),
                        ].filter(Boolean).join(' | ');

                        cell.dataset.origin = origin;
                        cell.dataset.locked = isLocked ? '1' : '0';

                        const lbl = cell.querySelector('.mc-cell__label');
                        if (lbl) {
                            lbl.textContent = (slotData.label || '').slice(0, 6);
                            lbl.title = slotData.label || '';
                        }
                    }

                    // Row aggregate
                    const MAX_COLS = 16;
                    const subRows = Math.ceil(engineMaxSlots / MAX_COLS);
                    for (let sr = 0; sr < subRows; sr++) {
                        const rowEl = document.getElementById(`rt-matrix-row-${letter}-${sr}`);
                        rowEl?.classList.toggle('mc-row--active', rowTotal > 0);

                        const aggEl = document.getElementById(`rt-row-agg-${letter}-${sr}`);
                        if (aggEl && sr === 0) {
                            if (rowTotal > 0) {
                                aggEl.textContent = `${rowTotal}`;
                                aggEl.className = 'mc-row-agg';
                                if (rowFailed > 0)      aggEl.classList.add('mc-row-agg--fail');
                                else if (rowPassed > 0) aggEl.classList.add('mc-row-agg--pass');
                                else                    aggEl.classList.add('mc-row-agg--ok');
                            } else {
                                aggEl.textContent = '';
                                aggEl.className = 'mc-row-agg';
                            }
                        }
                    }
                }

                // Staging pipeline in-flight entries
                const inFlight = data.in_flight || [];
                for (const ifr of inFlight) {
                    const addr = ifr.reserved_address;
                    const cell = document.getElementById(`rt-mcell-${addr}`);
                    if (!cell) continue;
                    const phaseClass = {
                        'queued': S.STAGED,
                        'speculating': S.SPECULATING,
                        'promoting': S.PROMOTING,
                        'passed': S.SPECULATING,
                    }[ifr.phase] || S.STAGED;
                    cell.className = `mc-cell mc-cell--${phaseClass}`;
                    cell.title = `${(addr || '').toUpperCase()} | ${ifr.label} | ${(ifr.phase || '').toUpperCase()}`;
                }

                // Stats summary
                if (this.matrixStats) {
                    this.matrixStats.textContent = [
                        `${total} slots`,
                        committed > 0 ? `${committed} ok` : '',
                        passed > 0 ? `${passed} passed` : '',
                        failed > 0 ? `${failed} failed` : '',
                        executing > 0 ? `${executing} running` : '',
                        locked > 0 ? `${locked} locked` : '',
                    ].filter(Boolean).join(' / ');
                }
            } catch (e) {
                console.error('[RuntimePanel] _refreshRuntimeMatrix failed', e);
            }
        }

        /* ──────────────────────────────────────────
           SLOT INFO OVERLAY
           ────────────────────────────────────────── */
        async _showSlotOverlay(addr, anchorEl) {
            this._closeSlotOverlay();

            try {
                const resp = await fetch(`/api/registry/slot/${addr}/info`);
                const info = await resp.json();
                if (!info.success || !info.occupied) return;

                const prov = info.provenance || {};
                const stg  = info.staging || {};
                const ledg = info.ledger || {};
                const origin = info.origin || prov.origin || 'live-exec';
                const isLocked = info.locked;
                const NAMES = window.ENGINE_NAMES || {};
                const engineLang = stg.language || ledg.language || NAMES[addr[0]] || info.engine || '';

                const rect = anchorEl.getBoundingClientRect();
                const overlayX = Math.min(rect.left, window.innerWidth - 360);
                const overlayY = Math.max(8, rect.top - 260);

                const scrim = document.createElement('div');
                scrim.className = 'slot-info-scrim';
                scrim.addEventListener('click', () => this._closeSlotOverlay());
                document.body.appendChild(scrim);

                const el = document.createElement('div');
                el.className = 'slot-info-overlay';
                el.id = 'slot-info-overlay';
                el.style.left = `${overlayX}px`;
                el.style.top  = `${overlayY}px`;

                const originLabel = origin === 'api' ? 'API AGENT' : (origin === 'canvas' ? 'CANVAS' : 'HUMAN');
                const badgeClass  = origin === 'api' ? 'api' : (origin === 'canvas' ? 'canvas' : 'live');
                const codeStr     = stg.code || ledg.source_code || stg.code_preview || '';
                const label       = stg.label || ledg.display_name || info.node_id?.slice(0, 16) || addr.toUpperCase();

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
                                <span class="slot-info-overlay__label">Agent</span>
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
                        </div>
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

        /* ── Slot lock toggle ── */
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
                    this._feedEvent('SYS', addr.toUpperCase(), isLocked ? 'Slot unlocked' : 'Slot locked', 'info');
                    this._refreshRuntimeMatrix();
                }
            } catch (e) {
                this._feedEvent('ERR', addr.toUpperCase(), `Lock toggle failed: ${e.message}`, 'error');
            }
        }

        /* ── Slot eviction ── */
        _showEvictConfirm(addr) {
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

            dlg.querySelector('#evict-cancel').addEventListener('click', () => { dlg.remove(); scrim.remove(); });
            scrim.addEventListener('click', () => { dlg.remove(); scrim.remove(); });
            dlg.querySelector('#evict-confirm').addEventListener('click', async () => {
                dlg.remove(); scrim.remove();
                await this._evictSlot(addr);
            });
        }

        async _evictSlot(addr) {
            try {
                const resp = await fetch(`/api/registry/slot/${addr}/evict`, { method: 'DELETE' });
                const data = await resp.json();
                if (data.success) {
                    this._feedEvent('SYS', addr.toUpperCase(), `Evicted: ${data.evicted_node}`, 'warn');
                    delete this._slotStatus[addr.toLowerCase()];
                    setTimeout(() => this._refreshRuntimeMatrix(), 300);
                } else {
                    this._feedEvent('ERR', addr.toUpperCase(), `Evict failed: ${data.error}`, 'error');
                }
            } catch (e) {
                this._feedEvent('ERR', addr.toUpperCase(), `Evict error: ${e.message}`, 'error');
            }
        }

        /* ──────────────────────────────────────────
           SNIPPET LIFECYCLE SOCKETIO
           ────────────────────────────────────────── */
        _bindSnippetLifecycleEvents() {
            if (!this._socket) return;

            this._socket.on('snippet_lifecycle', (data) => {
                const ev   = data.event;
                const addr = data.address;

                if (ev === 'submitted') {
                    const src = data.origin === 'api' ? 'API' : 'USR';
                    this._feedEvent(
                        (data.language || '?').toUpperCase(),
                        (addr || '??').toUpperCase(),
                        `[${src}] ${data.submitter || 'Unknown'} -> ${data.label || ''} (${data.phase})`,
                        'info'
                    );
                    if (addr) {
                        this._setCellStatus(addr, S.STAGED, data.language, data.label);
                        setTimeout(() => this._setCellStatus(addr, S.SPECULATING, data.language, data.label), 400);
                        setTimeout(() => {
                            const final = data.phase === 'promoted' ? S.PASSED : S.FAILED;
                            this._setCellStatus(addr, final, data.language, data.label);
                        }, 1200);
                    }
                    this._refreshRuntimeMatrix();
                } else if (ev === 'locked') {
                    this._feedEvent('SYS', (addr || '').toUpperCase(), 'Slot locked', 'meta');
                    this._refreshRuntimeMatrix();
                } else if (ev === 'unlocked') {
                    this._feedEvent('SYS', (addr || '').toUpperCase(), 'Slot unlocked', 'meta');
                    this._refreshRuntimeMatrix();
                } else if (ev === 'evicted') {
                    this._feedEvent('SYS', (addr || '').toUpperCase(), 'Slot evicted', 'warn');
                    this._refreshRuntimeMatrix();
                }
            });
        }

        /* ── Helper ── */
        _esc(s) {
            const d = document.createElement('div');
            d.textContent = s || '';
            return d.innerHTML;
        }
    }

    /* ──────────────────────────────────────────
       BOOTSTRAP
       ────────────────────────────────────────── */
    document.addEventListener('DOMContentLoaded', () => {
        window.runtimePanel = new RuntimePanel();
    });
})();