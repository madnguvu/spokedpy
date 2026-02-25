/**
 * Properties Panel - Dynamic form generation and JSON editing
 * 
 * This module handles the properties panel with automatic form field generation
 * based on node parameter types and context, plus JSON editing capability.
 */

class PropertiesPanel {
    constructor(visualEditor) {
        this.visualEditor = visualEditor;
        this.currentNode = null;
        this.currentMode = 'form'; // 'form' or 'json'
        this.formData = {};
        this.jsonData = {};
        this.validationErrors = new Map();
        
        this.initializePanel();
    }
    
    initializePanel() {
        // Add mode toggle buttons
        this.addModeToggle();
        
        // Initialize form builders
        this.formBuilders = new Map([
            ['string', this.createStringField.bind(this)],
            ['number', this.createNumberField.bind(this)],
            ['integer', this.createIntegerField.bind(this)],
            ['boolean', this.createBooleanField.bind(this)],
            ['array', this.createArrayField.bind(this)],
            ['object', this.createObjectField.bind(this)],
            ['enum', this.createEnumField.bind(this)],
            ['file', this.createFileField.bind(this)],
            ['color', this.createColorField.bind(this)],
            ['date', this.createDateField.bind(this)],
            ['time', this.createTimeField.bind(this)],
            ['url', this.createUrlField.bind(this)],
            ['email', this.createEmailField.bind(this)],
            ['code', this.createCodeField.bind(this)],
            ['expression', this.createExpressionField.bind(this)],
            ['function_name', this.createFunctionNameField.bind(this)],
            ['variable_name', this.createVariableNameField.bind(this)],
            ['class_name', this.createClassNameField.bind(this)],
            ['module_path', this.createModulePathField.bind(this)]
        ]);
        
        // Initialize validation rules
        this.validationRules = new Map([
            ['required', this.validateRequired.bind(this)],
            ['min', this.validateMin.bind(this)],
            ['max', this.validateMax.bind(this)],
            ['pattern', this.validatePattern.bind(this)],
            ['email', this.validateEmail.bind(this)],
            ['url', this.validateUrl.bind(this)],
            ['python_identifier', this.validatePythonIdentifier.bind(this)]
        ]);
    }
    
    addModeToggle() {
        const panelHeader = document.querySelector('.properties-panel .panel-header');
        if (!panelHeader) return;
        
        const toggleContainer = document.createElement('div');
        toggleContainer.className = 'mode-toggle';
        toggleContainer.innerHTML = `
            <button id="form-mode-btn" class="mode-btn active" data-mode="form">
                <i data-lucide="settings"></i>
                Form
            </button>
            <button id="json-mode-btn" class="mode-btn" data-mode="json">
                <i data-lucide="code"></i>
                JSON
            </button>
        `;
        
        panelHeader.appendChild(toggleContainer);
        
        // Add event listeners
        document.getElementById('form-mode-btn').addEventListener('click', () => this.switchMode('form'));
        document.getElementById('json-mode-btn').addEventListener('click', () => this.switchMode('json'));
    }
    
