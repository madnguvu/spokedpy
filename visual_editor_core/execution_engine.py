"""
Execution Engine for live execution and debugging of visual programs.

Supports multiple language executors:
  • PythonExecutor     — in-process exec() with shared namespace (REPL-style)
  • JavaScriptExecutor — subprocess via Node.js
  • RustExecutor       — subprocess via rustc (compile + run)
  • PerlExecutor       — subprocess via perl (Strawberry Perl)
"""

import sys
import io
import os
import tempfile
import subprocess
import shutil
import traceback
import ast
import time
from typing import Dict, Any, Optional, List, Callable
from contextlib import redirect_stdout, redirect_stderr
from .models import VisualModel, VisualNode, NodeType, InputPort, OutputPort
from .data_flow_visualizer import DataFlowVisualizer


def _run_subprocess(*args, **kwargs):
    """Wrapper around subprocess.run that forces UTF-8 encoding on Windows.
    Without this, Python defaults to the system locale (cp1252) which
    cannot decode many Unicode characters (box-drawing, emoji, etc.)."""
    if kwargs.get('text', False) and 'encoding' not in kwargs:
        kwargs['encoding'] = 'utf-8'
        kwargs['errors'] = 'replace'  # Never crash on stray bytes
    return subprocess.run(*args, **kwargs)


class ExecutionResult:
    """Represents the result of executing a visual model."""
    
    def __init__(self, success: bool, output: str = "", error: Optional[Exception] = None, 
                 variables: Optional[Dict[str, Any]] = None, execution_time: float = 0.0):
        self.success = success
        self.output = output
        self.error = error
        self.variables = variables or {}
        self.execution_time = execution_time
        self.traceback = None
        
        if error:
            self.traceback = traceback.format_exc()
    
    def __str__(self) -> str:
        """String representation of execution result."""
        if self.success:
            return f"Success: {self.output}"
        else:
            return f"Error: {self.error}"


class ExecutionState:
    """Represents the current state of program execution."""
    
    def __init__(self, current_node: Optional[str] = None, variables: Optional[Dict[str, Any]] = None,
                 line_number: int = 0, call_stack: Optional[List[str]] = None):
        self.current_node = current_node
        self.variables = variables or {}
        self.line_number = line_number
        self.call_stack = call_stack or []
        self.is_paused = False
        self.step_mode = False
    
    def copy(self) -> 'ExecutionState':
        """Create a copy of the current state."""
        return ExecutionState(
            current_node=self.current_node,
            variables=self.variables.copy(),
            line_number=self.line_number,
            call_stack=self.call_stack.copy()
        )


