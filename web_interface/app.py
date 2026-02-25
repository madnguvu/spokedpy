"""
Flask web interface for the Visual Editor Core.

This provides a REST API and web interface for interacting with the visual programming system.
"""

from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from typing import Dict, Any, List
from flask_socketio import SocketIO, emit
import uuid
import json
import requests as http_requests
from datetime import datetime

# Import our visual editor components
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))   # web_interface/ for sibling modules

from visual_editor_core.canvas import Canvas
from visual_editor_core.models import VisualNode, NodeType, InputPort, OutputPort
from visual_editor_core.visual_paradigms import ParadigmManager, ParadigmType, ExtendedNodeType
from visual_editor_core.node_palette import NodePalette
from visual_editor_core.uir_translator import get_translator
from visual_editor_core.session_ledger import (
    SessionLedger, LanguageID, resolve_language_id, resolve_language_string,
    LedgerEventType, NodeSnapshot, DependencyStrategy, resolve_dependency_strategy
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'visual-editor-secret-key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global instances
canvas = Canvas(width=1920, height=1080)
paradigm_manager = ParadigmManager()
node_palette = NodePalette()
uir_translator = get_translator()

# Session Ledger - the Kafka-inspired append-only event log
# This is the single source of truth for all node lineage and transformations
session_ledger = SessionLedger()

def _detect_language_from_code(code: str) -> str:
    """Best-effort language detection from code content.
    Returns a language string or '' if indeterminate."""
    if not code or not code.strip():
        return ''
    stripped = code.strip()
    # Shebang
    if stripped.startswith('#!/bin/bash') or stripped.startswith('#!/usr/bin/env bash'):
        return 'bash'
    if stripped.startswith('#!/usr/bin/env node'):
        return 'javascript'
    if stripped.startswith('#!/usr/bin/env python'):
        return 'python'
    # Go
    if 'package main' in stripped or ('import "fmt"' in stripped) or ('import (' in stripped and 'fmt' in stripped):
        return 'go'
    # Java
    if 'public class ' in stripped or 'public static void main' in stripped:
        return 'java'
    # C#
    if 'using System;' in stripped or 'namespace ' in stripped or 'Console.Write' in stripped:
        return 'csharp'
    # TypeScript (check before JS — TS has type annotations)
    if ('type ' in stripped and ':' in stripped and '=>' in stripped) or \
       ': string' in stripped or ': number' in stripped or ': boolean' in stripped or \
       'interface ' in stripped or '<T>' in stripped:
        return 'typescript'
    # JavaScript vs Python heuristics
    js_signals = ['const ', 'let ', 'var ', 'function ', 'console.log', '=>', '===', '!==']
    py_signals = ['def ', 'import ', 'print(', 'elif ', 'self.', '__init__', 'True', 'False', 'None']
    js_count = sum(1 for s in js_signals if s in stripped)
    py_count = sum(1 for s in py_signals if s in stripped)
    if js_count > py_count and js_count >= 2:
        return 'javascript'
    if py_count > js_count and py_count >= 1:
        return 'python'
    # Rust
    if 'fn main()' in stripped and ('let mut ' in stripped or 'println!' in stripped):
        return 'rust'
    # Ruby
    if 'puts ' in stripped or 'def ' in stripped and '.each ' in stripped:
        return 'ruby'
    # Perl
    if stripped.startswith('#!/usr/bin/perl') or stripped.startswith('#!/usr/bin/env perl') or \
       ('use strict;' in stripped) or ('my $' in stripped and ';' in stripped) or \
       ('print ' in stripped and '$' in stripped and ';' in stripped):
        return 'perl'
    return ''


# Store active sessions and UIR data
sessions: Dict[str, Dict[str, Any]] = {}
uir_modules: Dict[str, Any] = {}  # Store parsed UIR modules


@app.route('/')
def index():
    """Serve the main interface."""
    return render_template('index.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files."""
    return send_from_directory('static', filename)


@app.route('/favicon.ico')
def favicon():
    """Suppress favicon 404 errors."""
    return '', 204


# Canvas API endpoints
@app.route('/api/canvas/state', methods=['GET'])
def get_canvas_state():
    """Get the current canvas state."""
    try:
        state = canvas.get_canvas_state()
        return jsonify({
            'success': True,
            'data': state
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/canvas/nodes', methods=['GET'])
def get_nodes():
    """Get all nodes on the canvas."""
    try:
        nodes_data = {}
        for node_id, node in canvas.model.nodes.items():
            nodes_data[node_id] = {
                'id': node.id,
                'type': node.type.value,
                'position': node.position,
                'parameters': node.parameters,
                'metadata': node.metadata,
                'inputs': [{'name': inp.name, 'type': inp.data_type.__name__, 'required': inp.required} for inp in node.inputs],
                'outputs': [{'name': out.name, 'type': out.data_type.__name__} for out in node.outputs]
            }
        
        return jsonify({
            'success': True,
            'data': nodes_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/canvas/nodes', methods=['POST'])
def add_node():
    """Add a new node to the canvas."""
    try:
        data = request.get_json()
        
        # Get node type - try ExtendedNodeType first, fallback to basic NodeType
        node_type_str = data.get('type', 'function')
        try:
            # Try to create ExtendedNodeType
            extended_type = ExtendedNodeType(node_type_str)
            # Map to basic NodeType for the VisualNode
            if extended_type in [ExtendedNodeType.FUNCTION, ExtendedNodeType.ASYNC_FUNCTION]:
                node_type = NodeType.FUNCTION
            elif extended_type in [ExtendedNodeType.VARIABLE, ExtendedNodeType.CONSTANT]:
                node_type = NodeType.VARIABLE
            elif extended_type in [ExtendedNodeType.IF_CONDITION, ExtendedNodeType.WHILE_LOOP, ExtendedNodeType.FOR_LOOP]:
                node_type = NodeType.CONTROL_FLOW
            elif extended_type == ExtendedNodeType.CLASS:
                node_type = NodeType.CLASS
            elif extended_type == ExtendedNodeType.DECORATOR:
                node_type = NodeType.DECORATOR
            else:
                node_type = NodeType.CUSTOM
        except ValueError:
            # Fallback to basic NodeType
            try:
                node_type = NodeType(node_type_str)
            except ValueError:
                node_type = NodeType.CUSTOM
        
        # Create node
        node = VisualNode(
            type=node_type,
            position=tuple(data.get('position', [100, 100])),
            parameters=data.get('parameters', {}),
            metadata=data.get('metadata', {})
        )
        
        # Store the extended type in metadata
        node.metadata['extended_type'] = node_type_str
        
        # Add ports from payload if provided
        inputs_payload = data.get('inputs', [])
        outputs_payload = data.get('outputs', [])
        
        if inputs_payload or outputs_payload:
            node.inputs = []
            node.outputs = []
            for inp in inputs_payload:
                name = str(inp.get('name', '')).strip()
                if not name:
                    continue
                data_type = _parse_port_type(inp.get('type'))
                node.inputs.append(InputPort(
                    name=name,
                    data_type=data_type,
                    required=bool(inp.get('required', False)),
                    description=inp.get('description', '') or ''
                ))
            for out in outputs_payload:
                name = str(out.get('name', '')).strip()
                if not name:
                    continue
                data_type = _parse_port_type(out.get('type'))
                node.outputs.append(OutputPort(
                    name=name,
                    data_type=data_type,
                    description=out.get('description', '') or ''
                ))
        else:
            # Add default ports based on extended node type
            if node_type_str in ['function', 'async_function']:
                node.inputs.append(InputPort(name='input', data_type=object))
                node.outputs.append(OutputPort(name='output', data_type=object))
            elif node_type_str in ['variable', 'constant']:
                node.outputs.append(OutputPort(name='value', data_type=object))
            elif node_type_str in ['if_condition', 'while_loop', 'for_loop']:
                node.inputs.append(InputPort(name='condition', data_type=bool))
                node.outputs.append(OutputPort(name='true', data_type=object))
                node.outputs.append(OutputPort(name='false', data_type=object))
            elif node_type_str == 'http_request':
                node.inputs.append(InputPort(name='url', data_type=str))
                node.inputs.append(InputPort(name='method', data_type=str))
                node.outputs.append(OutputPort(name='response', data_type=object))
            elif node_type_str in ['event', 'timer', 'delay']:
                node.inputs.append(InputPort(name='trigger', data_type=object))
                node.outputs.append(OutputPort(name='output', data_type=object))
            else:
                # Default ports for unknown types
                node.inputs.append(InputPort(name='input', data_type=object))
                node.outputs.append(OutputPort(name='output', data_type=object))
        
        node_id = canvas.add_node(node, node.position)
        
        # === LEDGER: Record this node creation ===
        metadata = data.get('metadata', {})
        params = data.get('parameters', {})
        source_code = (metadata.get('source_code', '') or 
                       params.get('source_code', '') or 
                       data.get('code_snippet', ''))
        raw_name = (metadata.get('raw_name', '') or 
                    params.get('function_name', '') or 
                    params.get('name', '') or 
                    data.get('name', ''))
        display_name = (params.get('name', '') or 
                        metadata.get('display_name', '') or 
                        metadata.get('name', '') or raw_name or 'node')
        source_language = (metadata.get('source_language', '') or 
                           params.get('source_language', '') or
                           _detect_language_from_code(source_code) or
                           'python')
        class_name = metadata.get('class_name', None)
        source_file = params.get('source_file', '') or metadata.get('source_file', '')
        function_type = (metadata.get('function_type', '') or 
                         params.get('function_type', ''))
        
        # Determine if this is part of an active import or a manual creation
        import_session = metadata.get('import_session_number', 0)
        
        session_ledger.record_node_imported(
            node_id=node_id,
            node_type=node_type_str,
            display_name=display_name,
            raw_name=raw_name,
            source_code=source_code,
            source_language=source_language,
            source_file=source_file,
            import_session_number=import_session,
            class_name=class_name,
            parameters=params,
            inputs=[{'name': inp.name, 'type': inp.data_type.__name__, 'required': inp.required} for inp in node.inputs],
            outputs=[{'name': out.name, 'type': out.data_type.__name__} for out in node.outputs],
            metadata={
                'function_type': function_type,
                'is_async': metadata.get('is_async', False),
                'uir_function_id': metadata.get('uir_function_id', ''),
                'visual_props': metadata.get('visual_props', {}),
            }
        )
        
        # Emit update to all connected clients
        socketio.emit('node_added', {
            'node_id': node_id,
            'node': {
                'id': node.id,
                'type': node_type_str,  # Use the extended type string
                'position': node.position,
                'parameters': node.parameters,
                'metadata': node.metadata,
                'inputs': [{'name': inp.name, 'type': inp.data_type.__name__, 'required': inp.required} for inp in node.inputs],
                'outputs': [{'name': out.name, 'type': out.data_type.__name__} for out in node.outputs]
            }
        })
        
        return jsonify({
            'success': True,
            'data': {'node_id': node_id}
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/canvas/nodes/<node_id>', methods=['DELETE'])
def remove_node(node_id):
    """Remove a node from the canvas."""
    try:
        success = canvas.remove_node(node_id)
        
        if success:
            # === LEDGER: Record deletion ===
            session_ledger.record_node_deleted(node_id)
            
            # Emit update to all connected clients
            socketio.emit('node_removed', {'node_id': node_id})
        
        return jsonify({
            'success': success,
            'data': {'removed': success}
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/canvas/nodes/<node_id>/move', methods=['POST'])
def move_node(node_id):
    """Move a node to a new position."""
    try:
        data = request.get_json()
        position = tuple(data.get('position', [0, 0]))
        
        success = canvas.move_node(node_id, position)
        
        if success:
            # === LEDGER: Record move ===
            session_ledger.record_node_moved(node_id, (position[0], position[1]))
            
            # Emit update to all connected clients
            socketio.emit('node_moved', {
                'node_id': node_id,
                'position': position
            })
        
        return jsonify({
            'success': success,
            'data': {'moved': success}
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/canvas/connections', methods=['GET'])
def get_connections():
    """Get all connections on the canvas."""
    try:
        connections_data = []
        for conn in canvas.model.connections:
            connections_data.append({
                'id': conn.id,
                'source_node_id': conn.source_node_id,
                'source_port': conn.source_port,
                'target_node_id': conn.target_node_id,
                'target_port': conn.target_port,
                'data_type': conn.data_type.__name__ if conn.data_type else 'None'
            })
        
        return jsonify({
            'success': True,
            'data': connections_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/canvas/connections', methods=['POST'])
def add_connection():
    """Add a new connection between nodes."""
    try:
        data = request.get_json()
        
        connection = canvas.model.connect_nodes(
            data['source_node_id'],
            data['source_port'],
            data['target_node_id'],
            data['target_port']
        )
        
        if connection:
            # === LEDGER: Record connection ===
            session_ledger.record_connection_created(
                connection.id,
                connection.source_node_id, connection.source_port,
                connection.target_node_id, connection.target_port
            )
            
            # Emit update to all connected clients
            socketio.emit('connection_added', {
                'connection': {
                    'id': connection.id,
                    'source_node_id': connection.source_node_id,
                    'source_port': connection.source_port,
                    'target_node_id': connection.target_node_id,
                    'target_port': connection.target_port,
                    'data_type': connection.data_type.__name__ if connection.data_type else 'None'
                }
            })
        
        return jsonify({
            'success': connection is not None,
            'data': {'connection_id': connection.id if connection else None}
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/canvas/connections/<connection_id>', methods=['DELETE'])
def remove_connection(connection_id):
    """Remove a connection from the canvas."""
    try:
        success = canvas.remove_connection(connection_id)
        
        if success:
            # === LEDGER: Record connection deletion ===
            session_ledger.record_connection_deleted(connection_id)
            
            # Emit update to all connected clients
            socketio.emit('connection_removed', {'connection_id': connection_id})
        
        return jsonify({
            'success': success,
            'data': {'removed': success}
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Viewport API endpoints
@app.route('/api/canvas/viewport', methods=['GET'])
def get_viewport():
    """Get the current viewport state."""
    try:
        viewport = {
            'zoom': canvas.viewport.zoom,
            'pan_x': canvas.viewport.pan_x,
            'pan_y': canvas.viewport.pan_y,
            'width': canvas.viewport.width,
            'height': canvas.viewport.height
        }
        
        return jsonify({
            'success': True,
            'data': viewport
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/canvas/viewport/zoom', methods=['POST'])
def set_zoom():
    """Set the viewport zoom level."""
    try:
        data = request.get_json()
        zoom = data.get('zoom', 1.0)
        center_x = data.get('center_x', 0.0)
        center_y = data.get('center_y', 0.0)
        
        canvas.set_zoom(zoom, center_x, center_y)
        
        # Emit update to all connected clients
        socketio.emit('viewport_changed', {
            'zoom': canvas.viewport.zoom,
            'pan_x': canvas.viewport.pan_x,
            'pan_y': canvas.viewport.pan_y
        })
        
        return jsonify({
            'success': True,
            'data': {
                'zoom': canvas.viewport.zoom,
                'pan_x': canvas.viewport.pan_x,
                'pan_y': canvas.viewport.pan_y
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/canvas/viewport/pan', methods=['POST'])
def pan_viewport():
    """Pan the viewport."""
    try:
        data = request.get_json()
        delta_x = data.get('delta_x', 0.0)
        delta_y = data.get('delta_y', 0.0)
        
        canvas.pan_viewport(delta_x, delta_y)
        
        # Emit update to all connected clients
        socketio.emit('viewport_changed', {
            'zoom': canvas.viewport.zoom,
            'pan_x': canvas.viewport.pan_x,
            'pan_y': canvas.viewport.pan_y
        })
        
        return jsonify({
            'success': True,
            'data': {
                'pan_x': canvas.viewport.pan_x,
                'pan_y': canvas.viewport.pan_y
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Node Palette API endpoints
@app.route('/api/palette/nodes', methods=['GET'])
def get_palette_nodes():
    """Get available nodes from the palette."""
    try:
        paradigm_type_param = request.args.get('paradigm', 'all')
        
        # Get all nodes across paradigms by default
        if paradigm_type_param == 'all':
            all_elements = paradigm_manager.node_factory.get_all_element_types()
            node_definitions = []
            for element_def in all_elements:
                paradigm = element_def.get('paradigm', 'node_based')
                node_def = {
                    'id': f"{paradigm}_{element_def['type']}",
                    'name': element_def['name'],
                    'type': element_def['type'],
                    'category': element_def['category'],
                    'description': element_def['description'],
                    'icon': element_def['icon'],
                    'paradigm': paradigm,
                    'inputs': element_def.get('inputs', []),
                    'outputs': element_def.get('outputs', [])
                }
                if 'image' in element_def:
                    node_def['image'] = element_def['image']
                node_definitions.append(node_def)
            
            return jsonify({
                'success': True,
                'data': node_definitions
            })
        
        paradigm_type = ParadigmType(paradigm_type_param)
        
        # Get element definitions from NodeFactory
        element_types = paradigm_manager.get_available_element_types(paradigm_type)
        
        # Convert to the expected format for the frontend
        node_definitions = []
        for element_def in element_types:
            node_def = {
                'id': f"{paradigm_type.value}_{element_def['type']}",
                'name': element_def['name'],
                'type': element_def['type'],
                'category': element_def['category'],
                'description': element_def['description'],
                'icon': element_def['icon'],
                'paradigm': paradigm_type.value
            }
            
            # Add image path if available
            if 'image' in element_def:
                node_def['image'] = element_def['image']
            
            # Add paradigm-specific properties
            if paradigm_type == ParadigmType.NODE_BASED:
                node_def.update({
                    'inputs': element_def.get('inputs', []),
                    'outputs': element_def.get('outputs', [])
                })
            elif paradigm_type == ParadigmType.BLOCK_BASED:
                node_def.update({
                    'shape': element_def.get('shape', 'rect'),
                    'color': element_def.get('color', '#D3D3D3')
                })
            elif paradigm_type == ParadigmType.DIAGRAM_BASED:
                node_def.update({
                    'stereotype': element_def.get('stereotype'),
                    'notation': element_def.get('notation', 'UML')
                })
            elif paradigm_type == ParadigmType.TIMELINE_BASED:
                node_def.update({
                    'temporal_type': element_def.get('temporal_type', 'generic')
                })
            
            node_definitions.append(node_def)
        
        return jsonify({
            'success': True,
            'data': node_definitions
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Library Node Generation API endpoints
@app.route('/api/library/generate', methods=['POST'])
def generate_library_nodes():
    """Generate nodes from a Python library or module."""
    try:
        data = request.get_json()
        source_type = data.get('source_type', 'module')  # 'module', 'file', 'pip'
        source = data.get('source', '')  # module name, file path, or package name
        
        if not source:
            return jsonify({
                'success': False,
                'error': 'Source is required'
            }), 400
        
        from visual_editor_core.library_node_generator import LibraryNodeGenerator
        generator = LibraryNodeGenerator()
        
        if source_type == 'module':
            # Generate from installed module
            nodes = generator.generate_nodes_from_module(source)
            result = {
                'success': True,
                'module': source,
                'nodes': generator.to_palette_format(nodes)
            }
        elif source_type == 'file':
            # Generate from file path
            nodes = generator.generate_nodes_from_source_file(source)
            result = {
                'success': True,
                'module': source,
                'nodes': generator.to_palette_format(nodes)
            }
        elif source_type == 'pip':
            # Install via pip and generate
            success, message = generator.install_package(source)
            if success:
                nodes = generator.generate_nodes_from_module(source)
                result = {
                    'success': True,
                    'module': source,
                    'nodes': generator.to_palette_format(nodes),
                    'message': message
                }
            else:
                result = {
                    'success': False,
                    'error': message
                }
        else:
            return jsonify({
                'success': False,
                'error': f'Unknown source_type: {source_type}'
            }), 400
        
        if result['success']:
            # Convert generated nodes to palette format
            generated_nodes = []
            for node_def in result.get('nodes', []):
                generated_nodes.append({
                    'id': f"lib_{node_def['type']}",
                    'name': node_def['name'],
                    'type': node_def['type'],
                    'category': node_def['category'],
                    'description': node_def['description'],
                    'icon': node_def.get('icon', '📦'),
                    'paradigm': 'node_based',
                    'inputs': node_def.get('inputs', []),
                    'outputs': node_def.get('outputs', []),
                    'library': result.get('module', source),
                    'generated': True
                })
            
            return jsonify({
                'success': True,
                'data': {
                    'module': result.get('module', source),
                    'nodes': generated_nodes,
                    'count': len(generated_nodes)
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error during generation')
            }), 400
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/library/installed', methods=['GET'])
def get_installed_libraries():
    """Get list of installed Python libraries that can be used for node generation."""
    try:
        from visual_editor_core.library_node_generator import LibraryNodeGenerator
        generator = LibraryNodeGenerator()
        libraries = generator.get_installed_packages()
        
        return jsonify({
            'success': True,
            'data': libraries
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/library/pip/install', methods=['POST'])
def pip_install_library():
    """Install a library via pip and optionally generate nodes."""
    try:
        data = request.get_json()
        package_name = data.get('package', '')
        generate_nodes = data.get('generate_nodes', True)
        
        if not package_name:
            return jsonify({
                'success': False,
                'error': 'Package name is required'
            }), 400
        
        from visual_editor_core.library_node_generator import LibraryNodeGenerator
        generator = LibraryNodeGenerator()
        
        # Install the package
        success, message = generator.install_package(package_name)
        
        if not success:
            return jsonify({
                'success': False,
                'error': message
            }), 400
        
        result = {
            'success': True,
            'data': {
                'package': package_name,
                'installed': True,
                'message': message
            }
        }
        
        if generate_nodes:
            # Try to generate nodes from the installed package
            try:
                nodes = generator.generate_nodes_from_module(package_name)
                result['data']['nodes'] = generator.to_palette_format(nodes)
                result['data']['nodes_generated'] = len(nodes)
            except Exception as gen_error:
                result['data']['generation_error'] = str(gen_error)
                result['data']['nodes'] = []
                result['data']['nodes_generated'] = 0
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# AST-Grep Pattern Search & Refactoring API
# ============================================

@app.route('/api/ast-grep/search', methods=['POST'])
def ast_grep_search():
    """Search for a pattern across all nodes' source code."""
    try:
        data = request.get_json()
        pattern = data.get('pattern', '')
        language = data.get('language', 'python')
        browser_nodes = data.get('nodes_data', None)  # Nodes from browser
        
        # Debug: Log what we received from browser
        print(f"[AST-GREP DEBUG] Received pattern: '{pattern}'")
        print(f"[AST-GREP DEBUG] Browser nodes received: {len(browser_nodes) if browser_nodes else 0}")
        if browser_nodes:
            first_key = list(browser_nodes.keys())[0]
            first_node = browser_nodes[first_key]
            print(f"[AST-GREP DEBUG] First node ID: {first_key}")
            print(f"[AST-GREP DEBUG] First node keys: {list(first_node.keys())}")
            params = first_node.get('parameters', {})
            print(f"[AST-GREP DEBUG] First node parameters keys: {list(params.keys())}")
            if 'source_code' in params:
                source = params['source_code']
                print(f"[AST-GREP DEBUG] First node source_code length: {len(source) if source else 0}")
                print(f"[AST-GREP DEBUG] First node source_code preview: {source[:100] if source else 'None'}...")
        
        if not pattern:
            return jsonify({
                'success': False,
                'error': 'Pattern is required'
            }), 400
        
        from visual_editor_core.ast_grep_integration import get_ast_grep_integration
        ast_grep = get_ast_grep_integration()
        
        # Use browser-provided nodes if available, otherwise fall back to server canvas
        if browser_nodes and len(browser_nodes) > 0:
            # Process browser nodes - extract source code from parameters
            nodes_data = {}
            for node_id, node_info in browser_nodes.items():
                node_dict = {
                    'id': node_id,
                    'name': node_info.get('name', node_id),
                    'type': node_info.get('type', 'unknown'),
                    'parameters': node_info.get('parameters', {}),
                    'metadata': node_info.get('metadata', {})
                }
                # Extract source code from parameters
                params = node_info.get('parameters', {})
                source_parts = []
                code_fields = ['source_code', 'code', 'body', 'expression', 'value', 'content']
                for field in code_fields:
                    if field in params:
                        val = params[field]
                        if isinstance(val, str) and val.strip():
                            source_parts.append(val)
                
                if source_parts:
                    node_dict['source_code'] = '\n'.join(source_parts)
                
                nodes_data[node_id] = node_dict
            
            # Debug: Log how many nodes have source_code after processing
            nodes_with_code = sum(1 for n in nodes_data.values() if n.get('source_code'))
            print(f"[AST-GREP DEBUG] Processed {len(nodes_data)} nodes, {nodes_with_code} have source_code")
            if nodes_with_code > 0:
                # Show first node with code
                for nid, ndata in nodes_data.items():
                    if ndata.get('source_code'):
                        print(f"[AST-GREP DEBUG] Example node with code: {nid}")
                        print(f"[AST-GREP DEBUG] Source code: {ndata['source_code'][:200]}...")
                        break
        else:
            # Fall back to server-side canvas nodes
            nodes_data = {}
            for node_id, node in canvas.model.nodes.items():
                node_dict = {
                    'id': node.id,
                    'name': getattr(node, 'name', node.id),
                    'type': node.type.value if hasattr(node.type, 'value') else str(node.type),
                    'parameters': node.parameters,
                    'metadata': node.metadata
                }
                source_parts = []
                code_fields = ['source_code', 'code', 'body', 'expression', 'value', 'content']
                for field in code_fields:
                    if field in node.parameters:
                        val = node.parameters[field]
                        if isinstance(val, str) and val.strip():
                            source_parts.append(val)
                
                if source_parts:
                    node_dict['source_code'] = '\n'.join(source_parts)
                
                nodes_data[node_id] = node_dict
        
        # Search for pattern
        matches = ast_grep.search_pattern(pattern, nodes_data, language)
        
        # Debug: Log search results
        print(f"[AST-GREP DEBUG] Pattern search completed. Found {len(matches)} matches")

        # Format results
        results = []
        for match in matches:
            results.append({
                'node_id': match.node_id,
                'node_name': match.node_name,
                'node_type': match.node_type,
                'match_text': match.match_text,
                'start_line': match.start_line,
                'end_line': match.end_line,
                'captured_vars': match.captured_vars
            })
        
        return jsonify({
            'success': True,
            'data': {
                'pattern': pattern,
                'matches': results,
                'count': len(results),
                'matched_node_ids': ast_grep.get_matched_node_ids(),
                'tag_style': ast_grep.get_tag_style()
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ast-grep/refactor', methods=['POST'])
def ast_grep_refactor():
    """Apply a refactoring transformation to matching nodes."""
    try:
        data = request.get_json()
        search_pattern = data.get('search_pattern', '')
        replace_pattern = data.get('replace_pattern', '')
        language = data.get('language', 'python')
        node_ids = data.get('node_ids', None)  # Optional: specific nodes to refactor
        apply = data.get('apply', False)  # Whether to actually apply changes
        
        if not search_pattern or not replace_pattern:
            return jsonify({
                'success': False,
                'error': 'Both search_pattern and replace_pattern are required'
            }), 400
        
        from visual_editor_core.ast_grep_integration import get_ast_grep_integration
        ast_grep = get_ast_grep_integration()
        
        # Get nodes data
        nodes_data = {}
        for node_id, node in canvas.model.nodes.items():
            node_dict = {
                'id': node.id,
                'name': getattr(node, 'name', node.id),
                'type': node.type.value if hasattr(node.type, 'value') else str(node.type),
                'parameters': node.parameters,
                'metadata': node.metadata
            }
            if 'source_code' in node.parameters:
                node_dict['source_code'] = node.parameters['source_code']
            elif 'code' in node.parameters:
                node_dict['source_code'] = node.parameters['code']
            elif 'body' in node.parameters:
                node_dict['source_code'] = node.parameters['body']
            nodes_data[node_id] = node_dict
        
        # Apply refactoring
        results = ast_grep.refactor_pattern(
            search_pattern, replace_pattern, nodes_data, language, node_ids
        )
        
        # Format results
        refactor_results = []
        for result in results:
            refactor_results.append({
                'node_id': result.node_id,
                'original_code': result.original_code,
                'refactored_code': result.refactored_code,
                'success': result.success,
                'error': result.error,
                'changed': result.original_code != result.refactored_code
            })
        
        # If apply=True, update the nodes
        if apply:
            for result in results:
                if result.success and result.original_code != result.refactored_code:
                    node = canvas.model.nodes.get(result.node_id)
                    if node:
                        # Update the source code in the node
                        if 'source_code' in node.parameters:
                            node.parameters['source_code'] = result.refactored_code
                        elif 'code' in node.parameters:
                            node.parameters['code'] = result.refactored_code
                        elif 'body' in node.parameters:
                            node.parameters['body'] = result.refactored_code
                        
                        # === LEDGER: Record the refactored code edit ===
                        session_ledger.record_code_edit(
                            result.node_id, result.refactored_code,
                            reason='ast_grep_refactor'
                        )
                        
                        # Emit update event
                        socketio.emit('node_updated', {
                            'node_id': result.node_id,
                            'changes': {'source_code': result.refactored_code}
                        })
        
        return jsonify({
            'success': True,
            'data': {
                'search_pattern': search_pattern,
                'replace_pattern': replace_pattern,
                'results': refactor_results,
                'total_changed': sum(1 for r in refactor_results if r['changed']),
                'applied': apply
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ast-grep/patterns', methods=['GET'])
def get_ast_grep_patterns():
    """Get list of common search patterns."""
    try:
        from visual_editor_core.ast_grep_integration import get_ast_grep_integration
        ast_grep = get_ast_grep_integration()
        
        return jsonify({
            'success': True,
            'data': {
                'search_patterns': ast_grep.get_common_patterns(),
                'refactoring_patterns': ast_grep.get_common_refactorings(),
                'ast_grep_available': ast_grep.ast_grep_available
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ast-grep/clear', methods=['POST'])
def clear_ast_grep_matches():
    """Clear all current pattern matches."""
    try:
        from visual_editor_core.ast_grep_integration import get_ast_grep_integration
        ast_grep = get_ast_grep_integration()
        ast_grep.clear_matches()
        
        # Emit event to clear visual tags on frontend
        socketio.emit('ast_grep_matches_cleared')
        
        return jsonify({
            'success': True,
            'message': 'Matches cleared'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/palette/categories', methods=['GET'])
def get_palette_categories():
    """Get available categories for the current paradigm."""
    try:
        paradigm_type_param = request.args.get('paradigm', 'node_based')
        paradigm_type = ParadigmType(paradigm_type_param)
        
        element_types = paradigm_manager.get_available_element_types(paradigm_type)
        
        # Group by category
        categories = {}
        for element_def in element_types:
            category = element_def['category']
            if category not in categories:
                categories[category] = {
                    'name': category,
                    'elements': [],
                    'count': 0
                }
            categories[category]['elements'].append(element_def)
            categories[category]['count'] += 1
        
        return jsonify({
            'success': True,
            'data': {
                'paradigm': paradigm_type.value,
                'categories': list(categories.values())
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Paradigm API endpoints
@app.route('/api/paradigms', methods=['GET'])
def get_paradigms():
    """Get available visual paradigms."""
    try:
        paradigms = []
        for paradigm_type in ParadigmType:
            paradigm = paradigm_manager.get_paradigm(paradigm_type)
            if paradigm:
                paradigms.append({
                    'type': paradigm_type.value,
                    'name': paradigm_type.value.replace('_', ' ').title(),
                    'properties': paradigm.properties,
                    'active': paradigm_type == paradigm_manager.active_paradigm
                })
        
        return jsonify({
            'success': True,
            'data': paradigms
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/paradigms/<paradigm_type>/elements', methods=['GET'])
def get_paradigm_elements(paradigm_type):
    """Get available elements for a specific paradigm."""
    try:
        paradigm_enum = ParadigmType(paradigm_type)
        element_types = paradigm_manager.get_available_element_types(paradigm_enum)
        
        return jsonify({
            'success': True,
            'data': {
                'paradigm_type': paradigm_type,
                'elements': element_types
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/paradigms/<paradigm_type>/elements/<element_type>', methods=['POST'])
def create_paradigm_element(paradigm_type, element_type):
    """Create an element in a specific paradigm."""
    try:
        data = request.get_json()
        position = tuple(data.get('position', [100, 100]))
        
        paradigm_enum = ParadigmType(paradigm_type)
        element_id = paradigm_manager.create_element_in_paradigm(
            paradigm_enum, element_type, position, **data.get('properties', {})
        )
        
        if element_id:
            # Convert to visual model and add to canvas
            paradigm = paradigm_manager.get_paradigm(paradigm_enum)
            if paradigm:
                visual_model = paradigm.to_visual_model()
                
                # Find the newly created element
                if element_id in visual_model.nodes:
                    node = visual_model.nodes[element_id]
                    canvas_node_id = canvas.add_node(node, node.position)
                    
                    # Emit update to all connected clients
                    socketio.emit('node_added', {
                        'node_id': canvas_node_id,
                        'node': {
                            'id': node.id,
                            'type': node.type.value,
                            'position': node.position,
                            'parameters': node.parameters,
                            'metadata': node.metadata,
                            'inputs': [{'name': inp.name, 'type': inp.data_type.__name__, 'required': inp.required} for inp in node.inputs],
                            'outputs': [{'name': out.name, 'type': out.data_type.__name__} for out in node.outputs]
                        }
                    })
        
        return jsonify({
            'success': element_id is not None,
            'data': {'element_id': element_id}
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/paradigms/active', methods=['POST'])
def set_active_paradigm():
    """Set the active visual paradigm."""
    try:
        data = request.get_json()
        paradigm_type = ParadigmType(data.get('type'))
        
        success = paradigm_manager.set_active_paradigm(paradigm_type)
        
        if success:
            # Emit update to all connected clients
            socketio.emit('paradigm_changed', {'type': paradigm_type.value})
        
        return jsonify({
            'success': success,
            'data': {'active_paradigm': paradigm_type.value if success else None}
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/paradigms/capabilities', methods=['GET'])
def get_paradigm_capabilities():
    """Get capabilities of all paradigms."""
    try:
        capabilities = {}
        for paradigm_type in ParadigmType:
            capabilities[paradigm_type.value] = paradigm_manager.get_paradigm_capabilities(paradigm_type)
        
        return jsonify({
            'success': True,
            'data': capabilities
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/paradigms/convert', methods=['POST'])
def convert_paradigms():
    """Convert between different paradigms."""
    try:
        data = request.get_json()
        source_type = ParadigmType(data.get('source_type'))
        target_type = ParadigmType(data.get('target_type'))
        
        success = paradigm_manager.convert_between_paradigms(source_type, target_type)
        
        if success:
            # Emit update to all connected clients
            socketio.emit('paradigm_converted', {
                'source_type': source_type.value,
                'target_type': target_type.value
            })
        
        return jsonify({
            'success': success,
            'data': {
                'converted': success,
                'source_type': source_type.value,
                'target_type': target_type.value
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Model validation and execution
@app.route('/api/canvas/validate', methods=['POST'])
def validate_model():
    """Validate the current visual model."""
    try:
        # Get all nodes in the model
        node_count = len(canvas.model.nodes)
        connection_count = len(canvas.model.connections)
        
        # If no nodes, return as valid (empty canvas is valid)
        if node_count == 0:
            return jsonify({
                'success': True,
                'data': {
                    'valid': True,
                    'errors': [],
                    'warnings': ['Canvas is empty - no nodes to validate'],
                    'node_count': 0,
                    'connection_count': 0
                }
            })
        
        errors = canvas.validate_model()
        
        # Collect warnings separately from errors
        warnings = []
        critical_errors = []
        
        for error in errors:
            error_str = str(error)
            # Classify errors
            if 'missing source node' in error_str.lower() or 'missing target node' in error_str.lower():
                # These might be stale connections - treat as warnings
                warnings.append(error_str)
            elif 'circular dependencies' in error_str.lower():
                warnings.append(error_str)  # Cycles are often intentional in data flow
            else:
                critical_errors.append(error_str)
        
        # Node-specific validation results
        node_results = []
        for node_id, node in canvas.model.nodes.items():
            node_errors = node.validate()
            node_results.append({
                'node_id': node_id,
                'node_name': node.name or node.parameters.get('name', node_id[:8]),
                'node_type': node.type.value if hasattr(node.type, 'value') else str(node.type),
                'valid': len(node_errors) == 0,
                'errors': [str(e) for e in node_errors]
            })
        
        return jsonify({
            'success': True,
            'data': {
                'valid': len(critical_errors) == 0,
                'errors': critical_errors,
                'warnings': warnings,
                'node_count': node_count,
                'connection_count': connection_count,
                'node_results': node_results
            }
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/canvas/clear', methods=['POST'])
def clear_canvas():
    """Clear all nodes and connections from the canvas."""
    try:
        # Clear the model
        canvas.model.nodes.clear()
        canvas.model.connections.clear()
        canvas.clear_selection()
        
        # Also reset the session ledger so stale nodes don't duplicate on re-import
        session_ledger.clear()
        
        # Emit update to all connected clients
        socketio.emit('canvas_cleared')
        
        return jsonify({
            'success': True,
            'data': {'cleared': True}
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Helper functions for repository analysis


@app.route('/api/repository/upload', methods=['POST'])
def upload_repository():
    """Handle repository file uploads."""
    try:
        if 'files' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No files uploaded'
            }), 400
        
        files = request.files.getlist('files')
        uploaded_files = []
        
        for file in files:
            if file.filename:
                # Read file content
                content = file.read().decode('utf-8', errors='ignore')
                
                uploaded_files.append({
                    'name': file.filename,
                    'content': content,
                    'size': len(content),
                    'type': get_file_type_from_extension(file.filename)
                })
        
        return jsonify({
            'success': True,
            'data': {
                'files': uploaded_files,
                'count': len(uploaded_files)
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def get_file_type_from_extension(filename):
    """Get file type from extension for all 17 supported languages."""
    ext = filename.lower().split('.')[-1]
    type_map = {
        # Python
        'py': 'python',
        # JavaScript/TypeScript
        'js': 'javascript',
        'mjs': 'javascript',
        'ts': 'typescript',
        'tsx': 'typescript',
        # Java/JVM languages
        'java': 'java',
        'kt': 'kotlin',
        'kts': 'kotlin',
        'scala': 'scala',
        'sc': 'scala',
        # Systems languages
        'c': 'c',
        'h': 'c',
        'rs': 'rust',
        'go': 'go',
        # .NET languages
        'cs': 'csharp',
        # Apple ecosystem
        'swift': 'swift',
        # Scripting languages
        'rb': 'ruby',
        'php': 'php',
        'lua': 'lua',
        'r': 'r',
        # Shell scripting
        'sh': 'bash',
        'bash': 'bash',
        # Perl
        'pl': 'perl',
        'pm': 'perl',
        # Database
        'sql': 'sql'
    }
    return type_map.get(ext, 'unknown')


# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    session_id = str(uuid.uuid4())
    # Flask-SocketIO adds 'sid' attribute to Flask's request object during Socket.IO events
    sid = request.sid  # type: ignore[attr-defined]
    sessions[sid] = {'session_id': session_id}
    emit('connected', {'session_id': session_id})
    print(f"Client connected: {sid}")


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    sid = request.sid  # type: ignore[attr-defined]
    if sid in sessions:
        del sessions[sid]
    print(f"Client disconnected: {sid}")


@socketio.on('canvas_update')
def handle_canvas_update(data):
    """Handle canvas updates from clients."""
    try:
        # Broadcast update to all other clients
        emit('canvas_update', data, broadcast=True, include_self=False)
    except Exception as e:
        emit('error', {'message': str(e)})


# Universal IR Translation API endpoints
@app.route('/api/uir/translate', methods=['POST'])
def translate_code():
    """Translate code between languages using UIR."""
    try:
        data = request.get_json()

        source_code = data.get('source_code', '')
        source_language = data.get('source_language', '')
        target_language = data.get('target_language', '')
        filename = data.get('filename', None)

        if not source_code or not source_language or not target_language:
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: source_code, source_language, target_language'
            }), 400

        # Perform translation
        translated_code, uir_module = uir_translator.translate_code(
            source_code, source_language, target_language, filename
        )

        # Store UIR module for potential reuse
        module_id = str(uuid.uuid4())
        uir_modules[module_id] = uir_module

        # Get function signatures for visual representation
        function_signatures = uir_translator.get_function_signatures(uir_module)

        return jsonify({
            'success': True,
            'data': {
                'translated_code': translated_code,
                'module_id': module_id,
                'source_language': source_language,
                'target_language': target_language,
                'function_signatures': function_signatures,
                'module_info': {
                    'name': uir_module.name,
                    'function_count': len(uir_module.functions),
                    'class_count': len(uir_module.classes),
                    'variable_count': len(uir_module.variables)
                }
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Live Execution API endpoints
@app.route('/api/execution/start', methods=['POST'])
def start_execution():
    """Start live execution of the current canvas model."""
    try:
        data = request.get_json()
        execution_mode = data.get('mode', 'normal')  # normal, debug, step

        # Get current canvas model
        model = canvas.model

        # Validate model
        validation_errors = model.validate_model()
        if validation_errors:
            return jsonify({
                'success': False,
                'error': f'Model validation failed: {"; ".join(str(e) for e in validation_errors)}'
            }), 400

        # Initialize execution engine
        from visual_editor_core.execution_engine import ExecutionEngine
        from visual_editor_core.execution_visualizer import ExecutionVisualizer

        execution_engine = ExecutionEngine()
        visualizer = ExecutionVisualizer()

        # Configure execution mode
        if execution_mode == 'debug':
            execution_engine.enable_debug_mode()
        elif execution_mode == 'step':
            execution_engine.enable_debug_mode()
            execution_engine.step_execution()

        # Set up visualization callbacks
        def emit_execution_event(event):
            socketio.emit('execution_event', event.to_dict())

        visualizer.add_event_callback(emit_execution_event)

        # Start execution
        result = execution_engine.execute_model(model)

        # Get execution summary
        summary = visualizer.get_execution_summary()

        return jsonify({
            'success': True,
            'data': {
                'execution_result': {
                    'success': result.success,
                    'output': result.output,
                    'error': str(result.error) if result.error else None,
                    'execution_time': result.execution_time,
                    'variables': result.variables
                },
                'execution_summary': summary
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/execution/step', methods=['POST'])
def step_execution():
    """Step through execution one node at a time."""
    try:
        # This would be implemented with a persistent execution engine
        # For now, return a placeholder response
        return jsonify({
            'success': True,
            'data': {
                'current_node': 'node_1',
                'variables': {'x': 10, 'y': 20},
                'can_continue': True
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/execution/stop', methods=['POST'])
def stop_execution():
    """Stop the current execution."""
    try:
        # This would stop the persistent execution engine
        return jsonify({
            'success': True,
            'data': {'stopped': True}
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/demos/load/<demo_type>', methods=['POST'])
def load_demo(demo_type):
    """Load a demo application for the specified paradigm."""
    try:
        # Import demo applications
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from demo_applications import DemoApplications

        demo_app = DemoApplications()

        # Create the appropriate demo
        if demo_type == 'node_based':
            model = demo_app.create_node_based_demo()
            demo_name = "Data Processing Pipeline"
        elif demo_type == 'block_based':
            model = demo_app.create_block_based_demo()
            demo_name = "Interactive Game Logic"
        elif demo_type == 'diagram_based':
            model = demo_app.create_diagram_based_demo()
            demo_name = "Object-Oriented Design"
        elif demo_type == 'timeline_based':
            model = demo_app.create_timeline_based_demo()
            demo_name = "Async Event Processing"
        else:
            return jsonify({
                'success': False,
                'error': f'Unknown demo type: {demo_type}'
            }), 400

        # Clear current canvas and load demo
        canvas.model.nodes.clear()
        canvas.model.connections.clear()

        # Add demo nodes and connections to canvas
        for node_id, node in model.nodes.items():
            canvas.model.nodes[node_id] = node

        for connection in model.connections:
            canvas.model.connections.append(connection)

        # Emit updates to all connected clients
        socketio.emit('canvas_cleared')

        # Send all nodes
        for node_id, node in model.nodes.items():
            socketio.emit('node_added', {
                'node_id': node_id,
                'node': {
                    'id': node.id,
                    'type': node.type.value,
                    'position': node.position,
                    'parameters': node.parameters,
                    'metadata': node.metadata,
                    'inputs': [{'name': inp.name, 'type': inp.data_type.__name__, 'required': inp.required} for inp in node.inputs],
                    'outputs': [{'name': out.name, 'type': out.data_type.__name__} for out in node.outputs]
                }
            })

        # Send all connections
        for connection in model.connections:
            socketio.emit('connection_added', {
                'connection': {
                    'id': connection.id,
                    'source_node_id': connection.source_node_id,
                    'source_port': connection.source_port,
                    'target_node_id': connection.target_node_id,
                    'target_port': connection.target_port,
                    'data_type': connection.data_type.__name__ if connection.data_type else 'None'
                }
            })

        return jsonify({
            'success': True,
            'data': {
                'demo_type': demo_type,
                'demo_name': demo_name,
                'nodes_count': len(model.nodes),
                'connections_count': len(model.connections)
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/uir/parse', methods=['POST'])
def parse_code_to_uir():
    """Parse source code into Universal IR."""
    try:
        data = request.get_json()

        source_code = data.get('source_code', '')
        source_language = data.get('source_language', '')
        filename = data.get('filename', None)

        if not source_code or not source_language:
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: source_code, source_language'
            }), 400

        # Parse to UIR
        uir_module = uir_translator.parse_code_to_uir(source_code, source_language, filename)

        # Store UIR module
        module_id = str(uuid.uuid4())
        uir_modules[module_id] = uir_module

        # Get function signatures and visual nodes
        function_signatures = uir_translator.get_function_signatures(uir_module)
        visual_nodes = uir_translator.create_visual_nodes_from_functions(uir_module)

        return jsonify({
            'success': True,
            'data': {
                'module_id': module_id,
                'source_language': source_language,
                'function_signatures': function_signatures,
                'visual_nodes': visual_nodes,
                'module_info': {
                    'name': uir_module.name,
                    'function_count': len(uir_module.functions),
                    'class_count': len(uir_module.classes),
                    'variable_count': len(uir_module.variables),
                    'imports': uir_module.imports
                }
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/uir/generate', methods=['POST'])
def generate_code_from_uir():
    """Generate code from stored UIR module."""
    try:
        data = request.get_json()

        module_id = data.get('module_id', '')
        target_language = data.get('target_language', '')

        if not module_id or not target_language:
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: module_id, target_language'
            }), 400

        # Get stored UIR module
        if module_id not in uir_modules:
            return jsonify({
                'success': False,
                'error': 'UIR module not found'
            }), 404

        uir_module = uir_modules[module_id]

        # Generate code
        generated_code = uir_translator.generate_code_from_uir(uir_module, target_language)

        return jsonify({
            'success': True,
            'data': {
                'generated_code': generated_code,
                'target_language': target_language,
                'module_id': module_id
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/uir/languages', methods=['GET'])
def get_supported_languages():
    """Get list of supported languages for UIR translation."""
    try:
        languages = uir_translator.get_supported_languages()

        return jsonify({
            'success': True,
            'data': {
                'languages': languages,
                'language_info': {
                    'python': {
                        'name': 'Python',
                        'extensions': ['.py'],
                        'description': 'Python programming language'
                    },
                    'javascript': {
                        'name': 'JavaScript',
                        'extensions': ['.js', '.mjs'],
                        'description': 'JavaScript programming language'
                    }
                }
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/uir/validate', methods=['POST'])
def validate_translation():
    """Validate a translation by round-trip testing."""
    try:
        data = request.get_json()

        original_code = data.get('original_code', '')
        translated_code = data.get('translated_code', '')
        source_language = data.get('source_language', '')
        target_language = data.get('target_language', '')

        if not all([original_code, translated_code, source_language, target_language]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters'
            }), 400

        # Validate translation
        validation_results = uir_translator.validate_translation(
            original_code, translated_code, source_language, target_language
        )

        return jsonify({
            'success': True,
            'data': validation_results
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/uir/nodes/import', methods=['POST'])
def import_uir_nodes():
    """Import UIR functions as visual nodes."""
    try:
        data = request.get_json()
        module_id = data.get('module_id', '')

        if not module_id or module_id not in uir_modules:
            return jsonify({
                'success': False,
                'error': 'UIR module not found'
            }), 404

        uir_module = uir_modules[module_id]

        # Create visual nodes from UIR functions
        visual_nodes = uir_translator.create_visual_nodes_from_functions(uir_module)

        # Add nodes to canvas
        added_nodes = []
        for i, node_def in enumerate(visual_nodes):
            # Create visual node
            node = VisualNode(
                type=NodeType.FUNCTION,
                position=(100 + i * 200, 100),
                parameters=node_def.get('metadata', {}),
                metadata={
                    'uir_node': True,
                    'node_definition': node_def
                }
            )

            # Add input ports
            for input_def in node_def.get('inputs', []):
                node.inputs.append(InputPort(
                    name=input_def['name'],
                    data_type=object,  # Simplified for now
                    required=input_def.get('required', True)
                ))

            # Add output ports
            for output_def in node_def.get('outputs', []):
                node.outputs.append(OutputPort(
                    name=output_def['name'],
                    data_type=object  # Simplified for now
                ))

            node_id = canvas.add_node(node, node.position)

            added_nodes.append({
                'node_id': node_id,
                'definition': node_def
            })

            # Emit update to all connected clients
            socketio.emit('node_added', {
                'node_id': node_id,
                'node': {
                    'id': node.id,
                    'type': node.type.value,
                    'position': node.position,
                    'parameters': node.parameters,
                    'metadata': node.metadata,
                    'inputs': [{'name': inp.name, 'type': inp.data_type.__name__, 'required': inp.required} for inp in node.inputs],
                    'outputs': [{'name': out.name, 'type': out.data_type.__name__} for out in node.outputs]
                }
            })

        return jsonify({
            'success': True,
            'data': {
                'imported_nodes': added_nodes,
                'count': len(added_nodes)
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Repository Analysis API endpoints
@app.route('/api/repository/analyze', methods=['POST'])
@app.route('/api/repository/analyze', methods=['POST'])
def analyze_repository():
    """Analyze uploaded repository files using UIR translation."""
    try:
        data = request.get_json()
        files = data.get('files', [])

        if not files:
            return jsonify({
                'success': False,
                'error': 'No files provided'
            }), 400

        # Extract import options (dependency strategy, etc.)
        import_options = data.get('options', {})
        dep_strategy_str = import_options.get('dependencyStrategy', 'preserve')

        analysis_results = {
            'files': [],
            'uir_modules': [],
            'visual_nodes': [],
            'summary': {
                'total_files': len(files),
                'supported_files': 0,
                'total_functions': 0,
                'total_classes': 0,
                'total_variables': 0,
                'languages_detected': set()
            }
        }

        for file_info in files:
            file_path = file_info.get('path', '')
            file_content = file_info.get('content', '')
            file_type = file_info.get('type', 'unknown')

            # Detect language if not provided
            if file_type == 'unknown':
                detected_lang = uir_translator.detect_language_from_filename(file_path)
                if detected_lang:
                    file_type = detected_lang

            # Skip unsupported files
            if file_type not in uir_translator.get_supported_languages():
                continue

            try:
                # === LEDGER: Begin import session for this file ===
                import_session_num = session_ledger.begin_import(
                    source_file=file_path,
                    source_language=file_type,
                    file_content=file_content,
                    dependency_strategy=dep_strategy_str
                )
                
                # Parse file using UIR
                uir_module = uir_translator.parse_code_to_uir(file_content, file_type, file_path)

                # === LEDGER: Record file-level imports ===
                if uir_module.imports:
                    session_ledger.record_file_imports(
                        import_session_num, uir_module.imports, file_path
                    )

                # Store UIR module
                module_id = str(uuid.uuid4())
                uir_modules[module_id] = uir_module

                # Get function signatures and visual nodes
                function_signatures = uir_translator.get_function_signatures(uir_module)
                visual_nodes = uir_translator.create_visual_nodes_from_functions(uir_module)

                # Create file analysis
                file_analysis = {
                    'path': file_path,
                    'type': file_type,
                    'size': len(file_content),
                    'module_id': module_id,
                    'functions': [],
                    'classes': [],
                    'variables': [],
                    'dependencies': {
                        'imports': uir_module.imports,
                        'exports': uir_module.exports
                    },
                    'uir_info': {
                        'function_count': len(uir_module.functions),
                        'class_count': len(uir_module.classes),
                        'variable_count': len(uir_module.variables)
                    }
                }

                # Extract functions from UIR
                for func in uir_module.functions:
                    func_info = {
                        'id': func.id,
                        'name': func.name,
                        'parameters': [param.name for param in func.parameters],
                        'return_type': str(func.return_type),
                        'isAsync': func.implementation_hints.get('is_async', False),
                        'hasComplexLogic': func.implementation_hints.get('complexity', 1) > 5,
                        'description': func.semantics.purpose if func.semantics else None,
                        'source_language': func.source_language
                    }
                    file_analysis['functions'].append(func_info)
                    analysis_results['summary']['total_functions'] += 1

                # Extract classes from UIR
                for cls in uir_module.classes:
                    class_info = {
                        'id': cls.id,
                        'name': cls.name,
                        'baseClasses': cls.base_classes,
                        'methods': [method.name for method in cls.methods],
                        'properties': [prop.name for prop in cls.properties],
                        'source_language': cls.source_language
                    }
                    file_analysis['classes'].append(class_info)
                    analysis_results['summary']['total_classes'] += 1

                # Extract variables from UIR
                for var in uir_module.variables:
                    var_info = {
                        'id': var.id,
                        'name': var.name,
                        'type': str(var.type_sig),
                        'isConstant': var.is_constant,
                        'isGlobal': var.is_global,
                        'value': str(var.value) if var.value is not None else None,
                        'source_language': var.source_language
                    }
                    file_analysis['variables'].append(var_info)
                    analysis_results['summary']['total_variables'] += 1

                analysis_results['files'].append(file_analysis)
                analysis_results['uir_modules'].append({
                    'module_id': module_id,
                    'file_path': file_path,
                    'language': file_type,
                    'function_signatures': function_signatures
                })
                
                # Tag each visual node with its import session number and source file
                for vnode in visual_nodes:
                    if 'metadata' not in vnode:
                        vnode['metadata'] = {}
                    vnode['metadata']['import_session_number'] = import_session_num
                    vnode['metadata']['source_file'] = file_path
                    vnode['metadata']['source_language'] = file_type
                
                analysis_results['visual_nodes'].extend(visual_nodes)
                analysis_results['summary']['supported_files'] += 1
                analysis_results['summary']['languages_detected'].add(file_type)

            except Exception as e:
                # Handle parsing errors gracefully
                file_analysis = {
                    'path': file_path,
                    'type': file_type,
                    'error': f"UIR parse error: {str(e)}",
                    'functions': [],
                    'classes': [],
                    'variables': [],
                    'dependencies': {'imports': [], 'exports': []},
                    'uir_info': {'function_count': 0, 'class_count': 0, 'variable_count': 0}
                }
                analysis_results['files'].append(file_analysis)

        # Convert set to list for JSON serialization
        analysis_results['summary']['languages_detected'] = list(analysis_results['summary']['languages_detected'])

        return jsonify({
            'success': True,
            'data': analysis_results
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/canvas/nodes/<node_id>/parameters', methods=['PATCH', 'PUT'])
def update_node_parameters(node_id):
    """Update node parameters."""
    try:
        data = request.get_json()

        # Find the node in the canvas
        node = canvas.model.nodes.get(node_id)
        if not node:
            return jsonify({
                'success': False,
                'error': 'Node not found'
            }), 404

        if request.method == 'PATCH':
            # Partial update - merge with existing parameters
            if not hasattr(node, 'parameters') or node.parameters is None:
                node.parameters = {}
            node.parameters.update(data)
        else:
            # Full update - replace all parameters
            node.parameters = data

        # === LEDGER: Record parameter & code changes ===
        # Check if source_code was changed (the most important field)
        code_fields = ['source_code', 'code', 'body']
        code_changed = False
        for field in code_fields:
            if field in data:
                new_code = data[field]
                if isinstance(new_code, str):
                    session_ledger.record_code_edit(node_id, new_code, reason='parameter_update')
                    code_changed = True
                    break
        
        # Record general parameter change
        session_ledger.record_params_change(node_id, node.parameters)

        # Emit update to all connected clients
        socketio.emit('node_parameters_updated', {
            'node_id': node_id,
            'parameters': node.parameters
        })

        return jsonify({
            'success': True,
            'data': {
                'node_id': node_id,
                'parameters': node.parameters
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/canvas/nodes/<node_id>/metadata', methods=['PATCH', 'PUT'])
def update_node_metadata(node_id):
    """Update node metadata."""
    try:
        data = request.get_json()

        # Find the node in the canvas
        node = canvas.model.nodes.get(node_id)
        if not node:
            return jsonify({
                'success': False,
                'error': 'Node not found'
            }), 404

        if request.method == 'PATCH':
            # Partial update - merge with existing metadata
            if not hasattr(node, 'metadata') or node.metadata is None:
                node.metadata = {}
            node.metadata.update(data)
        else:
            # Full update - replace all metadata
            node.metadata = data

        # === LEDGER: Record metadata changes ===
        # If source_code was updated via metadata, record the code edit
        if 'source_code' in data and isinstance(data['source_code'], str):
            session_ledger.record_code_edit(node_id, data['source_code'], reason='metadata_update')

        # Emit update to all connected clients
        socketio.emit('node_metadata_updated', {
            'node_id': node_id,
            'metadata': node.metadata
        })

        return jsonify({
            'success': True,
            'data': {'metadata': node.metadata}
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _parse_port_type(type_name: str):
    if not type_name:
        return object
    normalized = str(type_name).strip().lower()
    type_map = {
        'str': str,
        'string': str,
        'int': int,
        'integer': int,
        'float': float,
        'number': float,
        'bool': bool,
        'boolean': bool,
        'list': list,
        'array': list,
        'dict': dict,
        'object': object,
        'any': object
    }
    return type_map.get(normalized, object)


def _get_canvas_selection():
    """Robustly retrieve the current selection from the canvas with multiple fallbacks."""
    # Prefer an explicit method if present (use getattr to avoid static access warnings)
    get_sel = getattr(canvas, 'get_selection', None)
    if callable(get_sel):
        try:
            sel = get_sel() or {}
        except Exception:
            sel = {}
        if isinstance(sel, dict):
            return {
                'nodes': list(sel.get('nodes', sel.get('selected_nodes', []))),
                'connections': list(sel.get('connections', sel.get('selected_connections', [])))
            }
        # Fallback when selection is not a dict
        try:
            nodes = list(getattr(sel, 'nodes', getattr(sel, 'selected_nodes', [])))
        except Exception:
            nodes = []
        try:
            connections = list(getattr(sel, 'connections', getattr(sel, 'selected_connections', [])))
        except Exception:
            connections = []
        return {
            'nodes': nodes,
            'connections': connections
        }

    # Try a selection attribute
    if hasattr(canvas, 'selection') and isinstance(getattr(canvas, 'selection'), dict):
        sel = getattr(canvas, 'selection')
        return {
            'nodes': list(sel.get('nodes', sel.get('selected_nodes', []))),
            'connections': list(sel.get('connections', sel.get('selected_connections', [])))
        }

    # Try common attribute names for selected items
    nodes = getattr(canvas, 'selected_nodes', None)
    if nodes is None:
        nodes = getattr(canvas, 'selection_nodes', [])
    connections = getattr(canvas, 'selected_connections', None)
    if connections is None:
        connections = getattr(canvas, 'selection_connections', [])

    # Normalize to lists
    try:
        node_list = list(nodes) if nodes is not None else []
    except Exception:
        node_list = []
    try:
        connection_list = list(connections) if connections is not None else []
    except Exception:
        connection_list = []

    return {
        'nodes': node_list,
        'connections': connection_list
    }


def _set_canvas_selection(nodes, connections):
    """Set the current selection on the canvas using available methods or attributes with fallbacks."""
    # Normalize inputs
    node_list = list(nodes) if nodes is not None else []
    connection_list = list(connections) if connections is not None else []

    # If Canvas provides set_selection, prefer that (use getattr to avoid static access warnings)
    set_sel = getattr(canvas, 'set_selection', None)
    if callable(set_sel):
        try:
            set_sel(node_list, connection_list)
            return True
        except Exception:
            pass

    # If canvas.selection is a dict, update it
    if hasattr(canvas, 'selection') and isinstance(getattr(canvas, 'selection'), dict):
        try:
            sel = getattr(canvas, 'selection')
            sel['nodes'] = node_list
            sel['connections'] = connection_list
            return True
        except Exception:
            pass

    # Try common attribute names for selected items
    try:
        setattr(canvas, 'selected_nodes', node_list)
        setattr(canvas, 'selected_connections', connection_list)
        return True
    except Exception:
        pass

    # Last attempt: try to mutate the object returned by get_selection if possible (use getattr)
    get_sel = getattr(canvas, 'get_selection', None)
    if callable(get_sel):
        try:
            sel = get_sel()
            if isinstance(sel, dict):
                sel['nodes'] = node_list
                sel['connections'] = connection_list
                return True
        except Exception:
            pass

    # Could not set selection
    return False


@app.route('/api/canvas/nodes/<node_id>/ports', methods=['PUT'])
def update_node_ports(node_id):
    """Update node input/output ports."""
    try:
        data = request.get_json() or {}
        inputs = data.get('inputs', [])
        outputs = data.get('outputs', [])

        node = canvas.model.nodes.get(node_id)
        if not node:
            return jsonify({
                'success': False,
                'error': 'Node not found'
            }), 404

        # Build new port lists
        new_inputs = []
        for inp in inputs:
            name = str(inp.get('name', '')).strip()
            if not name:
                continue
            data_type = _parse_port_type(inp.get('type'))
            new_inputs.append(InputPort(
                name=name,
                data_type=data_type,
                required=bool(inp.get('required', False)),
                description=inp.get('description', '') or ''
            ))

        new_outputs = []
        for out in outputs:
            name = str(out.get('name', '')).strip()
            if not name:
                continue
            data_type = _parse_port_type(out.get('type'))
            new_outputs.append(OutputPort(
                name=name,
                data_type=data_type,
                description=out.get('description', '') or ''
            ))

        # Apply the changes to the node
        node.inputs = new_inputs
        node.outputs = new_outputs

        # === LEDGER: Record I/O port changes ===
        session_ledger.record_io_change(
            node_id,
            [{'name': inp.name, 'type': inp.data_type.__name__, 'required': getattr(inp, 'required', False)} for inp in new_inputs],
            [{'name': out.name, 'type': out.data_type.__name__} for out in new_outputs]
        )

        # Emit update to all connected clients
        socketio.emit('node_ports_updated', {
            'node_id': node_id,
            'inputs': [{'name': inp.name, 'type': inp.data_type.__name__, 'required': getattr(inp, 'required', False)} for inp in node.inputs],
            'outputs': [{'name': out.name, 'type': out.data_type.__name__} for out in node.outputs]
        })

        return jsonify({
            'success': True,
            'data': {
                'inputs': [{'name': inp.name, 'type': inp.data_type.__name__, 'required': getattr(inp, 'required', False)} for inp in node.inputs],
                'outputs': [{'name': out.name, 'type': out.data_type.__name__} for out in node.outputs]
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/canvas/selection', methods=['GET'])
def get_selection():
    """Get currently selected nodes and connections using robust helper."""
    try:
        sel = _get_canvas_selection()
        return jsonify({
            'success': True,
            'data': {
                'selected_nodes': list(sel.get('nodes', [])),
                'selected_connections': list(sel.get('connections', []))
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/canvas/selection', methods=['POST'])
def update_selection():
    """Update the current selection using robust helper and fallbacks."""
    try:
        data = request.get_json()
        selected_nodes = data.get('nodes', [])
        selected_connections = data.get('connections', [])
        
        # Use robust setter that handles multiple Canvas implementations
        success = _set_canvas_selection(selected_nodes, selected_connections)
        if not success:
            # Final fallback: set attributes directly (best-effort)
            try:
                setattr(canvas, 'selected_nodes', list(selected_nodes))
                setattr(canvas, 'selected_connections', list(selected_connections))
            except Exception:
                pass
        
        # Emit update to all connected clients
        socketio.emit('selection_changed', {
            'selected_nodes': selected_nodes,
            'selected_connections': selected_connections
        })
        
        return jsonify({
            'success': True,
            'data': {
                'selected_nodes': selected_nodes,
                'selected_connections': selected_connections
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== SESSION LEDGER API ====================

@app.route('/api/session/stats', methods=['GET'])
def get_session_stats():
    """Get current session ledger statistics."""
    try:
        stats = session_ledger.get_session_stats()
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/session/ledger', methods=['GET'])
def get_session_ledger():
    """Get the full session ledger (for diagnostics / dev tools)."""
    try:
        data = session_ledger.to_dict()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/session/node/<node_id>/history', methods=['GET'])
def get_node_history(node_id):
    """Get the full event history for a single node."""
    try:
        entries = session_ledger.get_node_history(node_id)
        history = []
        for entry in entries:
            history.append({
                'entry_id': entry.entry_id,
                'event_type': entry.event_type.value,
                'timestamp': entry.timestamp,
                'source_language_id': entry.source_language_id,
                'target_language_id': entry.target_language_id,
                'payload': entry.get_payload(),
            })
        return jsonify({'success': True, 'data': history})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/session/node/<node_id>/snapshot', methods=['GET'])
def get_node_snapshot(node_id):
    """Get the current materialized snapshot for a single node."""
    try:
        snapshot = session_ledger.get_node_snapshot(node_id)
        if snapshot is None:
            return jsonify({'success': False, 'error': 'Node not found in ledger'}), 404
        
        return jsonify({
            'success': True,
            'data': {
                'node_id': snapshot.node_id,
                'node_type': snapshot.node_type,
                'raw_name': snapshot.raw_name,
                'display_name': snapshot.display_name,
                'class_name': snapshot.class_name,
                'original_source_code': snapshot.original_source_code,
                'current_source_code': snapshot.current_source_code,
                'original_language_id': snapshot.original_language_id,
                'current_language_id': snapshot.current_language_id,
                'source_file': snapshot.source_file,
                'import_session_number': snapshot.import_session_number,
                'is_modified': snapshot.is_modified,
                'is_converted': snapshot.is_converted,
                'is_connected': snapshot.is_connected,
                'version': snapshot.version,
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/session/reset', methods=['POST'])
def reset_session_ledger():
    """Reset the session ledger (creates a fresh one)."""
    global session_ledger
    try:
        session_ledger = SessionLedger()
        return jsonify({'success': True, 'message': 'Session ledger reset'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== AI CHAT PROXY ====================

@app.route('/api/ai/chat', methods=['POST'])
def ai_chat_proxy():
    """Proxy AI chat requests to the configured LLM endpoint to avoid CORS issues.
    
    The browser sends everything to this Flask route, and Flask forwards
    the request server-side to the actual LLM API (local or remote).
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON body provided'}), 400

        endpoint = (data.get('endpoint') or '').rstrip('/')
        api_key = data.get('apiKey', '')
        model = data.get('model', 'gpt-4o')
        messages = data.get('messages', [])
        temperature = data.get('temperature', 0.7)
        max_tokens = data.get('max_tokens', 4096)

        if not endpoint:
            return jsonify({'error': 'No endpoint configured'}), 400

        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

        upstream_url = f'{endpoint}/chat/completions'
        payload = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens
        }

        resp = http_requests.post(upstream_url, json=payload, headers=headers, timeout=120)
        return (resp.content, resp.status_code, {'Content-Type': resp.headers.get('Content-Type', 'application/json')})

    except http_requests.exceptions.ConnectionError:
        return jsonify({'error': 'Cannot connect to LLM endpoint. Is the server running?'}), 502
    except http_requests.exceptions.Timeout:
        return jsonify({'error': 'LLM endpoint timed out (120s)'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== EXPORT CLEAN CODE ====================

@app.route('/api/export/code', methods=['POST'])
def export_clean_code():
    """Export clean, standalone executable code from visual model.
    
    Uses the Session Ledger as the primary source of truth for node lineage,
    source code, and transformation history. Falls back to frontend-sent data
    for any nodes not tracked by the ledger.
    """
    try:
        data = request.json or {}
        nodes_from_frontend = data.get('nodes', [])
        connections = data.get('connections', [])
        target_language = data.get('target_language', 'python')
        export_options = data.get('options', {})
        
        # Options for code generation
        include_imports = export_options.get('include_imports', True)
        include_docstrings = export_options.get('include_docstrings', True)
        include_type_hints = export_options.get('include_type_hints', True)
        include_error_handling = export_options.get('include_error_handling', False)
        optimize_code = export_options.get('optimize_code', False)
        standalone_mode = export_options.get('standalone_mode', True)
        entry_point = export_options.get('entry_point', 'main')
        
        # === LEDGER: Record export start ===
        session_ledger.record_export_started(target_language, export_options)
        
        # === BUILD AUTHORITATIVE NODE LIST FROM LEDGER ===
        # The ledger is the source of truth. Frontend data fills gaps.
        import re
        
        ledger_snapshots = session_ledger.get_active_snapshots()
        
        # Build a merged node list: ledger snapshots + any frontend-only nodes
        export_nodes = []
        seen_node_ids = set()
        
        # First: nodes from the ledger (authoritative)
        for node_id, snapshot in ledger_snapshots.items():
            seen_node_ids.add(node_id)
            export_nodes.append({
                'id': node_id,
                'type': snapshot.node_type,
                'raw_name': snapshot.raw_name,
                'display_name': snapshot.display_name,
                'class_name': snapshot.class_name,
                'source_code': snapshot.current_source_code,
                'original_source_code': snapshot.original_source_code,
                'source_language': resolve_language_string(LanguageID(snapshot.original_language_id)),
                'current_language': resolve_language_string(LanguageID(snapshot.current_language_id)),
                'parameters': snapshot.parameters,
                'metadata': snapshot.metadata,
                'function_type': snapshot.metadata.get('function_type', ''),
                'is_modified': snapshot.is_modified,
                'is_converted': snapshot.is_converted,
                'import_session': snapshot.import_session_number,
                'creation_order': snapshot.global_creation_order,
                'source_file': snapshot.source_file,
                'version': snapshot.version,
                '_from_ledger': True,
            })
        
        # Second: any frontend nodes NOT in ledger (manual creations, edge cases)
        for node_data in nodes_from_frontend:
            nid = node_data.get('id', '')
            if nid in seen_node_ids:
                continue
            
            metadata = node_data.get('metadata', {})
            raw_name = (node_data.get('raw_name') or metadata.get('raw_name', '') or
                       node_data.get('parameters', {}).get('function_name', '') or
                       node_data.get('parameters', {}).get('name', ''))
            source_code = (node_data.get('source_code') or metadata.get('source_code', '') or
                          node_data.get('code_snippet', ''))
            
            export_nodes.append({
                'id': nid,
                'type': node_data.get('type', 'expression'),
                'raw_name': raw_name,
                'display_name': node_data.get('name', raw_name or 'node'),
                'class_name': metadata.get('class_name'),
                'source_code': source_code,
                'original_source_code': source_code,
                'source_language': metadata.get('source_language', '') or _detect_language_from_code(source_code) or 'python',
                'current_language': metadata.get('source_language', '') or _detect_language_from_code(source_code) or 'python',
                'parameters': node_data.get('parameters', {}),
                'metadata': metadata,
                'function_type': (node_data.get('function_type') or 
                                 metadata.get('function_type', '')),
                'is_modified': False,
                'is_converted': False,
                'import_session': 0,
                'creation_order': 0,
                'source_file': '',
                'version': 0,
                '_from_ledger': False,
            })
        
        # Sort by creation order (preserves original file structure)
        export_nodes.sort(key=lambda n: (n.get('import_session', 0), n.get('creation_order', 0)))
        
        generated_code = ""
        
        if target_language == 'python':
            generated_code = _export_python(
                export_nodes, connections, 
                include_imports=include_imports,
                include_docstrings=include_docstrings,
                include_type_hints=include_type_hints,
                include_error_handling=include_error_handling,
                optimize_code=optimize_code,
                standalone_mode=standalone_mode,
                entry_point=entry_point
            )
            
        else:
            # For other languages, use the language-specific generators
            try:
                # Map language to generator module
                generator_map = {
                    'javascript': 'js_generator',
                    'typescript': 'typescript_generator',
                    'java': 'java_generator',
                    'go': 'go_generator',
                    'rust': 'rust_generator',
                    'csharp': 'csharp_generator',
                    'kotlin': 'kotlin_generator',
                    'swift': 'swift_generator',
                    'scala': 'scala_generator',
                    'c': 'c_generator',
                    'sql': 'sql_generator',
                    'bash': 'bash_generator',
                    'ruby': 'ruby_generator',
                    'php': 'php_generator',
                    'lua': 'lua_generator',
                    'r': 'r_generator'
                }
                
                if target_language not in generator_map:
                    return jsonify({
                        'success': False,
                        'error': f'No generator available for language: {target_language}'
                    }), 400
                
                # Import the appropriate generator
                import importlib
                generator_module = importlib.import_module(f'visual_editor_core.{generator_map[target_language]}')
                
                # Get the generator class
                generator_class_name = f'{target_language.title().replace("sharp", "#")}Generator'
                if hasattr(generator_module, generator_class_name):
                    generator = getattr(generator_module, generator_class_name)()
                else:
                    # Try alternate naming
                    for attr_name in dir(generator_module):
                        if 'Generator' in attr_name:
                            generator = getattr(generator_module, attr_name)()
                            break
                    else:
                        return jsonify({
                            'success': False,
                            'error': f'Generator class not found for: {target_language}'
                        }), 400
                
                # Build a proper UniversalModule from export_nodes + ledger imports
                from visual_editor_core.universal_ir import (
                    UniversalModule, UniversalFunction, UniversalClass,
                    UniversalVariable, Parameter, TypeSignature, DataType
                )
                import re as _re

                # ── FILTER & DEDUPLICATE (same logic as _export_python) ────
                _CF_PREFIXES = ('if ', 'for ', 'while ', 'try', 'with ', 'elif ', 'except', 'else')
                _CF_TYPES = frozenset({
                    'if_condition', 'for_loop', 'while_loop', 'try_except', 'with',
                    'Control Flow',
                })
                _LANG_TAG_PREFIXES = (
                    '[PY] ', '[JS] ', '[TS] ', '[JAVA] ', '[GO] ', '[RUST] ',
                    '[C] ', '[CS] ', '[KT] ', '[SWIFT] ', '[SCALA] ', '[RB] ',
                    '[PHP] ', '[LUA] ', '[R] ', '[BASH] ', '[SQL] ',
                )

                filtered_nodes = []
                for node in export_nodes:
                    raw = node.get('raw_name', '') or ''
                    ftype = node.get('function_type', '') or ''
                    ntype = node.get('type', '') or ''
                    meta = node.get('metadata', {}) or {}
                    src = node.get('source_code', '') or ''

                    # Skip control-flow nodes (embedded in parent method source)
                    if ftype in _CF_TYPES:
                        continue
                    if ntype in ('if_condition', 'for_loop', 'while_loop', 'try_except', 'with'):
                        continue
                    if raw and any(raw.startswith(pfx) for pfx in _CF_PREFIXES) and ntype not in ('function', 'method', 'async_function'):
                        if not src.strip().startswith(('def ', 'async def ', '@', 'function ', 'fn ', 'func ', 'public ', 'private ', 'protected ')):
                            continue

                    # Skip external-call / dependency reference stub nodes
                    if any(raw.startswith(tp) for tp in _LANG_TAG_PREFIXES):
                        continue
                    if ftype == 'External Call':
                        continue
                    if meta.get('external_call'):
                        continue

                    # Skip unnamed stubs with no real source code
                    if (not raw or raw == 'unnamed_function') and (not src or src.strip() in ('', 'pass')):
                        continue

                    filtered_nodes.append(node)

                # Deduplicate: keep latest version of each (raw_name, class_name)
                dedup_map = {}
                for node in filtered_nodes:
                    raw = node.get('raw_name', '') or ''
                    cls = node.get('class_name', '') or ''
                    key = (raw, cls)
                    existing = dedup_map.get(key)
                    if existing is None:
                        dedup_map[key] = node
                    else:
                        new_ver = node.get('version', 0) or 0
                        old_ver = existing.get('version', 0) or 0
                        new_ord = node.get('creation_order', 0) or 0
                        old_ord = existing.get('creation_order', 0) or 0
                        if (new_ver > old_ver) or (new_ver == old_ver and new_ord > old_ord):
                            dedup_map[key] = node

                export_nodes = list(dedup_map.values())
                export_nodes.sort(key=lambda n: (n.get('import_session', 0), n.get('creation_order', 0)))

                # ── BUILD MODULE ──────────────────────────────────────────
                module = UniversalModule(
                    name="exported_module",
                    source_language=target_language
                )

                # ── Inject ledger imports (respecting dependency strategy) ──
                dep_strategy = session_ledger.get_dependency_strategy()
                if include_imports and dep_strategy != DependencyStrategy.IGNORE:
                    ledger_imports = session_ledger.get_file_imports()
                    module.imports.extend(ledger_imports)

                # Track method names per class for stray-method cleanup
                class_method_names = set()

                # ── Populate module with functions / classes / variables ──
                for node in export_nodes:
                    ntype = node.get('type', 'expression')
                    raw = node.get('raw_name', '') or ''
                    src = node.get('source_code', '') or ''
                    cls_name = node.get('class_name') or ''
                    ftype = node.get('function_type', '') or ''
                    params = node.get('parameters', {})
                    meta = node.get('metadata', {})

                    # Collect inline imports from source code
                    if src and include_imports:
                        for m in _re.findall(
                            r'^(?:import |from |use |require|#include |using |library\(|source\().*$',
                            src, _re.MULTILINE
                        ):
                            if m not in module.imports:
                                module.imports.append(m)

                    is_method = bool(cls_name) or ftype in (
                        'Public Method', 'Private Method', 'Constructor',
                        'Getter', 'Setter', 'Static Method', 'Class Method',
                    )

                    if ntype in ('class', 'metaclass') and not is_method:
                        cls_obj = UniversalClass(
                            name=raw or params.get('name', 'UnnamedClass'),
                            source_language=target_language
                        )
                        cls_obj.source_code = src
                        module.classes.append(cls_obj)

                    elif ntype in ('function', 'async_function', 'method', 'lambda') or is_method or ftype:
                        func_obj = UniversalFunction(
                            name=raw or params.get('name', 'unnamed'),
                            parameters=[],
                            return_type=TypeSignature(DataType.ANY),
                            source_language=target_language,
                            source_code=src
                        )
                        func_obj.implementation_hints = {
                            'is_async': meta.get('is_async', False),
                            'class_name': cls_name,
                            'function_type': ftype,
                        }
                        if is_method and cls_name:
                            # Find or create the class, then add as method
                            target_cls = None
                            for c in module.classes:
                                if c.name == cls_name:
                                    target_cls = c
                                    break
                            if target_cls is None:
                                target_cls = UniversalClass(
                                    name=cls_name,
                                    source_language=target_language
                                )
                                module.classes.append(target_cls)
                            target_cls.methods.append(func_obj)
                            class_method_names.add(raw)
                        else:
                            module.functions.append(func_obj)

                    elif ntype in ('variable', 'constant', 'global_variable'):
                        var_obj = UniversalVariable(
                            name=raw or params.get('name', 'var'),
                            type_sig=TypeSignature(DataType.ANY),
                            value=params.get('value', params.get('initial_value', None)),
                            is_constant=(ntype == 'constant'),
                            source_language=target_language
                        )
                        module.variables.append(var_obj)

                # Post-categorisation cleanup: remove standalone functions that
                # are actually class methods (stray duplicates)
                module.functions = [
                    f for f in module.functions
                    if f.name not in class_method_names
                    and not (f.source_code and _re.match(
                        r'^\s*(?:async\s+)?def\s+\w+\s*\(\s*self[\s,)]',
                        f.source_code.strip().split('\n')[0]
                    ))
                ]

                # Try to use the generator
                if hasattr(generator, 'generate_from_nodes'):
                    generated_code = generator.generate_from_nodes(export_nodes, connections)
                elif hasattr(generator, 'generate_module'):
                    generated_code = generator.generate_module(module)
                elif hasattr(generator, 'generate'):
                    generated_code = generator.generate(module)
                    
            except ImportError as e:
                return jsonify({
                    'success': False,
                    'error': f'Generator not available: {str(e)}'
                }), 400
        
        # === LEDGER: Record export completion ===
        session_ledger.record_export_completed(target_language, True, len(export_nodes))
        
        return jsonify({
            'success': True,
            'code': generated_code,
            'language': target_language,
            'metadata': {
                'node_count': len(export_nodes),
                'connection_count': len(connections),
                'generated_at': datetime.now().isoformat(),
                'options': export_options,
                'ledger_nodes': sum(1 for n in export_nodes if n.get('_from_ledger')),
                'fallback_nodes': sum(1 for n in export_nodes if not n.get('_from_ledger')),
            }
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


def _export_python(export_nodes, connections, include_imports=True, include_docstrings=True,
                    include_type_hints=True, include_error_handling=False, optimize_code=False,
                    standalone_mode=True, entry_point='main'):
    """Generate clean Python code from ledger-backed export nodes.
    
    This function uses the authoritative node data (primarily from the SessionLedger)
    to produce correct, working Python code. Each node carries its original or current
    source_code, raw_name, class_name, and full metadata.
    """
    import re
    from visual_editor_core.code_generator import PythonFormatter, CodeOptimizer
    
    formatter = PythonFormatter()
    optimizer = CodeOptimizer()
    
    # ── 1. Header ──────────────────────────────────────────────────
    code_sections = []
    if standalone_mode:
        code_sections.append("#!/usr/bin/env python3")
        code_sections.append("# -*- coding: utf-8 -*-")
        code_sections.append("")
    
    if include_docstrings:
        code_sections.append('"""')
        code_sections.append('Generated by VPyD Visual Programming Platform')
        code_sections.append(f'Generated: {datetime.now().isoformat()}')
        code_sections.append('"""')
        code_sections.append("")
    
    # ── 2. Filter & deduplicate nodes ─────────────────────────────
    # Control flow keywords that appear as node raw_names from the UIR parser
    _CF_PREFIXES = ('if ', 'for ', 'while ', 'try', 'with ', 'elif ', 'except', 'else')
    _CF_TYPES = frozenset({
        'if_condition', 'for_loop', 'while_loop', 'try_except', 'with',
        'Control Flow',
    })

    filtered_nodes = []
    for node in export_nodes:
        raw = node.get('raw_name', '') or ''
        ftype = node.get('function_type', '') or ''
        ntype = node.get('type', '') or ''
        meta = node.get('metadata', {}) or {}
        src = node.get('source_code', '') or ''

        # ── Skip control-flow nodes (they are embedded in parent method source) ──
        if ftype in _CF_TYPES:
            continue
        if ntype in ('if_condition', 'for_loop', 'while_loop', 'try_except', 'with'):
            continue
        if raw and any(raw.startswith(pfx) for pfx in _CF_PREFIXES) and ntype not in ('function', 'method', 'async_function'):
            # Only skip if the node is NOT a real function/method definition
            # (a real function might coincidentally start with "for_" or "if_")
            if not src.strip().startswith(('def ', 'async def ', '@')):
                continue

        # ── Skip external-call / dependency reference nodes ──
        if raw.startswith('[PY] ') or raw.startswith('[JS] ') or raw.startswith('[TS] '):
            continue
        if ftype == 'External Call':
            continue
        if meta.get('external_call'):
            continue

        # ── Skip unnamed stubs with no real source code ──
        if (not raw or raw == 'unnamed_function') and (not src or src.strip() in ('', 'pass')):
            continue

        filtered_nodes.append(node)

    # ── Deduplicate: keep only the latest version of each (raw_name, class_name) ──
    dedup_map = {}  # (raw_name, class_name) -> node
    for node in filtered_nodes:
        raw = node.get('raw_name', '') or ''
        cls = node.get('class_name', '') or ''
        key = (raw, cls)

        existing = dedup_map.get(key)
        if existing is None:
            dedup_map[key] = node
        else:
            # Keep the one with the higher version (more recent edit), or higher creation_order
            new_ver = node.get('version', 0) or 0
            old_ver = existing.get('version', 0) or 0
            new_ord = node.get('creation_order', 0) or 0
            old_ord = existing.get('creation_order', 0) or 0
            if (new_ver > old_ver) or (new_ver == old_ver and new_ord > old_ord):
                dedup_map[key] = node

    export_nodes = list(dedup_map.values())
    # Re-sort after dedup to preserve original file order
    export_nodes.sort(key=lambda n: (n.get('import_session', 0), n.get('creation_order', 0)))

    # ── 3. Categorise nodes ────────────────────────────────────────
    imports_set = set()
    standalone_functions = []   # (raw_name, source_code, params, node)
    class_buckets = {}          # class_name -> [(method_name, source_code, params, node)]
    variable_defs = []
    main_code_fragments = []
    class_level_nodes = {}      # class_name -> source_code (for standalone class definitions)
    
    for node in export_nodes:
        ntype = node.get('type', 'expression')
        raw = node.get('raw_name', '') or ''
        src = node.get('source_code', '') or ''
        cls = node.get('class_name') or ''
        ftype = node.get('function_type', '') or ''
        params = node.get('parameters', {})
        meta = node.get('metadata', {})
        
        # ── Extract imports from source code ──
        if src and include_imports:
            for m in re.findall(r'^(?:import|from)\s+[\w.]+.*$', src, re.MULTILINE):
                imports_set.add(m)
        
        # ── Determine category ──
        is_method = bool(cls) or ftype in (
            'Public Method', 'Private Method', 'Constructor',
            'Getter', 'Setter', 'Static Method', 'Class Method',
        )
        
        if ntype in ('class', 'metaclass') and not is_method:
            # Full class definition node — if source_code has the class body, keep it
            class_name = raw or params.get('name', 'UnnamedClass')
            if src and src.strip().startswith('class '):
                class_level_nodes[class_name] = src.strip()
            else:
                # Generate from params using the existing helper
                class_level_nodes[class_name] = generate_class_code_from_data(
                    class_name, params, src, include_type_hints, include_docstrings
                )
        
        elif ntype in ('function', 'async_function', 'method', 'lambda') or is_method or ftype:
            if is_method and cls:
                # Method → bucket under its class
                if cls not in class_buckets:
                    class_buckets[cls] = []
                class_buckets[cls].append((raw, src, params, node))
            else:
                # Standalone function
                standalone_functions.append((raw, src, params, node))
        
        elif ntype in ('variable', 'constant', 'global_variable'):
            var_name = raw or params.get('variable_name', params.get('name', ''))
            var_value = params.get('value', params.get('initial_value', 'None'))
            var_type = params.get('type', '')
            if var_name:
                if include_type_hints and var_type:
                    variable_defs.append(f"{var_name}: {var_type} = {var_value}")
                else:
                    variable_defs.append(f"{var_name} = {var_value}")
        
        elif ntype == 'import':
            module = params.get('module', '')
            if module:
                imports_set.add(f"import {module}")
        
        elif ntype in ('expression', 'statement', 'control_flow', 'custom'):
            body = src or params.get('code', params.get('body', ''))
            if body:
                main_code_fragments.append(body)
    
    # ── 3b. Post-categorisation cleanup ────────────────────────────
    # Remove standalone functions that are actually class methods (same raw_name
    # already exists in a class bucket, or the source uses 'self' as first param).
    class_method_names = set()
    for methods in class_buckets.values():
        for method_name, _src, _params, _node in methods:
            class_method_names.add(method_name)
    
    cleaned_standalone = []
    for func_name, func_src, func_params, func_node in standalone_functions:
        # If this function name already appears as a class method, skip it
        if func_name and func_name in class_method_names:
            continue
        # If the source code uses 'self' as first parameter, it's a stray method
        if func_src and func_src.strip():
            first_line = func_src.strip().split('\n')[0]
            if re.match(r'^\s*(?:async\s+)?def\s+\w+\s*\(\s*self[\s,)]', first_line):
                continue
        cleaned_standalone.append((func_name, func_src, func_params, func_node))
    standalone_functions = cleaned_standalone
    
    # ── 4. Assemble imports ────────────────────────────────────────
    # Merge file-level imports from the session ledger based on dependency strategy
    dep_strategy = session_ledger.get_dependency_strategy()
    
    if include_imports and dep_strategy != DependencyStrategy.IGNORE:
        # Pull file-level imports recorded by the parser → ledger pipeline
        ledger_imports = session_ledger.get_file_imports()
        imports_set.update(ledger_imports)
    
    if include_imports and imports_set:
        code_sections.append("# Imports")
        code_sections.extend(sorted(imports_set))
        code_sections.append("")
    
    # ── 5. Variables ───────────────────────────────────────────────
    if variable_defs:
        code_sections.append("# Variables")
        code_sections.extend(variable_defs)
        code_sections.append("")
    
    # ── 6. Classes ─────────────────────────────────────────────────
    # Merge class-level nodes with method buckets
    all_class_names = sorted(set(list(class_level_nodes.keys()) + list(class_buckets.keys())))
    
    if all_class_names:
        code_sections.append("# Classes")
    
    for class_name in all_class_names:
        # If we already have a full class definition from source_code, use it
        if class_name in class_level_nodes and class_name not in class_buckets:
            code_sections.append(class_level_nodes[class_name])
            code_sections.append("")
            continue
        
        # Otherwise build the class from bucketed methods
        methods = class_buckets.get(class_name, [])
        
        # Check if we have a class-level source that already includes some methods
        if class_name in class_level_nodes:
            existing_src = class_level_nodes[class_name]
            if existing_src.strip().startswith('class ') and methods:
                # We have both a class skeleton and separate methods.
                # Prefer methods (they come from the ledger with full source)
                pass  # fall through to method-assembly below
            elif existing_src.strip().startswith('class '):
                code_sections.append(existing_src)
                code_sections.append("")
                continue
        
        # Build class from methods
        class_lines = [f"class {class_name}:"]
        if include_docstrings:
            class_lines.append(f'    """{class_name} class"""')
        
        if not methods:
            class_lines.append("    pass")
        
        for method_name, method_src, method_params, method_node in methods:
            class_lines.append("")
            
            if method_src and method_src.strip():
                src_stripped = method_src.strip()
                
                # If source_code is a full method def, indent it under the class
                if src_stripped.startswith(('def ', 'async def ', '@')):
                    for line in src_stripped.split('\n'):
                        if line.strip():
                            # Ensure 4-space indentation for class body
                            stripped_line = line.rstrip()
                            if not stripped_line.startswith('    '):
                                class_lines.append(f"    {stripped_line}")
                            else:
                                class_lines.append(stripped_line)
                        else:
                            class_lines.append("")
                else:
                    # Source is the body only; wrap it in a def
                    fn = method_node.get('function_type', '')
                    is_constructor = fn == 'Constructor' or method_name == '__init__'
                    m_name = '__init__' if is_constructor else (method_name or 'method')
                    is_async = method_params.get('is_async', False)
                    async_pfx = "async " if is_async else ""
                    
                    # Build parameter list
                    fp = method_params.get('parameters', method_params.get('args', []))
                    parts = ['self']
                    if isinstance(fp, list):
                        for p in fp:
                            pn = p.get('name', p) if isinstance(p, dict) else str(p)
                            if pn != 'self':
                                parts.append(pn)
                    class_lines.append(f"    {async_pfx}def {m_name}({', '.join(parts)}):")
                    
                    for bline in src_stripped.split('\n'):
                        if bline.strip():
                            class_lines.append(f"        {bline.lstrip()}")
                        else:
                            class_lines.append("")
            else:
                # No source code — generate a stub
                fn = method_node.get('function_type', '')
                is_constructor = fn == 'Constructor' or method_name == '__init__'
                m_name = '__init__' if is_constructor else (method_name or 'method')
                class_lines.append(f"    def {m_name}(self):")
                if include_docstrings and fn:
                    class_lines.append(f'        """{fn}"""')
                class_lines.append("        pass")
        
        code_sections.append('\n'.join(class_lines))
        code_sections.append("")
    
    # ── 7. Standalone functions ────────────────────────────────────
    if standalone_functions:
        code_sections.append("# Functions")
    
    for func_name, func_src, func_params, func_node in standalone_functions:
        if func_src and func_src.strip():
            src_stripped = func_src.strip()
            
            # If source_code already has a complete def, emit as-is
            if src_stripped.startswith(('def ', 'async def ', '@')):
                code_sections.append(src_stripped)
            else:
                # Source is the body — wrap in a def
                code_sections.append(
                    generate_function_code_from_data(
                        func_name or 'unnamed_function',
                        func_params,
                        func_src,
                        include_type_hints,
                        include_docstrings
                    )
                )
        else:
            # No source code, generate from params
            code_sections.append(
                generate_function_code_from_data(
                    func_name or 'unnamed_function',
                    func_params,
                    '',
                    include_type_hints,
                    include_docstrings
                )
            )
        code_sections.append("")
    
    # ── 8. Main block ──────────────────────────────────────────────
    # Only generate a main() stub if there are actual code fragments to put in it,
    # or if the export has no classes/functions at all (truly empty canvas).
    has_real_content = bool(all_class_names or standalone_functions or variable_defs)
    
    if standalone_mode and main_code_fragments:
        code_sections.append(f"def {entry_point}():")
        if include_docstrings:
            code_sections.append(f'    """Main entry point"""')
        
        for fragment in main_code_fragments:
            for line in fragment.split('\n'):
                if include_error_handling:
                    code_sections.append("    try:")
                    code_sections.append(f"        {line}")
                    code_sections.append("    except Exception as e:")
                    code_sections.append("        print(f'Error: {e}')")
                else:
                    code_sections.append(f"    {line}" if line.strip() else "")
        
        code_sections.append("")
        code_sections.append("")
        code_sections.append("if __name__ == '__main__':")
        code_sections.append(f"    {entry_point}()")
    elif standalone_mode and not has_real_content:
        # Empty canvas — generate a placeholder main
        code_sections.append(f"def {entry_point}():")
        if include_docstrings:
            code_sections.append(f'    """Main entry point"""')
        code_sections.append("    pass  # Add your code here")
        code_sections.append("")
        code_sections.append("")
        code_sections.append("if __name__ == '__main__':")
        code_sections.append(f"    {entry_point}()")
    elif main_code_fragments:
        code_sections.append("# Main code")
        for fragment in main_code_fragments:
            code_sections.extend(fragment.split('\n'))
    
    # ── 9. Finalise ────────────────────────────────────────────────
    generated_code = '\n'.join(code_sections)
    
    if optimize_code:
        generated_code = optimizer.optimize_imports(generated_code)
        generated_code = optimizer.remove_redundant_code(generated_code)
    
    generated_code = formatter.format_code(generated_code)
    
    return generated_code


def generate_function_code_from_data(name, params, code_snippet, include_type_hints=True, include_docstrings=True):
    """Generate Python function code from node data"""
    import re
    
    body = code_snippet or params.get('body', '') or ''
    
    # Check if the source code already contains a complete function definition
    if body and body.strip().startswith(('def ', 'async def ')):
        # Source code already has function definition, return as-is
        return body.strip()
    
    func_params = params.get('parameters', params.get('args', []))
    return_type = params.get('return_type', 'None')
    docstring = params.get('docstring', params.get('description', ''))
    is_async = params.get('is_async', False) or params.get('async', False)
    
    # Build parameter string
    param_parts = []
    if isinstance(func_params, list):
        for p in func_params:
            if isinstance(p, dict):
                p_name = p.get('name', 'arg')
                p_type = p.get('type', 'Any')
                p_default = p.get('default', None)
                if include_type_hints and p_type:
                    param_str = f"{p_name}: {p_type}"
                else:
                    param_str = p_name
                if p_default is not None:
                    param_str += f" = {p_default}"
                param_parts.append(param_str)
            elif isinstance(p, str):
                param_parts.append(p)
    elif isinstance(func_params, str):
        param_parts = [func_params] if func_params else []
    
    param_string = ', '.join(param_parts)
    
    # Build function signature
    async_prefix = "async " if is_async else ""
    if include_type_hints:
        signature = f"{async_prefix}def {name}({param_string}) -> {return_type}:"
    else:
        signature = f"{async_prefix}def {name}({param_string}):"
    
    lines = [signature]
    
    # Add docstring
    if include_docstrings and docstring:
        lines.append(f'    """{docstring}"""')
    
    # Add body
    if body:
        for line in body.split('\n'):
            if line.strip():
                # Check if already indented
                if line.startswith('    ') or line.startswith('\t'):
                    lines.append(line)
                else:
                    lines.append(f"    {line}")
            else:
                lines.append("")
    else:
        lines.append("    pass")
    
    return '\n'.join(lines)


def generate_class_code_from_data(name, params, code_snippet, include_type_hints=True, include_docstrings=True):
    """Generate Python class code from node data"""
    
    # Check if the source code already contains a complete class definition
    if code_snippet and code_snippet.strip().startswith('class '):
        return code_snippet.strip()
    
    bases = params.get('bases', params.get('parent_classes', []))
    methods = params.get('methods', [])
    attributes = params.get('attributes', params.get('properties', []))
    docstring = params.get('docstring', params.get('description', ''))
    
    # Build class signature
    if bases:
        if isinstance(bases, list):
            base_str = ', '.join(bases)
        else:
            base_str = str(bases)
        signature = f"class {name}({base_str}):"
    else:
        signature = f"class {name}:"
    
    lines = [signature]
    
    # Add docstring
    if include_docstrings:
        doc = docstring or f'{name} class'
        lines.append(f'    """{doc}"""')
    
    has_content = False
    
    # Add class attributes
    if attributes:
        lines.append("")
        for attr in attributes:
            if isinstance(attr, dict):
                attr_name = attr.get('name', 'attr')
                attr_type = attr.get('type', 'Any')
                attr_value = attr.get('value', attr.get('default', 'None'))
                if include_type_hints:
                    lines.append(f"    {attr_name}: {attr_type} = {attr_value}")
                else:
                    lines.append(f"    {attr_name} = {attr_value}")
                has_content = True
            elif isinstance(attr, str):
                lines.append(f"    {attr} = None")
                has_content = True
    
    # Add __init__ if we have attributes but no explicit init
    has_init = any(m.get('name') == '__init__' for m in methods if isinstance(m, dict))
    if not has_init and attributes:
        lines.append("")
        if include_type_hints:
            lines.append("    def __init__(self) -> None:")
        else:
            lines.append("    def __init__(self):")
        if include_docstrings:
            lines.append('        """Initialize instance"""')
        for attr in attributes:
            if isinstance(attr, dict):
                attr_name = attr.get('name', 'attr')
                attr_value = attr.get('value', attr.get('default', 'None'))
                lines.append(f"        self.{attr_name} = {attr_value}")
        has_content = True
    
    # Add methods
    for method in methods:
        if isinstance(method, dict):
            lines.append("")
            method_code = generate_function_code_from_data(
                method.get('name', 'method'),
                method,
                method.get('body', ''),
                include_type_hints,
                include_docstrings
            )
            # Indent method code
            for line in method_code.split('\n'):
                lines.append(f"    {line}" if line.strip() else "")
            has_content = True
    
    # Add code snippet as method body if present
    if code_snippet and not has_content:
        lines.append("")
        for line in code_snippet.split('\n'):
            if line.strip():
                lines.append(f"    {line}")
        has_content = True
    
    if not has_content:
        lines.append("    pass")
    
    return '\n'.join(lines)


# ==================== RUNTIME (REGISTRY + EXECUTION + MULTI-DEBUGGER) ====================
# Extracted to runtime.py — Blueprint-based modular separation
from web_interface.runtime import init_runtime
init_runtime(app, session_ledger, socketio)

# ==================== SHUTDOWN HOOK — flush state checkpoint ====================
import atexit as _atexit

def _shutdown_checkpoint():
    """Write a final state checkpoint before the process exits."""
    try:
        from web_interface.runtime import (
            _state_persistence, staging_pipeline,
            _marshal_tokens, _marshal_lock,
            _locked_slots, _locked_slots_lock,
        )
        from web_interface.state_persistence import build_promoted_snapshots
        if _state_persistence is not None and staging_pipeline is not None:
            with _marshal_lock:
                tokens_copy = dict(_marshal_tokens)
            with _locked_slots_lock:
                locks_copy = dict(_locked_slots)
            snapshots = build_promoted_snapshots(staging_pipeline, tokens_copy, locks_copy)
            _state_persistence.checkpoint_now(locks_copy, tokens_copy, snapshots)
            print("  [STATE] Shutdown checkpoint written.")
    except Exception as exc:
        print(f"  [STATE] Shutdown checkpoint FAILED: {exc}")

_atexit.register(_shutdown_checkpoint)

# ==================== SETTINGS HUB ====================
# Centralized settings, logging, test runner, and change-history.
from web_interface.settings_hub import register_settings_hub
register_settings_hub(app)

# ==================== SWAGGER / OPENAPI ====================
# Must be registered AFTER all other blueprints so the spec generator
# can enumerate every route.  New endpoints are documented automatically.
from web_interface.swagger import register_swagger
register_swagger(app)


if __name__ == '__main__':
    # Create templates and static directories
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)

    # ── Signal handlers for graceful shutdown + state checkpoint ──
    import signal as _signal

    def _signal_handler(signum, frame):
        print(f"\n  Received signal {signum} — flushing state checkpoint...")
        _shutdown_checkpoint()
        raise SystemExit(0)

    _signal.signal(_signal.SIGINT, _signal_handler)
    _signal.signal(_signal.SIGTERM, _signal_handler)

    print("Starting Visual Editor Web Interface...")
    
    # Use threading backend instead of eventlet to avoid port conflicts
    #
    # RELOADER NOTE:  The watchdog reloader on Windows uses PurePosixPath
    # for pattern matching, which can't handle backslash-separated paths.
    # This means exclude_patterns silently fails to exclude anything.
    # When the staging pipeline writes snippet files (stg-*.py) or the
    # audit logger appends JSONL, watchdog sees the change and restarts
    # the server — nuking all in-memory state (marshal tokens, staging
    # pipeline, node registry).
    #
    # Fix: use use_reloader=False for production-like use, or set
    # SPOKEDPY_RELOADER=1 env var to enable during active development
    # on runtime.py / app.py only.
    import os as _os
    use_reloader = _os.environ.get('SPOKEDPY_RELOADER', '0') == '1'
    host = _os.environ.get('SPOKEDPY_HOST', '0.0.0.0')
    port = int(_os.environ.get('SPOKEDPY_PORT', '5002'))

    print(f"Access the interface at: http://localhost:{port}")

    socketio.run(
        app,
        debug=True,
        host=host,
        port=port,
        use_reloader=use_reloader,
    )
