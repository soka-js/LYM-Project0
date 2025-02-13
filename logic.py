#!/usr/bin/env python3
"""
logic.py

Este archivo contiene la lógica de nuestro parser para el lenguaje de control de robot.
Utiliza expresiones regulares para el análisis léxico (tokenización) y un parser
recursivo-descendente basado en una gramática libre de contexto para verificar la sintaxis.

El módulo expone la función check_file(filename) que retorna True si el archivo cumple
con las reglas del lenguaje; False en caso contrario.
"""

import re

# --------------------------------------------------
# Tokenización (Lexer)
# --------------------------------------------------
def tokenize(text):
    # Order matters: longer tokens like ":=" must come before ":".
    token_specs = [
        ('ASSIGN',   r':='),   # operador de asignación
        ('HASHID',   r'#[A-Za-z_][A-Za-z0-9_]*'),  # ej: #chips, #north
        ('NUMBER',   r'\d+'),
        ('ID',       r'[A-Za-z_][A-Za-z0-9_]*'),
        ('PIPE',     r'\|'),
        ('LBRACKET', r'\['),
        ('RBRACKET', r'\]'),
        ('COLON',    r':'),
        ('DOT',      r'\.'),
        ('COMMA',    r','),    # para separar variables locales
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
# Estado Global del Parser
# --------------------------------------------------
tokens = []   # Lista de tokens (se llena con tokenize)
pos = 0       # Posición actual en la lista

variables = set()   # Variables globales
procedures = {}     # Procedimientos definidos

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
# Funciones del Parser (Recursivo-Descendente)
# --------------------------------------------------

# Programa -> VariableDeclaration ProcedureDefinitions MainBlock
def parse_program():
    program = {}
    # Declaración global de variables (opcional)
    if current_token() and current_token()[0] == 'PIPE':
        program['variables'] = parse_variable_declaration()
    else:
        program['variables'] = []
    
    # Procedimientos (cero o más)
    proc_defs = []
    while current_token() and current_token()[0] == 'ID' and current_token()[1] == 'proc':
        proc_defs.append(parse_procedure_definition())
    program['procedures'] = proc_defs
    
    # Bloque principal (opcional)
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
            advance()  # saltar ":"
            if current_token() is None or current_token()[0] != 'ID':
                error("Expected parameter name after ':'")
            params.append(current_token()[1])
            advance()
        elif token and token[0] == 'ID' and token[1].startswith("and"):
            advance()  # saltar la etiqueta (ej: "andBalloons")
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
                advance()
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

# Condition se trata simplemente como una expresión en este parser
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
# Función principal de la lógica
# --------------------------------------------------
def check_file(filename):
    """
    Lee el archivo cuyo nombre se pasa como parámetro, lo tokeniza y lo parsea.
    Retorna True si el archivo cumple con las reglas del lenguaje; False en caso contrario.
    Además, para el caso global se exige que la declaración de variables tenga exactamente 4 identificadores.
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
        # Verificar que la declaración global tenga exactamente 4 variables.
        if len(program['variables']) != 4:
            raise Exception("La declaración global de variables debe tener exactamente 4 identificadores.")
        # Verificar que se hayan consumido todos los tokens.
        if pos != len(tokens):
            raise Exception("Se encontraron tokens extra al final de la entrada.")
        return True
    except Exception as e:
        # Para depuración se puede imprimir el error:
        # print("Parsing error:", e)
        return False
