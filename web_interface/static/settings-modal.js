/**
 * Settings Hub — Unified settings modal for SpokedPy.
 *
 * Provides a tabbed modal accessed from the status-bar gear icon:
 *   • Settings    — all configurable values grouped by category
 *   • AI Config   — endpoint, API key, model, system prompt
 *   • Logs        — searchable/filterable application log viewer
 *   • Tests       — discover and run test suites, view past results
 *   • History     — chronological feed of settings/test/log changes
 *
 * All data is persisted via /api/hub/* endpoints and stored in SQLite.
 */

class SettingsHub {
    constructor() {
        this.activeTab = 'settings';
        this.settings = {};
        this.groups = [];
        this.logPollTimer = null;
        this._inject();
        this._bind();
    }

    /* ================================================================
       DOM INJECTION
       ================================================================ */

    _inject() {
        // ── Replace the "Connected" label with gear icon ──────────
        const statusLeft = document.querySelector('.status-left');
        if (statusLeft) {
            const connSpan = document.getElementById('connection-status');
            if (connSpan) {
                // Keep connection dot but replace text with gear button
                connSpan.innerHTML = `
                    <span id="conn-indicator" class="conn-indicator conn-indicator--ok" title="Connected">
                        <i data-lucide="wifi"></i>
                    </span>`;
            }
            // Insert gear button right after connection indicator
            const gear = document.createElement('button');
            gear.id = 'settings-hub-btn';
            gear.className = 'status-item settings-hub-btn';
            gear.title = 'Settings & System Hub';
            gear.innerHTML = '<i data-lucide="settings"></i> <span class="settings-hub-label">Settings</span>';
            statusLeft.insertBefore(gear, statusLeft.children[1] || null);
        }

        // ── Inject the modal markup ──────────────────────────────
        const modal = document.createElement('div');
        modal.id = 'settings-hub-modal';
        modal.className = 'modal settings-hub-modal';
        modal.style.display = 'none';
        modal.innerHTML = this._modalHTML();
        document.body.appendChild(modal);

        // Cache references
        this.modal = modal;
        this.backdrop = modal.querySelector('.modal-backdrop');
        this.tabBtns = modal.querySelectorAll('.shub-tab-btn');
        this.tabPanels = modal.querySelectorAll('.shub-panel');
        this.closeBtn = modal.querySelector('.modal-close');
        this.gearBtn = document.getElementById('settings-hub-btn');
        this.saveBtn = modal.querySelector('#shub-save-btn');
        this.revertAllBtn = modal.querySelector('#shub-revert-btn');

        // Logs panel references
        this.logBody = modal.querySelector('#shub-log-body');
        this.logLevelFilter = modal.querySelector('#shub-log-level');
        this.logSourceFilter = modal.querySelector('#shub-log-source');
        this.logRefreshBtn = modal.querySelector('#shub-log-refresh');
        this.logClearBtn = modal.querySelector('#shub-log-clear');

        // Tests panel references
        this.testFileList = modal.querySelector('#shub-test-files');
        this.testRunBtn = modal.querySelector('#shub-test-run');
        this.testRunAllBtn = modal.querySelector('#shub-test-run-all');
        this.testOutput = modal.querySelector('#shub-test-output');
        this.testHistory = modal.querySelector('#shub-test-history');

        // History panel
        this.historyBody = modal.querySelector('#shub-history-body');
        this.historyCatFilter = modal.querySelector('#shub-history-cat');

        // Re-render Lucide icons
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }

