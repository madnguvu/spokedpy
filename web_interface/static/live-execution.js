/**
 * Live Execution Panel - Ledger-Sourced Execution
 * 
 * Reads from the Session Ledger (the source of truth for node code),
 * NOT from the canvas. Executes via the Flask backend which uses
 * a persistent PythonExecutor (REPL-style shared namespace).
 * 
 * Every execution is recorded as an immutable ledger event, so you
 * get full execution history per node.
 * 
 * Supports two execution modes:
 *   LEDGER  — direct ledger → executor (original path)
 *   REGISTRY — ledger → registry slots → executor (matrix path)
 * 
 * Engine Tabs:
 *   Each tab maps to one engine row in the registry (Python, JS, Rust, …).
 *   Users can load code into tabs and execute all engines simultaneously.
 * 
 * Project Persistence:
 *   Save/Load projects (canvas + engine tabs) to a SQLite database via
 *   the /api/projects endpoints.
 */

/* ── Engine maps — loaded from /api/engines (single source of truth) ──
 *
 * These start with hardcoded defaults so the panel renders immediately.
 * Once the API responds, they're overwritten with the canonical data.
 * Other scripts (runtime-panel.js, app.js) should read window.ENGINE_*
 * instead of maintaining their own copies.
 */
const ENGINE_NAMES = {
    a: 'Python',   b: 'JavaScript', c: 'TypeScript', d: 'Rust',
    e: 'Java',     f: 'Swift',      g: 'C++',        h: 'R',
    i: 'Go',       j: 'Ruby',       k: 'C#',         l: 'Kotlin',
    m: 'C',        n: 'Bash',       o: 'Perl'
};
const ENGINE_LETTERS = Object.keys(ENGINE_NAMES);
const ENGINE_SLOTS = {
    a: 64,
    b: 16, c: 16, d: 16, e: 16, f: 16, g: 16, h: 16,
    i: 16, j: 16, k: 16, l: 16, m: 16, n: 16, o: 16
};
const MAX_DISPLAY_SLOTS = 16;
const LETTER_TO_LANG = {
    a: 'python', b: 'javascript', c: 'typescript', d: 'rust',
    e: 'java',   f: 'swift',      g: 'cpp',        h: 'r',
    i: 'go',     j: 'ruby',       k: 'csharp',     l: 'kotlin',
    m: 'c',      n: 'bash',       o: 'perl'
};
/** Per-engine file extensions (for export) */
const LANG_TO_EXT = {};
/** Per-engine availability (is the runtime installed on this machine?) */
const ENGINE_AVAILABLE = {};
/** Per-engine capabilities (repl, debug, canvas_exec, engine_tab, …) */
const ENGINE_CAPABILITIES = {};
/** Per-engine tier: 'primary', 'tier-1', 'tier-2' */
const ENGINE_TIERS = {};
/** Per-engine parser/executor class name */
const ENGINE_PARSERS = {};
/** Per-engine runtime version string (or null) */
const ENGINE_VERSIONS = {};

/* Expose globally so runtime-panel.js / app.js read the same data */
window.ENGINE_NAMES        = ENGINE_NAMES;
window.ENGINE_LETTERS      = ENGINE_LETTERS;
window.ENGINE_SLOTS        = ENGINE_SLOTS;
window.LETTER_TO_LANG      = LETTER_TO_LANG;
window.LANG_TO_EXT         = LANG_TO_EXT;
window.ENGINE_AVAILABLE    = ENGINE_AVAILABLE;
window.ENGINE_CAPABILITIES = ENGINE_CAPABILITIES;
window.ENGINE_TIERS        = ENGINE_TIERS;
window.ENGINE_PARSERS      = ENGINE_PARSERS;
window.ENGINE_VERSIONS     = ENGINE_VERSIONS;

/**
 * Fetch the canonical engine manifest from the backend and overwrite
 * the local maps.  Called once on page load — the API endpoint derives
 * everything from the Python EngineID enum so this is always in sync.
 */
async function _loadEngineManifest() {
    try {
        const resp = await fetch('/api/engines');
        if (!resp.ok) return;
        const data = await resp.json();
        if (!data.success || !data.engines) return;

        // Clear and rebuild maps from the canonical manifest
        for (const key of Object.keys(ENGINE_NAMES))  delete ENGINE_NAMES[key];
        for (const key of Object.keys(ENGINE_SLOTS))  delete ENGINE_SLOTS[key];
        for (const key of Object.keys(LETTER_TO_LANG)) delete LETTER_TO_LANG[key];
        for (const key of Object.keys(LANG_TO_EXT))   delete LANG_TO_EXT[key];
        for (const key of Object.keys(ENGINE_AVAILABLE)) delete ENGINE_AVAILABLE[key];
        for (const key of Object.keys(ENGINE_CAPABILITIES)) delete ENGINE_CAPABILITIES[key];
        for (const key of Object.keys(ENGINE_TIERS))   delete ENGINE_TIERS[key];
        for (const key of Object.keys(ENGINE_PARSERS)) delete ENGINE_PARSERS[key];
        for (const key of Object.keys(ENGINE_VERSIONS)) delete ENGINE_VERSIONS[key];
        ENGINE_LETTERS.length = 0;

        for (const eng of data.engines) {
            ENGINE_NAMES[eng.letter]        = eng.name;
            ENGINE_SLOTS[eng.letter]        = eng.max_slots;
            LETTER_TO_LANG[eng.letter]      = eng.language;
            LANG_TO_EXT[eng.language]       = eng.extension;
            ENGINE_AVAILABLE[eng.letter]    = eng.platform_enabled;
            ENGINE_CAPABILITIES[eng.letter] = eng.capabilities || {};
            ENGINE_TIERS[eng.letter]        = eng.tier || 'tier-2';
            ENGINE_PARSERS[eng.letter]      = eng.parser || null;
            ENGINE_VERSIONS[eng.letter]     = eng.runtime_version || null;
            ENGINE_LETTERS.push(eng.letter);
        }

        console.log(`[Engine Manifest] Loaded ${data.total} engines ` +
                     `(${data.enabled} enabled, ${data.disabled} disabled) from /api/engines`);
    } catch (e) {
        console.warn('[Engine Manifest] Could not fetch /api/engines, using defaults:', e.message);
    }
}

// Fire and forget — maps are usable immediately with defaults
_loadEngineManifest();

class LiveExecutionPanel {
    constructor() {
        this.nodes = [];
        this.variables = {};
        this.isOpen = false;
        this.selectedNodeId = null;
        this.executionHistory = [];
        this.autoRefreshInterval = null;

        /** @type {'ledger'|'registry'} */
        this.mode = 'ledger';

        /** Slot-address → visual state for the matrix grid */
        this._matrixState = {};

        // ── Engine Tabs state ──
        /** @type {Map<string, {engine_letter:string, language:string, code:string, label:string}>} */
        this.engineTabs = new Map();
        this.activeTabId = null;

        // ── Project state ──
        this.currentProjectId = null;

        this.init();
    }

    /* ────────────────────────────────────────
       INIT
       ──────────────────────────────────────── */
    init() {
        this.panel = document.getElementById('live-exec-panel');
        if (!this.panel) return;

        this.toggleBtn = document.getElementById('live-exec-toggle');
        this.nodeList = document.getElementById('exec-node-list');
        this.outputArea = document.getElementById('exec-output');
        this.variablesArea = document.getElementById('exec-variables');
        this.historyArea = document.getElementById('exec-history');
        this.statusIndicator = document.getElementById('exec-status');

        // Matrix grid containers
        this.matrixGrid = document.getElementById('exec-matrix-grid');
        this.matrixBody = document.getElementById('exec-matrix-body');
        this.matrixStats = document.getElementById('exec-matrix-stats');

        // Mode toggle switch
        this.modeSwitch = document.getElementById('exec-mode-switch');
        this.modeLabelLedger = document.getElementById('exec-mode-label-ledger');
        this.modeLabelRegistry = document.getElementById('exec-mode-label-registry');
        this.modeSwitch?.addEventListener('change', () => this._onModeToggle());

        // Toggle panel
        this.toggleBtn?.addEventListener('click', () => this.toggle());

        // Control buttons
        document.getElementById('exec-run-selected')?.addEventListener('click', () => this.runSelected());
        document.getElementById('exec-run-all')?.addEventListener('click', () => this.runAll());
        document.getElementById('exec-reset')?.addEventListener('click', () => this.resetExecutor());
        document.getElementById('exec-refresh')?.addEventListener('click', () => this.refreshNodes());
        document.getElementById('exec-clear-output')?.addEventListener('click', () => this.clearOutput());
        
        // Close button
        document.getElementById('exec-close-btn')?.addEventListener('click', () => this.toggle());

        // New buttons
        document.getElementById('exec-run-engines')?.addEventListener('click', () => this.runAllEngines());
        document.getElementById('exec-save-project')?.addEventListener('click', () => this.showSaveProjectModal());
        document.getElementById('exec-load-project')?.addEventListener('click', () => this.showLoadProjectModal());

        // Import JSON button → opens file picker, then feeds through importCanvasState
        const importJsonBtn = document.getElementById('exec-import-json');
        const importJsonFile = document.getElementById('exec-import-json-file');
        importJsonBtn?.addEventListener('click', () => importJsonFile?.click());
        importJsonFile?.addEventListener('change', (e) => {
            const file = e.target.files?.[0];
            if (file) {
                this.importJSONFile(file);
                importJsonFile.value = '';  // reset so same file can be re-imported
            }
        });

        // Build the static matrix grid HTML once
        this._buildMatrixGrid();

        // Build engine tabs UI
        this._buildEngineTabs();
    }

