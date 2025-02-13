#!/usr/bin/env python3
"""
main.py

Este archivo es el punto de entrada del programa.
Se encarga de preguntar al usuario el nombre del archivo de texto a cargar
y luego invoca la lógica (en logic.py) para verificar si el archivo cumple
con las reglas del lenguaje.
El programa imprime True si el archivo es correcto o False en caso contrario.
"""

from logic import check_file

def main():
    filename = input("Ingrese el nombre del archivo a cargar (ej: caso_prueba.txt): ").strip()
    result = check_file(filename)
    print(result)

if __name__ == '__main__':
    main()