class VisualDebugger:
    """Provides debugging capabilities for visual programs."""
    
    def __init__(self):
        self.breakpoints: Dict[str, bool] = {}  # node_id -> enabled
        self.step_mode = False
        self.current_node = None
        self.execution_history: List[ExecutionState] = []
        self.variable_watch_list: List[str] = []
        self.step_into_mode = False
        self.step_over_mode = False
        self.call_stack: List[Dict[str, Any]] = []
        self.variable_modifications: Dict[str, List[Any]] = {}  # Track variable changes
        self.execution_trace: List[Dict[str, Any]] = []
    
    def set_breakpoint(self, node_id: str, enabled: bool = True):
        """Set a breakpoint on a visual node."""
        self.breakpoints[node_id] = enabled
    
    def clear_breakpoint(self, node_id: str):
        """Clear a breakpoint from a visual node."""
        self.breakpoints.pop(node_id, None)
    
    def clear_all_breakpoints(self):
        """Clear all breakpoints."""
        self.breakpoints.clear()
    
    def is_breakpoint_set(self, node_id: str) -> bool:
        """Check if a breakpoint is set and enabled for a node."""
        return self.breakpoints.get(node_id, False)
    
    def enable_step_mode(self):
        """Enable step-by-step execution."""
        self.step_mode = True
    
    def disable_step_mode(self):
        """Disable step-by-step execution."""
        self.step_mode = False
    
    def enable_step_into(self):
        """Enable step-into mode for function calls."""
        self.step_into_mode = True
        self.step_over_mode = False
    
    def enable_step_over(self):
        """Enable step-over mode for function calls."""
        self.step_over_mode = True
        self.step_into_mode = False
    
    def disable_step_modes(self):
        """Disable all step modes."""
        self.step_into_mode = False
        self.step_over_mode = False
    
    def should_pause_at_node(self, node_id: str) -> bool:
        """Check if execution should pause at this node."""
        return self.step_mode or self.is_breakpoint_set(node_id)
    
    def add_to_watch_list(self, variable_name: str):
        """Add a variable to the watch list."""
        if variable_name not in self.variable_watch_list:
            self.variable_watch_list.append(variable_name)
    
    def remove_from_watch_list(self, variable_name: str):
        """Remove a variable from the watch list."""
        if variable_name in self.variable_watch_list:
            self.variable_watch_list.remove(variable_name)
    
    def get_watched_variables(self, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Get values of watched variables."""
        return {name: variables.get(name, '<undefined>') 
                for name in self.variable_watch_list}
    
    def record_execution_state(self, state: ExecutionState):
        """Record an execution state for debugging history."""
        self.execution_history.append(state.copy())
        # Keep only last 100 states to prevent memory issues
        if len(self.execution_history) > 100:
            self.execution_history.pop(0)
    
    def push_call_stack(self, function_name: str, node_id: str, variables: Dict[str, Any]):
        """Push a function call onto the call stack."""
        call_info = {
            'function_name': function_name,
            'node_id': node_id,
            'variables': variables.copy(),
            'timestamp': self._get_timestamp()
        }
        self.call_stack.append(call_info)
    
    def pop_call_stack(self) -> Optional[Dict[str, Any]]:
        """Pop a function call from the call stack."""
        if self.call_stack:
            return self.call_stack.pop()
        return None
    
    def get_call_stack(self) -> List[Dict[str, Any]]:
        """Get the current call stack."""
        return self.call_stack.copy()
    
    def track_variable_modification(self, variable_name: str, old_value: Any, new_value: Any):
        """Track modifications to variables."""
        if variable_name not in self.variable_modifications:
            self.variable_modifications[variable_name] = []
        
        modification = {
            'old_value': old_value,
            'new_value': new_value,
            'timestamp': self._get_timestamp(),
            'node_id': self.current_node
        }
        self.variable_modifications[variable_name].append(modification)
        
        # Keep only last 50 modifications per variable
        if len(self.variable_modifications[variable_name]) > 50:
            self.variable_modifications[variable_name].pop(0)
    
    def get_variable_history(self, variable_name: str) -> List[Dict[str, Any]]:
        """Get the modification history of a variable."""
        return self.variable_modifications.get(variable_name, [])
    
    def add_execution_trace(self, node_id: str, node_type: str, operation: str, 
                           variables: Dict[str, Any], result: Any = None):
        """Add an entry to the execution trace."""
        trace_entry = {
            'node_id': node_id,
            'node_type': node_type,
            'operation': operation,
            'variables': variables.copy(),
            'result': result,
            'timestamp': self._get_timestamp()
        }
        self.execution_trace.append(trace_entry)
        
        # Keep only last 1000 trace entries
        if len(self.execution_trace) > 1000:
            self.execution_trace.pop(0)
    
    def get_execution_trace(self) -> List[Dict[str, Any]]:
        """Get the execution trace."""
        return self.execution_trace.copy()
    
    def highlight_current_node(self, node_id: str):
        """Highlight the currently executing node."""
        self.current_node = node_id
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Get comprehensive debug information."""
        return {
            'current_node': self.current_node,
            'breakpoints': self.breakpoints,
            'step_mode': self.step_mode,
            'step_into_mode': self.step_into_mode,
            'step_over_mode': self.step_over_mode,
            'watch_list': self.variable_watch_list,
            'call_stack_depth': len(self.call_stack),
            'execution_history_length': len(self.execution_history),
            'trace_entries': len(self.execution_trace)
        }
    
    def reset_debug_session(self):
        """Reset all debugging state."""
        self.current_node = None
        self.execution_history.clear()
        self.call_stack.clear()
        self.variable_modifications.clear()
        self.execution_trace.clear()
        self.disable_step_modes()
        self.disable_step_mode()
    
    def _get_timestamp(self) -> float:
        """Get current timestamp."""
        import time
        return time.time()


class PythonExecutor:
    """Executes Python code generated from visual models."""
    
    def __init__(self):
        self.global_namespace = {}
        self.local_namespace = {}
        self.output_buffer = io.StringIO()
        self.error_buffer = io.StringIO()
    
    def execute(self, code: str, capture_output: bool = True) -> ExecutionResult:
        """Execute Python code and return the result."""
        import time
        start_time = time.time()
        
        # Reset buffers
        self.output_buffer = io.StringIO()
        self.error_buffer = io.StringIO()
        
        try:
            if capture_output:
                # Capture stdout and stderr
                with redirect_stdout(self.output_buffer), redirect_stderr(self.error_buffer):
                    # Execute the code
                    exec(code, self.global_namespace, self.local_namespace)
            else:
                # Execute without capturing output
                exec(code, self.global_namespace, self.local_namespace)
            
            execution_time = time.time() - start_time
            output = self.output_buffer.getvalue()
            
            # Get final variable state
            variables = {**self.global_namespace, **self.local_namespace}
            # Filter out built-ins
            variables = {k: v for k, v in variables.items() 
                        if not k.startswith('__') and not callable(v)}
            
            return ExecutionResult(
                success=True,
                output=output,
                variables=variables,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_output = self.error_buffer.getvalue()
            
            return ExecutionResult(
                success=False,
                output=error_output,
                error=e,
                execution_time=execution_time
            )
    
    def execute_single_statement(self, statement: str) -> ExecutionResult:
        """Execute a single Python statement."""
        return self.execute(statement)
    
    def evaluate_expression(self, expression: str) -> Any:
        """Evaluate a Python expression and return the result."""
        try:
            return eval(expression, self.global_namespace, self.local_namespace)
        except Exception as e:
            return f"Error: {e}"
    
    def get_variable_value(self, variable_name: str) -> Any:
        """Get the value of a specific variable."""
        if variable_name in self.local_namespace:
            return self.local_namespace[variable_name]
        elif variable_name in self.global_namespace:
            return self.global_namespace[variable_name]
        else:
            return None
    
    def set_variable_value(self, variable_name: str, value: Any):
        """Set the value of a variable."""
        self.local_namespace[variable_name] = value
    
    def reset_namespace(self):
        """Reset the execution namespace."""
        self.global_namespace.clear()
        self.local_namespace.clear()
        # Add built-ins back
        self.global_namespace['__builtins__'] = __builtins__


# =========================================================================
# JAVASCRIPT EXECUTOR — Node.js subprocess
# =========================================================================

class JavaScriptExecutor:
    """Executes JavaScript code via Node.js subprocess.

    Each call to execute() is isolated — there is no shared namespace across
    invocations (unlike PythonExecutor's REPL style).  Variables are extracted
    from a trailing JSON dump injected into the user code.
    """

    TIMEOUT_SECONDS = 30

    def __init__(self):
        self._node_path: Optional[str] = shutil.which('node')

    # ------------------------------------------------------------------
    # public API  (mirrors PythonExecutor)
    # ------------------------------------------------------------------

    def execute(self, code: str, capture_output: bool = True) -> ExecutionResult:
        """Execute JavaScript code via Node.js and return the result."""
        if not self._node_path:
            return ExecutionResult(
                success=False,
                error=Exception('Node.js runtime not found on PATH — install Node.js to execute JavaScript'),
            )

        start_time = time.time()
        tmp_file = None

        try:
            # Write code to a temp file (handles multi-line, imports, etc.)
            tmp_fd, tmp_file = tempfile.mkstemp(suffix='.js', prefix='vpyd_js_')
            os.close(tmp_fd)

            with open(tmp_file, 'w', encoding='utf-8') as f:
                f.write(code)

            proc = _run_subprocess(
                [self._node_path, tmp_file],
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT_SECONDS,
            )

            execution_time = time.time() - start_time
            output = proc.stdout or ''
            error_text = proc.stderr or ''

            if proc.returncode != 0:
                return ExecutionResult(
                    success=False,
                    output=output,
                    error=Exception(error_text.strip() or f'Node.js exited with code {proc.returncode}'),
                    execution_time=execution_time,
                )

            return ExecutionResult(
                success=True,
                output=output,
                variables={},
                execution_time=execution_time,
            )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                error=Exception(f'JavaScript execution timed out after {self.TIMEOUT_SECONDS}s'),
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=e,
                execution_time=time.time() - start_time,
            )
        finally:
            if tmp_file and os.path.exists(tmp_file):
                try:
                    os.unlink(tmp_file)
                except OSError:
                    pass

    def execute_single_statement(self, statement: str) -> ExecutionResult:
        """Execute a single JavaScript statement."""
        return self.execute(statement)

    def reset_namespace(self):
        """No-op — each JS invocation is already isolated."""
        pass

    def set_variable_value(self, variable_name: str, value: Any):
        """Not supported for subprocess-based executor."""
        pass

    def get_variable_value(self, variable_name: str) -> Any:
        """Not supported for subprocess-based executor."""
        return None


# =========================================================================
# RUST EXECUTOR — rustc compile + run
# =========================================================================

class RustExecutor:
    """Executes Rust code by compiling with rustc then running the binary.

    Each call to execute() writes source to a temp file, compiles, and runs.
    Fully isolated — no shared state between invocations.
    """

    COMPILE_TIMEOUT = 60
    RUN_TIMEOUT = 30

    def __init__(self):
        self._rustc_path: Optional[str] = shutil.which('rustc')

    # ------------------------------------------------------------------
    # public API  (mirrors PythonExecutor)
    # ------------------------------------------------------------------

    def execute(self, code: str, capture_output: bool = True) -> ExecutionResult:
        """Compile and execute Rust code, returning the result."""
        # Lazy re-probe: PATH may have been updated since process start
        if not self._rustc_path:
            self._rustc_path = shutil.which('rustc')
        if not self._rustc_path:
            return ExecutionResult(
                success=False,
                error=Exception('rustc not found on PATH — install the Rust toolchain to execute Rust'),
            )

        start_time = time.time()
        tmp_dir = None

        try:
            # Create a temp directory for source + binary
            tmp_dir = tempfile.mkdtemp(prefix='vpyd_rs_')
            src_path = os.path.join(tmp_dir, 'main.rs')
            if sys.platform == 'win32':
                bin_path = os.path.join(tmp_dir, 'main.exe')
            else:
                bin_path = os.path.join(tmp_dir, 'main')

            with open(src_path, 'w', encoding='utf-8') as f:
                f.write(code)

            # ---- Compile ----
            compile_proc = _run_subprocess(
                [self._rustc_path, src_path, '-o', bin_path],
                capture_output=True,
                text=True,
                timeout=self.COMPILE_TIMEOUT,
            )

            if compile_proc.returncode != 0:
                compile_time = time.time() - start_time
                error_msg = compile_proc.stderr.strip() or f'rustc exited with code {compile_proc.returncode}'
                return ExecutionResult(
                    success=False,
                    output=compile_proc.stdout or '',
                    error=Exception(f'Compilation failed:\n{error_msg}'),
                    execution_time=compile_time,
                )

            # ---- Run ----
            run_proc = _run_subprocess(
                [bin_path],
                capture_output=True,
                text=True,
                timeout=self.RUN_TIMEOUT,
            )

            execution_time = time.time() - start_time
            output = run_proc.stdout or ''
            error_text = run_proc.stderr or ''

            if run_proc.returncode != 0:
                return ExecutionResult(
                    success=False,
                    output=output,
                    error=Exception(error_text.strip() or f'Rust binary exited with code {run_proc.returncode}'),
                    execution_time=execution_time,
                )

            return ExecutionResult(
                success=True,
                output=output,
                variables={},
                execution_time=execution_time,
            )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                error=Exception(f'Rust execution timed out'),
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=e,
                execution_time=time.time() - start_time,
            )
        finally:
            if tmp_dir and os.path.exists(tmp_dir):
                try:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                except OSError:
                    pass

    def execute_single_statement(self, statement: str) -> ExecutionResult:
        """Execute a single Rust statement (wraps in main if needed)."""
        return self.execute(statement)

    def reset_namespace(self):
        """No-op — each Rust invocation is already isolated."""
        pass

    def set_variable_value(self, variable_name: str, value: Any):
        """Not supported for subprocess-based executor."""
        pass

    def get_variable_value(self, variable_name: str) -> Any:
        """Not supported for subprocess-based executor."""
        return None


# =========================================================================
# BASH EXECUTOR — shell subprocess
# =========================================================================

