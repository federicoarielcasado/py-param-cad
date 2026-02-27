# Próximos pasos — py-param-cad

> Documento de planificación actualizado al: 2026-02-26
> Estado actual: **Semanas 7-8 completas** — 50/50 tests ✅ — FreeCAD genera `.FCStd` + `.STEP` reales

---

## Estado de avance

| Semana | Tarea | Estado |
|--------|-------|--------|
| 1-2 | Arquitectura base + DB schema SQLite + repositorios | ✅ Completo |
| 3-4 | GUI: catálogo de piezas + formulario paramétrico | ✅ Completo |
| 5-6 | SchematicViewer dinámico (QPainter) + integración con formulario | ✅ Completo |
| 7-8 | Motor CAD: FreeCAD subprocess → .FCStd + .STEP | ✅ Completo |
| **9** | **Validaciones avanzadas + feedback de manufacturabilidad** | ⏳ Próximo |
| 10 | Generación planos 2D: DXF + PDF con cajetín IRAM 4505 | ⏳ Pendiente |
| 11 | BOM automática: Excel (.xlsx) + PDF | ⏳ Pendiente |
| 12 | Panel de revisiones en GUI + ECO básico | ⏳ Pendiente |
| 13-14 | Testing integral + empaquetado `.exe` (PyInstaller) | ⏳ Pendiente |

---

## Semana 9 — Validaciones avanzadas de manufacturabilidad

### Objetivo
Completar la capa de validación para que cubra el 100% de las reglas definidas y mostrar feedback claro al usuario tanto en el formulario como en los resultados de generación.

### Tareas

#### 9.1 — Ampliar reglas en `piece_catalog.json`
Agregar reglas faltantes para Placa Base:

| ID | Regla | Severidad |
|----|-------|-----------|
| VR-BP-09 | Separación mínima entre agujeros: `dist_centros >= 3 * d` (AISC) | error |
| VR-BP-10 | Relación largo_ranura / ancho_ranura ≤ 8 (fresabilidad) | warning |
| VR-BP-11 | Si `patron_perforaciones == "rectangular_6"`: ancho debe alojar 2 margenes + 3 diámetros | error |

#### 9.2 — Mejorar feedback en la GUI
- Mostrar ícono de estado (✅ / ⚠️ / ❌) en el header de cada parámetro cuando cambia su valor
- En `_ValidationPanel`: agrupar mensajes por severidad con separadores visuales
- Tooltip en el botón "Generar" listando warnings activos

#### 9.3 — Panel de resultado de generación
Actualmente el resultado se muestra en un `QMessageBox`. Reemplazarlo por un panel lateral
(`_ResultPanel`) que persista en la UI con:
- Paths de archivos generados (clickeables para abrir en explorador)
- Tiempo de generación
- Lista de advertencias
- Botón "Abrir en FreeCAD"

---

## Semana 10 — Generación de planos 2D

### Objetivo
Generar planos de fabricación en formato DXF + PDF con cajetín normalizado IRAM 4505 / ISO 7200.

### Tareas

#### 10.1 — `drawing/dxf_generator.py`
Implementar generador DXF con `ezdxf`:

```
Vistas a generar:
  ┌─────────────┬─────────────┐
  │  Planta     │  Isométrica │
  │  (top view) │             │
  ├─────────────┼─────────────┤
  │  Alzado     │  Perfil     │
  │  (front)    │  (side)     │
  └─────────────┴─────────────┘
  └──────── Cajetín IRAM ─────┘
```

Contenido del cajetín IRAM 4505:
- Empresa / Proyecto
- Título de la pieza
- Número de plano + Revisión
- Material / Escala / Unidades
- Fecha / Autor / Aprobación
- Notas técnicas (tolerancias generales, acabado)

#### 10.2 — Exportación PDF
Convertir DXF a PDF usando `reportlab` o llamando a FreeCAD TechDraw como subproceso.

#### 10.3 — Integración con `PieceController.generate()`
Agregar al pipeline del Step 4 la llamada al generador de planos:
```python
# Después de generar el 3D:
dxf_result = dxf_gen.generate(piece_code, parameters, output_dir, revision_code)
rev_repo.update_output_paths(revision_id, {"dxf": ..., "pdf": ...})
```

---

## Semana 11 — BOM automática

### Objetivo
Generar Lista de Materiales (BOM) desde el modelo en formato Excel y PDF.

### Tareas

#### 11.1 — `core/bom_generator.py`
Implementar `BOMGenerator.generate(piece_code, parameters, revision_id)`:
- Leer `bom_template` del `piece_catalog.json`
- Calcular volumen + peso con densidades por material:

| Material | Densidad (kg/mm³) |
|----------|------------------|
| ASTM A36 | 7.85 × 10⁻⁶ |
| SS304 | 7.93 × 10⁻⁶ |
| AL6061T6 | 2.70 × 10⁻⁶ |

- Persistir ítems en tabla `bom_items` (ya existe en DB)

