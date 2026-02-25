/**
 * Repository Analyzer - Advanced code analysis and node generation
 * 
 * This module handles importing and analyzing entire repositories,
 * breaking them down into meaningful visual nodes.
 */

class RepositoryAnalyzer {
    constructor(visualEditor) {
        this.visualEditor = visualEditor;
        this.analysisResults = null;
        this.importedFiles = new Map();
        this.dependencyGraph = new Map();
        this.codePatterns = new Map();
        this.generatedNodes = new Map();
    }
    
    /**
     * Import and analyze a repository from uploaded files
     */
    async importRepository(files, options = {}) {
        console.log('Starting repository import...', files.length, 'files');
        console.log('Import options:', options);
        
        try {
            const progressTitle = options.progressTitle || 'Analyzing Repository';
            const resultsTitle = options.resultsTitle || 'Repository Analysis Complete';
            const importMode = options.importMode || 'full-analysis';
            const targetLanguage = options.targetLanguage || '';
            const sourceLanguage = options.sourceLanguage || '';
            const dependencyStrategy = options.dependencyStrategy || 'preserve';

            // Show progress dialog
            this.showProgressDialog(progressTitle, 'Reading files...');

            // Clear backend canvas to avoid duplicate nodes (unless in uir-only mode)
            if (importMode !== 'uir-only') {
                try {
                    await fetch('/api/canvas/clear', { method: 'POST' });
                } catch (error) {
                    console.warn('Failed to clear backend canvas:', error);
                }
                
                // Clear client canvas
                await this.visualEditor.clearCanvas();
            }
            
            // Read all files with optional language override
            const fileContents = await this.readFiles(files, sourceLanguage);
            console.log('Files read successfully:', fileContents.length, 'supported files');
            
            if (fileContents.length === 0) {
                throw new Error('No supported files found. Supported languages: Python, JavaScript, TypeScript, Java, Kotlin, Scala, C, Rust, Go, C#, Swift, Ruby, PHP, Lua, R, Bash, SQL');
            }
            
            this.updateProgress('Parsing code with Universal IR...');
            
            // Analyze code structure using UIR with options
            const analysisResults = await this.analyzeCodeStructure(fileContents, {
                importMode,
                targetLanguage,
                dependencyStrategy
            });
            console.log('UIR Analysis completed:', analysisResults);
            
            // Process based on import mode
            let uirModules = analysisResults.uir_modules || [];
            let visualNodes = analysisResults.visual_nodes || [];
            let dependencyGraph = null;
            
            if (importMode === 'uir-only') {
                this.hideProgressDialog();
                // Show UIR translation panel directly
                this.showUIRTranslationPanel(uirModules, targetLanguage);
                return {
                    success: true,
                    analysisResults,
                    uirModules,
                    visualNodes: [],
                    dependencyGraph: null
                };
            }
            
            if (importMode !== 'visual-only') {
                this.updateProgress('Processing UIR modules...');
            }
            
            if (importMode === 'dependency-map') {
                this.updateProgress('Generating dependency graph...');
                dependencyGraph = await this.buildDependencyGraph(analysisResults);
                this.hideProgressDialog();
                this.showDependencyMapDialog(dependencyGraph, analysisResults);
                return {
                    success: true,
                    analysisResults,
                    uirModules,
                    visualNodes: [],
                    dependencyGraph
                };
            }
            
            this.updateProgress('Generating dependency graph...');
            dependencyGraph = await this.buildDependencyGraph(analysisResults);
            
            this.updateProgress('Creating visual representation...');
            
            // Create visual representation using UIR nodes
            await this.createUIRVisualRepresentation(visualNodes, uirModules);
            
            this.hideProgressDialog();
            
            // Show analysis results
            this.showAnalysisResults({
                filesAnalyzed: fileContents.length,
                nodesGenerated: visualNodes.length,
                uirModules: uirModules.length,
                languagesDetected: analysisResults.summary.languages_detected || [],
                totalFunctions: analysisResults.summary.total_functions || 0,
                totalClasses: analysisResults.summary.total_classes || 0,
                importMode: importMode,
                targetLanguage: targetLanguage,
                dependencyStrategy: dependencyStrategy
            }, resultsTitle);
            
            return {
                success: true,
                analysisResults,
                uirModules,
                visualNodes,
                dependencyGraph
            };
            
        } catch (error) {
            this.hideProgressDialog();
            console.error('Repository import failed:', error);
            this.showError(options.errorTitle || 'Repository Import Failed', error.message);
            return { success: false, error: error.message };
        }
    }

    /**
     * Import and analyze a single file
     */
    async importFile(file, options = {}) {
        return this.importRepository([file], {
            ...options,
            progressTitle: options.progressTitle || 'Analyzing File',
            resultsTitle: options.resultsTitle || 'File Analysis Complete',
            errorTitle: options.errorTitle || 'File Import Failed'
        });
    }
    
    /**
     * Read uploaded files
     */
    async readFiles(files, languageOverride = '') {
        const fileContents = [];
        
        for (const file of files) {
            if (this.isSupportedFile(file.name)) {
                try {
                    const content = await this.readFileContent(file);
                    const detectedType = this.getFileType(file.name);
                    fileContents.push({
                        name: file.name,
                        path: file.webkitRelativePath || file.name,
                        content: content,
                        size: file.size,
                        type: languageOverride || detectedType
                    });
                } catch (error) {
                    console.warn(`Failed to read file ${file.name}:`, error);
                }
            }
        }
        
        return fileContents;
    }
    