    _modalHTML() {
        return `
        <div class="modal-backdrop"></div>
        <div class="modal-content shub-content">
            <div class="modal-header">
                <h2><i data-lucide="settings"></i> System Hub</h2>
                <button class="modal-close"><i data-lucide="x"></i></button>
            </div>

            <!-- Tab bar -->
            <div class="shub-tabs">
                <button class="shub-tab-btn active" data-tab="settings">
                    <i data-lucide="sliders-horizontal"></i> Settings
                </button>
                <button class="shub-tab-btn" data-tab="ai">
                    <i data-lucide="bot"></i> AI Config
                </button>
                <button class="shub-tab-btn" data-tab="logs">
                    <i data-lucide="scroll-text"></i> Logs
                </button>
                <button class="shub-tab-btn" data-tab="tests">
                    <i data-lucide="test-tubes"></i> Tests
                </button>
                <button class="shub-tab-btn" data-tab="history">
                    <i data-lucide="history"></i> History
                </button>
            </div>

            <div class="modal-body shub-body">
                <!-- ═══ SETTINGS PANEL ═══ -->
                <div class="shub-panel active" data-panel="settings" id="shub-panel-settings">
                    <div class="shub-settings-grid" id="shub-settings-grid">
                        <div class="shub-loading">Loading settings…</div>
                    </div>
                </div>

                <!-- ═══ AI CONFIG PANEL ═══ -->
                <div class="shub-panel" data-panel="ai" id="shub-panel-ai">
                    <div class="shub-ai-grid" id="shub-ai-grid">
                        <div class="shub-loading">Loading AI config…</div>
                    </div>
                </div>

                <!-- ═══ LOGS PANEL ═══ -->
                <div class="shub-panel" data-panel="logs" id="shub-panel-logs">
                    <div class="shub-log-toolbar">
                        <select id="shub-log-level" class="shub-select">
                            <option value="">All Levels</option>
                            <option value="debug">Debug</option>
                            <option value="info">Info</option>
                            <option value="warn">Warn</option>
                            <option value="error">Error</option>
                        </select>
                        <select id="shub-log-source" class="shub-select">
                            <option value="">All Sources</option>
                            <option value="system">System</option>
                            <option value="settings">Settings</option>
                            <option value="tests">Tests</option>
                            <option value="ui">UI</option>
                            <option value="runtime">Runtime</option>
                        </select>
                        <button id="shub-log-refresh" class="btn btn-small shub-icon-btn" title="Refresh">
                            <i data-lucide="refresh-cw"></i>
                        </button>
                        <button id="shub-log-clear" class="btn btn-small shub-icon-btn shub-danger" title="Clear logs">
                            <i data-lucide="trash-2"></i>
                        </button>
                    </div>
                    <div class="shub-log-table-wrap">
                        <table class="shub-table">
                            <thead>
                                <tr>
                                    <th style="width:150px">Time</th>
                                    <th style="width:60px">Level</th>
                                    <th style="width:80px">Source</th>
                                    <th>Message</th>
                                </tr>
                            </thead>
                            <tbody id="shub-log-body"></tbody>
                        </table>
                    </div>
                </div>

                <!-- ═══ TESTS PANEL ═══ -->
                <div class="shub-panel" data-panel="tests" id="shub-panel-tests">
                    <div class="shub-test-toolbar">
                        <button id="shub-test-run-all" class="btn btn-primary btn-small">
                            <i data-lucide="play"></i> Run All Tests
                        </button>
                        <button id="shub-test-run" class="btn btn-secondary btn-small">
                            <i data-lucide="play-circle"></i> Run Selected
                        </button>
                    </div>
                    <div class="shub-test-split">
                        <div class="shub-test-left">
                            <h4>Test Files</h4>
                            <div id="shub-test-files" class="shub-test-files"></div>
                        </div>
                        <div class="shub-test-right">
                            <h4>Output</h4>
                            <pre id="shub-test-output" class="shub-test-output">Click "Run All Tests" or select files and click "Run Selected".</pre>
                            <h4 style="margin-top:12px">Past Runs</h4>
                            <div id="shub-test-history" class="shub-test-history"></div>
                        </div>
                    </div>
                </div>

                <!-- ═══ HISTORY PANEL ═══ -->
                <div class="shub-panel" data-panel="history" id="shub-panel-history">
                    <div class="shub-log-toolbar">
                        <select id="shub-history-cat" class="shub-select">
                            <option value="">All Categories</option>
                            <option value="settings">Settings</option>
                            <option value="tests">Tests</option>
                            <option value="logs">Logs</option>
                        </select>
                    </div>
                    <div class="shub-log-table-wrap">
                        <table class="shub-table">
                            <thead>
                                <tr>
                                    <th style="width:150px">Time</th>
                                    <th style="width:80px">Category</th>
                                    <th style="width:80px">Action</th>
                                    <th style="width:120px">Key</th>
                                    <th>Old → New</th>
                                </tr>
                            </thead>
                            <tbody id="shub-history-body"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Footer -->
            <div class="modal-footer shub-footer">
                <div class="shub-footer-left">
                    <span class="shub-server-info" id="shub-server-info"></span>
                </div>
                <div class="shub-footer-right">
                    <button id="shub-revert-btn" class="btn btn-secondary btn-small">
                        <i data-lucide="rotate-ccw"></i> Revert All
                    </button>
                    <button id="shub-save-btn" class="btn btn-primary btn-small">
                        <i data-lucide="save"></i> Save Changes
                    </button>
                </div>
            </div>
        </div>`;
    }

