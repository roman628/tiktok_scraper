#!/usr/bin/env python3
"""
Claude Tools - Definition Checker
Scans the TikTok scraper codebase for function/class definitions and variables,
then identifies potential redundancies in the refactored architecture.
"""

import os
import ast
import re
from typing import Dict, List, Set, Tuple
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class Definition:
    """Represents a function, class, or variable definition"""
    name: str
    type: str  # 'function', 'class', 'variable'
    file_path: str
    line_number: int
    args: List[str] = None  # For functions
    decorators: List[str] = None  # For functions/classes


class CodeAnalyzer:
    """Analyzes Python code for definitions and redundancies"""
    
    def __init__(self, root_dir: str = "."):
        self.root_dir = root_dir
        self.definitions = []
        self.function_defs = defaultdict(list)
        self.class_defs = defaultdict(list)
        self.variable_defs = defaultdict(list)
        
    def scan_directory(self, directory: str = None):
        """Scan directory for Python files and extract definitions"""
        if directory is None:
            directory = self.root_dir
            
        print(f"🔍 Scanning directory: {directory}")
        
        python_files = []
        for root, dirs, files in os.walk(directory):
            # Skip certain directories
            skip_dirs = {'venv', '__pycache__', '.git', 'node_modules', 'downloads'}
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))
        
        print(f"📂 Found {len(python_files)} Python files")
        
        for file_path in python_files:
            self._analyze_file(file_path)
        
        self._categorize_definitions()
    
    def _analyze_file(self, file_path: str):
        """Analyze a single Python file for definitions"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse the AST
            tree = ast.parse(content, filename=file_path)
            
            # Walk through the AST
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    self._extract_function(node, file_path)
                elif isinstance(node, ast.AsyncFunctionDef):
                    self._extract_async_function(node, file_path)
                elif isinstance(node, ast.ClassDef):
                    self._extract_class(node, file_path)
                elif isinstance(node, ast.Assign):
                    self._extract_variable(node, file_path)
                elif isinstance(node, ast.AnnAssign):
                    self._extract_annotated_variable(node, file_path)
        
        except Exception as e:
            print(f"⚠️  Error analyzing {file_path}: {e}")
    
    def _extract_function(self, node: ast.FunctionDef, file_path: str):
        """Extract function definition"""
        args = [arg.arg for arg in node.args.args]
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]
        
        definition = Definition(
            name=node.name,
            type='function',
            file_path=file_path,
            line_number=node.lineno,
            args=args,
            decorators=decorators
        )
        self.definitions.append(definition)
    
    def _extract_async_function(self, node: ast.AsyncFunctionDef, file_path: str):
        """Extract async function definition"""
        args = [arg.arg for arg in node.args.args]
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]
        
        definition = Definition(
            name=node.name,
            type='async_function',
            file_path=file_path,
            line_number=node.lineno,
            args=args,
            decorators=decorators
        )
        self.definitions.append(definition)
    
    def _extract_class(self, node: ast.ClassDef, file_path: str):
        """Extract class definition"""
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]
        
        definition = Definition(
            name=node.name,
            type='class',
            file_path=file_path,
            line_number=node.lineno,
            decorators=decorators
        )
        self.definitions.append(definition)
    
    def _extract_variable(self, node: ast.Assign, file_path: str):
        """Extract variable assignment"""
        for target in node.targets:
            if isinstance(target, ast.Name):
                definition = Definition(
                    name=target.id,
                    type='variable',
                    file_path=file_path,
                    line_number=node.lineno
                )
                self.definitions.append(definition)
    
    def _extract_annotated_variable(self, node: ast.AnnAssign, file_path: str):
        """Extract annotated variable assignment"""
        if isinstance(node.target, ast.Name):
            definition = Definition(
                name=node.target.id,
                type='variable',
                file_path=file_path,
                line_number=node.lineno
            )
            self.definitions.append(definition)
    
    def _get_decorator_name(self, decorator) -> str:
        """Get decorator name as string"""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return ast.unparse(decorator)
        else:
            return str(decorator)
    
    def _categorize_definitions(self):
        """Categorize definitions by type"""
        for definition in self.definitions:
            if definition.type in ['function', 'async_function']:
                self.function_defs[definition.name].append(definition)
            elif definition.type == 'class':
                self.class_defs[definition.name].append(definition)
            elif definition.type == 'variable':
                # Filter out common variables
                if not self._is_common_variable(definition.name):
                    self.variable_defs[definition.name].append(definition)
    
    def _is_common_variable(self, name: str) -> bool:
        """Check if variable is too common to be meaningful"""
        common_vars = {
            'i', 'j', 'k', 'x', 'y', 'z', 'e', 'f', 'data', 'result', 'response',
            'content', 'line', 'item', 'value', 'key', 'args', 'kwargs', 'self',
            'cls', 'path', 'name', 'url', 'config', 'error'
        }
        return name in common_vars or len(name) <= 1
    
    def print_summary(self):
        """Print summary of definitions found"""
        print("\n" + "="*60)
        print("📊 DEFINITION ANALYSIS SUMMARY")
        print("="*60)
        
        print(f"📁 Total Python files analyzed: {len(set(d.file_path for d in self.definitions))}")
        print(f"🔧 Total functions found: {len([d for d in self.definitions if d.type in ['function', 'async_function']])}")
        print(f"🏗️  Total classes found: {len([d for d in self.definitions if d.type == 'class'])}")
        print(f"📝 Total variables found: {len([d for d in self.definitions if d.type == 'variable'])}")
        
        # Functions by file
        print(f"\n🔧 FUNCTIONS ({len(self.function_defs)} unique names):")
        function_counts = defaultdict(int)
        for name, defs in self.function_defs.items():
            for definition in defs:
                file_short = self._shorten_path(definition.file_path)
                function_counts[file_short] += 1
                
        for file_path, count in sorted(function_counts.items()):
            print(f"   {file_path}: {count} functions")
        
        # Classes by file
        print(f"\n🏗️  CLASSES ({len(self.class_defs)} unique names):")
        class_counts = defaultdict(int)
        for name, defs in self.class_defs.items():
            for definition in defs:
                file_short = self._shorten_path(definition.file_path)
                class_counts[file_short] += 1
                
        for file_path, count in sorted(class_counts.items()):
            print(f"   {file_path}: {count} classes")
        
        # Variables by file
        print(f"\n📝 VARIABLES ({len(self.variable_defs)} unique names):")
        var_counts = defaultdict(int)
        for name, defs in self.variable_defs.items():
            for definition in defs:
                file_short = self._shorten_path(definition.file_path)
                var_counts[file_short] += 1
        
        for file_path, count in sorted(var_counts.items()):
            print(f"   {file_path}: {count} variables")
    
    def _shorten_path(self, file_path: str) -> str:
        """Shorten file path for display"""
        return file_path.replace(self.root_dir + '/', '').replace(self.root_dir, '.')
    
    def check_redundancies(self):
        """Analyze definitions for potential redundancies"""
        print("\n" + "="*60)
        print("🔍 REDUNDANCY ANALYSIS")
        print("="*60)
        
        self._check_duplicate_functions()
        self._check_duplicate_classes()
        self._check_similar_functions()
        self._check_similar_variables()
        
    def _check_duplicate_functions(self):
        """Check for duplicate function names"""
        print("\n🔧 DUPLICATE FUNCTION NAMES:")
        duplicates_found = False
        
        for name, defs in self.function_defs.items():
            if len(defs) > 1:
                duplicates_found = True
                print(f"\n   📍 Function '{name}' defined {len(defs)} times:")
                for definition in defs:
                    file_short = self._shorten_path(definition.file_path)
                    args_str = f"({', '.join(definition.args)})" if definition.args else "()"
                    print(f"      - {file_short}:{definition.line_number} {args_str}")
                    
                # Analyze if they're truly redundant
                if self._are_functions_similar(defs):
                    print(f"      ⚠️  POTENTIAL REDUNDANCY: Similar argument patterns")
        
        if not duplicates_found:
            print("   ✅ No duplicate function names found")
    
    def _check_duplicate_classes(self):
        """Check for duplicate class names"""
        print("\n🏗️  DUPLICATE CLASS NAMES:")
        duplicates_found = False
        
        for name, defs in self.class_defs.items():
            if len(defs) > 1:
                duplicates_found = True
                print(f"\n   📍 Class '{name}' defined {len(defs)} times:")
                for definition in defs:
                    file_short = self._shorten_path(definition.file_path)
                    print(f"      - {file_short}:{definition.line_number}")
                print(f"      ⚠️  POTENTIAL REDUNDANCY: Multiple class definitions")
        
        if not duplicates_found:
            print("   ✅ No duplicate class names found")
    
    def _check_similar_functions(self):
        """Check for functions with similar names or purposes"""
        print("\n🔧 SIMILAR FUNCTION ANALYSIS:")
        
        function_names = list(self.function_defs.keys())
        similar_groups = []
        
        # Group by similar names
        for i, name1 in enumerate(function_names):
            for j, name2 in enumerate(function_names[i+1:], i+1):
                if self._are_names_similar(name1, name2):
                    # Check if already in a group
                    found_group = None
                    for group in similar_groups:
                        if name1 in group or name2 in group:
                            found_group = group
                            break
                    
                    if found_group:
                        found_group.update([name1, name2])
                    else:
                        similar_groups.append({name1, name2})
        
        if similar_groups:
            for group in similar_groups:
                print(f"\n   📍 Similar function names: {', '.join(sorted(group))}")
                for name in sorted(group):
                    for definition in self.function_defs[name]:
                        file_short = self._shorten_path(definition.file_path)
                        args_str = f"({', '.join(definition.args)})" if definition.args else "()"
                        print(f"      - {name}: {file_short}:{definition.line_number} {args_str}")
                print(f"      💡 Consider consolidating similar functionality")
        else:
            print("   ✅ No similar function names detected")
    
    def _check_similar_variables(self):
        """Check for variables that might be redundant"""
        print("\n📝 VARIABLE REDUNDANCY ANALYSIS:")
        
        # Group variables by similar names
        var_names = list(self.variable_defs.keys())
        redundant_vars = []
        
        for name, defs in self.variable_defs.items():
            if len(defs) > 3:  # Variables defined in multiple places
                files = set(self._shorten_path(d.file_path) for d in defs)
                if len(files) > 2:  # Across multiple files
                    redundant_vars.append((name, len(defs), len(files)))
        
        if redundant_vars:
            print("   📍 Variables defined in multiple files (potential for constants):")
            for name, def_count, file_count in sorted(redundant_vars, key=lambda x: x[1], reverse=True):
                print(f"      - '{name}': {def_count} definitions across {file_count} files")
                for definition in self.variable_defs[name][:5]:  # Show first 5
                    file_short = self._shorten_path(definition.file_path)
                    print(f"        • {file_short}:{definition.line_number}")
                if len(self.variable_defs[name]) > 5:
                    print(f"        ... and {len(self.variable_defs[name]) - 5} more")
                print(f"        💡 Consider creating a constants file")
        else:
            print("   ✅ No significant variable redundancy detected")
    
    def _are_functions_similar(self, definitions: List[Definition]) -> bool:
        """Check if functions have similar argument patterns"""
        if len(definitions) < 2:
            return False
        
        # Compare argument counts
        arg_counts = [len(d.args) if d.args else 0 for d in definitions]
        return len(set(arg_counts)) <= 2  # Similar if arg counts are close
    
    def _are_names_similar(self, name1: str, name2: str) -> bool:
        """Check if two names are similar"""
        # Simple similarity checks
        if name1 == name2:
            return False
        
        # Check for common patterns
        patterns = [
            (name1.replace('_', ''), name2.replace('_', '')),  # Underscore variants
            (name1.lower(), name2.lower()),  # Case variants
        ]
        
        for n1, n2 in patterns:
            if n1 == n2 and n1 != name1:
                return True
        
        # Check for similar prefixes/suffixes
        if len(name1) > 4 and len(name2) > 4:
            if (name1.startswith(name2[:4]) or name2.startswith(name1[:4]) or
                name1.endswith(name2[-4:]) or name2.endswith(name1[-4:])):
                return True
        
        return False
    
    def generate_report(self, output_file: str = "definition_analysis.txt"):
        """Generate detailed report file"""
        print(f"\n📄 Generating detailed report: {output_file}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("TikTok Scraper - Definition Analysis Report\n")
            f.write("="*50 + "\n\n")
            
            # Summary
            f.write("SUMMARY\n")
            f.write("-"*20 + "\n")
            f.write(f"Total functions: {len([d for d in self.definitions if d.type in ['function', 'async_function']])}\n")
            f.write(f"Total classes: {len([d for d in self.definitions if d.type == 'class'])}\n")
            f.write(f"Total variables: {len([d for d in self.definitions if d.type == 'variable'])}\n\n")
            
            # All functions
            f.write("ALL FUNCTIONS\n")
            f.write("-"*20 + "\n")
            for name, defs in sorted(self.function_defs.items()):
                for definition in defs:
                    file_short = self._shorten_path(definition.file_path)
                    args_str = f"({', '.join(definition.args)})" if definition.args else "()"
                    f.write(f"{name}{args_str} - {file_short}:{definition.line_number}\n")
            
            # All classes
            f.write("\nALL CLASSES\n")
            f.write("-"*20 + "\n")
            for name, defs in sorted(self.class_defs.items()):
                for definition in defs:
                    file_short = self._shorten_path(definition.file_path)
                    f.write(f"{name} - {file_short}:{definition.line_number}\n")
        
        print(f"✅ Report saved to {output_file}")


def main():
    """Main function to run the definition checker"""
    print("🔍 Claude Tools - Definition Checker")
    print("="*50)
    
    # Initialize analyzer
    analyzer = CodeAnalyzer()
    
    # Scan the codebase
    analyzer.scan_directory()
    
    # Print summary
    analyzer.print_summary()
    
    # Check for redundancies
    analyzer.check_redundancies()
    
    # Generate detailed report
    analyzer.generate_report()
    
    print("\n" + "="*60)
    print("✅ ANALYSIS COMPLETE")
    print("="*60)
    print("💡 Use this analysis to identify opportunities for further code consolidation")
    print("📄 Check 'definition_analysis.txt' for detailed listings")


if __name__ == "__main__":
    main()