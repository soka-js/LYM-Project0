#!/usr/bin/env python3
"""
Robot Control Language Parser (Procedural Version)

This parser implements a syntax checker for a robot–control language.
It supports:
  - Global and local variable declarations (using | ... |)
  - Procedure definitions with parameters using both the standard (":")
    and alternate label syntaxes (e.g. "andBalloons:" or "ofType:")
  - Assignments (using :=)
  - Procedure calls (with parameter passing using labeled parameters)
  - Control structures: while and if-else
  - Basic expressions: numbers, identifiers, and hash–prefixed identifiers

The parser is built using regular expressions (for tokenization)
and a recursive–descent parser based on a context–free grammar.
"""

import re
import sys

# --------------------------------------------------
# Tokenization (Lexer)
# --------------------------------------------------
def tokenize(text):
    # Order matters: longer tokens like ":=" must come before ":".
    token_specs = [
        ('ASSIGN',   r':='),   # assignment operator
        ('HASHID',   r'#[A-Za-z_][A-Za-z0-9_]*'),  # e.g., #chips, #north
        ('NUMBER',   r'\d+'),
        ('ID',       r'[A-Za-z_][A-Za-z0-9_]*'),
        ('PIPE',     r'\|'),
        ('LBRACKET', r'\['),
        ('RBRACKET', r'\]'),
        ('COLON',    r':'),
        ('DOT',      r'\.'),
        ('COMMA',    r','),    # for separating local variable declarations
        ('SKIP',     r'[ \t]+'),
        ('NEWLINE',  r'\n'),
        ('MISMATCH', r'.'),
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
        elif kind in ('ID', 'HASHID'):
            tokens.append((kind, value, line_num, column))
        elif kind in ('PIPE', 'LBRACKET', 'RBRACKET', 'COLON', 'DOT', 'COMMA', 'ASSIGN'):
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
# Global Parser State
# --------------------------------------------------
tokens = []   # list of tokens (populated by tokenize)
pos = 0       # current position in tokens

# Global symbol tables for global variables and procedures
variables = set()
procedures = {}

def current_token():
    global tokens, pos
    if pos < len(tokens):
        return tokens[pos]
    return None

def advance():
    global pos
    pos += 1

def expect(token_type, token_value=None):
    token = current_token()
    if token is None:
        error("Unexpected end of input")
    if token[0] != token_type:
        error(f"Expected token type {token_type} but got {token[0]}")
    if token_value is not None and token[1] != token_value:
        error(f"Expected token value '{token_value}' but got '{token[1]}'")
    advance()

def error(message):
    token = current_token()
    if token:
        raise Exception(f"Syntax error at line {token[2]}, col {token[3]}: {message} (got {token})")
    else:
        raise Exception(f"Syntax error at end of input: {message}")

# --------------------------------------------------
# Parsing Functions (Recursive–Descent)
# --------------------------------------------------

# Program -> VariableDeclaration ProcedureDefinitions MainBlock
def parse_program():
    program = {}
    # Optional global variable declaration
    if current_token() and current_token()[0] == 'PIPE':
        program['variables'] = parse_variable_declaration()
    else:
        program['variables'] = []
    
    # Zero or more procedure definitions
    proc_defs = []
    while current_token() and current_token()[0] == 'ID' and current_token()[1] == 'proc':
        proc_defs.append(parse_procedure_definition())
    program['procedures'] = proc_defs
    
    # Optional main code block
    if current_token() and current_token()[0] == 'LBRACKET':
        program['main'] = parse_code_block()
    else:
        program['main'] = []
    return program

# VariableDeclaration -> "|" IdentifierList "|"
# Supports both global declarations (space-separated) and local ones (comma-separated)
def parse_variable_declaration():
    vars_list = []
    expect('PIPE')
    while current_token() and current_token()[0] == 'ID':
        var_name = current_token()[1]
        vars_list.append(var_name)
        advance()
        if current_token() and current_token()[0] == 'COMMA':
            advance()
    expect('PIPE')
    return vars_list

# ProcedureDefinition -> "proc" Identifier { (COLON | (ID starting with "and")) Parameter } CodeBlock
def parse_procedure_definition():
    expect('ID', 'proc')
    if current_token() is None or current_token()[0] != 'ID':
        error("Expected procedure name after 'proc'")
    proc_name = current_token()[1]
    advance()
    
    params = []
    # Loop to allow parameters using ":" or an alternative label (e.g., "andBalloons:")
    while True:
        token = current_token()
        if token and token[0] == 'COLON':
            advance()  # skip COLON
            if current_token() is None or current_token()[0] != 'ID':
                error("Expected parameter name after ':'")
            params.append(current_token()[1])
            advance()
        elif token and token[0] == 'ID' and token[1].startswith("and"):
            advance()  # skip the label (e.g., "andBalloons")
            expect('COLON')
            if current_token() is None or current_token()[0] != 'ID':
                error("Expected parameter name after 'and...:'")
            params.append(current_token()[1])
            advance()
        else:
            break

    body = parse_code_block()
    proc_def = {'name': proc_name, 'params': params, 'body': body}
    procedures[proc_name] = proc_def
    return proc_def

# CodeBlock -> "[" InstructionList "]"
def parse_code_block():
    expect('LBRACKET')
    instrs = []
    while current_token() and current_token()[0] != 'RBRACKET':
        instrs.append(parse_instruction())
    expect('RBRACKET')
    return instrs

# Instruction -> VariableDeclaration | Assignment | ControlStructure | ProcedureCall
def parse_instruction():
    token = current_token()
    if token is None:
        error("Unexpected end of input in instruction")
    # Local variable declaration starts with PIPE
    if token[0] == 'PIPE':
        return parse_variable_declaration()
    # Control structures: if or while
    if token[0] == 'ID' and token[1] in ('if', 'while'):
        return parse_control_structure()
    # Assignment: if an ID is followed by ASSIGN
    if token[0] == 'ID' and (pos + 1 < len(tokens) and tokens[pos+1][0] == 'ASSIGN'):
        return parse_assignment()
    # Otherwise, assume a procedure call
    return parse_procedure_call()

# Assignment -> ID ASSIGN Expression DOT
def parse_assignment():
    if current_token() is None or current_token()[0] != 'ID':
        error("Expected variable name in assignment")
    var_name = current_token()[1]
    advance()  # consume variable name
    expect('ASSIGN')
    expr = parse_expression()
    expect('DOT')
    return ('assign', var_name, expr)

# ProcedureCall -> ID { ParameterPart } [DOT]
# ParameterPart -> [ Label ] COLON Expression
# A Label is an ID token immediately followed by a COLON.
# Here, the trailing DOT is required unless the next token is RBRACKET.
def parse_procedure_call():
    global pos, tokens
    token = current_token()
    if token is None or token[0] != 'ID':
        error("Expected procedure name in procedure call")
    proc_name = token[1]
    advance()  # consume procedure name
    args = []
    # Look for parameters
    while current_token() is not None:
        token = current_token()
        if token[0] == 'COLON':
            # No label provided: just a colon then expression.
            advance()  # skip COLON
            args.append(parse_expression())
        elif token[0] == 'ID':
            # Look ahead: if the next token is COLON, treat current ID as a label.
            if pos + 1 < len(tokens) and tokens[pos+1][0] == 'COLON':
                advance()  # skip label token (e.g., "ofType", "with", etc.)
                expect('COLON')
                args.append(parse_expression())
            else:
                break
        else:
            break
    # If a DOT is present, consume it.
    # Otherwise, if the next token is RBRACKET, consider the DOT optional.
    token = current_token()
    if token is not None and token[0] == 'DOT':
        advance()
    elif token is not None and token[0] != 'RBRACKET':
        error("Expected token type DOT or end-of-block but got " + str(token))
    return ('proc_call', proc_name, args)

# ControlStructure -> WhileStructure | IfStructure
def parse_control_structure():
    token = current_token()
    if token[0] == 'ID' and token[1] == 'while':
        return parse_while_structure()
    elif token[0] == 'ID' and token[1] == 'if':
        return parse_if_structure()
    else:
        error("Unknown control structure")

# WhileStructure -> "while" COLON Condition "do" COLON CodeBlock
def parse_while_structure():
    expect('ID', 'while')
    expect('COLON')
    cond = parse_condition()
    cond_parts = [cond]
    while current_token() and not (current_token()[0] == 'ID' and current_token()[1] == 'do'):
        if current_token()[0] == 'COLON':
            advance()
            cond_parts.append(':')
            cond_parts.append(parse_expression())
        else:
            cond_parts.append(parse_expression())
    expect('ID', 'do')
    expect('COLON')
    block = parse_code_block()
    return ('while', cond_parts, block)

# IfStructure -> "if" COLON Condition "then" COLON CodeBlock [ "else" COLON CodeBlock ]
def parse_if_structure():
    expect('ID', 'if')
    expect('COLON')
    cond = parse_condition()
    cond_parts = [cond]
    while current_token() and not (current_token()[0] == 'ID' and current_token()[1] == 'then'):
        if current_token()[0] == 'COLON':
            advance()
            cond_parts.append(':')
            cond_parts.append(parse_expression())
        else:
            cond_parts.append(parse_expression())
    expect('ID', 'then')
    expect('COLON')
    then_block = parse_code_block()
    else_block = None
    if current_token() and current_token()[0] == 'ID' and current_token()[1] == 'else':
        advance()
        expect('COLON')
        else_block = parse_code_block()
    return ('if', cond_parts, then_block, else_block)

# Condition is simplified to an expression for our parser
def parse_condition():
    return parse_expression()

# Expression -> NUMBER | ID | HASHID
def parse_expression():
    token = current_token()
    if token is None:
        error("Expected an expression but found end of input")
    if token[0] == 'NUMBER':
        value = token[1]
        advance()
        return value
    elif token[0] in ('ID', 'HASHID'):
        value = token[1]
        advance()
        return value
    else:
        error("Expected an expression (NUMBER, ID, or HASHID)")

# --------------------------------------------------
# Main Function
# --------------------------------------------------
def main():
    global tokens, pos, variables, procedures
    if len(sys.argv) < 2:
        print("Usage: python parser.py <filename>")
        sys.exit(1)
    
    filename = sys.argv[1]
    try:
        with open(filename, 'r') as file:
            source_code = file.read()
    except IOError as e:
        print(f"Error reading file {filename}: {e}")
        sys.exit(1)
    
    try:
        tokens = tokenize(source_code)
        # Uncomment the following line to print the token list for debugging:
        # print("Tokens:", tokens)
        
        pos = 0
        variables = set()
        procedures = {}
        
        ast = parse_program()
        print("Parsed Program AST:")
        print(ast)
    except Exception as e:
        print("Parsing error:", e)

if __name__ == '__main__':
    main()
