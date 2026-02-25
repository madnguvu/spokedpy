"""
SQL Code Generator from Universal IR.

This module generates SQL code from Universal Intermediate Representation.
"""

from typing import List, Dict, Any, Optional
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, LanguageMapping
)


class SQLGenerator:
    """Generates SQL code from Universal IR."""
    
    def __init__(self, dialect: str = "postgresql"):
        self.mapping = LanguageMapping("universal", "sql")
        self.dialect = dialect  # postgresql, mysql, sqlite, sqlserver
        self.indent_level = 0
        self.indent_size = 4
    
    def generate_module(self, module: UniversalModule) -> str:
        """Generate SQL code for a Universal Module."""
        lines = []
        
        # Header comment
        lines.append(f"-- Generated SQL for {module.name}")
        lines.append(f"-- Dialect: {self.dialect}")
        lines.append("")
        
        # Schema/extension imports from module.imports (populated by parser / ledger)
        from .import_translator import translate_imports
        translated = translate_imports(module.imports, 'sql')
        sql_imports = []
        for imp in translated:
            stripped = imp.strip()
            if stripped and stripped not in sql_imports:
                sql_imports.append(stripped)
                lines.append(stripped if stripped.endswith(";") else f"{stripped};")
        if sql_imports:
            lines.append("")
        
        # Generate tables
        for cls in module.classes:
            if cls.implementation_hints.get('is_table'):
                table_code = self._generate_table(cls)
                lines.extend(table_code)
                lines.append("")
        
        # Generate views
        for cls in module.classes:
            if cls.implementation_hints.get('is_view'):
                view_code = self._generate_view(cls)
                lines.extend(view_code)
                lines.append("")
        
        # Generate stored procedures
        for func in module.functions:
            if func.implementation_hints.get('is_procedure'):
                proc_code = self._generate_procedure(func)
                lines.extend(proc_code)
                lines.append("")
        
        # Generate functions
        for func in module.functions:
            if func.implementation_hints.get('is_function'):
                func_code = self._generate_function(func)
                lines.extend(func_code)
                lines.append("")
        
        # Generate triggers
        for func in module.functions:
            if func.implementation_hints.get('is_trigger'):
                trigger_code = self._generate_trigger(func)
                lines.extend(trigger_code)
                lines.append("")
        
        while lines and lines[-1] == "":
            lines.pop()
        
        return "\n".join(lines)
    
    def generate_project(self, project: UniversalProject) -> Dict[str, str]:
        """Generate SQL code for an entire project."""
        files = {}
        
        for module in project.modules:
            filename = f"{module.name}.sql"
            files[filename] = self.generate_module(module)
        
        return files
    
    def _indent(self, text: str = "") -> str:
        """Return properly indented text."""
        return " " * (self.indent_level * self.indent_size) + text
    
    def _generate_table(self, cls: UniversalClass) -> List[str]:
        """Generate CREATE TABLE statement."""
        lines = []
        
        lines.append(f"CREATE TABLE IF NOT EXISTS {cls.name} (")
        self.indent_level += 1
        
        columns = cls.implementation_hints.get('columns', [])
        
        if columns:
            for i, col in enumerate(columns):
                col_name = col.get('name', 'column')
                col_type = self._map_type_to_sql_column(col.get('type', 'TEXT'))
                nullable = "" if col.get('nullable', True) else " NOT NULL"
                pk = " PRIMARY KEY" if col.get('primary_key', False) else ""
                
                comma = "," if i < len(columns) - 1 else ""
                lines.append(self._indent(f"{col_name} {col_type}{nullable}{pk}{comma}"))
        else:
            # Generate from constructor parameters
            constructor = None
            for method in cls.methods:
                if method.implementation_hints.get('is_constructor'):
                    constructor = method
                    break
            
            if constructor:
                params = constructor.parameters
                for i, param in enumerate(params):
                    type_str = self._map_type_to_sql(param.type_sig)
                    comma = "," if i < len(params) - 1 else ""
                    lines.append(self._indent(f"{param.name} {type_str}{comma}"))
            else:
                lines.append(self._indent("id SERIAL PRIMARY KEY"))
        
        self.indent_level -= 1
        lines.append(");")
        
        return lines
    
    def _generate_view(self, cls: UniversalClass) -> List[str]:
        """Generate CREATE VIEW statement."""
        lines = []
        
        select_stmt = cls.implementation_hints.get('select_statement', 'SELECT 1')
        
        lines.append(f"CREATE OR REPLACE VIEW {cls.name} AS")
        lines.append(f"{select_stmt};")
        
        return lines
    
    def _generate_procedure(self, func: UniversalFunction) -> List[str]:
        """Generate CREATE PROCEDURE statement."""
        lines = []
        
        params = self._generate_parameters(func.parameters)
        
        if self.dialect == 'postgresql':
            lines.append(f"CREATE OR REPLACE PROCEDURE {func.name}({params})")
            lines.append("LANGUAGE plpgsql")
            lines.append("AS $$")
            lines.append("BEGIN")
            self.indent_level += 1
            lines.append(self._indent("-- TODO: Implement"))
            self.indent_level -= 1
            lines.append("END;")
            lines.append("$$;")
        elif self.dialect == 'mysql':
            lines.append(f"DELIMITER //")
            lines.append(f"CREATE PROCEDURE {func.name}({params})")
            lines.append("BEGIN")
            self.indent_level += 1
            lines.append(self._indent("-- TODO: Implement"))
            self.indent_level -= 1
            lines.append("END //")
            lines.append("DELIMITER ;")
        else:
            lines.append(f"CREATE PROCEDURE {func.name}({params})")
            lines.append("AS")
            lines.append("BEGIN")
            self.indent_level += 1
            lines.append(self._indent("-- TODO: Implement"))
            self.indent_level -= 1
            lines.append("END;")
        
        return lines
    
    def _generate_function(self, func: UniversalFunction) -> List[str]:
        """Generate CREATE FUNCTION statement."""
        lines = []
        
        params = self._generate_parameters(func.parameters)
        return_type = self._map_type_to_sql(func.return_type)
        
        if self.dialect == 'postgresql':
            lines.append(f"CREATE OR REPLACE FUNCTION {func.name}({params})")
            lines.append(f"RETURNS {return_type}")
            lines.append("LANGUAGE plpgsql")
            lines.append("AS $$")
            lines.append("BEGIN")
            self.indent_level += 1
            lines.append(self._indent("-- TODO: Implement"))
            default_return = self._get_default_return(func.return_type)
            lines.append(self._indent(f"RETURN {default_return};"))
            self.indent_level -= 1
            lines.append("END;")
            lines.append("$$;")
        else:
            lines.append(f"CREATE FUNCTION {func.name}({params})")
            lines.append(f"RETURNS {return_type}")
            lines.append("BEGIN")
            self.indent_level += 1
            lines.append(self._indent("-- TODO: Implement"))
            default_return = self._get_default_return(func.return_type)
            lines.append(self._indent(f"RETURN {default_return};"))
            self.indent_level -= 1
            lines.append("END;")
        
        return lines
    
    def _generate_trigger(self, func: UniversalFunction) -> List[str]:
        """Generate CREATE TRIGGER statement."""
        lines = []
        
        hints = func.implementation_hints
        timing = hints.get('timing', 'BEFORE')
        event = hints.get('event', 'INSERT')
        table = hints.get('table', 'table_name')
        
        if self.dialect == 'postgresql':
            # Create trigger function first
            lines.append(f"CREATE OR REPLACE FUNCTION {func.name}_fn()")
            lines.append("RETURNS TRIGGER")
            lines.append("LANGUAGE plpgsql")
            lines.append("AS $$")
            lines.append("BEGIN")
            self.indent_level += 1
            lines.append(self._indent("-- TODO: Implement"))
            lines.append(self._indent("RETURN NEW;"))
            self.indent_level -= 1
            lines.append("END;")
            lines.append("$$;")
            lines.append("")
            lines.append(f"CREATE TRIGGER {func.name}")
            lines.append(f"{timing} {event} ON {table}")
            lines.append("FOR EACH ROW")
            lines.append(f"EXECUTE FUNCTION {func.name}_fn();")
        else:
            lines.append(f"CREATE TRIGGER {func.name}")
            lines.append(f"{timing} {event} ON {table}")
            lines.append("FOR EACH ROW")
            lines.append("BEGIN")
            self.indent_level += 1
            lines.append(self._indent("-- TODO: Implement"))
            self.indent_level -= 1
            lines.append("END;")
        
        return lines
    
    def _generate_parameters(self, parameters: List[Parameter]) -> str:
        """Generate SQL parameter list."""
        param_strs = []
        
        for param in parameters:
            type_str = self._map_type_to_sql(param.type_sig)
            param_strs.append(f"{param.name} {type_str}")
        
        return ", ".join(param_strs)
    
    def _map_type_to_sql(self, type_sig: TypeSignature) -> str:
        """Map UIR type signature to SQL type."""
        if self.dialect == 'postgresql':
            type_mapping = {
                DataType.VOID: 'VOID',
                DataType.BOOLEAN: 'BOOLEAN',
                DataType.INTEGER: 'INTEGER',
                DataType.FLOAT: 'DOUBLE PRECISION',
                DataType.STRING: 'TEXT',
                DataType.ARRAY: 'JSON',
                DataType.OBJECT: 'JSONB',
                DataType.ANY: 'TEXT',
            }
        else:
            type_mapping = {
                DataType.VOID: 'VOID',
                DataType.BOOLEAN: 'BOOLEAN',
                DataType.INTEGER: 'INT',
                DataType.FLOAT: 'DOUBLE',
                DataType.STRING: 'VARCHAR(255)',
                DataType.ARRAY: 'JSON',
                DataType.OBJECT: 'JSON',
                DataType.ANY: 'TEXT',
            }
        
        return type_mapping.get(type_sig.base_type, 'TEXT')
    
    def _map_type_to_sql_column(self, type_str: str) -> str:
        """Normalize SQL column type for current dialect."""
        type_str = type_str.upper()
        
        if self.dialect == 'postgresql':
            mapping = {
                'INT': 'INTEGER',
                'DOUBLE': 'DOUBLE PRECISION',
            }
        else:
            mapping = {}
        
        return mapping.get(type_str, type_str)
    
    def _get_default_return(self, type_sig: TypeSignature) -> str:
        """Get default return value for a type."""
        defaults = {
            DataType.BOOLEAN: 'FALSE',
            DataType.INTEGER: '0',
            DataType.FLOAT: '0.0',
            DataType.STRING: "''",
            DataType.ARRAY: 'NULL',
            DataType.OBJECT: 'NULL',
            DataType.ANY: 'NULL',
        }
        return defaults.get(type_sig.base_type, 'NULL')