#### 11.2 — Exportación Excel (`openpyxl`)
- Hoja "BOM" con tabla formateada, encabezados, bordes
- Hoja "Resumen" con datos del plano y firma

#### 11.3 — Exportación PDF (`reportlab`)
- Layout tipo tabla técnica de fabricación

---

## Semana 12 — Panel de revisiones + ECO básico

### Objetivo
Implementar la GUI del historial de revisiones y el flujo ECO mínimo.

### Tareas

#### 12.1 — `gui/revision_panel.py`
Panel que muestra el historial de una pieza:
- Lista de revisiones con código, fecha, usuario, estado ECO
- Comparación de parámetros entre dos revisiones seleccionadas
- Botón "Emitir" (cambia eco_status: draft → issued)
- Botón "Obsoleto" (issued → obsolete)

#### 12.2 — Integración en `MainWindow`
Agregar tercera pestaña o panel desplegable "Historial" al QStackedWidget.

#### 12.3 — Exportación de paquete ZIP
Implementar `CU-04 — Exportar paquete para fabricación`:
```
output_package/
├── base_plate_A.FCStd
├── base_plate_A.step
├── PL-001_A.dxf
├── PL-001_A.pdf
├── BOM_PL-001_A.xlsx
└── README_PL-001_A.txt
```

---

## Semanas 13-14 — Testing integral + empaquetado

### Objetivo
Suite completa de pruebas de integración y distribución como `.exe` standalone.

### Tareas

#### 13.1 — Tests de integración end-to-end
- `test_full_pipeline.py`: desde parámetros → modelo generado → plano → BOM
- Tests de regresión para cada patrón de perforaciones y material

#### 13.2 — Empaquetado PyInstaller
```bash
pyinstaller --onefile --windowed \
  --add-data "cad_generator/config:config" \
  --add-data "cad_generator/assets:assets" \
  --add-data "cad_generator/cad/scripts:cad/scripts" \
  main.py
```
Consideraciones:
- FreeCAD **no** va dentro del `.exe` — se detecta en runtime
- SQLite DB se crea en `%APPDATA%/py-param-cad/` en modo empaquetado
- Verificar que `freecad_generate.py` se incluya como dato

#### 13.3 — Instalador Windows (opcional)
Considerar `NSIS` o `Inno Setup` para un instalador `.exe` más profesional.

---

## Decisiones de diseño pendientes

| # | Decisión | Opciones | Recomendación |
|---|----------|----------|---------------|
| D1 | Generación PDF de planos | `reportlab` directo vs FreeCAD TechDraw subprocess | `ezdxf` → DXF → FreeCAD TechDraw para PDF |
| D2 | Apertura de archivos generados desde GUI | `os.startfile()` vs subprocess | `os.startfile()` (Windows nativo) |
| D3 | Multi-pieza | Ampliar catálogo JSON con Viga HEB, Angular, Perno | Siguiente fase — no bloquea MVP |
| D4 | Empaquetado | `.exe` solo vs instalador NSIS | `.exe` standalone para MVP |

---

## Deuda técnica conocida

| Item | Impacto | Prioridad |
|------|---------|-----------|
| `solidworks_engine.py` es stub | Bajo (Fase 2) | Baja |
| `bom_generator.py` es stub | Medio — BOM no disponible hasta S11 | Media |
| `revision_panel.py` es stub | Medio — historial no visible en GUI hasta S12 | Media |
| `dxf_generator.py` es stub | Alto — planos son entregable clave | Alta |
| Validación VR-BP-09/10/11 faltante | Medio | Media |
| `_on_generate` abre `QMessageBox` básico | Bajo — reemplazar por `_ResultPanel` en S9 | Baja |

---

## Notas técnicas para continuación

### Protocolo subprocess FreeCAD (crítico)
```python
# freecadcmd.exe NO acepta args posicionales — los trata como documentos a abrir
# Pasar el path del JSON por variable de entorno:
env["FREECAD_PARAMS"] = str(params_file)
subprocess.run([freecadcmd_exe, freecad_generate_py], env=env, ...)

# freecadcmd.exe NO setea __name__ == "__main__"
# Al final del script, llamar main() incondicionalmente:
if __name__ == "__main__":
    main()
else:
    main()
```

### Estructura de outputs generados
```
outputs/
└── base_plate/
    └── {safe_design_name}/
        └── {revision_code}/         ← A, B, C...
            ├── base_plate_A.FCStd
            ├── base_plate_A.step
            ├── base_plate_A.dxf     ← Semana 10
            ├── base_plate_A.pdf     ← Semana 10
            ├── BOM_A.xlsx           ← Semana 11
            ├── BOM_A.pdf            ← Semana 11
            └── result.json          ← metadata de generación
```

### Tests: patrón para nuevas pruebas de controller
Ver `cad_generator/tests/test_piece_controller.py` — fixture `patched_controller`
que inyecta DB en memoria + settings mockeados + engine mock.
