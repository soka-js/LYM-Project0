#!/usr/bin/env python3
"""
logic.py

This module contains the logic for our robot control language parser.
It uses:
  - Regular Expressions (see comments "regex") for lexical analysis (tokenization).
  - A Recursive‑Descent Parser (see comments "grammar") based on a context‑free grammar.
  - A Semantic Analysis phase (see comments "semantic analysis") that checks, for example,
    that constants are used where required.
    
The module exposes the function check_file(filename), which returns True if the file
satisfies the language rules; False otherwise.
"""

import re

# --------------------------------------------------
# Tokenization (Lexer) – using Regular Expressions (Regex)
# --------------------------------------------------
def tokenize(text):
    # The order of patterns is important; e.g., ":=" must be matched before ":".
    token_specs = [
        ('ASSIGN',   r':='),   # assignment operator (regex topic)
        ('HASHID',   r'#[A-Za-z_][A-Za-z0-9_]*'),  # constants starting with '#' (regex)
        ('NUMBER',   r'\d+'),
        ('ID',       r'[A-Za-z_][A-Za-z0-9_]*'),
        ('PIPE',     r'\|'),
        ('LBRACKET', r'\['),
        ('RBRACKET', r'\]'),
        ('COLON',    r':'),
        ('DOT',      r'\.'), 
        ('COMMA',    r','),    # used to separate local variables
        ('SKIP',     r'[ \t]+'),  # whitespace to ignore
        ('NEWLINE',  r'\n'),
        ('MISMATCH', r'.'),
    ]
    # Build a master regular expression that matches any token (regex topic)
    token_regex = "|".join("(?P<%s>%s)" % (name, pattern) for name, pattern in token_specs)
    regex = re.compile(token_regex)
    
    tokens = []
    line_num = 1
    line_start = 0
    
    # Scan through the input using the regular expression.
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
tokens = []       # List of tokens produced by tokenize() (grammar topic)
pos = 0           # Current position in the token list
variables = set() # Global variables declared at the start
procedures = {}   # Procedures defined in the program

def current_token():
    global tokens, pos
    if pos < len(tokens):
        return tokens[pos]
    return None

def advance():
    global pos
    pos += 1

def expect(token_type, token_value=None):
    # This function implements the concept of "matching a terminal" from the grammar.
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
# Parser Functions (Recursive-Descent Parser)
# (These functions implement the production rules of the grammar)
# --------------------------------------------------

# The top-level production: Program -> VariableDeclaration ProcedureDefinitions MainBlock
def parse_program():
    program = {}
    # Global variable declaration (if present)
    if current_token() and current_token()[0] == 'PIPE':
        program['variables'] = parse_variable_declaration()
    else:
        program['variables'] = []
    
    # Parse procedure definitions (zero or more)
    proc_defs = []
    while current_token() and current_token()[0] == 'ID' and current_token()[1] == 'proc':
        proc_defs.append(parse_procedure_definition())
    program['procedures'] = proc_defs
    
    # Parse the main code block (if present)
    if current_token() and current_token()[0] == 'LBRACKET':
        program['main'] = parse_code_block()
    else:
        program['main'] = []
    return program

# VariableDeclaration -> "|" IdentifierList "|"
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
    while True:
        token = current_token()
        if token and token[0] == 'COLON':
            advance()  # Skip the colon
            if current_token() is None or current_token()[0] != 'ID':
                error("Expected parameter name after ':'")
            params.append(current_token()[1])
            advance()
        elif token and token[0] == 'ID' and token[1].startswith("and"):
            advance()  # Skip the alternative label (e.g., "andBalloons")
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
    if token[0] == 'PIPE':
        return parse_variable_declaration()
    if token[0] == 'ID' and token[1] in ('if', 'while'):
        return parse_control_structure()
    if token[0] == 'ID' and (pos + 1 < len(tokens) and tokens[pos+1][0] == 'ASSIGN'):
        return parse_assignment()
    return parse_procedure_call()

# Assignment -> ID ASSIGN Expression DOT
def parse_assignment():
    if current_token() is None or current_token()[0] != 'ID':
        error("Expected variable name in assignment")
    var_name = current_token()[1]
    advance()
    expect('ASSIGN')
    expr = parse_expression()
    expect('DOT')
    # (grammar: assignment production)
    return ('assign', var_name, expr)

