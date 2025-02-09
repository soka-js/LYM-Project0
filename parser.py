#!/usr/bin/env python3
"""
Robot Control Language Parser (Procedural Version)

This parser implements a simple syntax checker for a robot–control language.
It uses:
  - Regular Expressions to tokenize the input.
  - A recursive–descent parser (following a context–free grammar) to check syntax.

The grammar (simplified) is roughly:
  Program              → VariableDeclaration ProcedureDefinitions MainBlock
  VariableDeclaration  → "|" IdentifierList "|"
  IdentifierList       → Identifier { Identifier }
  ProcedureDefinition  → "proc" Identifier { ":" Identifier } CodeBlock
  CodeBlock            → "[" InstructionList "]"
  InstructionList      → Instruction { Instruction }
  Instruction          → ProcedureCall
  ProcedureCall        → Identifier { ":" Expression } "."
  Expression           → Number | Identifier
"""

import re
import sys

# --------------------------------------------------
# Tokenization (Lexer) using Regular Expressions
# --------------------------------------------------
def tokenize(text):
    """
    Converts the source text into a list of tokens.
    Each token is represented as a tuple:
         (token_type, value, line, column)
    """
    token_specs = [
        ('NUMBER',    r'\d+'),
        ('ID',        r'[A-Za-z_][A-Za-z0-9_]*'),
        ('PIPE',      r'\|'),
        ('LBRACKET',  r'\['),
        ('RBRACKET',  r'\]'),
        ('COLON',     r':'),
        ('DOT',       r'\.'),
        ('SKIP',      r'[ \t]+'),
        ('NEWLINE',   r'\n'),
        ('MISMATCH',  r'.'),  # any other character is an error
    ]
    token_regex = "|".join("(?P<%s>%s)" % (name, pattern) for name, pattern in token_specs)
    regex = re.compile(token_regex)
    
    tokens = []
    line_num = 1
    line_start = 0

    for mo in regex.finditer(text):
        kind = mo.lastgroup
        value = mo.group()
        column = mo.start() - line_start
        if kind == 'NUMBER':
            tokens.append((kind, int(value), line_num, column))
        elif kind == 'ID':
            tokens.append((kind, value, line_num, column))
        elif kind in ('PIPE', 'LBRACKET', 'RBRACKET', 'COLON', 'DOT'):
            tokens.append((kind, value, line_num, column))
        elif kind == 'NEWLINE':
            line_num += 1
            line_start = mo.end()
        elif kind == 'SKIP':
            continue
        elif kind == 'MISMATCH':
            raise RuntimeError(f"Unexpected character {value!r} on line {line_num}")
    return tokens

# --------------------------------------------------
# Global Parser State (Procedural Style)
# --------------------------------------------------
tokens = []   # List of tokens (populated by tokenize)
pos = 0       # Current position in the token list

# Global symbol tables (for variable and procedure declarations)
variables = set()
procedures = {}

def current_token():
    """Return the current token (or None if at the end)."""
    global tokens, pos
    if pos < len(tokens):
        return tokens[pos]
    return None

def advance():
    """Advance to the next token."""
    global pos
    pos += 1

def expect(token_type, token_value=None):
    """
    Check that the current token matches the expected type (and value, if provided),
    then advance. Otherwise, report a syntax error.
    """
    token = current_token()
    if token is None:
        error("Unexpected end of input")
    if token[0] != token_type:
        error(f"Expected token type {token_type} but got {token[0]}")
    if token_value is not None and token[1] != token_value:
        error(f"Expected token value '{token_value}' but got '{token[1]}'")
    advance()

def error(message):
    """Raise a syntax error with line and column info."""
    token = current_token()
    if token:
        raise Exception(f"Syntax error at line {token[2]}, col {token[3]}: {message} (got {token})")
    else:
        raise Exception(f"Syntax error at end of input: {message}")

# --------------------------------------------------
# Parsing Functions (Based on our Context-Free Grammar)
# --------------------------------------------------

