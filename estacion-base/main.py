#!/usr/bin/env python3
"""Shim para compatibilidad: ejecuta el paquete src/estacion_base."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from estacion_base.__main__ import main
if __name__ == "__main__":
    main()