class BashExecutor:
    """Executes Bash / shell scripts via subprocess.

    On Windows, falls back to Git-Bash, then PowerShell, then cmd.exe.
    Each call is isolated — no shared state.
    """

    TIMEOUT_SECONDS = 30

    def __init__(self):
        self._shell_path: Optional[str] = None
        self._shell_type: str = 'bash'  # 'bash', 'powershell', 'cmd'
        
        # Try bash first — but on Windows, verify it actually works
        bash_path = shutil.which('bash')
        if bash_path:
            # Quick probe: does bash actually launch?  WSL bash without
            # distros exits with 0xFFFFFFFF and prints an error.
            try:
                probe = subprocess.run(
                    [bash_path, '-c', 'echo ok'],
                    capture_output=True, text=True, timeout=5,
                    encoding='utf-8', errors='replace',
                )
                if probe.returncode == 0 and 'ok' in (probe.stdout or ''):
                    self._shell_path = bash_path
                    self._shell_type = 'bash'
            except Exception:
                pass

        if not self._shell_path:
            sh_path = shutil.which('sh')
            if sh_path:
                self._shell_path = sh_path
                self._shell_type = 'bash'

        # On Windows, prefer PowerShell over cmd for scripting capabilities
        if not self._shell_path and sys.platform == 'win32':
            pwsh = shutil.which('pwsh') or shutil.which('powershell')
            if pwsh:
                self._shell_path = pwsh
                self._shell_type = 'powershell'
            else:
                cmd_path = shutil.which('cmd')
                if cmd_path:
                    self._shell_path = cmd_path
                    self._shell_type = 'cmd'

    def execute(self, code: str, capture_output: bool = True) -> ExecutionResult:
        if not self._shell_path:
            return ExecutionResult(success=False, error=Exception(
                'No shell interpreter found (bash/sh/powershell/cmd) — install Git-Bash or WSL'))

        start_time = time.time()
        tmp_file = None
        try:
            # Choose file extension and command based on shell type
            if self._shell_type == 'powershell':
                suffix = '.ps1'
                # Translate common bash-isms to PowerShell equivalents
                ps_code = self._bash_to_powershell(code)
                tmp_fd, tmp_file = tempfile.mkstemp(suffix=suffix, prefix='vpyd_sh_')
                os.close(tmp_fd)
                with open(tmp_file, 'w', encoding='utf-8-sig') as f:
                    f.write(ps_code)
                cmd = [self._shell_path, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', tmp_file]
            elif self._shell_type == 'cmd':
                suffix = '.bat'
                tmp_fd, tmp_file = tempfile.mkstemp(suffix=suffix, prefix='vpyd_sh_')
                os.close(tmp_fd)
                with open(tmp_file, 'w', encoding='utf-8') as f:
                    f.write(code)
                cmd = [self._shell_path, '/c', tmp_file]
            else:
                suffix = '.sh'
                tmp_fd, tmp_file = tempfile.mkstemp(suffix=suffix, prefix='vpyd_sh_')
                os.close(tmp_fd)
                with open(tmp_file, 'w', encoding='utf-8', newline='\n') as f:
                    f.write(code)
                cmd = [self._shell_path, tmp_file]
            proc = _run_subprocess(cmd, capture_output=True, text=True, timeout=self.TIMEOUT_SECONDS)

            execution_time = time.time() - start_time
            output = proc.stdout or ''
            error_text = proc.stderr or ''

            if proc.returncode != 0:
                return ExecutionResult(success=False, output=output,
                    error=Exception(error_text.strip() or f'Shell exited with code {proc.returncode}'),
                    execution_time=execution_time)

            return ExecutionResult(success=True, output=output, variables={}, execution_time=execution_time)
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, error=Exception(f'Shell execution timed out after {self.TIMEOUT_SECONDS}s'),
                                  execution_time=time.time() - start_time)
        except Exception as e:
            return ExecutionResult(success=False, error=e, execution_time=time.time() - start_time)
        finally:
            if tmp_file and os.path.exists(tmp_file):
                try: os.unlink(tmp_file)
                except OSError: pass

    def execute_single_statement(self, statement: str) -> ExecutionResult:
        return self.execute(statement)

    def reset_namespace(self): pass
    def set_variable_value(self, variable_name, value): pass
    def get_variable_value(self, variable_name): return None

    @staticmethod
    def _bash_to_powershell(code: str) -> str:
        """Best-effort translation of simple bash scripts to PowerShell.
        
        Handles: echo, variable assignment, command -v, for loops (simple),
        shebang stripping, and common builtins.
        """
        import re
        lines = code.split('\n')
        out = []
        for line in lines:
            stripped = line.strip()
            # Strip shebang
            if stripped.startswith('#!'):
                out.append('# ' + stripped)
                continue
            # Comments
            if stripped.startswith('#'):
                out.append(line)
                continue
            # Skip empty
            if not stripped:
                out.append('')
                continue

            # ── for i in $(seq ...) one-liner → PowerShell foreach ──
            m = re.match(
                r'for\s+(\w+)\s+in\s+\$\(seq\s+(\d+)\s+(\d+)\);\s*do\s+(.*?);\s*done',
                stripped)
            if m:
                var, lo, hi, body = m.group(1), m.group(2), m.group(3), m.group(4)
                # translate body: VAR=$((VAR + i)) → $VAR = $VAR + $i
                ps_body = re.sub(
                    r'([A-Z_][A-Z0-9_]*)=\$\(\((.*?)\)\)',
                    lambda mb: f'${mb.group(1)} = ' + re.sub(r'\b([A-Za-z_]\w*)\b',
                        lambda mv: f'${mv.group(1)}', mb.group(2)),
                    body)
                # catch simple VAR=expr without $((...))
                ps_body = re.sub(
                    r'^([A-Z_][A-Z0-9_]*)=(.+)',
                    lambda mb: f'${mb.group(1)} = {mb.group(2)}',
                    ps_body)
                out.append(f'foreach (${var} in {lo}..{hi}) {{ {ps_body} }}')
                continue

            # echo → Write-Host
            if stripped.startswith('echo '):
                content = stripped[5:]
                # Remove bash quoting
                if (content.startswith("'") and content.endswith("'")) or \
                   (content.startswith('"') and content.endswith('"')):
                    content = content[1:-1]
                # Replace embedded $(nproc) with PowerShell equivalent
                content = content.replace('$(nproc)', '$env:NUMBER_OF_PROCESSORS')
                # Replace embedded $(hostname) — works in PS already
                # Replace embedded $(date) → $(Get-Date -Format …)
                content = re.sub(
                    r'\$\(date\)',
                    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
                    content)
                # Replace embedded $(uname …)
                content = re.sub(
                    r'\$\(uname[^)]*\)',
                    '$([System.Environment]::OSVersion.VersionString)',
                    content)
                out.append(f'Write-Host "{content}"')
                continue
            # command -v → Get-Command
            m = re.match(r'if\s+command\s+-v\s+(\S+)', stripped)
            if m or 'command -v' in stripped:
                # Skip complex bash conditionals — just output comment
                out.append(f'# (skipped bash-specific) {stripped}')
                continue
            # Variable assignment: VAR=value → $VAR = value
            m = re.match(r'^([A-Z_][A-Z0-9_]*)=(.*)', stripped)
            if m:
                out.append(f'${m.group(1)} = {m.group(2)}')
                continue
            # $(command) → already valid in PS
            # hostname → works in PS
            # date → Get-Date
            if stripped == 'date' or stripped.startswith('date '):
                out.append('Get-Date -Format "yyyy-MM-dd HH:mm:ss"')
                continue
            # nproc → number of processors
            if stripped == 'nproc' or 'nproc' in stripped:
                out.append('$env:NUMBER_OF_PROCESSORS')
                continue
            # uname → $env:OS
            if 'uname' in stripped:
                out.append('[System.Environment]::OSVersion.VersionString')
                continue
            # Pass through — many things work in both
            out.append(line)
        return '\n'.join(out)


# =========================================================================
# C EXECUTOR — gcc/cc compile + run
# =========================================================================

class CExecutor:
    """Compiles C code with gcc/cc and runs the resulting binary."""

    COMPILE_TIMEOUT = 60
    RUN_TIMEOUT = 30

    def __init__(self):
        self._cc_path: Optional[str] = shutil.which('gcc') or shutil.which('cc')

    def execute(self, code: str, capture_output: bool = True) -> ExecutionResult:
        if not self._cc_path:
            return ExecutionResult(success=False, error=Exception(
                'gcc/cc not found on PATH — install a C compiler (MinGW, build-essential, Xcode CLI, etc.)'))

        start_time = time.time()
        tmp_dir = None
        try:
            tmp_dir = tempfile.mkdtemp(prefix='vpyd_c_')
            src_path = os.path.join(tmp_dir, 'main.c')
            bin_path = os.path.join(tmp_dir, 'main.exe' if sys.platform == 'win32' else 'main')

            with open(src_path, 'w', encoding='utf-8') as f:
                f.write(code)

            comp = _run_subprocess([self._cc_path, src_path, '-o', bin_path, '-lm'],
                                  capture_output=True, text=True, timeout=self.COMPILE_TIMEOUT)
            if comp.returncode != 0:
                return ExecutionResult(success=False, output=comp.stdout or '',
                    error=Exception(f'Compilation failed:\n{comp.stderr.strip()}'),
                    execution_time=time.time() - start_time)

            run = _run_subprocess([bin_path], capture_output=True, text=True, timeout=self.RUN_TIMEOUT)
            execution_time = time.time() - start_time

            if run.returncode != 0:
                return ExecutionResult(success=False, output=run.stdout or '',
                    error=Exception(run.stderr.strip() or f'C binary exited with code {run.returncode}'),
                    execution_time=execution_time)

            return ExecutionResult(success=True, output=run.stdout or '', variables={}, execution_time=execution_time)
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, error=Exception('C compilation/execution timed out'),
                                  execution_time=time.time() - start_time)
        except Exception as e:
            return ExecutionResult(success=False, error=e, execution_time=time.time() - start_time)
        finally:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def execute_single_statement(self, s): return self.execute(s)
    def reset_namespace(self): pass
    def set_variable_value(self, n, v): pass
    def get_variable_value(self, n): return None