    /* ================================================================
       EVENT BINDING
       ================================================================ */

    _bind() {
        this.gearBtn?.addEventListener('click', () => this.open());
        this.closeBtn?.addEventListener('click', () => this.close());
        this.backdrop?.addEventListener('click', () => this.close());

        // Tabs
        this.tabBtns.forEach(btn => {
            btn.addEventListener('click', () => this._switchTab(btn.dataset.tab));
        });

        // Save / Revert
        this.saveBtn?.addEventListener('click', () => this._saveAll());
        this.revertAllBtn?.addEventListener('click', () => this._revertAll());

        // Logs
        this.logRefreshBtn?.addEventListener('click', () => this._loadLogs());
        this.logClearBtn?.addEventListener('click', () => this._clearLogs());
        this.logLevelFilter?.addEventListener('change', () => this._loadLogs());
        this.logSourceFilter?.addEventListener('change', () => this._loadLogs());

        // Tests
        this.testRunAllBtn?.addEventListener('click', () => this._runTests(false));
        this.testRunBtn?.addEventListener('click', () => this._runTests(true));

        // History
        this.historyCatFilter?.addEventListener('change', () => this._loadHistory());

        // Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.style.display !== 'none') {
                this.close();
            }
        });
    }

    /* ================================================================
       OPEN / CLOSE
       ================================================================ */

    open() {
        this.modal.style.display = 'flex';
        this._loadSettings();
        this._loadServerInfo();
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }

    close() {
        this.modal.style.display = 'none';
        if (this.logPollTimer) {
            clearInterval(this.logPollTimer);
            this.logPollTimer = null;
        }
    }

    /* ================================================================
       TAB SWITCHING
       ================================================================ */

    _switchTab(tab) {
        this.activeTab = tab;
        this.tabBtns.forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
        this.tabPanels.forEach(p => p.classList.toggle('active', p.dataset.panel === tab));

        // Lazy-load data for the activated tab
        if (tab === 'logs') this._loadLogs();
        if (tab === 'tests') { this._discoverTests(); this._loadTestHistory(); }
        if (tab === 'history') this._loadHistory();
        if (tab === 'ai') this._loadSettings(); // re-use; AI fields are in the same dataset
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }

    /* ================================================================
       SETTINGS
       ================================================================ */

    async _loadSettings() {
        try {
            const resp = await fetch('/api/hub/settings');
            const data = await resp.json();
            if (!data.success) throw new Error(data.error);
            this.settings = data.settings;
            this.groups = data.groups;
            this._renderSettings();
            this._renderAI();
        } catch (e) {
            console.error('Settings load failed:', e);
        }
    }

    _renderSettings() {
        const grid = this.modal.querySelector('#shub-settings-grid');
        const nonAI = this.groups.filter(g => g.key !== 'ai');

        let html = '';
        for (const group of nonAI) {
            const entries = Object.entries(this.settings).filter(([, v]) => v.group === group.key);
            if (!entries.length) continue;
            html += `<div class="shub-group">
                <h3 class="shub-group-title"><i data-lucide="${group.icon}"></i> ${group.label}</h3>`;
            for (const [key, meta] of entries) {
                html += this._renderField(key, meta);
            }
            html += `</div>`;
        }
        grid.innerHTML = html;
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }

    _renderAI() {
        const grid = this.modal.querySelector('#shub-ai-grid');
        const entries = Object.entries(this.settings).filter(([, v]) => v.group === 'ai');
        if (!entries.length) {
            grid.innerHTML = '<p class="shub-muted">No AI settings found.</p>';
            return;
        }
        let html = '<div class="shub-group"><h3 class="shub-group-title"><i data-lucide="bot"></i> AI Agent Configuration</h3>';
        for (const [key, meta] of entries) {
            html += this._renderField(key, meta);
        }
        html += '</div>';
        grid.innerHTML = html;
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }

    _renderField(key, meta) {
        const id = `shub-field-${key}`;
        const sourceClass = `shub-source--${meta.source}`;
        const sourceBadge = `<span class="shub-source ${sourceClass}">${meta.source}</span>`;
        const restartBadge = meta.restart ? '<span class="shub-badge shub-badge--restart">restart</span>' : '';
        const val = meta.value || '';

        let input = '';
        if (meta.type === 'textarea') {
            input = `<textarea id="${id}" class="shub-input shub-textarea" data-key="${key}"
                        placeholder="${meta.default || ''}">${this._esc(val)}</textarea>`;
        } else if (meta.type === 'secret') {
            input = `<input id="${id}" type="password" class="shub-input" data-key="${key}"
                        value="${this._esc(val)}" placeholder="••••••••"
                        autocomplete="off">
                     <button class="shub-eye-btn" data-target="${id}" title="Toggle visibility">
                        <i data-lucide="eye"></i>
                     </button>`;
        } else if (meta.type === 'boolean') {
            const checked = val === '1' || val === 'true' ? 'checked' : '';
            input = `<label class="shub-toggle">
                        <input id="${id}" type="checkbox" data-key="${key}" ${checked}>
                        <span class="shub-toggle-slider"></span>
                     </label>`;
        } else {
            const inputType = meta.type === 'number' ? 'number' : 'text';
            input = `<input id="${id}" type="${inputType}" class="shub-input" data-key="${key}"
                        value="${this._esc(val)}" placeholder="${this._esc(meta.default || '')}">`;
        }

        return `
            <div class="shub-field">
                <label class="shub-label" for="${id}">
                    ${meta.label} ${sourceBadge} ${restartBadge}
                </label>
                <div class="shub-input-row">${input}</div>
                <div class="shub-field-meta">
                    <span class="shub-muted">Key: <code>${key}</code></span>
                    <span class="shub-muted">Env: <code>${meta.env_value ? '<i data-lucide="check" style="width:12px;height:12px;display:inline;vertical-align:-1px;"></i> ' + meta.env_value : '—'}</code></span>
                    <span class="shub-muted">Default: <code>${this._esc(meta.default || '—')}</code></span>
                </div>
            </div>`;
    }

    async _saveAll() {
        const inputs = this.modal.querySelectorAll('[data-key]');
        const updates = {};
        let changed = 0;

        inputs.forEach(el => {
            const key = el.dataset.key;
            const meta = this.settings[key];
            let val;
            if (el.type === 'checkbox') {
                val = el.checked ? '1' : '0';
            } else {
                val = el.value;
            }
            // Only send if different from current effective value
            if (val !== (meta?.value || '')) {
                updates[key] = val;
                changed++;
            }
        });

        if (!changed) {
            this._toast('No changes to save', 'info');
            return;
        }

        try {
            const resp = await fetch('/api/hub/settings/bulk', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ updates }),
            });
            const data = await resp.json();
            if (!data.success) throw new Error(data.error || 'Save failed');

            // Sync AI settings to localStorage for ai-chat.js compatibility
            this._syncAIToLocalStorage(updates);

            const msg = data.restart_required
                ? `${changed} setting(s) saved. Some changes require a server restart.`
                : `${changed} setting(s) saved.`;
            this._toast(msg, data.restart_required ? 'warn' : 'success');
            this._loadSettings(); // refresh
        } catch (e) {
            this._toast(`Save failed: ${e.message}`, 'error');
        }
    }

    async _revertAll() {
        if (!confirm('Revert ALL database overrides? Settings will fall back to .env or defaults.')) return;
        const keys = Object.keys(this.settings).filter(k => this.settings[k].source === 'database');
        for (const key of keys) {
            await fetch(`/api/hub/settings/${key}`, { method: 'DELETE' });
        }
        this._toast(`Reverted ${keys.length} override(s)`, 'success');
        this._loadSettings();
    }

    _syncAIToLocalStorage(updates) {
        // Bridge: write AI settings into localStorage so ai-chat.js picks them up
        const mapping = {
            ai_endpoint: 'endpoint',
            ai_api_key: 'apiKey',
            ai_model: 'model',
            ai_temperature: 'temperature',
        };
        try {
            const saved = JSON.parse(localStorage.getItem('vpyd_ai_settings') || '{}');
            for (const [dbKey, lsKey] of Object.entries(mapping)) {
                if (dbKey in updates) {
                    saved[lsKey] = updates[dbKey];
                }
            }
            localStorage.setItem('vpyd_ai_settings', JSON.stringify(saved));
        } catch (_) { /* ignore */ }
    }

    /* ================================================================
       LOGS
       ================================================================ */

    async _loadLogs() {
        const level = this.logLevelFilter?.value || '';
        const source = this.logSourceFilter?.value || '';
        const params = new URLSearchParams();
        if (level) params.set('level', level);
        if (source) params.set('source', source);
        params.set('limit', '300');

        try {
            const resp = await fetch(`/api/hub/logs?${params}`);
            const data = await resp.json();
            if (!data.success) return;
            this._renderLogs(data.logs, data.total);
        } catch (e) {
            console.error('Failed to load logs:', e);
        }
    }

    _renderLogs(logs, total) {
        if (!this.logBody) return;
        if (!logs.length) {
            this.logBody.innerHTML = '<tr><td colspan="4" class="shub-empty">No log entries</td></tr>';
            return;
        }
        this.logBody.innerHTML = logs.map(l => {
            const t = new Date(l.timestamp * 1000).toLocaleString();
            const cls = `shub-log-level--${l.level}`;
            const detail = l.detail ? ` title="${this._esc(l.detail)}"` : '';
            return `<tr class="${cls}"${detail}>
                <td class="shub-mono">${t}</td>
                <td><span class="shub-pill shub-pill--${l.level}">${l.level}</span></td>
                <td>${l.source}</td>
                <td>${this._esc(l.message)}</td>
            </tr>`;
        }).join('');
    }

    async _clearLogs() {
        if (!confirm('Clear all application logs?')) return;
        await fetch('/api/hub/logs', { method: 'DELETE' });
        this._loadLogs();
        this._toast('Logs cleared', 'info');
    }

    /* ================================================================
       TESTS
       ================================================================ */

    async _discoverTests() {
        try {
            const resp = await fetch('/api/hub/tests/discover');
            const data = await resp.json();
            if (!data.success) return;
            this._renderTestFiles(data.test_files);
        } catch (e) {
            console.error('Test discover failed:', e);
        }
    }

    _renderTestFiles(files) {
        if (!this.testFileList) return;
        if (!files.length) {
            this.testFileList.innerHTML = '<div class="shub-empty">No test files found</div>';
            return;
        }
        this.testFileList.innerHTML = files.map(f => `
            <label class="shub-test-file">
                <input type="checkbox" value="${f}">
                <span>${f}</span>
            </label>
        `).join('');
    }

    async _runTests(selectedOnly) {
        const files = [];
        if (selectedOnly && this.testFileList) {
            this.testFileList.querySelectorAll('input:checked').forEach(cb => files.push(cb.value));
            if (!files.length) {
                this._toast('Select at least one test file', 'warn');
                return;
            }
        }

        const startTime = Date.now();
        let timerHandle = null;

        if (this.testOutput) {
            this.testOutput.textContent = 'Running tests… (0s elapsed)';
            this.testOutput.classList.add('shub-running');
            // Live elapsed-time counter so user knows it's still working
            timerHandle = setInterval(() => {
                const elapsed = Math.round((Date.now() - startTime) / 1000);
                this.testOutput.textContent = `Running tests… (${elapsed}s elapsed)`;
            }, 1000);
        }
        this.testRunBtn.disabled = true;
        this.testRunAllBtn.disabled = true;

        try {
            const resp = await fetch('/api/hub/tests/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ files, verbose: true }),
            });
            const data = await resp.json();
            if (timerHandle) clearInterval(timerHandle);
            if (this.testOutput) {
                this.testOutput.classList.remove('shub-running');
                if (data.success) {
                    const r = data.run;
                    const header = `Status: ${r.status.toUpperCase()}  |  ` +
                        `${r.passed} passed  ${r.failed} failed  ${r.errors} errors  ${r.skipped} skipped  ` +
                        `(${r.duration}s)\n${'─'.repeat(70)}\n`;
                    this.testOutput.textContent = header + r.output;
                    this.testOutput.className = `shub-test-output shub-test-${r.status}`;
                } else {
                    this.testOutput.textContent = `Error: ${data.error}`;
                }
            }
            this._loadTestHistory();
        } catch (e) {
            if (timerHandle) clearInterval(timerHandle);
            if (this.testOutput) {
                this.testOutput.classList.remove('shub-running');
                this.testOutput.textContent = `Request failed: ${e.message}`;
            }
        } finally {
            this.testRunBtn.disabled = false;
            this.testRunAllBtn.disabled = false;
        }
    }

    async _loadTestHistory() {
        try {
            const resp = await fetch('/api/hub/tests?limit=10');
            const data = await resp.json();
            if (!data.success || !this.testHistory) return;
            if (!data.runs.length) {
                this.testHistory.innerHTML = '<div class="shub-empty">No past test runs</div>';
                return;
            }
            this.testHistory.innerHTML = data.runs.map(r => {
                const t = new Date(r.started_at * 1000).toLocaleString();
                const cls = r.status === 'passed' ? 'shub-pill--pass' : 'shub-pill--fail';
                return `<div class="shub-test-run-row" data-run-id="${r.id}">
                    <span class="shub-mono">${t}</span>
                    <span class="shub-pill ${cls}">${r.status}</span>
                    <span>${r.passed}<i data-lucide="check" style="width:12px;height:12px;display:inline;vertical-align:-1px;color:#4ade80;"></i> ${r.failed}<i data-lucide="x" style="width:12px;height:12px;display:inline;vertical-align:-1px;color:#f87171;"></i> ${r.errors}<i data-lucide="triangle-alert" style="width:12px;height:12px;display:inline;vertical-align:-1px;color:#facc15;"></i> (${r.duration || 0}s)</span>
                </div>`;
            }).join('');

            // Click to view detail
            this.testHistory.querySelectorAll('.shub-test-run-row').forEach(row => {
                row.addEventListener('click', () => this._viewTestRun(row.dataset.runId));
            });
            if (typeof lucide !== 'undefined') lucide.createIcons({ root: this.testHistory });
        } catch (e) {
            console.error('Test history load failed:', e);
        }
    }

    async _viewTestRun(runId) {
        try {
            const resp = await fetch(`/api/hub/tests/${runId}`);
            const data = await resp.json();
            if (data.success && this.testOutput) {
                const r = data.run;
                const header = `[Past Run] Status: ${r.status.toUpperCase()}  |  ` +
                    `${r.passed} passed  ${r.failed} failed  ${r.errors} errors  ${r.skipped} skipped  ` +
                    `(${r.duration}s)\n${'─'.repeat(70)}\n`;
                this.testOutput.textContent = header + (r.output || '');
                this.testOutput.className = `shub-test-output shub-test-${r.status}`;
            }
        } catch (e) {
            console.error('Test detail load failed:', e);
        }
    }

    /* ================================================================
       HISTORY
       ================================================================ */

    async _loadHistory() {
        const cat = this.historyCatFilter?.value || '';
        const params = new URLSearchParams({ limit: '200' });
        if (cat) params.set('category', cat);

        try {
            const resp = await fetch(`/api/hub/history?${params}`);
            const data = await resp.json();
            if (!data.success || !this.historyBody) return;
            if (!data.history.length) {
                this.historyBody.innerHTML = '<tr><td colspan="5" class="shub-empty">No history entries</td></tr>';
                return;
            }
            this.historyBody.innerHTML = data.history.map(h => {
                const t = new Date(h.timestamp * 1000).toLocaleString();
                const oldVal = h.old_value ? this._truncate(h.old_value, 40) : '—';
                const newVal = h.new_value ? this._truncate(h.new_value, 40) : '—';
                return `<tr>
                    <td class="shub-mono">${t}</td>
                    <td>${h.category}</td>
                    <td>${h.action}</td>
                    <td><code>${h.key || '—'}</code></td>
                    <td class="shub-change-vals">${oldVal} → ${newVal}</td>
                </tr>`;
            }).join('');
        } catch (e) {
            console.error('History load failed:', e);
        }
    }

    /* ================================================================
       SERVER INFO
       ================================================================ */

    async _loadServerInfo() {
        try {
            const resp = await fetch('/api/hub/info');
            const data = await resp.json();
            if (data.success) {
                const i = data.info;
                const el = document.getElementById('shub-server-info');
                if (el) {
                    el.textContent = `Python ${i.python_version.split(' ')[0]} · PID ${i.pid} · ${i.test_count} test files`;
                }
            }
        } catch (_) { /* non-critical */ }
    }

    /* ================================================================
       CONNECTION STATUS (replaces the old static label)
       ================================================================ */

    updateConnectionStatus(connected) {
        const indicator = document.getElementById('conn-indicator');
        if (!indicator) return;
        indicator.className = connected
            ? 'conn-indicator conn-indicator--ok'
            : 'conn-indicator conn-indicator--err';
        indicator.title = connected ? 'Connected' : 'Disconnected';
        const icon = indicator.querySelector('i');
        if (icon) {
            icon.dataset.lucide = connected ? 'wifi' : 'wifi-off';
            if (typeof lucide !== 'undefined') lucide.createIcons();
        }
    }

    /* ================================================================
       UTILITIES
       ================================================================ */

    _esc(s) {
        if (!s) return '';
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }

    _truncate(s, max) {
        if (!s || s.length <= max) return this._esc(s);
        return this._esc(s.slice(0, max)) + '…';
    }

    _toast(message, level = 'info') {
        // Simple transient notification at the bottom of the modal
        const toast = document.createElement('div');
        toast.className = `shub-toast shub-toast--${level}`;
        toast.textContent = message;
        this.modal.querySelector('.shub-content')?.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }
}

// ─── Eye toggle for secret fields ────────────────────────────────
document.addEventListener('click', (e) => {
    const btn = e.target.closest('.shub-eye-btn');
    if (!btn) return;
    const input = document.getElementById(btn.dataset.target);
    if (input) {
        input.type = input.type === 'password' ? 'text' : 'password';
    }
});
