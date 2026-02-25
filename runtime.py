import os
import sys
import subprocess
import tempfile
import shutil
import logging
import json
from flask import Blueprint, request, jsonify

try:
    from visual_editor_core.session_ledger import LanguageID
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Blueprint & Globals
# ---------------------------------------------------------------------------
runtime_bp = Blueprint('runtime', __name__)
logger = logging.getLogger('vpyd.runtime')

_session_ledger = None
_socketio = None
node_registry = None
_pipeline_manager = None

# ==================== REAL EXECUTION ENGINES ====================

class BaseExecutor:
    def run(self, code, input_data):
        raise NotImplementedError

class PythonExecutor(BaseExecutor):
    """Executes Python code in-process using a shared or isolated context."""
    def run(self, code, input_data):
        # Contract: Input is injected as '_input'. 
        # Code must assign result to '_output' or printed to stdout is captured?
        # For this demo: We use widespread convention: variable _input in, _output out.
        local_scope = {'_input': input_data, '_output': None}
        try:
            # Wrap in try/except for user code safety
            exec(code, {}, local_scope)
            return local_scope.get('_output', str(local_scope))
        except Exception as e:
            return f"Error: {str(e)}"

class SubprocessExecutor(BaseExecutor):
    """Base for CLI-based languages (Node, Rust, C). Transforms data via Stdin/Stdout."""
    def _run_process(self, command, input_str):
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False # Security best practice
            )
            stdout, stderr = process.communicate(input=str(input_str))
            if process.returncode != 0:
                return f"Runtime Error:\n{stderr}"
            return stdout.strip()
        except FileNotFoundError:
            return None # Signal that tool is missing

class NodeJSExecutor(SubprocessExecutor):
    def run(self, code, input_data):
        if not shutil.which('node'):
             return f"[Simulated JS] Node.js not found. Result: {input_data} (via Mock)"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as tmp:
            tmp.write(code)
            tmp_path = tmp.name
        
        try:
            result = self._run_process(['node', tmp_path], input_data)
            return result if result is not None else "Node execution failed"
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

class RustExecutor(SubprocessExecutor):
    def run(self, code, input_data):
        # Rust requires compilation.
        if not shutil.which('rustc'):
            # Fallback for demo environments without Rust installed
            return f"[Simulated Rust] Compiler not found. Logic: FastFilter({input_data})"

        with tempfile.TemporaryDirectory() as tmpdir:
            src_path = os.path.join(tmpdir, 'main.rs')
            bin_path = os.path.join(tmpdir, 'main.exe' if os.name == 'nt' else 'main')
            
            with open(src_path, 'w') as f:
                f.write(code)
            
            # Compile
            compile_res = subprocess.run(
                ['rustc', src_path, '-o', bin_path], 
                capture_output=True, text=True
            )
            
            if compile_res.returncode != 0:
                return f"Compilation Error:\n{compile_res.stderr}"
            
            # Execute
            return self._run_process([bin_path], input_data)

class CExecutor(SubprocessExecutor):
    def run(self, code, input_data):
        if not shutil.which('gcc'):
            return f"[Simulated C] GCC not found. Logic: Checksum({input_data})"

        with tempfile.TemporaryDirectory() as tmpdir:
            src_path = os.path.join(tmpdir, 'main.c')
            bin_path = os.path.join(tmpdir, 'main.exe' if os.name == 'nt' else 'main')
            
            with open(src_path, 'w') as f:
                f.write(code)
            
            # Compile
            compile_res = subprocess.run(
                ['gcc', src_path, '-o', bin_path], 
                capture_output=True, text=True
            )
            
            if compile_res.returncode != 0:
                return f"Compilation Error:\n{compile_res.stderr}"
            
            # Execute
            return self._run_process([bin_path], input_data)


# Instantiate Executors
_executors = {
    'a': PythonExecutor(),      # Python
    'b': NodeJSExecutor(),      # JavaScript
    'd': RustExecutor(),        # Rust
    'm': CExecutor()            # C
}

# ==================== UNIFIED PIPELINE MANAGER ====================

