/**
 * AI Chat Panel for Visual Editor
 * Supports OpenAI-compatible endpoints with node generation and canvas injection
 */

class AIChat {
    constructor(visualEditor) {
        this.visualEditor = visualEditor;
        this.messages = [];
        this.isLoading = false;
        this.settings = this.loadSettings();
        
        // System prompt for the AI assistant
        this.systemPrompt = this.getSystemPrompt();
        
        this.initializeElements();
        this.bindEvents();
        this.applySettings();
    }
    
    getSystemPrompt() {
        return `You are an AI assistant embedded in VPyD (Visual Python Designer), a visual node-based programming environment. Your role is to help users create, understand, and manipulate visual programming workflows.

## CORE CAPABILITIES

### 1. Canvas Understanding
You have access to the current canvas state including:
- All nodes currently on the canvas with their IDs, types, positions, and parameters
- Connections between nodes
- The visual paradigm being used (node_based, block_based, diagram_based, timeline_based)

### 2. Node Generation
You can generate nodes in JSON format that will be automatically injected onto the canvas. When generating nodes, use this exact format:

\`\`\`json:inject-nodes
{
    "nodes": [
        {
            "type": "function",
            "name": "Node Display Name",
            "position": [100, 100],
            "parameters": {
                "name": "function_name",
                "description": "What this node does",
                "source_code": "def function_name(param1, param2):\\n    # Your code here\\n    return result"
            },
            "inputs": [
                {"name": "input1", "type": "any", "required": true}
            ],
            "outputs": [
                {"name": "output", "type": "any"}
            ]
        }
    ],
    "connections": [
        {
            "source_node_index": 0,
            "source_port": "output",
            "target_node_index": 1,
            "target_port": "input1"
        }
    ]
}
\`\`\`

### 3. Available Node Types
- **function**: Custom Python function nodes
- **input**: Data input nodes (file readers, API calls, user input)
- **output**: Data output nodes (file writers, displays, exports)
- **transform**: Data transformation nodes (map, filter, reduce)
- **condition**: Conditional logic nodes (if/else, switch)
- **loop**: Iteration nodes (for, while, foreach)
- **variable**: Variable storage and retrieval
- **math**: Mathematical operations
- **string**: String manipulation
- **list**: List/array operations
- **dict**: Dictionary operations
- **api**: HTTP/API request nodes
- **database**: Database connection and query nodes
- **file**: File system operations
- **json**: JSON parsing and generation
- **csv**: CSV handling
- **datetime**: Date and time operations

### 4. Node Parameters by Type

**Function Node Parameters:**
- name: Function identifier
- description: What the function does
- source_code: The actual Python code
- parameters: List of function parameters

**Input Node Parameters:**
- source_type: "file", "api", "user", "constant"
- value: The input value or path
- data_type: Expected data type

**Transform Node Parameters:**
- operation: "map", "filter", "reduce", "sort", "aggregate"
- expression: The transformation expression

**Condition Node Parameters:**
- condition: The condition expression
- true_branch: Action if true
- false_branch: Action if false

### 5. Best Practices for Node Generation

1. **Positioning**: Start nodes at (100, 100) and space them 250px apart horizontally, 150px vertically
2. **Naming**: Use clear, descriptive names that explain the node's purpose
3. **Source Code**: Include complete, working Python code with proper imports
4. **Connections**: Ensure data types match between connected ports
5. **Error Handling**: Include try/except blocks for robust code

### 6. Response Guidelines

When responding:
1. **Be concise** but thorough in explanations
2. **Use code blocks** for any code snippets
3. **Generate inject-nodes JSON** when the user asks to create nodes/workflows
4. **Explain your reasoning** when making design decisions
5. **Ask clarifying questions** if the request is ambiguous

### 7. Example Interactions

**User**: "Create a node that reads a JSON file"
**Response**: I'll create a JSON file reader node for you:

\`\`\`json:inject-nodes
{
    "nodes": [
        {
            "type": "input",
            "name": "Read JSON File",
            "position": [100, 100],
            "parameters": {
                "name": "json_reader",
                "description": "Reads and parses a JSON file",
                "source_code": "import json\\n\\ndef read_json(file_path: str) -> dict:\\n    with open(file_path, 'r') as f:\\n        return json.load(f)"
            },
            "inputs": [
                {"name": "file_path", "type": "str", "required": true}
            ],
            "outputs": [
                {"name": "data", "type": "dict"}
            ]
        }
    ]
}
\`\`\`

This node takes a file path as input and outputs the parsed JSON data as a dictionary.

### 8. Canvas Context

When I provide canvas context, it will be in this format:
- Current nodes: List of nodes with their details
- Current connections: List of connections
- Selected nodes: Currently selected items

Use this context to:
- Reference existing nodes by ID
- Suggest connections to existing nodes
- Avoid duplicate functionality
- Position new nodes appropriately

### 9. Special Commands

Users may use special commands:
- "analyze canvas" - Describe what's on the canvas
- "optimize workflow" - Suggest improvements
- "generate [description]" - Create nodes matching the description
- "connect [nodeA] to [nodeB]" - Suggest or create connections
- "explain [node/concept]" - Provide detailed explanation

Remember: You are helping users build visual programs. Focus on practical, working solutions that integrate well with the visual programming paradigm.`;
    }
    
