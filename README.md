# py-param-cad

Generador paramétrico de modelos CAD 3D y planos 2D de fabricación para piezas de ingeniería estructural.

---

## Descripción

Aplicación de escritorio en Python/PyQt6 que automatiza la generación de modelos CAD 3D editables y planos 2D de fabricación a partir de parámetros técnicos ingresados por el usuario. Simula el flujo real de trabajo multidisciplina (mecánica, estructura, eléctrica).

**Pieza implementada — MVP:** Placa Base Estructural con:
- 4 patrones de perforaciones (ninguno / rectangular 4 / rectangular 6 / lineal 2)
- Ranuras de ajuste opcionales
- 5 materiales (ASTM A36, A572 Gr.50, Inox 304/316, Al 6061-T6)
- Validaciones de manufacturabilidad en tiempo real (criterios AISC / IRAM)
- Exportación a `.FCStd` (FreeCAD nativo) y `.STEP` (intercambio universal)

---

## Requisitos

| Dependencia | Versión mínima | Notas |
|-------------|----------------|-------|
| Python | 3.12 | |
| PyQt6 | 6.6 | GUI |
| SQLAlchemy | 2.0 | ORM SQLite |
| pydantic-settings | 2.0 | Configuración tipada |
| ezdxf | 1.4 | Generación DXF (Semana 10) |
| openpyxl | 3.1 | BOM Excel (Semana 11) |
| reportlab | 4.0 | BOM PDF (Semana 11) |
| **FreeCAD 1.0** | 1.0 | Motor CAD 3D — instalación separada |

> **FreeCAD** debe estar instalado en `C:\Program Files\FreeCAD 1.0\`.
> Descarga: https://www.freecad.org/downloads.php

---

## Instalación

```bash
git clone https://github.com/federicoarielcasado/py-param-cad.git
cd py-param-cad

# Dependencias de producción
pip install -r requirements.txt

# Dependencias de desarrollo (tests)
pip install -r requirements-dev.txt
```

---

## Uso

```bash
python -m cad_generator.main
```

**Flujo básico:**
1. Seleccioná la pieza en el catálogo (panel izquierdo)
2. Ingresá los parámetros — el diagrama esquemático se actualiza en tiempo real
3. Verificá que las validaciones estén en verde (✅)
4. Hacé clic en **Crear Diseño** para registrarlo
5. Hacé clic en **Generar** → se genera `.FCStd` + `.STEP` en la carpeta `outputs/`

---

## Tests

```bash
python -m pytest cad_generator/tests/ -v
```

```
50 passed in ~1s
```

Cobertura:
- `test_models.py` — serialización JSON, propiedades calculadas
- `test_repositories.py` — CRUD completo + lógica de revisiones
- `test_validation_engine.py` — 8 reglas de manufacturabilidad
- `test_piece_controller.py` — pipeline completo con motor CAD mockeado

---

## Estructura del proyecto

```
py-param-cad/
├── cad_generator/
│   ├── main.py                      # Punto de entrada
│   ├── config/
│   │   ├── settings.py              # Configuración (pydantic-settings)
│   │   ├── piece_catalog.json       # Definición de piezas y parámetros
│   │   └── catalog_loader.py        # Acceso tipado al catálogo
│   ├── data/
│   │   ├── models.py                # ORM: PieceType, Design, Revision, BOMItem
│   │   ├── database.py              # Engine SQLite + get_session()
│   │   └── repositories.py         # Patrón repositorio (CRUD)
│   ├── core/
│   │   ├── validation_engine.py     # Validación de parámetros (reglas AISC/IRAM)
│   │   ├── piece_controller.py      # Fachada: orquesta generación completa
│   │   ├── bom_generator.py         # BOM automática (Semana 11)
│   │   └── revision_manager.py      # ECO / revisiones (Semana 12)
│   ├── cad/
│   │   ├── base_engine.py           # Interfaz ICADEngine (ABC)
│   │   ├── freecad_engine.py        # Adaptador FreeCAD (subprocess)
│   │   ├── solidworks_engine.py     # Stub SolidWorks (Fase 2)
│   │   └── scripts/
│   │       └── freecad_generate.py  # Script standalone para Python 3.11
│   ├── drawing/
│   │   └── dxf_generator.py         # Planos DXF con ezdxf (Semana 10)
│   ├── gui/
│   │   ├── main_window.py           # Ventana principal (QSplitter + QStackedWidget)
│   │   ├── catalog_widget.py        # Árbol de catálogo de piezas
│   │   ├── parameter_form.py        # Formulario paramétrico dinámico
│   │   ├── schematic_viewer.py      # Diagrama esquemático QPainter
│   │   ├── new_design_dialog.py     # Diálogo de creación de diseño
│   │   └── revision_panel.py        # Panel de historial (Semana 12)
│   ├── assets/
│   │   └── schematics/              # Imágenes esquemáticas por parámetro
│   └── tests/
│       ├── conftest.py
│       ├── test_models.py
│       ├── test_repositories.py
│       ├── test_validation_engine.py
│       └── test_piece_controller.py
├── PROXIMOS_PASOS.md
├── requirements.txt
└── requirements-dev.txt
```

---

## Estado de desarrollo

| Semana | Módulo | Estado |
|--------|--------|--------|
| 1-2 | Data layer (SQLite + repositorios) | ✅ |
| 3-4 | GUI: catálogo + formulario paramétrico | ✅ |
| 5-6 | SchematicViewer dinámico (QPainter) | ✅ |
| 7-8 | Motor CAD FreeCAD → `.FCStd` + `.STEP` | ✅ |
| 9 | Validaciones avanzadas + panel de resultado | ⏳ |
| 10 | Planos 2D DXF + PDF (cajetín IRAM 4505) | ⏳ |
| 11 | BOM automática Excel + PDF | ⏳ |
| 12 | Panel de revisiones + ECO básico | ⏳ |
| 13-14 | Testing integral + empaquetado `.exe` | ⏳ |

Ver [PROXIMOS_PASOS.md](PROXIMOS_PASOS.md) para el detalle completo.

---

## Arquitectura

```
GUI (PyQt6)
    │ signals/slots
Core (PieceController, ValidationEngine)
    │
CAD Adapter (ICADEngine)
    ├── FreeCADEngine  ← subprocess Python 3.11
    └── SolidWorksEngine (Fase 2)
    │
Data Layer (SQLAlchemy / SQLite)
```

El motor FreeCAD se ejecuta como **subproceso** (no embebido) para evitar conflictos entre Python 3.12 del proyecto y Python 3.11 bundleado por FreeCAD 1.0.

---

## Licencia

Uso personal / proyecto privado.
