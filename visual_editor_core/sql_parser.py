"""
SQL to Universal IR Parser.

This module parses SQL code and converts it to Universal Intermediate Representation.
"""

import re
from typing import Dict, List, Optional, Any
from .universal_ir import (
    UniversalProject, UniversalModule, UniversalFunction, UniversalClass,
    UniversalVariable, Parameter, TypeSignature, DataType, SemanticDescription,
    Contract, PurityLevel
)


class SQLParser:
    """Parses SQL code into Universal IR."""
    
    def __init__(self):
        self.current_module: Optional[UniversalModule] = None
    
    def parse_code(self, sql_code: str, filename: str = "script.sql") -> UniversalModule:
        """Parse SQL code into a Universal Module."""
        module = UniversalModule(
            name=filename.replace('.sql', ''),
            source_language="sql",
            source_file=filename
        )
        
        self.current_module = module
        
        # Parse SQL constructs
        self._parse_source_includes(sql_code)
        self._parse_create_tables(sql_code)
        self._parse_create_views(sql_code)
        self._parse_stored_procedures(sql_code)
        self._parse_functions(sql_code)
        self._parse_triggers(sql_code)
        
        return module

    def _parse_source_includes(self, code: str):
        """Parse SQL file inclusion directives (dialect-specific)."""
        if self.current_module is None:
            return
        # PostgreSQL: \i file.sql  or  \include file.sql
        psql_pattern = r'^\s*(\\i(?:nclude)?\s+\S+)'
        for m in re.finditer(psql_pattern, code, re.MULTILINE):
            self.current_module.imports.append(m.group(1).strip())
        # MySQL: SOURCE file.sql
        mysql_pattern = r'^\s*(SOURCE\s+\S+)'
        for m in re.finditer(mysql_pattern, code, re.MULTILINE | re.IGNORECASE):
            self.current_module.imports.append(m.group(1).strip())
    
    def _parse_create_tables(self, code: str):
        """Parse CREATE TABLE statements."""
        table_pattern = r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\(([^;]+)\)'
        tables = re.finditer(table_pattern, code, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        
        for match in tables:
            table_name = match.group(1)
            columns_str = match.group(2)
            
            cls = UniversalClass(
                name=table_name,
                source_language="sql"
            )
            
            cls.implementation_hints = {'is_table': True}
            
            # Parse columns
            columns = self._parse_columns(columns_str)
            cls.implementation_hints['columns'] = columns
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_columns(self, columns_str: str) -> List[Dict[str, Any]]:
        """Parse column definitions."""
        columns = []
        
        # Split by comma but not inside parentheses
        depth = 0
        current = ""
        parts = []
        
        for char in columns_str:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            elif char == ',' and depth == 0:
                parts.append(current.strip())
                current = ""
                continue
            current += char
        
        if current.strip():
            parts.append(current.strip())
        
        for part in parts:
            # Skip constraints
            if any(kw in part.upper() for kw in ['PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE', 'CHECK', 'CONSTRAINT']):
                continue
            
            # Parse column: name type [constraints]
            tokens = part.split()
            if len(tokens) >= 2:
                col_name = tokens[0]
                col_type = tokens[1]
                
                columns.append({
                    'name': col_name,
                    'type': col_type,
                    'nullable': 'NOT NULL' not in part.upper(),
                    'primary_key': 'PRIMARY KEY' in part.upper(),
                })
        
        return columns
    
    def _parse_create_views(self, code: str):
        """Parse CREATE VIEW statements."""
        view_pattern = r'CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+(\w+)\s+AS\s+(SELECT[^;]+)'
        views = re.finditer(view_pattern, code, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        
        for match in views:
            view_name = match.group(1)
            select_stmt = match.group(2)
            
            cls = UniversalClass(
                name=view_name,
                source_language="sql"
            )
            
            cls.implementation_hints = {
                'is_view': True,
                'select_statement': select_stmt.strip()
            }
            
            if self.current_module is not None:
                self.current_module.classes.append(cls)
    
    def _parse_stored_procedures(self, code: str):
        """Parse CREATE PROCEDURE statements."""
        proc_pattern = r'CREATE\s+(?:OR\s+REPLACE\s+)?PROCEDURE\s+(\w+)\s*\(([^)]*)\)\s*(?:AS|BEGIN)\s*([^;]*(?:;[^;]*)*?)(?:END|GO)'
        procs = re.finditer(proc_pattern, code, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        
        for match in procs:
            proc_name = match.group(1)
            params_str = match.group(2)
            body = match.group(3)
            
            parameters = self._parse_sql_parameters(params_str)
            
            func = UniversalFunction(
                name=proc_name,
                parameters=parameters,
                return_type=TypeSignature(DataType.VOID),
                source_language="sql",
                source_code=match.group(0),
                implementation_hints={
                    'is_procedure': True,
                    'control_flow': self._extract_control_flow(body)
                }
            )
            
            if self.current_module is not None:
                self.current_module.functions.append(func)
    
    def _parse_functions(self, code: str):
        """Parse CREATE FUNCTION statements."""
        func_pattern = r'CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(\w+)\s*\(([^)]*)\)\s*RETURNS\s+(\w+)\s*(?:AS|BEGIN)\s*([^;]*(?:;[^;]*)*?)(?:END|GO)'
        functions = re.finditer(func_pattern, code, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        
        for match in functions:
            func_name = match.group(1)
            params_str = match.group(2)
            return_type_str = match.group(3)
            body = match.group(4)
            
            parameters = self._parse_sql_parameters(params_str)
            return_type = self._parse_sql_type(return_type_str)
            
            func = UniversalFunction(
                name=func_name,
                parameters=parameters,
                return_type=return_type,
                source_language="sql",
                source_code=match.group(0),
                implementation_hints={
                    'is_function': True,
                    'control_flow': self._extract_control_flow(body)
                }
            )
            
            if self.current_module is not None:
                self.current_module.functions.append(func)
    
    def _parse_triggers(self, code: str):
        """Parse CREATE TRIGGER statements."""
        trigger_pattern = r'CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+(\w+)\s+(BEFORE|AFTER)\s+(INSERT|UPDATE|DELETE)\s+ON\s+(\w+)'
        triggers = re.finditer(trigger_pattern, code, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        
        for match in triggers:
            trigger_name = match.group(1)
            timing = match.group(2)
            event = match.group(3)
            table_name = match.group(4)
            
            func = UniversalFunction(
                name=trigger_name,
                parameters=[],
                return_type=TypeSignature(DataType.VOID),
                source_language="sql",
                source_code=match.group(0),
                implementation_hints={
                    'is_trigger': True,
                    'timing': timing.upper(),
                    'event': event.upper(),
                    'table': table_name
                }
            )
            
            if self.current_module is not None:
                self.current_module.functions.append(func)
    
    def _parse_sql_parameters(self, params_str: str) -> List[Parameter]:
        """Parse SQL procedure/function parameters."""
        parameters = []
        if not params_str.strip():
            return parameters
        
        parts = [p.strip() for p in params_str.split(',') if p.strip()]
        
        for part in parts:
            tokens = part.split()
            
            # Handle IN/OUT/INOUT modifiers
            mode = 'IN'
            if tokens and tokens[0].upper() in ['IN', 'OUT', 'INOUT']:
                mode = tokens.pop(0).upper()
            
            if len(tokens) >= 2:
                name = tokens[0]
                type_str = tokens[1]
                
                parameters.append(Parameter(
                    name=name,
                    type_sig=self._parse_sql_type(type_str),
                    required=True
                ))
        
        return parameters
    
    def _parse_sql_type(self, type_str: str) -> TypeSignature:
        """Parse SQL type into UIR TypeSignature."""
        if not type_str:
            return TypeSignature(DataType.ANY)
        
        type_str = type_str.upper().strip()
        
        # Remove size specifications
        type_str = re.sub(r'\([^)]+\)', '', type_str)
        
        type_mapping = {
            'VOID': DataType.VOID,
            'BOOLEAN': DataType.BOOLEAN,
            'BOOL': DataType.BOOLEAN,
            'BIT': DataType.BOOLEAN,
            'INT': DataType.INTEGER,
            'INTEGER': DataType.INTEGER,
            'SMALLINT': DataType.INTEGER,
            'BIGINT': DataType.INTEGER,
            'TINYINT': DataType.INTEGER,
            'FLOAT': DataType.FLOAT,
            'REAL': DataType.FLOAT,
            'DOUBLE': DataType.FLOAT,
            'DECIMAL': DataType.FLOAT,
            'NUMERIC': DataType.FLOAT,
            'CHAR': DataType.STRING,
            'VARCHAR': DataType.STRING,
            'TEXT': DataType.STRING,
            'NVARCHAR': DataType.STRING,
            'NCHAR': DataType.STRING,
            'DATE': DataType.STRING,
            'TIME': DataType.STRING,
            'DATETIME': DataType.STRING,
            'TIMESTAMP': DataType.STRING,
            'JSON': DataType.OBJECT,
            'JSONB': DataType.OBJECT,
            'ARRAY': DataType.ARRAY,
            'TABLE': DataType.ARRAY,
        }
        
        return TypeSignature(type_mapping.get(type_str, DataType.ANY))
    
    def _extract_control_flow(self, body: str) -> List[Dict[str, Any]]:
        """Extract control flow structures from SQL body."""
        control_flow = []
        
        if not body:
            return control_flow
        
        patterns = [
            (r'IF\s+', 'if_condition'),
            (r'CASE\s+', 'switch'),
            (r'WHILE\s+', 'while_loop'),
            (r'LOOP\s+', 'loop'),
            (r'FOR\s+', 'for_loop'),
        ]
        
        for pattern, kind in patterns:
            for match in re.finditer(pattern, body, re.IGNORECASE):
                control_flow.append({
                    'kind': kind,
                    'source_code': match.group(0),
                    'lineno': body[:match.start()].count('\n') + 1
                })
        
        return control_flow