    loadSettings() {
        try {
            const saved = localStorage.getItem('vpyd_ai_settings');
            if (saved) {
                return JSON.parse(saved);
            }
        } catch (e) {
            console.warn('Failed to load AI settings:', e);
        }
        
        return {
            endpoint: 'https://api.openai.com/v1',
            apiKey: '',
            model: 'gpt-4o',
            customModel: '',
            temperature: 0.7
        };
    }
    
    saveSettings() {
        try {
            localStorage.setItem('vpyd_ai_settings', JSON.stringify(this.settings));
        } catch (e) {
            console.warn('Failed to save AI settings:', e);
        }
    }
    
    initializeElements() {
        // Panel elements
        this.panel = document.getElementById('ai-chat-panel');
        this.container = this.panel?.querySelector('.ai-chat-container');
        this.toggleBtn = document.getElementById('ai-chat-toggle');
        this.minimizeBtn = document.getElementById('ai-chat-minimize-btn');
        this.resizeHandle = this.panel?.querySelector('.ai-chat-resize-handle');
        
        // Settings elements
        this.settingsPanel = document.getElementById('ai-chat-settings');
        this.settingsBtn = document.getElementById('ai-chat-settings-btn');
        this.settingsSaveBtn = document.getElementById('ai-settings-save');
        this.settingsCancelBtn = document.getElementById('ai-settings-cancel');
        
        this.endpointInput = document.getElementById('ai-endpoint');
        this.apiKeyInput = document.getElementById('ai-api-key');
        this.modelSelect = document.getElementById('ai-model');
        this.customModelInput = document.getElementById('ai-custom-model');
        this.customModelGroup = document.getElementById('custom-model-group');
        this.temperatureInput = document.getElementById('ai-temperature');
        this.temperatureValue = document.getElementById('ai-temperature-value');
        
        // Chat elements
        this.messagesContainer = document.getElementById('ai-chat-messages');
        this.inputField = document.getElementById('ai-chat-input');
        this.sendBtn = document.getElementById('ai-chat-send');
        this.clearBtn = document.getElementById('ai-chat-clear-btn');
        
        // Quick actions
        this.quickActions = document.querySelectorAll('.ai-quick-action');
    }
    