    /* ────────────────────────────────────────
       MODE TOGGLE
       ──────────────────────────────────────── */
    _onModeToggle() {
        const isRegistry = this.modeSwitch?.checked;
        this.mode = isRegistry ? 'registry' : 'ledger';

        this.modeLabelLedger?.classList.toggle('exec-mode-label-active', !isRegistry);
        this.modeLabelRegistry?.classList.toggle('exec-mode-label-active', isRegistry);

        if (this.matrixGrid) {
            this.matrixGrid.style.display = isRegistry ? 'block' : 'none';
        }

        const modeName = isRegistry ? 'Registry' : 'Ledger';
        this.appendOutput(`\nSwitched to ${modeName} mode\n`, 'info');
        this.setStatus(`${modeName} mode`, 'idle');

        if (isRegistry) {
            this._refreshMatrix();
        }
    }

    /* ────────────────────────────────────────
       PANEL TOGGLE
       ──────────────────────────────────────── */
    toggle() {
        this.isOpen = !this.isOpen;
        this.panel?.classList.toggle('collapsed', !this.isOpen);
        this.panel?.classList.toggle('open', this.isOpen);
        
        if (this.isOpen) {
            this.refreshNodes();
            this.refreshVariables();
            if (this.mode === 'registry') this._refreshMatrix();
        }
    }

    setStatus(text, type = 'idle') {
        if (!this.statusIndicator) return;
        this.statusIndicator.textContent = text;
        this.statusIndicator.className = `exec-status exec-status-${type}`;
    }

    /* ════════════════════════════════════════════════════════════════
       AUTO-HYDRATE ENGINE TABS FROM CANVAS NODES
       ════════════════════════════════════════════════════════════════
       Fetches all active nodes from the session ledger, groups them by
       language, and populates engine tabs automatically.  This bridges
       the gap between "nodes on canvas" and "engine tabs ready to run".

       Called automatically when Play is pressed and no tabs exist yet,
       but can also be triggered manually via the Refresh button.
       ════════════════════════════════════════════════════════════════ */

    /**
     * Build a reverse map: language string → engine letter.
     * Reads from the canonical LETTER_TO_LANG map loaded from /api/engines.
     */
    _langToLetter(lang) {
        const l = (lang || '').toLowerCase().trim();
        for (const [letter, language] of Object.entries(LETTER_TO_LANG)) {
            if (language === l) return letter;
        }
        // Common aliases
        const aliases = { 'c++': 'g', 'c#': 'k', 'shell': 'n', 'sh': 'n' };
        return aliases[l] || null;
    }

    /**
     * Fetch canvas nodes from the ledger and auto-populate engine tabs.
     *
     * Strategy:
     *   1. GET /api/execution/ledger/nodes  → all active nodes with source code
     *   2. Group by language
     *   3. For each language, create ONE engine tab whose code is
     *      all node source-codes concatenated (separated by comments).
     *   4. Skip languages that already have a tab with code in them.
     *
     * @param {boolean} force — if true, replace existing tabs too
     * @returns {number} — number of tabs created
     */
    async autoHydrateFromCanvas(force = false) {
        try {
            const resp = await fetch('/api/execution/ledger/nodes');
            const data = await resp.json();

            if (!data.success || !data.nodes || data.nodes.length === 0) {
                this.appendOutput('[i] No nodes with source code in the ledger.\n', 'meta');
                return 0;
            }

            // Filter to nodes that actually have source code
            const withCode = data.nodes.filter(n => n.source_code && n.source_code.trim());
            if (withCode.length === 0) {
                this.appendOutput('[i] Nodes found but none have source code yet.\n', 'meta');
                return 0;
            }

            // Group by language
            const byLang = {};
            for (const node of withCode) {
                const lang = (node.language || 'python').toLowerCase();
                if (!byLang[lang]) byLang[lang] = [];
                byLang[lang].push(node);
            }

            // Languages that already have a non-empty tab
            const existingLangs = new Set();
            if (!force) {
                for (const tab of this.engineTabs.values()) {
                    if (tab.code && tab.code.trim()) {
                        existingLangs.add(tab.language);
                    }
                }
            }

            let created = 0;
            for (const [lang, nodes] of Object.entries(byLang)) {
                if (existingLangs.has(lang)) continue;

                const letter = this._langToLetter(lang);
                if (!letter) {
                    this.appendOutput(`[!] No engine mapping for language "${lang}", skipping ${nodes.length} node(s).\n`, 'warn');
                    continue;
                }

                // Build combined source code with node header comments
                const commentChar = ['python', 'ruby', 'r', 'perl', 'bash'].includes(lang) ? '#' : '//';
                const chunks = nodes.map(n => {
                    const header = `${commentChar} ── ${n.display_name} (${n.node_type}) ──`;
                    return `${header}\n${n.source_code.trim()}`;
                });
                const combinedCode = chunks.join('\n\n');

                const displayName = ENGINE_NAMES[letter] || lang;
                const label = `${displayName} (${nodes.length} node${nodes.length > 1 ? 's' : ''})`;

                // If force mode, remove existing tabs for this language first
                if (force) {
                    for (const [tabId, tab] of this.engineTabs.entries()) {
                        if (tab.language === lang) {
                            this._removeTabDOM(tabId);
                            this.engineTabs.delete(tabId);
                        }
                    }
                }

                this.addEngineTab(letter, lang, displayName, combinedCode, label);
                created++;
                this.appendOutput(`  [+] Auto-loaded ${displayName}: ${nodes.length} node(s), ${combinedCode.split('\n').length} lines\n`, 'info');
            }

            if (created > 0) {
                this.appendOutput(`\n━━━ Auto-hydrated ${created} engine tab(s) from ${withCode.length} canvas node(s) ━━━\n`, 'info');
            }

            return created;

        } catch (e) {
            this.appendOutput(`[ERR] Auto-hydrate failed: ${e.message}\n`, 'error');
            console.error('autoHydrateFromCanvas failed:', e);
            return 0;
        }
    }

    /**
     * Remove a tab's DOM elements (tab button + active content) without
     * affecting other tabs.  Used by autoHydrate force-refresh.
     */
    _removeTabDOM(tabId) {
        document.querySelector(`.engine-tab-btn[data-tab-id="${tabId}"]`)?.remove();
    }

    /* ════════════════════════════════════════════════════════════════
       ENGINE TABS — Tabbed code editors per language
       ════════════════════════════════════════════════════════════════ */

    _buildEngineTabs() {
        const container = document.getElementById('exec-engine-tabs');
        if (!container) return;

        // Tab bar
        const tabBar = document.createElement('div');
        tabBar.className = 'engine-tab-bar';
        tabBar.id = 'engine-tab-bar';

        // Add-tab button
        const addBtn = document.createElement('button');
        addBtn.className = 'engine-tab-add';
        addBtn.title = 'Add Engine Tab';
        addBtn.textContent = '+';
        addBtn.addEventListener('click', () => this._showAddTabMenu(addBtn));
        tabBar.appendChild(addBtn);

        container.appendChild(tabBar);

        // Tab content area (code editor)
        const contentArea = document.createElement('div');
        contentArea.className = 'engine-tab-content';
        contentArea.id = 'engine-tab-content';
        contentArea.innerHTML = `
            <div class="engine-tab-empty">
                <p>Click <strong>+</strong> to add an engine tab (Python, JavaScript, Rust, …)</p>
                <p class="exec-empty-hint">Load code into each tab, then hit <strong>Run All Engines</strong></p>
            </div>`;
        container.appendChild(contentArea);
    }

    _showAddTabMenu(anchorEl) {
        // Remove any existing menu
        document.getElementById('engine-add-menu')?.remove();

        const menu = document.createElement('div');
        menu.id = 'engine-add-menu';
        menu.className = 'engine-add-menu';

        // Only show engines that have executors
        const available = [
            { letter: 'a', lang: 'python',     name: 'Python'},
            { letter: 'b', lang: 'javascript',  name: 'JavaScript'},
            { letter: 'd', lang: 'rust',        name: 'Rust' },
            { letter: 'm', lang: 'c',           name: 'C' },
            { letter: 'g', lang: 'cpp',         name: 'C++' },
            { letter: 'n', lang: 'bash',        name: 'Bash' },
            { letter: 'c', lang: 'typescript',  name: 'TypeScript' },
            { letter: 'e', lang: 'java',        name: 'Java' },
            { letter: 'i', lang: 'go',          name: 'Go'},
            { letter: 'j', lang: 'ruby',        name: 'Ruby' },
            { letter: 'h', lang: 'r',           name: 'R'},
            { letter: 'k', lang: 'csharp',      name: 'C#' },
            { letter: 'l', lang: 'kotlin',      name: 'Kotlin' },
            { letter: 'f', lang: 'swift',       name: 'Swift' },
        ];

        for (const eng of available) {
            const item = document.createElement('div');
            item.className = 'engine-add-item';
            item.innerHTML = `<span class="engine-add-icon">${eng.icon}</span> ${eng.name}`;
            item.addEventListener('click', () => {
                this.addEngineTab(eng.letter, eng.lang, eng.name);
                menu.remove();
            });
            menu.appendChild(item);
        }

        // Position near anchor
        const rect = anchorEl.getBoundingClientRect();
        menu.style.position = 'fixed';
        menu.style.left = `${rect.left}px`;
        menu.style.top = `${rect.bottom + 4}px`;
        document.body.appendChild(menu);

        // Close on outside click
        const closeHandler = (e) => {
            if (!menu.contains(e.target) && e.target !== anchorEl) {
                menu.remove();
                document.removeEventListener('click', closeHandler);
            }
        };
        setTimeout(() => document.addEventListener('click', closeHandler), 0);
    }