    switchMode(mode) {
        if (this.currentMode === mode) return;
        
        // Save current data before switching
        if (this.currentMode === 'form') {
            this.saveFormData();
        } else if (this.currentMode === 'json') {
            this.saveJsonData();
        }
        
        this.currentMode = mode;
        
        // Update button states
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });
        
        // Re-render the current node
        if (this.currentNode) {
            this.showNodeProperties(this.currentNode);
        }
    }
    
    showNodeProperties(nodeData) {
        this.currentNode = nodeData;
        
        const noSelection = document.getElementById('no-selection');
        const nodeProperties = document.getElementById('node-properties');
        
        if (!nodeData) {
            noSelection.style.display = 'block';
            nodeProperties.style.display = 'none';
            return;
        }
        
        noSelection.style.display = 'none';
        nodeProperties.style.display = 'block';
        
        // Update basic info
        document.getElementById('prop-node-id').value = nodeData.id || '';
        document.getElementById('prop-node-type').value = nodeData.type || '';
        document.getElementById('prop-pos-x').value = nodeData.position ? nodeData.position[0] : 0;
        document.getElementById('prop-pos-y').value = nodeData.position ? nodeData.position[1] : 0;
        
        // Render parameters based on current mode
        if (this.currentMode === 'form') {
            this.renderFormView(nodeData);
        } else {
            this.renderJsonView(nodeData);
        }
        
        // Update ports
        this.updatePortsDisplay(nodeData);
    }
    
    renderFormView(nodeData) {
        const parametersContainer = document.getElementById('prop-parameters');
        parametersContainer.innerHTML = '';
        parametersContainer.className = 'parameters-form';
        
        const parameters = nodeData.parameters || {};
        const parameterSchema = this.getParameterSchema(nodeData.type);
        
        // Create form fields based on schema
        for (const [paramName, schema] of Object.entries(parameterSchema)) {
            const fieldContainer = document.createElement('div');
            fieldContainer.className = 'form-field';
            
            const currentValue = parameters[paramName];
            const field = this.createFormField(paramName, schema, currentValue);
            
            fieldContainer.appendChild(field);
            parametersContainer.appendChild(fieldContainer);
        }
        
        // Add custom parameters that aren't in schema
        for (const [paramName, value] of Object.entries(parameters)) {
            if (!parameterSchema[paramName]) {
                const fieldContainer = document.createElement('div');
                fieldContainer.className = 'form-field custom-field';
                
                const schema = this.inferParameterSchema(paramName, value);
                const field = this.createFormField(paramName, schema, value);
                
                fieldContainer.appendChild(field);
                parametersContainer.appendChild(fieldContainer);
            }
        }
        
        // Add "Add Parameter" button
        this.addParameterButton(parametersContainer);
    }
    
    renderJsonView(nodeData) {
        const parametersContainer = document.getElementById('prop-parameters');
        parametersContainer.innerHTML = '';
        parametersContainer.className = 'parameters-json';
        
        const mergedParameters = this.buildDefaultParameters(nodeData.type, nodeData.parameters || {});
        
        const jsonEditor = document.createElement('div');
        jsonEditor.className = 'json-editor';
        
        const textarea = document.createElement('textarea');
        textarea.id = 'json-parameters';
        textarea.className = 'json-textarea';
        textarea.value = JSON.stringify(mergedParameters, null, 2);
        textarea.addEventListener('input', this.validateJson.bind(this));
        
        const validationMessage = document.createElement('div');
        validationMessage.id = 'json-validation';
        validationMessage.className = 'validation-message';
        
        jsonEditor.appendChild(textarea);
        jsonEditor.appendChild(validationMessage);
        parametersContainer.appendChild(jsonEditor);
    }
    
    getParameterSchema(nodeType) {
        // Define schemas for different node types
        const schemas = {
            'function': {
                'name': {
                    type: 'string',
                    label: 'Name',
                    required: false,
                    description: 'Display name for this node'
                },
                'description': {
                    type: 'string',
                    label: 'Description',
                    required: false,
                    description: 'Short description of this node'
                },
                'source_code': {
                    type: 'code',
                    label: 'Source Code',
                    required: false,
                    description: 'Source code for this node'
                },
                'display_as': {
                    type: 'string',
                    label: 'Display As',
                    required: false,
                    description: 'Short label for the node display'
                },
                'show_display_label': {
                    type: 'boolean',
                    label: 'Show Display Label',
                    suppressDefault: true,
                    description: 'Show display label near node on hover'
                },
                'show_label_overlay': {
                    type: 'boolean',
                    label: 'Show Label Overlay',
                    suppressDefault: true,
                    description: 'Render label directly on node'
                },
                'source_language': {
                    type: 'enum',
                    label: 'Source Language',
                    options: ['python', 'javascript', 'typescript', 'unknown'],
                    required: false,
                    description: 'Detected source language'
                },
                'function_type': {
                    type: 'string',
                    label: 'Function Type',
                    required: false,
                    description: 'UIR-derived function type'
                },
                'function_name': {
                    type: 'function_name',
                    label: 'Function Name',
                    required: true,
                    description: 'Name of the function to call'
                },
                'module': {
                    type: 'module_path',
                    label: 'Module',
                    required: false,
                    description: 'Module containing the function'
                },
                'timeout': {
                    type: 'number',
                    label: 'Timeout (seconds)',
                    required: false,
                    min: 0,
                    max: 3600,
                    description: 'Maximum execution time'
                },
                'retry_count': {
                    type: 'integer',
                    label: 'Retry Count',
                    required: false,
                    min: 0,
                    max: 10,
                    default: 0,
                    description: 'Number of retries on failure'
                }
            },
            'variable': {
                'variable_name': {
                    type: 'variable_name',
                    label: 'Variable Name',
                    required: true,
                    description: 'Name of the variable'
                },
                'default_value': {
                    type: 'string',
                    label: 'Default Value',
                    required: false,
                    description: 'Initial value of the variable'
                },
                'data_type': {
                    type: 'enum',
                    label: 'Data Type',
                    options: ['string', 'number', 'boolean', 'array', 'object', 'null'],
                    default: 'string',
                    description: 'Type of the variable'
                },
                'is_constant': {
                    type: 'boolean',
                    label: 'Is Constant',
                    default: false,
                    description: 'Whether this is a constant value'
                }
            },
            'class': {
                'class_name': {
                    type: 'class_name',
                    label: 'Class Name',
                    required: true,
                    description: 'Name of the class'
                },
                'base_classes': {
                    type: 'array',
                    label: 'Base Classes',
                    itemType: 'class_name',
                    description: 'Parent classes to inherit from'
                },
                'is_abstract': {
                    type: 'boolean',
                    label: 'Abstract Class',
                    default: false,
                    description: 'Whether this is an abstract class'
                },
                'metaclass': {
                    type: 'class_name',
                    label: 'Metaclass',
                    required: false,
                    description: 'Custom metaclass to use'
                }
            },
            'control_flow': {
                'control_type': {
                    type: 'enum',
                    label: 'Control Type',
                    options: ['if', 'for', 'while', 'try', 'with'],
                    required: true,
                    description: 'Type of control flow structure'
                },
                'condition': {
                    type: 'expression',
                    label: 'Condition',
                    required: false,
                    description: 'Condition expression (for if/while)'
                },
                'iterable': {
                    type: 'expression',
                    label: 'Iterable',
                    required: false,
                    description: 'Iterable expression (for loops)'
                }
            },
            'pattern': {
                'pattern_type': {
                    type: 'enum',
                    label: 'Pattern Type',
                    options: ['singleton', 'factory', 'observer', 'decorator', 'strategy'],
                    required: true,
                    description: 'Type of design pattern'
                },
                'implementation': {
                    type: 'enum',
                    label: 'Implementation',
                    options: ['basic', 'thread_safe', 'lazy', 'eager'],
                    default: 'basic',
                    description: 'Pattern implementation variant'
                }
            },
            'custom': {
                'name': {
                    type: 'string',
                    label: 'Name',
                    required: false,
                    description: 'Display name for this node'
                },
                'description': {
                    type: 'string',
                    label: 'Description',
                    required: false,
                    description: 'Short description of this node'
                },
                'source_code': {
                    type: 'code',
                    label: 'Source Code',
                    required: false,
                    description: 'Source code for this node'
                },
                'display_as': {
                    type: 'string',
                    label: 'Display As',
                    required: false,
                    description: 'Short label for the node display'
                },
                'show_display_label': {
                    type: 'boolean',
                    label: 'Show Display Label',
                    suppressDefault: true,
                    description: 'Show display label near node on hover'
                },
                'show_label_overlay': {
                    type: 'boolean',
                    label: 'Show Label Overlay',
                    suppressDefault: true,
                    description: 'Render label directly on node'
                },
                'source_language': {
                    type: 'enum',
                    label: 'Source Language',
                    options: ['python', 'javascript', 'typescript', 'unknown'],
                    required: false,
                    description: 'Detected source language'
                },
                'function_type': {
                    type: 'string',
                    label: 'Function Type',
                    required: false,
                    description: 'UIR-derived function type'
                }
            }
        };
        
        return schemas[nodeType] || {};
    }

    buildDefaultParameters(nodeType, currentParameters = {}) {
        const parameterSchema = this.getParameterSchema(nodeType);
        const merged = {};
        
        for (const [paramName, schema] of Object.entries(parameterSchema)) {
            if (currentParameters[paramName] !== undefined) {
                merged[paramName] = currentParameters[paramName];
                continue;
            }

            if (schema.suppressDefault) {
                continue;
            }
            
            if (schema.default !== undefined) {
                merged[paramName] = schema.default;
                continue;
            }
            
            switch (schema.type) {
                case 'boolean':
                    merged[paramName] = false;
                    break;
                case 'array':
                    merged[paramName] = [];
                    break;
                case 'object':
                    merged[paramName] = {};
                    break;
                case 'enum':
                    merged[paramName] = schema.options?.[0] ?? '';
                    break;
                default:
                    merged[paramName] = '';
            }
        }
        
        for (const [paramName, value] of Object.entries(currentParameters)) {
            if (merged[paramName] === undefined) {
                merged[paramName] = value;
            }
        }
        
        return merged;
    }
    
    inferParameterSchema(paramName, value) {
        // Infer schema from parameter name and value
        const namePatterns = {
            'name': { type: 'string', pattern: '^[a-zA-Z_][a-zA-Z0-9_]*$' },
            'count': { type: 'integer', min: 0 },
            'size': { type: 'integer', min: 1 },
            'timeout': { type: 'number', min: 0 },
            'enabled': { type: 'boolean' },
            'url': { type: 'url' },
            'email': { type: 'email' },
            'color': { type: 'color' },
            'date': { type: 'date' },
            'time': { type: 'time' },
            'file': { type: 'file' },
            'code': { type: 'code' }
        };
        
        // Check name patterns
        for (const [pattern, schema] of Object.entries(namePatterns)) {
            if (paramName.toLowerCase().includes(pattern)) {
                return { ...schema, label: this.formatLabel(paramName) };
            }
        }
        
        // Infer from value type
        if (typeof value === 'boolean') {
            return { type: 'boolean', label: this.formatLabel(paramName) };
        } else if (typeof value === 'number') {
            return { 
                type: Number.isInteger(value) ? 'integer' : 'number', 
                label: this.formatLabel(paramName) 
            };
        } else if (Array.isArray(value)) {
            return { type: 'array', label: this.formatLabel(paramName) };
        } else if (typeof value === 'object' && value !== null) {
            return { type: 'object', label: this.formatLabel(paramName) };
        }
        
        // Default to string
        return { type: 'string', label: this.formatLabel(paramName) };
    }
    
    formatLabel(paramName) {
        return paramName
            .replace(/_/g, ' ')
            .replace(/([A-Z])/g, ' $1')
            .replace(/^./, str => str.toUpperCase())
            .trim();
    }
    
    createFormField(paramName, schema, currentValue) {
        const fieldContainer = document.createElement('div');
        fieldContainer.className = 'field-container';
        
        // Create label
        const label = document.createElement('label');
        label.textContent = schema.label || this.formatLabel(paramName);
        label.className = 'field-label';
        if (schema.required) {
            label.classList.add('required');
        }
        
        // Create field based on type
        const fieldBuilder = this.formBuilders.get(schema.type) || this.createStringField;
        const field = fieldBuilder(paramName, schema, currentValue);
        
        // Add description if available
        if (schema.description) {
            const description = document.createElement('div');
            description.className = 'field-description';
            description.textContent = schema.description;
            fieldContainer.appendChild(description);
        }
        
        // Add validation message container
        const validationMessage = document.createElement('div');
        validationMessage.className = 'field-validation';
        validationMessage.id = `validation-${paramName}`;
        
        fieldContainer.appendChild(label);
        fieldContainer.appendChild(field);
        fieldContainer.appendChild(validationMessage);
        
        return fieldContainer;
    }
    
    createStringField(paramName, schema, currentValue) {
        const input = document.createElement('input');
        input.type = 'text';
        input.name = paramName;
        input.value = currentValue || schema.default || '';
        input.className = 'form-input';
        
        if (schema.placeholder) {
            input.placeholder = schema.placeholder;
        }
        
        if (schema.pattern) {
            input.pattern = schema.pattern;
        }
        
        input.addEventListener('input', (e) => {
            this.validateField(paramName, e.target.value, schema);
            this.updateParameter(paramName, e.target.value);
        });
        
        return input;
    }
    
    createNumberField(paramName, schema, currentValue) {
        const input = document.createElement('input');
        input.type = 'number';
        input.name = paramName;
        input.value = currentValue !== undefined ? currentValue : (schema.default || '');
        input.className = 'form-input';
        
        if (schema.min !== undefined) input.min = schema.min;
        if (schema.max !== undefined) input.max = schema.max;
        if (schema.step !== undefined) input.step = schema.step;
        
        input.addEventListener('input', (e) => {
            const value = parseFloat(e.target.value);
            this.validateField(paramName, value, schema);
            this.updateParameter(paramName, isNaN(value) ? null : value);
        });
        
        return input;
    }
    
    createIntegerField(paramName, schema, currentValue) {
        const input = document.createElement('input');
        input.type = 'number';
        input.name = paramName;
        input.value = currentValue !== undefined ? currentValue : (schema.default || '');
        input.className = 'form-input';
        input.step = '1';
        
        if (schema.min !== undefined) input.min = schema.min;
        if (schema.max !== undefined) input.max = schema.max;
        
        input.addEventListener('input', (e) => {
            const value = parseInt(e.target.value);
            this.validateField(paramName, value, schema);
            this.updateParameter(paramName, isNaN(value) ? null : value);
        });
        
        return input;
    }
    
    createBooleanField(paramName, schema, currentValue) {
        const container = document.createElement('div');
        container.className = 'checkbox-container';
        
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.name = paramName;
        input.checked = currentValue !== undefined ? currentValue : (schema.default || false);
        input.className = 'form-checkbox';
        
        const checkboxLabel = document.createElement('label');
        checkboxLabel.textContent = schema.checkboxLabel || 'Enable';
        checkboxLabel.className = 'checkbox-label';
        
        input.addEventListener('change', (e) => {
            this.updateParameter(paramName, e.target.checked);
        });
        
        container.appendChild(input);
        container.appendChild(checkboxLabel);
        
        return container;
    }
    
    createArrayField(paramName, schema, currentValue) {
        const container = document.createElement('div');
        container.className = 'array-field';
        
        const itemsContainer = document.createElement('div');
        itemsContainer.className = 'array-items';
        
        const items = Array.isArray(currentValue) ? currentValue : (schema.default || []);
        
        const renderItems = () => {
            itemsContainer.innerHTML = '';
            items.forEach((item, index) => {
                const itemContainer = document.createElement('div');
                itemContainer.className = 'array-item';
                
                const itemInput = document.createElement('input');
                itemInput.type = 'text';
                itemInput.value = item;
                itemInput.className = 'form-input';
                
                const removeBtn = document.createElement('button');
                removeBtn.type = 'button';
                removeBtn.className = 'btn-remove';
                removeBtn.innerHTML = '<i data-lucide="x"></i>';
                removeBtn.addEventListener('click', () => {
                    items.splice(index, 1);
                    renderItems();
                    this.updateParameter(paramName, items);
                });
                
                itemInput.addEventListener('input', (e) => {
                    items[index] = e.target.value;
                    this.updateParameter(paramName, items);
                });
                
                itemContainer.appendChild(itemInput);
                itemContainer.appendChild(removeBtn);
                itemsContainer.appendChild(itemContainer);
            });
        };
        
        const addBtn = document.createElement('button');
        addBtn.type = 'button';
        addBtn.className = 'btn-add';
        addBtn.innerHTML = '<i data-lucide="plus"></i> Add Item';
        addBtn.addEventListener('click', () => {
            items.push('');
            renderItems();
            this.updateParameter(paramName, items);
        });
        
        renderItems();
        container.appendChild(itemsContainer);
        container.appendChild(addBtn);
        
        return container;
    }
    
    createObjectField(paramName, schema, currentValue) {
        const container = document.createElement('div');
        container.className = 'object-field';
        
        const textarea = document.createElement('textarea');
        textarea.name = paramName;
        textarea.className = 'form-textarea object-textarea';
        textarea.rows = 4;
        
        try {
            textarea.value = JSON.stringify(currentValue || schema.default || {}, null, 2);
        } catch (e) {
            textarea.value = '{}';
        }
        
        textarea.addEventListener('input', (e) => {
            try {
                const value = JSON.parse(e.target.value);
                this.clearFieldValidation(paramName);
                this.updateParameter(paramName, value);
            } catch (error) {
                this.setFieldValidation(paramName, 'Invalid JSON format');
            }
        });
        
        container.appendChild(textarea);
        return container;
    }
    
    createEnumField(paramName, schema, currentValue) {
        const select = document.createElement('select');
        select.name = paramName;
        select.className = 'form-select';
        
        // Add empty option if not required
        if (!schema.required) {
            const emptyOption = document.createElement('option');
            emptyOption.value = '';
            emptyOption.textContent = '-- Select --';
            select.appendChild(emptyOption);
        }
        
        // Add options
        for (const option of schema.options || []) {
            const optionElement = document.createElement('option');
            optionElement.value = option;
            optionElement.textContent = option;
            optionElement.selected = currentValue === option;
            select.appendChild(optionElement);
        }
        
        select.addEventListener('change', (e) => {
            this.updateParameter(paramName, e.target.value || null);
        });
        
        return select;
    }
    
    createFileField(paramName, schema, currentValue) {
        const container = document.createElement('div');
        container.className = 'file-field';
        
        const input = document.createElement('input');
        input.type = 'file';
        input.name = paramName;
        input.className = 'form-file';
        
        if (schema.accept) {
            input.accept = schema.accept;
        }
        
        const preview = document.createElement('div');
        preview.className = 'file-preview';
        if (currentValue) {
            preview.textContent = `Current: ${currentValue}`;
        }
        
        input.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                preview.textContent = `Selected: ${file.name}`;
                this.updateParameter(paramName, file.name);
            }
        });
        
        container.appendChild(input);
        container.appendChild(preview);
        
        return container;
    }
    
    createColorField(paramName, schema, currentValue) {
        const input = document.createElement('input');
        input.type = 'color';
        input.name = paramName;
        input.value = currentValue || schema.default || '#000000';
        input.className = 'form-color';
        
        input.addEventListener('input', (e) => {
            this.updateParameter(paramName, e.target.value);
        });
        
        return input;
    }
    
    createDateField(paramName, schema, currentValue) {
        const input = document.createElement('input');
        input.type = 'date';
        input.name = paramName;
        input.value = currentValue || schema.default || '';
        input.className = 'form-input';
        
        input.addEventListener('input', (e) => {
            this.updateParameter(paramName, e.target.value);
        });
        
        return input;
    }
    
    createTimeField(paramName, schema, currentValue) {
        const input = document.createElement('input');
        input.type = 'time';
        input.name = paramName;
        input.value = currentValue || schema.default || '';
        input.className = 'form-input';
        
        input.addEventListener('input', (e) => {
            this.updateParameter(paramName, e.target.value);
        });
        
        return input;
    }
    
    createUrlField(paramName, schema, currentValue) {
        const input = document.createElement('input');
        input.type = 'url';
        input.name = paramName;
        input.value = currentValue || schema.default || '';
        input.className = 'form-input';
        input.placeholder = 'https://example.com';
        
        input.addEventListener('input', (e) => {
            this.validateField(paramName, e.target.value, schema);
            this.updateParameter(paramName, e.target.value);
        });
        
        return input;
    }
    
    createEmailField(paramName, schema, currentValue) {
        const input = document.createElement('input');
        input.type = 'email';
        input.name = paramName;
        input.value = currentValue || schema.default || '';
        input.className = 'form-input';
        input.placeholder = 'user@example.com';
        
        input.addEventListener('input', (e) => {
            this.validateField(paramName, e.target.value, schema);
            this.updateParameter(paramName, e.target.value);
        });
        
        return input;
    }
    
    createCodeField(paramName, schema, currentValue) {
        const wrapper = document.createElement('div');
        wrapper.className = 'code-field-wrapper';

        // Code Dive button
        const diveBtn = document.createElement('button');
        diveBtn.type = 'button';
        diveBtn.className = 'code-dive-trigger-btn';
        diveBtn.innerHTML = '<i data-lucide="maximize-2"></i> Code Dive';
        diveBtn.title = 'Open immersive editor (Monaco)';
        diveBtn.addEventListener('click', () => {
            const nodeId = this.getCurrentNodeCanvasId();
            if (nodeId && window.visualEditor) {
                window.visualEditor.enterCodeDive(nodeId, { fromPanel: true });
            }
        });

        const textarea = document.createElement('textarea');
        textarea.name = paramName;
        textarea.className = 'form-textarea code-textarea';
        textarea.value = currentValue || schema.default || '';
        textarea.rows = 6;
        textarea.style.fontFamily = 'monospace';
        
        textarea.addEventListener('input', (e) => {
            this.updateParameter(paramName, e.target.value);
        });

        wrapper.appendChild(diveBtn);
        wrapper.appendChild(textarea);
        return wrapper;
    }
    
    createExpressionField(paramName, schema, currentValue) {
        const container = document.createElement('div');
        container.className = 'expression-field';
        
        const input = document.createElement('input');
        input.type = 'text';
        input.name = paramName;
        input.value = currentValue || schema.default || '';
        input.className = 'form-input expression-input';
        input.placeholder = 'Enter Python expression...';
        
        const helpBtn = document.createElement('button');
        helpBtn.type = 'button';
        helpBtn.className = 'btn-help';
        helpBtn.innerHTML = '<i data-lucide="help-circle"></i>';
        helpBtn.title = 'Expression help';
        
        input.addEventListener('input', (e) => {
            this.validatePythonExpression(paramName, e.target.value);
            this.updateParameter(paramName, e.target.value);
        });
        
        container.appendChild(input);
        container.appendChild(helpBtn);
        
        return container;
    }
    
    createFunctionNameField(paramName, schema, currentValue) {
        const input = document.createElement('input');
        input.type = 'text';
        input.name = paramName;
        input.value = currentValue || schema.default || '';
        input.className = 'form-input';
        input.placeholder = 'function_name';
        input.pattern = '^[a-zA-Z_][a-zA-Z0-9_]*$';
        
        input.addEventListener('input', (e) => {
            this.validateField(paramName, e.target.value, {
                ...schema,
                validation: ['python_identifier']
            });
            this.updateParameter(paramName, e.target.value);
        });
        
        return input;
    }
    
    createVariableNameField(paramName, schema, currentValue) {
        const input = document.createElement('input');
        input.type = 'text';
        input.name = paramName;
        input.value = currentValue || schema.default || '';
        input.className = 'form-input';
        input.placeholder = 'variable_name';
        input.pattern = '^[a-zA-Z_][a-zA-Z0-9_]*$';
        
        input.addEventListener('input', (e) => {
            this.validateField(paramName, e.target.value, {
                ...schema,
                validation: ['python_identifier']
            });
            this.updateParameter(paramName, e.target.value);
        });
        
        return input;
    }
    
    createClassNameField(paramName, schema, currentValue) {
        const input = document.createElement('input');
        input.type = 'text';
        input.name = paramName;
        input.value = currentValue || schema.default || '';
        input.className = 'form-input';
        input.placeholder = 'ClassName';
        input.pattern = '^[A-Z][a-zA-Z0-9_]*$';
        
        input.addEventListener('input', (e) => {
            this.validateField(paramName, e.target.value, {
                ...schema,
                validation: ['python_identifier'],
                pattern: '^[A-Z][a-zA-Z0-9_]*$'
            });
            this.updateParameter(paramName, e.target.value);
        });
        
        return input;
    }
    
    createModulePathField(paramName, schema, currentValue) {
        const input = document.createElement('input');
        input.type = 'text';
        input.name = paramName;
        input.value = currentValue || schema.default || '';
        input.className = 'form-input';
        input.placeholder = 'module.submodule';
        
        input.addEventListener('input', (e) => {
            this.validateModulePath(paramName, e.target.value);
            this.updateParameter(paramName, e.target.value);
        });
        
        return input;
    }
    
    addParameterButton(container) {
        const addButton = document.createElement('button');
        addButton.type = 'button';
        addButton.className = 'btn-add-parameter';
        addButton.innerHTML = '<i data-lucide="plus"></i> Add Custom Parameter';
        
        addButton.addEventListener('click', () => {
            this.showAddParameterDialog();
        });
        
        container.appendChild(addButton);
    }
    
    showAddParameterDialog() {
        const dialog = document.createElement('div');
        dialog.className = 'add-parameter-dialog';
        dialog.innerHTML = `
            <div class="dialog-content">
                <h3>Add Custom Parameter</h3>
                <div class="form-field">
                    <label>Parameter Name:</label>
                    <input type="text" id="new-param-name" placeholder="parameter_name">
                </div>
                <div class="form-field">
                    <label>Parameter Type:</label>
                    <select id="new-param-type">
                        <option value="string">String</option>
                        <option value="number">Number</option>
                        <option value="boolean">Boolean</option>
                        <option value="array">Array</option>
                        <option value="object">Object</option>
                    </select>
                </div>
                <div class="form-field">
                    <label>Default Value:</label>
                    <input type="text" id="new-param-value" placeholder="Default value">
                </div>
                <div class="dialog-actions">
                    <button id="add-param-btn">Add</button>
                    <button id="cancel-param-btn">Cancel</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(dialog);
        
        document.getElementById('add-param-btn').addEventListener('click', () => {
            const name = document.getElementById('new-param-name').value;
            const type = document.getElementById('new-param-type').value;
            const value = document.getElementById('new-param-value').value;
            
            if (name) {
                this.addCustomParameter(name, type, value);
                dialog.remove();
            }
        });
        
        document.getElementById('cancel-param-btn').addEventListener('click', () => {
            dialog.remove();
        });
    }
    
    addCustomParameter(name, type, value) {
        if (!this.currentNode) return;
        
        // Convert value based on type
        let convertedValue = value;
        try {
            switch (type) {
                case 'number':
                    convertedValue = parseFloat(value) || 0;
                    break;
                case 'boolean':
                    convertedValue = value.toLowerCase() === 'true';
                    break;
                case 'array':
                    convertedValue = value ? JSON.parse(value) : [];
                    break;
                case 'object':
                    convertedValue = value ? JSON.parse(value) : {};
                    break;
            }
        } catch (e) {
            console.warn('Failed to convert parameter value:', e);
        }
        
        this.updateParameter(name, convertedValue);
        this.showNodeProperties(this.currentNode); // Re-render
    }
    
    updateParameter(paramName, value) {
        if (!this.currentNode) return;
        
        // Update the node's parameters
        if (!this.currentNode.parameters) {
            this.currentNode.parameters = {};
        }
        this.currentNode.parameters[paramName] = value;
        
        // Send update to backend
        this.sendParameterUpdate(paramName, value);

        if (paramName === 'name' || paramName === 'display_name' || paramName === 'display_as') {
            if (!this.currentNode.metadata) {
                this.currentNode.metadata = {};
            }
            if (paramName === 'display_as') {
                this.currentNode.metadata.display_as = value;
                this.sendMetadataUpdate({ display_as: value });
            } else {
                this.currentNode.metadata.name = value;
                this.sendMetadataUpdate({ name: value });
            }
        }
    }
    
    async sendParameterUpdate(paramName, value) {
        const nodeId = this.getCurrentNodeCanvasId();
        if (!nodeId) return;
        
        try {
            const response = await fetch(`/api/canvas/nodes/${nodeId}/parameters`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    [paramName]: value
                })
            });
            
            if (!response.ok) {
                console.error('Failed to update parameter:', response.statusText);
            }
        } catch (error) {
            console.error('Error updating parameter:', error);
        }
    }
    
    validateField(paramName, value, schema) {
        const errors = [];
        
        // Run validation rules
        if (schema.validation) {
            for (const rule of schema.validation) {
                const validator = this.validationRules.get(rule);
                if (validator) {
                    const error = validator(value, schema);
                    if (error) errors.push(error);
                }
            }
        }
        
        // Built-in validations
        if (schema.required && !value) {
            errors.push('This field is required');
        }
        
        if (value && schema.min !== undefined && value < schema.min) {
            errors.push(`Value must be at least ${schema.min}`);
        }
        
        if (value && schema.max !== undefined && value > schema.max) {
            errors.push(`Value must be at most ${schema.max}`);
        }
        
        if (value && schema.pattern) {
            const regex = new RegExp(schema.pattern);
            if (!regex.test(value)) {
                errors.push('Value does not match required pattern');
            }
        }
        
        // Update validation display
        if (errors.length > 0) {
            this.setFieldValidation(paramName, errors[0]);
        } else {
            this.clearFieldValidation(paramName);
        }
        
        return errors.length === 0;
    }
    
    validateRequired(value, schema) {
        if (schema.required && (!value || value === '')) {
            return 'This field is required';
        }
        return null;
    }
    
    validateMin(value, schema) {
        if (value !== undefined && schema.min !== undefined && value < schema.min) {
            return `Value must be at least ${schema.min}`;
        }
        return null;
    }
    
    validateMax(value, schema) {
        if (value !== undefined && schema.max !== undefined && value > schema.max) {
            return `Value must be at most ${schema.max}`;
        }
        return null;
    }
    
    validatePattern(value, schema) {
        if (value && schema.pattern) {
            const regex = new RegExp(schema.pattern);
            if (!regex.test(value)) {
                return 'Value does not match required pattern';
            }
        }
        return null;
    }
    
    validateEmail(value, schema) {
        if (value) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(value)) {
                return 'Please enter a valid email address';
            }
        }
        return null;
    }
    
    validateUrl(value, schema) {
        if (value) {
            try {
                new URL(value);
            } catch (e) {
                return 'Please enter a valid URL';
            }
        }
        return null;
    }
    
    validatePythonIdentifier(value, schema) {
        if (value) {
            const identifierRegex = /^[a-zA-Z_][a-zA-Z0-9_]*$/;
            if (!identifierRegex.test(value)) {
                return 'Must be a valid Python identifier';
            }
        }
        return null;
    }
    
    validatePythonExpression(paramName, expression) {
        // Simple validation - in practice you'd want more sophisticated parsing
        if (expression) {
            // Check for basic syntax issues
            const dangerousPatterns = ['import ', 'exec(', 'eval(', '__'];
            for (const pattern of dangerousPatterns) {
                if (expression.includes(pattern)) {
                    this.setFieldValidation(paramName, 'Expression contains potentially dangerous code');
                    return false;
                }
            }
        }
        
        this.clearFieldValidation(paramName);
        return true;
    }
    
    validateModulePath(paramName, path) {
        if (path) {
            const moduleRegex = /^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$/;
            if (!moduleRegex.test(path)) {
                this.setFieldValidation(paramName, 'Must be a valid module path (e.g., module.submodule)');
                return false;
            }
        }
        
        this.clearFieldValidation(paramName);
        return true;
    }
    
    validateJson() {
        const textarea = document.getElementById('json-parameters');
        const validationMessage = document.getElementById('json-validation');
        
        if (!textarea || !validationMessage) return;
        
        try {
            const parsed = JSON.parse(textarea.value);
            validationMessage.textContent = '';
            validationMessage.className = 'validation-message';
            
            // Update the current node's parameters
            if (this.currentNode) {
                this.currentNode.parameters = parsed;
                this.sendAllParametersUpdate(parsed);
            }
        } catch (error) {
            validationMessage.textContent = `Invalid JSON: ${error.message}`;
            validationMessage.className = 'validation-message error';
        }
    }
    
    async sendAllParametersUpdate(parameters) {
        const nodeId = this.getCurrentNodeCanvasId();
        if (!nodeId) return;
        
        try {
            const response = await fetch(`/api/canvas/nodes/${nodeId}/parameters`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(parameters)
            });
            
            if (!response.ok) {
                console.error('Failed to update parameters:', response.statusText);
            }
        } catch (error) {
            console.error('Error updating parameters:', error);
        }
    }

    async sendMetadataUpdate(metadata) {
        const nodeId = this.getCurrentNodeCanvasId();
        if (!nodeId) return;
        
        try {
            const response = await fetch(`/api/canvas/nodes/${nodeId}/metadata`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(metadata)
            });
            
            if (!response.ok) {
                console.error('Failed to update metadata:', response.statusText);
            }
        } catch (error) {
            console.error('Error updating metadata:', error);
        }
    }

    getCurrentNodeCanvasId() {
        if (!this.currentNode) return null;
        return this.currentNode.canvasId || this.currentNode.node_id || this.currentNode.nodeId || null;
    }
    
    setFieldValidation(paramName, message) {
        const validationElement = document.getElementById(`validation-${paramName}`);
        if (validationElement) {
            validationElement.textContent = message;
            validationElement.className = 'field-validation error';
        }
        this.validationErrors.set(paramName, message);
    }
    
    clearFieldValidation(paramName) {
        const validationElement = document.getElementById(`validation-${paramName}`);
        if (validationElement) {
            validationElement.textContent = '';
            validationElement.className = 'field-validation';
        }
        this.validationErrors.delete(paramName);
    }
    
    saveFormData() {
        // Save current form data
        this.formData = { ...this.currentNode?.parameters };
    }
    
    saveJsonData() {
        // Save current JSON data
        const textarea = document.getElementById('json-parameters');
        if (textarea) {
            try {
                this.jsonData = JSON.parse(textarea.value);
            } catch (e) {
                this.jsonData = this.currentNode?.parameters || {};
            }
        }
    }
    
    updatePortsDisplay(nodeData) {
        // Update inputs display
        const inputsContainer = document.getElementById('prop-inputs');
        inputsContainer.innerHTML = '';
        this.renderPortEditorList(inputsContainer, nodeData.inputs || [], true);
        
        // Update outputs display
        const outputsContainer = document.getElementById('prop-outputs');
        outputsContainer.innerHTML = '';
        this.renderPortEditorList(outputsContainer, nodeData.outputs || [], false);
    }

    renderPortEditorList(container, ports, isInput) {
        const list = document.createElement('div');
        list.className = 'port-editor-list';
        
        ports.forEach((port) => {
            const row = this.createPortEditorRow(port, isInput);
            list.appendChild(row);
        });
        
        const addButton = document.createElement('button');
        addButton.type = 'button';
        addButton.className = 'btn-add-parameter';
        addButton.innerHTML = `<i data-lucide="plus"></i> Add ${isInput ? 'Input' : 'Output'}`;
        addButton.addEventListener('click', () => this.addPort(isInput));
        
        container.appendChild(list);
        container.appendChild(addButton);
    }

    createPortEditorRow(port, isInput) {
        const row = document.createElement('div');
        row.className = 'port-item port-edit-row';
        
        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.className = 'form-input port-name-input';
        nameInput.value = port.name || '';
        
        const typeSelect = document.createElement('select');
        typeSelect.className = 'form-select port-type-select';
        this.getPortTypeOptions().forEach(option => {
            const opt = document.createElement('option');
            opt.value = option.value;
            opt.textContent = option.label;
            typeSelect.appendChild(opt);
        });
        typeSelect.value = this.normalizePortType(port.type);
        
        const removeButton = document.createElement('button');
        removeButton.type = 'button';
        removeButton.className = 'btn-remove';
        removeButton.innerHTML = '<i data-lucide="x"></i>';
        
        row.appendChild(nameInput);
        row.appendChild(typeSelect);
        
        if (isInput) {
            const requiredLabel = document.createElement('label');
            requiredLabel.className = 'checkbox-container';
            
            const requiredInput = document.createElement('input');
            requiredInput.type = 'checkbox';
            requiredInput.className = 'form-checkbox';
            requiredInput.checked = Boolean(port.required);
            
            const requiredText = document.createElement('span');
            requiredText.className = 'checkbox-label';
            requiredText.textContent = 'Required';
            
            requiredLabel.appendChild(requiredInput);
            requiredLabel.appendChild(requiredText);
            row.appendChild(requiredLabel);
            
            requiredInput.addEventListener('change', () => {
                port.required = requiredInput.checked;
                this.updatePorts();
            });
        }
        
        row.appendChild(removeButton);
        
        const commitNameChange = () => {
            const nextName = nameInput.value.trim();
            if (!nextName) return;
            port.name = nextName;
            this.updatePorts();
        };
        
        nameInput.addEventListener('change', commitNameChange);
        nameInput.addEventListener('blur', commitNameChange);
        
        typeSelect.addEventListener('change', () => {
            port.type = typeSelect.value;
            this.updatePorts();
        });
        
        removeButton.addEventListener('click', () => {
            this.removePort(port, isInput);
        });
        
        if (typeof lucide !== 'undefined') lucide.createIcons({ root: row });
        return row;
    }

    getPortTypeOptions() {
        return [
            { value: 'object', label: 'Object' },
            { value: 'string', label: 'String' },
            { value: 'number', label: 'Number' },
            { value: 'integer', label: 'Integer' },
            { value: 'boolean', label: 'Boolean' },
            { value: 'array', label: 'Array' },
            { value: 'dict', label: 'Dict' }
        ];
    }

    normalizePortType(typeValue) {
        const normalized = String(typeValue || '').toLowerCase();
        const map = {
            'str': 'string',
            'string': 'string',
            'int': 'integer',
            'integer': 'integer',
            'float': 'number',
            'number': 'number',
            'bool': 'boolean',
            'boolean': 'boolean',
            'list': 'array',
            'array': 'array',
            'dict': 'dict',
            'object': 'object',
            'any': 'object'
        };
        return map[normalized] || 'object';
    }

    addPort(isInput) {
        if (!this.currentNode) return;
        const ports = isInput ? (this.currentNode.inputs || []) : (this.currentNode.outputs || []);
        const baseName = isInput ? 'input' : 'output';
        const existingNames = new Set(ports.map(port => port.name));
        let name = baseName;
        let index = 1;
        while (existingNames.has(name)) {
            name = `${baseName}_${index}`;
            index += 1;
        }
        
        const newPort = {
            name,
            type: 'object'
        };
        if (isInput) {
            newPort.required = false;
        }
        
        ports.push(newPort);
        if (isInput) {
            this.currentNode.inputs = ports;
        } else {
            this.currentNode.outputs = ports;
        }
        this.updatePorts();
        this.showNodeProperties(this.currentNode);
    }

    removePort(port, isInput) {
        if (!this.currentNode) return;
        const ports = isInput ? (this.currentNode.inputs || []) : (this.currentNode.outputs || []);
        const updated = ports.filter(item => item !== port);
        if (isInput) {
            this.currentNode.inputs = updated;
        } else {
            this.currentNode.outputs = updated;
        }
        this.updatePorts();
        this.showNodeProperties(this.currentNode);
    }

    updatePorts() {
        if (!this.currentNode) return;
        const inputs = (this.currentNode.inputs || []).map((port) => ({
            name: port.name,
            type: port.type || 'object',
            required: Boolean(port.required)
        }));
        const outputs = (this.currentNode.outputs || []).map((port) => ({
            name: port.name,
            type: port.type || 'object'
        }));
        this.sendPortsUpdate(inputs, outputs);
    }

    async sendPortsUpdate(inputs, outputs) {
        const nodeId = this.getCurrentNodeCanvasId();
        if (!nodeId) return;
        
        try {
            const response = await fetch(`/api/canvas/nodes/${nodeId}/ports`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    inputs,
                    outputs
                })
            });
            
            if (!response.ok) {
                console.error('Failed to update ports:', response.statusText);
            }
        } catch (error) {
            console.error('Error updating ports:', error);
        }
    }
}

// Export for use in main application
window.PropertiesPanel = PropertiesPanel;