    bindEvents() {
        // Toggle panel
        this.toggleBtn?.addEventListener('click', () => this.togglePanel());
        this.minimizeBtn?.addEventListener('click', () => this.togglePanel());
        
        // Settings
        this.settingsBtn?.addEventListener('click', () => this.toggleSettings());
        this.settingsSaveBtn?.addEventListener('click', () => this.saveSettingsFromUI());
        this.settingsCancelBtn?.addEventListener('click', () => this.toggleSettings(false));
        
        this.modelSelect?.addEventListener('change', () => {
            const isCustom = this.modelSelect.value === 'custom';
            if (this.customModelGroup) {
                this.customModelGroup.style.display = isCustom ? 'block' : 'none';
            }
        });
        
        this.temperatureInput?.addEventListener('input', () => {
            if (this.temperatureValue) {
                this.temperatureValue.textContent = this.temperatureInput.value;
            }
        });
        
        // Chat
        this.sendBtn?.addEventListener('click', () => this.sendMessage());
        this.inputField?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Auto-resize textarea
        this.inputField?.addEventListener('input', () => this.autoResizeInput());
        
        // Clear chat
        this.clearBtn?.addEventListener('click', () => this.clearChat());
        
        // Quick actions
        this.quickActions?.forEach(btn => {
            btn.addEventListener('click', () => {
                const prompt = btn.dataset.prompt;
                if (prompt && this.inputField) {
                    this.inputField.value = prompt;
                    this.sendMessage();
                }
            });
        });
        
        // Resize handle
        this.initResize();
    }
    
