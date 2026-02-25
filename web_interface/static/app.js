/**
 * Visual Editor Core - Web Interface JavaScript
 * 
 * This file handles all frontend interactions for the visual programming interface.
 */

class VisualEditor {
    constructor() {
        this.socket = null;
        this.canvas = null;
        this.canvasContent = null;
        this.nodesLayer = null;
        this.connectionsLayer = null;
        this.selectionLayer = null;
        this.previewLayer = null;
        
        this.nodes = new Map();
        this.connections = new Map();
        this.selectedNodes = new Set();
        this.selectedConnections = new Set();
        
        this.viewport = {
            zoom: 1.0,
            panX: 0,
            panY: 0,
            width: 0,
            height: 0
        };
        
        this.dragState = {
            isDragging: false,
            dragType: null, // 'node', 'canvas', 'connection'
            startX: 0,
            startY: 0,
            dragTarget: null,
            connectionPreview: null
        };
        
        this.nodeDefinitions = [];
        this.paletteNodes = []; // Store all palette nodes including generated ones
        this.paradigmData = [];
        this.currentParadigm = 'node_based';
        
        // Initialize enhanced components
        this.propertiesPanel = null;
        this.repositoryAnalyzer = null;
        
        // Live execution visualization state
        this.executionState = {
            isExecuting: false,
            currentNode: null,
            executionEvents: [],
            executionSpeed: 1.0,
            highlightDuration: 1500,
            animationEnabled: true
        };

        this.storageKey = 'vpyD.canvasState.v1';
        this.projectKey = 'vpyD.projectMeta.v1';
        this.uiSettingsKey = 'vpyD.uiSettings.v1';
        this.saveTimeoutId = null;
        this.isRestoring = false;
        this.uiSettings = this.loadUiSettings();
        
        // NEW: Store execution sequence for Polyglot Harmony demos
        this.executionSequence = [];

        // Code Dive — immersive full-source overlay (Monaco Editor)
        this.codeDive = {
            active: false,
            nodeId: null,
            savedViewport: null,   // { zoom, panX, panY } before the dive
            overlay: null,         // DOM element
            editor: null,          // Monaco editor instance
            monaco: null,          // Monaco namespace reference
        };
        
        this.init();
    }
    
    async init() {
        console.log('Initializing Visual Editor...');
        
        // Initialize DOM elements
        this.initializeElements();
        
        // Initialize enhanced components
        this.initializeEnhancedComponents();
        
        // Initialize WebSocket connection
        this.initializeSocket();
        
        // Initialize event listeners
        this.initializeEventListeners();
        
        // Initialize live execution visualization
        this.initializeLiveExecution();
        
        // Load initial data
        await this.loadInitialData();
        
        // Restore canvas state from browser storage if available
        await this.restoreCanvasState();

        // Initialize project metadata and session controls
        this.initializeProjectMeta();
        this.initializeSessionControls();
        this.initializeGlobalSettingsControls();
        
        // Initialize Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
        
        console.log('Visual Editor initialized successfully');
    }
    
    initializeEnhancedComponents() {
        // Initialize enhanced properties panel
        if (typeof PropertiesPanel !== 'undefined') {
            this.propertiesPanel = new PropertiesPanel(this);
        }
        
        // Initialize repository analyzer
        if (typeof RepositoryAnalyzer !== 'undefined') {
            this.repositoryAnalyzer = new RepositoryAnalyzer(this);
            
            // Make it globally available for UIR translation panel
            window.repositoryAnalyzer = this.repositoryAnalyzer;
            
            this.initializeRepositoryImport();
        }
        
        // Initialize AI Chat panel
        if (typeof AIChat !== 'undefined') {
            this.aiChat = new AIChat(this);
            console.log('AI Chat panel initialized');
        }
    }
    
    initializeRepositoryImport() {
        // Add repository import functionality to the header
        const headerRight = document.querySelector('.header-right');
        if (headerRight) {
            const importBtn = document.createElement('button');
            importBtn.id = 'import-repo-btn';
            importBtn.className = 'btn btn-secondary';
            importBtn.innerHTML = '<i data-lucide="upload"></i> Import Repository';
            importBtn.addEventListener('click', this.showRepositoryImportDialog.bind(this));
            
            const importFileBtn = document.createElement('button');
            importFileBtn.id = 'import-file-btn';
            importFileBtn.className = 'btn btn-secondary';
            importFileBtn.innerHTML = '<i data-lucide="file-plus"></i> Import File';
            importFileBtn.addEventListener('click', this.showFileImportDialog.bind(this));
            
            // Export Clean Code button
            const exportBtn = document.createElement('button');
            exportBtn.id = 'export-code-btn';
            exportBtn.className = 'btn btn-primary';
            exportBtn.innerHTML = '<i data-lucide="download"></i> Export Code';
            exportBtn.addEventListener('click', this.showExportCodeDialog.bind(this));
            
            // Multi-Debugger button
            const debugBtn = document.createElement('button');
            debugBtn.id = 'multi-debug-btn';
            debugBtn.className = 'btn btn-secondary';
            debugBtn.innerHTML = '<i data-lucide="bug"></i> Multi-Debug';
            debugBtn.addEventListener('click', this.showMultiDebuggerPanel.bind(this));
            
            headerRight.insertBefore(importBtn, headerRight.firstChild);
            headerRight.insertBefore(importFileBtn, importBtn.nextSibling);
            headerRight.insertBefore(exportBtn, importFileBtn.nextSibling);
            headerRight.insertBefore(debugBtn, exportBtn.nextSibling);
            
            // Refresh Lucide icons for newly added buttons
            if (window.lucide) {
                window.lucide.createIcons();
            }
        }
    }
    