    addEngineTab(engineLetter, language, displayName, code = '', label = '') {
        const tabId = `tab-${engineLetter}-${Date.now()}`;
        const tabLabel = label || `${displayName}`;

        this.engineTabs.set(tabId, {
            engine_letter: engineLetter,
            language: language,
            code: code,
            label: tabLabel,
        });

        // Add tab button to tab bar
        const tabBar = document.getElementById('engine-tab-bar');
        if (!tabBar) return;

        const addBtn = tabBar.querySelector('.engine-tab-add');

        const tabBtn = document.createElement('button');
        tabBtn.className = 'engine-tab-btn';
        tabBtn.dataset.tabId = tabId;
        tabBtn.innerHTML = `
            <span class="engine-tab-letter">${engineLetter.toUpperCase()}</span>
            <span class="engine-tab-label">${this._escapeHtml(tabLabel)}</span>
            <span class="engine-tab-close" title="Close tab"><i data-lucide="x"></i></span>`;
        if (typeof lucide !== 'undefined') lucide.createIcons({ root: tabBtn });
        tabBtn.addEventListener('click', (e) => {
            if (e.target.classList.contains('engine-tab-close')) {
                this.removeEngineTab(tabId);
            } else {
                this.selectEngineTab(tabId);
            }
        });

        tabBar.insertBefore(tabBtn, addBtn);
        this.selectEngineTab(tabId);
    }

    removeEngineTab(tabId) {
        this.engineTabs.delete(tabId);
        const btn = document.querySelector(`.engine-tab-btn[data-tab-id="${tabId}"]`);
        btn?.remove();

        if (this.activeTabId === tabId) {
            this.activeTabId = null;
            // Select next available tab
            const firstTab = this.engineTabs.keys().next().value;
            if (firstTab) {
                this.selectEngineTab(firstTab);
            } else {
                this._showEmptyTabContent();
            }
        }
    }

    selectEngineTab(tabId) {
        // Save current tab's code before switching
        this._saveCurrentTabCode();

        this.activeTabId = tabId;

        // Update tab bar active state
        document.querySelectorAll('.engine-tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tabId === tabId);
        });

        // Show tab content
        const tab = this.engineTabs.get(tabId);
        if (!tab) return;

        const contentArea = document.getElementById('engine-tab-content');
        if (!contentArea) return;

        contentArea.innerHTML = `
            <div class="engine-tab-editor-header">
                <span class="engine-tab-lang-badge" data-lang="${tab.language}">${tab.language}</span>
                <input type="text" class="engine-tab-name-input" value="${this._escapeHtml(tab.label)}"
                       placeholder="Tab name" id="active-tab-label">
                <button class="exec-ctrl-btn engine-tab-run-one" title="Run this engine only" id="run-this-engine">
                     Run
                </button>
                <button class="exec-ctrl-btn engine-tab-stage-btn" title="Stage → Speculate → Promote to registry" id="stage-this-engine">
                    🧪 Stage
                </button>
            </div>
            <textarea class="engine-tab-editor" id="active-tab-editor"
                      placeholder="Enter ${tab.language} code here…"
                      spellcheck="false">${this._escapeHtml(tab.code)}</textarea>`;

        // Wire up the "Run this engine" button
        document.getElementById('run-this-engine')?.addEventListener('click', () => {
            this.runSingleEngineTab(tabId);
        });

        // Wire up the "Stage" button
        document.getElementById('stage-this-engine')?.addEventListener('click', () => {
            this.stageSnippet(tabId);
        });

        // Save label on change
        document.getElementById('active-tab-label')?.addEventListener('input', (e) => {
            tab.label = e.target.value;
            const tabBtn = document.querySelector(`.engine-tab-btn[data-tab-id="${tabId}"] .engine-tab-label`);
            if (tabBtn) tabBtn.textContent = e.target.value;
        });