    initResize() {
        if (!this.resizeHandle || !this.panel) return;
        
        let isResizing = false;
        let startX, startWidth;
        
        this.resizeHandle.addEventListener('mousedown', (e) => {
            isResizing = true;
            startX = e.clientX;
            startWidth = this.panel.offsetWidth;
            this.resizeHandle.classList.add('resizing');
            document.body.style.cursor = 'ew-resize';
            document.body.style.userSelect = 'none';
        });
        
        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;
            
            const diff = startX - e.clientX;
            const newWidth = Math.max(300, Math.min(800, startWidth + diff));
            this.panel.style.width = `${newWidth}px`;
        });
        
        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;
                this.resizeHandle.classList.remove('resizing');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            }
        });
    }
    
    applySettings() {
        if (this.endpointInput) this.endpointInput.value = this.settings.endpoint || '';
        if (this.apiKeyInput) this.apiKeyInput.value = this.settings.apiKey || '';
        if (this.modelSelect) {
            const modelExists = Array.from(this.modelSelect.options).some(opt => opt.value === this.settings.model);
            this.modelSelect.value = modelExists ? this.settings.model : 'custom';
            if (!modelExists && this.customModelGroup) {
                this.customModelGroup.style.display = 'block';
            }
        }
        if (this.customModelInput) this.customModelInput.value = this.settings.customModel || '';
        if (this.temperatureInput) this.temperatureInput.value = this.settings.temperature || 0.7;
        if (this.temperatureValue) this.temperatureValue.textContent = this.settings.temperature || 0.7;
    }
    
    saveSettingsFromUI() {
        this.settings.endpoint = this.endpointInput?.value || 'https://api.openai.com/v1';
        this.settings.apiKey = this.apiKeyInput?.value || '';
        this.settings.model = this.modelSelect?.value || 'gpt-4o';
        this.settings.customModel = this.customModelInput?.value || '';
        this.settings.temperature = parseFloat(this.temperatureInput?.value) || 0.7;
        
        this.saveSettings();
        this.toggleSettings(false);
        this.addSystemMessage('Settings saved successfully!');
    }
    
    togglePanel() {
        this.panel?.classList.toggle('collapsed');
        
        // Refresh icons when opening
        if (!this.panel?.classList.contains('collapsed')) {
            setTimeout(() => {
                if (typeof lucide !== 'undefined') {
                    lucide.createIcons();
                }
            }, 300);
        }
    }
    
    toggleSettings(show = null) {
        if (!this.settingsPanel) return;
        
        const shouldShow = show !== null ? show : this.settingsPanel.style.display === 'none';
        this.settingsPanel.style.display = shouldShow ? 'block' : 'none';
        
        if (shouldShow) {
            this.applySettings();
        }
    }
    
    autoResizeInput() {
        if (!this.inputField) return;
        
        this.inputField.style.height = 'auto';
        const newHeight = Math.min(120, this.inputField.scrollHeight);
        this.inputField.style.height = `${newHeight}px`;
    }
    
    getCanvasContext() {
        const context = {
            nodes: [],
            connections: [],
            selectedNodes: []
        };
        
        // Get nodes from visualEditor
        if (this.visualEditor?.nodes) {
            this.visualEditor.nodes.forEach((node, id) => {
                context.nodes.push({
                    id: id,
                    name: node.name || node.parameters?.name || id,
                    type: node.type || 'unknown',
                    position: node.position || [0, 0],
                    parameters: node.parameters || {}
                });
            });
        }
        
        // Get connections
        if (this.visualEditor?.connections) {
            this.visualEditor.connections.forEach(conn => {
                context.connections.push({
                    source: conn.source_node_id,
                    sourcePort: conn.source_port,
                    target: conn.target_node_id,
                    targetPort: conn.target_port
                });
            });
        }
        
        // Get selected nodes
        if (this.visualEditor?.selectedNodes) {
            context.selectedNodes = Array.from(this.visualEditor.selectedNodes);
        }
        
        return context;
    }
    
    async sendMessage() {
        const message = this.inputField?.value?.trim();
        if (!message || this.isLoading) return;
        
        // Check if API key is set
        if (!this.settings.apiKey) {
            this.addSystemMessage('Please configure your API key in settings (⚙️ button) before chatting.');
            return;
        }
        
        // Add user message
        this.addMessage('user', message);
        this.inputField.value = '';
        this.autoResizeInput();
        
        // Show thinking indicator
        this.isLoading = true;
        this.updateSendButton();
        const thinkingEl = this.addThinkingIndicator();
        
        try {
            // Get canvas context
            const canvasContext = this.getCanvasContext();
            
            // Build messages array
            const apiMessages = [
                { role: 'system', content: this.systemPrompt },
                { 
                    role: 'system', 
                    content: `Current canvas context:\n${JSON.stringify(canvasContext, null, 2)}\n\nTotal nodes on canvas: ${canvasContext.nodes.length}`
                }
            ];
            
            // Add conversation history (last 10 messages)
            const recentMessages = this.messages.slice(-10);
            recentMessages.forEach(msg => {
                if (msg.role === 'user' || msg.role === 'assistant') {
                    apiMessages.push({ role: msg.role, content: msg.content });
                }
            });
            
            // Add current message
            apiMessages.push({ role: 'user', content: message });
            
            // Make API request
            const response = await this.callAPI(apiMessages);
            
            // Remove thinking indicator
            thinkingEl?.remove();
            
            // Process response
            this.processResponse(response);
            
        } catch (error) {
            thinkingEl?.remove();
            console.error('AI Chat error:', error);
            this.addErrorMessage(`Error: ${error.message}`);
        } finally {
            this.isLoading = false;
            this.updateSendButton();
        }
    }
    
    async callAPI(messages) {
        const model = this.settings.model === 'custom' ? this.settings.customModel : this.settings.model;
        
        const response = await fetch('/api/ai/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                endpoint: this.settings.endpoint.replace(/\/$/, ''),
                apiKey: this.settings.apiKey,
                model: model,
                messages: messages,
                temperature: this.settings.temperature,
                max_tokens: 4096
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error?.message || `API error: ${response.status}`);
        }
        
        const data = await response.json();
        return data.choices?.[0]?.message?.content || 'No response received';
    }
    
    processResponse(responseText) {
        // Check for inject-nodes JSON blocks
        const injectPattern = /```json:inject-nodes\s*([\s\S]*?)```/g;
        let lastIndex = 0;
        let hasInjectBlocks = false;
        let match;
        
        const parts = [];
        
        while ((match = injectPattern.exec(responseText)) !== null) {
            hasInjectBlocks = true;
            
            // Add text before this match
            if (match.index > lastIndex) {
                parts.push({
                    type: 'text',
                    content: responseText.slice(lastIndex, match.index)
                });
            }
            
            // Add inject block
            try {
                const jsonData = JSON.parse(match[1]);
                parts.push({
                    type: 'inject',
                    content: match[1],
                    data: jsonData
                });
            } catch (e) {
                parts.push({
                    type: 'text',
                    content: match[0]
                });
            }
            
            lastIndex = match.index + match[0].length;
        }
        
        // Add remaining text
        if (lastIndex < responseText.length) {
            parts.push({
                type: 'text',
                content: responseText.slice(lastIndex)
            });
        }
        
        // Build message content
        let messageHtml = '';
        let injectData = null;
        
        parts.forEach(part => {
            if (part.type === 'text') {
                messageHtml += this.formatMarkdown(part.content);
            } else if (part.type === 'inject') {
                injectData = part.data;
                messageHtml += `
                    <div class="ai-code-block">
                        <div class="ai-code-header">
                            <span>📦 Generated Nodes (${part.data.nodes?.length || 0})</span>
                        </div>
                        <pre><code>${this.escapeHtml(part.content)}</code></pre>
                    </div>
                `;
            }
        });
        
        // Add message with inject button if applicable
        this.addMessage('assistant', responseText, messageHtml, injectData);
    }
    
    formatMarkdown(text) {
        // Simple markdown formatting
        let html = text
            // Code blocks
            .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
            // Inline code
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            // Bold
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            // Italic
            .replace(/\*([^*]+)\*/g, '<em>$1</em>')
            // Lists
            .replace(/^\s*[-*]\s+(.+)$/gm, '<li>$1</li>')
            // Paragraphs
            .replace(/\n\n/g, '</p><p>')
            // Line breaks
            .replace(/\n/g, '<br>');
        
        // Wrap list items
        html = html.replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>');
        
        // Wrap in paragraph
        html = `<p>${html}</p>`;
        
        // Clean up empty paragraphs
        html = html.replace(/<p>\s*<\/p>/g, '');
        
        return html;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    addMessage(role, content, formattedHtml = null, injectData = null) {
        this.messages.push({ role, content, timestamp: Date.now() });
        
        const messageEl = document.createElement('div');
        messageEl.className = `ai-message ai-message-${role}`;
        
        const avatarIcon = role === 'user' ? 'user' : 'bot';
        
        messageEl.innerHTML = `
            <div class="ai-message-avatar">
                <i data-lucide="${avatarIcon}"></i>
            </div>
            <div class="ai-message-content">
                ${formattedHtml || this.formatMarkdown(content)}
            </div>
        `;
        
        // Add inject button if there's injectable data
        if (injectData && injectData.nodes?.length > 0) {
            const contentEl = messageEl.querySelector('.ai-message-content');
            const injectBtn = document.createElement('button');
            injectBtn.className = 'ai-inject-btn';
            injectBtn.innerHTML = `
                <i data-lucide="plus-circle"></i>
                Add ${injectData.nodes.length} node${injectData.nodes.length > 1 ? 's' : ''} to Canvas
            `;
            injectBtn.addEventListener('click', () => this.injectNodes(injectData));
            contentEl.appendChild(injectBtn);
        }
        
        this.messagesContainer?.appendChild(messageEl);
        this.scrollToBottom();
        
        // Refresh icons
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }
    
    addSystemMessage(content) {
        const messageEl = document.createElement('div');
        messageEl.className = 'ai-message ai-message-system';
        messageEl.innerHTML = `
            <div class="ai-message-avatar">
                <i data-lucide="info"></i>
            </div>
            <div class="ai-message-content">
                <p>${content}</p>
            </div>
        `;
        
        this.messagesContainer?.appendChild(messageEl);
        this.scrollToBottom();
        
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }
    
    addErrorMessage(content) {
        const messageEl = document.createElement('div');
        messageEl.className = 'ai-message ai-message-error';
        messageEl.innerHTML = `
            <div class="ai-message-avatar">
                <i data-lucide="alert-circle"></i>
            </div>
            <div class="ai-message-content">
                <p>${content}</p>
            </div>
        `;
        
        this.messagesContainer?.appendChild(messageEl);
        this.scrollToBottom();
        
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }
    
    addThinkingIndicator() {
        const thinkingEl = document.createElement('div');
        thinkingEl.className = 'ai-message ai-message-assistant';
        thinkingEl.innerHTML = `
            <div class="ai-message-avatar">
                <i data-lucide="bot"></i>
            </div>
            <div class="ai-thinking">
                <div class="ai-thinking-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
                <span>Thinking...</span>
            </div>
        `;
        
        this.messagesContainer?.appendChild(thinkingEl);
        this.scrollToBottom();
        
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
        
        return thinkingEl;
    }
    
    async injectNodes(data) {
        if (!data.nodes || data.nodes.length === 0) {
            this.addSystemMessage('No nodes to inject.');
            return;
        }
        
        try {
            const nodeIdMap = {}; // Map index to created node ID
            let successCount = 0;
            
            // Create nodes
            for (let i = 0; i < data.nodes.length; i++) {
                const nodeDef = data.nodes[i];
                
                // Prepare node data for API
                const nodeData = {
                    type: nodeDef.type || 'function',
                    position: nodeDef.position || [100 + (i * 250), 100],
                    parameters: {
                        name: nodeDef.name || `Node_${i}`,
                        ...nodeDef.parameters
                    },
                    metadata: {
                        ai_generated: true,
                        generated_at: new Date().toISOString()
                    },
                    inputs: nodeDef.inputs || [],
                    outputs: nodeDef.outputs || []
                };
                
                // Call API to create node
                try {
                    const response = await fetch('/api/canvas/nodes', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(nodeData)
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        nodeIdMap[i] = result.data.node_id;
                        successCount++;
                        // Node will be added to canvas via socket 'node_added' event
                    }
                } catch (e) {
                    console.error(`Failed to create node ${i}:`, e);
                }
            }
            
            // Create connections
            if (data.connections && data.connections.length > 0) {
                for (const conn of data.connections) {
                    const sourceId = nodeIdMap[conn.source_node_index];
                    const targetId = nodeIdMap[conn.target_node_index];
                    
                    if (sourceId && targetId) {
                        try {
                            await fetch('/api/canvas/connections', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    source_node_id: sourceId,
                                    source_port: conn.source_port,
                                    target_node_id: targetId,
                                    target_port: conn.target_port
                                })
                            });
                        } catch (e) {
                            console.error('Failed to create connection:', e);
                        }
                    }
                }
            }
            
            this.addSystemMessage(`✅ Successfully added ${successCount} node${successCount > 1 ? 's' : ''} to canvas!`);
            
        } catch (error) {
            console.error('Failed to inject nodes:', error);
            this.addErrorMessage(`Failed to inject nodes: ${error.message}`);
        }
    }
    
    updateSendButton() {
        if (this.sendBtn) {
            this.sendBtn.disabled = this.isLoading;
        }
    }
    
    scrollToBottom() {
        if (this.messagesContainer) {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }
    }
    
    clearChat() {
        this.messages = [];
        if (this.messagesContainer) {
            this.messagesContainer.innerHTML = `
                <div class="ai-message ai-message-system">
                    <div class="ai-message-avatar">
                        <i data-lucide="bot"></i>
                    </div>
                    <div class="ai-message-content">
                        <p>Chat cleared. How can I help you with your visual program?</p>
                    </div>
                </div>
            `;
        }
        
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }
}

// Export for use in app.js
window.AIChat = AIChat;