# Program → VariableDeclaration ProcedureDefinitions MainBlock
def parse_program():
    program = {}
    # Optional variable declaration (must be at the beginning)
    if current_token() and current_token()[0] == 'PIPE':
        program['variables'] = parse_variable_declaration()
    else:
        program['variables'] = []
    
    # Zero or more procedure definitions
    procedures_list = []
    while current_token() and current_token()[0] == 'ID' and current_token()[1] == 'proc':
        procedures_list.append(parse_procedure_definition())
    program['procedures'] = procedures_list
    
    # Optional main code block
    if current_token() and current_token()[0] == 'LBRACKET':
        program['main'] = parse_code_block()
    else:
        program['main'] = []
    
    return program

# VariableDeclaration → "|" IdentifierList "|"
def parse_variable_declaration():
    vars_list = []
    expect('PIPE')  # Opening '|'
    while current_token() and current_token()[0] == 'ID':
        var_name = current_token()[1]
        if var_name in variables:
            error(f"Variable '{var_name}' already declared")
        vars_list.append(var_name)
        variables.add(var_name)
        advance()
    expect('PIPE')  # Closing '|'
    return vars_list

# ProcedureDefinition → "proc" Identifier { ":" Identifier } CodeBlock
def parse_procedure_definition():
    expect('ID', 'proc')  # Expect the keyword 'proc'
    if current_token() is None or current_token()[0] != 'ID':
        error("Expected procedure name after 'proc'")
    proc_name = current_token()[1]
    advance()
    
    params = []
    # Zero or more parameters (each preceded by a colon)
    while current_token() and current_token()[0] == 'COLON':
        advance()  # Skip the colon
        if current_token() is None or current_token()[0] != 'ID':
            error("Expected parameter name after ':'")
        params.append(current_token()[1])
        advance()
    
    body = parse_code_block()
    proc_def = {'name': proc_name, 'params': params, 'body': body}
    procedures[proc_name] = proc_def  # Record the procedure definition
    return proc_def

# CodeBlock → "[" InstructionList "]"
def parse_code_block():
    expect('LBRACKET')
    instructions = []
    while current_token() and current_token()[0] != 'RBRACKET':
        instructions.append(parse_instruction())
    expect('RBRACKET')
    return instructions

# Instruction → ProcedureCall
# (For simplicity, this version treats every instruction as a procedure call.)
def parse_instruction():
    return parse_procedure_call()

# ProcedureCall → Identifier { ":" Expression } "."
def parse_procedure_call():
    if current_token() is None or current_token()[0] != 'ID':
        error("Expected procedure name in procedure call")
    proc_name = current_token()[1]
    if proc_name not in procedures:
        error(f"Procedure '{proc_name}' not declared")
    advance()
    
    args = []
    while current_token() and current_token()[0] == 'COLON':
        advance()  # Skip the colon
        args.append(parse_expression())
    
    expect('DOT')
    return ('proc_call', proc_name, args)

# Expression → NUMBER | Identifier
def parse_expression():
    token = current_token()
    if token is None:
        error("Expected an expression but found end of input")
    if token[0] == 'NUMBER':
        value = token[1]
        advance()
        return value
    elif token[0] == 'ID':
        value = token[1]
        advance()
        return value
    else:
        error("Expected an expression (NUMBER or ID)")

# --------------------------------------------------
# Main Function
# --------------------------------------------------
def main():
    global tokens, pos, variables, procedures
    if len(sys.argv) < 2:
        print("Usage: python robot_parser_proc.py <filename>")
        sys.exit(1)
    
    filename = sys.argv[1]
    try:
        with open(filename, 'r') as file:
            source_code = file.read()
    except IOError as e:
        print(f"Error reading file {filename}: {e}")
        sys.exit(1)
    
    # 1. Tokenize the source code using Regular Expressions.
    tokens = tokenize(source_code)
    
    # Reset global state before parsing.
    pos = 0
    variables = set()
    procedures = {}
    
    # 2. Parse the token stream following our context-free grammar.
    try:
        ast = parse_program()
        print("Parsed Program AST:")
        print(ast)
    except Exception as e:
        print("Parsing error:", e)

if __name__ == '__main__':
    main()
