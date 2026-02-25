/**
 * Virtual Scrolling for Node Palette
 * 
 * This module implements virtual scrolling for the node palette to handle
 * large numbers of nodes efficiently by only rendering visible items.
 */

class VirtualScroller {
    constructor(container, itemHeight = 40, overscan = 3) {
        this.container = container;
        this.itemHeight = itemHeight;
        this.overscan = overscan; // Number of additional items to render before/after visible area
        
        this.items = [];
        this.visibleItems = [];
        this.renderedItems = new Map();
        this.scrollTop = 0;
        
        this.virtualContainer = null;
        this.virtualContent = null;
        
        this.initialize();
    }
    
    initialize() {
        // Create virtual scrolling DOM structure
        this.virtualContainer = document.createElement('div');
        this.virtualContainer.className = 'palette-virtual-container';
        
        this.virtualContent = document.createElement('div');
        this.virtualContent.className = 'palette-virtual-content';
        
        this.virtualContainer.appendChild(this.virtualContent);
        this.container.appendChild(this.virtualContainer);
        
        // Add scroll event listener
        this.virtualContainer.addEventListener('scroll', this.handleScroll.bind(this));
        
        // Set initial height
        this.updateHeight();
    }
    
    setItems(items) {
        this.items = items;
        this.visibleItems = [];
        this.renderedItems.clear();
        this.virtualContent.innerHTML = '';
        this.updateHeight();
        this.renderVisibleItems();
    }
    
    updateHeight() {
        const totalHeight = this.items.length * this.itemHeight;
        this.virtualContent.style.height = `${totalHeight}px`;
    }
    
    handleScroll() {
        this.scrollTop = this.virtualContainer.scrollTop;
        this.renderVisibleItems();
    }
    
    getVisibleRange() {
        const containerHeight = this.virtualContainer.clientHeight;
        const startIndex = Math.max(0, Math.floor(this.scrollTop / this.itemHeight) - this.overscan);
        const endIndex = Math.min(
            this.items.length - 1,
            Math.ceil((this.scrollTop + containerHeight) / this.itemHeight) + this.overscan
        );
        
        return { start: startIndex, end: endIndex };
    }
    
    renderVisibleItems() {
        const range = this.getVisibleRange();
        
        // Remove items that are no longer visible
        this.renderedItems.forEach((itemElement, index) => {
            if (index < range.start || index > range.end) {
                itemElement.remove();
                this.renderedItems.delete(index);
            }
        });
        
        // Render new visible items
        for (let i = range.start; i <= range.end; i++) {
            if (!this.renderedItems.has(i)) {
                this.renderItem(i);
            }
        }
        
        this.visibleItems = this.items.slice(range.start, range.end + 1);
    }
    
    renderItem(index) {
        const item = this.items[index];
        if (!item) return;
        
        const itemElement = document.createElement('div');
        itemElement.className = 'palette-virtual-item';
        itemElement.style.top = `${index * this.itemHeight}px`;
        
        // Create node element based on item type
        if (item.type === 'category') {
            itemElement.appendChild(this.createCategoryElement(item));
        } else if (item.type === 'node') {
            itemElement.appendChild(this.createNodeElement(item));
        }
        
        this.virtualContent.appendChild(itemElement);
        this.renderedItems.set(index, itemElement);
        
        // If it's a node, add drag events
        if (item.type === 'node') {
            this.addDragEvents(itemElement, item);
        }
    }
    
    createCategoryElement(categoryItem) {
        const categoryDiv = document.createElement('div');
        categoryDiv.className = 'palette-category';
        categoryDiv.dataset.category = categoryItem.category;
        
        // Category header
        const header = document.createElement('div');
        header.className = 'category-header';
        header.innerHTML = `
            <i data-lucide="chevron-down" class="category-icon"></i>
            <span class="category-name">${categoryItem.name}</span>
            <span class="category-count">(${categoryItem.nodes.length})</span>
        `;
        header.addEventListener('click', this.handleCategoryToggle.bind(this));
        
        categoryDiv.appendChild(header);
        
        return categoryDiv;
    }
    