class PipelineManager:
    def __init__(self, registry, socketio=None):
        self.registry = registry
        self.socketio = socketio
        self.loaded_artifacts = {}

    def load_artifact(self, artifact_id, artifact_type, source_path):
        logger.info(f"Fusing artifact {artifact_id} ({artifact_type}) from {source_path}")
        self.loaded_artifacts[artifact_id] = {"type": artifact_type, "path": source_path}
        return True

    def execute_sequence(self, sequence_def, initial_payload=None):
        """
        Executes a chain of real code.
        """
        # Safety check: Avoid crash if sequence is empty
        if not sequence_def:
             return {"error": "Empty sequence", "status": "failed"}

        current_data = initial_payload
        trace_log = []
        
        logger.info(f"--- PIPELINE START: {len(sequence_def)} stages ---")

        for stage_idx, stage in enumerate(sequence_def):
            slot_id = stage.get('slot')
            # Support inline execution for demo/stateless mode
            inline_code = stage.get('code', None) 
            
            # Visualization: Start
            if self.socketio:
                self.socketio.emit('node_execution_start', {
                    'slot_id': slot_id,
                    'stage_index': stage_idx,
                    'timestamp': stage_idx
                })
            
            # 1. Resolve Language Engine
            lang_char = slot_id[2] if len(slot_id) > 2 else 'a' # Default Python
            execution_engine = _executors.get(lang_char, _executors['a'])
            
            # 2. Preparation
            if current_data is None and stage_idx == 0:
                current_data = "" # Init for source nodes

            logger.info(f" -> Stage {stage_idx+1}: Executing {slot_id} [Engine={lang_char}]")
            
            # 3. Execution (Real)
            try:
                # In real app: code = self.registry.get_code(slot_id)
                code_to_run = inline_code if inline_code else f"# Code for {slot_id} missing in payload"
                
                # Execute!
                processed = execution_engine.run(code_to_run, current_data)
                
                # Check for artifact usage (Mock check for demo)
                if "artifact:" in str(current_data):
                    processed = str(processed) + " [Linked Artifact Used]"

                # Visualization: Success
                if self.socketio:
                    self.socketio.emit('node_execution_success', {
                        'slot_id': slot_id,
                        'output_preview': str(processed)[:50],
                        'stage_index': stage_idx
                    })

            except Exception as exec_err:
                logger.error(f"Slot {slot_id} fatal error: {exec_err}")
                if self.socketio:
                    self.socketio.emit('node_execution_error', {'slot_id': slot_id, 'error': str(exec_err)})
                trace_log.append({"stage": stage_idx, "slot": slot_id, "error": str(exec_err)})
                break
            
            # 4. Handoff
            current_data = processed
            
            trace_log.append({
                "stage": stage_idx,
                "slot": slot_id,
                "engine": lang_char,
                "output_snapshot": str(current_data)[:100]
            })

        logger.info("--- PIPELINE FINISHED ---")
        return {
            "final_output": current_data,
            "trace": trace_log,
            "status": "success"
        }

# ==================== INITIALIZATION ====================

def init_runtime(app, session_ledger, socketio, registry_instance=None):
    global _session_ledger, _socketio, node_registry, _pipeline_manager

    _session_ledger = session_ledger
    _socketio = socketio
    node_registry = registry_instance 
    
    _pipeline_manager = PipelineManager(node_registry, socketio=socketio)

    app.register_blueprint(runtime_bp)
    logger.info("Runtime Pipeline Manager Initialized")

# ==================== ROUTES ====================

@runtime_bp.route('/api/execution/pipeline/run', methods=['POST'])
def run_pipeline():
    try:
        if _pipeline_manager is None:
             return jsonify({"error": "Runtime not initialized"}), 500

        data = request.json
        sequence = data.get('sequence', [])
        initial_input = data.get('input', None)

        if not sequence:
             return jsonify({"error": "No execution sequence provided"}), 400

        result = _pipeline_manager.execute_sequence(sequence, initial_input)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Pipeline Execution Failed: {e}")
        return jsonify({"error": str(e)}), 500

@runtime_bp.route('/api/execution/pipeline/fuse', methods=['POST'])
def fuse_artifact():
    try:
        data = request.json
        artifact_id = data.get('id')
        artifact_type = data.get('type')
        path = data.get('path')
        success = _pipeline_manager.load_artifact(artifact_id, artifact_type, path)
        return jsonify({"status": "fused", "id": artifact_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