# =========================================================================
# C++ EXECUTOR — g++/c++ compile + run
# =========================================================================

class CppExecutor:
    """Compiles C++ code with g++ and runs the resulting binary."""

    COMPILE_TIMEOUT = 60
    RUN_TIMEOUT = 30

    def __init__(self):
        self._cxx_path: Optional[str] = shutil.which('g++') or shutil.which('c++') or shutil.which('clang++')

    def execute(self, code: str, capture_output: bool = True) -> ExecutionResult:
        if not self._cxx_path:
            return ExecutionResult(success=False, error=Exception(
                'g++/c++/clang++ not found on PATH — install a C++ compiler'))

        start_time = time.time()
        tmp_dir = None
        try:
            tmp_dir = tempfile.mkdtemp(prefix='vpyd_cpp_')
            src_path = os.path.join(tmp_dir, 'main.cpp')
            bin_path = os.path.join(tmp_dir, 'main.exe' if sys.platform == 'win32' else 'main')

            with open(src_path, 'w', encoding='utf-8') as f:
                f.write(code)

            comp = _run_subprocess([self._cxx_path, src_path, '-o', bin_path, '-std=c++17'],
                                  capture_output=True, text=True, timeout=self.COMPILE_TIMEOUT)
            if comp.returncode != 0:
                return ExecutionResult(success=False, output=comp.stdout or '',
                    error=Exception(f'Compilation failed:\n{comp.stderr.strip()}'),
                    execution_time=time.time() - start_time)

            run = _run_subprocess([bin_path], capture_output=True, text=True, timeout=self.RUN_TIMEOUT)
            execution_time = time.time() - start_time

            if run.returncode != 0:
                return ExecutionResult(success=False, output=run.stdout or '',
                    error=Exception(run.stderr.strip() or f'C++ binary exited with code {run.returncode}'),
                    execution_time=execution_time)

            return ExecutionResult(success=True, output=run.stdout or '', variables={}, execution_time=execution_time)
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, error=Exception('C++ compilation/execution timed out'),
                                  execution_time=time.time() - start_time)
        except Exception as e:
            return ExecutionResult(success=False, error=e, execution_time=time.time() - start_time)
        finally:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def execute_single_statement(self, s): return self.execute(s)
    def reset_namespace(self): pass
    def set_variable_value(self, n, v): pass
    def get_variable_value(self, n): return None


# =========================================================================
# GO EXECUTOR — go run
# =========================================================================

class GoExecutor:
    """Executes Go code via `go run`."""

    TIMEOUT_SECONDS = 30

    def __init__(self):
        self._go_path: Optional[str] = shutil.which('go')

    def execute(self, code: str, capture_output: bool = True) -> ExecutionResult:
        if not self._go_path:
            return ExecutionResult(success=False, error=Exception(
                'go not found on PATH — install the Go toolchain'))

        start_time = time.time()
        tmp_dir = None
        try:
            tmp_dir = tempfile.mkdtemp(prefix='vpyd_go_')
            src_path = os.path.join(tmp_dir, 'main.go')

            with open(src_path, 'w', encoding='utf-8') as f:
                f.write(code)

            proc = _run_subprocess([self._go_path, 'run', src_path],
                                  capture_output=True, text=True, timeout=self.TIMEOUT_SECONDS)
            execution_time = time.time() - start_time

            if proc.returncode != 0:
                return ExecutionResult(success=False, output=proc.stdout or '',
                    error=Exception(proc.stderr.strip() or f'go run exited with code {proc.returncode}'),
                    execution_time=execution_time)

            return ExecutionResult(success=True, output=proc.stdout or '', variables={}, execution_time=execution_time)
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, error=Exception('Go execution timed out'),
                                  execution_time=time.time() - start_time)
        except Exception as e:
            return ExecutionResult(success=False, error=e, execution_time=time.time() - start_time)
        finally:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def execute_single_statement(self, s): return self.execute(s)
    def reset_namespace(self): pass
    def set_variable_value(self, n, v): pass
    def get_variable_value(self, n): return None


# =========================================================================
# JAVA EXECUTOR — javac + java
# =========================================================================

class JavaExecutor:
    """Compiles and runs Java code via javac + java.

    Expects a class with a main method.  The class name is auto-detected
    from the source code or defaults to ``Main``.
    """

    COMPILE_TIMEOUT = 60
    RUN_TIMEOUT = 30

    def __init__(self):
        self._javac_path: Optional[str] = shutil.which('javac')
        self._java_path: Optional[str] = shutil.which('java')

    def execute(self, code: str, capture_output: bool = True) -> ExecutionResult:
        if not self._javac_path or not self._java_path:
            return ExecutionResult(success=False, error=Exception(
                'javac/java not found on PATH — install a JDK'))

        start_time = time.time()
        tmp_dir = None
        try:
            # Try to detect the public class name
            import re
            match = re.search(r'public\s+class\s+(\w+)', code)
            class_name = match.group(1) if match else 'Main'

            tmp_dir = tempfile.mkdtemp(prefix='vpyd_java_')
            src_path = os.path.join(tmp_dir, f'{class_name}.java')

            with open(src_path, 'w', encoding='utf-8') as f:
                f.write(code)

            comp = _run_subprocess([self._javac_path, '-encoding', 'UTF-8', src_path],
                                  capture_output=True, text=True, timeout=self.COMPILE_TIMEOUT)
            if comp.returncode != 0:
                return ExecutionResult(success=False, output=comp.stdout or '',
                    error=Exception(f'Compilation failed:\n{comp.stderr.strip()}'),
                    execution_time=time.time() - start_time)

            run = _run_subprocess([self._java_path, '-Dstdout.encoding=UTF-8',
                                   '-Dstderr.encoding=UTF-8', '-cp', tmp_dir, class_name],
                                 capture_output=True, text=True, timeout=self.RUN_TIMEOUT)
            execution_time = time.time() - start_time

            if run.returncode != 0:
                return ExecutionResult(success=False, output=run.stdout or '',
                    error=Exception(run.stderr.strip() or f'Java exited with code {run.returncode}'),
                    execution_time=execution_time)

            return ExecutionResult(success=True, output=run.stdout or '', variables={}, execution_time=execution_time)
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, error=Exception('Java compilation/execution timed out'),
                                  execution_time=time.time() - start_time)
        except Exception as e:
            return ExecutionResult(success=False, error=e, execution_time=time.time() - start_time)
        finally:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def execute_single_statement(self, s): return self.execute(s)
    def reset_namespace(self): pass
    def set_variable_value(self, n, v): pass
    def get_variable_value(self, n): return None


# =========================================================================
# RUBY EXECUTOR — ruby subprocess
# =========================================================================

class RubyExecutor:
    """Executes Ruby code via the ruby interpreter."""

    TIMEOUT_SECONDS = 30

    def __init__(self):
        self._ruby_path: Optional[str] = shutil.which('ruby')

    def execute(self, code: str, capture_output: bool = True) -> ExecutionResult:
        if not self._ruby_path:
            return ExecutionResult(success=False, error=Exception(
                'ruby not found on PATH — install Ruby'))

        start_time = time.time()
        tmp_file = None
        try:
            tmp_fd, tmp_file = tempfile.mkstemp(suffix='.rb', prefix='vpyd_rb_')
            os.close(tmp_fd)
            with open(tmp_file, 'w', encoding='utf-8') as f:
                f.write(code)

            proc = _run_subprocess([self._ruby_path, tmp_file],
                                  capture_output=True, text=True, timeout=self.TIMEOUT_SECONDS)
            execution_time = time.time() - start_time

            if proc.returncode != 0:
                return ExecutionResult(success=False, output=proc.stdout or '',
                    error=Exception(proc.stderr.strip() or f'Ruby exited with code {proc.returncode}'),
                    execution_time=execution_time)

            return ExecutionResult(success=True, output=proc.stdout or '', variables={}, execution_time=execution_time)
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, error=Exception('Ruby execution timed out'),
                                  execution_time=time.time() - start_time)
        except Exception as e:
            return ExecutionResult(success=False, error=e, execution_time=time.time() - start_time)
        finally:
            if tmp_file and os.path.exists(tmp_file):
                try: os.unlink(tmp_file)
                except OSError: pass

    def execute_single_statement(self, s): return self.execute(s)
    def reset_namespace(self): pass
    def set_variable_value(self, n, v): pass
    def get_variable_value(self, n): return None