    showRepositoryImportDialog() {
        const dialog = document.createElement('div');
        dialog.className = 'repository-import-dialog';
        dialog.innerHTML = `
            <div class="dialog-content">
                <h3>Import Repository</h3>
                
                <div class="import-options">
                    <div class="option-group">
                        <label for="import-mode">Import Mode:</label>
                        <select id="import-mode" class="import-select">
                            <option value="full-analysis">Full Analysis (Parse & Visualize)</option>
                            <option value="visual-only">Visual Nodes Only</option>
                            <option value="uir-only">UIR Translation Only</option>
                            <option value="dependency-map">Dependency Map Only</option>
                        </select>
                    </div>
                    
                    <div class="option-group">
                        <label for="dependency-strategy">Dependencies / Imports:</label>
                        <select id="dependency-strategy" class="import-select" title="How to handle import statements and external dependencies">
                            <option value="preserve" selected>Preserve Pointers (keep import statements as-is)</option>
                            <option value="ignore">Ignore (strip all imports)</option>
                            <option value="consolidate">Consolidate (resolve &amp; inline dependency source)</option>
                            <option value="refactor_export">Refactor &amp; Export (consolidate + immediate re-export)</option>
                        </select>
                    </div>
                    
                    <div class="option-group">
                        <label for="target-language">Target Language (for translation):</label>
                        <select id="target-language" class="import-select">
                            <option value="">Keep Original</option>
                            <optgroup label="Popular">
                                <option value="python">Python</option>
                                <option value="javascript">JavaScript</option>
                                <option value="typescript">TypeScript</option>
                            </optgroup>
                            <optgroup label="JVM Languages">
                                <option value="java">Java</option>
                                <option value="kotlin">Kotlin</option>
                                <option value="scala">Scala</option>
                            </optgroup>
                            <optgroup label="Systems Languages">
                                <option value="c">C</option>
                                <option value="rust">Rust</option>
                                <option value="go">Go</option>
                            </optgroup>
                            <optgroup label=".NET / Apple">
                                <option value="csharp">C#</option>
                                <option value="swift">Swift</option>
                            </optgroup>
                            <optgroup label="Scripting">
                                <option value="ruby">Ruby</option>
                                <option value="php">PHP</option>
                                <option value="lua">Lua</option>
                                <option value="r">R</option>
                            </optgroup>
                            <optgroup label="Other">
                                <option value="bash">Bash</option>
                                <option value="sql">SQL</option>
                            </optgroup>
                        </select>
                    </div>
                </div>
                
                <div class="repository-import" id="repo-drop-zone">
                    <div class="import-icon">📁</div>
                    <div class="import-text">Drop repository files here</div>
                    <div class="import-subtext">or click to browse</div>
                    <div class="supported-languages">
                        Supported: Python, JavaScript, TypeScript, Java, Kotlin, Scala, C, Rust, Go, C#, Swift, Ruby, PHP, Lua, R, Bash, SQL
                    </div>
                    <input type="file" id="repo-file-input" multiple webkitdirectory style="display: none;">
                </div>
                <div class="dialog-actions">
                    <button onclick="this.closest('.repository-import-dialog').remove()">Cancel</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(dialog);
        
        const dropZone = document.getElementById('repo-drop-zone');
        const fileInput = document.getElementById('repo-file-input');
        
        // File input handling
        dropZone.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                const importMode = document.getElementById('import-mode').value;
                const targetLanguage = document.getElementById('target-language').value;
                const dependencyStrategy = document.getElementById('dependency-strategy').value;
                this.handleRepositoryImport(Array.from(e.target.files), { importMode, targetLanguage, dependencyStrategy });
                dialog.remove();
            }
        });
        
        // Drag and drop handling
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
        
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('dragover');
        });
        
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            
            const files = Array.from(e.dataTransfer.files);
            if (files.length > 0) {
                const importMode = document.getElementById('import-mode').value;
                const targetLanguage = document.getElementById('target-language').value;
                const dependencyStrategy = document.getElementById('dependency-strategy').value;
                this.handleRepositoryImport(files, { importMode, targetLanguage, dependencyStrategy });
                dialog.remove();
            }
        });
    }

    showFileImportDialog() {
        const dialog = document.createElement('div');
        dialog.className = 'repository-import-dialog';
        dialog.innerHTML = `
            <div class="dialog-content">
                <h3>Import File</h3>
                
                <div class="import-options">
                    <div class="option-group">
                        <label for="file-import-mode">Import Mode:</label>
                        <select id="file-import-mode" class="import-select">
                            <option value="full-analysis">Full Analysis (Parse & Visualize)</option>
                            <option value="visual-only">Visual Nodes Only</option>
                            <option value="uir-only">UIR Translation Only</option>
                        </select>
                    </div>
                    
                    <div class="option-group">
                        <label for="file-dependency-strategy">Dependencies / Imports:</label>
                        <select id="file-dependency-strategy" class="import-select" title="How to handle import statements and external dependencies">
                            <option value="preserve" selected>Preserve Pointers (keep import statements as-is)</option>
                            <option value="ignore">Ignore (strip all imports)</option>
                            <option value="consolidate">Consolidate (resolve &amp; inline dependency source)</option>
                            <option value="refactor_export">Refactor &amp; Export (consolidate + immediate re-export)</option>
                        </select>
                    </div>
                    
                    <div class="option-group">
                        <label for="file-source-language">Source Language (auto-detect if blank):</label>
                        <select id="file-source-language" class="import-select">
                            <option value="">Auto-detect from extension</option>
                            <optgroup label="Popular">
                                <option value="python">Python (.py)</option>
                                <option value="javascript">JavaScript (.js, .mjs)</option>
                                <option value="typescript">TypeScript (.ts, .tsx)</option>
                            </optgroup>
                            <optgroup label="JVM Languages">
                                <option value="java">Java (.java)</option>
                                <option value="kotlin">Kotlin (.kt, .kts)</option>
                                <option value="scala">Scala (.scala, .sc)</option>
                            </optgroup>
                            <optgroup label="Systems Languages">
                                <option value="c">C (.c, .h)</option>
                                <option value="rust">Rust (.rs)</option>
                                <option value="go">Go (.go)</option>
                            </optgroup>
                            <optgroup label=".NET / Apple">
                                <option value="csharp">C# (.cs)</option>
                                <option value="swift">Swift (.swift)</option>
                            </optgroup>
                            <optgroup label="Scripting">
                                <option value="ruby">Ruby (.rb)</option>
                                <option value="php">PHP (.php)</option>
                                <option value="lua">Lua (.lua)</option>
                                <option value="r">R (.R, .r)</option>
                            </optgroup>
                            <optgroup label="Other">
                                <option value="bash">Bash (.sh, .bash)</option>
                                <option value="sql">SQL (.sql)</option>
                            </optgroup>
                        </select>
                    </div>
                    
                    <div class="option-group">
                        <label for="file-target-language">Translate To (optional):</label>
                        <select id="file-target-language" class="import-select">
                            <option value="">Keep Original</option>
                            <optgroup label="Popular">
                                <option value="python">Python</option>
                                <option value="javascript">JavaScript</option>
                                <option value="typescript">TypeScript</option>
                            </optgroup>
                            <optgroup label="JVM Languages">
                                <option value="java">Java</option>
                                <option value="kotlin">Kotlin</option>
                                <option value="scala">Scala</option>
                            </optgroup>
                            <optgroup label="Systems Languages">
                                <option value="c">C</option>
                                <option value="rust">Rust</option>
                                <option value="go">Go</option>
                            </optgroup>
                            <optgroup label=".NET / Apple">
                                <option value="csharp">C#</option>
                                <option value="swift">Swift</option>
                            </optgroup>
                            <optgroup label="Scripting">
                                <option value="ruby">Ruby</option>
                                <option value="php">PHP</option>
                                <option value="lua">Lua</option>
                                <option value="r">R</option>
                            </optgroup>
                            <optgroup label="Other">
                                <option value="bash">Bash</option>
                                <option value="sql">SQL</option>
                            </optgroup>
                        </select>
                    </div>
                </div>
                
                <div class="repository-import" id="file-drop-zone">
                    <div class="import-icon">📄</div>
                    <div class="import-text">Drop a file here</div>
                    <div class="import-subtext">or click to browse</div>
                    <div class="supported-languages">
                        Supported: .py, .js, .ts, .java, .kt, .scala, .c, .rs, .go, .cs, .swift, .rb, .php, .lua, .r, .R, .sh, .sql
                    </div>
                    <input type="file" id="file-input" accept=".py,.js,.mjs,.ts,.tsx,.java,.kt,.kts,.scala,.sc,.c,.h,.rs,.go,.cs,.swift,.rb,.php,.lua,.r,.R,.sh,.bash,.sql" style="display: none;">
                </div>
                <div class="dialog-actions">
                    <button onclick="this.closest('.repository-import-dialog').remove()">Cancel</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(dialog);
        
        const dropZone = document.getElementById('file-drop-zone');
        const fileInput = document.getElementById('file-input');
        
        // File input handling
        dropZone.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                const importMode = document.getElementById('file-import-mode').value;
                const sourceLanguage = document.getElementById('file-source-language').value;
                const targetLanguage = document.getElementById('file-target-language').value;
                const dependencyStrategy = document.getElementById('file-dependency-strategy').value;
                this.handleSingleFileImport(e.target.files[0], { importMode, sourceLanguage, targetLanguage, dependencyStrategy });
                dialog.remove();
            }
        });
        
        // Drag and drop handling
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
        
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('dragover');
        });
        
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            
            const files = Array.from(e.dataTransfer.files);
            if (files.length > 0) {
                const importMode = document.getElementById('file-import-mode').value;
                const sourceLanguage = document.getElementById('file-source-language').value;
                const targetLanguage = document.getElementById('file-target-language').value;
                const dependencyStrategy = document.getElementById('file-dependency-strategy').value;
                this.handleSingleFileImport(files[0], { importMode, sourceLanguage, targetLanguage, dependencyStrategy });
                dialog.remove();
            }
        });
    }
    
    async handleRepositoryImport(files, options = {}) {
        if (this.repositoryAnalyzer) {
            await this.repositoryAnalyzer.importRepository(files, {
                importMode: options.importMode || 'full-analysis',
                targetLanguage: options.targetLanguage || '',
                dependencyStrategy: options.dependencyStrategy || 'preserve',
                progressTitle: 'Analyzing Repository',
                resultsTitle: 'Repository Analysis Complete',
                errorTitle: 'Repository Import Failed'
            });
        }
    }

    async handleSingleFileImport(file, options = {}) {
        if (this.repositoryAnalyzer) {
            await this.repositoryAnalyzer.importFile(file, {
                importMode: options.importMode || 'full-analysis',
                sourceLanguage: options.sourceLanguage || '',
                targetLanguage: options.targetLanguage || '',
                dependencyStrategy: options.dependencyStrategy || 'preserve',
                progressTitle: 'Analyzing File',
                resultsTitle: 'File Analysis Complete',
                errorTitle: 'File Import Failed'
            });
        }
    }
    
    showExportCodeDialog() {
        const dialog = document.createElement('div');
        dialog.className = 'export-code-dialog';
        dialog.innerHTML = `
            <div class="dialog-content">
                <h3>Export Clean Code</h3>
                <p class="dialog-description">Generate standalone, executable code from your visual model</p>
                
                <div class="export-options">
                    <div class="option-group">
                        <label for="export-language">Target Language:</label>
                        <select id="export-language" class="import-select">
                            <optgroup label="Popular">
                                <option value="python" selected>Python</option>
                                <option value="javascript">JavaScript</option>
                                <option value="typescript">TypeScript</option>
                            </optgroup>
                            <optgroup label="JVM Languages">
                                <option value="java">Java</option>
                                <option value="kotlin">Kotlin</option>
                                <option value="scala">Scala</option>
                            </optgroup>
                            <optgroup label="Systems Languages">
                                <option value="c">C</option>
                                <option value="rust">Rust</option>
                                <option value="go">Go</option>
                            </optgroup>
                            <optgroup label=".NET / Apple">
                                <option value="csharp">C#</option>
                                <option value="swift">Swift</option>
                            </optgroup>
                            <optgroup label="Scripting">
                                <option value="ruby">Ruby</option>
                                <option value="php">PHP</option>
                                <option value="lua">Lua</option>
                                <option value="r">R</option>
                            </optgroup>
                            <optgroup label="Other">
                                <option value="bash">Bash</option>
                                <option value="sql">SQL</option>
                            </optgroup>
                        </select>
                    </div>
                    
                    <div class="option-group">
                        <label for="export-entry-point">Entry Point Function:</label>
                        <input type="text" id="export-entry-point" class="import-input" value="main" placeholder="main">
                    </div>
                    
                    <div class="checkbox-options">
                        <label class="checkbox-option">
                            <input type="checkbox" id="export-imports" checked>
                            <span>Include Imports</span>
                        </label>
                        <label class="checkbox-option">
                            <input type="checkbox" id="export-docstrings" checked>
                            <span>Include Docstrings</span>
                        </label>
                        <label class="checkbox-option">
                            <input type="checkbox" id="export-type-hints" checked>
                            <span>Include Type Hints</span>
                        </label>
                        <label class="checkbox-option">
                            <input type="checkbox" id="export-error-handling">
                            <span>Add Error Handling</span>
                        </label>
                        <label class="checkbox-option">
                            <input type="checkbox" id="export-optimize">
                            <span>Optimize Code</span>
                        </label>
                        <label class="checkbox-option">
                            <input type="checkbox" id="export-standalone" checked>
                            <span>Standalone Mode (executable)</span>
                        </label>
                    </div>
                </div>
                
                <div class="dialog-actions">
                    <button class="btn btn-secondary" onclick="this.closest('.export-code-dialog').remove()">Cancel</button>
                    <button class="btn btn-primary" id="export-generate-btn">
                        <i data-lucide="download"></i> Generate & Download
                    </button>
                    <button class="btn btn-secondary" id="export-preview-btn">
                        <i data-lucide="eye"></i> Preview
                    </button>
                </div>
                
                <div class="export-preview-area" id="export-preview" style="display: none;">
                    <div class="preview-header">
                        <h4>Generated Code Preview</h4>
                        <button class="btn btn-sm" id="export-copy-btn">
                            <i data-lucide="copy"></i> Copy
                        </button>
                    </div>
                    <pre class="code-preview"><code id="export-code-content"></code></pre>
                </div>
            </div>
        `;
        
        document.body.appendChild(dialog);
        
        // Initialize Lucide icons
        if (window.lucide) {
            window.lucide.createIcons();
        }
        
        // Add event listeners
        const generateBtn = dialog.querySelector('#export-generate-btn');
        const previewBtn = dialog.querySelector('#export-preview-btn');
        const copyBtn = dialog.querySelector('#export-copy-btn');
        
        generateBtn.addEventListener('click', () => this.handleExportCode(dialog, true));
        previewBtn.addEventListener('click', () => this.handleExportCode(dialog, false));
        copyBtn.addEventListener('click', () => this.copyExportedCode(dialog));

        // Close dialog when clicking outside content
        dialog.addEventListener('click', (e) => {
            if (e.target === dialog) {
                dialog.remove();
            }
        });
    }
    
    async handleExportCode(dialog, download = false) {
        const language = dialog.querySelector('#export-language').value;
        const entryPoint = dialog.querySelector('#export-entry-point').value || 'main';
        const includeImports = dialog.querySelector('#export-imports').checked;
        const includeDocstrings = dialog.querySelector('#export-docstrings').checked;
        const includeTypeHints = dialog.querySelector('#export-type-hints').checked;
        const includeErrorHandling = dialog.querySelector('#export-error-handling').checked;
        const optimizeCode = dialog.querySelector('#export-optimize').checked;
        const standaloneMode = dialog.querySelector('#export-standalone').checked;
        
        // Collect nodes and connections from canvas
        const nodes = [];
        this.nodes.forEach((nodeData, nodeId) => {
            // Extract metadata for UIR-imported nodes
            const metadata = nodeData.metadata || nodeData.parameters?.metadata || {};
            
            nodes.push({
                id: nodeId,
                type: nodeData.type || 'expression',
                name: nodeData.name || nodeData.parameters?.name || 'node',
                x: nodeData.x || 0,
                y: nodeData.y || 0,
                parameters: nodeData.parameters || {},
                code_snippet: nodeData.code_snippet || nodeData.parameters?.body || '',
                metadata: metadata,
                // Include source code from metadata if available
                source_code: metadata.source_code || nodeData.source_code || '',
                raw_name: metadata.raw_name || nodeData.raw_name || '',
                source_language: metadata.source_language || nodeData.source_language || 'python',
                function_type: metadata.function_type || nodeData.function_type || ''
            });
        });
        
        const connections = [];
        this.connections.forEach((connData, connId) => {
            connections.push({
                id: connId,
                source_node: connData.sourceNode,
                source_port: connData.sourcePort,
                target_node: connData.targetNode,
                target_port: connData.targetPort
            });
        });
        
        try {
            const response = await fetch('/api/export/code', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    nodes: nodes,
                    connections: connections,
                    target_language: language,
                    options: {
                        include_imports: includeImports,
                        include_docstrings: includeDocstrings,
                        include_type_hints: includeTypeHints,
                        include_error_handling: includeErrorHandling,
                        optimize_code: optimizeCode,
                        standalone_mode: standaloneMode,
                        entry_point: entryPoint
                    }
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                if (download) {
                    // Download the file
                    this.downloadCode(result.code, language, entryPoint);
                    dialog.remove();
                } else {
                    // Show preview
                    const previewArea = dialog.querySelector('#export-preview');
                    const codeContent = dialog.querySelector('#export-code-content');
                    codeContent.textContent = result.code;
                    previewArea.style.display = 'block';
                    
                    // Apply syntax highlighting if available
                    if (window.hljs) {
                        window.hljs.highlightElement(codeContent);
                    }
                }
            } else {
                alert('Export failed: ' + result.error);
            }
        } catch (error) {
            console.error('Export error:', error);
            alert('Export failed: ' + error.message);
        }
    }
    
    downloadCode(code, language, entryPoint) {
        // Use global LANG_TO_EXT from /api/engines (single source of truth),
        // fall back to a minimal map if the manifest hasn't loaded yet.
        const extensions = (window.LANG_TO_EXT && Object.keys(window.LANG_TO_EXT).length > 0)
            ? window.LANG_TO_EXT
            : {
                'python': 'py', 'javascript': 'js', 'typescript': 'ts',
                'java': 'java', 'kotlin': 'kt', 'scala': 'scala',
                'c': 'c', 'rust': 'rs', 'go': 'go', 'csharp': 'cs',
                'swift': 'swift', 'ruby': 'rb', 'php': 'php', 'lua': 'lua',
                'r': 'R', 'bash': 'sh', 'perl': 'pl', 'sql': 'sql'
              };
        
        const ext = extensions[language] || 'txt';
        const filename = `${entryPoint}.${ext}`;
        
        const blob = new Blob([code], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
    
    copyExportedCode(dialog) {
        const codeContent = dialog.querySelector('#export-code-content');
        if (codeContent) {
            navigator.clipboard.writeText(codeContent.textContent).then(() => {
                const copyBtn = dialog.querySelector('#export-copy-btn');
                const originalHTML = copyBtn.innerHTML;
                copyBtn.innerHTML = '<i data-lucide="check"></i> Copied!';
                if (window.lucide) window.lucide.createIcons();
                setTimeout(() => {
                    copyBtn.innerHTML = originalHTML;
                    if (window.lucide) window.lucide.createIcons();
                }, 2000);
            });
        }
    }
    
    showMultiDebuggerPanel() {
        // Check if panel already exists
        let panel = document.getElementById('multi-debugger-panel');
        if (panel) {
            panel.style.display = panel.style.display === 'none' ? 'flex' : 'none';
            return;
        }
        
        // Create the multi-debugger panel
        panel = document.createElement('div');
        panel.id = 'multi-debugger-panel';
        panel.className = 'multi-debugger-panel';
        panel.innerHTML = `
            <div class="panel-header">
                <h3>Multi-Debugger</h3>
                <div class="panel-controls">
                    <button class="btn btn-sm" id="debug-create-session" title="Create Debug Session">
                        <i data-lucide="plus"></i>
                    </button>
                    <button class="btn btn-sm" id="debug-run-all" title="Run All Sessions">
                        <i data-lucide="play"></i>
                    </button>
                    <button class="btn btn-sm" id="debug-stop-all" title="Stop All Sessions">
                        <i data-lucide="square"></i>
                    </button>
                    <button class="btn btn-sm" id="debug-close-panel" title="Close Panel">
                        <i data-lucide="x"></i>
                    </button>
                </div>
            </div>
            <div class="sessions-container" id="debug-sessions">
                <div class="no-sessions">
                    <p>No debug sessions active</p>
                    <p class="hint">Select nodes and click + to create a debug session</p>
                </div>
            </div>
            <div class="shared-variables">
                <h4>Shared Namespace</h4>
                <div class="variables-list" id="shared-variables-list">
                    <span class="empty-vars">No variables yet</span>
                </div>
            </div>
        `;
        
        document.body.appendChild(panel);
        
        // Initialize Lucide icons
        if (window.lucide) {
            window.lucide.createIcons();
        }
        
        // Set up event listeners
        document.getElementById('debug-create-session').addEventListener('click', () => this.createDebugSession());
        document.getElementById('debug-run-all').addEventListener('click', () => this.runAllDebugSessions());
        document.getElementById('debug-stop-all').addEventListener('click', () => this.stopAllDebugSessions());
        document.getElementById('debug-close-panel').addEventListener('click', () => {
            panel.style.display = 'none';
        });
        
        // Set up WebSocket listeners for debug events
        this.setupDebugSocketListeners();
    }
    
    setupDebugSocketListeners() {
        if (!this.debugSocketInitialized && this.socket) {
            this.debugSocketInitialized = true;
            
            this.socket.on('debug_session_created', (data) => {
                this.addDebugSessionToPanel(data.session_id, data.state);
            });
            
            this.socket.on('debug_session_started', (data) => {
                this.updateDebugSessionState(data.session_id, 'running');
            });
            
            this.socket.on('debug_step_executed', (data) => {
                this.updateDebugStepResult(data.session_id, data.result);
                this.highlightExecutingNode(data.result.node_id);
                this.updateSharedVariables(data.result.variables);
            });
            
            this.socket.on('debug_session_stopped', (data) => {
                this.removeDebugSessionFromPanel(data.session_id);
            });
            
            this.socket.on('all_sessions_completed', (data) => {
                this.handleAllSessionsCompleted(data.results);
            });
        }
    }
    
    async createDebugSession() {
        // Get selected nodes
        const selectedNodes = [];
        this.selectedNodes.forEach(nodeId => {
            const nodeData = this.nodes.get(nodeId);
            if (nodeData) {
                selectedNodes.push({
                    id: nodeId,
                    type: nodeData.type,
                    name: nodeData.name || nodeData.parameters?.name,
                    code_snippet: nodeData.code_snippet || nodeData.parameters?.body || ''
                });
            }
        });
        
        if (selectedNodes.length === 0) {
            alert('Please select nodes to create a debug session');
            return;
        }
        
        try {
            const response = await fetch('/api/execution/multi-debug/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    nodes: selectedNodes,
                    options: { shared_namespace: true }
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.addDebugSessionToPanel(result.session_id, 'created', selectedNodes.length);
            } else {
                alert('Failed to create debug session: ' + result.error);
            }
        } catch (error) {
            console.error('Error creating debug session:', error);
            alert('Failed to create debug session');
        }
    }
    
    addDebugSessionToPanel(sessionId, state, nodeCount = 0) {
        const container = document.getElementById('debug-sessions');
        const noSessions = container.querySelector('.no-sessions');
        if (noSessions) {
            noSessions.style.display = 'none';
        }
        
        const sessionEl = document.createElement('div');
        sessionEl.className = 'debug-session';
        sessionEl.id = `debug-session-${sessionId}`;
        sessionEl.innerHTML = `
            <div class="session-header">
                <span class="session-name">Session ${sessionId.substring(0, 8)}</span>
                <span class="session-state state-${state}">${state}</span>
            </div>
            <div class="session-info">
                <span class="node-count">${nodeCount} nodes</span>
            </div>
            <div class="session-controls">
                <button class="btn btn-sm btn-start" data-session="${sessionId}" title="Start">
                    <i data-lucide="play"></i>
                </button>
                <button class="btn btn-sm btn-step" data-session="${sessionId}" title="Step">
                    <i data-lucide="skip-forward"></i>
                </button>
                <button class="btn btn-sm btn-stop" data-session="${sessionId}" title="Stop">
                    <i data-lucide="square"></i>
                </button>
            </div>
            <div class="session-output" id="session-output-${sessionId}"></div>
        `;
        
        container.appendChild(sessionEl);
        
        // Initialize icons
        if (window.lucide) window.lucide.createIcons();
        
        // Add event listeners
        sessionEl.querySelector('.btn-start').addEventListener('click', () => this.startDebugSession(sessionId));
        sessionEl.querySelector('.btn-step').addEventListener('click', () => this.stepDebugSession(sessionId));
        sessionEl.querySelector('.btn-stop').addEventListener('click', () => this.stopDebugSession(sessionId));
    }
    
    async startDebugSession(sessionId) {
        try {
            const response = await fetch(`/api/execution/multi-debug/start/${sessionId}`, {
                method: 'POST'
            });
            const result = await response.json();
            if (result.success) {
                this.updateDebugSessionState(sessionId, 'running');
            }
        } catch (error) {
            console.error('Error starting debug session:', error);
        }
    }
    
    async stepDebugSession(sessionId) {
        try {
            const response = await fetch(`/api/execution/multi-debug/step/${sessionId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ step_type: 'next' })
            });
            const result = await response.json();
            if (result.success) {
                this.updateDebugStepResult(sessionId, result);
                if (result.node_id) {
                    this.highlightExecutingNode(result.node_id);
                }
                if (result.variables) {
                    this.updateSharedVariables(result.variables);
                }
            }
        } catch (error) {
            console.error('Error stepping debug session:', error);
        }
    }
    
    async stopDebugSession(sessionId) {
        try {
            const response = await fetch(`/api/execution/multi-debug/stop/${sessionId}`, {
                method: 'POST'
            });
            const result = await response.json();
            if (result.success) {
                this.removeDebugSessionFromPanel(sessionId);
            }
        } catch (error) {
            console.error('Error stopping debug session:', error);
        }
    }
    
    async runAllDebugSessions() {
        try {
            const response = await fetch('/api/execution/multi-debug/run-all', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ timeout: 30 })
            });
            const result = await response.json();
            if (result.success) {
                this.handleAllSessionsCompleted(result.results);
            }
        } catch (error) {
            console.error('Error running all debug sessions:', error);
        }
    }
    
    async stopAllDebugSessions() {
        try {
            const response = await fetch('/api/execution/multi-debug/list');
            const result = await response.json();
            if (result.success) {
                for (const session of result.sessions) {
                    await this.stopDebugSession(session.id);
                }
            }
        } catch (error) {
            console.error('Error stopping all debug sessions:', error);
        }
    }
    
    updateDebugSessionState(sessionId, state) {
        const sessionEl = document.getElementById(`debug-session-${sessionId}`);
        if (sessionEl) {
            const stateEl = sessionEl.querySelector('.session-state');
            stateEl.className = `session-state state-${state}`;
            stateEl.textContent = state;
        }
    }
    
    updateDebugStepResult(sessionId, result) {
        const outputEl = document.getElementById(`session-output-${sessionId}`);
        if (outputEl && result) {
            const stepEl = document.createElement('div');
            stepEl.className = 'step-result';
            stepEl.innerHTML = `
                <span class="step-node">${result.node_id?.substring(0, 8) || 'unknown'}</span>
                <span class="step-status">${result.status}</span>
            `;
            outputEl.appendChild(stepEl);
            outputEl.scrollTop = outputEl.scrollHeight;
        }
    }
    
    removeDebugSessionFromPanel(sessionId) {
        const sessionEl = document.getElementById(`debug-session-${sessionId}`);
        if (sessionEl) {
            sessionEl.remove();
        }
        
        // Show "no sessions" message if empty
        const container = document.getElementById('debug-sessions');
        if (container && container.querySelectorAll('.debug-session').length === 0) {
            const noSessions = container.querySelector('.no-sessions');
            if (noSessions) {
                noSessions.style.display = 'block';
            }
        }
        
        // Remove highlight from any nodes
        this.clearExecutionHighlights();
    }
    
    highlightExecutingNode(nodeId) {
        // Remove previous highlight
        this.clearExecutionHighlights();
        
        // Add highlight to current node
        const nodeEl = document.getElementById(`node-${nodeId}`);
        if (nodeEl) {
            nodeEl.classList.add('executing');
        }
    }
    
    clearExecutionHighlights() {
        document.querySelectorAll('.visual-node.executing').forEach(el => {
            el.classList.remove('executing');
        });
    }
    
    updateSharedVariables(variables) {
        const varsList = document.getElementById('shared-variables-list');
        if (!varsList || !variables) return;
        
        varsList.innerHTML = '';
        
        const varNames = Object.keys(variables);
        if (varNames.length === 0) {
            varsList.innerHTML = '<span class="empty-vars">No variables yet</span>';
            return;
        }
        
        varNames.slice(0, 20).forEach(name => {
            // Skip internal/private variables
            if (name.startsWith('_')) return;
            
            const value = variables[name];
            const varEl = document.createElement('div');
            varEl.className = 'variable-item';
            varEl.innerHTML = `
                <span class="var-name">${name}</span>
                <span class="var-value">${this.formatVariableValue(value)}</span>
            `;
            varsList.appendChild(varEl);
        });
    }
    
    formatVariableValue(value) {
        if (value === null) return 'null';
        if (value === undefined) return 'undefined';
        if (typeof value === 'string') return `"${value.substring(0, 50)}${value.length > 50 ? '...' : ''}"`;
        if (typeof value === 'object') return JSON.stringify(value).substring(0, 50) + '...';
        return String(value);
    }
    
    handleAllSessionsCompleted(results) {
        console.log('All debug sessions completed:', results);
        
        // Update all session states
        for (const [sessionId, result] of Object.entries(results)) {
            this.updateDebugSessionState(sessionId, result.state || 'completed');
        }
        
        // Clear execution highlights
        this.clearExecutionHighlights();
    }
    
    initializeElements() {
        this.canvas = document.getElementById('canvas');
        this.canvasContent = document.getElementById('canvas-content');
        this.nodesLayer = document.getElementById('nodes-layer');
        this.connectionsLayer = document.getElementById('connections-layer');
        this.selectionLayer = document.getElementById('selection-layer');
        this.previewLayer = document.getElementById('preview-layer');
        
        // Update viewport dimensions
        const rect = this.canvas.getBoundingClientRect();
        this.viewport.width = rect.width;
        this.viewport.height = rect.height;
    }

    initializeNodeHoverLabel() {
        const label = document.createElement('div');
        label.id = 'node-hover-label';
        label.className = 'node-hover-label';
        label.style.display = 'none';
        document.body.appendChild(label);
        this.hoverLabel = label;
    }
    
    initializeSocket() {
        this.socket = io();
        
        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.updateConnectionStatus(true);
        });
        
        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.updateConnectionStatus(false);
        });
        
        this.socket.on('node_added', (data) => {
            this.addNodeToCanvas(data.node_id, data.node);
        });
        
        this.socket.on('node_removed', (data) => {
            this.removeNodeFromCanvas(data.node_id);
        });
        
        this.socket.on('node_moved', (data) => {
            this.updateNodePosition(data.node_id, data.position);
        });
        
        this.socket.on('connection_added', (data) => {
            this.addConnectionToCanvas(data.connection);
        });
        
        this.socket.on('connection_removed', (data) => {
            this.removeConnectionFromCanvas(data.connection_id);
        });

        this.socket.on('node_parameters_updated', (data) => {
            const nodeData = this.nodes.get(data.node_id);
            if (nodeData) {
                nodeData.parameters = data.parameters || {};
                if (this.selectedNodes.has(data.node_id)) {
                    this.updatePropertiesPanel();
                }
                this.updateNodeTitle(data.node_id);
                this.updateNodeCodePreview(data.node_id);
                this.scheduleSaveCanvasState();
            }
        });

        this.socket.on('node_metadata_updated', (data) => {
            const nodeData = this.nodes.get(data.node_id);
            if (nodeData) {
                nodeData.metadata = data.metadata || {};
                this.updateNodeTitle(data.node_id);
                if (this.selectedNodes.has(data.node_id)) {
                    this.updatePropertiesPanel();
                }
                this.updateNodeCodePreview(data.node_id);
                this.scheduleSaveCanvasState();
            }
        });

        this.socket.on('node_ports_updated', (data) => {
            const nodeData = this.nodes.get(data.node_id);
            if (nodeData) {
                nodeData.inputs = data.inputs || [];
                nodeData.outputs = data.outputs || [];
                this.redrawNode(data.node_id);
                if (this.selectedNodes.has(data.node_id)) {
                    this.updatePropertiesPanel();
                }
                this.scheduleSaveCanvasState();
            }
        });

        this.socket.on('canvas_cleared', () => {
            this.clearCanvas();
        });
        
        this.socket.on('viewport_changed', (data) => {
            this.updateViewport(data);
        });
        
        this.socket.on('paradigm_changed', (data) => {
            this.updateParadigm(data.type);
        });
    }
    
    initializeEventListeners() {
        // Canvas events
        this.canvas.addEventListener('mousedown', this.handleCanvasMouseDown.bind(this));
        this.canvas.addEventListener('mousemove', this.handleCanvasMouseMove.bind(this));
        this.canvas.addEventListener('mouseup', this.handleCanvasMouseUp.bind(this));
        this.canvas.addEventListener('wheel', this.handleCanvasWheel.bind(this));
        this.canvas.addEventListener('contextmenu', this.handleCanvasContextMenu.bind(this));
        this.canvas.addEventListener('mousemove', (event) => {
            this.lastMouse = { x: event.clientX, y: event.clientY };
        });
        
        // Window events
        window.addEventListener('resize', this.handleWindowResize.bind(this));
        window.addEventListener('keydown', this.handleKeyDown.bind(this));
        window.addEventListener('keyup', this.handleKeyUp.bind(this));
        
        // Header controls (with null checks for optional elements)
        const paradigmSelect = document.getElementById('paradigm-select');
        if (paradigmSelect) {
            paradigmSelect.addEventListener('change', this.handleParadigmChange.bind(this));
        }
        
        const validateBtn = document.getElementById('validate-btn');
        if (validateBtn) {
            validateBtn.addEventListener('click', this.handleValidate.bind(this));
        }
        
        const clearBtn = document.getElementById('clear-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', this.handleClear.bind(this));
        }
        
        const zoomFitBtn = document.getElementById('zoom-fit-btn');
        if (zoomFitBtn) {
            zoomFitBtn.addEventListener('click', this.handleZoomFit.bind(this));
        }
        
        // Toolbar controls
        const gridToggle = document.getElementById('grid-toggle');
        if (gridToggle) {
            gridToggle.addEventListener('click', this.handleGridToggle.bind(this));
        }
        
        // Palette events
        const paletteSearch = document.getElementById('palette-search');
        if (paletteSearch) {
            paletteSearch.addEventListener('input', this.handlePaletteSearch.bind(this));
        }
        
        // Category headers
        document.querySelectorAll('.category-header').forEach(header => {
            header.addEventListener('click', this.handleCategoryToggle.bind(this));
        });
        
        // Context menu
        document.addEventListener('click', this.handleDocumentClick.bind(this));
        
        // Properties panel
        const propPosX = document.getElementById('prop-pos-x');
        if (propPosX) {
            propPosX.addEventListener('change', this.handlePositionChange.bind(this));
        }
        
        const propPosY = document.getElementById('prop-pos-y');
        if (propPosY) {
            propPosY.addEventListener('change', this.handlePositionChange.bind(this));
        }
        
        // Generate Nodes modal
        const generateNodesBtn = document.getElementById('generate-nodes-btn');
        if (generateNodesBtn) {
            generateNodesBtn.addEventListener('click', () => this.showGenerateNodesModal());
        }
        
        this.initializeGenerateNodesModal();
        
        // AST-Grep Pattern Search modal
        const astGrepBtn = document.getElementById('ast-grep-btn');
        if (astGrepBtn) {
            astGrepBtn.addEventListener('click', () => this.showAstGrepModal());
        }
        
        this.initializeAstGrepModal();
    }
    
    async loadInitialData() {
        try {
            // Load paradigm information first
            await this.loadParadigmData();
            
            // Load node palette for current paradigm
            await this.loadNodePalette();
            
            // Load existing nodes
            const nodesResponse = await fetch('/api/canvas/nodes');
            const nodesData = await nodesResponse.json();
            if (nodesData.success) {
                Object.entries(nodesData.data).forEach(([nodeId, node]) => {
                    this.addNodeToCanvas(nodeId, node);
                });
            }
            
            // Load existing connections
            const connectionsResponse = await fetch('/api/canvas/connections');
            const connectionsData = await connectionsResponse.json();
            if (connectionsData.success) {
                connectionsData.data.forEach(connection => {
                    this.addConnectionToCanvas(connection);
                });
            }
            
            // Load viewport state
            const viewportResponse = await fetch('/api/canvas/viewport');
            const viewportData = await viewportResponse.json();
            if (viewportData.success) {
                this.updateViewport(viewportData.data);
            }
            
            // Update status
            this.updateStatus();
            
        } catch (error) {
            console.error('Error loading initial data:', error);
        }
    }
    
    async loadParadigmData() {
        try {
            const response = await fetch('/api/paradigms');
            const data = await response.json();
            if (data.success) {
                this.paradigmData = data.data;
                
                // Update paradigm selector
                const paradigmSelect = document.getElementById('paradigm-select');
                if (paradigmSelect) {
                    paradigmSelect.innerHTML = '';
                    this.paradigmData.forEach(paradigm => {
                        const option = document.createElement('option');
                        option.value = paradigm.type;
                        option.textContent = paradigm.name;
                        option.selected = paradigm.active;
                        paradigmSelect.appendChild(option);
                        
                        if (paradigm.active) {
                            this.currentParadigm = paradigm.type;
                        }
                    });
                }
            }
        } catch (error) {
            console.error('Error loading paradigm data:', error);
        }
    }
    
    async loadNodePalette() {
        try {
            // Load ALL nodes across all paradigms by default
            const response = await fetch(`/api/palette/nodes?paradigm=all`);
            const data = await response.json();
            if (data.success) {
                this.nodeDefinitions = data.data;
                this.paletteNodes = data.data; // Store for later reference
                this.populateNodePalette();
            }
        } catch (error) {
            console.error('Error loading node palette:', error);
        }
    }
    
    renderNodePalette() {
        // Re-render palette with current nodes
        this.nodeDefinitions = this.paletteNodes || [];
        this.populateNodePalette();
    }
    
    populateNodePalette() {
        // Group nodes by category
        const categories = {};
        this.nodeDefinitions.forEach(node => {
            if (!categories[node.category]) {
                categories[node.category] = [];
            }
            categories[node.category].push(node);
        });
        
        // Clear existing palette content
        const paletteContent = document.querySelector('.palette-content');
        if (!paletteContent) return;
        
        paletteContent.innerHTML = '';
        
        // Populate each category
        Object.entries(categories).forEach(([category, nodes]) => {
            const categoryElement = this.createCategoryElement(category, nodes);
            paletteContent.appendChild(categoryElement);
        });

        // Open first category by default
        const firstCategory = paletteContent.querySelector('.palette-category .category-nodes');
        const firstIcon = paletteContent.querySelector('.palette-category .category-icon');
        if (firstCategory) {
            firstCategory.style.display = 'block';
        }
        if (firstIcon) {
            firstIcon.setAttribute('data-lucide', 'chevron-down');
        }
        
        // Update Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }
    
    createCategoryElement(categoryName, nodes) {
        const categoryDiv = document.createElement('div');
        categoryDiv.className = 'palette-category';
        categoryDiv.dataset.category = categoryName;
        
        // Category header
        const header = document.createElement('div');
        header.className = 'category-header';
        header.innerHTML = `
            <i data-lucide="chevron-down" class="category-icon"></i>
            <span class="category-name">${categoryName}</span>
            <span class="category-count">(${nodes.length})</span>
        `;
        header.addEventListener('click', this.handleCategoryToggle.bind(this));
        categoryDiv.appendChild(header);
        
        // Category nodes container
        const nodesContainer = document.createElement('div');
        nodesContainer.className = 'category-nodes';
        
        nodes.forEach(node => {
            const nodeElement = this.createPaletteNodeElement(node);
            nodesContainer.appendChild(nodeElement);
        });
        
        categoryDiv.appendChild(nodesContainer);
        return categoryDiv;
    }
    
    createPaletteNodeElement(nodeDefinition) {
        const element = document.createElement('div');
        element.className = 'palette-node';
        element.draggable = true;
        element.dataset.nodeType = nodeDefinition.type;
        element.dataset.nodeId = nodeDefinition.id;
        element.dataset.paradigm = nodeDefinition.paradigm || this.currentParadigm;
        
        // Add paradigm-specific styling
        if (nodeDefinition.paradigm) {
            element.classList.add(`paradigm-${nodeDefinition.paradigm.replace('_', '-')}`);
        }
        
        // Create node content based on paradigm
        let nodeContent = '';
        
        if (this.currentParadigm === 'block_based' && nodeDefinition.color) {
            element.style.setProperty('--node-color', nodeDefinition.color);
            element.classList.add('block-node');
        }
        
        // Check if we have a custom PNG image for this node type
        const customImagePath = this.getCustomNodeImage(nodeDefinition.type, nodeDefinition);
        
        if (customImagePath) {
            // Use PNG image in palette
            nodeContent = `
                <div class="node-icon-container image-container">
                    <img src="${customImagePath}" class="node-image-icon" alt="${nodeDefinition.name}">
                </div>
                <div class="node-info">
                    <div class="node-name">${nodeDefinition.name}</div>
                    <div class="node-description">${nodeDefinition.description}</div>
                </div>
            `;
        } else {
            // Use Lucide icon
            nodeContent = `
                <div class="node-icon-container">
                    <i data-lucide="${nodeDefinition.icon}" class="node-icon"></i>
                </div>
                <div class="node-info">
                    <div class="node-name">${nodeDefinition.name}</div>
                    <div class="node-description">${nodeDefinition.description}</div>
                </div>
            `;
        }
        
        // Add paradigm-specific indicators
        if (nodeDefinition.paradigm && nodeDefinition.paradigm !== this.currentParadigm) {
            nodeContent += `<div class="paradigm-indicator">${nodeDefinition.paradigm}</div>`;
        }
        
        // Add type-specific indicators
        if (nodeDefinition.temporal_type) {
            nodeContent += `<div class="temporal-indicator">${nodeDefinition.temporal_type}</div>`;
        }
        
        if (nodeDefinition.stereotype) {
            nodeContent += `<div class="stereotype-indicator">${nodeDefinition.stereotype}</div>`;
        }
        
        element.innerHTML = nodeContent;
        
        // Add drag events
        element.addEventListener('dragstart', this.handlePaletteDragStart.bind(this));
        element.addEventListener('dragend', this.handlePaletteDragEnd.bind(this));
        
        // Add click event for additional info
        element.addEventListener('click', (e) => {
            if (e.detail === 2) { // Double click
                this.showNodeDefinitionDetails(nodeDefinition);
            }
        });
        
        return element;
    }
    
    showNodeDefinitionDetails(nodeDefinition) {
        // Create a modal or popup showing detailed node information
        const modal = document.createElement('div');
        modal.className = 'node-details-modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3><i data-lucide="${nodeDefinition.icon}"></i> ${nodeDefinition.name}</h3>
                    <button class="close-btn" onclick="this.closest('.node-details-modal').remove()">
                        <i data-lucide="x"></i>
                    </button>
                </div>
                <div class="modal-body">
                    <p><strong>Description:</strong> ${nodeDefinition.description}</p>
                    <p><strong>Category:</strong> ${nodeDefinition.category}</p>
                    <p><strong>Type:</strong> ${nodeDefinition.type}</p>
                    <p><strong>Paradigm:</strong> ${nodeDefinition.paradigm || this.currentParadigm}</p>
                    
                    ${nodeDefinition.inputs ? `
                        <div class="inputs-section">
                            <h4>Inputs:</h4>
                            <ul>
                                ${nodeDefinition.inputs.map(input => `<li>${input}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                    
                    ${nodeDefinition.outputs ? `
                        <div class="outputs-section">
                            <h4>Outputs:</h4>
                            <ul>
                                ${nodeDefinition.outputs.map(output => `<li>${output}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                    
                    ${nodeDefinition.properties ? `
                        <div class="properties-section">
                            <h4>Properties:</h4>
                            <pre>${JSON.stringify(nodeDefinition.properties, null, 2)}</pre>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Update Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
        
        // Auto-remove after 10 seconds or on click outside
        setTimeout(() => {
            if (modal.parentNode) modal.remove();
        }, 10000);
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }
    
    handlePaletteDragStart(event) {
        const nodeId = event.target.closest('.palette-node').dataset.nodeId;
        const nodeDefinition = this.nodeDefinitions.find(n => n.id === nodeId);
        
        event.dataTransfer.setData('application/json', JSON.stringify(nodeDefinition));
        event.dataTransfer.effectAllowed = 'copy';
        
        // Add visual feedback
        event.target.style.opacity = '0.5';
    }
    
    handlePaletteDragEnd(event) {
        event.target.style.opacity = '1';
    }
    
    handleCanvasMouseDown(event) {
        event.preventDefault();
        
        const rect = this.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        
        // Convert to canvas coordinates
        const canvasPoint = this.screenToCanvas(x, y);
        
        // Check what was clicked
        const target = event.target;
        const isShiftPressed = event.shiftKey;
        const isCtrlPressed = event.ctrlKey || event.metaKey;
        
        if (target.classList.contains('port-circle')) {
            // Start connection
            this.startConnection(target, canvasPoint);
        } else if (target.closest('.visual-node')) {
            // Start node drag
            const nodeElement = target.closest('.visual-node');
            const nodeId = nodeElement.dataset.nodeId;
            this.startNodeDrag(nodeId, canvasPoint, isShiftPressed || isCtrlPressed);
        } else {
            // Start canvas pan or selection
            this.startCanvasDrag(canvasPoint);
        }
        
        this.dragState.startX = x;
        this.dragState.startY = y;
    }
    
    handleCanvasMouseMove(event) {
        if (!this.dragState.isDragging) return;
        
        const rect = this.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        const canvasPoint = this.screenToCanvas(x, y);
        
        const deltaX = x - this.dragState.startX;
        const deltaY = y - this.dragState.startY;
        
        switch (this.dragState.dragType) {
            case 'node':
                this.updateNodeDrag(canvasPoint);
                break;
            case 'canvas':
                this.updateCanvasPan(deltaX, deltaY);
                break;
            case 'connection':
                this.updateConnectionPreview(canvasPoint);
                break;
        }
    }
    
    handleCanvasMouseUp(event) {
        if (!this.dragState.isDragging) return;
        
        const rect = this.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        const canvasPoint = this.screenToCanvas(x, y);
        
        switch (this.dragState.dragType) {
            case 'node':
                this.finishNodeDrag();
                break;
            case 'connection':
                this.finishConnection(event.target);
                break;
        }
        
        this.resetDragState();
    }
    
    handleCanvasWheel(event) {
        event.preventDefault();

        // ── If we are inside a Code Dive, scroll-down exits ─────────
        if (this.codeDive.active) {
            if (event.deltaY > 0) {          // scroll down = zoom out
                this.exitCodeDive();
            }
            return;                           // swallow all wheel events while diving
        }
        
        const rect = this.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        
        const zoomFactor = event.deltaY > 0 ? 0.9 : 1.1;
        const newZoom = Math.max(0.1, Math.min(5.0, this.viewport.zoom * zoomFactor));

        // ── Code Dive trigger: zooming IN while already at max ──────
        if (event.deltaY < 0 && this.viewport.zoom >= 4.9) {
            // Find the node under the cursor
            const nodeEl = document.elementFromPoint(event.clientX, event.clientY)
                                  ?.closest('.visual-node');
            if (nodeEl) {
                const nodeId = nodeEl.dataset.nodeId;
                const nodeData = this.nodes.get(nodeId);
                const src = nodeData?.parameters?.source_code || nodeData?.metadata?.source_code;
                if (src?.trim()) {
                    this.enterCodeDive(nodeId);
                    return;
                }
            }
        }

        this.setZoom(newZoom, x, y);
    }
    
    handleCanvasContextMenu(event) {
        event.preventDefault();
        
        const target = event.target;
        if (target.closest('.visual-node') || target.closest('.connection')) {
            this.showContextMenu(event.clientX, event.clientY, target);
        }
    }
    
    startConnection(portElement, point) {
        this.dragState.isDragging = true;
        this.dragState.dragType = 'connection';
        this.dragState.dragTarget = portElement;
        
        // Create connection preview
        const preview = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        preview.classList.add('connection-preview');
        this.previewLayer.appendChild(preview);
        this.dragState.connectionPreview = preview;
        
        this.updateConnectionPreview(point);
    }
    
    updateConnectionPreview(endPoint) {
        if (!this.dragState.connectionPreview) return;
        
        const portElement = this.dragState.dragTarget;
        const portRect = portElement.getBoundingClientRect();
        const canvasRect = this.canvas.getBoundingClientRect();
        
        const startX = portRect.left + portRect.width / 2 - canvasRect.left;
        const startY = portRect.top + portRect.height / 2 - canvasRect.top;
        
        const startPoint = this.screenToCanvas(startX, startY);
        
        const path = this.createConnectionPath(startPoint, endPoint);
        this.dragState.connectionPreview.setAttribute('d', path);
    }
    
    finishConnection(targetElement) {
        if (!targetElement.classList.contains('port-circle')) {
            this.clearConnectionPreview();
            return;
        }
        
        const sourcePort = this.dragState.dragTarget;
        const targetPort = targetElement;
        
        if (sourcePort === targetPort) {
            this.clearConnectionPreview();
            return;
        }
        
        // Get port information
        const sourceNode = sourcePort.closest('.visual-node');
        const targetNode = targetPort.closest('.visual-node');
        
        if (sourceNode === targetNode) {
            this.clearConnectionPreview();
            return;
        }
        
        const sourceNodeId = sourceNode.dataset.nodeId;
        const targetNodeId = targetNode.dataset.nodeId;
        const sourcePortName = sourcePort.dataset.portName;
        const targetPortName = targetPort.dataset.portName;
        
        // Create connection
        this.createConnection(sourceNodeId, sourcePortName, targetNodeId, targetPortName);
        
        this.clearConnectionPreview();
    }
    
    clearConnectionPreview() {
        if (this.dragState.connectionPreview) {
            this.dragState.connectionPreview.remove();
            this.dragState.connectionPreview = null;
        }
    }
    
    async createConnection(sourceNodeId, sourcePort, targetNodeId, targetPort) {
        try {
            const response = await fetch('/api/canvas/connections', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    source_node_id: sourceNodeId,
                    source_port: sourcePort,
                    target_node_id: targetNodeId,
                    target_port: targetPort
                })
            });
            
            const data = await response.json();
            if (!data.success) {
                console.error('Failed to create connection:', data.error);
            }
        } catch (error) {
            console.error('Error creating connection:', error);
        }
    }
    
    startNodeDrag(nodeId, point, addToSelection = false) {
        this.dragState.isDragging = true;
        this.dragState.dragType = 'node';
        this.dragState.dragTarget = nodeId;
        
        // Handle selection based on modifier keys
        if (addToSelection) {
            // Shift/Ctrl+Click: Add to or toggle selection
            this.selectNode(nodeId, true);
        } else if (!this.selectedNodes.has(nodeId)) {
            // Click without modifier on unselected node: Select only this node
            this.selectNode(nodeId, false);
        }
        // If clicking on already selected node without modifier, keep selection as is
    }
    
    updateNodeDrag(point) {
        const nodeId = this.dragState.dragTarget;
        const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);
        if (!nodeElement) return;
        
        // Update visual position immediately
        nodeElement.setAttribute('transform', `translate(${point.x}, ${point.y})`);
        
        // Update connections
        this.updateNodeConnections(nodeId);
    }
    
    async finishNodeDrag() {
        const nodeId = this.dragState.dragTarget;
        const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);
        if (!nodeElement) return;
        
        // Get final position
        const transform = nodeElement.getAttribute('transform');
        const match = transform.match(/translate\(([^,]+),\s*([^)]+)\)/);
        if (!match) return;
        
        const x = parseFloat(match[1]);
        const y = parseFloat(match[2]);
        
        try {
            const response = await fetch(`/api/canvas/nodes/${nodeId}/move`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    position: [x, y]
                })
            });
            
            const data = await response.json();
            if (!data.success) {
                console.error('Failed to move node:', data.error);
            }
        } catch (error) {
            console.error('Error moving node:', error);
        }
    }
    
    startCanvasDrag(point) {
        this.dragState.isDragging = true;
        this.dragState.dragType = 'canvas';
        this.canvas.style.cursor = 'grabbing';
    }
    
    updateCanvasPan(deltaX, deltaY) {
        const newPanX = this.viewport.panX + deltaX / this.viewport.zoom;
        const newPanY = this.viewport.panY + deltaY / this.viewport.zoom;
        
        this.setPan(newPanX, newPanY);
        
        this.dragState.startX += deltaX;
        this.dragState.startY += deltaY;
    }
    
    resetDragState() {
        this.dragState.isDragging = false;
        this.dragState.dragType = null;
        this.dragState.dragTarget = null;
        this.canvas.style.cursor = 'grab';
        this.clearConnectionPreview();
    }
    
    // Canvas drop handling
    handleCanvasDrop(event) {
        event.preventDefault();
        
        try {
            const nodeDefinition = JSON.parse(event.dataTransfer.getData('application/json'));
            
            const rect = this.canvas.getBoundingClientRect();
            const x = event.clientX - rect.left;
            const y = event.clientY - rect.top;
            const canvasPoint = this.screenToCanvas(x, y);
            
            this.createNode(nodeDefinition, canvasPoint);
        } catch (error) {
            console.error('Error handling canvas drop:', error);
        }
    }
    
    handleCanvasDragOver(event) {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'copy';
    }
    
    async createNode(nodeDefinition, position) {
        try {
            const response = await fetch('/api/canvas/nodes', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    type: nodeDefinition.type,
                    position: [position.x, position.y],
                    parameters: {},
                    metadata: {
                        name: nodeDefinition.name,
                        description: nodeDefinition.description
                    }
                })
            });
            
            const data = await response.json();
            if (!data.success) {
                console.error('Failed to create node:', data.error);
            }
        } catch (error) {
            console.error('Error creating node:', error);
        }
    }
    
    addNodeToCanvas(nodeId, nodeData) {
        if (this.nodes.has(nodeId)) {
            this.removeNodeFromCanvas(nodeId);
        }

        nodeData.canvasId = nodeId;
        const nodeElement = this.createNodeElement(nodeId, nodeData);
        this.nodesLayer.appendChild(nodeElement);
        this.nodes.set(nodeId, nodeData);
        
        this.updateStatus();
        this.scheduleSaveCanvasState();
        this.updateNodeCodePreview(nodeId);
        
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }
    
    createNodeElement(nodeId, nodeData) {
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.classList.add('visual-node');
        g.dataset.nodeId = nodeId;

        // Safely extract position — handle [x,y] array, {x,y} object, or missing
        let px = 0, py = 0;
        const pos = nodeData.position;
        if (Array.isArray(pos)) {
            px = Number(pos[0]) || 0;
            py = Number(pos[1]) || 0;
        } else if (pos && typeof pos === 'object') {
            px = Number(pos.x) || 0;
            py = Number(pos.y) || 0;
        }
        g.setAttribute('transform', `translate(${px}, ${py})`);
        
        // Check if we have a custom PNG image for this node type
        const customImagePath = this.getCustomNodeImage(nodeData.type, nodeData.metadata?.nodeDefinition);
        
        if (customImagePath) {
            // Use PNG image for the node
            this.createImageNode(g, nodeData, customImagePath);
        } else {
            // Use traditional SVG node
            this.createSVGNode(g, nodeData);
        }
        
        // Input ports
        nodeData.inputs?.forEach((input, index) => {
            const portGroup = this.createPortElement(input.name, 'input', index, nodeData.inputs.length);
            g.appendChild(portGroup);
        });
        
        // Output ports
        nodeData.outputs?.forEach((output, index) => {
            const portGroup = this.createPortElement(output.name, 'output', index, nodeData.outputs.length);
            g.appendChild(portGroup);
        });
        
        // Add click handler
        g.addEventListener('click', (event) => {
            event.stopPropagation();
            this.selectNode(nodeId);
        });

        g.addEventListener('mouseenter', (event) => {
            this.showNodeHoverLabel(nodeId, event.clientX, event.clientY);
        });
        g.addEventListener('mousemove', (event) => {
            this.showNodeHoverLabel(nodeId, event.clientX, event.clientY);
        });
        g.addEventListener('mouseleave', () => {
            this.hideNodeHoverLabel();
        });
        g.addEventListener('mousedown', (event) => {
            this.showNodeHoverLabel(nodeId, event.clientX, event.clientY);
        });
        
        return g;
    }
    
    getCustomNodeImage(nodeType, nodeDefinition = null) {
        // First check if the node definition has an image path
        if (nodeDefinition && nodeDefinition.image) {
            return nodeDefinition.image;
        }
        
        // Fallback to hardcoded map for backward compatibility
        const imageMap = {
            'function': '/static/images/function_node.png',
            'async_function': '/static/images/async_function_node.png',
            'lambda': '/static/images/lambda_node.png',
            'variable': '/static/images/variable_node.png',
            'constant': '/static/images/constant_node.png',
            'if_condition': '/static/images/if_node.png',
            'while_loop': '/static/images/while_node.png',
            'for_loop': '/static/images/for_node.png',
            'list': '/static/images/list_node.png',
            'dict': '/static/images/dict_node.png',
            'file_read': '/static/images/file_read_node.png',
            'http_request': '/static/images/http_request_node.png',
            'class': '/static/images/class_node.png',
            'method': '/static/images/method_node.png',
            'property': '/static/images/property_node.png',
            'try_except': '/static/images/try_except_node.png',
            'decorator': '/static/images/decorator_node.png',
            'generator': '/static/images/generator_node.png',
            'context_manager': '/static/images/context_manager_node.png',
            'map': '/static/images/map_node.png',
            'filter': '/static/images/filter_node.png',
            'reduce': '/static/images/reduce_node.png',
            'file_write': '/static/images/file_write_node.png',
            'database_query': '/static/images/database_query_node.png',
            'api_call': '/static/images/api_call_node.png',
            'event': '/static/images/event_node.png',
            'timer': '/static/images/timer_node.png',
            'delay': '/static/images/delay_node.png',
            'parallel': '/static/images/parallel_node.png',
            'sequence': '/static/images/sequence_node.png',
            'await': '/static/images/await_node.png'
        };
        
        return imageMap[nodeType] || null;
    }
    
    createImageNode(g, nodeData, imagePath) {
        const nodeWidth = 120;
        const nodeHeight = 80;
        
        this.createNodeCodePreview(g, nodeData, {
            x: 0,
            y: 0,
            width: nodeWidth,
            height: nodeHeight
        });
        
        // PNG Image - full size without padding
        const image = document.createElementNS('http://www.w3.org/2000/svg', 'image');
        image.classList.add('node-image');
        image.setAttribute('href', imagePath);
        image.setAttribute('x', '0');
        image.setAttribute('y', '0');
        image.setAttribute('width', nodeWidth);
        image.setAttribute('height', nodeHeight);
        image.setAttribute('preserveAspectRatio', 'none'); // Stretch to fill exactly
        g.appendChild(image);
        
        // Title overlay removed to keep PNG unobstructed

        this.createNodeIconBadge(g, nodeData, nodeWidth, nodeHeight);
    }
    
    createSVGNode(g, nodeData) {
        // Traditional SVG node (fallback)
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.classList.add('node-body', nodeData.type);
        rect.setAttribute('width', '120');
        rect.setAttribute('height', '80');
        rect.setAttribute('rx', '8');
        g.appendChild(rect);
        
        // Node title
        const title = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        title.classList.add('node-title');
        title.setAttribute('x', '60');
        title.setAttribute('y', '25');
        title.textContent = nodeData.metadata?.name || nodeData.type;
        g.appendChild(title);
        
        // Node type
        const type = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        type.classList.add('node-type');
        type.setAttribute('x', '60');
        type.setAttribute('y', '40');
        type.textContent = nodeData.type;
        g.appendChild(type);
        this.createNodeCodePreview(g, nodeData, {
            x: 0,
            y: 0,
            width: 120,
            height: 80
        });

        this.createNodeIconBadge(g, nodeData, 120, 80);
    }

    createNodeIconBadge(g, nodeData, width, height) {
        const iconName = this.getNodeIconName(nodeData);
        if (!iconName) return;
        
        const fo = document.createElementNS('http://www.w3.org/2000/svg', 'foreignObject');
        fo.setAttribute('x', (width - 22).toString());
        fo.setAttribute('y', (height - 22).toString());
        fo.setAttribute('width', '20');
        fo.setAttribute('height', '20');
        fo.classList.add('node-icon-badge');
        
        const container = document.createElement('div');
        container.className = 'node-icon-badge-inner';
        container.innerHTML = `<i data-lucide="${iconName}"></i>`;
        fo.appendChild(container);
        
        g.appendChild(fo);
    }

    getNodeIconName(nodeData) {
        if (nodeData.metadata?.external_call) return 'external-link';
        const type = nodeData.type || '';
        const funcType = nodeData.metadata?.function_type || '';
        
        if (type === 'if_condition') return 'git-branch';
        if (type === 'for_loop') return 'repeat';
        if (type === 'while_loop') return 'refresh-ccw';
        if (type === 'try_except') return 'shield-alert';
        if (type === 'with') return 'link';
        
        if (funcType.includes('Async')) return 'clock';
        if (funcType.includes('Factory')) return 'box';
        if (funcType.includes('Validator')) return 'check-circle';
        if (funcType.includes('Processor')) return 'cpu';
        if (funcType.includes('Event')) return 'zap';
        if (funcType.includes('Control Flow')) return 'git-branch';
        
        if (type === 'variable' || type === 'constant') return 'database';
        if (type === 'class') return 'layers';
        if (type === 'function') return 'function-square';
        
        return 'box';
    }
    
    createNodeCodePreview(g, nodeData, bounds) {
        const sourceCode = nodeData.parameters?.source_code || nodeData.metadata?.source_code;
        if (!sourceCode) return;
        
        const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        group.classList.add('node-code');
        group.dataset.nodeId = g.dataset.nodeId;

        const clipId = `code-clip-${g.dataset.nodeId}`;
        const defs = this.ensureCanvasDefs();
        const clipPath = document.createElementNS('http://www.w3.org/2000/svg', 'clipPath');
        clipPath.setAttribute('id', clipId);
        const clipRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        clipRect.setAttribute('x', bounds.x.toString());
        clipRect.setAttribute('y', bounds.y.toString());
        clipRect.setAttribute('width', bounds.width.toString());
        clipRect.setAttribute('height', bounds.height.toString());
        clipRect.setAttribute('rx', '6');
        clipPath.appendChild(clipRect);
        defs.appendChild(clipPath);
        group.setAttribute('clip-path', `url(#${clipId})`);
        
        const bgLayer = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        bgLayer.classList.add('node-code-layer');
        bgLayer.dataset.depth = '0.2';
        
        const background = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        background.classList.add('node-code-bg');
        background.setAttribute('x', bounds.x.toString());
        background.setAttribute('y', bounds.y.toString());
        background.setAttribute('width', bounds.width.toString());
        background.setAttribute('height', bounds.height.toString());
        background.setAttribute('rx', '6');
        bgLayer.appendChild(background);
        group.appendChild(bgLayer);
        
        const textLayer = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        textLayer.classList.add('node-code-layer');
        textLayer.dataset.depth = '0.4';
        
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.classList.add('node-code-text');
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('x', (bounds.x + bounds.width / 2).toString());
        text.setAttribute('y', (bounds.y + bounds.height / 2).toString());
        text.setAttribute('xml:space', 'preserve');
        textLayer.appendChild(text);
        group.appendChild(textLayer);
        
        g.appendChild(group);
        this.updateNodeCodePreview(g.dataset.nodeId);
    }

    ensureCanvasDefs() {
        let defs = this.canvas.querySelector('defs');
        if (!defs) {
            defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
            this.canvas.insertBefore(defs, this.canvas.firstChild);
        }
        return defs;
    }
    
    createPortElement(portName, portType, index, totalPorts) {
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.classList.add('port', portType);
        
        const isInput = portType === 'input';
        const x = isInput ? -6 : 126;
        const y = 50 + (index * 15) - ((totalPorts - 1) * 7.5);
        
        g.setAttribute('transform', `translate(${x}, ${y})`);
        
        // Port circle
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.classList.add('port-circle');
        circle.setAttribute('r', '6');
        circle.dataset.portName = portName;
        circle.dataset.portType = portType;
        g.appendChild(circle);
        
        // Port label
        const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        label.classList.add('port-label');
        label.setAttribute('x', isInput ? -15 : 15);
        label.setAttribute('y', '3');
        label.setAttribute('text-anchor', isInput ? 'end' : 'start');
        label.textContent = portName;
        g.appendChild(label);
        
        return g;
    }
    
    removeNodeFromCanvas(nodeId) {
        const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);
        if (nodeElement) {
            nodeElement.remove();
        }
        
        this.nodes.delete(nodeId);
        this.selectedNodes.delete(nodeId);
        
        // Remove connections involving this node
        const connectionsToRemove = [];
        this.connections.forEach((connection, connectionId) => {
            if (connection.source_node_id === nodeId || connection.target_node_id === nodeId) {
                connectionsToRemove.push(connectionId);
            }
        });
        
        connectionsToRemove.forEach(connectionId => {
            this.removeConnectionFromCanvas(connectionId);
        });
        
        this.updateStatus();
        this.updatePropertiesPanel();
        this.scheduleSaveCanvasState();
    }

    redrawNode(nodeId) {
        const nodeData = this.nodes.get(nodeId);
        if (!nodeData) return;
        
        const wasSelected = this.selectedNodes.has(nodeId);
        const existingElement = document.querySelector(`[data-node-id="${nodeId}"]`);
        if (existingElement) {
            existingElement.remove();
        }
        
        const nodeElement = this.createNodeElement(nodeId, nodeData);
        this.nodesLayer.appendChild(nodeElement);
        
        if (wasSelected) {
            const rect = nodeElement.querySelector('.node-body');
            if (rect) {
                rect.classList.add('selected');
            }
        }
        
        this.updateNodeConnections(nodeId);
    }

    updateNodeTitle(nodeId) {
        const nodeData = this.nodes.get(nodeId);
        if (!nodeData) return;
        
        const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);
        if (!nodeElement) return;
        
        const displayName = nodeData.metadata?.display_as || nodeData.metadata?.name || nodeData.metadata?.display_name || nodeData.type;
        const titleElement = nodeElement.querySelector('.node-title');
        if (titleElement) {
            titleElement.textContent = displayName;
        }
        
        const shouldShowOverlay = nodeData.parameters?.show_label_overlay !== undefined
            ? Boolean(nodeData.parameters?.show_label_overlay)
            : Boolean(this.uiSettings.showLabelOverlay);
        let overlayTitle = nodeElement.querySelector('.node-title-overlay');
        if (shouldShowOverlay && !overlayTitle) {
            overlayTitle = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            overlayTitle.classList.add('node-title-overlay');
            overlayTitle.setAttribute('x', '60');
            overlayTitle.setAttribute('y', '72');
            overlayTitle.setAttribute('text-anchor', 'middle');
            overlayTitle.setAttribute('font-size', '11');
            overlayTitle.setAttribute('font-weight', '600');
            overlayTitle.setAttribute('fill', '#e2e8f0');
            overlayTitle.setAttribute('stroke', '#0f172a');
            overlayTitle.setAttribute('stroke-width', '2');
            overlayTitle.setAttribute('paint-order', 'stroke fill');
            nodeElement.appendChild(overlayTitle);
        }
        if (overlayTitle) {
            if (shouldShowOverlay) {
                overlayTitle.textContent = displayName;
                overlayTitle.style.display = 'block';
            } else {
                overlayTitle.style.display = 'none';
            }
        }
    }

    showNodeHoverLabel(nodeId, clientX = null, clientY = null) {
        if (!this.hoverLabel) return;
        const nodeData = this.nodes.get(nodeId);
        if (!nodeData) return;

        const shouldShowHover = nodeData.parameters?.show_display_label !== undefined
            ? Boolean(nodeData.parameters?.show_display_label)
            : Boolean(this.uiSettings.showDisplayLabels);
        if (!shouldShowHover) {
            this.hideNodeHoverLabel();
            return;
        }
        
        const displayName = nodeData.metadata?.display_as || nodeData.metadata?.name || nodeData.metadata?.display_name || nodeData.type;
        this.hoverLabel.textContent = displayName;
        this.hoverLabel.style.display = 'block';
        
        let x = clientX;
        let y = clientY;
        if (x === null || y === null) {
            const screenPos = this.canvasToScreen(nodeData.position[0], nodeData.position[1]);
            x = screenPos.x + 140;
            y = screenPos.y + 20;
        }
        
        this.hoverLabel.style.left = `${x + 12}px`;
        this.hoverLabel.style.top = `${y + 12}px`;
    }

    hideNodeHoverLabel() {
        if (this.hoverLabel) {
            this.hoverLabel.style.display = 'none';
        }
    }

    updateAllNodeCodePreviews() {
        this.nodes.forEach((nodeData, nodeId) => {
            this.updateNodeCodePreview(nodeId);
        });
    }

    updateNodeCodePreview(nodeId) {
        const nodeData = this.nodes.get(nodeId);
        if (!nodeData) return;
        
        const group = document.querySelector(`[data-node-id="${nodeId}"] .node-code`);
        if (!group) return;
        
        const textElement = group.querySelector('.node-code-text');
        const bgElement = group.querySelector('.node-code-bg');
        if (!textElement || !bgElement) return;
        
        const sourceCode = nodeData.parameters?.source_code || nodeData.metadata?.source_code || '';
        if (!sourceCode.trim()) return;
        
        const zoom = this.viewport.zoom || 1;
        const bounds = bgElement.getBBox();

        // ── Font size ───────────────────────────────────────────────
        // In SVG units (canvas scale(zoom) handles magnification).
        // Apparent screen font size = fontSize * zoom = constant 9px.
        const fontSize = 9 / zoom;

        // ── Line spacing ────────────────────────────────────────────
        // We want the *apparent* (screen-pixel) gap between lines to
        // GROW as zoom increases — i.e. the spacing in SVG units must
        // shrink *slower* than fontSize does.
        //
        //   apparentLineHeight = lineHeight_svg * zoom
        //
        // If lineHeight_svg = fontSize * M, then apparent = 9 * M.
        // For M to grow with zoom we use:
        //   M = 1.6 + 0.35 * ln(zoom)          (ln, not log2)
        //
        //   zoom 1×  → M = 1.60  → apparent gap 14.4 px
        //   zoom 2×  → M = 1.84  → apparent gap 16.6 px
        //   zoom 3×  → M = 1.98  → apparent gap 17.9 px
        //   zoom 5×  → M = 2.16  → apparent gap 19.5 px
        //
        const spacingMultiplier = 1.6 + 0.35 * Math.log(Math.max(1, zoom));
        const lineHeight = fontSize * spacingMultiplier;

        // ── How many lines can we show? ─────────────────────────────
        const padding = 10 / zoom;
        const availableHeight = bounds.height - padding * 2;
        const maxFit = Math.max(1, Math.floor(availableHeight / lineHeight));

        // Lines grow gently: 2 at zoom 1×, 3 at ~2.5×, 4 at ~5×
        const wanted = Math.min(8, 2 + Math.floor(Math.log(Math.max(1, zoom)) * 1.2));
        const linesToShow = Math.min(wanted, maxFit);
        
        const lines = sourceCode.split('\n').map(l => l.replace(/\s+$/g, '')).filter(Boolean);
        const centerIndex = Math.floor(lines.length / 2);
        const startIndex = Math.max(0, centerIndex - Math.floor(linesToShow / 2));
        const visibleLines = lines.slice(startIndex, startIndex + linesToShow);
        
        textElement.setAttribute('font-size', fontSize.toFixed(2));
        textElement.setAttribute('x', (bounds.x + bounds.width / 2).toString());
        const totalHeight = (visibleLines.length - 1) * lineHeight;
        const startY = (bounds.y + bounds.height / 2) - (totalHeight / 2);
        textElement.setAttribute('y', startY.toFixed(2));
        textElement.setAttribute('dominant-baseline', 'alphabetic');
        
        textElement.innerHTML = '';
        visibleLines.forEach((line, index) => {
            const lineSpan = document.createElementNS('http://www.w3.org/2000/svg', 'tspan');
            lineSpan.setAttribute('x', (bounds.x + bounds.width / 2).toString());
            lineSpan.setAttribute('dy', index === 0 ? '0' : lineHeight.toString());
            const visibleChars = this.getVisibleCharsForZoom(zoom);
            const centeredLine = this.centerSlice(line, visibleChars);
            const tokens = this.tokenizeCodeLine(centeredLine);
            tokens.forEach((token) => {
                const tspan = document.createElementNS('http://www.w3.org/2000/svg', 'tspan');
                tspan.textContent = token.value;
                if (token.type) {
                    tspan.classList.add(token.type);
                }
                lineSpan.appendChild(tspan);
            });
            textElement.appendChild(lineSpan);
        });
        
        this.applyParallaxToCode(group);
    }

    getVisibleCharsForZoom(zoom) {
        const baseChars = 18;
        const maxChars = 50;
        return Math.max(baseChars, Math.min(maxChars, Math.floor(baseChars * zoom)));
    }

    centerSlice(line, maxChars) {
        if (line.length <= maxChars) return line;
        const mid = Math.floor(line.length / 2);
        const half = Math.floor(maxChars / 2);
        const start = Math.max(0, mid - half);
        return line.slice(start, start + maxChars);
    }

    applyParallaxToCode(group) {
        const canvasRect = this.canvas.getBoundingClientRect();
        const centerX = canvasRect.left + canvasRect.width / 2;
        const centerY = canvasRect.top + canvasRect.height / 2;
        const mouseX = this.lastMouse?.x ?? centerX;
        const mouseY = this.lastMouse?.y ?? centerY;
        const offsetX = (mouseX - centerX) / canvasRect.width;
        const offsetY = (mouseY - centerY) / canvasRect.height;
        
        group.querySelectorAll('.node-code-layer').forEach((layer) => {
            const depth = parseFloat(layer.dataset.depth || '0.2');
            const translateX = offsetX * depth * 6;
            const translateY = offsetY * depth * 6;
            layer.setAttribute('transform', `translate(${translateX}, ${translateY})`);
        });
    }

    tokenizeCodeLine(line) {
        const tokens = [];
        const keywords = new Set([
            'if', 'elif', 'else', 'for', 'while', 'try', 'except', 'with', 'return',
            'def', 'class', 'import', 'from', 'as', 'in', 'is', 'not', 'and', 'or',
            'raise', 'await', 'async', 'yield', 'pass', 'break', 'continue'
        ]);
        
        let current = '';
        let mode = null;
        let modeQuote = null;
        const pushToken = (value, type) => {
            if (!value) return;
            tokens.push({ value, type });
        };
        
        let i = 0;
        while (i < line.length) {
            const char = line[i];
            if (mode === 'string') {
                current += char;
                if (char === modeQuote && line[i - 1] !== '\\') {
                    pushToken(current, 'code-str');
                    current = '';
                    mode = null;
                }
                i += 1;
                continue;
            }
            
            if (char === '#' && mode === null) {
                pushToken(current, this.classifyWord(current, keywords));
                current = '';
                pushToken(line.slice(i), 'code-com');
                break;
            }
            
            if ((char === '"' || char === "'") && mode === null) {
                pushToken(current, this.classifyWord(current, keywords));
                current = char;
                mode = 'string';
                modeQuote = char;
                i += 1;
                continue;
            }
            
            if (/[\s]/.test(char)) {
                pushToken(current, this.classifyWord(current, keywords));
                current = '';
                pushToken(char, null);
                i += 1;
                continue;
            }
            
            if (/[0-9]/.test(char)) {
                let number = char;
                i += 1;
                while (i < line.length && /[0-9._]/.test(line[i])) {
                    number += line[i];
                    i += 1;
                }
                pushToken(current, this.classifyWord(current, keywords));
                current = '';
                pushToken(number, 'code-num');
                continue;
            }
            
            current += char;
            i += 1;
        }
        
        pushToken(current, this.classifyWord(current, keywords));
        return tokens;
    }

    classifyWord(word, keywords) {
        if (!word) return null;
        const trimmed = word.trim();
        if (!trimmed) return null;
        return keywords.has(trimmed) ? 'code-kw' : null;
    }

    // ═══════════════════════════════════════════════════════════════
    // CODE DIVE — immersive full-source view powered by Monaco Editor
    // ═══════════════════════════════════════════════════════════════

    /**
     * Enter Code Dive.
     * @param {string}  nodeId
     * @param {object}  [opts]
     * @param {boolean} [opts.fromPanel=false]  true when triggered from the
     *                                          properties panel (skip viewport save)
     */
    enterCodeDive(nodeId, opts = {}) {
        if (this.codeDive.active) return;

        const nodeData = this.nodes.get(nodeId);
        if (!nodeData) return;
        const sourceCode = nodeData.parameters?.source_code
                        || nodeData.metadata?.source_code || '';

        // ── Language mapping for Monaco ──────────────────────────
        const langMap = {
            python: 'python', javascript: 'javascript', typescript: 'typescript',
            rust: 'rust', java: 'java', swift: 'swift', cpp: 'cpp', r: 'r',
            go: 'go', ruby: 'ruby', csharp: 'csharp', kotlin: 'kotlin',
            c: 'c', bash: 'shell', perl: 'perl',
        };
        const srcLang = nodeData.parameters?.source_language
                     || nodeData.metadata?.source_language
                     || 'python';
        const monacoLang = langMap[srcLang] || 'plaintext';

        // ── Viewport bookkeeping ────────────────────────────────
        if (!opts.fromPanel) {
            this.codeDive.savedViewport = {
                zoom: this.viewport.zoom,
                panX: this.viewport.panX,
                panY: this.viewport.panY,
            };
        } else {
            this.codeDive.savedViewport = null;   // nothing to restore
        }
        this.codeDive.nodeId = nodeId;
        this.codeDive.active = true;

        const nodeName  = this._escapeHtml(nodeData.metadata?.name || nodeData.type);
        const lineCount = sourceCode.split('\n').length;

        // ── Overlay DOM ─────────────────────────────────────────
        const overlay = document.createElement('div');
        overlay.className = 'code-dive-overlay';
        overlay.innerHTML = `
            <div class="code-dive-chrome">
                <div class="code-dive-header">
                    <span class="code-dive-icon">
                        <i data-lucide="code-2" style="width:18px;height:18px"></i>
                    </span>
                    <span class="code-dive-title">${nodeName}</span>
                    <span class="code-dive-badge">${lineCount} lines</span>
                    <span class="code-dive-lang">${srcLang}</span>
                    <span class="code-dive-hint">
                        <kbd>Ctrl+S</kbd> save &nbsp; <kbd>Esc</kbd> close
                    </span>
                    <button class="code-dive-close" title="Exit Code Dive">&times;</button>
                </div>
                <div class="code-dive-body" id="code-dive-monaco"></div>
                <div class="code-dive-footer">
                    <span class="code-dive-status" id="code-dive-status">Ready</span>
                    <span class="code-dive-pos"    id="code-dive-pos">Ln 1, Col 1</span>
                </div>
            </div>`;

        // Close button
        overlay.querySelector('.code-dive-close')
               .addEventListener('click', () => this.exitCodeDive());
        // Click on backdrop (outside chrome) to close
        overlay.addEventListener('mousedown', (e) => {
            if (e.target === overlay) this.exitCodeDive();
        });

        document.body.appendChild(overlay);
        this.codeDive.overlay = overlay;

        // Entrance animation
        requestAnimationFrame(() => {
            overlay.classList.add('code-dive-active');
            if (typeof lucide !== 'undefined') lucide.createIcons({ root: overlay });
        });

        // ── Instantiate Monaco (lazy AMD load, cached after first) ──
        const container = overlay.querySelector('#code-dive-monaco');
        const statusEl  = overlay.querySelector('#code-dive-status');
        const posEl     = overlay.querySelector('#code-dive-pos');

        if (typeof require !== 'undefined' && typeof require.config === 'function') {
            require(['vs/editor/editor.main'], (monaco) => {
                if (!this.codeDive.active) return;       // closed before load finished

                // SpokedPy dark theme (register once)
                if (!this._monacoThemeRegistered) {
                    monaco.editor.defineTheme('spokedpy-dark', {
                        base: 'vs-dark', inherit: true,
                        rules: [
                            { token: 'comment',  foreground: '555555', fontStyle: 'italic' },
                            { token: 'keyword',  foreground: 'aaaaaa', fontStyle: 'bold'   },
                            { token: 'string',   foreground: '999999' },
                            { token: 'number',   foreground: '888888' },
                            { token: 'type',     foreground: '999999' },
                            { token: 'function', foreground: 'bbbbbb' },
                        ],
                        colors: {
                            'editor.background':               '#000000',
                            'editor.foreground':               '#cccccc',
                            'editor.lineHighlightBackground':  '#0a0a0a',
                            'editorLineNumber.foreground':     '#333333',
                            'editorLineNumber.activeForeground':'#666666',
                            'editor.selectionBackground':      '#8b5cf620',
                            'editorCursor.foreground':         '#8b5cf6',
                            'editorIndentGuide.background':    '#1a1a1a',
                            'scrollbarSlider.background':      '#22222280',
                        },
                    });
                    this._monacoThemeRegistered = true;
                }

                const editor = monaco.editor.create(container, {
                    value:      sourceCode,
                    language:   monacoLang,
                    theme:      'spokedpy-dark',
                    fontSize:   14,
                    lineHeight: 22,
                    fontFamily: "'JetBrains Mono','Fira Code','Cascadia Code',monospace",
                    minimap:    { enabled: lineCount > 80 },
                    scrollBeyondLastLine: false,
                    automaticLayout:     true,
                    padding:   { top: 12, bottom: 12 },
                    roundedSelection:    true,
                    cursorBlinking:      'smooth',
                    smoothScrolling:     true,
                    renderWhitespace:    'selection',
                    bracketPairColorization: { enabled: true },
                    wordWrap:     'off',
                    tabSize:      4,
                    insertSpaces: true,
                });

                this.codeDive.editor = editor;
                this.codeDive.monaco = monaco;

                // Cursor position indicator
                editor.onDidChangeCursorPosition((e) => {
                    posEl.textContent =
                        `Ln ${e.position.lineNumber}, Col ${e.position.column}`;
                });

                // Dirty-state tracking
                let savedVersion = editor.getModel().getAlternativeVersionId();
                editor.onDidChangeModelContent(() => {
                    const dirty = editor.getModel().getAlternativeVersionId() !== savedVersion;
                    statusEl.textContent = dirty ? '● Modified' : 'Saved';
                    statusEl.className =
                        `code-dive-status ${dirty ? 'code-dive-dirty' : 'code-dive-saved'}`;
                });

                // Ctrl+S  →  save without closing
                editor.addAction({
                    id: 'spokedpy-save',
                    label: 'Save Code',
                    keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS],
                    run: () => {
                        this._codeDiveSave();
                        savedVersion = editor.getModel().getAlternativeVersionId();
                        statusEl.textContent = 'Saved';
                        statusEl.className = 'code-dive-status code-dive-saved';
                    },
                });

                // Escape  →  close Code Dive
                editor.addAction({
                    id: 'spokedpy-close',
                    label: 'Close Code Dive',
                    keybindings: [monaco.KeyCode.Escape],
                    run: () => this.exitCodeDive(),
                });

                editor.focus();
            });
        } else {
            // ── Fallback: plain textarea when Monaco CDN unavailable ──
            container.innerHTML = `<textarea class="code-dive-fallback"
                style="width:100%;height:100%;background:#000000;color:#cccccc;
                       border:none;resize:none;padding:16px;font-family:monospace;
                       font-size:14px;outline:none;tab-size:4;"
            ></textarea>`;
            const ta = container.querySelector('textarea');
            ta.value = sourceCode;
            this.codeDive.editor = { getValue: () => ta.value, dispose: () => {} };
        }

        // Global Escape fallback (if editor doesn't have focus yet)
        this._codeDiveKeyHandler = (e) => {
            if (e.key === 'Escape' && this.codeDive.active
                && !e.target.closest('.monaco-editor')) {
                this.exitCodeDive();
            }
        };
        document.addEventListener('keydown', this._codeDiveKeyHandler);
    }

    /** Persist the current editor content back to the node. */
    _codeDiveSave() {
        if (!this.codeDive.active || !this.codeDive.editor) return;
        const code   = this.codeDive.editor.getValue();
        const nodeId = this.codeDive.nodeId;
        const nodeData = this.nodes.get(nodeId);
        if (!nodeData) return;

        // Update in-memory model
        if (!nodeData.parameters) nodeData.parameters = {};
        nodeData.parameters.source_code = code;
        if (nodeData.metadata) nodeData.metadata.source_code = code;

        // Persist via REST
        fetch(`/api/canvas/nodes/${nodeId}/parameters`, {
            method:  'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ source_code: code }),
        }).catch(err => console.error('Code Dive save error:', err));

        // Refresh the SVG code preview on the canvas
        this.updateNodeCodePreview(nodeId);

        // If the properties panel is showing this node, sync the textarea
        if (this.propertiesPanel?.currentNode) {
            const panelNodeId = this.propertiesPanel.getCurrentNodeCanvasId();
            if (panelNodeId === nodeId) {
                const ta = document.querySelector('textarea[name="source_code"]');
                if (ta && ta.value !== code) ta.value = code;
            }
        }

        this.scheduleSaveCanvasState();
    }

    exitCodeDive() {
        if (!this.codeDive.active) return;
        const overlay = this.codeDive.overlay;

        // Auto-save any pending changes
        this._codeDiveSave();

        // Dispose Monaco editor
        if (this.codeDive.editor) {
            this.codeDive.editor.dispose();
            this.codeDive.editor = null;
        }
        this.codeDive.monaco = null;

        // Exit animation
        overlay.classList.remove('code-dive-active');
        overlay.classList.add('code-dive-exit');

        // Restore viewport (only when entered via canvas zoom)
        if (this.codeDive.savedViewport) {
            const sv = this.codeDive.savedViewport;
            this.viewport.zoom = sv.zoom;
            this.viewport.panX = sv.panX;
            this.viewport.panY = sv.panY;
            this.applyViewportTransform();
            this.updateViewportDisplay();
        }

        // Clean up after animation completes
        const cleanup = () => {
            overlay.remove();
            document.removeEventListener('keydown', this._codeDiveKeyHandler);
            this.codeDive.active = false;
            this.codeDive.overlay = null;
            this.codeDive.nodeId = null;
            this.codeDive.savedViewport = null;
        };
        overlay.addEventListener('transitionend', cleanup, { once: true });
        setTimeout(cleanup, 500);     // safety fallback
    }

    _escapeHtml(str) {
        const d = document.createElement('div');
        d.textContent = str || '';
        return d.innerHTML;
    }

    // ═══════════════════════════════════════════════════════════════
    
    addConnectionToCanvas(connectionData) {
        if (this.connections.has(connectionData.id)) {
            this.removeConnectionFromCanvas(connectionData.id);
        }
        
        const connectionElement = this.createConnectionElement(connectionData);
        this.connectionsLayer.appendChild(connectionElement);
        this.connections.set(connectionData.id, connectionData);
        
        this.updateStatus();
        this.scheduleSaveCanvasState();
    }
    
    createConnectionElement(connectionData) {
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.classList.add('connection');
        path.dataset.connectionId = connectionData.id;
        
        // Calculate path
        const pathData = this.calculateConnectionPath(connectionData);
        path.setAttribute('d', pathData);
        
        // Add click handler
        path.addEventListener('click', (event) => {
            event.stopPropagation();
            this.selectConnection(connectionData.id);
        });
        
        return path;
    }
    
    calculateConnectionPath(connectionData) {
        const sourceNode = document.querySelector(`[data-node-id="${connectionData.source_node_id}"]`);
        const targetNode = document.querySelector(`[data-node-id="${connectionData.target_node_id}"]`);
        
        if (!sourceNode || !targetNode) return '';
        
        // Get node positions
        const sourceTransform = sourceNode.getAttribute('transform');
        const targetTransform = targetNode.getAttribute('transform');
        
        const sourceMatch = sourceTransform.match(/translate\(([^,]+),\s*([^)]+)\)/);
        const targetMatch = targetTransform.match(/translate\(([^,]+),\s*([^)]+)\)/);
        
        if (!sourceMatch || !targetMatch) return '';
        
        const sourceX = parseFloat(sourceMatch[1]) + 120; // Node width
        const sourceY = parseFloat(sourceMatch[2]) + 40;  // Middle of source node
        const targetX = parseFloat(targetMatch[1]);       // Left side of target node
        const targetY = parseFloat(targetMatch[2]) + 40;  // Middle of target node
        
        return this.createConnectionPath({ x: sourceX, y: sourceY }, { x: targetX, y: targetY });
    }
    
    createConnectionPath(start, end) {
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        
        // Create a smooth curve
        const cp1x = start.x + Math.max(50, Math.abs(dx) * 0.5);
        const cp1y = start.y;
        const cp2x = end.x - Math.max(50, Math.abs(dx) * 0.5);
        const cp2y = end.y;
        
        return `M ${start.x} ${start.y} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${end.x} ${end.y}`;
    }
    
    removeConnectionFromCanvas(connectionId) {
        const connectionElement = document.querySelector(`[data-connection-id="${connectionId}"]`);
        if (connectionElement) {
            connectionElement.remove();
        }
        
        this.connections.delete(connectionId);
        this.selectedConnections.delete(connectionId);
        
        this.updateStatus();
        this.scheduleSaveCanvasState();
    }
    
    updateNodeConnections(nodeId) {
        this.connections.forEach((connection, connectionId) => {
            if (connection.source_node_id === nodeId || connection.target_node_id === nodeId) {
                const connectionElement = document.querySelector(`[data-connection-id="${connectionId}"]`);
                if (connectionElement) {
                    const pathData = this.calculateConnectionPath(connection);
                    connectionElement.setAttribute('d', pathData);
                }
            }
        });
    }
    
    selectNode(nodeId, addToSelection = false) {
        // If not adding to selection, clear existing selection
        if (!addToSelection) {
            this.clearSelection();
        }
        
        // Toggle selection if already selected and adding to selection
        if (addToSelection && this.selectedNodes.has(nodeId)) {
            this.selectedNodes.delete(nodeId);
            const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);
            if (nodeElement) {
                const rect = nodeElement.querySelector('.node-body');
                if (rect) {
                    rect.classList.remove('selected');
                }
            }
        } else {
            this.selectedNodes.add(nodeId);
            const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);
            if (nodeElement) {
                const rect = nodeElement.querySelector('.node-body');
                if (rect) {
                    rect.classList.add('selected');
                }
            }
        }
        
        this.updatePropertiesPanel();
        this.updateSelectionInfo();
    }
    
    updateSelectionInfo() {
        // Update any UI showing selection count
        const selectionCount = this.selectedNodes.size;
        const debugBtn = document.getElementById('multi-debug-btn');
        if (debugBtn && selectionCount > 0) {
            debugBtn.title = `Multi-Debug (${selectionCount} nodes selected)`;
        } else if (debugBtn) {
            debugBtn.title = 'Multi-Debug';
        }
    }
    
    selectConnection(connectionId) {
        this.clearSelection();
        this.selectedConnections.add(connectionId);
        
        const connectionElement = document.querySelector(`[data-connection-id="${connectionId}"]`);
        if (connectionElement) {
            connectionElement.classList.add('selected');
        }
        
        this.updatePropertiesPanel();
    }
    
    clearSelection() {
        // Clear node selection
        this.selectedNodes.forEach(nodeId => {
            const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);
            if (nodeElement) {
                const rect = nodeElement.querySelector('.node-body');
                if (rect) {
                    rect.classList.remove('selected');
                }
            }
        });
        this.selectedNodes.clear();
        
        // Clear connection selection
        this.selectedConnections.forEach(connectionId => {
            const connectionElement = document.querySelector(`[data-connection-id="${connectionId}"]`);
            if (connectionElement) {
                connectionElement.classList.remove('selected');
            }
        });
        this.selectedConnections.clear();
        
        this.updatePropertiesPanel();
    }
    
    updatePropertiesPanel() {
        // Use enhanced properties panel if available
        if (this.propertiesPanel) {
            const selectedNodeData = this.getSelectedNodeData();
            this.propertiesPanel.showNodeProperties(selectedNodeData);
            return;
        }
        
        // Fallback to basic properties panel
        const noSelection = document.getElementById('no-selection');
        const nodeProperties = document.getElementById('node-properties');
        
        if (this.selectedNodes.size === 1) {
            const nodeId = Array.from(this.selectedNodes)[0];
            const nodeData = this.nodes.get(nodeId);
            
            if (nodeData) {
                noSelection.style.display = 'none';
                nodeProperties.style.display = 'block';
                
                document.getElementById('prop-node-id').value = nodeId;
                document.getElementById('prop-node-type').value = nodeData.type;
                document.getElementById('prop-pos-x').value = nodeData.position[0];
                document.getElementById('prop-pos-y').value = nodeData.position[1];
                
                // Update parameters
                const parametersContainer = document.getElementById('prop-parameters');
                parametersContainer.innerHTML = '';
                Object.entries(nodeData.parameters || {}).forEach(([key, value]) => {
                    const item = document.createElement('div');
                    item.className = 'parameter-item';
                    item.innerHTML = `
                        <div class="parameter-name">${key}</div>
                        <div class="parameter-value">${value}</div>
                    `;
                    parametersContainer.appendChild(item);
                });
                
                // Update inputs
                const inputsContainer = document.getElementById('prop-inputs');
                inputsContainer.innerHTML = '';
                (nodeData.inputs || []).forEach(input => {
                    const item = document.createElement('div');
                    item.className = 'port-item';
                    item.innerHTML = `
                        <div class="port-name">${input.name}</div>
                        <div class="port-type">${input.type}</div>
                    `;
                    inputsContainer.appendChild(item);
                });
                
                // Update outputs
                const outputsContainer = document.getElementById('prop-outputs');
                outputsContainer.innerHTML = '';
                (nodeData.outputs || []).forEach(output => {
                    const item = document.createElement('div');
                    item.className = 'port-item';
                    item.innerHTML = `
                        <div class="port-name">${output.name}</div>
                        <div class="port-type">${output.type}</div>
                    `;
                    outputsContainer.appendChild(item);
                });
            }
        } else {
            noSelection.style.display = 'block';
            nodeProperties.style.display = 'none';
        }
    }
    
    getSelectedNodeData() {
        if (this.selectedNodes.size === 1) {
            const nodeId = Array.from(this.selectedNodes)[0];
            return this.nodes.get(nodeId);
        }
        return null;
    }
    
    // Viewport management
    screenToCanvas(screenX, screenY) {
        return {
            x: (screenX - this.viewport.panX) / this.viewport.zoom,
            y: (screenY - this.viewport.panY) / this.viewport.zoom
        };
    }
    
    canvasToScreen(canvasX, canvasY) {
        return {
            x: canvasX * this.viewport.zoom + this.viewport.panX,
            y: canvasY * this.viewport.zoom + this.viewport.panY
        };
    }
    
    updateViewport(viewportData) {
        this.viewport.zoom = viewportData.zoom || this.viewport.zoom;
        this.viewport.panX = viewportData.pan_x || this.viewport.panX;
        this.viewport.panY = viewportData.pan_y || this.viewport.panY;
        
        this.applyViewportTransform();
        this.updateViewportDisplay();
    }
    
    applyViewportTransform() {
        const transform = `translate(${this.viewport.panX}, ${this.viewport.panY}) scale(${this.viewport.zoom})`;
        this.canvasContent.setAttribute('transform', transform);
    }
    
    updateViewportDisplay() {
        document.getElementById('zoom-level').textContent = `${Math.round(this.viewport.zoom * 100)}%`;
        document.getElementById('pan-info').textContent = `${Math.round(this.viewport.panX)}, ${Math.round(this.viewport.panY)}`;
        this.updateAllNodeCodePreviews();
    }
    
    async setPan(panX, panY) {
        this.viewport.panX = panX;
        this.viewport.panY = panY;
        this.applyViewportTransform();
        this.updateViewportDisplay();
    }
    
    // Event handlers
    handleParadigmChange(event) {
        const paradigmType = event.target.value;
        this.setActiveParadigm(paradigmType);
    }
    
    async setActiveParadigm(paradigmType) {
        console.log('Setting active paradigm to:', paradigmType);
        
        try {
            const response = await fetch('/api/paradigms/active', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ type: paradigmType })
            });
            
            const data = await response.json();
            if (data.success) {
                this.currentParadigm = paradigmType;
                console.log('Paradigm changed successfully to:', paradigmType);
                
                // Reload node palette for new paradigm
                await this.loadNodePalette();
                
                // Apply visual changes immediately
                this.applyParadigmStyling(paradigmType);
                this.showParadigmChangeNotification(paradigmType);
                
                // Update paradigm-specific UI elements
                this.updateParadigmUI(paradigmType);
            } else {
                console.error('Failed to set paradigm:', data.error);
            }
        } catch (error) {
            console.error('Error setting paradigm:', error);
        }
    }
    
    updateParadigmUI(paradigmType) {
        // Update canvas instructions based on paradigm
        const canvasInstructions = document.querySelector('.canvas-instructions');
        if (canvasInstructions) {
            const instructions = {
                'node_based': 'Drag nodes from the palette and connect them to create data flows',
                'block_based': 'Snap blocks together to build sequential programs',
                'diagram_based': 'Create UML diagrams by adding classes and relationships',
                'timeline_based': 'Arrange temporal elements along the timeline'
            };
            canvasInstructions.textContent = instructions[paradigmType] || 'Select elements from the palette';
        }
        
        // Update palette header
        const paletteHeader = document.querySelector('.palette-header h3');
        if (paletteHeader) {
            const titles = {
                'node_based': 'Node Palette',
                'block_based': 'Block Palette',
                'diagram_based': 'Diagram Elements',
                'timeline_based': 'Timeline Elements'
            };
            paletteHeader.textContent = titles[paradigmType] || 'Element Palette';
        }
        
        // Show/hide paradigm-specific controls
        this.updateParadigmControls(paradigmType);
    }
    
    updateParadigmControls(paradigmType) {
        // Hide all paradigm-specific controls first
        document.querySelectorAll('.paradigm-control').forEach(control => {
            control.style.display = 'none';
        });
        
        // Show controls for current paradigm
        document.querySelectorAll(`.paradigm-control.${paradigmType.replace('_', '-')}`).forEach(control => {
            control.style.display = 'block';
        });
        
        // Update toolbar based on paradigm
        const toolbar = document.querySelector('.toolbar');
        if (toolbar) {
            // Remove existing paradigm classes
            toolbar.classList.remove('node-based', 'block-based', 'diagram-based', 'timeline-based');
            // Add current paradigm class
            toolbar.classList.add(paradigmType.replace('_', '-'));
        }
    }
    
    async handleValidate() {
        try {
            const response = await fetch('/api/canvas/validate', {
                method: 'POST'
            });
            
            const data = await response.json();
            if (data.success) {
                const isValid = data.data.valid;
                const errors = data.data.errors || [];
                const warnings = data.data.warnings || [];
                const nodeCount = data.data.node_count || 0;
                const connectionCount = data.data.connection_count || 0;
                const nodeResults = data.data.node_results || [];
                
                this.updateValidationStatus(isValid, errors);
                
                // Highlight invalid nodes on canvas
                this.clearValidationHighlights();
                nodeResults.forEach(result => {
                    if (!result.valid) {
                        this.highlightInvalidNode(result.node_id);
                    }
                });
                
                // Show detailed results
                if (!isValid) {
                    console.warn('Validation errors:', errors);
                    let message = `Validation Results\n\n`;
                    message += `Nodes: ${nodeCount}, Connections: ${connectionCount}\n\n`;
                    
                    if (errors.length > 0) {
                        message += `Errors:\n${errors.map(e => '- ' + e).join('\n')}\n\n`;
                    }
                    if (warnings.length > 0) {
                        message += `Warnings:\n${warnings.map(w => '- ' + w).join('\n')}\n\n`;
                    }
                    
                    // Show which nodes failed
                    const failedNodes = nodeResults.filter(r => !r.valid);
                    if (failedNodes.length > 0) {
                        message += `Invalid Nodes:\n`;
                        failedNodes.forEach(n => {
                            message += `- ${n.node_name} (${n.node_type}): ${n.errors.join(', ')}\n`;
                        });
                    }
                    
                    alert(message);
                } else {
                    let message = `Model is valid!\n\n`;
                    message += `Nodes: ${nodeCount}, Connections: ${connectionCount}`;
                    if (warnings.length > 0) {
                        message += `\n\nWarnings:\n${warnings.map(w => '- ' + w).join('\n')}`;
                    }
                    alert(message);
                }
            } else {
                console.error('Validation failed:', data.error);
                alert('Validation error: ' + data.error);
            }
        } catch (error) {
            console.error('Error validating model:', error);
            alert('Error during validation: ' + error.message);
        }
    }
    
    clearValidationHighlights() {
        document.querySelectorAll('.visual-node.validation-error').forEach(el => {
            el.classList.remove('validation-error');
        });
    }
    
    highlightInvalidNode(nodeId) {
        const nodeEl = document.querySelector(`[data-node-id="${nodeId}"]`);
        if (nodeEl) {
            nodeEl.classList.add('validation-error');
        }
    }
    
    async handleClear() {
        if (confirm('Are you sure you want to clear the canvas? This will remove all nodes and connections.')) {
            try {
                const response = await fetch('/api/canvas/clear', {
                    method: 'POST'
                });
                
                const data = await response.json();
                if (!data.success) {
                    console.error('Failed to clear canvas:', data.error);
                }
            } catch (error) {
                console.error('Error clearing canvas:', error);
            }
        }
    }
    
    handleZoomFit() {
        // Calculate bounds of all nodes
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        
        this.nodes.forEach(node => {
            const x = node.position[0];
            const y = node.position[1];
            minX = Math.min(minX, x);
            minY = Math.min(minY, y);
            maxX = Math.max(maxX, x + 120); // Node width
            maxY = Math.max(maxY, y + 80);  // Node height
        });
        
        if (this.nodes.size === 0) {
            this.setZoom(1.0);
            this.setPan(0, 0);
            return;
        }
        
        const padding = 50;
        const contentWidth = maxX - minX + padding * 2;
        const contentHeight = maxY - minY + padding * 2;
        
        const scaleX = this.viewport.width / contentWidth;
        const scaleY = this.viewport.height / contentHeight;
        const scale = Math.min(scaleX, scaleY, 1.0);
        
        const centerX = (minX + maxX) / 2;
        const centerY = (minY + maxY) / 2;
        
        this.setZoom(scale);
        this.setPan(
            this.viewport.width / 2 - centerX * scale,
            this.viewport.height / 2 - centerY * scale
        );
    }
    
    handleGridToggle() {
        const gridBackground = document.querySelector('.grid-background');
        const isVisible = gridBackground.style.display !== 'none';
        gridBackground.style.display = isVisible ? 'none' : 'block';
    }
    
    handlePaletteSearch(event) {
        const searchTerm = event.target.value.toLowerCase();
        const paletteNodes = document.querySelectorAll('.palette-node');
        
        paletteNodes.forEach(node => {
            const name = node.querySelector('.node-name').textContent.toLowerCase();
            const description = node.querySelector('.node-description').textContent.toLowerCase();
            const matches = name.includes(searchTerm) || description.includes(searchTerm);
            node.style.display = matches ? 'flex' : 'none';
        });
    }
    
    // ============================================
    // Generate Nodes Modal
    // ============================================
    
    initializeGenerateNodesModal() {
        const modal = document.getElementById('generate-nodes-modal');
        if (!modal) return;
        
        // Store references
        this.generateNodesModal = {
            element: modal,
            sourceType: 'module',
            generatedNodes: []
        };
        
        // Close buttons
        const closeBtn = document.getElementById('modal-close-btn');
        const cancelBtn = document.getElementById('modal-cancel-btn');
        if (closeBtn) closeBtn.addEventListener('click', () => this.hideGenerateNodesModal());
        if (cancelBtn) cancelBtn.addEventListener('click', () => this.hideGenerateNodesModal());
        
        // Backdrop click to close
        const backdrop = modal.querySelector('.modal-backdrop');
        if (backdrop) backdrop.addEventListener('click', () => this.hideGenerateNodesModal());
        
        // Source tabs
        const sourceTabs = modal.querySelectorAll('.source-tab');
        sourceTabs.forEach(tab => {
            tab.addEventListener('click', () => this.switchSourceTab(tab.dataset.source));
        });
        
        // Package chips
        const packageChips = modal.querySelectorAll('.package-chip');
        packageChips.forEach(chip => {
            chip.addEventListener('click', () => {
                const moduleInput = document.getElementById('module-name');
                if (moduleInput) {
                    moduleInput.value = chip.dataset.module;
                }
            });
        });
        
        // Generate button
        const generateBtn = document.getElementById('generate-btn');
        if (generateBtn) generateBtn.addEventListener('click', () => this.handleGenerateNodes());
        
        // Add to palette button
        const addBtn = document.getElementById('add-to-palette-btn');
        if (addBtn) addBtn.addEventListener('click', () => this.handleAddGeneratedToPalette());
    }
    
    showGenerateNodesModal() {
        const modal = document.getElementById('generate-nodes-modal');
        if (modal) {
            modal.style.display = 'flex';
            // Reset state
            this.resetGenerateNodesModal();
            // Refresh lucide icons in modal
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        }
    }
    
    hideGenerateNodesModal() {
        const modal = document.getElementById('generate-nodes-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    }
    
    resetGenerateNodesModal() {
        // Clear inputs
        const moduleInput = document.getElementById('module-name');
        const fileInput = document.getElementById('file-path');
        const pipInput = document.getElementById('pip-package');
        if (moduleInput) moduleInput.value = '';
        if (fileInput) fileInput.value = '';
        if (pipInput) pipInput.value = '';
        
        // Hide status and preview
        const status = document.getElementById('generate-status');
        const preview = document.getElementById('generated-preview');
        const addBtn = document.getElementById('add-to-palette-btn');
        if (status) status.style.display = 'none';
        if (preview) preview.style.display = 'none';
        if (addBtn) addBtn.style.display = 'none';
        
        // Reset to module tab
        this.switchSourceTab('module');
        
        // Clear stored nodes
        if (this.generateNodesModal) {
            this.generateNodesModal.generatedNodes = [];
        }
    }
    
    switchSourceTab(sourceType) {
        if (this.generateNodesModal) {
            this.generateNodesModal.sourceType = sourceType;
        }
        
        // Update tabs
        document.querySelectorAll('.source-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.source === sourceType);
        });
        
        // Show/hide panels
        const modulePanel = document.getElementById('module-panel');
        const filePanel = document.getElementById('file-panel');
        const pipPanel = document.getElementById('pip-panel');
        
        if (modulePanel) modulePanel.style.display = sourceType === 'module' ? 'block' : 'none';
        if (filePanel) filePanel.style.display = sourceType === 'file' ? 'block' : 'none';
        if (pipPanel) pipPanel.style.display = sourceType === 'pip' ? 'block' : 'none';
    }
    
    async handleGenerateNodes() {
        const sourceType = this.generateNodesModal?.sourceType || 'module';
        let source = '';
        
        // Get source based on type
        if (sourceType === 'module') {
            source = document.getElementById('module-name')?.value?.trim() || '';
        } else if (sourceType === 'file') {
            source = document.getElementById('file-path')?.value?.trim() || '';
        } else if (sourceType === 'pip') {
            source = document.getElementById('pip-package')?.value?.trim() || '';
        }
        
        if (!source) {
            this.showGenerateStatus('error', 'Please enter a source name or path');
            return;
        }
        
        // Show loading state
        this.showGenerateStatus('loading', `Generating nodes from ${source}...`);
        
        try {
            const response = await fetch('/api/library/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_type: sourceType,
                    source: source
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                const nodes = data.data?.nodes || [];
                this.generateNodesModal.generatedNodes = nodes;
                this.showGenerateStatus('success', `Generated ${nodes.length} nodes from ${data.data?.module || source}`);
                this.showGeneratedPreview(nodes);
            } else {
                this.showGenerateStatus('error', data.error || 'Failed to generate nodes');
            }
        } catch (error) {
            console.error('Generate nodes error:', error);
            this.showGenerateStatus('error', `Error: ${error.message}`);
        }
    }
    
    showGenerateStatus(type, message) {
        const status = document.getElementById('generate-status');
        if (!status) return;
        
        status.style.display = 'block';
        status.className = `generate-status ${type}`;
        
        const msgEl = status.querySelector('.status-message');
        if (msgEl) msgEl.textContent = message;
        
        const progressEl = status.querySelector('.status-progress');
        if (progressEl) progressEl.style.display = type === 'loading' ? 'block' : 'none';
    }
    
    showGeneratedPreview(nodes) {
        const preview = document.getElementById('generated-preview');
        const countEl = document.getElementById('generated-count');
        const listEl = preview?.querySelector('.generated-list');
        const addBtn = document.getElementById('add-to-palette-btn');
        
        if (!preview || !listEl) return;
        
        if (nodes.length === 0) {
            preview.style.display = 'none';
            if (addBtn) addBtn.style.display = 'none';
            return;
        }
        
        preview.style.display = 'block';
        if (countEl) countEl.textContent = nodes.length;
        if (addBtn) addBtn.style.display = 'inline-flex';
        
        // Render node list
        listEl.innerHTML = nodes.slice(0, 50).map(node => `
            <div class="generated-item">
                <div class="generated-item-icon">
                    <i data-lucide="${node.icon || 'code'}"></i>
                </div>
                <div class="generated-item-info">
                    <div class="generated-item-name">${node.name}</div>
                    <div class="generated-item-type">${node.type} - ${node.category}</div>
                </div>
            </div>
        `).join('');
        
        if (nodes.length > 50) {
            listEl.innerHTML += `<div class="generated-item" style="opacity:0.6;">
                <div class="generated-item-info">
                    <div class="generated-item-name">... and ${nodes.length - 50} more</div>
                </div>
            </div>`;
        }
        
        // Refresh icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }
    
    handleAddGeneratedToPalette() {
        const nodes = this.generateNodesModal?.generatedNodes || [];
        if (nodes.length === 0) return;
        
        // Add nodes to palette definitions
        nodes.forEach(node => {
            if (!this.paletteNodes.find(n => n.id === node.id)) {
                this.paletteNodes.push(node);
            }
        });
        
        // Re-render palette
        this.renderNodePalette();
        
        // Show success message
        this.showGenerateStatus('success', `Added ${nodes.length} nodes to palette!`);
        
        // Hide modal after short delay
        setTimeout(() => {
            this.hideGenerateNodesModal();
        }, 1000);
    }
    
    handleCategoryToggle(event) {
        const header = event.target;
        const category = header.closest('.palette-category');
        const nodes = category.querySelector('.category-nodes');
        const icon = header.querySelector('i');
        
        const isExpanded = nodes.style.display !== 'none';
        document.querySelectorAll('.category-nodes').forEach(section => {
            section.style.display = 'none';
        });
        document.querySelectorAll('.category-header .category-icon').forEach(headerIcon => {
            headerIcon.setAttribute('data-lucide', 'chevron-right');
        });
        nodes.style.display = isExpanded ? 'none' : 'block';
        icon.setAttribute('data-lucide', isExpanded ? 'chevron-right' : 'chevron-down');
        
        // Refresh icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }
    
    handlePositionChange() {
        if (this.selectedNodes.size !== 1) return;
        
        const nodeId = Array.from(this.selectedNodes)[0];
        const x = parseFloat(document.getElementById('prop-pos-x').value) || 0;
        const y = parseFloat(document.getElementById('prop-pos-y').value) || 0;
        
        this.moveNodeTo(nodeId, x, y);
    }
    
    async moveNodeTo(nodeId, x, y) {
        try {
            const response = await fetch(`/api/canvas/nodes/${nodeId}/move`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    position: [x, y]
                })
            });
            
            const data = await response.json();
            if (data.success) {
                this.updateNodePosition(nodeId, [x, y]);
            }
        } catch (error) {
            console.error('Error moving node:', error);
        }
    }
    
    updateNodePosition(nodeId, position) {
        const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);
        if (nodeElement) {
            nodeElement.setAttribute('transform', `translate(${position[0]}, ${position[1]})`);
            this.updateNodeConnections(nodeId);
        }
        
        // Update stored data
        const nodeData = this.nodes.get(nodeId);
        if (nodeData) {
            nodeData.position = position;
        }
        
        this.scheduleSaveCanvasState();
    }
    
    handleKeyDown(event) {
        // Code Dive intercepts Escape before anything else
        if (event.key === 'Escape' && this.codeDive.active) {
            event.preventDefault();
            this.exitCodeDive();
            return;
        }

        if (this.isTextInputTarget(event.target)) {
            return;
        }
        
        const PAN_SPEED = 50;
        
        if (event.key === 'Delete' || event.key === 'Backspace') {
            event.preventDefault();
            this.deleteSelected();
        } else if (event.key === 'Escape') {
            this.clearSelection();
        } else if (event.ctrlKey || event.metaKey) {
            // Ctrl/Cmd shortcuts
            switch (event.key.toLowerCase()) {
                case 'a':
                    event.preventDefault();
                    this.selectAll();
                    break;
                case 's':
                    event.preventDefault();
                    this.saveCanvasState();
                    break;
                case 'z':
                    event.preventDefault();
                    // TODO: Undo
                    break;
                case 'y':
                    event.preventDefault();
                    // TODO: Redo
                    break;
                case 'e':
                    event.preventDefault();
                    this.showExportCodeDialog();
                    break;
                case 'd':
                    event.preventDefault();
                    this.showMultiDebuggerPanel();
                    break;
            }
        } else if (event.shiftKey) {
            // Shift + Arrow keys for faster panning
            switch (event.key) {
                case 'ArrowUp':
                    event.preventDefault();
                    this.panCanvas(0, PAN_SPEED * 2);
                    break;
                case 'ArrowDown':
                    event.preventDefault();
                    this.panCanvas(0, -PAN_SPEED * 2);
                    break;
                case 'ArrowLeft':
                    event.preventDefault();
                    this.panCanvas(PAN_SPEED * 2, 0);
                    break;
                case 'ArrowRight':
                    event.preventDefault();
                    this.panCanvas(-PAN_SPEED * 2, 0);
                    break;
            }
        } else {
            // Regular keys
            switch (event.key) {
                case 'ArrowUp':
                    event.preventDefault();
                    this.panCanvas(0, PAN_SPEED);
                    break;
                case 'ArrowDown':
                    event.preventDefault();
                    this.panCanvas(0, -PAN_SPEED);
                    break;
                case 'ArrowLeft':
                    event.preventDefault();
                    this.panCanvas(PAN_SPEED, 0);
                    break;
                case 'ArrowRight':
                    event.preventDefault();
                    this.panCanvas(-PAN_SPEED, 0);
                    break;
                case '+':
                case '=':
                    event.preventDefault();
                    this.zoomIn();
                    break;
                case '-':
                case '_':
                    event.preventDefault();
                    this.zoomOut();
                    break;
                case '0':
                    event.preventDefault();
                    this.resetZoom();
                    break;
                case 'f':
                case 'F':
                    event.preventDefault();
                    this.handleZoomFit();
                    break;
                case ' ':
                    // Space key - enable pan mode
                    event.preventDefault();
                    this.enablePanMode();
                    break;
            }
        }
    }
    
    handleKeyUp(event) {
        if (event.key === ' ') {
            this.disablePanMode();
        }
    }
    
    panCanvas(deltaX, deltaY) {
        this.viewport.panX += deltaX;
        this.viewport.panY += deltaY;
        this.applyViewportTransform();
        this.updateViewportDisplay();
    }
    
    zoomIn() {
        const newZoom = Math.min(this.viewport.zoom * 1.2, 5);
        this.setZoom(newZoom);
    }
    
    zoomOut() {
        const newZoom = Math.max(this.viewport.zoom / 1.2, 0.1);
        this.setZoom(newZoom);
    }
    
    resetZoom() {
        this.viewport.zoom = 1;
        this.viewport.panX = 0;
        this.viewport.panY = 0;
        this.applyViewportTransform();
        this.updateViewportDisplay();
    }
    
    setZoom(zoom, centerX = null, centerY = null) {
        const oldZoom = this.viewport.zoom;
        this.viewport.zoom = zoom;

        // Adjust pan so the point under the cursor stays fixed
        if (centerX !== null && centerY !== null) {
            this.viewport.panX = centerX - (centerX - this.viewport.panX) * (zoom / oldZoom);
            this.viewport.panY = centerY - (centerY - this.viewport.panY) * (zoom / oldZoom);
        }

        this.applyViewportTransform();
        this.updateViewportDisplay();
    }
    
    enablePanMode() {
        this.isPanModeActive = true;
        if (this.canvas) {
            this.canvas.style.cursor = 'grab';
        }
    }
    
    disablePanMode() {
        this.isPanModeActive = false;
        if (this.canvas) {
            this.canvas.style.cursor = 'default';
        }
    }

    isTextInputTarget(target) {
        if (!target) return false;
        if (target.isContentEditable) return true;
        
        const tagName = target.tagName ? target.tagName.toLowerCase() : '';
        if (tagName === 'input' || tagName === 'textarea' || tagName === 'select') {
            return true;
        }
        
        return false;
    }
    
    async deleteSelected() {
        // Delete selected connections
        for (const connectionId of this.selectedConnections) {
            try {
                await fetch(`/api/canvas/connections/${connectionId}`, {
                    method: 'DELETE'
                });
            } catch (error) {
                console.error('Error deleting connection:', error);
            }
        }
        
        // Delete selected nodes
        for (const nodeId of this.selectedNodes) {
            try {
                await fetch(`/api/canvas/nodes/${nodeId}`, {
                    method: 'DELETE'
                });
            } catch (error) {
                console.error('Error deleting node:', error);
            }
        }
    }
    
    selectAll() {
        this.clearSelection();
        this.nodes.forEach((nodeData, nodeId) => {
            this.selectedNodes.add(nodeId);
            const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);
            if (nodeElement) {
                const rect = nodeElement.querySelector('.node-body');
                rect.classList.add('selected');
            }
        });
        this.updatePropertiesPanel();
    }
    
    showContextMenu(x, y, target) {
        const contextMenu = document.getElementById('context-menu');
        contextMenu.style.display = 'block';
        contextMenu.style.left = `${x}px`;
        contextMenu.style.top = `${y}px`;
        
        // Store target for context actions
        contextMenu.dataset.target = target.closest('.visual-node, .connection').dataset.nodeId || 
                                     target.closest('.visual-node, .connection').dataset.connectionId;
        contextMenu.dataset.targetType = target.closest('.visual-node') ? 'node' : 'connection';
    }
    
    handleDocumentClick(event) {
        const contextMenu = document.getElementById('context-menu');
        
        if (event.target.closest('.context-item')) {
            const action = event.target.closest('.context-item').dataset.action;
            const targetId = contextMenu.dataset.target;
            const targetType = contextMenu.dataset.targetType;
            
            this.handleContextAction(action, targetId, targetType);
        }
        
        // Hide context menu
        contextMenu.style.display = 'none';
        
        // Clear selection if clicking on empty space
        if (!event.target.closest('.visual-node, .connection, .properties-panel') && !this.isDialogTarget(event.target)) {
            this.clearSelection();
        }
    }

    isDialogTarget(target) {
        if (!target) return false;
        return Boolean(target.closest(
            '.add-parameter-dialog, .analysis-results-dialog, .error-dialog, ' +
            '.progress-dialog, .repository-import-dialog, .translated-code-dialog, ' +
            '.node-details-modal, .uir-translation-panel'
        ));
    }
    
    async handleContextAction(action, targetId, targetType) {
        switch (action) {
            case 'delete':
                if (targetType === 'node') {
                    await fetch(`/api/canvas/nodes/${targetId}`, { method: 'DELETE' });
                } else if (targetType === 'connection') {
                    await fetch(`/api/canvas/connections/${targetId}`, { method: 'DELETE' });
                }
                break;
            case 'duplicate':
                if (targetType === 'node') {
                    const nodeData = this.nodes.get(targetId);
                    if (nodeData) {
                        const newPosition = [nodeData.position[0] + 50, nodeData.position[1] + 50];
                        await this.createNode({
                            type: nodeData.type,
                            name: nodeData.metadata?.name || nodeData.type,
                            description: nodeData.metadata?.description || ''
                        }, { x: newPosition[0], y: newPosition[1] });
                    }
                }
                break;
            case 'properties':
                if (targetType === 'node') {
                    this.selectNode(targetId);
                }
                break;
        }
    }
    
    handleWindowResize() {
        const rect = this.canvas.getBoundingClientRect();
        this.viewport.width = rect.width;
        this.viewport.height = rect.height;
    }
    
    // Status and UI updates
    updateConnectionStatus(connected) {
        // Delegate to SettingsHub if available (replaces old static label)
        if (window.settingsHub) {
            window.settingsHub.updateConnectionStatus(connected);
            return;
        }
        // Fallback for legacy path
        const statusElement = document.getElementById('connection-status');
        const icon = statusElement.querySelector('i');
        
        if (connected) {
            statusElement.innerHTML = '<i data-lucide="wifi"></i> Connected';
            statusElement.classList.remove('text-error');
            statusElement.classList.add('text-success');
        } else {
            statusElement.innerHTML = '<i data-lucide="wifi-off"></i> Disconnected';
            statusElement.classList.remove('text-success');
            statusElement.classList.add('text-error');
        }
        
        // Refresh icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }
    
    updateStatus() {
        document.getElementById('node-count').textContent = `Nodes: ${this.nodes.size}`;
        document.getElementById('connection-count').textContent = `Connections: ${this.connections.size}`;
    }
    
    updateValidationStatus(isValid, errors = []) {
        const statusElement = document.getElementById('validation-status');
        
        if (isValid) {
            statusElement.innerHTML = '<i data-lucide="check-circle" class="text-success"></i> Valid';
        } else {
            statusElement.innerHTML = '<i data-lucide="alert-circle" class="text-error"></i> Invalid';
        }
        
        // Refresh icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }
    
    updateParadigm(paradigmType) {
        this.currentParadigm = paradigmType;
        document.getElementById('paradigm-select').value = paradigmType;
        
        // Add visual feedback for paradigm change
        this.showParadigmChangeNotification(paradigmType);
        
        // Apply paradigm-specific visual styling
        this.applyParadigmStyling(paradigmType);
    }
    
    showParadigmChangeNotification(paradigmType) {
        // Create notification
        const notification = document.createElement('div');
        notification.className = 'paradigm-notification';
        notification.innerHTML = `
            <div class="notification-content">
                <i data-lucide="zap"></i>
                <span>Switched to ${paradigmType.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())} paradigm</span>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Animate in
        setTimeout(() => notification.classList.add('show'), 100);
        
        // Remove after 3 seconds
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
        
        // Update Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }
    
    applyParadigmStyling(paradigmType) {
        // Remove existing paradigm classes
        document.body.classList.remove('paradigm-node-based', 'paradigm-block-based', 'paradigm-diagram-based', 'paradigm-timeline-based');
        
        // Add new paradigm class
        document.body.classList.add(`paradigm-${paradigmType.replace('_', '-')}`);
        
        // Update canvas styling based on paradigm
        const canvas = document.getElementById('canvas');
        if (canvas) {
            canvas.setAttribute('data-paradigm', paradigmType);
        }
        
        // Log paradigm change for debugging
        console.log(`Applied ${paradigmType} paradigm styling`);
    }
    
    clearCanvas() {
        this.nodes.clear();
        this.connections.clear();
        this.selectedNodes.clear();
        this.selectedConnections.clear();
        
        this.nodesLayer.innerHTML = '';
        this.connectionsLayer.innerHTML = '';
        this.selectionLayer.innerHTML = '';
        
        this.updateStatus();
        this.updatePropertiesPanel();
        this.scheduleSaveCanvasState();
    }

    scheduleSaveCanvasState() {
        if (this.isRestoring) return;
        if (this.saveTimeoutId) {
            clearTimeout(this.saveTimeoutId);
        }
        this.setAutosaveStatus('Saving...');
        this.saveTimeoutId = setTimeout(() => {
            this.saveCanvasState();
        }, 300);
    }

    saveCanvasState() {
        if (this.isRestoring) return;
        const state = this.serializeCanvasState();
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(state));
            this.setAutosaveStatus('Saved');
        } catch (error) {
            console.warn('Failed to save canvas state:', error);
            this.setAutosaveStatus('Save failed');
        }
    }

    setAutosaveStatus(text) {
        const indicator = document.getElementById('autosave-indicator');
        if (indicator) {
            indicator.textContent = text;
        }
    }

    serializeCanvasState() {
        return {
            nodes: Array.from(this.nodes.entries()).map(([nodeId, nodeData]) => ({
                id: nodeId,
                type: nodeData.type,
                position: nodeData.position,
                parameters: nodeData.parameters || {},
                metadata: nodeData.metadata || {},
                inputs: nodeData.inputs || [],
                outputs: nodeData.outputs || []
            })),
            connections: Array.from(this.connections.values()).map((connection) => ({
                id: connection.id,
                source_node_id: connection.source_node_id,
                source_port: connection.source_port,
                target_node_id: connection.target_node_id,
                target_port: connection.target_port,
                data_type: connection.data_type
            })),
            viewport: { ...this.viewport }
        };
    }

    getSavedCanvasState() {
        try {
            const raw = localStorage.getItem(this.storageKey);
            return raw ? JSON.parse(raw) : null;
        } catch (error) {
            console.warn('Failed to read saved canvas state:', error);
            return null;
        }
    }

    async restoreCanvasState() {
        const saved = this.getSavedCanvasState();
        if (!saved || !saved.nodes || saved.nodes.length === 0) {
            return;
        }
        
        this.isRestoring = true;
        try {
            await fetch('/api/canvas/clear', { method: 'POST' });
        } catch (error) {
            console.warn('Failed to clear backend canvas during restore:', error);
        }
        
        this.clearCanvas();
        
        const idMap = new Map();
        for (const node of saved.nodes) {
            try {
                const response = await fetch('/api/canvas/nodes', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        type: node.type,
                        position: node.position,
                        parameters: node.parameters,
                        metadata: node.metadata,
                        inputs: node.inputs,
                        outputs: node.outputs
                    })
                });
                
                const result = await response.json();
                if (result.success) {
                    idMap.set(node.id, result.data.node_id);
                }
            } catch (error) {
                console.error('Failed to restore node:', error);
            }
        }
        
        for (const connection of saved.connections || []) {
            const sourceId = idMap.get(connection.source_node_id);
            const targetId = idMap.get(connection.target_node_id);
            if (!sourceId || !targetId) {
                continue;
            }
            try {
                await fetch('/api/canvas/connections', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        source_node_id: sourceId,
                        source_port: connection.source_port,
                        target_node_id: targetId,
                        target_port: connection.target_port
                    })
                });
            } catch (error) {
                console.error('Failed to restore connection:', error);
            }
        }
        
        if (saved.viewport) {
            this.viewport = { ...this.viewport, ...saved.viewport };
            this.applyViewportTransform();
            this.updateViewportDisplay();
        }
        
        this.isRestoring = false;
        this.saveCanvasState();
    }

    initializeProjectMeta() {
        const projectInput = document.getElementById('project-name');
        if (!projectInput) return;
        
        const saved = this.getProjectMeta();
        if (saved?.name) {
            projectInput.value = saved.name;
            document.title = `${saved.name} | Visual Editor Core`;
        }
        
        projectInput.addEventListener('input', () => {
            const name = projectInput.value.trim() || 'Untitled Flow';
            this.saveProjectMeta({ name });
            document.title = `${name} | Visual Editor Core`;
        });
    }

    getProjectMeta() {
        try {
            const raw = localStorage.getItem(this.projectKey);
            return raw ? JSON.parse(raw) : null;
        } catch (error) {
            console.warn('Failed to read project meta:', error);
            return null;
        }
    }

    saveProjectMeta(meta) {
        try {
            localStorage.setItem(this.projectKey, JSON.stringify(meta));
        } catch (error) {
            console.warn('Failed to save project meta:', error);
        }
    }

    loadUiSettings() {
        try {
            const raw = localStorage.getItem(this.uiSettingsKey);
            if (!raw) {
                return { showLabelOverlay: false, showDisplayLabels: false };
            }
            const parsed = JSON.parse(raw);
            return {
                showLabelOverlay: Boolean(parsed.showLabelOverlay),
                showDisplayLabels: Boolean(parsed.showDisplayLabels)
            };
        } catch (error) {
            console.warn('Failed to read UI settings:', error);
            return { showLabelOverlay: false, showDisplayLabels: false };
        }
    }

    saveUiSettings(settings) {
        this.uiSettings = { ...this.uiSettings, ...settings };
        try {
            localStorage.setItem(this.uiSettingsKey, JSON.stringify(this.uiSettings));
        } catch (error) {
            console.warn('Failed to save UI settings:', error);
        }
    }

    initializeGlobalSettingsControls() {
        const headerRight = document.querySelector('.header-right');
        if (!headerRight) return;
        
        const labelToggle = document.createElement('button');
        labelToggle.id = 'toggle-label-overlay';
        labelToggle.className = 'btn btn-secondary';
        labelToggle.innerHTML = '<i data-lucide="tag"></i> Labels';
        labelToggle.title = 'Toggle label overlays on nodes';
        labelToggle.classList.toggle('active', this.uiSettings.showLabelOverlay);
        
        labelToggle.addEventListener('click', () => {
            const nextValue = !this.uiSettings.showLabelOverlay;
            this.saveUiSettings({ showLabelOverlay: nextValue });
            labelToggle.classList.toggle('active', nextValue);
            this.updateAllNodeTitles();
        });
        
        const displayLabelToggle = document.createElement('button');
        displayLabelToggle.id = 'toggle-display-label';
        displayLabelToggle.className = 'btn btn-secondary';
        displayLabelToggle.innerHTML = '<i data-lucide="message-square"></i> Hover';
        displayLabelToggle.title = 'Toggle hover display labels';
        displayLabelToggle.classList.toggle('active', this.uiSettings.showDisplayLabels);
        
        displayLabelToggle.addEventListener('click', () => {
            const nextValue = !this.uiSettings.showDisplayLabels;
            this.saveUiSettings({ showDisplayLabels: nextValue });
            displayLabelToggle.classList.toggle('active', nextValue);
            if (!nextValue) {
                this.hideNodeHoverLabel();
            }
        });
        
        headerRight.appendChild(labelToggle);
        headerRight.appendChild(displayLabelToggle);
        
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    updateAllNodeTitles() {
        this.nodes.forEach((_, nodeId) => {
            this.updateNodeTitle(nodeId);
        });
    }

    initializeSessionControls() {
        const headerRight = document.querySelector('.header-right');
        if (!headerRight) return;
        
        const exportBtn = document.createElement('button');
        exportBtn.id = 'export-canvas-btn';
        exportBtn.className = 'btn btn-secondary';
        exportBtn.innerHTML = '<i data-lucide="download"></i> Export Canvas';
        exportBtn.addEventListener('click', () => this.exportCanvasState());
        
        const importBtn = document.createElement('button');
        importBtn.id = 'import-canvas-btn';
        importBtn.className = 'btn btn-secondary';
        importBtn.innerHTML = '<i data-lucide="upload-cloud"></i> Import Canvas';
        
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = 'application/json';
        fileInput.style.display = 'none';
        fileInput.addEventListener('change', (event) => {
            const file = event.target.files?.[0];
            if (file) {
                this.importCanvasState(file);
            }
        });
        
        importBtn.addEventListener('click', () => fileInput.click());
        
        headerRight.insertBefore(exportBtn, headerRight.firstChild);
        headerRight.insertBefore(importBtn, exportBtn.nextSibling);
        headerRight.appendChild(fileInput);
        
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }

    exportCanvasState() {
        const state = this.serializeCanvasState();
        const projectName = (document.getElementById('project-name')?.value || 'canvas').trim();

        // Include engine tabs so the JSON is a complete project snapshot
        let engineTabs = [];
        if (window.liveExec && typeof window.liveExec._getEngineTabsData === 'function') {
            engineTabs = window.liveExec._getEngineTabsData();
        }

        const payload = {
            project: {
                name: projectName,
                saved_at: new Date().toISOString()
            },
            state,
            engine_tabs: engineTabs
        };
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `${projectName || 'canvas'}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(link.href);
    }

    async importCanvasState(file) {
        try {
            const text = await file.text();
            const payload = JSON.parse(text);
            const state = payload.state || payload;

            // Reset the backend execution namespace so stale variables
            // from previous sessions don't leak into new imports.
            try {
                await fetch('/api/execution/reset-namespace', { method: 'POST' });
            } catch (resetErr) {
                console.warn('Could not reset execution namespace before import:', resetErr);
            }

            // Normalize imported data so it matches what restoreFromState expects
            this._normalizeImportState(state);

            await this.restoreFromState(state);
            if (payload.project?.name) {
                const projectInput = document.getElementById('project-name');
                if (projectInput) {
                    projectInput.value = payload.project.name;
                    this.saveProjectMeta({ name: payload.project.name });
                }
            }

            // ── Populate engine tabs from the imported JSON ──
            if (window.liveExec && Array.isArray(payload.engine_tabs) && payload.engine_tabs.length > 0) {
                window.liveExec.loadFromJSON(payload.engine_tabs);
            }
        } catch (error) {
            console.error('Failed to import canvas state:', error);
        }
    }

    /**
     * Normalizes an imported state object so it conforms to the internal format
     * expected by restoreFromState / createNodeElement.
     *  - position: must be [x, y] array, not {x, y} object
     *  - nodes must have type, parameters, metadata, inputs, outputs
     *  - connections must use source_node_id / target_node_id / source_port / target_port
     */
    _normalizeImportState(state) {
        if (!state) return;

        // --- Normalize nodes ---
        if (Array.isArray(state.nodes)) {
            state.nodes = state.nodes.map(n => {
                // Position: convert {x,y} object to [x,y] array
                let pos = n.position;
                if (pos && !Array.isArray(pos)) {
                    pos = [pos.x ?? 0, pos.y ?? 0];
                }
                if (!pos) pos = [0, 0];

                return {
                    id: n.id,
                    type: n.type || 'function',
                    position: pos,
                    parameters: n.parameters || {},
                    metadata: n.metadata || {
                        name: n.label || n.name || n.id,
                        description: n.documentation || n.description || ''
                    },
                    inputs: n.inputs || [{ name: 'input', type: 'any' }],
                    outputs: n.outputs || [{ name: 'output', type: 'any' }]
                };
            });
        }

        // --- Normalize connections ---
        if (Array.isArray(state.connections)) {
            state.connections = state.connections.map(c => ({
                source_node_id: c.source_node_id || c.source,
                source_port: c.source_port || 'output',
                target_node_id: c.target_node_id || c.target,
                target_port: c.target_port || 'input'
            }));
        }
    }

    async restoreFromState(state) {
        if (!state || !state.nodes) return;
        this.isRestoring = true;
        try {
            await fetch('/api/canvas/clear', { method: 'POST' });
        } catch (error) {
            console.warn('Failed to clear backend canvas during restore:', error);
        }

        this.clearCanvas();

        const idMap = new Map();
        for (const node of state.nodes) {
            try {
                const response = await fetch('/api/canvas/nodes', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        type: node.type,
                        position: node.position,
                        parameters: node.parameters,
                        metadata: node.metadata,
                        inputs: node.inputs,
                        outputs: node.outputs
                    })
                });

                if (!response.ok) {
                    // Backend failed (500 or similar) — fallback to client-only rendering so import continues
                    console.warn(`Server refused node ${node.id} (${response.status}). Rendering client-only fallback.`);
                    const fallbackId = node.id || `local_${Date.now()}_${Math.random().toString(36).substr(2,9)}`;
                    try {
                        this.addNodeToCanvas(fallbackId, node);
                    } catch (err) {
                        console.error('Failed to render fallback node locally:', err);
                    }
                    idMap.set(node.id, fallbackId);
                    continue;
                }

                // Try to parse JSON, but tolerate invalid JSON from error pages
                let result = null;
                try {
                    result = await response.json();
                } catch (err) {
                    console.warn('Non-JSON response while restoring node', node.id, err);
                }

                if (result && result.success) {
                    idMap.set(node.id, result.data.node_id);
                } else {
                    // Backend responded but didn't return success — fallback visually
                    console.warn(`Backend did not create node ${node.id}. Falling back to visual-only.`);
                    const fallbackId = node.id || `local_${Date.now()}_${Math.random().toString(36).substr(2,9)}`;
                    try {
                        this.addNodeToCanvas(fallbackId, node);
                    } catch (err) {
                        console.error('Failed to render fallback node locally:', err);
                    }
                    idMap.set(node.id, fallbackId);
                }
            } catch (error) {
                console.error('Failed to restore node:', error);
                const fallbackId = node.id || `local_${Date.now()}_${Math.random().toString(36).substr(2,9)}`;
                try {
                    this.addNodeToCanvas(fallbackId, node);
                } catch (err) {
                    console.error('Failed to render fallback node locally after exception:', err);
                }
                idMap.set(node.id, fallbackId);
            }
        }

        for (const connection of state.connections || []) {
            const sourceId = idMap.get(connection.source_node_id) || connection.source_node_id;
            const targetId = idMap.get(connection.target_node_id) || connection.target_node_id;
            if (!sourceId || !targetId) {
                console.warn('Skipping connection during restore (missing node mapping):', connection);
                continue;
            }
            try {
                const response = await fetch('/api/canvas/connections', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        source_node_id: sourceId,
                        source_port: connection.source_port,
                        target_node_id: targetId,
                        target_port: connection.target_port
                    })
                });

                if (!response.ok) {
                    console.warn(`Server refused connection ${connection.id || ''} (${response.status}). Adding visual-only connection.`);
                    const connFallback = {
                        id: connection.id || `conn_${Date.now()}_${Math.random().toString(36).substr(2,6)}`,
                        sourceNode: sourceId,
                        targetNode: targetId,
                        sourcePort: connection.source_port,
                        targetPort: connection.target_port
                    };
                    try {
                        this.addConnectionToCanvas(connFallback);
                    } catch (err) {
                        console.error('Failed to render fallback connection locally:', err);
                    }
                    continue;
                }

                // Attempt to parse response; if backend returns valid connection object, add it
                let connResult = null;
                try {
                    connResult = await response.json();
                } catch (err) {
                    // ignore
                }

                if (connResult && connResult.success && connResult.data) {
                    this.addConnectionToCanvas(connResult.data);
                } else {
                    // fallback visual
                    const connFallback = {
                        id: connection.id || `conn_${Date.now()}_${Math.random().toString(36).substr(2,6)}`,
                        sourceNode: sourceId,
                        targetNode: targetId,
                        sourcePort: connection.source_port,
                        targetPort: connection.target_port
                    };
                    try {
                        this.addConnectionToCanvas(connFallback);
                    } catch (err) {
                        console.error('Failed to render fallback connection locally after parse error:', err);
                    }
                }
            } catch (error) {
                console.error('Failed to restore connection:', error);
                const connFallback = {
                    id: connection.id || `conn_${Date.now()}_${Math.random().toString(36).substr(2,6)}`,
                    sourceNode: sourceId,
                    targetNode: targetId,
                    sourcePort: connection.source_port,
                    targetPort: connection.target_port
                };
                try {
                    this.addConnectionToCanvas(connFallback);
                } catch (err) {
                    console.error('Failed to render fallback connection locally after exception:', err);
                }
            }
        }

        if (state.viewport) {
            this.viewport = { ...this.viewport, ...state.viewport };
            this.applyViewportTransform();
            this.updateViewportDisplay();
        }

        this.isRestoring = false;
        this.saveCanvasState();
    }
    
    // Live Execution Visualization Methods
    initializeLiveExecution() {
        console.log('Initializing live execution visualization...');
        
        // Execution controls removed from header — redundant with Live Execution and Runtime panels
        // this.addExecutionControls();
        
        // Set up WebSocket listeners for execution events
        this.setupExecutionEventListeners();
        
        // Initialize execution visualization overlay
        this.initializeExecutionOverlay();
    }
    
    addExecutionControls() {
        const headerRight = document.querySelector('.header-right');
        if (!headerRight) return;
        
        // Create execution controls container
        const executionControls = document.createElement('div');
        executionControls.className = 'execution-controls';
        executionControls.innerHTML = `
            <button id="play-btn" class="btn btn-success" title="Start Execution">
                <i data-lucide="play"></i>
            </button>
            <button id="step-btn" class="btn btn-secondary" title="Step Execution" disabled>
                <i data-lucide="step-forward"></i>
            </button>
            <button id="pause-btn" class="btn btn-warning" title="Pause Execution" disabled>
                <i data-lucide="pause"></i>
            </button>
            <button id="stop-btn" class="btn btn-danger" title="Stop Execution" disabled>
                <i data-lucide="square"></i>
            </button>
            <div class="execution-speed-control">
                <label for="speed-slider">Speed:</label>
                <input type="range" id="speed-slider" min="0.1" max="3.0" step="0.1" value="1.0">
                <span id="speed-display">1.0x</span>
            </div>
        `;
        
        // Add event listeners
        executionControls.querySelector('#play-btn').addEventListener('click', () => this.startExecution());
        executionControls.querySelector('#step-btn').addEventListener('click', () => this.stepExecution());
        executionControls.querySelector('#pause-btn').addEventListener('click', () => this.pauseExecution());
        executionControls.querySelector('#stop-btn').addEventListener('click', () => this.stopExecution());
        
        const speedSlider = executionControls.querySelector('#speed-slider');
        const speedDisplay = executionControls.querySelector('#speed-display');
        speedSlider.addEventListener('input', (e) => {
            const speed = parseFloat(e.target.value);
            this.executionState.executionSpeed = speed;
            speedDisplay.textContent = `${speed}x`;
        });
        
        headerRight.insertBefore(executionControls, headerRight.firstChild);
        
        // Refresh Lucide icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }
    
    setupExecutionEventListeners() {
        if (!this.socket) return;
        
        // Listen for execution events from the backend
        this.socket.on('execution_event', (eventData) => {
            this.handleExecutionEvent(eventData);
        });
        
        // Listen for execution state changes
        this.socket.on('execution_started', (data) => {
            this.onExecutionStarted(data);
        });
        
        this.socket.on('execution_completed', (data) => {
            this.onExecutionCompleted(data);
        });
        
        this.socket.on('execution_error', (data) => {
            this.onExecutionError(data);
        });
    }
    
    initializeExecutionOverlay() {
        // Create execution visualization overlay
        const overlay = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        overlay.classList.add('execution-overlay');
        this.canvasContent.appendChild(overlay);
        
        // Create layers for different visualization elements
        const nodeHighlights = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        nodeHighlights.classList.add('node-highlights');
        overlay.appendChild(nodeHighlights);
        
        const dataFlowAnimations = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        dataFlowAnimations.classList.add('data-flow-animations');
        overlay.appendChild(dataFlowAnimations);
        
        const executionPath = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        executionPath.classList.add('execution-path');
        overlay.appendChild(executionPath);
        
        // Store references
        this.executionOverlay = {
            container: overlay,
            nodeHighlights: nodeHighlights,
            dataFlowAnimations: dataFlowAnimations,
            executionPath: executionPath
        };
    }
    
    async startExecution() {
        if (this.executionState.isExecuting) return;
        
        try {
            // Update UI state
            this.setExecutionControlsState('executing');
            
            // Clear previous execution visualization
            this.clearExecutionVisualization();
            
            // Start execution on backend
            const response = await fetch('/api/execution/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    mode: 'normal',
                    speed: this.executionState.executionSpeed,
                    animation_enabled: this.executionState.animationEnabled
                })
            });
            
            const data = await response.json();
            if (!data.success) {
                console.error('Failed to start execution:', data.error);
                this.setExecutionControlsState('idle');
                return;
            }
            
            this.executionState.isExecuting = true;
            console.log('Execution started successfully');
            
        } catch (error) {
            console.error('Error starting execution:', error);
            this.setExecutionControlsState('idle');
        }
    }
    
    async stepExecution() {
        if (!this.executionState.isExecuting) return;
        
        try {
            const response = await fetch('/api/execution/step', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            if (data.success) {
                console.log('Step execution:', data.data);
            }
            
        } catch (error) {
            console.error('Error stepping execution:', error);
        }
    }
    
    async pauseExecution() {
        if (!this.executionState.isExecuting) return;
        
        try {
            // This would pause the execution on the backend
            console.log('Pausing execution...');
            this.setExecutionControlsState('paused');
            
        } catch (error) {
            console.error('Error pausing execution:', error);
        }
    }
    
    async stopExecution() {
        try {
            const response = await fetch('/api/execution/stop', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            if (data.success) {
                this.onExecutionStopped();
            }
            
        } catch (error) {
            console.error('Error stopping execution:', error);
        }
    }
    
    setExecutionControlsState(state) {
        const playBtn = document.getElementById('play-btn');
        const stepBtn = document.getElementById('step-btn');
        const pauseBtn = document.getElementById('pause-btn');
        const stopBtn = document.getElementById('stop-btn');
        
        if (!playBtn) return;
        
        // Reset all buttons
        [playBtn, stepBtn, pauseBtn, stopBtn].forEach(btn => {
            btn.disabled = false;
            btn.classList.remove('active');
        });
        
        switch (state) {
            case 'idle':
                stepBtn.disabled = true;
                pauseBtn.disabled = true;
                stopBtn.disabled = true;
                break;
            case 'executing':
                playBtn.disabled = true;
                playBtn.classList.add('active');
                break;
            case 'paused':
                pauseBtn.classList.add('active');
                break;
        }
    }
    
    handleExecutionEvent(eventData) {
        console.log('Execution event:', eventData);
        
        // Store the event
        this.executionState.executionEvents.push(eventData);
        
        // Handle different event types
        switch (eventData.event_type) {
            case 'node_start':
                this.visualizeNodeStart(eventData);
                break;
            case 'node_complete':
                this.visualizeNodeComplete(eventData);
                break;
            case 'node_error':
                this.visualizeNodeError(eventData);
                break;
            case 'data_flow':
                this.visualizeDataFlow(eventData);
                break;
            case 'variable_update':
                this.visualizeVariableUpdate(eventData);
                break;
            case 'execution_complete':
                this.onExecutionCompleted(eventData);
                break;
            case 'execution_error':
                this.onExecutionError(eventData);
                break;
        }
    }
    
    visualizeNodeStart(eventData) {
        const nodeId = eventData.node_id;
        if (!nodeId) return;
        
        // Highlight the node that's starting execution
        this.highlightNode(nodeId, 'executing', this.executionState.highlightDuration);
        
        // Update current node
        this.executionState.currentNode = nodeId;
        
        // Show execution info
        this.showExecutionInfo(nodeId, `Executing ${eventData.data?.node_type || 'node'}...`);
    }
    
    visualizeNodeComplete(eventData) {
        const nodeId = eventData.node_id;
        if (!nodeId) return;
        
        // Highlight the node as completed
        this.highlightNode(nodeId, 'completed', this.executionState.highlightDuration);
        
        // Show completion info
        const executionTime = eventData.data?.execution_time || 0;
        this.showExecutionInfo(nodeId, `Completed in ${executionTime.toFixed(3)}s`);
        
        // Clear current node if it matches
        if (this.executionState.currentNode === nodeId) {
            this.executionState.currentNode = null;
        }
    }
    
    visualizeNodeError(eventData) {
        const nodeId = eventData.node_id;
        if (!nodeId) return;
        
        // Highlight the node with error
        this.highlightNode(nodeId, 'error', this.executionState.highlightDuration * 2);
        
        // Show error info
        const errorMessage = eventData.data?.error_message || 'Unknown error';
        this.showExecutionInfo(nodeId, `Error: ${errorMessage}`, 'error');
    }
    
    visualizeDataFlow(eventData) {
        const connectionId = eventData.connection_id;
        const sourceNode = eventData.data?.source_node;
        const targetNode = eventData.data?.target_node;
        const dataValue = eventData.data?.value;
        
        if (!connectionId || !sourceNode || !targetNode) return;
        
        // Animate data flow along the connection
        this.animateDataFlow(sourceNode, targetNode, dataValue);
    }
    
    visualizeVariableUpdate(eventData) {
        const variableName = eventData.data?.variable_name;
        const newValue = eventData.data?.new_value;
        
        if (!variableName) return;
        
        // Show variable update in a side panel or overlay
        this.showVariableUpdate(variableName, newValue);
    }
    
    highlightNode(nodeId, type, duration) {
        const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);
        if (!nodeElement) return;
        
        // Remove existing highlights
        this.clearNodeHighlight(nodeId);
        
        // Create highlight element
        const highlight = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        highlight.classList.add('node-highlight', `highlight-${type}`);
        highlight.setAttribute('x', '-5');
        highlight.setAttribute('y', '-5');
        highlight.setAttribute('width', '130');
        highlight.setAttribute('height', '90');
        highlight.setAttribute('rx', '8');
        highlight.dataset.nodeId = nodeId;
        
        // Add to highlights layer
        this.executionOverlay.nodeHighlights.appendChild(highlight);
        
        // Position the highlight at the node's position
        const transform = nodeElement.getAttribute('transform');
        if (transform) {
            highlight.setAttribute('transform', transform);
        }
        
        // Auto-remove after duration
        if (duration > 0) {
            setTimeout(() => {
                this.clearNodeHighlight(nodeId);
            }, duration);
        }
    }
    
    clearNodeHighlight(nodeId) {
        const existingHighlight = this.executionOverlay.nodeHighlights.querySelector(`[data-node-id="${nodeId}"]`);
        if (existingHighlight) {
            existingHighlight.remove();
        }
    }
    
    animateDataFlow(sourceNodeId, targetNodeId, dataValue) {
        const sourceElement = document.querySelector(`[data-node-id="${sourceNodeId}"]`);
        const targetElement = document.querySelector(`[data-node-id="${targetNodeId}"]`);
        
        if (!sourceElement || !targetElement) return;
        
        // Get node positions
        const sourceTransform = sourceElement.getAttribute('transform');
        const targetTransform = targetElement.getAttribute('transform');
        
        const sourceMatch = sourceTransform?.match(/translate\(([^,]+),\s*([^)]+)\)/);
        const targetMatch = targetTransform?.match(/translate\(([^,]+),\s*([^)]+)\)/);
        
        if (!sourceMatch || !targetMatch) return;
        
        const sourceX = parseFloat(sourceMatch[1]) + 60; // Center of node
        const sourceY = parseFloat(sourceMatch[2]) + 40;
        const targetX = parseFloat(targetMatch[1]) + 60;
        const targetY = parseFloat(targetMatch[2]) + 40;
        
        // Create animated data packet
        const dataPacket = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        dataPacket.classList.add('data-packet');
        dataPacket.setAttribute('r', '4');
        dataPacket.setAttribute('cx', sourceX);
        dataPacket.setAttribute('cy', sourceY);
        
        // Add data value as title
        if (dataValue) {
            const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
            title.textContent = `Data: ${dataValue}`;
            dataPacket.appendChild(title);
        }
        
        this.executionOverlay.dataFlowAnimations.appendChild(dataPacket);
        
        // Animate movement
        const animation = dataPacket.animate([
            { transform: `translate(${sourceX}px, ${sourceY}px)` },
            { transform: `translate(${targetX}px, ${targetY}px)` }
        ], {
            duration: 1000 / this.executionState.executionSpeed,
            easing: 'ease-in-out'
        });
        
        // Remove after animation
        animation.addEventListener('finish', () => {
            dataPacket.remove();
        });
    }
    
    showExecutionInfo(nodeId, message, type = 'info') {
        // Create or update execution info panel
        let infoPanel = document.getElementById('execution-info-panel');
        if (!infoPanel) {
            infoPanel = document.createElement('div');
            infoPanel.id = 'execution-info-panel';
            infoPanel.className = 'execution-info-panel';
            document.body.appendChild(infoPanel);
        }
        
        // Add message to panel
        const messageElement = document.createElement('div');
        messageElement.className = `execution-message ${type}`;
        messageElement.innerHTML = `
            <span class="timestamp">${new Date().toLocaleTimeString()}</span>
            <span class="node-id">[${nodeId}]</span>
            <span class="message">${message}</span>
        `;
        
        infoPanel.appendChild(messageElement);
        
        // Auto-scroll to bottom
        infoPanel.scrollTop = infoPanel.scrollHeight;
        
        // Limit number of messages
        const messages = infoPanel.querySelectorAll('.execution-message');
        if (messages.length > 50) {
            messages[0].remove();
        }
    }
    
    showVariableUpdate(variableName, newValue) {
        // Create or update variables panel
        let variablesPanel = document.getElementById('variables-panel');
        if (!variablesPanel) {
            variablesPanel = document.createElement('div');
            variablesPanel.id = 'variables-panel';
            variablesPanel.className = 'variables-panel';
            variablesPanel.innerHTML = '<h3>Variables</h3><div class="variables-list"></div>';
            document.body.appendChild(variablesPanel);
        }
        
        const variablesList = variablesPanel.querySelector('.variables-list');
        
        // Find or create variable entry
        let variableEntry = variablesList.querySelector(`[data-variable="${variableName}"]`);
        if (!variableEntry) {
            variableEntry = document.createElement('div');
            variableEntry.className = 'variable-entry';
            variableEntry.dataset.variable = variableName;
            variablesList.appendChild(variableEntry);
        }
        
        // Update variable display
        variableEntry.innerHTML = `
            <span class="variable-name">${variableName}:</span>
            <span class="variable-value">${newValue}</span>
        `;
        
        // Highlight the update
        variableEntry.classList.add('updated');
        setTimeout(() => {
            variableEntry.classList.remove('updated');
        }, 1000);
    }
    
    onExecutionStarted(data) {
        console.log('Execution started:', data);
        this.executionState.isExecuting = true;
        this.setExecutionControlsState('executing');
    }
    
    onExecutionCompleted(data) {
        console.log('Execution completed:', data);
        this.executionState.isExecuting = false;
        this.setExecutionControlsState('idle');
        
        // Show completion message
        this.showExecutionInfo('system', 'Execution completed successfully', 'success');
        
        // Clear current node highlight
        if (this.executionState.currentNode) {
            this.clearNodeHighlight(this.executionState.currentNode);
            this.executionState.currentNode = null;
        }
    }
    
    onExecutionError(data) {
        console.error('Execution error:', data);
        this.executionState.isExecuting = false;
        this.setExecutionControlsState('idle');
        
        // Show error message
        const errorMessage = data.data?.error_message || 'Unknown execution error';
        this.showExecutionInfo('system', `Execution failed: ${errorMessage}`, 'error');
    }
    
    onExecutionStopped() {
        console.log('Execution stopped');
        this.executionState.isExecuting = false;
        this.setExecutionControlsState('idle');
        
        // Clear all execution visualization
        this.clearExecutionVisualization();
        
        // Show stop message
        this.showExecutionInfo('system', 'Execution stopped by user', 'warning');
    }
    
    clearExecutionVisualization() {
        // Clear all highlights
        if (this.executionOverlay?.nodeHighlights) {
            this.executionOverlay.nodeHighlights.innerHTML = '';
        }
        
        // Clear all data flow animations
        if (this.executionOverlay?.dataFlowAnimations) {
            this.executionOverlay.dataFlowAnimations.innerHTML = '';
        }
        
        // Clear execution path
        if (this.executionOverlay?.executionPath) {
            this.executionOverlay.executionPath.innerHTML = '';
        }
        
        // Reset execution state
        this.executionState.currentNode = null;
        this.executionState.executionEvents = [];
    }
    
    // Demo loading methods
    async loadDemo(demoType) {
        try {
            const response = await fetch(`/api/demos/load/${demoType}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            if (data.success) {
                console.log(`Loaded ${data.data.demo_name} demo with ${data.data.nodes_count} nodes`);
                
                // Show notification
                this.showNotification(`Loaded ${data.data.demo_name}`, 'success');
                
                // Auto-start execution after a short delay
                setTimeout(() => {
                    if (confirm('Would you like to start live execution of this demo?')) {
                        this.startExecution();
                    }
                }, 1000);
            } else {
                console.error('Failed to load demo:', data.error);
                this.showNotification(`Failed to load demo: ${data.error}`, 'error');
            }
            
        } catch (error) {
            console.error('Error loading demo:', error);
            this.showNotification(`Error loading demo: ${error.message}`, 'error');
        }
    }
    
    // ==========================================
    // AST-Grep Pattern Search Methods
    // ==========================================
    
    initializeAstGrepModal() {
        const modal = document.getElementById('ast-grep-modal');
        if (!modal) return;
        
        this.astGrepModal = {
            mode: 'search',
            matchedNodes: [],
            taggedNodeIds: new Set()
        };
        
        // Close buttons
        const closeBtn = document.getElementById('ast-grep-close-btn');
        const cancelBtn = document.getElementById('ast-cancel-btn');
        const backdrop = modal.querySelector('.modal-backdrop');
        
        if (closeBtn) closeBtn.addEventListener('click', () => this.hideAstGrepModal());
        if (cancelBtn) cancelBtn.addEventListener('click', () => this.hideAstGrepModal());
        if (backdrop) backdrop.addEventListener('click', () => this.hideAstGrepModal());
        
        // Mode tabs
        document.querySelectorAll('.ast-mode-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                const mode = e.currentTarget.dataset.mode;
                this.switchAstGrepMode(mode);
            });
        });
        
        // Action buttons
        const searchBtn = document.getElementById('ast-search-btn');
        const tagCheckbox = document.getElementById('ast-tag-checkbox');
        const tagToggleContainer = document.getElementById('ast-tag-toggle-container');
        const refactorBtn = document.getElementById('ast-refactor-btn');
        const clearTagsBtn = document.getElementById('ast-clear-tags-btn');
        
        if (searchBtn) searchBtn.addEventListener('click', () => this.handleAstGrepSearch());
        if (tagCheckbox) tagCheckbox.addEventListener('change', (e) => this.handleAstGrepTagToggle(e.target.checked));
        if (refactorBtn) refactorBtn.addEventListener('click', () => this.handleAstGrepRefactor());
        if (clearTagsBtn) clearTagsBtn.addEventListener('click', () => this.clearTaggedNodes());
        
        // Load common patterns
        this.loadAstGrepPatterns();
    }
    
    async loadAstGrepPatterns() {
        try {
            const response = await fetch('/api/ast-grep/patterns');
            const data = await response.json();
            
            if (data.success && data.patterns) {
                const chipsEl = document.getElementById('pattern-chips');
                if (!chipsEl) return;
                
                chipsEl.innerHTML = '';
                
                // Show first 8 patterns
                Object.entries(data.patterns).slice(0, 8).forEach(([name, pattern]) => {
                    const chip = document.createElement('button');
                    chip.className = 'pattern-chip';
                    chip.textContent = name.replace(/_/g, ' ');
                    chip.title = pattern;
                    chip.addEventListener('click', () => {
                        const patternInput = document.getElementById('ast-pattern') || 
                                           document.getElementById('ast-refactor-pattern');
                        if (patternInput) {
                            patternInput.value = pattern;
                        }
                        // Mark as selected
                        document.querySelectorAll('.pattern-chip').forEach(c => c.classList.remove('selected'));
                        chip.classList.add('selected');
                    });
                    chipsEl.appendChild(chip);
                });
            }
        } catch (error) {
            console.warn('Failed to load ast-grep patterns:', error);
        }
    }
    
    showAstGrepModal() {
        const modal = document.getElementById('ast-grep-modal');
        if (modal) {
            modal.style.display = 'block';
            this.resetAstGrepModal();
            
            // Refresh icons
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        }
    }
    
    hideAstGrepModal() {
        const modal = document.getElementById('ast-grep-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    }
    
    resetAstGrepModal() {
        // Clear inputs
        const patternInput = document.getElementById('ast-pattern');
        const refactorPatternInput = document.getElementById('ast-refactor-pattern');
        const replacementInput = document.getElementById('ast-replacement');
        
        if (patternInput) patternInput.value = '';
        if (refactorPatternInput) refactorPatternInput.value = '';
        if (replacementInput) replacementInput.value = '';
        
        // Hide results
        const resultsEl = document.getElementById('ast-results');
        const statusEl = document.getElementById('ast-status');
        if (resultsEl) resultsEl.style.display = 'none';
        if (statusEl) statusEl.style.display = 'none';
        
        // Reset buttons and toggle
        const tagToggleContainer = document.getElementById('ast-tag-toggle-container');
        const tagCheckbox = document.getElementById('ast-tag-checkbox');
        const refactorBtn = document.getElementById('ast-refactor-btn');
        const clearTagsBtn = document.getElementById('ast-clear-tags-btn');
        
        if (tagToggleContainer) tagToggleContainer.style.display = 'none';
        if (tagCheckbox) tagCheckbox.checked = false;
        if (refactorBtn) refactorBtn.style.display = 'none';
        if (clearTagsBtn) clearTagsBtn.style.display = this.astGrepModal?.taggedNodeIds?.size > 0 ? 'inline-flex' : 'none';
        
        // Clear selected patterns
        document.querySelectorAll('.pattern-chip').forEach(c => c.classList.remove('selected'));
        
        // Reset modal state
        if (this.astGrepModal) {
            this.astGrepModal.matchedNodes = [];
        }
        
        // Switch to search mode
        this.switchAstGrepMode('search');
    }
    
    switchAstGrepMode(mode) {
        this.astGrepModal.mode = mode;
        
        // Update tabs
        document.querySelectorAll('.ast-mode-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.mode === mode);
        });
        
        // Show/hide panels
        const searchPanel = document.getElementById('ast-search-panel');
        const refactorPanel = document.getElementById('ast-refactor-panel');
        
        if (searchPanel) searchPanel.style.display = mode === 'search' ? 'block' : 'none';
        if (refactorPanel) refactorPanel.style.display = mode === 'refactor' ? 'block' : 'none';
        
        // Update search button text
        const searchBtn = document.getElementById('ast-search-btn');
        if (searchBtn) {
            const icon = searchBtn.querySelector('i');
            if (mode === 'search') {
                if (icon) icon.setAttribute('data-lucide', 'search');
                searchBtn.innerHTML = '<i data-lucide="search"></i> Search';
            } else {
                if (icon) icon.setAttribute('data-lucide', 'eye');
                searchBtn.innerHTML = '<i data-lucide="eye"></i> Preview';
            }
            
            // Refresh icons
            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
        }
        
        // Hide/show tag toggle and refactor buttons based on mode
        const tagToggleContainer = document.getElementById('ast-tag-toggle-container');
        const refactorBtn = document.getElementById('ast-refactor-btn');
        
        if (tagToggleContainer) tagToggleContainer.style.display = 'none';
        if (refactorBtn) refactorBtn.style.display = 'none';
    }
    
    async handleAstGrepSearch() {
        const mode = this.astGrepModal.mode;
        let pattern;
        
        if (mode === 'search') {
            pattern = document.getElementById('ast-pattern')?.value?.trim();
        } else {
            pattern = document.getElementById('ast-refactor-pattern')?.value?.trim();
        }
        
        if (!pattern) {
            this.showAstGrepStatus('error', 'Please enter a search pattern');
            return;
        }
        
        this.showAstGrepStatus('loading', 'Searching nodes...');
        
        try {
            // Collect full node data directly from this.nodes Map
            let nodesData = {};
            
            console.log(`[AST-Grep Search] this.nodes Map size: ${this.nodes.size}`);
            
            this.nodes.forEach((nodeInfo, nodeId) => {
                if (nodeInfo) {
                    nodesData[nodeId] = {
                        id: nodeId,
                        name: nodeInfo.name || nodeInfo.parameters?.name || nodeId,
                        type: nodeInfo.type || 'unknown',
                        parameters: nodeInfo.parameters || {},
                        metadata: nodeInfo.metadata || {}
                    };
                }
            });
            
            console.log(`[AST-Grep Search] Collected ${Object.keys(nodesData).length} nodes for search`);
            // Log first node's parameters to see what we're working with
            const firstNodeId = Object.keys(nodesData)[0];
            if (firstNodeId) {
                console.log(`[AST-Grep Search] First node params:`, Object.keys(nodesData[firstNodeId].parameters || {}));
            }
            
            // If local nodes empty, try fetching from server as fallback
            if (Object.keys(nodesData).length === 0) {
                console.log('[AST-Grep Search] Local nodes empty, fetching from server...');
                try {
                    const serverResponse = await fetch('/api/canvas/nodes');
                    const serverData = await serverResponse.json();
                    if (serverData.success && serverData.data) {
                        nodesData = serverData.data;
                        console.log(`[AST-Grep Search] Fetched ${Object.keys(nodesData).length} nodes from server`);
                    }
                } catch (fetchError) {
                    console.error('[AST-Grep Search] Failed to fetch from server:', fetchError);
                }
            }
            
            // If still no nodes, show message
            if (Object.keys(nodesData).length === 0) {
                this.showAstGrepStatus('error', 'No nodes on canvas to search. Try loading a file first.');
                return;
            }
            
            const response = await fetch('/api/ast-grep/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    pattern, 
                    nodes_data: nodesData  // Send full node data
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Access matches from data.data (server nests response under 'data')
                const allMatches = data.data?.matches || [];
                console.log(`[AST-Grep Search] Server returned ${allMatches.length} total matches`);
                
                // Deduplicate by node_id - keep first match per node but count total matches
                const nodeMatchCounts = new Map();
                const uniqueMatches = [];
                
                allMatches.forEach(match => {
                    if (!nodeMatchCounts.has(match.node_id)) {
                        nodeMatchCounts.set(match.node_id, 1);
                        uniqueMatches.push({...match, match_count: 1});
                    } else {
                        nodeMatchCounts.set(match.node_id, nodeMatchCounts.get(match.node_id) + 1);
                    }
                });
                
                // Update match counts in unique matches
                uniqueMatches.forEach(match => {
                    match.match_count = nodeMatchCounts.get(match.node_id);
                });
                
                console.log(`[AST-Grep Search] ${uniqueMatches.length} unique nodes with matches`);
                
                this.astGrepModal.matchedNodes = uniqueMatches;
                this.renderAstGrepResults(uniqueMatches, allMatches.length);
                
                // Show appropriate action button/toggle
                const tagToggleContainer = document.getElementById('ast-tag-toggle-container');
                const tagCheckbox = document.getElementById('ast-tag-checkbox');
                const refactorBtn = document.getElementById('ast-refactor-btn');
                const clearTagsBtn = document.getElementById('ast-clear-tags-btn');
                
                if (uniqueMatches.length > 0) {
                    if (mode === 'search' && tagToggleContainer) {
                        tagToggleContainer.style.display = 'inline-flex';
                        // Uncheck by default when new search is performed
                        if (tagCheckbox) tagCheckbox.checked = false;
                    }
                    if (mode === 'refactor' && refactorBtn) {
                        refactorBtn.style.display = 'inline-flex';
                    }
                } else {
                    if (tagToggleContainer) tagToggleContainer.style.display = 'none';
                }
                
                // Show clear tags button if there are tagged nodes
                if (clearTagsBtn) {
                    clearTagsBtn.style.display = this.astGrepModal.taggedNodeIds.size > 0 ? 'inline-flex' : 'none';
                }
                
                this.hideAstGrepStatus();
            } else {
                this.showAstGrepStatus('error', data.error || 'Search failed');
            }
        } catch (error) {
            console.error('AST-grep search error:', error);
            this.showAstGrepStatus('error', `Error: ${error.message}`);
        }
    }
    
    renderAstGrepResults(matches, totalMatches = null) {
        const resultsEl = document.getElementById('ast-results');
        const listEl = document.getElementById('ast-results-list');
        const countEl = document.getElementById('ast-match-count');
        
        if (!resultsEl || !listEl) return;
        
        // Show "X nodes (Y matches)" format
        if (totalMatches !== null && totalMatches !== matches.length) {
            countEl.textContent = `${matches.length} nodes (${totalMatches} matches)`;
        } else {
            countEl.textContent = matches.length;
        }
        resultsEl.style.display = 'block';
        
        if (matches.length === 0) {
            listEl.innerHTML = `
                <div class="ast-result-item" style="opacity: 0.6;">
                    <div class="ast-result-info">
                        <div class="ast-result-name">No matching nodes found</div>
                        <div class="ast-result-code">Try a different pattern</div>
                    </div>
                </div>
            `;
            return;
        }
        
        listEl.innerHTML = matches.map(match => `
            <div class="ast-result-item" data-node-id="${match.node_id}">
                <input type="checkbox" class="ast-result-checkbox" checked>
                <div class="ast-result-icon">
                    <i data-lucide="code-2"></i>
                </div>
                <div class="ast-result-info">
                    <div class="ast-result-name">
                        ${this.escapeHtml(match.node_name || match.node_id)}
                        ${match.match_count > 1 ? `<span class="ast-match-badge">${match.match_count} matches</span>` : ''}
                    </div>
                    <div class="ast-result-code" title="${this.escapeHtml(match.match_text || '')}">
                        ${this.escapeHtml((match.match_text || '').substring(0, 60))}${(match.match_text || '').length > 60 ? '...' : ''}
                    </div>
                </div>
            </div>
        `).join('');
        
        // Add click handlers to focus nodes
        listEl.querySelectorAll('.ast-result-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (e.target.classList.contains('ast-result-checkbox')) return;
                
                const nodeId = item.dataset.nodeId;
                this.focusOnNode(nodeId);
            });
        });
        
        // Refresh icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }
    
    focusOnNode(nodeId) {
        // Try both class names for compatibility
        let nodeEl = document.querySelector(`.visual-node[data-node-id="${nodeId}"]`);
        if (!nodeEl) {
            nodeEl = document.querySelector(`.canvas-node[data-node-id="${nodeId}"]`);
        }
        if (!nodeEl) return;
        
        // Clear current selection
        this.clearSelection();
        
        // Select this node
        this.selectNode(nodeId);
        
        // Scroll into view
        nodeEl.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
        
        // Flash effect
        nodeEl.classList.add('node-tagged-pulse');
        setTimeout(() => nodeEl.classList.remove('node-tagged-pulse'), 2000);
    }
    
    async handleAstGrepTagToggle(isChecked) {
        if (isChecked) {
            // Tag the nodes
            this.applyAstGrepTags();
        } else {
            // Clear tags from current search results only
            this.clearCurrentSearchTags();
        }
        
        // Update clear tags button visibility
        const clearTagsBtn = document.getElementById('ast-clear-tags-btn');
        if (clearTagsBtn) {
            clearTagsBtn.style.display = this.astGrepModal.taggedNodeIds.size > 0 ? 'inline-flex' : 'none';
        }
    }
    
    applyAstGrepTags() {
        // Get checked node IDs from results
        const checkedNodeIds = Array.from(document.querySelectorAll('.ast-result-item'))
            .filter(item => item.querySelector('.ast-result-checkbox')?.checked)
            .map(item => item.dataset.nodeId)
            .filter(Boolean);
        
        if (checkedNodeIds.length === 0) {
            this.showAstGrepStatus('error', 'No nodes selected');
            const tagCheckbox = document.getElementById('ast-tag-checkbox');
            if (tagCheckbox) tagCheckbox.checked = false;
            return;
        }
        
        // Tag the nodes visually (try both class names)
        let taggedCount = 0;
        checkedNodeIds.forEach(nodeId => {
            let nodeEl = document.querySelector(`.visual-node[data-node-id="${nodeId}"]`);
            if (!nodeEl) {
                nodeEl = document.querySelector(`.canvas-node[data-node-id="${nodeId}"]`);
            }
            if (nodeEl) {
                nodeEl.classList.add('node-tagged');
                this.astGrepModal.taggedNodeIds.add(nodeId);
                taggedCount++;
            }
        });
        
        this.showNotification(`Tagged ${taggedCount} nodes`, 'success');
    }
    
    clearCurrentSearchTags() {
        // Only clear tags for nodes in the current search results
        const resultNodeIds = Array.from(document.querySelectorAll('.ast-result-item'))
            .map(item => item.dataset.nodeId)
            .filter(Boolean);
        
        let clearedCount = 0;
        resultNodeIds.forEach(nodeId => {
            let nodeEl = document.querySelector(`.visual-node[data-node-id="${nodeId}"]`);
            if (!nodeEl) {
                nodeEl = document.querySelector(`.canvas-node[data-node-id="${nodeId}"]`);
            }
            if (nodeEl && nodeEl.classList.contains('node-tagged')) {
                nodeEl.classList.remove('node-tagged', 'node-tagged-pulse');
                this.astGrepModal.taggedNodeIds.delete(nodeId);
                clearedCount++;
            }
        });
        
        if (clearedCount > 0) {
            this.showNotification(`Cleared ${clearedCount} tags`, 'info');
        }
    }
    
    clearTaggedNodes() {
        // Clear both possible class names
        document.querySelectorAll('.node-tagged, .visual-node.node-tagged, .canvas-node.node-tagged').forEach(el => {
            el.classList.remove('node-tagged', 'node-tagged-pulse');
        });
        
        if (this.astGrepModal) {
            this.astGrepModal.taggedNodeIds.clear();
        }
        
        // Uncheck the tag toggle if it exists
        const tagCheckbox = document.getElementById('ast-tag-checkbox');
        if (tagCheckbox) tagCheckbox.checked = false;
        
        // Hide the clear tags button
        const clearTagsBtn = document.getElementById('ast-clear-tags-btn');
        if (clearTagsBtn) clearTagsBtn.style.display = 'none';
        
        this.showNotification('All tags cleared', 'info');
    }
    
    async handleAstGrepRefactor() {
        const pattern = document.getElementById('ast-refactor-pattern')?.value?.trim();
        const replacement = document.getElementById('ast-replacement')?.value?.trim();
        
        if (!pattern || !replacement) {
            this.showAstGrepStatus('error', 'Please enter both find and replace patterns');
            return;
        }
        
        // Get checked node IDs
        const checkedNodeIds = Array.from(document.querySelectorAll('.ast-result-item'))
            .filter(item => item.querySelector('.ast-result-checkbox')?.checked)
            .map(item => item.dataset.nodeId)
            .filter(Boolean);
        
        if (checkedNodeIds.length === 0) {
            this.showAstGrepStatus('error', 'No nodes selected for refactoring');
            return;
        }
        
        // Confirm action
        if (!confirm(`Refactor ${checkedNodeIds.length} nodes? This will modify their source code.`)) {
            return;
        }
        
        this.showAstGrepStatus('loading', 'Applying refactoring...');
        
        try {
            const response = await fetch('/api/ast-grep/refactor', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    pattern,
                    replacement,
                    node_ids: checkedNodeIds
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showNotification(`Refactored ${data.refactored_count || 0} nodes`, 'success');
                
                // Reload canvas to reflect changes
                await this.loadInitialData();
                
                this.hideAstGrepModal();
            } else {
                this.showAstGrepStatus('error', data.error || 'Refactoring failed');
            }
        } catch (error) {
            console.error('AST-grep refactor error:', error);
            this.showAstGrepStatus('error', `Error: ${error.message}`);
        }
    }
    
    showAstGrepStatus(type, message) {
        const statusEl = document.getElementById('ast-status');
        if (!statusEl) return;
        
        statusEl.style.display = 'block';
        statusEl.className = `generate-status ${type}`;
        statusEl.querySelector('.status-message').textContent = message;
    }
    
    hideAstGrepStatus() {
        const statusEl = document.getElementById('ast-status');
        if (statusEl) {
            statusEl.style.display = 'none';
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 3 seconds
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.visualEditor = new VisualEditor();

    // Settings Hub (gear icon in status bar)
    window.settingsHub = new SettingsHub();
    
    // Add drag and drop support to canvas
    const canvas = document.getElementById('canvas');
    canvas.addEventListener('dragover', window.visualEditor.handleCanvasDragOver.bind(window.visualEditor));
    canvas.addEventListener('drop', window.visualEditor.handleCanvasDrop.bind(window.visualEditor));
});