# ProcedureCall -> ID { ParameterPart } [DOT]
def parse_procedure_call():
    global pos, tokens
    token = current_token()
    if token is None or token[0] != 'ID':
        error("Expected procedure name in procedure call")
    proc_name = token[1]
    advance()
    args = []
    while current_token() is not None:
        token = current_token()
        if token[0] == 'COLON':
            advance()
            args.append(parse_expression())
        elif token[0] == 'ID':
            if pos + 1 < len(tokens) and tokens[pos+1][0] == 'COLON':
                advance()  # Skip label (e.g., "ofType", "with", etc.)
                expect('COLON')
                args.append(parse_expression())
            else:
                break
        else:
            break
    token = current_token()
    if token is not None and token[0] == 'DOT':
        advance()
    elif token is not None and token[0] != 'RBRACKET':
        error("Expected token type DOT or end-of-block but got " + str(token))
    # (grammar: procedure call production)
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

# Condition is treated simply as an expression in this parser.
def parse_condition():
    return parse_expression()

# --------------------------------------------------
# Expression Parsing – Using Grammar and Tagging (for Semantic Analysis)
# (Topic: Context-Free Grammars and Expression Parsing)
# --------------------------------------------------
def parse_expression():
    token = current_token()
    if token is None:
        error("Expected an expression but found end of input")
    # If the token is a number, return a tuple tagged as 'num'
    if token[0] == 'NUMBER':
        value = token[1]
        advance()
        return ('num', value)
    # If the token is a HASHID, return a tuple tagged as 'const' (constant)
    elif token[0] == 'HASHID':
        value = token[1]
        advance()
        return ('const', value)
    # If the token is an ID (variable), return a tuple tagged as 'id'
    elif token[0] == 'ID':
        value = token[1]
        advance()
        return ('id', value)
    else:
        error("Expected an expression (NUMBER, ID, or HASHID)")

# --------------------------------------------------
# Semantic Analysis – Enforce constant usage where required
# (Topic: Semantic Analysis)
# --------------------------------------------------
def check_semantics(node):
    # Recursively traverse the AST and enforce that specific commands use constants.
    if isinstance(node, dict):
        for key, value in node.items():
            check_semantics(value)
    elif isinstance(node, list):
        for item in node:
            check_semantics(item)
    elif isinstance(node, tuple):
        if node[0] == 'proc_call':
            proc_name = node[1]
            args = node[2]
            # Example semantic rules:
            if proc_name == 'face':
                # The 'face' command must have a constant as its first argument.
                if len(args) < 1 or args[0][0] != 'const':
                    raise Exception("Semantic error: 'face' command requires a constant argument (e.g., #north).")
            elif proc_name == 'turn':
                # The 'turn' command must have a constant (e.g., #left, #right, or #around)
                if len(args) < 1 or args[0][0] != 'const':
                    raise Exception("Semantic error: 'turn' command requires a constant argument (e.g., #left).")
            elif proc_name == 'put':
                # The 'put' command should have at least two arguments and the second must be constant.
                if len(args) < 2 or args[1][0] != 'const':
                    raise Exception("Semantic error: 'put' command requires a constant type argument (e.g., #chips).")
            elif proc_name == 'pick':
                # The 'pick' command should have at least two arguments and the second must be constant.
                if len(args) < 2 or args[1][0] != 'const':
                    raise Exception("Semantic error: 'pick' command requires a constant type argument (e.g., #balloons).")
        # Recursively check all tuple items.
        for item in node:
            check_semantics(item)

# --------------------------------------------------
# Main Function for Logic – Integrates Lexing, Parsing, and Semantic Checks
# (Topics: Regex, CFG, and Semantic Analysis)
# --------------------------------------------------
def check_file(filename):
    """
    Reads the file, tokenizes it, parses it, and performs semantic checks.
    Returns True if the file fully complies with the language rules; False otherwise.
    Additionally, for the global case, the variable declaration must contain exactly 4 identifiers.
    """
    global tokens, pos, variables, procedures
    try:
        with open(filename, 'r') as file:
            source_code = file.read()
        tokens = tokenize(source_code)
        pos = 0
        variables = set()
        procedures = {}
        program = parse_program()
        # Semantic requirement: global variable declaration must have exactly 4 identifiers.
        if len(program['variables']) != 4:
            raise Exception("Global variable declaration must have exactly 4 identifiers.")
        # Ensure that all tokens were consumed.
        if pos != len(tokens):
            raise Exception("Extra tokens found at the end of the input.")
        # Perform semantic analysis on the AST.
        check_semantics(program)
        return True
    except Exception as e:
        # Uncomment the next line to print error details during debugging:
        # print("Parsing/Semantic error:", e)
        return False