# =========================================================================
# R EXECUTOR — Rscript subprocess
# =========================================================================

class RExecutor:
    """Executes R code via Rscript."""

    TIMEOUT_SECONDS = 30

    def __init__(self):
        self._rscript_path: Optional[str] = shutil.which('Rscript')

    def execute(self, code: str, capture_output: bool = True) -> ExecutionResult:
        if not self._rscript_path:
            return ExecutionResult(success=False, error=Exception(
                'Rscript not found on PATH — install R'))

        start_time = time.time()
        tmp_file = None
        try:
            tmp_fd, tmp_file = tempfile.mkstemp(suffix='.R', prefix='vpyd_r_')
            os.close(tmp_fd)
            with open(tmp_file, 'w', encoding='utf-8') as f:
                f.write(code)

            proc = _run_subprocess([self._rscript_path, tmp_file],
                                  capture_output=True, text=True, timeout=self.TIMEOUT_SECONDS)
            execution_time = time.time() - start_time

            if proc.returncode != 0:
                return ExecutionResult(success=False, output=proc.stdout or '',
                    error=Exception(proc.stderr.strip() or f'Rscript exited with code {proc.returncode}'),
                    execution_time=execution_time)

            return ExecutionResult(success=True, output=proc.stdout or '', variables={}, execution_time=execution_time)
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, error=Exception('R execution timed out'),
                                  execution_time=time.time() - start_time)
        except Exception as e:
            return ExecutionResult(success=False, error=e, execution_time=time.time() - start_time)
        finally:
            if tmp_file and os.path.exists(tmp_file):
                try: os.unlink(tmp_file)
                except OSError: pass

    def execute_single_statement(self, s): return self.execute(s)
    def reset_namespace(self): pass
    def set_variable_value(self, n, v): pass
    def get_variable_value(self, n): return None


# =========================================================================
# C# EXECUTOR — dotnet-script or csc + mono / .NET
# =========================================================================

class CSharpExecutor:
    """Executes C# code.

    Strategy priority:
      1. ``dotnet-script`` (if installed — simplest, script-style)
      2. ``dotnet`` CLI (create temp console app, ``dotnet run``)
      3. ``csc`` / ``mcs`` compile + run directly
    """

    COMPILE_TIMEOUT = 60
    RUN_TIMEOUT = 30

    def __init__(self):
        self._dotnet_script: Optional[str] = shutil.which('dotnet-script')
        self._dotnet_path: Optional[str] = shutil.which('dotnet')
        self._csc_path: Optional[str] = shutil.which('csc') or shutil.which('mcs')

    def execute(self, code: str, capture_output: bool = True) -> ExecutionResult:
        if self._dotnet_script:
            return self._run_dotnet_script(code)
        elif self._csc_path:
            return self._run_csc(code)
        elif self._dotnet_path:
            return self._run_dotnet_run(code)
        else:
            return ExecutionResult(success=False, error=Exception(
                'No C# toolchain found — install .NET SDK, dotnet-script, or Mono'))

    def _run_dotnet_script(self, code: str) -> ExecutionResult:
        start_time = time.time()
        tmp_file = None
        try:
            tmp_fd, tmp_file = tempfile.mkstemp(suffix='.csx', prefix='vpyd_cs_')
            os.close(tmp_fd)
            with open(tmp_file, 'w', encoding='utf-8') as f:
                f.write(code)
            proc = _run_subprocess([self._dotnet_script, tmp_file],
                                  capture_output=True, text=True, timeout=self.RUN_TIMEOUT)
            execution_time = time.time() - start_time
            if proc.returncode != 0:
                return ExecutionResult(success=False, output=proc.stdout or '',
                    error=Exception(proc.stderr.strip() or f'dotnet-script exited with code {proc.returncode}'),
                    execution_time=execution_time)
            return ExecutionResult(success=True, output=proc.stdout or '', variables={}, execution_time=execution_time)
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, error=Exception('C# execution timed out'),
                                  execution_time=time.time() - start_time)
        except Exception as e:
            return ExecutionResult(success=False, error=e, execution_time=time.time() - start_time)
        finally:
            if tmp_file and os.path.exists(tmp_file):
                try: os.unlink(tmp_file)
                except OSError: pass

    def _run_csc(self, code: str) -> ExecutionResult:
        start_time = time.time()
        tmp_dir = None
        try:
            tmp_dir = tempfile.mkdtemp(prefix='vpyd_cs_')
            src_path = os.path.join(tmp_dir, 'Program.cs')
            bin_path = os.path.join(tmp_dir, 'Program.exe')

            with open(src_path, 'w', encoding='utf-8') as f:
                f.write(code)

            comp = _run_subprocess([self._csc_path, f'-out:{bin_path}', src_path],
                                  capture_output=True, text=True, timeout=self.COMPILE_TIMEOUT)
            if comp.returncode != 0:
                return ExecutionResult(success=False, output=comp.stdout or '',
                    error=Exception(f'Compilation failed:\n{comp.stderr.strip()}'),
                    execution_time=time.time() - start_time)

            # On Windows the .exe runs directly; on Linux/Mac use mono
            run_cmd = [bin_path] if sys.platform == 'win32' else ['mono', bin_path]
            run = _run_subprocess(run_cmd, capture_output=True, text=True, timeout=self.RUN_TIMEOUT)
            execution_time = time.time() - start_time
            if run.returncode != 0:
                return ExecutionResult(success=False, output=run.stdout or '',
                    error=Exception(run.stderr.strip() or f'C# exited with code {run.returncode}'),
                    execution_time=execution_time)
            return ExecutionResult(success=True, output=run.stdout or '', variables={}, execution_time=execution_time)
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, error=Exception('C# compilation/execution timed out'),
                                  execution_time=time.time() - start_time)
        except Exception as e:
            return ExecutionResult(success=False, error=e, execution_time=time.time() - start_time)
        finally:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def _run_dotnet_run(self, code: str) -> ExecutionResult:
        """Create a throwaway console project, write code, dotnet run."""
        start_time = time.time()
        tmp_dir = None
        try:
            tmp_dir = tempfile.mkdtemp(prefix='vpyd_cs_')
            # Scaffold a console project
            _run_subprocess([self._dotnet_path, 'new', 'console', '-o', tmp_dir, '--force'],
                           capture_output=True, text=True, timeout=self.COMPILE_TIMEOUT)
            prog_path = os.path.join(tmp_dir, 'Program.cs')
            with open(prog_path, 'w', encoding='utf-8') as f:
                f.write(code)
            proc = _run_subprocess([self._dotnet_path, 'run', '--project', tmp_dir],
                                  capture_output=True, text=True, timeout=self.RUN_TIMEOUT + self.COMPILE_TIMEOUT)
            execution_time = time.time() - start_time
            if proc.returncode != 0:
                return ExecutionResult(success=False, output=proc.stdout or '',
                    error=Exception(proc.stderr.strip() or f'dotnet run exited with code {proc.returncode}'),
                    execution_time=execution_time)
            return ExecutionResult(success=True, output=proc.stdout or '', variables={}, execution_time=execution_time)
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, error=Exception('C# execution timed out'),
                                  execution_time=time.time() - start_time)
        except Exception as e:
            return ExecutionResult(success=False, error=e, execution_time=time.time() - start_time)
        finally:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def execute_single_statement(self, s): return self.execute(s)
    def reset_namespace(self): pass
    def set_variable_value(self, n, v): pass
    def get_variable_value(self, n): return None


# =========================================================================
# KOTLIN EXECUTOR — kotlinc -script  or  kotlin
# =========================================================================

