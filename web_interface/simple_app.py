"""
Simple Flask web interface for testing the Visual Editor Core.
"""

from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import json
import uuid
from typing import Dict, Any, List

# Import our visual editor components
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from visual_editor_core.canvas import Canvas
from visual_editor_core.models import VisualNode, NodeType, InputPort, OutputPort
from visual_editor_core.visual_paradigms import ParadigmManager, ParadigmType
from visual_editor_core.node_palette import NodePalette

app = Flask(__name__)
app.config['SECRET_KEY'] = 'visual-editor-secret-key'
CORS(app)

# Global instances
canvas = Canvas(width=1920, height=1080)
paradigm_manager = ParadigmManager()
node_palette = NodePalette()

@app.route('/')
def index():
    """Serve the main interface."""
    return render_template('index.html')

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

@app.route('/api/test', methods=['GET'])
def test_endpoint():
    """Simple test endpoint."""
    return jsonify({
        'success': True,
        'message': 'Visual Editor API is working!',
        'canvas_size': {'width': canvas.viewport.width, 'height': canvas.viewport.height}
    })

if __name__ == '__main__':
    # Create templates and static directories
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    print("Starting Simple Visual Editor Web Interface...")
    print("Access the interface at: http://localhost:5003")
    
    app.run(debug=True, host='0.0.0.0', port=5003)