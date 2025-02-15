#!/usr/bin/env python3
"""
logic.py

This module contains the logic for our robot control language parser.
It uses:
  - Regular Expressions (Regex) for lexical analysis.
  - A Recursive‑Descent Parser (Grammar) based on a context‑free grammar.
  - A Semantic Analysis phase to enforce that only allowed constants are used.
  
The module exposes the function check_file(filename), which returns True if the file complies with the language rules; False otherwise.
"""

import re

# --------------------------------------------------
# Tokenization (Lexer) – using Regex
# (Topic: Regular Expressions)
# --------------------------------------------------
def tokenize(text):
    # The order of patterns is important; longer tokens must come before shorter ones.
    token_specs = [
        ('ASSIGN',   r':='),   # assignment operator
        # Here we "hardcode" the valid constants:
        ('DIRECTION', r'#(north|south|east|west)'),  # allowed directions
        ('TURN',      r'#(left|right|around)'),      # allowed turn directions
        ('TYPE',      r'#(chips|balloons)'),          # allowed types
        ('NUMBER',   r'\d+'),
        ('ID',       r'[A-Za-z_][A-Za-z0-9_]*'),      # identifiers (variables, procedure names, etc.)
        ('PIPE',     r'\|'),
        ('LBRACKET', r'\['),
        ('RBRACKET', r'\]'),
        ('COLON',    r':'),
        ('DOT',      r'\.'),
        ('COMMA',    r','),    # for separating local variables
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
        elif kind in ('ID', 'DIRECTION', 'TURN', 'TYPE'):
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
# (Topic: Grammar – Managing Tokens and Parser State)
# --------------------------------------------------
tokens = []       # List of tokens produced by tokenize()
pos = 0           # Current position in the tokens list
variables = set() # Global variables declared at the beginning
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
    # This function matches a specific terminal from our grammar.
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
# Parser Functions (Recursive‑Descent Parsing – Grammar)
# (Topic: Context-Free Grammars and Parsing)
# --------------------------------------------------

def parse_program():
    # Program -> VariableDeclaration ProcedureDefinitions MainBlock
    program = {}
    if current_token() and current_token()[0] == 'PIPE':
        program['variables'] = parse_variable_declaration()
    else:
        program['variables'] = []
    
    proc_defs = []
    while current_token() and current_token()[0] == 'ID' and current_token()[1] == 'proc':
        proc_defs.append(parse_procedure_definition())
    program['procedures'] = proc_defs
    
    if current_token() and current_token()[0] == 'LBRACKET':
        program['main'] = parse_code_block()
    else:
        program['main'] = []
    return program

def parse_variable_declaration():
    # VariableDeclaration -> "|" IdentifierList "|"
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

def parse_procedure_definition():
    # ProcedureDefinition -> "proc" Identifier { (COLON | (ID starting with "and")) Parameter } CodeBlock
    expect('ID', 'proc')
    if current_token() is None or current_token()[0] != 'ID':
        error("Expected procedure name after 'proc'")
    proc_name = current_token()[1]
    advance()
    
    params = []
    while True:
        token = current_token()
        if token and token[0] == 'COLON':
            advance()  # Skip ":"
            if current_token() is None or current_token()[0] != 'ID':
                error("Expected parameter name after ':'")
            params.append(current_token()[1])
            advance()
        elif token and token[0] == 'ID' and token[1].startswith("and"):
            advance()  # Skip alternative label (e.g., "andBalloons")
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

def parse_code_block():
    # CodeBlock -> "[" InstructionList "]"
    expect('LBRACKET')
    instrs = []
    while current_token() and current_token()[0] != 'RBRACKET':
        instrs.append(parse_instruction())
    expect('RBRACKET')
    return instrs

def parse_instruction():
    # Instruction -> VariableDeclaration | Assignment | ControlStructure | ProcedureCall
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

def parse_assignment():
    # Assignment -> ID ASSIGN Expression DOT
    if current_token() is None or current_token()[0] != 'ID':
        error("Expected variable name in assignment")
    var_name = current_token()[1]
    advance()
    expect('ASSIGN')
    expr = parse_expression()
    expect('DOT')
    return ('assign', var_name, expr)

def parse_procedure_call():
    # ProcedureCall -> ID { ParameterPart } [DOT]
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
                advance()  # Skip label (e.g., "ofType", "with")
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
    return ('proc_call', proc_name, args)

def parse_control_structure():
    # ControlStructure -> WhileStructure | IfStructure
    token = current_token()
    if token[0] == 'ID' and token[1] == 'while':
        return parse_while_structure()
    elif token[0] == 'ID' and token[1] == 'if':
        return parse_if_structure()
    else:
        error("Unknown control structure")

def parse_while_structure():
    # WhileStructure -> "while" COLON Condition "do" COLON CodeBlock
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

def parse_if_structure():
    # IfStructure -> "if" COLON Condition "then" COLON CodeBlock [ "else" COLON CodeBlock ]
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

def parse_condition():
    # Condition is parsed as an expression.
    return parse_expression()

# --------------------------------------------------
# Expression Parsing – Using Grammar and Tagging (Semantic Preparation)
# (Topic: Context-Free Grammars and Expression Parsing)
# --------------------------------------------------
def parse_expression():
    token = current_token()
    if token is None:
        error("Expected an expression but found end of input")
    # For numbers, return a tuple tagged as 'num'
    if token[0] == 'NUMBER':
        value = token[1]
        advance()
        return ('num', value)
    # For tokens representing allowed constants (DIRECTION, TURN, or TYPE), return them as 'const'
    elif token[0] in ('DIRECTION', 'TURN', 'TYPE'):
        value = token[1]
        advance()
        return ('const', value)
    # Otherwise, if it's an identifier (variable), return a tuple tagged as 'id'
    elif token[0] == 'ID':
        value = token[1]
        advance()
        return ('id', value)
    else:
        error("Expected an expression (NUMBER, ID, or valid constant)")

# --------------------------------------------------
# Semantic Analysis – Enforcing Allowed Constants
# (Topic: Semantic Analysis)
# --------------------------------------------------
ALLOWED_DIRECTIONS = {'#north', '#south', '#east', '#west'}
ALLOWED_TURNS = {'#left', '#right', '#around'}
ALLOWED_TYPES = {'#chips', '#balloons'}

def check_semantics(node):
    if isinstance(node, dict):
        for key, value in node.items():
            check_semantics(value)
    elif isinstance(node, list):
        for item in node:
            check_semantics(item)
    elif isinstance(node, tuple):
        # Example: enforce that the 'face' command must have a valid direction constant.
        if node[0] == 'proc_call':
            proc_name = node[1]
            args = node[2]
            if proc_name == 'face':
                if len(args) < 1 or args[0][0] != 'const' or args[0][1] not in ALLOWED_DIRECTIONS:
                    raise Exception("Semantic error: 'face' command requires a valid direction constant (e.g., #north).")
            elif proc_name == 'turn':
                if len(args) < 1 or args[0][0] != 'const' or args[0][1] not in ALLOWED_TURNS:
                    raise Exception("Semantic error: 'turn' command requires a valid turn constant (e.g., #left).")
            elif proc_name in ('put', 'pick'):
                if len(args) < 2 or args[1][0] != 'const' or args[1][1] not in ALLOWED_TYPES:
                    raise Exception("Semantic error: 'put'/'pick' command requires a valid type constant (e.g., #chips).")
        for item in node:
            check_semantics(item)

# --------------------------------------------------
# Main Function for Logic – Integrates Lexing, Parsing, and Semantic Analysis
# (Topics: Regex, CFG, and Semantic Analysis)
# --------------------------------------------------
def check_file(filename):
    """
    Reads the file, tokenizes it, parses it, and performs semantic analysis.
    Returns True if the file fully complies with the language rules; False otherwise.
    Also, the global variable declaration must contain exactly 4 identifiers.
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
        # Enforce that the global variable declaration has exactly 4 identifiers.
        if len(program['variables']) != 4:
            raise Exception("Global variable declaration must have exactly 4 identifiers.")
        # Ensure that all tokens have been consumed.
        if pos != len(tokens):
            raise Exception("Extra tokens found at the end of the input.")
        # Perform semantic analysis.
        check_semantics(program)
        return True
    except Exception as e:
        # Uncomment the next line to print error details during debugging:
        # print("Parsing/Semantic error:", e)
        return False