    createNodeElement(nodeItem) {
        const nodeElement = document.createElement('div');
        nodeElement.className = 'palette-node';
        nodeElement.draggable = true;
        nodeElement.dataset.nodeType = nodeItem.type;
        nodeElement.dataset.nodeId = nodeItem.id;
        nodeElement.dataset.paradigm = nodeItem.paradigm || 'node_based';
        
        // Check if we have a custom PNG image for this node type
        const customImagePath = this.getCustomNodeImage(nodeItem.type, nodeItem);
        
        if (customImagePath) {
            // Use PNG image in palette
            nodeElement.innerHTML = `
                <div class="node-icon-container image-container">
                    <img src="${customImagePath}" class="node-image-icon" alt="${nodeItem.name}">
                </div>
                <div class="node-info">
                    <div class="node-name">${nodeItem.name}</div>
                    <div class="node-description">${nodeItem.description}</div>
                </div>
            `;
        } else {
            // Use Lucide icon
            nodeElement.innerHTML = `
                <div class="node-icon-container">
                    <i data-lucide="${nodeItem.icon}" class="node-icon"></i>
                </div>
                <div class="node-info">
                    <div class="node-name">${nodeItem.name}</div>
                    <div class="node-description">${nodeItem.description}</div>
                </div>
            `;
        }
        
        // Add paradigm-specific indicators
        if (nodeItem.paradigm && nodeItem.paradigm !== 'node_based') {
            const paradigmIndicator = document.createElement('div');
            paradigmIndicator.className = 'paradigm-indicator';
            paradigmIndicator.textContent = nodeItem.paradigm;
            nodeElement.appendChild(paradigmIndicator);
        }
        
        // Add type-specific indicators
        if (nodeItem.temporal_type) {
            const temporalIndicator = document.createElement('div');
            temporalIndicator.className = 'temporal-indicator';
            temporalIndicator.textContent = nodeItem.temporal_type;
            nodeElement.appendChild(temporalIndicator);
        }
        
        if (nodeItem.stereotype) {
            const stereotypeIndicator = document.createElement('div');
            stereotypeIndicator.className = 'stereotype-indicator';
            stereotypeIndicator.textContent = nodeItem.stereotype;
            nodeElement.appendChild(stereotypeIndicator);
        }
        
        // Add click event for additional info
        nodeElement.addEventListener('click', (e) => {
            if (e.detail === 2) { // Double click
                this.showNodeDefinitionDetails(nodeItem);
            }
        });
        
        return nodeElement;
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
    
    addDragEvents(element, item) {
        element.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('application/json', JSON.stringify(item));
            e.dataTransfer.effectAllowed = 'copy';
            element.style.opacity = '0.5';
        });
        
        element.addEventListener('dragend', (e) => {
            element.style.opacity = '1';
        });
    }
    
    handleCategoryToggle(event) {
        const header = event.target;
        const category = header.closest('.palette-category');
        const categoryName = category.dataset.category;
        
        // Collapse/expand category
        category.classList.toggle('collapsed');
        
        // Refresh visible items
        this.renderVisibleItems();
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
                    <p><strong>Paradigm:</strong> ${nodeDefinition.paradigm || 'node_based'}</p>
                    
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
    
    searchNodes(query) {
        if (!query) {
            // If no query, show all nodes
            this.renderVisibleItems();
            return;
        }
        
        const searchTerm = query.toLowerCase();
        const filteredItems = this.items.filter(item => 
            item.type === 'category' || 
            (item.type === 'node' && 
             (item.name.toLowerCase().includes(searchTerm) || 
              item.description.toLowerCase().includes(searchTerm) || 
              (item.tags && item.tags.some(tag => tag.toLowerCase().includes(searchTerm))))
        );
        
        this.setItems(filteredItems);
    }
    
    getRenderedItemCount() {
        return this.renderedItems.size;
    }
    
    getTotalItemCount() {
        return this.items.length;
    }
    
    destroy() {
        if (this.virtualContainer) {
            this.virtualContainer.removeEventListener('scroll', this.handleScroll.bind(this));
            this.virtualContainer.remove();
        }
    }
}

// Export for use in main application
window.VirtualScroller = VirtualScroller;