class KotlinExecutor:
    """Executes Kotlin code via kotlinc scripting mode or kotlin CLI."""

    TIMEOUT_SECONDS = 60  # Kotlin compiler is slow on first run

    def __init__(self):
        self._kotlinc_path: Optional[str] = shutil.which('kotlinc')
        self._kotlin_path: Optional[str] = shutil.which('kotlin')

    def execute(self, code: str, capture_output: bool = True) -> ExecutionResult:
        if not self._kotlinc_path and not self._kotlin_path:
            return ExecutionResult(success=False, error=Exception(
                'kotlinc/kotlin not found on PATH — install the Kotlin compiler'))

        start_time = time.time()
        tmp_file = None
        try:
            tmp_fd, tmp_file = tempfile.mkstemp(suffix='.kts', prefix='vpyd_kt_')
            os.close(tmp_fd)
            with open(tmp_file, 'w', encoding='utf-8') as f:
                f.write(code)

            # Prefer kotlinc -script for .kts files
            cmd = [self._kotlinc_path, '-script', tmp_file] if self._kotlinc_path else [self._kotlin_path, tmp_file]
            proc = _run_subprocess(cmd, capture_output=True, text=True, timeout=self.TIMEOUT_SECONDS)
            execution_time = time.time() - start_time

            if proc.returncode != 0:
                return ExecutionResult(success=False, output=proc.stdout or '',
                    error=Exception(proc.stderr.strip() or f'Kotlin exited with code {proc.returncode}'),
                    execution_time=execution_time)

            return ExecutionResult(success=True, output=proc.stdout or '', variables={}, execution_time=execution_time)
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, error=Exception('Kotlin execution timed out'),
                                  execution_time=time.time() - start_time)
        except Exception as e:
            return ExecutionResult(success=False, error=e, execution_time=time.time() - start_time)
        finally:
            if tmp_file and os.path.exists(tmp_file):
                try: os.unlink(tmp_file)
                except OSError: pass

    def execute_single_statement(self, s): return self.execute(s)
    def reset_namespace(self): pass
    def set_variable_value(self, n, v): pass
    def get_variable_value(self, n): return None


# =========================================================================
# SWIFT EXECUTOR — swift subprocess
# =========================================================================

class SwiftExecutor:
    """Executes Swift code via the swift interpreter / compiler."""

    TIMEOUT_SECONDS = 30

    def __init__(self):
        self._swift_path: Optional[str] = shutil.which('swift')

    def execute(self, code: str, capture_output: bool = True) -> ExecutionResult:
        if not self._swift_path:
            return ExecutionResult(success=False, error=Exception(
                'swift not found on PATH — install the Swift toolchain (Xcode CLI or swift.org)'))

        start_time = time.time()
        tmp_file = None
        try:
            tmp_fd, tmp_file = tempfile.mkstemp(suffix='.swift', prefix='vpyd_sw_')
            os.close(tmp_fd)
            with open(tmp_file, 'w', encoding='utf-8') as f:
                f.write(code)

            proc = _run_subprocess([self._swift_path, tmp_file],
                                  capture_output=True, text=True, timeout=self.TIMEOUT_SECONDS)
            execution_time = time.time() - start_time

            if proc.returncode != 0:
                return ExecutionResult(success=False, output=proc.stdout or '',
                    error=Exception(proc.stderr.strip() or f'Swift exited with code {proc.returncode}'),
                    execution_time=execution_time)

            return ExecutionResult(success=True, output=proc.stdout or '', variables={}, execution_time=execution_time)
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, error=Exception('Swift execution timed out'),
                                  execution_time=time.time() - start_time)
        except Exception as e:
            return ExecutionResult(success=False, error=e, execution_time=time.time() - start_time)
        finally:
            if tmp_file and os.path.exists(tmp_file):
                try: os.unlink(tmp_file)
                except OSError: pass

    def execute_single_statement(self, s): return self.execute(s)
    def reset_namespace(self): pass
    def set_variable_value(self, n, v): pass
    def get_variable_value(self, n): return None


# =========================================================================
# PERL EXECUTOR — perl subprocess (Strawberry Perl / system perl)
# =========================================================================

class PerlExecutor:
    """Executes Perl code via the perl interpreter.

    Searches PATH first, then well-known Windows install locations
    (Strawberry Perl, ActivePerl).
    """

    TIMEOUT_SECONDS = 30

    _EXTRA_SEARCH = [
        r'c:\strawberry\perl\bin\perl.exe',
        r'c:\Perl64\bin\perl.exe',
        r'c:\Perl\bin\perl.exe',
    ]

    def __init__(self):
        self._perl_path: Optional[str] = shutil.which('perl')
        if not self._perl_path:
            for candidate in self._EXTRA_SEARCH:
                if os.path.isfile(candidate):
                    self._perl_path = candidate
                    break

    def execute(self, code: str, capture_output: bool = True) -> ExecutionResult:
        if not self._perl_path:
            return ExecutionResult(success=False, error=Exception(
                'perl not found on PATH or in standard install locations — '
                'install Strawberry Perl (https://strawberryperl.com)'))

        start_time = time.time()
        tmp_file = None
        try:
            tmp_fd, tmp_file = tempfile.mkstemp(suffix='.pl', prefix='vpyd_pl_')
            os.close(tmp_fd)
            with open(tmp_file, 'w', encoding='utf-8') as f:
                f.write(code)

            proc = _run_subprocess(
                [self._perl_path, tmp_file],
                capture_output=True, text=True, timeout=self.TIMEOUT_SECONDS)
            execution_time = time.time() - start_time

            if proc.returncode != 0:
                return ExecutionResult(
                    success=False, output=proc.stdout or '',
                    error=Exception(proc.stderr.strip() or
                                    f'Perl exited with code {proc.returncode}'),
                    execution_time=execution_time)

            return ExecutionResult(
                success=True, output=proc.stdout or '',
                variables={}, execution_time=execution_time)
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False,
                error=Exception('Perl execution timed out'),
                execution_time=time.time() - start_time)
        except Exception as e:
            return ExecutionResult(success=False, error=e,
                                  execution_time=time.time() - start_time)
        finally:
            if tmp_file and os.path.exists(tmp_file):
                try: os.unlink(tmp_file)
                except OSError: pass

    def execute_single_statement(self, s): return self.execute(s)
    def reset_namespace(self): pass
    def set_variable_value(self, n, v): pass
    def get_variable_value(self, n): return None


# =========================================================================
# TYPESCRIPT EXECUTOR — ts-node or npx tsx
# =========================================================================

class TypeScriptExecutor:
    """Executes TypeScript code via ts-node, tsx, or npx tsx.

    Falls back to the JavaScript executor (Node.js) if no TS runner is found,
    which handles plain-JS-compatible TS code.
    """

    TIMEOUT_SECONDS = 30

    def __init__(self):
        self._tsx_path: Optional[str] = shutil.which('tsx')
        self._tsnode_path: Optional[str] = shutil.which('ts-node')
        self._npx_path: Optional[str] = shutil.which('npx')
        self._node_path: Optional[str] = shutil.which('node')

    def execute(self, code: str, capture_output: bool = True) -> ExecutionResult:
        start_time = time.time()
        tmp_file = None

        # Determine runner command
        if self._tsx_path:
            runner = [self._tsx_path]
        elif self._tsnode_path:
            # --transpile-only skips type-checker which avoids the
            # "export {};" injection that causes SyntaxError on Windows.
            # Explicit --compiler-options overrides any tsconfig.json that
            # may set isolatedModules or an incompatible module format.
            runner = [self._tsnode_path, '--transpile-only',
                      '-O', '{"module":"commonjs","target":"es2020"}']
        elif self._npx_path:
            runner = [self._npx_path, 'tsx']
        elif self._node_path:
            # Fallback: strip type annotations wouldn't work well, but try node
            runner = [self._node_path]
        else:
            return ExecutionResult(success=False, error=Exception(
                'No TypeScript runner found — install tsx, ts-node, or Node.js'))

        try:
            suffix = '.ts' if runner[0] != self._node_path else '.js'
            tmp_fd, tmp_file = tempfile.mkstemp(suffix=suffix, prefix='vpyd_ts_')
            os.close(tmp_fd)
            with open(tmp_file, 'w', encoding='utf-8') as f:
                f.write(code)

            proc = _run_subprocess(runner + [tmp_file],
                                  capture_output=True, text=True, timeout=self.TIMEOUT_SECONDS)
            execution_time = time.time() - start_time

            if proc.returncode != 0:
                return ExecutionResult(success=False, output=proc.stdout or '',
                    error=Exception(proc.stderr.strip() or f'TypeScript runner exited with code {proc.returncode}'),
                    execution_time=execution_time)

            return ExecutionResult(success=True, output=proc.stdout or '', variables={}, execution_time=execution_time)
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, error=Exception('TypeScript execution timed out'),
                                  execution_time=time.time() - start_time)
        except Exception as e:
            return ExecutionResult(success=False, error=e, execution_time=time.time() - start_time)
        finally:
            if tmp_file and os.path.exists(tmp_file):
                try: os.unlink(tmp_file)
                except OSError: pass

    def execute_single_statement(self, s): return self.execute(s)
    def reset_namespace(self): pass
    def set_variable_value(self, n, v): pass
    def get_variable_value(self, n): return None