        // Handle Tab key in the editor
        const editor = document.getElementById('active-tab-editor');
        if (editor) {
            editor.addEventListener('keydown', (e) => {
                if (e.key === 'Tab') {
                    e.preventDefault();
                    const start = editor.selectionStart;
                    const end = editor.selectionEnd;
                    editor.value = editor.value.substring(0, start) + '    ' + editor.value.substring(end);
                    editor.selectionStart = editor.selectionEnd = start + 4;
                }
            });
        }
    }

    _saveCurrentTabCode() {
        if (!this.activeTabId) return;
        const tab = this.engineTabs.get(this.activeTabId);
        if (!tab) return;
        const editor = document.getElementById('active-tab-editor');
        if (editor) {
            tab.code = editor.value;
        }
    }

    _showEmptyTabContent() {
        const contentArea = document.getElementById('engine-tab-content');
        if (!contentArea) return;
        contentArea.innerHTML = `
            <div class="engine-tab-empty">
                <p>Click <strong>+</strong> to add an engine tab (Python, JavaScript, Rust, …)</p>
                <p class="exec-empty-hint">Load code into each tab, then hit <strong> Run All Engines</strong></p>
            </div>`;
    }

    /** Run a single engine tab */
    async runSingleEngineTab(tabId) {
        this._saveCurrentTabCode();
        const tab = this.engineTabs.get(tabId);
        if (!tab || !tab.code.trim()) {
            this.appendOutput(`Tab "${tab?.label || tabId}" has no code.\n`, 'warn');
            return;
        }

        this.setStatus(`Running ${tab.label}…`, 'running');
        this.appendOutput(`\n [${tab.language.toUpperCase()}] Running: ${tab.label}\n`, 'info');

        try {
            const resp = await fetch('/api/execution/engines/run-simultaneous', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tabs: [tab],
                    reset_before: false,
                })
            });
            const data = await resp.json();

            if (data.success && data.results) {
                for (const r of data.results) {
                    if (r.output) this.appendOutput(r.output, 'output');
                    if (r.error) this.appendOutput(`${r.error}\n`, 'error');
                    this.appendOutput(` ${(r.execution_time * 1000).toFixed(1)}ms\n`, 'meta');
                }
                const allOk = data.results.every(r => r.success);
                this.setStatus(allOk ? 'Done' : 'Error', allOk ? 'success' : 'error');
            } else {
                this.appendOutput(`${data.error || 'Unknown error'}\n`, 'error');
                this.setStatus('Error', 'error');
            }
            this.refreshVariables();
        } catch (e) {
            this.appendOutput(` Network error: ${e.message}\n`, 'error');
            this.setStatus('Error', 'error');
        }
    }

    /** Run ALL engine tabs simultaneously.
     *
     *  Strategy:
     *    1. Try per-slot execution from registry (each slot = own temp file)
     *    2. Fall back to engine-tab mode (legacy, may concatenate per engine)
     */
    async runAllEngines() {
        // ── Strategy 1: Per-slot from registry ──────────────────────
        try {
            const slotResp = await fetch('/api/execution/registry/run-all-slots', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reset_before: false })
            });
            const slotData = await slotResp.json();

            if (slotData.success && slotData.results && slotData.results.length > 0) {
                this.setStatus(`Running ${slotData.results.length} slots…`, 'running');
                this.appendOutput(`\n━━━ Running All Slots (${slotData.results.length} isolated) ━━━\n`, 'info');

                for (const r of slotData.results) {
                    const tag = r.language?.toUpperCase() || r.engine_letter?.toUpperCase() || '?';
                    const addr = r.address || `${r.engine_letter}?`;
                    this.appendOutput(`\n [${tag}] ${r.label} (${addr.toUpperCase()}):\n`, 'info');
                    if (r.skipped) {
                        this.appendOutput(`  Skipped: ${r.skip_reason}\n`, 'meta');
                    } else {
                        if (r.output) this.appendOutput(r.output, 'output');
                        if (r.error) this.appendOutput(`  [ERR] ${r.error}\n`, 'error');
                        this.appendOutput(`  ${(r.execution_time * 1000).toFixed(1)}ms\n`, 'meta');
                    }
                    this._flashCell(addr, r.success ? 'success' : 'error', 3000);
                }

                const s = slotData.summary;
                this.appendOutput(
                    `\n━━━ All Slots: ${s.passed}/${s.total_slots} passed, ` +
                    `${(s.total_time * 1000).toFixed(1)}ms total ━━━\n`, 'meta'
                );
                this.setStatus(`${s.passed}/${s.total_slots} passed`, s.failed > 0 ? 'error' : 'success');

                this.refreshVariables();
                if (this.mode === 'registry') {
                    setTimeout(() => this._refreshMatrix(), 3500);
                }
                return;  // Done — per-slot path used
            }
        } catch (_) { /* fall through to legacy */ }

        // ── Strategy 2: Legacy engine-tab mode ──────────────────────
        this._saveCurrentTabCode();

        let tabs = Array.from(this.engineTabs.values()).filter(t => t.code.trim());

        // ── Auto-hydrate from canvas if no tabs have code ──
        if (tabs.length === 0) {
            this.appendOutput('[i] No engine tabs — auto-loading from canvas nodes…\n', 'meta');
            const created = await this.autoHydrateFromCanvas();
            if (created > 0) {
                this._saveCurrentTabCode();
                tabs = Array.from(this.engineTabs.values()).filter(t => t.code.trim());
            }
        }

        if (tabs.length === 0) {
            this.appendOutput('[!] No engine tabs with code and no canvas nodes to load.\n', 'warn');
            return;
        }

        this.setStatus(`Running ${tabs.length} engines…`, 'running');
        this.appendOutput(`\n━━━ Running All Engines (${tabs.length} tabs, legacy mode) ━━━\n`, 'info');

        // Flash matrix cells for committed engines
        for (const tab of tabs) {
            const addr = `${tab.engine_letter}1`;
            this._flashCell(addr, 'executing');
        }

        try {
            const resp = await fetch('/api/execution/engines/run-simultaneous', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tabs, reset_before: false })
            });
            const data = await resp.json();

            if (data.success && data.results) {
                for (const r of data.results) {
                    const tag = r.language?.toUpperCase() || r.engine_letter?.toUpperCase() || '?';
                    this.appendOutput(`\n [${tag}] ${r.label}:\n`, 'info');
                    if (r.skipped) {
                        this.appendOutput(`  Skipped: ${r.skip_reason}\n`, 'meta');
                    } else {
                        if (r.output) this.appendOutput(r.output, 'output');
                        if (r.error) this.appendOutput(`  [ERR] ${r.error}\n`, 'error');
                        this.appendOutput(`  ${(r.execution_time * 1000).toFixed(1)}ms\n`, 'meta');
                    }
                    // Flash matrix cell
                    const addr = `${r.engine_letter}1`;
                    this._flashCell(addr, r.success ? 'success' : 'error', 3000);
                }

                const s = data.summary;
                this.appendOutput(
                    `\n━━━ All Engines: ${s.passed}/${s.total_tabs} passed, ` +
                    `${(s.total_time * 1000).toFixed(1)}ms total ━━━\n`, 'meta'
                );
                this.setStatus(`${s.passed}/${s.total_tabs} passed`, s.failed > 0 ? 'error' : 'success');
            } else {
                this.appendOutput(`${data.error || 'Unknown error'}\n`, 'error');
                this.setStatus('Error', 'error');
            }

            this.refreshVariables();
            if (this.mode === 'registry') {
                setTimeout(() => this._refreshMatrix(), 3500);
            }
        } catch (e) {
            this.appendOutput(`[ERR] Network error: ${e.message}\n`, 'error');
            this.setStatus('Error', 'error');
        }
    }

    /* ════════════════════════════════════════════════════════════════
       PROJECT SAVE / LOAD
       ════════════════════════════════════════════════════════════════ */

    _getCanvasState() {
        // Delegate to the global VisualEditor if available
        if (window.visualEditor && typeof window.visualEditor.serializeCanvasState === 'function') {
            return window.visualEditor.serializeCanvasState();
        }
        return {};
    }

    _getProjectName() {
        return document.getElementById('project-name')?.value?.trim() || 'Untitled';
    }

    _getEngineTabsData() {
        this._saveCurrentTabCode();
        const tabs = [];
        let pos = 0;
        this.engineTabs.forEach((tab) => {
            tabs.push({
                engine_letter: tab.engine_letter,
                language: tab.language,
                code: tab.code,
                label: tab.label,
                position: pos++,
            });
        });
        return tabs;
    }

    async showSaveProjectModal() {
        // Remove existing modal
        document.getElementById('project-save-modal')?.remove();

        const name = this._getProjectName();

        const modal = document.createElement('div');
        modal.id = 'project-save-modal';
        modal.className = 'modal';
        modal.style.display = 'block';
        modal.innerHTML = `
            <div class="modal-backdrop"></div>
            <div class="modal-content" style="max-width:480px;">
                <div class="modal-header">
                    <h2> Save Project</h2>
                    <button class="modal-close" id="save-modal-close"><i data-lucide="x"></i></button>
                </div>
                <div class="modal-body">
                    <div class="form-group" style="margin-bottom:12px;">
                        <label>Project Name:</label>
                        <input type="text" class="form-input" id="save-project-name" value="${this._escapeHtml(name)}">
                    </div>
                    <div class="form-group" style="margin-bottom:12px;">
                        <label>Description (optional):</label>
                        <input type="text" class="form-input" id="save-project-desc" placeholder="What does this project do?">
                    </div>
                    <div class="form-group">
                        <label>Engine Tabs: <strong>${this.engineTabs.size}</strong></label>
                    </div>
                    ${this.currentProjectId ? `<div class="form-help">Overwriting project <code>${this.currentProjectId.slice(0,8)}…</code></div>` : ''}
                </div>
                <div class="modal-footer">
                    <button class="btn btn-primary" id="save-project-confirm"> Save</button>
                    ${this.currentProjectId ? `<button class="btn btn-secondary" id="save-project-new">Save as New</button>` : ''}
                    <button class="btn btn-secondary" id="save-project-cancel">Cancel</button>
                </div>
            </div>`;

        document.body.appendChild(modal);
        if (typeof lucide !== 'undefined') lucide.createIcons({ root: modal });

        // Wire events
        modal.querySelector('#save-modal-close')?.addEventListener('click', () => modal.remove());
        modal.querySelector('#save-project-cancel')?.addEventListener('click', () => modal.remove());
        modal.querySelector('.modal-backdrop')?.addEventListener('click', () => modal.remove());

        modal.querySelector('#save-project-confirm')?.addEventListener('click', async () => {
            await this._doSaveProject(
                modal.querySelector('#save-project-name').value.trim() || 'Untitled',
                modal.querySelector('#save-project-desc').value.trim(),
                this.currentProjectId  // overwrite if exists
            );
            modal.remove();
        });

        modal.querySelector('#save-project-new')?.addEventListener('click', async () => {
            await this._doSaveProject(
                modal.querySelector('#save-project-name').value.trim() || 'Untitled',
                modal.querySelector('#save-project-desc').value.trim(),
                null  // force new project
            );
            modal.remove();
        });
    }

    async _doSaveProject(name, description, projectId) {
        const state = this._getCanvasState();
        const engineTabs = this._getEngineTabsData();

        try {
            const resp = await fetch('/api/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, state, engine_tabs: engineTabs, description, project_id: projectId })
            });
            const data = await resp.json();
            if (data.success) {
                this.currentProjectId = data.project.id;
                this.appendOutput(` Project "${name}" saved.\n`, 'info');
                this.setStatus('Saved', 'success');
                // Update header project name
                const projectInput = document.getElementById('project-name');
                if (projectInput) projectInput.value = name;
            } else {
                this.appendOutput(` Save failed: ${data.error}\n`, 'error');
            }
        } catch (e) {
            this.appendOutput(` Save failed: ${e.message}\n`, 'error');
        }
    }

    async showLoadProjectModal() {
        // Remove existing modal
        document.getElementById('project-load-modal')?.remove();

        const modal = document.createElement('div');
        modal.id = 'project-load-modal';
        modal.className = 'modal';
        modal.style.display = 'block';
        modal.innerHTML = `
            <div class="modal-backdrop"></div>
            <div class="modal-content" style="max-width:560px;">
                <div class="modal-header">
                    <h2><i data-lucide="folder-open"></i> Load Project</h2>
                    <button class="modal-close" id="load-modal-close"><i data-lucide="x"></i></button>
                </div>
                <div class="modal-body">
                    <div id="project-list-loading" style="text-align:center;padding:20px;">Loading projects…</div>
                    <div id="project-list-container" style="display:none;max-height:400px;overflow-y:auto;"></div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" id="load-project-cancel">Cancel</button>
                </div>
            </div>`;

        document.body.appendChild(modal);
        if (typeof lucide !== 'undefined') lucide.createIcons({ root: modal });

        modal.querySelector('#load-modal-close')?.addEventListener('click', () => modal.remove());
        modal.querySelector('#load-project-cancel')?.addEventListener('click', () => modal.remove());
        modal.querySelector('.modal-backdrop')?.addEventListener('click', () => modal.remove());

        // Fetch project list
        try {
            const resp = await fetch('/api/projects');
            const data = await resp.json();

            const loadingEl = modal.querySelector('#project-list-loading');
            const listEl = modal.querySelector('#project-list-container');

            if (!data.success || !data.projects || data.projects.length === 0) {
                loadingEl.textContent = 'No saved projects found.';
                return;
            }

            loadingEl.style.display = 'none';
            listEl.style.display = 'block';

            listEl.innerHTML = data.projects.map(p => {
                const date = new Date(p.updated_at * 1000).toLocaleString();
                const isCurrent = p.id === this.currentProjectId;
                return `
                    <div class="project-list-item ${isCurrent ? 'project-current' : ''}" data-id="${p.id}">
                        <div class="project-list-info">
                            <div class="project-list-name">${this._escapeHtml(p.name)} ${isCurrent ? '(current)' : ''}</div>
                            <div class="project-list-meta">${this._escapeHtml(p.description || '')} · ${date}</div>
                        </div>
                        <div class="project-list-actions">
                            <button class="btn btn-primary btn-small project-load-btn" data-id="${p.id}">Load</button>
                            <button class="btn btn-danger btn-small project-delete-btn" data-id="${p.id}" title="Delete"><i data-lucide="trash-2"></i></button>
                        </div>
                    </div>`;
            }).join('');

            if (typeof lucide !== 'undefined') lucide.createIcons({ root: listEl });

            // Wire load buttons
            listEl.querySelectorAll('.project-load-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    await this._doLoadProject(btn.dataset.id);
                    modal.remove();
                });
            });

            // Wire delete buttons
            listEl.querySelectorAll('.project-delete-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    if (confirm('Delete this project permanently?')) {
                        await this._doDeleteProject(btn.dataset.id);
                        btn.closest('.project-list-item')?.remove();
                    }
                });
            });
        } catch (e) {
            modal.querySelector('#project-list-loading').textContent = `Error: ${e.message}`;
        }
    }

    async _doLoadProject(projectId) {
        try {
            const resp = await fetch(`/api/projects/${projectId}`);
            const data = await resp.json();
            if (!data.success || !data.project) {
                this.appendOutput(` Load failed: ${data.error || 'Not found'}\n`, 'error');
                return;
            }

            const project = data.project;
            this.currentProjectId = project.id;

            // 1) Reset execution namespace
            try {
                await fetch('/api/execution/reset-namespace', { method: 'POST' });
            } catch (_) {}

            // 2) Restore canvas state if the global editor is available
            if (window.visualEditor && project.state) {
                // Clear canvas first
                try { await fetch('/api/canvas/clear', { method: 'POST' }); } catch (_) {}
                window.visualEditor.nodes.clear();
                window.visualEditor.connections.clear();
                document.getElementById('nodes-layer')?.replaceChildren();
                document.getElementById('connections-layer')?.replaceChildren();

                // Normalize and restore
                if (typeof window.visualEditor._normalizeImportState === 'function') {
                    window.visualEditor._normalizeImportState(project.state);
                }
                await window.visualEditor.restoreFromState(project.state);
            }

            // 3) Restore engine tabs
            // Clear existing tabs
            this.engineTabs.clear();
            document.querySelectorAll('.engine-tab-btn').forEach(btn => btn.remove());
            this.activeTabId = null;

            if (project.engine_tabs && project.engine_tabs.length > 0) {
                for (const tab of project.engine_tabs) {
                    const name = ENGINE_NAMES[tab.engine_letter] || tab.language;
                    this.addEngineTab(
                        tab.engine_letter,
                        tab.language,
                        name,
                        tab.code || '',
                        tab.label || name
                    );
                }
            } else {
                this._showEmptyTabContent();
            }

            // 4) Update project name
            const projectInput = document.getElementById('project-name');
            if (projectInput) projectInput.value = project.name;

            this.appendOutput(` Loaded project "${project.name}"\n`, 'info');
            this.setStatus('Loaded', 'success');
            this.refreshNodes();
            this.refreshVariables();
        } catch (e) {
            this.appendOutput(` Load failed: ${e.message}\n`, 'error');
        }
    }

    async _doDeleteProject(projectId) {
        try {
            const resp = await fetch(`/api/projects/${projectId}`, { method: 'DELETE' });
            const data = await resp.json();
            if (data.success) {
                this.appendOutput(' Project deleted.\n', 'info');
                if (this.currentProjectId === projectId) {
                    this.currentProjectId = null;
                }
            } else {
                this.appendOutput(` Delete failed: ${data.error}\n`, 'error');
            }
        } catch (e) {
            this.appendOutput(` Delete failed: ${e.message}\n`, 'error');
        }
    }

    /* ────────────────────────────────────────
       JSON IMPORT — Populate canvas + engine tabs from a .json file
       ──────────────────────────────────────── */

    /**
     * Read a .json file, restore the canvas, and populate engine tabs.
     * The JSON format matches the export:
     *   { project: { name, saved_at },
     *     state: { nodes, connections, viewport },
     *     engine_tabs: [ { engine_letter, language, code, label }, … ] }
     *
     * If the JSON has no `engine_tabs` key the canvas is still loaded
     * (backwards-compatible with plain canvas-only exports).
     */
    async importJSONFile(file) {
        this.appendOutput(` Importing JSON: ${file.name}…\n`, 'info');
        this.setStatus('Importing…', 'running');

        try {
            // If the global VisualEditor is available, delegate canvas
            // restore to it — it already handles normalize + restoreFromState
            // AND will call our loadFromJSON for engine_tabs.
            if (window.visualEditor && typeof window.visualEditor.importCanvasState === 'function') {
                await window.visualEditor.importCanvasState(file);
                this.appendOutput(' JSON import complete.\n', 'info');
                this.setStatus('Imported', 'success');
                this.refreshNodes();
                this.refreshVariables();
                return;
            }

            // Fallback: no VisualEditor — handle everything ourselves
            const text = await file.text();
            const payload = JSON.parse(text);

            // Reset namespace
            try {
                await fetch('/api/execution/reset-namespace', { method: 'POST' });
            } catch (_) {}

            // Load engine tabs
            if (Array.isArray(payload.engine_tabs) && payload.engine_tabs.length > 0) {
                this.loadFromJSON(payload.engine_tabs);
            }

            // Update project name
            if (payload.project?.name) {
                const projectInput = document.getElementById('project-name');
                if (projectInput) projectInput.value = payload.project.name;
            }

            this.appendOutput(' JSON import complete (engine tabs only — no canvas editor).\n', 'info');
            this.setStatus('Imported', 'success');
        } catch (e) {
            this.appendOutput(` Import error: ${e.message}\n`, 'error');
            this.setStatus('Error', 'error');
        }
    }

    /**
     * Populate engine tabs from an array of tab descriptors.
     * Called by importJSONFile / importCanvasState or any external caller.
     *
     * Each item: { engine_letter, language, code, label }
     */
    loadFromJSON(tabsArray) {
        if (!Array.isArray(tabsArray) || tabsArray.length === 0) return;

        // Clear existing tabs
        this._saveCurrentTabCode();
        this.engineTabs.clear();
        document.querySelectorAll('.engine-tab-btn').forEach(btn => btn.remove());
        this.activeTabId = null;

        const loaded = [];
        for (const tab of tabsArray) {
            const letter = tab.engine_letter || 'a';
            const lang = tab.language || LETTER_TO_LANG[letter] || 'python';
            const displayName = ENGINE_NAMES[letter] || lang;
            this.addEngineTab(
                letter,
                lang,
                displayName,
                tab.code || '',
                tab.label || displayName
            );
            loaded.push(`${displayName} (${letter})`);
        }

        this.appendOutput(
            `📋 Loaded ${tabsArray.length} engine tab(s): ${loaded.join(', ')}\n` +
            `💡 Click " Engines" to run all, or select a tab and press Run.\n`,
            'info'
        );
    }

    /* ────────────────────────────────────────
       POLYGLOT ENGINE DEMO
       ──────────────────────────────────────── */

    /**
     * Fetch demo code snippets from the server and populate engine tabs.
     * Only engines whose toolchain is detected on PATH are loaded.
     * If autoRun is true, immediately fires "Run All Engines" after loading.
     */
    async loadEngineDemo(autoRun = false) {
        this.appendOutput(' Loading polyglot engine demo…\n', 'info');
        this.setStatus('Loading demo…', 'running');

        try {
            const resp = await fetch('/api/demos/engine-tabs');
            const data = await resp.json();
            if (!data.success || !data.tabs || data.tabs.length === 0) {
                this.appendOutput(` Demo load failed: ${data.error || 'No engines available'}\n`, 'error');
                this.setStatus('Demo load failed', 'error');
                return;
            }

            // Clear existing tabs
            this._saveCurrentTabCode();
            this.engineTabs.clear();
            document.querySelectorAll('.engine-tab-btn').forEach(btn => btn.remove());
            this.activeTabId = null;

            // Reset the namespace so each engine starts fresh
            try {
                await fetch('/api/execution/reset-namespace', { method: 'POST' });
            } catch (_) {}

            // Populate tabs
            const loaded = [];
            for (const tab of data.tabs) {
                const displayName = ENGINE_NAMES[tab.engine_letter] || tab.language;
                this.addEngineTab(
                    tab.engine_letter,
                    tab.language,
                    displayName,
                    tab.code || '',
                    tab.label || displayName
                );
                loaded.push(`${displayName} (${tab.engine_letter})`);
            }

            this.appendOutput(
                ` Demo loaded: ${data.tabs.length} engine tabs\n` +
                `   ${loaded.join(', ')}\n\n` +
                `💡 Click " Engines" to run all simultaneously, ` +
                `or select a tab and press Run to execute individually.\n`,
                'info'
            );
            this.setStatus(`Demo: ${data.tabs.length} engines`, 'success');

            // Optional auto-run
            if (autoRun) {
                this.appendOutput('\n Auto-running all engines…\n', 'info');
                await this.runAllEngines();
            }
        } catch (e) {
            this.appendOutput(` Demo load error: ${e.message}\n`, 'error');
            this.setStatus('Error', 'error');
        }
    }

    /* ────────────────────────────────────────
       STAGING PIPELINE — Speculative Execution & Promotion
       ──────────────────────────────────────── */

    /**
     * Run the full staging pipeline for an engine tab:
     *   queue → speculate (dry-run) → verdict → promote (if pass)
     *
     * The snippet is executed in an ISOLATED sandbox first. If it passes,
     * it gets promoted to production: written to disk, added to the
     * SessionLedger, and committed to a real registry slot.
     */
    async stageSnippet(tabId, autoPromote = true) {
        this._saveCurrentTabCode();
        const tab = this.engineTabs.get(tabId);
        if (!tab || !tab.code.trim()) {
            this.appendOutput(` Tab "${tab?.label || tabId}" has no code to stage.\n`, 'warn');
            return null;
        }

        this.setStatus(`Staging ${tab.label}…`, 'running');
        this.appendOutput(
            `\n🧪 ━━━ STAGING PIPELINE ━━━━━━━━━━━━━━━━━━━━━━━━\n` +
            `   Tab: ${tab.label} (${tab.language})\n` +
            `   Engine: ${tab.engine_letter.toUpperCase()}\n`, 'info'
        );

        try {
            const resp = await fetch('/api/staging/run-full', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    engine_letter: tab.engine_letter,
                    language: tab.language,
                    code: tab.code,
                    label: tab.label,
                    auto_promote: autoPromote,
                }),
            });
            const data = await resp.json();

            if (!data.success) {
                this.appendOutput(` Pipeline error: ${data.error}\n`, 'error');
                this.setStatus('Stage failed', 'error');
                return null;
            }

            const s = data.snippet;

            // Phase 1: Queued
            this.appendOutput(
                ` QUEUED → slot reserved: ${s.reserved_address}\n`, 'info'
            );

            // Phase 2: Speculative execution result
            if (s.spec_success) {
                this.appendOutput(
                    ` SPECULATE →  PASS (${(s.spec_execution_time * 1000).toFixed(1)}ms)\n`, 'info'
                );
                if (s.spec_output) {
                    // Show first 20 lines of speculative output
                    const lines = s.spec_output.split('\n');
                    const preview = lines.slice(0, 20).join('\n');
                    this.appendOutput(`   ┌─ speculative output ─────────────────\n`, 'meta');
                    this.appendOutput(`${preview}\n`, 'output');
                    if (lines.length > 20) {
                        this.appendOutput(`   … (${lines.length - 20} more lines)\n`, 'meta');
                    }
                    this.appendOutput(`   └────────────────────────────────────\n`, 'meta');
                }
            } else {
                this.appendOutput(
                    `   2. SPECULATE -- FAIL\n` +
                    `      Error: ${s.spec_error?.substring(0, 300) || 'unknown'}\n`, 'error'
                );
            }

            // Phase 3: Verdict
            if (s.phase === 'promoted') {
                this.appendOutput(`   3. VERDICT --AUTO-PASS\n`, 'info');
                this.appendOutput(
                    `   4. PROMOTED --LIVE IN PRODUCTION\n` +
                    `      File:     ${s.saved_file_path}\n` +
                    `      Node:     ${s.ledger_node_id}\n` +
                    `      Slot:     ${s.registry_slot_id} (${s.reserved_address})\n` +
                    `      Time:     ${((s.promoted_at - s.created_at) * 1000).toFixed(0)}ms total\n`,
                    'info'
                );

                // Flash the matrix cell
                this._flashCell(s.reserved_address, 'success', 5000);

                this.setStatus(`Promoted → ${s.reserved_address}`, 'success');

                // Refresh the matrix grid to show the new slot
                if (this.mode === 'registry') {
                    setTimeout(() => this._refreshMatrix(), 1000);
                }
            } else if (s.phase === 'passed') {
                this.appendOutput(
                    `   3. VERDICT --PASS (awaiting manual promote)\n` +
                    `      Call: stagePromote('${s.staging_id}')\n`, 'info'
                );
                this.setStatus(`Passed → awaiting promote`, 'success');
            } else if (s.phase === 'rejected') {
                this.appendOutput(
                    `   3. VERDICT  --REJECTED\n` +
                    `      Reason: ${s.rejection_reason?.substring(0, 300) || 'spec failed'}\n`, 'error'
                );
                this._flashCell(s.reserved_address, 'error', 3000);
                this.setStatus('Rejected', 'error');
            } else if (s.phase === 'failed') {
                this.appendOutput(`   VERDICT  --FAILED\n`, 'error');
                this.setStatus('Failed', 'error');
            }

            this.appendOutput(` ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n`, 'info');

            this.refreshVariables();
            return s;

        } catch (e) {
            this.appendOutput(` Pipeline error: ${e.message}\n`, 'error');
            this.setStatus('Stage error', 'error');
            return null;
        }
    }

    /**
     * Stage ALL engine tabs through the pipeline simultaneously.
     */
    async stageAllTabs(autoPromote = true) {
        this._saveCurrentTabCode();
        const tabs = Array.from(this.engineTabs.entries()).filter(([, t]) => t.code.trim());
        if (tabs.length === 0) {
            this.appendOutput(' No tabs with code to stage.\n', 'warn');
            return;
        }

        this.appendOutput(
            `\n STAGING ALL ${tabs.length} TABS ━━━━━━━━━━━━━━━━━━\n`, 'info'
        );
        this.setStatus(`Staging ${tabs.length} tabs…`, 'running');

        let passed = 0, failed = 0;
        for (const [tabId, tab] of tabs) {
            const result = await this.stageSnippet(tabId, autoPromote);
            if (result && result.phase === 'promoted') passed++;
            else failed++;
        }

        this.appendOutput(
            `\nSTAGING COMPLETE: ${passed} promoted, ${failed} failed ━━━\n`, 'info'
        );
        this.setStatus(`Staged: ${passed}pos(+) ${failed}neg(-)`, failed > 0 ? 'error' : 'success');
    }

    /**
     * Manually promote a snippet that is in PASSED phase.
     */
    async stagePromote(stagingId) {
        try {
            const resp = await fetch(`/api/staging/promote/${stagingId}`, { method: 'POST' });
            const data = await resp.json();
            if (data.success) {
                const s = data.snippet;
                this.appendOutput(
                    ` Promoted: ${s.label} → ${s.reserved_address} (${s.registry_slot_id})\n` +
                    `   File: ${s.saved_file_path}\n`, 'info'
                );
                this._flashCell(s.reserved_address, 'success', 5000);
                if (this.mode === 'registry') {
                    setTimeout(() => this._refreshMatrix(), 1000);
                }
            } else {
                this.appendOutput(` Promote failed: ${data.error}\n`, 'error');
            }
        } catch (e) {
            this.appendOutput(` Promote error: ${e.message}\n`, 'error');
        }
    }

    /**
     * Rollback a promoted snippet from production.
     */
    async stageRollback(stagingId, reason = '') {
        try {
            const resp = await fetch(`/api/staging/rollback/${stagingId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reason }),
            });
            const data = await resp.json();
            if (data.success) {
                const s = data.snippet;
                this.appendOutput(
                    `↩️  Rolled back: ${s.label} from ${s.reserved_address}\n` +
                    `   Reason: ${reason || 'manual rollback'}\n`, 'info'
                );
                this._flashCell(s.reserved_address, 'error', 3000);
                if (this.mode === 'registry') {
                    setTimeout(() => this._refreshMatrix(), 1000);
                }
            } else {
                this.appendOutput(` Rollback failed: ${data.error}\n`, 'error');
            }
        } catch (e) {
            this.appendOutput(` Rollback error: ${e.message}\n`, 'error');
        }
    }

    /**
     * Get the staging pipeline summary.
     */
    async getStagingSummary() {
        try {
            const resp = await fetch('/api/staging/summary');
            const data = await resp.json();
            if (data.success) {
                this.appendOutput(
                    `\n Staging Pipeline Summary:\n` +
                    `   Active:     ${data.active_count}\n` +
                    `   Promoted:   ${data.promoted_total}\n` +
                    `   Rejected:   ${data.rejected_total}\n` +
                    `   Rolled back: ${data.rolled_back_total}\n` +
                    `   History:    ${data.history_count}\n`, 'info'
                );
                if (data.reserved_positions && Object.keys(data.reserved_positions).length > 0) {
                    this.appendOutput('   Reserved slots: ', 'meta');
                    for (const [eng, positions] of Object.entries(data.reserved_positions)) {
                        this.appendOutput(`${eng}:[${positions.join(',')}] `, 'meta');
                    }
                    this.appendOutput('\n', 'meta');
                }
            }
            return data;
        } catch (e) {
            this.appendOutput(`[ERR] Summary error: ${e.message}\n`, 'error');
            return null;
        }
    }

    /* ────────────────────────────────────────
       MATRIX GRID — Build / Refresh / Animate
       ──────────────────────────────────────── */
    _buildMatrixGrid() {
        if (!this.matrixBody) return;

        let html = '';

        for (const letter of ENGINE_LETTERS) {
            const totalSlots = ENGINE_SLOTS[letter] || 16;
            const subRows = Math.ceil(totalSlots / MAX_DISPLAY_SLOTS);

            for (let sr = 0; sr < subRows; sr++) {
                const startSlot = sr * MAX_DISPLAY_SLOTS + 1;
                const endSlot = Math.min((sr + 1) * MAX_DISPLAY_SLOTS, totalSlots);
                const rowLabel = subRows > 1
                    ? `${letter}${sr > 0 ? ' ' + (startSlot) + '-' + endSlot : ''}`
                    : letter;

                html += `<div class="exec-matrix-row" id="matrix-row-${letter}-${sr}">`;
                html += `<span class="exec-matrix-engine-label" data-engine="${letter}" title="${ENGINE_NAMES[letter]}${subRows > 1 ? ' [' + startSlot + '-' + endSlot + ']' : ''}">${rowLabel}</span>`;
                html += '<div class="exec-matrix-slots">';
                for (let s = startSlot; s <= startSlot + MAX_DISPLAY_SLOTS - 1; s++) {
                    if (s > totalSlots) {
                        html += '<span class="exec-matrix-cell slot-disabled"></span>';
                    } else {
                        const addr = `${letter}${s}`;
                        html += `<span class="exec-matrix-cell slot-empty" id="mcell-${addr}" data-addr="${addr}"></span>`;
                    }
                }
                html += '</div></div>';
            }
        }

        this.matrixBody.innerHTML = html;
    }

    async _refreshMatrix() {
        try {
            const resp = await fetch('/api/registry/matrix');
            const data = await resp.json();
            if (!data.success) return;

            let committed = 0, hotSwap = 0, total = 0;
            this._matrixState = {};

            const engines = data.engines || {};
            for (const engineName of Object.keys(engines)) {
                const row = engines[engineName];
                const letter = row.letter;
                const engineMaxSlots = row.max_slots || ENGINE_SLOTS[letter] || 16;

                const subRows = Math.ceil(engineMaxSlots / MAX_DISPLAY_SLOTS);
                let rowHasNodes = false;

                for (let s = 1; s <= engineMaxSlots; s++) {
                    const addr = `${letter}${s}`;
                    const cell = document.getElementById(`mcell-${addr}`);
                    if (!cell) continue;

                    const slotData = row.slots?.[String(s)];
                    cell.className = 'exec-matrix-cell';
                    cell.title = '';
                    cell.textContent = '';

                    if (!slotData || !slotData.node_id) {
                        cell.classList.add('slot-empty');
                        this._matrixState[addr] = 'empty';
                    } else {
                        total++;
                        rowHasNodes = true;
                        const needsSwap = slotData.needs_swap;
                        if (needsSwap) {
                            cell.classList.add('slot-hot-swap');
                            this._matrixState[addr] = 'hot-swap';
                            hotSwap++;
                        } else {
                            cell.classList.add('slot-committed');
                            this._matrixState[addr] = 'committed';
                            committed++;
                        }
                        cell.textContent = '';
                        cell.title = `${addr.toUpperCase()} \u2014 ${slotData.node_id?.slice(0, 8)}\u2026 v${slotData.version}`;
                    }
                }

                for (let sr = 0; sr < subRows; sr++) {
                    const rowEl = document.getElementById(`matrix-row-${letter}-${sr}`);
                    rowEl?.classList.toggle('row-active', rowHasNodes);
                }
            }

            if (this.matrixStats) {
                this.matrixStats.textContent = `${committed} committed · ${hotSwap} pending · ${total} total`;
            }
        } catch (e) {
            console.error('LiveExec: _refreshMatrix failed', e);
        }
    }

    _flashCell(addr, state, durationMs = 0) {
        const cell = document.getElementById(`mcell-${addr}`);
        if (!cell) return;
        cell.className = `exec-matrix-cell slot-${state}`;
        this._matrixState[addr] = state;
        if (durationMs > 0) {
            setTimeout(() => {
                cell.className = 'exec-matrix-cell slot-committed';
                cell.textContent = 'committed';
                this._matrixState[addr] = 'committed';
            }, durationMs);
        }
    }

    /* ────────────────────────────────────────
       NODE LIST
       ──────────────────────────────────────── */
    async refreshNodes() {
        try {
            this.setStatus('Loading…', 'running');
            const resp = await fetch('/api/execution/ledger/nodes');
            const data = await resp.json();
            
            if (data.success) {
                this.nodes = data.nodes;
                this.renderNodeList();
                this.setStatus(`${this.nodes.length} nodes · ${this.mode}`, 'idle');
            } else {
                this.setStatus('Error loading nodes', 'error');
            }
        } catch (e) {
            this.setStatus('Connection error', 'error');
            console.error('LiveExec: refreshNodes failed', e);
        }
    }

    renderNodeList() {
        if (!this.nodeList) return;
        
        if (this.nodes.length === 0) {
            this.nodeList.innerHTML = `
                <div class="exec-empty">
                    <span class="exec-empty-icon">import</span>
                    <p>No nodes in ledger yet.</p>
                    <p class="exec-empty-hint">Import a file or create nodes to get started.</p>
                </div>`;
            return;
        }

        this.nodeList.innerHTML = this.nodes.map(node => {
            const isSelected = node.id === this.selectedNodeId;
            const langBadge = this._langBadge(node.language);
            const typeBadge = this._typeBadge(node.node_type);
            const execCount = node.execution_count || 0;
            const lastStatus = node.last_execution
                ? (node.last_execution.success ? '' : '')
                : '';

            return `
                <div class="exec-node-item ${isSelected ? 'selected' : ''}"
                     data-node-id="${node.id}"
                     onclick="window.liveExec?.selectNode('${node.id}')">
                    <div class="exec-node-header">
                        <span class="exec-node-name" title="${node.raw_name}">${node.display_name}</span>
                        <span class="exec-node-status">${lastStatus}</span>
                    </div>
                    <div class="exec-node-meta">
                        ${langBadge} ${typeBadge}
                        <span class="exec-node-version">v${node.version}</span>
                        ${execCount > 0 ? `<span class="exec-node-runs" title="${execCount} executions">${execCount}</span>` : ''}
                    </div>
                </div>`;
        }).join('');
    }

    _langBadge(lang) {
        const color = '#555555';
        return `<span class="exec-badge" style="background:${color}">${lang}</span>`;
    }

    _typeBadge(type) {
        const icons = {
            function: '', class: '', variable: '', method: '·',
            control_flow: '', import: '', module: '',
        };
        return `<span class="exec-badge exec-badge-type">${icons[type] || '?'} ${type}</span>`;
    }

    selectNode(nodeId) {
        this.selectedNodeId = nodeId;
        this.renderNodeList();
        
        const node = this.nodes.find(n => n.id === nodeId);
        if (node) {
            this.showCodePreview(node);
            this.loadExecutionHistory(nodeId);
        }
    }

    showCodePreview(node) {
        const previewEl = document.getElementById('exec-code-preview');
        if (!previewEl) return;
        
        const code = node.source_code || '# (no source code)';
        const lines = code.split('\n');
        const truncated = lines.length > 25 ? lines.slice(0, 25).join('\n') + '\n# ...' : code;
        
        previewEl.innerHTML = `
            <div class="exec-code-header">
                <span>${node.display_name}</span>
                <span class="exec-code-lang">${node.language} · v${node.version}</span>
            </div>
            <pre class="exec-code-block">${this._escapeHtml(truncated)}</pre>`;
    }

    async loadExecutionHistory(nodeId) {
        if (!this.historyArea) return;
        
        try {
            const resp = await fetch(`/api/execution/ledger/history/${nodeId}`);
            const data = await resp.json();
            
            if (data.success && data.history.length > 0) {
                this.historyArea.innerHTML = data.history.slice(-10).reverse().map(entry => {
                    const time = new Date(entry.timestamp * 1000).toLocaleTimeString();
                    const statusIcon = entry.success ? '' : '';
                    const execTime = (entry.execution_time * 1000).toFixed(1);
                    return `
                        <div class="exec-history-entry ${entry.success ? '' : 'error'}">
                            <span class="exec-history-status">${statusIcon}</span>
                            <span class="exec-history-time">${time}</span>
                            <span class="exec-history-duration">${execTime}ms</span>
                            <span class="exec-history-version">v${entry.code_version}</span>
                        </div>`;
                }).join('');
            } else {
                this.historyArea.innerHTML = '<div class="exec-empty-hint">No execution history yet</div>';
            }
        } catch (e) {
            this.historyArea.innerHTML = '<div class="exec-empty-hint">Error loading history</div>';
        }
    }

    /* ────────────────────────────────────────
       RUN — branches on this.mode
       ──────────────────────────────────────── */
    async runSelected() {
        if (!this.selectedNodeId) {
            this.appendOutput('No node selected. Click a node first.\n', 'warn');
            return;
        }
        if (this.mode === 'registry') {
            return this._runSelectedViaRegistry();
        }
        return this._runSelectedViaLedger();
    }

    async runAll() {
        if (this.mode === 'registry') {
            return this._runAllViaRegistry();
        }
        return this._runAllViaLedger();
    }

    /* ── Ledger-direct paths ── */

    async _runSelectedViaLedger() {
        const node = this.nodes.find(n => n.id === this.selectedNodeId);
        if (!node) return;

        this.setStatus(`Running ${node.display_name}…`, 'running');
        this.appendOutput(`\nLedger Running: ${node.display_name} (v${node.version})\n`, 'info');

        try {
            const resp = await fetch(`/api/execution/ledger/run/${this.selectedNodeId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await resp.json();

            if (data.success && data.result) {
                const r = data.result;
                if (r.output) this.appendOutput(r.output, 'output');
                if (r.error) this.appendOutput(`[ERR] Error: ${r.error}\n`, 'error');
                this.appendOutput(` ${(r.execution_time * 1000).toFixed(1)}ms\n`, 'meta');
                this.setStatus(r.error ? 'Error' : 'Done', r.error ? 'error' : 'success');
            } else {
                this.appendOutput(` ${data.error || 'Unknown error'}\n`, 'error');
                this.setStatus('Error', 'error');
            }
            
            this.refreshVariables();
            this.loadExecutionHistory(this.selectedNodeId);
            this.refreshNodes();
        } catch (e) {
            this.appendOutput(` Network error: ${e.message}\n`, 'error');
            this.setStatus('Error', 'error');
        }
    }

    async _runAllViaLedger() {
        this.setStatus('Running all…', 'running');
        this.appendOutput('\n Ledger Running All Nodes \n', 'info');

        try {
            const resp = await fetch('/api/execution/ledger/run-all', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ continue_on_error: true })
            });
            const data = await resp.json();

            if (data.success) {
                for (const r of data.results) {
                    this.appendOutput(`\n ${r.node_name}:\n`, 'info');
                    if (r.output) this.appendOutput(r.output, 'output');
                    if (r.error) this.appendOutput(`   ${r.error}\n`, 'error');
                }
                const s = data.summary;
                this.appendOutput(
                    `\n━━━ Summary: ${s.passed}/${s.total_nodes} passed, ` +
                    `${(s.total_time * 1000).toFixed(1)}ms total ━━━\n`, 'meta'
                );
                this.setStatus(`${s.passed}/${s.total_nodes} passed`, s.failed > 0 ? 'error' : 'success');
            } else {
                this.appendOutput(` ${data.error}\n`, 'error');
                this.setStatus('Error', 'error');
            }

            this.refreshVariables();
            this.refreshNodes();
        } catch (e) {
            this.appendOutput(` Network error: ${e.message}\n`, 'error');
            this.setStatus('Error', 'error');
        }
    }

    /* ── Registry-backed paths ── */

    async _runSelectedViaRegistry() {
        const node = this.nodes.find(n => n.id === this.selectedNodeId);
        if (!node) return;

        this.setStatus(`Registry: committing ${node.display_name}…`, 'running');
        this.appendOutput(`\n⬡ [Registry] Committing: ${node.display_name}\n`, 'info');

        try {
            const commitResp = await fetch('/api/registry/commit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ node_id: this.selectedNodeId })
            });
            const commitData = await commitResp.json();

            let slotAddr = null;
            if (commitData.success && commitData.slot) {
                slotAddr = commitData.slot.address;
                this.appendOutput(`  → Slot ${slotAddr.toUpperCase()} (v${commitData.slot.committed_version})\n`, 'meta');
                this._flashCell(slotAddr, 'executing');
                await this._refreshMatrix();
            } else {
                this.appendOutput(`   Commit to registry failed: ${commitData.error || 'unknown'}\n`, 'warn');
            }

            this.setStatus(`Registry: running ${node.display_name}…`, 'running');
            const runResp = await fetch(`/api/execution/ledger/run/${this.selectedNodeId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const runData = await runResp.json();

            let success = false;
            if (runData.success && runData.result) {
                const r = runData.result;
                if (r.output) this.appendOutput(r.output, 'output');
                if (r.error) this.appendOutput(` Error: ${r.error}\n`, 'error');
                this.appendOutput(`⏱ ${(r.execution_time * 1000).toFixed(1)}ms\n`, 'meta');
                success = !r.error;
                this.setStatus(success ? 'Done' : 'Error', success ? 'success' : 'error');
            } else {
                this.appendOutput(` ${runData.error || 'Unknown error'}\n`, 'error');
                this.setStatus('Error', 'error');
            }

            if (slotAddr) {
                try {
                    await fetch('/api/registry/record-execution', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ node_id: this.selectedNodeId, success })
                    });
                } catch (_) {}
                this._flashCell(slotAddr, success ? 'success' : 'error', 2500);
            }

            this.refreshVariables();
            this.loadExecutionHistory(this.selectedNodeId);
            this.refreshNodes();
            setTimeout(() => this._refreshMatrix(), 3000);
        } catch (e) {
            this.appendOutput(` Network error: ${e.message}\n`, 'error');
            this.setStatus('Error', 'error');
        }
    }

    async _runAllViaRegistry() {
        this.setStatus('Registry: committing all…', 'running');
        this.appendOutput('\n━━━ [Registry] Commit All & Run ━━━\n', 'info');

        try {
            const commitResp = await fetch('/api/registry/commit-all', { method: 'POST' });
            const commitData = await commitResp.json();
            if (commitData.success) {
                this.appendOutput(`   Committed ${commitData.committed ?? '?'} node(s) to registry\n`, 'meta');
            } else {
                this.appendOutput(`   Commit-all error: ${commitData.error || 'unknown'}\n`, 'warn');
            }
            await this._refreshMatrix();

            this.setStatus('Registry: running all…', 'running');
            const runResp = await fetch('/api/execution/ledger/run-all', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ continue_on_error: true })
            });
            const runData = await runResp.json();

            if (runData.success) {
                for (const r of runData.results) {
                    this.appendOutput(`\n ${r.node_name}:\n`, 'info');
                    if (r.output) this.appendOutput(r.output, 'output');
                    if (r.error) this.appendOutput(`   ${r.error}\n`, 'error');

                    const slotAddr = await this._findSlotAddr(r.node_id);
                    if (slotAddr) {
                        const ok = !r.error;
                        this._flashCell(slotAddr, ok ? 'success' : 'error', 3000);
                        fetch('/api/registry/record-execution', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ node_id: r.node_id, success: ok })
                        }).catch(() => {});
                    }
                }

                const s = runData.summary;
                this.appendOutput(
                    `\n━━━ Summary: ${s.passed}/${s.total_nodes} passed, ` +
                    `${(s.total_time * 1000).toFixed(1)}ms total ━━━\n`, 'meta'
                );
                this.setStatus(`${s.passed}/${s.total_nodes} passed`, s.failed > 0 ? 'error' : 'success');
            } else {
                this.appendOutput(` ${runData.error}\n`, 'error');
                this.setStatus('Error', 'error');
            }

            this.refreshVariables();
            this.refreshNodes();
            setTimeout(() => this._refreshMatrix(), 3500);
        } catch (e) {
            this.appendOutput(` Network error: ${e.message}\n`, 'error');
            this.setStatus('Error', 'error');
        }
    }

    async _findSlotAddr(nodeId) {
        try {
            const resp = await fetch(`/api/registry/node/${nodeId}/slot`);
            const data = await resp.json();
            return data.success ? data.slot?.address : null;
        } catch (_) {
            return null;
        }
    }

    /* ────────────────────────────────────────
       RESET / VARIABLES / OUTPUT
       ──────────────────────────────────────── */
    async resetExecutor() {
        try {
            await fetch('/api/execution/ledger/reset', { method: 'POST' });
            this.clearOutput();
            this.appendOutput(' Executor reset — namespace cleared.\n', 'info');
            this.setStatus('Reset', 'idle');
            this.refreshVariables();
            if (this.mode === 'registry') this._refreshMatrix();
        } catch (e) {
            this.appendOutput(`[ERR] Reset failed: ${e.message}\n`, 'error');
        }
    }

    async refreshVariables() {
        if (!this.variablesArea) return;
        
        try {
            const resp = await fetch('/api/execution/ledger/variables');
            const data = await resp.json();
            
            if (data.success) {
                this.variables = data.variables;
                this.renderVariables();
            }
        } catch (e) {
            console.error('LiveExec: refreshVariables failed', e);
        }
    }

    renderVariables() {
        if (!this.variablesArea) return;
        
        const entries = Object.entries(this.variables);
        if (entries.length === 0) {
            this.variablesArea.innerHTML = '<div class="exec-empty-hint">No variables in scope</div>';
            return;
        }

        this.variablesArea.innerHTML = entries.map(([name, info]) => {
            const val = typeof info.value === 'string' ? info.value : JSON.stringify(info.value);
            const truncVal = val.length > 80 ? val.slice(0, 80) + '…' : val;
            return `
                <div class="exec-var-row">
                    <span class="exec-var-name">${this._escapeHtml(name)}</span>
                    <span class="exec-var-type">${info.type}</span>
                    <span class="exec-var-value" title="${this._escapeHtml(val)}">${this._escapeHtml(truncVal)}</span>
                </div>`;
        }).join('');
    }

    appendOutput(text, type = 'output') {
        if (!this.outputArea) return;
        const span = document.createElement('span');
        span.className = `exec-output-${type}`;
        span.textContent = text;
        this.outputArea.appendChild(span);
        this.outputArea.scrollTop = this.outputArea.scrollHeight;
    }

    clearOutput() {
        if (this.outputArea) {
            this.outputArea.innerHTML = '';
        }
    }

    _escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.liveExec = new LiveExecutionPanel();
});