    /**
     * Read file content as text
     */
    readFileContent(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = (e) => reject(e);
            reader.readAsText(file);
        });
    }
    
    /**
     * Check if file is supported for analysis
     */
    isSupportedFile(filename) {
        // All 17 languages supported by UIR
        const supportedExtensions = [
            // Python
            '.py',
            // JavaScript/TypeScript
            '.js', '.mjs', '.ts', '.tsx',
            // Java/JVM languages
            '.java', '.kt', '.kts', '.scala', '.sc',
            // Systems languages
            '.c', '.h', '.rs', '.go',
            // .NET languages
            '.cs',
            // Apple ecosystem
            '.swift',
            // Scripting languages
            '.rb', '.php', '.lua', '.r',
            // Shell scripting
            '.sh', '.bash',
            // Database
            '.sql'
        ];
        return supportedExtensions.some(ext => filename.toLowerCase().endsWith(ext));
    }
    
    /**
     * Get file type from extension
     */
    getFileType(filename) {
        const ext = filename.toLowerCase().split('.').pop();
        const typeMap = {
            // Python
            'py': 'python',
            // JavaScript/TypeScript
            'js': 'javascript',
            'mjs': 'javascript',
            'ts': 'typescript',
            'tsx': 'typescript',
            // Java/JVM languages
            'java': 'java',
            'kt': 'kotlin',
            'kts': 'kotlin',
            'scala': 'scala',
            'sc': 'scala',
            // Systems languages
            'c': 'c',
            'h': 'c',
            'rs': 'rust',
            'go': 'go',
            // .NET languages
            'cs': 'csharp',
            // Apple ecosystem
            'swift': 'swift',
            // Scripting languages
            'rb': 'ruby',
            'php': 'php',
            'lua': 'lua',
            'r': 'r',
            // Shell scripting
            'sh': 'bash',
            'bash': 'bash',
            // Database
            'sql': 'sql'
        };
        return typeMap[ext] || 'unknown';
    }
    
    /**
     * Analyze code structure using backend API
     */
    async analyzeCodeStructure(fileContents, options = {}) {
        console.log('Sending files to backend for analysis:', fileContents.length);
        console.log('Analysis options:', options);
        console.log('Sample file data:', fileContents[0]);
        
        const response = await fetch('/api/repository/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                files: fileContents,
                options: {
                    importMode: options.importMode || 'full-analysis',
                    targetLanguage: options.targetLanguage || '',
                    dependencyStrategy: options.dependencyStrategy || 'preserve'
                }
            })
        });
        
        if (!response.ok) {
            throw new Error(`Analysis failed: ${response.statusText}`);
        }
        
        const result = await response.json();
        console.log('Backend analysis result:', result);
        console.log('Analysis result structure:', {
            success: result.success,
            filesCount: result.data?.files?.length,
            summaryData: result.data?.summary
        });
        
        if (!result.success) {
            throw new Error(result.error || 'Analysis failed');
        }
        
        return result.data;
    }
    
    /**
     * Build dependency graph from analysis results
     */
    async buildDependencyGraph(analysisResults) {
        const dependencyGraph = new Map();
        
        // Process each file's dependencies
        for (const fileAnalysis of analysisResults.files) {
            const filePath = fileAnalysis.path;
            const dependencies = fileAnalysis.dependencies || {};
            
            dependencyGraph.set(filePath, {
                imports: dependencies.imports || [],
                exports: dependencies.exports || [],
                functions: fileAnalysis.functions || [],
                classes: fileAnalysis.classes || [],
                variables: fileAnalysis.variables || [],
                dependsOn: [],
                dependedBy: []
            });
        }
        
        // Calculate dependency relationships
        for (const [filePath, fileData] of dependencyGraph) {
            // Find files this file depends on
            for (const importPath of fileData.imports) {
                const resolvedPath = this.resolveDependencyPath(importPath, filePath, dependencyGraph);
                if (resolvedPath && dependencyGraph.has(resolvedPath)) {
                    fileData.dependsOn.push(resolvedPath);
                    const targetFile = dependencyGraph.get(resolvedPath);
                    if (targetFile && targetFile.dependedBy) {
                        targetFile.dependedBy.push(filePath);
                    }
                }
            }
        }
        
        this.dependencyGraph = dependencyGraph;
        return dependencyGraph;
    }
    
    /**
     * Resolve dependency path
     */
    resolveDependencyPath(importPath, currentFile, dependencyGraph) {
        // Simple resolution - in practice this would be more sophisticated
        if (importPath.startsWith('./') || importPath.startsWith('../')) {
            // Relative import
            const currentDir = currentFile.split('/').slice(0, -1).join('/');
            return this.normalizePath(currentDir + '/' + importPath);
        } else {
            // Look for matching file
            for (const filePath of dependencyGraph.keys()) {
                if (filePath.includes(importPath) || filePath.endsWith(importPath + '.py')) {
                    return filePath;
                }
            }
        }
        return null;
    }
    
    /**
     * Normalize file path
     */
    normalizePath(path) {
        const parts = path.split('/');
        const normalized = [];
        
        for (const part of parts) {
            if (part === '..') {
                normalized.pop();
            } else if (part !== '.' && part !== '') {
                normalized.push(part);
            }
        }
        
        return normalized.join('/');
    }
    
    /**
     * Identify reusable code patterns
     */
    async identifyCodePatterns(analysisResults) {
        const patterns = new Map();
        
        // Common patterns to look for
        const patternTypes = [
            'factory_pattern',
            'singleton_pattern',
            'observer_pattern',
            'decorator_pattern',
            'strategy_pattern',
            'data_processing_pipeline',
            'api_endpoint',
            'database_model',
            'utility_function',
            'configuration_handler'
        ];
        
        for (const fileAnalysis of analysisResults.files) {
            const filePatterns = this.analyzeFilePatterns(fileAnalysis);
            
            for (const pattern of filePatterns) {
                const patternKey = `${pattern.type}_${pattern.name}`;
                if (!patterns.has(patternKey)) {
                    patterns.set(patternKey, {
                        type: pattern.type,
                        name: pattern.name,
                        occurrences: [],
                        complexity: pattern.complexity || 'medium',
                        reusability: pattern.reusability || 'high'
                    });
                }
                
                patterns.get(patternKey).occurrences.push({
                    file: fileAnalysis.path,
                    location: pattern.location,
                    code: pattern.code
                });
            }
        }
        
        this.codePatterns = patterns;
        return patterns;
    }
    
    /**
     * Analyze patterns in a single file
     */
    analyzeFilePatterns(fileAnalysis) {
        const patterns = [];
        
        // Analyze classes for design patterns
        for (const classInfo of fileAnalysis.classes || []) {
            // Singleton pattern detection
            if (this.isSingletonPattern(classInfo)) {
                patterns.push({
                    type: 'singleton_pattern',
                    name: classInfo.name,
                    location: classInfo.location,
                    code: classInfo.code,
                    complexity: 'medium',
                    reusability: 'high'
                });
            }
            
            // Factory pattern detection
            if (this.isFactoryPattern(classInfo)) {
                patterns.push({
                    type: 'factory_pattern',
                    name: classInfo.name,
                    location: classInfo.location,
                    code: classInfo.code,
                    complexity: 'high',
                    reusability: 'high'
                });
            }
        }
        
        // Analyze functions for utility patterns
        for (const funcInfo of fileAnalysis.functions || []) {
            // Utility function detection
            if (this.isUtilityFunction(funcInfo)) {
                patterns.push({
                    type: 'utility_function',
                    name: funcInfo.name,
                    location: funcInfo.location,
                    code: funcInfo.code,
                    complexity: 'low',
                    reusability: 'very_high'
                });
            }
            
            // Data processing pipeline detection
            if (this.isDataProcessingPipeline(funcInfo)) {
                patterns.push({
                    type: 'data_processing_pipeline',
                    name: funcInfo.name,
                    location: funcInfo.location,
                    code: funcInfo.code,
                    complexity: 'high',
                    reusability: 'medium'
                });
            }
        }
        
        return patterns;
    }
    
    /**
     * Check if class follows singleton pattern
     */
    isSingletonPattern(classInfo) {
        const code = classInfo.code || '';
        return code.includes('__new__') && 
               code.includes('_instance') && 
               (code.includes('hasattr') || code.includes('getattr'));
    }
    
    /**
     * Check if class follows factory pattern
     */
    isFactoryPattern(classInfo) {
        const code = classInfo.code || '';
        const name = classInfo.name.toLowerCase();
        return (name.includes('factory') || name.includes('builder')) ||
               (code.includes('create') && code.includes('return'));
    }
    
    /**
     * Check if function is a utility function
     */
    isUtilityFunction(funcInfo) {
        const name = funcInfo.name.toLowerCase();
        const utilityKeywords = ['helper', 'util', 'format', 'parse', 'convert', 'validate', 'sanitize'];
        return utilityKeywords.some(keyword => name.includes(keyword)) ||
               (funcInfo.parameters && funcInfo.parameters.length <= 3 && !funcInfo.hasComplexLogic);
    }
    
    /**
     * Check if function is a data processing pipeline
     */
    isDataProcessingPipeline(funcInfo) {
        const code = funcInfo.code || '';
        const pipelineKeywords = ['transform', 'process', 'filter', 'map', 'reduce', 'pipeline'];
        return pipelineKeywords.some(keyword => code.includes(keyword)) &&
               (code.includes('for ') || code.includes('map(') || code.includes('filter('));
    }
    
    /**
     * Generate visual nodes from analysis results
     */
    async generateVisualNodes(analysisResults, dependencyGraph, codePatterns) {
        console.log('Generating visual nodes from analysis results:', analysisResults);
        console.log('Dependency graph size:', dependencyGraph.size);
        console.log('Code patterns size:', codePatterns.size);
        
        const generatedNodes = [];
        
        // Generate nodes for each file
        for (const fileAnalysis of analysisResults.files) {
            console.log('Processing file:', fileAnalysis.path, 'with', 
                       (fileAnalysis.functions || []).length, 'functions,',
                       (fileAnalysis.classes || []).length, 'classes,',
                       (fileAnalysis.variables || []).length, 'variables');
            
            const fileNodes = await this.generateNodesForFile(fileAnalysis, dependencyGraph, codePatterns);
            console.log('Generated', fileNodes.length, 'nodes for file:', fileAnalysis.path);
            generatedNodes.push(...fileNodes);
        }
        
        // Generate pattern nodes
        for (const [patternKey, pattern] of codePatterns) {
            const patternNode = this.generatePatternNode(pattern);
            if (patternNode) {
                generatedNodes.push(patternNode);
            }
        }
        
        console.log('Total generated nodes:', generatedNodes.length);
        this.generatedNodes = new Map(generatedNodes.map(node => [node.id, node]));
        return generatedNodes;
    }
    
    /**
     * Generate nodes for a single file
     */
    async generateNodesForFile(fileAnalysis, dependencyGraph, codePatterns) {
        const nodes = [];
        const filePath = fileAnalysis.path;
        const fileData = dependencyGraph.get(filePath);
        
        console.log('Generating nodes for file:', filePath);
        console.log('File data from dependency graph:', fileData);
        console.log('File analysis data:', fileAnalysis);
        
        if (!fileData) {
            console.warn('No file data found in dependency graph for:', filePath);
            return nodes;
        }
        
        // Generate class nodes
        const classes = fileData.classes || fileAnalysis.classes || [];
        console.log('Processing', classes.length, 'classes for', filePath);
        for (const classInfo of classes) {
            const classNode = {
                id: `class_${filePath}_${classInfo.name}`,
                type: 'class',
                name: classInfo.name,
                category: 'Classes',
                description: `Class ${classInfo.name} from ${filePath}`,
                sourceFile: filePath,
                sourceCode: classInfo.code || '',
                inputs: this.generateClassInputs(classInfo),
                outputs: this.generateClassOutputs(classInfo),
                metadata: {
                    methods: classInfo.methods || [],
                    properties: classInfo.properties || [],
                    baseClasses: classInfo.baseClasses || [],
                    complexity: this.calculateComplexity(classInfo.code || '')
                }
            };
            nodes.push(classNode);
            console.log('Generated class node:', classNode.id);
        }
        
        // Generate function nodes
        const functions = fileData.functions || fileAnalysis.functions || [];
        console.log('Processing', functions.length, 'functions for', filePath);
        for (const funcInfo of functions) {
            const funcNode = {
                id: `function_${filePath}_${funcInfo.name}`,
                type: 'function',
                name: funcInfo.name,
                category: 'Functions',
                description: `Function ${funcInfo.name} from ${filePath}`,
                sourceFile: filePath,
                sourceCode: funcInfo.code || '',
                inputs: this.generateFunctionInputs(funcInfo),
                outputs: this.generateFunctionOutputs(funcInfo),
                metadata: {
                    parameters: funcInfo.parameters || [],
                    returnType: funcInfo.returnType,
                    isAsync: funcInfo.isAsync || false,
                    complexity: this.calculateComplexity(funcInfo.code || '')
                }
            };
            nodes.push(funcNode);
            console.log('Generated function node:', funcNode.id);
        }
        
        // Generate variable/constant nodes
        const variables = fileData.variables || fileAnalysis.variables || [];
        console.log('Processing', variables.length, 'variables for', filePath);
        for (const varInfo of variables) {
            if (varInfo.isConstant || varInfo.isGlobal) {
                const varNode = {
                    id: `variable_${filePath}_${varInfo.name}`,
                    type: 'variable',
                    name: varInfo.name,
                    category: 'Variables',
                    description: `${varInfo.isConstant ? 'Constant' : 'Variable'} ${varInfo.name} from ${filePath}`,
                    sourceFile: filePath,
                    inputs: [],
                    outputs: [{ name: 'value', type: varInfo.type || 'any' }],
                    metadata: {
                        value: varInfo.value,
                        type: varInfo.type,
                        isConstant: varInfo.isConstant,
                        isGlobal: varInfo.isGlobal
                    }
                };
                nodes.push(varNode);
                console.log('Generated variable node:', varNode.id);
            }
        }
        
        console.log('Generated', nodes.length, 'total nodes for file:', filePath);
        return nodes;
    }
    
    /**
     * Generate inputs for a class node
     */
    generateClassInputs(classInfo) {
        const inputs = [];
        
        // Constructor parameters
        if (classInfo.constructor && classInfo.constructor.parameters) {
            for (const param of classInfo.constructor.parameters) {
                inputs.push({
                    name: param.name,
                    type: param.type || 'any',
                    required: !param.hasDefault,
                    description: param.description || `Constructor parameter ${param.name}`
                });
            }
        }
        
        return inputs;
    }
    
    /**
     * Generate outputs for a class node
     */
    generateClassOutputs(classInfo) {
        return [
            {
                name: 'instance',
                type: classInfo.name,
                description: `Instance of ${classInfo.name}`
            }
        ];
    }
    
    /**
     * Generate inputs for a function node
     */
    generateFunctionInputs(funcInfo) {
        const inputs = [];
        
        if (funcInfo.parameters) {
            for (const param of funcInfo.parameters) {
                inputs.push({
                    name: param.name,
                    type: param.type || 'any',
                    required: !param.hasDefault,
                    description: param.description || `Parameter ${param.name}`
                });
            }
        }
        
        return inputs;
    }
    
    /**
     * Generate outputs for a function node
     */
    generateFunctionOutputs(funcInfo) {
        return [
            {
                name: 'result',
                type: funcInfo.returnType || 'any',
                description: `Return value of ${funcInfo.name}`
            }
        ];
    }
    
    /**
     * Generate a node for a code pattern
     */
    generatePatternNode(pattern) {
        return {
            id: `pattern_${pattern.type}_${pattern.name}`,
            type: 'pattern',
            name: pattern.name,
            category: 'Patterns',
            description: `${pattern.type.replace('_', ' ')} pattern: ${pattern.name}`,
            inputs: this.generatePatternInputs(pattern),
            outputs: this.generatePatternOutputs(pattern),
            metadata: {
                patternType: pattern.type,
                complexity: pattern.complexity,
                reusability: pattern.reusability,
                occurrences: pattern.occurrences.length,
                sourceFiles: pattern.occurrences.map(occ => occ.file)
            }
        };
    }
    
    /**
     * Generate inputs for a pattern node
     */
    generatePatternInputs(pattern) {
        const inputs = [];
        
        switch (pattern.type) {
            case 'factory_pattern':
                inputs.push({ name: 'type', type: 'string', required: true });
                inputs.push({ name: 'config', type: 'object', required: false });
                break;
            case 'singleton_pattern':
                // Singleton typically has no inputs
                break;
            case 'utility_function':
                inputs.push({ name: 'input', type: 'any', required: true });
                break;
            case 'data_processing_pipeline':
                inputs.push({ name: 'data', type: 'array', required: true });
                inputs.push({ name: 'options', type: 'object', required: false });
                break;
            default:
                inputs.push({ name: 'input', type: 'any', required: true });
        }
        
        return inputs;
    }
    
    /**
     * Generate outputs for a pattern node
     */
    generatePatternOutputs(pattern) {
        const outputs = [];
        
        switch (pattern.type) {
            case 'factory_pattern':
                outputs.push({ name: 'instance', type: 'object' });
                break;
            case 'singleton_pattern':
                outputs.push({ name: 'instance', type: 'object' });
                break;
            case 'utility_function':
                outputs.push({ name: 'result', type: 'any' });
                break;
            case 'data_processing_pipeline':
                outputs.push({ name: 'processed_data', type: 'array' });
                break;
            default:
                outputs.push({ name: 'result', type: 'any' });
        }
        
        return outputs;
    }
    
    /**
     * Calculate code complexity
     */
    calculateComplexity(code) {
        if (!code) return 'low';
        
        const lines = code.split('\n').length;
        const cyclomaticComplexity = this.calculateCyclomaticComplexity(code);
        
        if (lines > 100 || cyclomaticComplexity > 10) return 'high';
        if (lines > 50 || cyclomaticComplexity > 5) return 'medium';
        return 'low';
    }
    
    /**
     * Calculate cyclomatic complexity
     */
    calculateCyclomaticComplexity(code) {
        const complexityKeywords = ['if', 'elif', 'else', 'for', 'while', 'try', 'except', 'and', 'or'];
        let complexity = 1; // Base complexity
        
        for (const keyword of complexityKeywords) {
            const regex = new RegExp(`\\b${keyword}\\b`, 'g');
            const matches = code.match(regex);
            if (matches) {
                complexity += matches.length;
            }
        }
        
        return complexity;
    }
    
    /**
     * Create visual representation using UIR nodes
     */
    async createUIRVisualRepresentation(visualNodes, uirModules) {
        console.log('Creating UIR visual representation with', visualNodes.length, 'nodes');
        
        // Group nodes by category and language
        const nodesByCategory = new Map();
        for (const node of visualNodes) {
            const category = node.category || 'Unknown';
            if (!nodesByCategory.has(category)) {
                nodesByCategory.set(category, []);
            }
            nodesByCategory.get(category).push(node);
        }
        
        // Position nodes by category
        let categoryY = 100;
        const categorySpacing = 250;
        const nodeSpacing = 200;
        
        const uirIdToCanvasId = new Map();
        
        for (const [category, nodes] of nodesByCategory) {
            let nodeX = 100;
            
            // Add category label
            await this.createCategoryLabel(category, 50, categoryY - 30);
            
            for (const node of nodes) {
                // Create visual node on canvas
                const canvasNodeId = await this.createUIRVisualNode(node, nodeX, categoryY);
                if (canvasNodeId) {
                    if (node.metadata?.uir_function_id) {
                        uirIdToCanvasId.set(node.metadata.uir_function_id, canvasNodeId);
                    }
                    if (node.metadata?.uir_control_id) {
                        uirIdToCanvasId.set(node.metadata.uir_control_id, canvasNodeId);
                    }
                    if (node.id) {
                        uirIdToCanvasId.set(node.id, canvasNodeId);
                    }
                }
                nodeX += nodeSpacing;
                
                // Wrap to next row if too many nodes
                if (nodeX > 1400) {
                    nodeX = 100;
                    categoryY += 120;
                }
            }
            
            categoryY += categorySpacing;
        }
        
        // Create call-graph connections when dependencies are available
        await this.createUIRConnections(visualNodes, uirIdToCanvasId, {
            startX: 100,
            startY: categoryY + 60,
            maxX: 1400,
            spacingX: 220,
            spacingY: 140
        });
        
        // Show UIR translation options
        this.showUIRTranslationPanel(uirModules);
    }
    
    /**
     * Create a category label
     */
    async createCategoryLabel(category, x, y) {
        // This would create a text label on the canvas
        // For now, we'll just log it
        console.log(`Category: ${category} at (${x}, ${y})`);
    }
    
    /**
     * Create a UIR visual node on the canvas
     */
    async createUIRVisualNode(nodeDefinition, x, y) {
        try {
            const displayName = nodeDefinition.metadata?.display_as || nodeDefinition.name || nodeDefinition.metadata?.display_name || 'Unnamed';
            const sourceCode = nodeDefinition.metadata?.source_code || nodeDefinition.sourceCode || '';
            const sourceLanguage = nodeDefinition.metadata?.source_language || 'unknown';
            const functionType = nodeDefinition.metadata?.function_type || 'Function';
            const rawName = nodeDefinition.metadata?.raw_name || nodeDefinition.name;
            const payload = {
                type: nodeDefinition.type || 'function',
                position: [x, y],
                inputs: nodeDefinition.inputs || [],
                outputs: nodeDefinition.outputs || [],
                parameters: {
                    name: displayName,
                    description: nodeDefinition.description || '',
                    source_language: sourceLanguage,
                    function_type: functionType,
                    source_code: sourceCode,
                    display_as: nodeDefinition.metadata?.display_as || '',
                    uir_function_id: nodeDefinition.metadata?.uir_function_id,
                    visual_props: nodeDefinition.metadata?.visual_props || {}
                },
                metadata: {
                    ...nodeDefinition.metadata,
                    uir_node: true,
                    node_definition: nodeDefinition,
                    name: displayName,
                    display_as: nodeDefinition.metadata?.display_as || '',
                    source_code: sourceCode,
                    source_language: sourceLanguage,
                    // Add visual differentiation data
                    visual_class: this.generateVisualClass(nodeDefinition),
                    display_name: displayName
                }
            };
            
            if (nodeDefinition.type === 'function' && rawName) {
                payload.parameters.function_name = rawName;
            }
            
            const response = await fetch('/api/canvas/nodes', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });
            
            const result = await response.json();
            if (!result.success) {
                console.error('Failed to create UIR visual node:', result.error);
            } else {
                console.log('Created UIR node:', nodeDefinition.name, 'at', x, y);
                
                // Apply visual styling after node creation
                setTimeout(() => {
                    this.applyUIRNodeStyling(result.data.node_id, nodeDefinition);
                }, 100);
                
                return result.data.node_id;
            }
        } catch (error) {
            console.error('Error creating UIR visual node:', error);
        }
        return null;
    }

    async createUIRConnections(visualNodes, uirIdToCanvasId, layout) {
        const getOutputName = (nodeDef) => {
            if (nodeDef.outputs && nodeDef.outputs.length > 0) {
                return nodeDef.outputs[0].name;
            }
            return 'output';
        };
        
        const getInputName = (nodeDef) => {
            if (nodeDef.inputs && nodeDef.inputs.length > 0) {
                return nodeDef.inputs[0].name;
            }
            return 'input';
        };

        const externalNodeIds = new Map();
        let extX = layout.startX;
        let extY = layout.startY;
        
        const placeExternalNode = async (name) => {
            if (externalNodeIds.has(name)) {
                return externalNodeIds.get(name);
            }
            
            const nodeDefinition = {
                name: `[PY] ${name}`,
                type: 'custom',
                category: 'External Calls',
                description: `External call: ${name}`,
                inputs: [{ name: 'input', type: 'object', required: false }],
                outputs: [{ name: 'result', type: 'object' }],
                metadata: {
                    function_type: 'External Call',
                    source_language: 'python',
                    external_call: true
                }
            };
            
            const canvasNodeId = await this.createUIRVisualNode(nodeDefinition, extX, extY);
            if (canvasNodeId) {
                externalNodeIds.set(name, canvasNodeId);
                extX += layout.spacingX;
                if (extX > layout.maxX) {
                    extX = layout.startX;
                    extY += layout.spacingY;
                }
            }
            return canvasNodeId;
        };
        
        for (const nodeDefinition of visualNodes) {
            const dependencyIds = nodeDefinition.metadata?.dependencies || [];
            const externalCalls = nodeDefinition.metadata?.external_calls || [];
            if (!dependencyIds.length) {
                if (!externalCalls.length) {
                    continue;
                }
            }
            
            const targetCanvasId = uirIdToCanvasId.get(nodeDefinition.metadata?.uir_function_id);
            if (!targetCanvasId) {
                continue;
            }
            
            const targetInput = getInputName(nodeDefinition);
            if (!targetInput) {
                continue;
            }
            
            for (const depId of dependencyIds) {
                const sourceCanvasId = uirIdToCanvasId.get(depId);
                if (!sourceCanvasId) {
                    continue;
                }
                
                const sourceNodeDef = visualNodes.find((node) => node.metadata?.uir_function_id === depId);
                const sourceOutput = getOutputName(sourceNodeDef || {});
                if (!sourceOutput) {
                    continue;
                }
                
                try {
                    await fetch('/api/canvas/connections', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            source_node_id: sourceCanvasId,
                            source_port: sourceOutput,
                            target_node_id: targetCanvasId,
                            target_port: targetInput
                        })
                    });
                } catch (error) {
                    console.error('Failed to create UIR connection:', error);
                }
            }
            
            for (const externalCall of externalCalls) {
                const sourceCanvasId = await placeExternalNode(externalCall);
                if (!sourceCanvasId) {
                    continue;
                }
                
                try {
                    await fetch('/api/canvas/connections', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            source_node_id: sourceCanvasId,
                            source_port: 'result',
                            target_node_id: targetCanvasId,
                            target_port: targetInput
                        })
                    });
                } catch (error) {
                    console.error('Failed to create external call connection:', error);
                }
            }
        }

        await this.createControlFlowConnections(visualNodes, uirIdToCanvasId, getOutputName, getInputName);
    }

    async createControlFlowConnections(visualNodes, uirIdToCanvasId, getOutputName, getInputName) {
        const controlNodesByParent = new Map();
        
        for (const node of visualNodes) {
            const parentId = node.metadata?.parent_function_id;
            if (!parentId) continue;
            if (!controlNodesByParent.has(parentId)) {
                controlNodesByParent.set(parentId, []);
            }
            controlNodesByParent.get(parentId).push(node);
        }
        
        for (const [parentId, controlNodes] of controlNodesByParent.entries()) {
            const parentCanvasId = uirIdToCanvasId.get(parentId);
            if (!parentCanvasId) continue;
            
            const parentNodeDef = visualNodes.find((node) => node.metadata?.uir_function_id === parentId);
            const parentOutput = getOutputName(parentNodeDef || {});
            
            const sortedControls = controlNodes.sort((a, b) => {
                const orderA = a.metadata?.order ?? 0;
                const orderB = b.metadata?.order ?? 0;
                return orderA - orderB;
            });
            
            let previousCanvasId = parentCanvasId;
            let previousNodeDef = parentNodeDef || {};
            
            for (const controlNode of sortedControls) {
                const controlCanvasId = uirIdToCanvasId.get(controlNode.metadata?.uir_control_id) ||
                    uirIdToCanvasId.get(controlNode.id) ||
                    null;
                
                if (!controlCanvasId) {
                    continue;
                }
                
                const sourceOutput = previousCanvasId === parentCanvasId ? parentOutput : getOutputName(previousNodeDef);
                const targetInput = getInputName(controlNode);
                
                try {
                    await fetch('/api/canvas/connections', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            source_node_id: previousCanvasId,
                            source_port: sourceOutput,
                            target_node_id: controlCanvasId,
                            target_port: targetInput
                        })
                    });
                } catch (error) {
                    console.error('Failed to create control-flow connection:', error);
                }
                
                previousCanvasId = controlCanvasId;
                previousNodeDef = controlNode;
            }
        }
    }
    
    /**
     * Generate CSS class for visual differentiation
     */
    generateVisualClass(nodeDefinition) {
        const metadata = nodeDefinition.metadata || {};
        const classes = ['uir-node'];
        
        // Add language class
        if (metadata.source_language) {
            classes.push(`lang-${metadata.source_language}`);
        }
        
        // Add function type class
        if (metadata.function_type) {
            classes.push(`type-${metadata.function_type.toLowerCase().replace(/\s+/g, '-')}`);
        }
        
        // Add async class
        if (metadata.is_async) {
            classes.push('async-function');
        }
        
        return classes.join(' ');
    }
    
    /**
     * Apply visual styling to UIR nodes
     */
    applyUIRNodeStyling(nodeId, nodeDefinition) {
        const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);
        if (!nodeElement) return;
        
        const metadata = nodeDefinition.metadata || {};
        const visualProps = metadata.visual_props || {};
        
        // Add data attributes for CSS styling
        nodeElement.setAttribute('data-uir-node', 'true');
        nodeElement.setAttribute('data-source-language', metadata.source_language || 'unknown');
        nodeElement.setAttribute('data-function-type', metadata.function_type || 'Function');
        nodeElement.setAttribute('data-language-indicator', this.getLanguageIndicator(metadata.source_language));
        
        // Apply color styling
        if (visualProps.color) {
            const nodeBody = nodeElement.querySelector('.node-body');
            if (nodeBody) {
                nodeBody.style.borderColor = visualProps.color;
                nodeBody.style.borderWidth = '2px';
                nodeBody.style.borderStyle = visualProps.border || 'solid';
            }
        }
        
        // Apply language accent
        if (visualProps.language_accent) {
            nodeElement.style.setProperty('--language-accent', visualProps.language_accent);
        }
        
        // Update node title with enhanced display
        const titleElement = nodeElement.querySelector('.node-title');
        if (titleElement) {
            titleElement.textContent = nodeDefinition.name;
            titleElement.title = `${metadata.function_type || 'Function'} from ${metadata.source_language || 'unknown'}`;
        }
    }
    
    /**
     * Get language indicator for display
     */
    getLanguageIndicator(language) {
        const indicators = {
            'javascript': 'JS',
            'python': 'PY',
            'typescript': 'TS',
            'java': 'JAVA',
            'kotlin': 'KT',
            'scala': 'SC',
            'c': 'C',
            'rust': 'RS',
            'go': 'GO',
            'csharp': 'C#',
            'swift': 'SW',
            'ruby': 'RB',
            'php': 'PHP',
            'lua': 'LUA',
            'r': 'R',
            'bash': 'SH',
            'sql': 'SQL',
            'cpp': 'C++'
        };
        return indicators[language] || (language ? language.toUpperCase().substr(0, 2) : '??');
    }
    
    /**
     * Show dependency map dialog
     */
    showDependencyMapDialog(dependencyGraph, analysisResults) {
        const dialog = document.createElement('div');
        dialog.className = 'dependency-map-dialog';
        
        // Build dependency visualization
        const files = Array.from(dependencyGraph.keys());
        const edges = [];
        
        for (const [filePath, fileData] of dependencyGraph) {
            for (const dep of fileData.dependsOn || []) {
                edges.push({ from: filePath, to: dep });
            }
        }
        
        dialog.innerHTML = `
            <div class="dialog-content" style="max-width: 800px; max-height: 80vh; overflow-y: auto;">
                <div class="dialog-header">
                    <h3>Dependency Map</h3>
                    <button class="close-btn" onclick="this.closest('.dependency-map-dialog').remove()"><i data-lucide="x"></i></button>
                </div>
                <div class="dependency-summary">
                    <p><strong>Files analyzed:</strong> ${files.length}</p>
                    <p><strong>Dependencies found:</strong> ${edges.length}</p>
                    <p><strong>Languages:</strong> ${Array.from(analysisResults.summary?.languages_detected || []).join(', ') || 'Unknown'}</p>
                </div>
                <div class="dependency-list">
                    <h4>File Dependencies:</h4>
                    ${files.map(file => {
                        const fileData = dependencyGraph.get(file);
                        const imports = fileData?.imports || [];
                        const exports = fileData?.exports || [];
                        const dependsOn = fileData?.dependsOn || [];
                        const dependedBy = fileData?.dependedBy || [];
                        
                        return `
                            <div class="file-deps">
                                <div class="file-name">${file}</div>
                                ${imports.length > 0 ? `<div class="imports"><strong>Imports:</strong> ${imports.slice(0, 5).join(', ')}${imports.length > 5 ? '...' : ''}</div>` : ''}
                                ${dependsOn.length > 0 ? `<div class="depends-on"><strong>Depends on:</strong> ${dependsOn.join(', ')}</div>` : ''}
                                ${dependedBy.length > 0 ? `<div class="depended-by"><strong>Used by:</strong> ${dependedBy.join(', ')}</div>` : ''}
                            </div>
                        `;
                    }).join('')}
                </div>
                <div class="dialog-actions">
                    <button onclick="this.closest('.dependency-map-dialog').remove()">Close</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(dialog);
        if (typeof lucide !== 'undefined') lucide.createIcons({ root: dialog });
    }
    
    /**
     * Show UIR translation panel
     */
    showUIRTranslationPanel(uirModules, defaultTargetLanguage = '') {
        // Remove existing panel
        const existingPanel = document.getElementById('uir-translation-panel');
        if (existingPanel) {
            existingPanel.remove();
        }
        
        const allLanguages = [
            { value: 'python', label: 'Python' },
            { value: 'javascript', label: 'JavaScript' },
            { value: 'typescript', label: 'TypeScript' },
            { value: 'java', label: 'Java' },
            { value: 'kotlin', label: 'Kotlin' },
            { value: 'scala', label: 'Scala' },
            { value: 'c', label: 'C' },
            { value: 'rust', label: 'Rust' },
            { value: 'go', label: 'Go' },
            { value: 'csharp', label: 'C#' },
            { value: 'swift', label: 'Swift' },
            { value: 'ruby', label: 'Ruby' },
            { value: 'php', label: 'PHP' },
            { value: 'lua', label: 'Lua' },
            { value: 'r', label: 'R' },
            { value: 'bash', label: 'Bash' },
            { value: 'sql', label: 'SQL' }
        ];
        
        const generateLanguageOptions = (currentLang) => {
            return allLanguages.map(lang => 
                `<option value="${lang.value}" ${currentLang === lang.value ? 'disabled' : ''} ${defaultTargetLanguage === lang.value ? 'selected' : ''}>${lang.label}</option>`
            ).join('');
        };
        
        const panel = document.createElement('div');
        panel.id = 'uir-translation-panel';
        panel.className = 'uir-translation-panel';
        panel.innerHTML = `
            <div class="panel-header">
                <h3>Universal IR Translation</h3>
                <button class="close-btn" onclick="this.closest('.uir-translation-panel').remove()"><i data-lucide="x"></i></button>
            </div>
            <div class="panel-content">
                <p>Found ${uirModules.length} modules that can be translated between 17 languages:</p>
                <div class="modules-list">
                    ${uirModules.map(module => `
                        <div class="module-item" data-module-id="${module.module_id}">
                            <div class="module-info">
                                <strong>${module.file_path}</strong>
                                <span class="language-tag">${module.language}</span>
                            </div>
                            <div class="module-stats">
                                ${module.function_signatures ? module.function_signatures.length : 0} functions
                            </div>
                            <div class="translation-controls">
                                <select class="target-language">
                                    <option value="">Select target language</option>
                                    ${generateLanguageOptions(module.language)}
                                </select>
                                <button class="translate-btn" onclick="window.repositoryAnalyzer.translateModule('${module.module_id}', this)">
                                    Translate
                                </button>
                            </div>
                        </div>
                    `).join('')}
                </div>
                <div class="panel-actions">
                    <button class="import-all-btn" onclick="window.repositoryAnalyzer.importAllUIRNodes()">
                        Import All as Nodes
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(panel);
        if (typeof lucide !== 'undefined') lucide.createIcons({ root: panel });
        
        // Store reference for later use
        this.uirModules = uirModules;
    }
    
    /**
     * Translate a UIR module to another language
     */
    async translateModule(moduleId, buttonElement) {
        const moduleItem = buttonElement.closest('.module-item');
        const targetLanguageSelect = moduleItem.querySelector('.target-language');
        const targetLanguage = targetLanguageSelect.value;
        
        if (!targetLanguage) {
            alert('Please select a target language');
            return;
        }
        
        try {
            buttonElement.disabled = true;
            buttonElement.textContent = 'Translating...';
            
            const response = await fetch('/api/uir/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    module_id: moduleId,
                    target_language: targetLanguage
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Show translated code in a dialog
                this.showTranslatedCode(result.data.generated_code, targetLanguage);
            } else {
                alert('Translation failed: ' + result.error);
            }
        } catch (error) {
            console.error('Translation error:', error);
            alert('Translation failed: ' + error.message);
        } finally {
            buttonElement.disabled = false;
            buttonElement.textContent = 'Translate';
        }
    }
    
    /**
     * Show translated code in a dialog
     */
    showTranslatedCode(code, language) {
        const dialog = document.createElement('div');
        dialog.className = 'translated-code-dialog';
        dialog.innerHTML = `
            <div class="dialog-content">
                <div class="dialog-header">
                    <h3>Translated Code (${language})</h3>
                    <button class="close-btn" onclick="this.closest('.translated-code-dialog').remove()"><i data-lucide="x"></i></button>
                </div>
                <div class="code-container">
                    <pre><code class="language-${language}">${this.escapeHtml(code)}</code></pre>
                </div>
                <div class="dialog-actions">
                    <button onclick="
                        if (navigator.clipboard && navigator.clipboard.writeText) {
                            navigator.clipboard.writeText(\`${code.replace(/`/g, '\\`')}\`).then(() => {
                                this.textContent = 'Copied!';
                                setTimeout(() => this.textContent = 'Copy Code', 2000);
                            }).catch(() => {
                                // Fallback for older browsers
                                const textArea = document.createElement('textarea');
                                textArea.value = \`${code.replace(/`/g, '\\`')}\`;
                                document.body.appendChild(textArea);
                                textArea.select();
                                document.execCommand('copy');
                                document.body.removeChild(textArea);
                                this.textContent = 'Copied!';
                                setTimeout(() => this.textContent = 'Copy Code', 2000);
                            });
                        } else {
                            // Fallback for older browsers
                            const textArea = document.createElement('textarea');
                            textArea.value = \`${code.replace(/`/g, '\\`')}\`;
                            document.body.appendChild(textArea);
                            textArea.select();
                            document.execCommand('copy');
                            document.body.removeChild(textArea);
                            this.textContent = 'Copied!';
                            setTimeout(() => this.textContent = 'Copy Code', 2000);
                        }
                    ">Copy Code</button>
                    <button onclick="this.closest('.translated-code-dialog').remove()">Close</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(dialog);
        if (typeof lucide !== 'undefined') lucide.createIcons({ root: dialog });
    }
    
    /**
     * Import all UIR nodes to the canvas
     */
    async importAllUIRNodes() {
        if (!this.uirModules || this.uirModules.length === 0) {
            alert('No UIR modules available to import');
            return;
        }
        
        try {
            for (const module of this.uirModules) {
                const response = await fetch('/api/uir/nodes/import', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        module_id: module.module_id
                    })
                });
                
                const result = await response.json();
                if (!result.success) {
                    console.error('Failed to import UIR nodes for module:', module.module_id, result.error);
                }
            }
            
            alert('UIR nodes imported successfully!');
            
            // Close the translation panel
            const panel = document.getElementById('uir-translation-panel');
            if (panel) {
                panel.remove();
            }
            
        } catch (error) {
            console.error('Error importing UIR nodes:', error);
            alert('Failed to import UIR nodes: ' + error.message);
        }
    }
    
    /**
     * Escape HTML for safe display
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    /**
     * Create a visual node on the canvas
     */
    async createVisualNode(nodeDefinition, x, y) {
        try {
            const response = await fetch('/api/canvas/nodes', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    type: nodeDefinition.type,
                    position: [x, y],
                    parameters: {
                        name: nodeDefinition.name,
                        description: nodeDefinition.description,
                        sourceFile: nodeDefinition.sourceFile,
                        sourceCode: nodeDefinition.sourceCode
                    },
                    metadata: {
                        ...nodeDefinition.metadata,
                        generatedFromRepository: true,
                        originalId: nodeDefinition.id
                    }
                })
            });
            
            const result = await response.json();
            if (!result.success) {
                console.error('Failed to create visual node:', result.error);
            }
        } catch (error) {
            console.error('Error creating visual node:', error);
        }
    }
    
    /**
     * Create connections based on dependencies
     */
    async createDependencyConnections(generatedNodes) {
        // This would analyze the dependency graph and create connections
        // between nodes that depend on each other
        
        for (const [filePath, fileData] of this.dependencyGraph) {
            for (const dependency of fileData.dependsOn) {
                // Find nodes for this file and its dependency
                const sourceNodes = generatedNodes.filter(n => n.sourceFile === filePath);
                const targetNodes = generatedNodes.filter(n => n.sourceFile === dependency);
                
                // Create connections between related nodes
                for (const sourceNode of sourceNodes) {
                    for (const targetNode of targetNodes) {
                        if (this.shouldConnect(sourceNode, targetNode)) {
                            await this.createConnection(sourceNode.id, targetNode.id);
                        }
                    }
                }
            }
        }
    }
    
    /**
     * Check if two nodes should be connected
     */
    shouldConnect(sourceNode, targetNode) {
        // Simple heuristic - connect if source uses target
        if (sourceNode.sourceCode && targetNode.name) {
            return sourceNode.sourceCode.includes(targetNode.name);
        }
        return false;
    }
    
    /**
     * Create a connection between two nodes
     */
    async createConnection(sourceNodeId, targetNodeId) {
        try {
            const response = await fetch('/api/canvas/connections', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    source_node_id: sourceNodeId,
                    source_port: 'output',
                    target_node_id: targetNodeId,
                    target_port: 'input'
                })
            });
            
            const result = await response.json();
            if (!result.success) {
                console.error('Failed to create connection:', result.error);
            }
        } catch (error) {
            console.error('Error creating connection:', error);
        }
    }
    
    /**
     * Show progress dialog
     */
    showProgressDialog(title, message) {
        const dialog = document.createElement('div');
        dialog.id = 'progress-dialog';
        dialog.className = 'progress-dialog';
        dialog.innerHTML = `
            <div class="progress-content">
                <h3>${title}</h3>
                <div class="progress-bar">
                    <div class="progress-fill"></div>
                </div>
                <p id="progress-message">${message}</p>
            </div>
        `;
        document.body.appendChild(dialog);
    }
    
    /**
     * Update progress dialog
     */
    updateProgress(message) {
        const messageElement = document.getElementById('progress-message');
        if (messageElement) {
            messageElement.textContent = message;
        }
    }
    
    /**
     * Hide progress dialog
     */
    hideProgressDialog() {
        const dialog = document.getElementById('progress-dialog');
        if (dialog) {
            dialog.remove();
        }
    }
    
    /**
     * Show analysis results
     */
    showAnalysisResults(results, title = 'Repository Analysis Complete') {
        const dialog = document.createElement('div');
        dialog.className = 'analysis-results-dialog';
        dialog.innerHTML = `
            <div class="dialog-content">
                <h3>${title}</h3>
                <div class="results-grid">
                    <div class="result-item">
                        <span class="result-label">Files Analyzed:</span>
                        <span class="result-value">${results.filesAnalyzed}</span>
                    </div>
                    <div class="result-item">
                        <span class="result-label">Visual Nodes Generated:</span>
                        <span class="result-value">${results.nodesGenerated}</span>
                    </div>
                    <div class="result-item">
                        <span class="result-label">UIR Modules Created:</span>
                        <span class="result-value">${results.uirModules || 0}</span>
                    </div>
                    <div class="result-item">
                        <span class="result-label">Languages Detected:</span>
                        <span class="result-value">${(results.languagesDetected || []).join(', ') || 'None'}</span>
                    </div>
                    <div class="result-item">
                        <span class="result-label">Functions Found:</span>
                        <span class="result-value">${results.totalFunctions || 0}</span>
                    </div>
                    <div class="result-item">
                        <span class="result-label">Classes Found:</span>
                        <span class="result-value">${results.totalClasses || 0}</span>
                    </div>
                    <div class="result-item">
                        <span class="result-label">Dependency Strategy:</span>
                        <span class="result-value">${{
                            'ignore': '🚫 Ignore',
                            'preserve': '🔗 Preserve Pointers',
                            'consolidate': '📦 Consolidate',
                            'refactor_export': '⚡ Refactor & Export'
                        }[results.dependencyStrategy] || '🔗 Preserve Pointers'}</span>
                    </div>
                </div>
                <div class="uir-features">
                    <h4>Universal IR Features Available:</h4>
                    <ul>
                        <li><i data-lucide="check" style="width:12px;height:12px;display:inline;vertical-align:-1px;color:#4ade80;"></i> Cross-language function translation</li>
                        <li><i data-lucide="check" style="width:12px;height:12px;display:inline;vertical-align:-1px;color:#4ade80;"></i> Visual node generation from code</li>
                        <li><i data-lucide="check" style="width:12px;height:12px;display:inline;vertical-align:-1px;color:#4ade80;"></i> Type inference and mapping</li>
                        <li><i data-lucide="check" style="width:12px;height:12px;display:inline;vertical-align:-1px;color:#4ade80;"></i> Dependency analysis</li>
                    </ul>
                </div>
                <div class="dialog-actions">
                    <button onclick="this.closest('.analysis-results-dialog').remove()">Close</button>
                </div>
            </div>
        `;
        document.body.appendChild(dialog);
        if (typeof lucide !== 'undefined') lucide.createIcons({ root: dialog });
        
        // Auto-remove after 8 seconds (longer to read UIR info)
        setTimeout(() => {
            if (dialog.parentNode) {
                dialog.remove();
            }
        }, 8000);
    }
    
    /**
     * Show error dialog
     */
    showError(title, message) {
        const dialog = document.createElement('div');
        dialog.className = 'error-dialog';
        dialog.innerHTML = `
            <div class="dialog-content">
                <h3>${title}</h3>
                <p>${message}</p>
                <div class="dialog-actions">
                    <button onclick="this.closest('.error-dialog').remove()">Close</button>
                </div>
            </div>
        `;
        document.body.appendChild(dialog);
    }
}

// Export for use in main application
window.RepositoryAnalyzer = RepositoryAnalyzer;