# =========================================================================
# EXECUTOR REGISTRY — language string → executor class mapping
# =========================================================================

# Canonical mapping used by runtime.py to dispatch execution by language.
EXECUTOR_CLASSES: Dict[str, type] = {
    'python':     PythonExecutor,
    'javascript': JavaScriptExecutor,
    'typescript': TypeScriptExecutor,
    'rust':       RustExecutor,
    'bash':       BashExecutor,
    'c':          CExecutor,
    'cpp':        CppExecutor,
    'go':         GoExecutor,
    'java':       JavaExecutor,
    'ruby':       RubyExecutor,
    'r':          RExecutor,
    'csharp':     CSharpExecutor,
    'kotlin':     KotlinExecutor,
    'swift':      SwiftExecutor,
    'perl':       PerlExecutor,
}

# Languages that share an executor — kept as fallback aliases.
EXECUTOR_ALIASES: Dict[str, str] = {
    # No aliases needed now that TypeScript has its own executor.
    # If ts-node/tsx aren't installed, TypeScriptExecutor falls back to Node.
}


def get_executor_for_language(language: str):
    """Return a *new* executor instance for the given language string.

    Returns None if the language is not supported for live execution.
    """
    lang = language.lower().strip()
    lang = EXECUTOR_ALIASES.get(lang, lang)
    cls = EXECUTOR_CLASSES.get(lang)
    if cls is None:
        return None
    return cls()


def get_supported_languages() -> List[str]:
    """Return the list of languages that have a live executor."""
    langs = list(EXECUTOR_CLASSES.keys())
    langs.extend(EXECUTOR_ALIASES.keys())
    return sorted(set(langs))


class ExecutionStateTracker:
    """Tracks the state of program execution."""
    
    def __init__(self):
        self.current_state = ExecutionState()
        self.execution_stack: List[ExecutionState] = []
        self.node_execution_order: List[str] = []
        self.execution_callbacks: List[Callable[[ExecutionState], None]] = []
    
    def update_state(self, node_id: str, variables: Dict[str, Any], line_number: int = 0):
        """Update the current execution state."""
        self.current_state.current_node = node_id
        self.current_state.variables.update(variables)
        self.current_state.line_number = line_number
        
        # Record execution order
        self.node_execution_order.append(node_id)
        
        # Notify callbacks
        for callback in self.execution_callbacks:
            callback(self.current_state)
    
    def push_state(self, state: ExecutionState):
        """Push a state onto the execution stack."""
        self.execution_stack.append(state.copy())
    
    def pop_state(self) -> Optional[ExecutionState]:
        """Pop a state from the execution stack."""
        if self.execution_stack:
            return self.execution_stack.pop()
        return None
    
    def get_execution_history(self) -> List[str]:
        """Get the history of node execution."""
        return self.node_execution_order.copy()
    
    def add_execution_callback(self, callback: Callable[[ExecutionState], None]):
        """Add a callback to be called when state changes."""
        self.execution_callbacks.append(callback)
    
    def clear_history(self):
        """Clear execution history."""
        self.node_execution_order.clear()
        self.execution_stack.clear()


class ExecutionEngine:
    """Provides live execution capabilities with debugging support."""
    
    def __init__(self):
        self.debugger = VisualDebugger()
        self.executor = PythonExecutor()
        self.state_tracker = ExecutionStateTracker()
        self.data_flow_visualizer: Optional[DataFlowVisualizer] = None
        self.is_executing = False
        self.should_stop = False
        self.hot_reload_enabled = False
        self.debug_mode = False
        self.step_execution_callback: Optional[Callable[[str, ExecutionState], None]] = None
        self.data_flow_enabled = True
    
    def execute_model(self, model: VisualModel) -> ExecutionResult:
        """Execute a visual model and return the result."""
        if self.is_executing:
            return ExecutionResult(success=False, error=Exception("Execution already in progress"))
        
        self.is_executing = True
        self.should_stop = False
        
        # Initialize data flow visualizer if not set
        if self.data_flow_visualizer is None and self.data_flow_enabled:
            self.data_flow_visualizer = DataFlowVisualizer(model)
        
        try:
            # Validate model first
            validation_errors = model.validate_model()
            if validation_errors:
                error_msg = f"Model validation failed: {'; '.join(str(e) for e in validation_errors)}"
                return ExecutionResult(success=False, error=Exception(error_msg))
            
            if self.debug_mode:
                return self._execute_model_with_debugging(model)
            else:
                return self._execute_model_normal(model)
            
        except Exception as e:
            return ExecutionResult(success=False, error=e)
        finally:
            self.is_executing = False
    
    def _execute_model_normal(self, model: VisualModel) -> ExecutionResult:
        """Execute model in normal mode without debugging."""
        # Generate Python code from the visual model
        from .ast_processor import ASTProcessor
        from .code_generator import CodeGenerator
        
        processor = ASTProcessor()
        generator = CodeGenerator()
        
        # Convert visual model to AST
        ast_tree = processor.visual_to_ast(model)
        
        # Generate Python code
        code = generator.generate_code(ast_tree, {
            'add_type_hints': False,  # Keep simple for execution
            'add_docstrings': False,
            'format_code': True,
            'optimize_code': True
        }, visual_model=model)
        
        # Execute the generated code
        result = self.executor.execute(code, capture_output=True)
        
        # Update state tracker with final state
        if result.success:
            self.state_tracker.update_state(
                node_id="execution_complete",
                variables=result.variables
            )
        
        return result
    
    def _execute_model_with_debugging(self, model: VisualModel) -> ExecutionResult:
        """Execute model with debugging support."""
        # Get execution order
        execution_order = model.get_execution_order()
        if not execution_order:
            return ExecutionResult(success=False, error=Exception("Cannot determine execution order"))
        
        # Execute nodes one by one with debugging
        for node_id in execution_order:
            if self.should_stop:
                break
            
            node = model.nodes[node_id]
            
            # Check if we should pause at this node
            if self.debugger.should_pause_at_node(node_id):
                self.debugger.highlight_current_node(node_id)
                
                # Call step execution callback if set
                if self.step_execution_callback:
                    self.step_execution_callback(node_id, self.state_tracker.current_state)
                
                # Wait for user to continue (in a real implementation, this would be event-driven)
                # For now, we'll just continue
                pass
            
            # Execute the node
            result = self.execute_node(node, model)
            
            # Update data flow visualization for outgoing connections
            if self.data_flow_visualizer and result.success:
                self._update_data_flow_for_node(node_id, model, result.variables)
            
            # Record execution trace
            self.debugger.add_execution_trace(
                node_id=node_id,
                node_type=node.type.value,
                operation="execute",
                variables=self.state_tracker.current_state.variables,
                result=result.output if result.success else str(result.error)
            )
            
            if not result.success:
                return result
        
        return ExecutionResult(success=True, output="Debug execution completed")
    
    def execute_node(self, node: VisualNode, model: VisualModel) -> ExecutionResult:
        """Execute a single visual node."""
        try:
            # Highlight current node for debugging
            self.debugger.highlight_current_node(node.id)
            
            # Generate code for just this node
            from .ast_processor import ASTProcessor
            from .code_generator import CodeGenerator
            
            # Create a temporary model with just this node
            temp_model = VisualModel()
            temp_model.add_node(node)
            
            processor = ASTProcessor()
            generator = CodeGenerator()
            
            ast_tree = processor.visual_to_ast(temp_model)
            code = generator.generate_code(ast_tree)
            
            # Track variable values before execution
            old_variables = self.executor.local_namespace.copy()
            
            # Execute the node's code
            result = self.executor.execute_single_statement(code)
            
            # Track variable modifications
            if result.success:
                new_variables = self.executor.local_namespace
                for var_name, new_value in new_variables.items():
                    old_value = old_variables.get(var_name, '<undefined>')
                    if old_value != new_value:
                        self.debugger.track_variable_modification(var_name, old_value, new_value)
                
                # Update state tracker
                self.state_tracker.update_state(
                    node_id=node.id,
                    variables=result.variables
                )
            
            return result
            
        except Exception as e:
            return ExecutionResult(success=False, error=e)
    
    def set_breakpoint(self, node_id: str):
        """Set a breakpoint on a visual node."""
        self.debugger.set_breakpoint(node_id)
    
    def clear_breakpoint(self, node_id: str):
        """Clear a breakpoint from a visual node."""
        self.debugger.clear_breakpoint(node_id)
    
    def step_execution(self) -> ExecutionState:
        """Step through execution one node at a time."""
        self.debugger.enable_step_mode()
        return self.state_tracker.current_state
    
    def step_into(self) -> ExecutionState:
        """Step into function calls."""
        self.debugger.enable_step_into()
        return self.state_tracker.current_state
    
    def step_over(self) -> ExecutionState:
        """Step over function calls."""
        self.debugger.enable_step_over()
        return self.state_tracker.current_state
    
    def continue_execution(self):
        """Continue execution from current breakpoint."""
        self.debugger.disable_step_mode()
    
    def stop_execution(self):
        """Stop the current execution."""
        self.should_stop = True
    
    def get_variable_values(self) -> Dict[str, Any]:
        """Get current variable values during execution."""
        return self.state_tracker.current_state.variables
    
    def get_variable_value(self, variable_name: str) -> Any:
        """Get the value of a specific variable."""
        return self.executor.get_variable_value(variable_name)
    
    def set_variable_value(self, variable_name: str, value: Any):
        """Set the value of a variable during debugging."""
        old_value = self.get_variable_value(variable_name)
        self.executor.set_variable_value(variable_name, value)
        
        # Track the modification
        self.debugger.track_variable_modification(variable_name, old_value, value)
        
        # Update state tracker
        self.state_tracker.current_state.variables[variable_name] = value
    
    def inspect_variable(self, variable_name: str) -> Dict[str, Any]:
        """Get detailed information about a variable."""
        value = self.get_variable_value(variable_name)
        history = self.debugger.get_variable_history(variable_name)
        
        return {
            'name': variable_name,
            'value': value,
            'type': type(value).__name__ if value is not None else 'NoneType',
            'modification_history': history,
            'is_watched': variable_name in self.debugger.variable_watch_list
        }
    
    def add_variable_watch(self, variable_name: str):
        """Add a variable to the watch list."""
        self.debugger.add_to_watch_list(variable_name)
    
    def remove_variable_watch(self, variable_name: str):
        """Remove a variable from the watch list."""
        self.debugger.remove_from_watch_list(variable_name)
    
    def get_watched_variables(self) -> Dict[str, Any]:
        """Get values of all watched variables."""
        return self.debugger.get_watched_variables(self.state_tracker.current_state.variables)
    
    def get_call_stack(self) -> List[Dict[str, Any]]:
        """Get the current call stack."""
        return self.debugger.get_call_stack()
    
    def get_execution_trace(self) -> List[Dict[str, Any]]:
        """Get the execution trace."""
        return self.debugger.get_execution_trace()
    
    def get_execution_state(self) -> ExecutionState:
        """Get the current execution state."""
        return self.state_tracker.current_state
    
    def reset_execution_state(self):
        """Reset the execution state."""
        self.executor.reset_namespace()
        self.state_tracker = ExecutionStateTracker()
        self.debugger.reset_debug_session()
        self.is_executing = False
        self.should_stop = False
    
    def enable_debug_mode(self):
        """Enable debug mode for detailed execution tracking."""
        self.debug_mode = True
    
    def disable_debug_mode(self):
        """Disable debug mode."""
        self.debug_mode = False
    
    def enable_hot_reload(self):
        """Enable hot-reloading of visual changes."""
        self.hot_reload_enabled = True
    
    def disable_hot_reload(self):
        """Disable hot-reloading of visual changes."""
        self.hot_reload_enabled = False
    
    def hot_reload_model(self, updated_model: VisualModel) -> ExecutionResult:
        """Hot-reload an updated visual model during execution."""
        if not self.hot_reload_enabled:
            return ExecutionResult(success=False, error=Exception("Hot reload is disabled"))
        
        if not self.is_executing:
            return ExecutionResult(success=False, error=Exception("No execution in progress"))
        
        try:
            # Save current state
            current_variables = self.get_variable_values()
            current_node = self.debugger.current_node
            
            # Preserve execution state
            self.executor.local_namespace.update(current_variables)
            
            # Execute the updated model with current variable state
            result = self.execute_model(updated_model)
            
            # Restore current node if execution was paused
            if current_node:
                self.debugger.highlight_current_node(current_node)
            
            return result
            
        except Exception as e:
            return ExecutionResult(success=False, error=e)
    
    def set_step_execution_callback(self, callback: Callable[[str, ExecutionState], None]):
        """Set a callback to be called during step execution."""
        self.step_execution_callback = callback
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Get comprehensive debugging information."""
        debug_info = self.debugger.get_debug_info()
        debug_info.update({
            'execution_metrics': self.get_execution_metrics(),
            'current_variables': self.get_variable_values(),
            'watched_variables': self.get_watched_variables(),
            'call_stack': self.get_call_stack()
        })
        return debug_info
    
    def get_execution_metrics(self) -> Dict[str, Any]:
        """Get metrics about the current execution."""
        metrics = {
            'is_executing': self.is_executing,
            'debug_mode': self.debug_mode,
            'nodes_executed': len(self.state_tracker.node_execution_order),
            'execution_history': self.state_tracker.get_execution_history(),
            'breakpoints_set': len(self.debugger.breakpoints),
            'variables_count': len(self.state_tracker.current_state.variables),
            'step_mode_enabled': self.debugger.step_mode,
            'hot_reload_enabled': self.hot_reload_enabled,
            'data_flow_enabled': self.data_flow_enabled
        }
        
        # Add data flow metrics if available
        if self.data_flow_visualizer:
            metrics['data_flow'] = self.data_flow_visualizer.get_visualization_state()
        
        return metrics
    
    def set_data_flow_visualizer(self, visualizer: DataFlowVisualizer):
        """Set the data flow visualizer."""
        self.data_flow_visualizer = visualizer
    
    def enable_data_flow_visualization(self):
        """Enable data flow visualization."""
        self.data_flow_enabled = True
    
    def disable_data_flow_visualization(self):
        """Disable data flow visualization."""
        self.data_flow_enabled = False
    
    def update_connection_data_flow(self, connection_id: str, data_value: Any, 
                                  transformation_type: str = None):
        """Update data flow for a specific connection."""
        if self.data_flow_visualizer and self.data_flow_enabled:
            self.data_flow_visualizer.update_data_flow(connection_id, data_value, transformation_type)
    
    def update_connection_performance(self, connection_id: str, **metrics):
        """Update performance metrics for a connection."""
        if self.data_flow_visualizer and self.data_flow_enabled:
            self.data_flow_visualizer.update_performance_metrics(connection_id, **metrics)
    
    def highlight_data_transformation(self, connection_id: str, input_data: Any,
                                    output_data: Any, transformation_type: str):
        """Highlight a data transformation."""
        if self.data_flow_visualizer and self.data_flow_enabled:
            self.data_flow_visualizer.highlight_data_transformation(
                connection_id, input_data, output_data, transformation_type
            )
    
    def inspect_connection_during_debug(self, connection_id: str, position: float = 0.5) -> Dict[str, Any]:
        """Inspect a connection point during debugging."""
        if self.data_flow_visualizer:
            return self.data_flow_visualizer.inspect_connection_point(connection_id, position)
        return {}
    
    def get_data_flow_bottlenecks(self) -> List[Dict[str, Any]]:
        """Get performance bottlenecks in data flow."""
        if self.data_flow_visualizer:
            return self.data_flow_visualizer.get_performance_bottlenecks()
        return []
    
    def _update_data_flow_for_node(self, node_id: str, model: VisualModel, variables: Dict[str, Any]):
        """Update data flow visualization for a node's outgoing connections."""
        if not self.data_flow_visualizer:
            return
        
        # Find all outgoing connections from this node
        outgoing_connections = [
            conn for conn in model.connections 
            if conn.source_node_id == node_id
        ]
        
        for connection in outgoing_connections:
            # Get the output value for this connection
            source_port = connection.source_port
            if source_port in variables:
                data_value = variables[source_port]
                
                # Update data flow
                self.data_flow_visualizer.update_data_flow(connection.id, data_value)
                
                # Simulate performance metrics (in a real implementation, these would be measured)
                import random
                import time
                
                # Simulate throughput and latency based on data size
                data_size = len(str(data_value)) if data_value is not None else 0
                throughput = max(1.0, 100.0 - data_size * 0.1 + random.uniform(-10, 10))
                latency = max(1.0, data_size * 0.5 + random.uniform(0, 50))
                
                self.data_flow_visualizer.update_performance_metrics(
                    connection.id,
                    throughput=throughput,
                    latency=latency,
                    error_rate=random.uniform(0, 2),
                    cpu_usage=random.uniform(10, 60)
                )