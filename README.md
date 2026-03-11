# PyParamCAD 🔩

**Generador paramétrico de escritorio para modelos CAD 3D y planos técnicos 2D**

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-151%2F151%20passing-brightgreen.svg)](cad_generator/tests/)
[![License](https://img.shields.io/badge/License-Privada-red.svg)](LICENSE)

---

## 📋 Descripción

PyParamCAD es una aplicación de escritorio que automatiza la generación de **modelos CAD 3D editables y planos técnicos 2D de fabricación** a partir de parámetros técnicos ingresados por el usuario. Simula el flujo real de trabajo multidisciplina (mecánica, estructura) incluyendo validación de manufacturabilidad, gestión de revisiones y exportación completa de entregables.

| Módulo | Función | Salida |
|--------|---------|--------|
| `ValidationEngine` | Reglas de manufacturabilidad (AISC/IRAM) | Feedback en tiempo real |
| `FreeCADEngine` | Generación del modelo 3D paramétrico | `.FCStd`, `.STEP` |
| `DXFDrawingGenerator` | Planos 2D con cajetín IRAM 4505 | `.DXF`, `.PDF` |
| `BOMGenerator` | Lista de materiales con cálculo de peso | `.xlsx`, `.PDF` |
| `RevisionManager` | Historial ECO (Borrador → Emitido → Obsoleto) | Trazabilidad completa |

### ✨ Características Principales

**Modelado Paramétrico (MVP — Placa Base Estructural):**
- ✅ **Geometría configurable**: largo, ancho, espesor, 4 patrones de perforaciones, ranuras de ajuste
- ✅ **Materiales predefinidos**: ASTM A36, ASTM A572 Gr.50, Inox 304, Inox 316, Aluminio 6061-T6
- ✅ **Modelo 3D**: archivo `.FCStd` (FreeCAD nativo) + `.STEP` (intercambio universal)

**Validación y Calidad:**
- ✅ **11 reglas de manufacturabilidad** en tiempo real (criterios AISC / IRAM)
- ✅ **Diagrama esquemático interactivo** con actualización en tiempo real (QPainter)
- ✅ **Ningún modelo inválido** se escribe en disco sin aviso al usuario

**Documentación y Entregables:**
- ✅ **Planos 2D** (DXF + PDF): 3 vistas (planta, alzado, perfil), tabla de coordenadas de agujeros, notas técnicas, cajetín IRAM 4505
- ✅ **BOM automática**: Excel (`.xlsx`) + PDF con peso calculado por material
- ✅ **Paquete ZIP** con todos los entregables de fabricación listos para enviar al taller

**Gestión y Configuración:**
- ✅ **Historial de revisiones**: trazabilidad completa con flujo ECO
- ✅ **Configuración de empresa**: nombre, autor, rutas — guardados en `.env`
- ✅ **Suite de 151 tests** automatizados

---

## 🚀 Instalación

### Requisitos Previos

- **Python 3.12** o superior
- **FreeCAD 1.0** instalado en `C:\Program Files\FreeCAD 1.0\` — [Descargar](https://www.freecad.org/downloads.php)

### Pasos de Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/federicoarielcasado/py-param-cad.git
cd py-param-cad

# 2. Crear entorno virtual (recomendado)
python -m venv venv
venv\Scripts\activate

# 3. Instalar dependencias de producción
pip install -r requirements.txt

# 4. Instalar dependencias de desarrollo (para tests)
pip install -r requirements-dev.txt

# 5. Ejecutar la aplicación
python -m cad_generator.main
```

### Dependencias Principales

| Librería | Versión mínima | Para qué sirve |
|----------|---------------|----------------|
| PyQt6 | ≥ 6.6 | Interfaz gráfica de escritorio |
| SQLAlchemy | ≥ 2.0 | ORM / persistencia SQLite |
| pydantic-settings | ≥ 2.0 | Configuración tipada con `.env` |
| ezdxf | ≥ 1.4 | Generación de archivos DXF |
| matplotlib | ≥ 3.8 | Exportación DXF → PDF |
| openpyxl | ≥ 3.1 | BOM en formato Excel |
| reportlab | ≥ 4.0 | BOM en formato PDF |
| **FreeCAD 1.0** | 1.0 | Motor CAD 3D (instalación separada) |

---

## 📖 Guía de Uso

### Caso 1: Flujo básico — Generar entregables de fabricación

```bash
python -m cad_generator.main
```

1. Seleccioná la pieza en el catálogo (panel izquierdo)
2. Ingresá los parámetros — el diagrama esquemático se actualiza en tiempo real
3. Verificá que todas las validaciones estén en verde ✅
4. Hacé clic en **Crear Diseño** para registrarlo en la base de datos
5. Hacé clic en **⚙ Generar CAD** → se generan todos los entregables en `outputs/`:
   - `placa_base.FCStd` — modelo FreeCAD editable
   - `placa_base.STEP` — exportación neutral para intercambio
   - `plano.DXF` / `plano.PDF` — planos con 3 vistas y cajetín IRAM 4505
   - `bom.xlsx` / `bom.PDF` — lista de materiales con peso calculado
6. Desde el panel de resultado: abrí directamente cada entregable o exportá el **paquete ZIP** completo

### Caso 2: Exportar paquete ZIP para taller

Desde el panel de resultado, hacé clic en **Exportar ZIP**. El paquete incluye:
- Modelo 3D (`.FCStd` + `.STEP`)
- Planos (`.DXF` + `.PDF`)
- BOM (`.xlsx` + `.PDF`)
- README de la revisión

### Caso 3: Gestión de revisiones ECO

1. Abrí el **Historial** desde el panel de resultado
2. Los estados disponibles son: `Borrador` → `Emitido` → `Obsoleto`
3. Cada cambio de estado queda registrado con fecha, autor y comentario

### Caso 4: Configuración de la aplicación

Menú **Archivo → ⚙ Configuración…** (o `Ctrl+,`) permite ajustar:
- Nombre de empresa (aparece en todos los rótulos y BOM)
- Autor por defecto
- Ruta de FreeCAD y carpeta de salida

Los cambios se guardan en `.env` y se aplican al reiniciar la aplicación.

---

## 🧩 Arquitectura del Software

### Estructura de Directorios

```
py-param-cad/
├── cad_generator/
│   ├── main.py                      # Punto de entrada + inicialización de logging
│   ├── config/
│   │   ├── settings.py              # Configuración tipada (pydantic-settings)
│   │   ├── piece_catalog.json       # Definición de piezas, parámetros y reglas
│   │   └── catalog_loader.py        # Acceso tipado al catálogo (singleton)
│   ├── data/
│   │   ├── models.py                # ORM: PieceType, Design, Revision, BOMItem
│   │   ├── database.py              # Engine SQLite + get_session()
│   │   └── repositories.py          # Patrón repositorio: CRUD + lógica de negocio
│   ├── core/
│   │   ├── validation_engine.py     # Motor de validación (11 reglas AISC/IRAM)
│   │   ├── piece_controller.py      # Fachada: orquesta el pipeline completo
│   │   ├── bom_generator.py         # BOM (Excel + PDF, cálculo de peso)
│   │   ├── revision_manager.py      # Gestión de revisiones ECO
│   │   └── logging_setup.py         # Logging rotativo a archivo
│   ├── cad/
│   │   ├── base_engine.py           # Interfaz ICADEngine (ABC)
│   │   ├── freecad_engine.py        # Adaptador FreeCAD (patrón subprocess)
│   │   └── scripts/
│   │       └── freecad_generate.py  # Script standalone Python 3.11
│   ├── drawing/
│   │   └── dxf_generator.py         # Planos 2D: 3 vistas, tabla, cajetín IRAM 4505
│   ├── gui/
│   │   ├── main_window.py           # Ventana principal (QSplitter + QStackedWidget)
│   │   ├── catalog_widget.py        # Árbol de catálogo de piezas
│   │   ├── parameter_form.py        # Formulario dinámico con validación
│   │   ├── schematic_viewer.py      # Diagrama esquemático (QPainter)
│   │   ├── new_design_dialog.py     # Diálogo de nuevo diseño
│   │   ├── revision_panel.py        # Panel de revisiones ECO
│   │   └── settings_dialog.py       # Configuración de la aplicación
│   └── tests/                       # 151 tests automatizados
├── requirements.txt
└── requirements-dev.txt
```

### Flujo de Ejecución

```
Usuario (GUI PyQt6)
         │ parámetros + acción
         ▼
PieceController (fachada)
         │
         ├──→ ValidationEngine
         │         11 reglas AISC/IRAM
         │         → Feedback en tiempo real (verde / rojo)
         │
         ├──→ ICADEngine
         │         ├── FreeCADEngine  ← subprocess Python 3.11
         │         │         → placa_base.FCStd + .STEP
         │         └── SolidWorksEngine (Fase 2 — stub)
         │
         ├──→ DXFDrawingGenerator (ezdxf)
         │         → plano.DXF + plano.PDF
         │
         ├──→ BOMGenerator (openpyxl + reportlab)
         │         → bom.xlsx + bom.PDF
         │
         └──→ RevisionManager (SQLAlchemy / SQLite)
                   → Historial de revisiones ECO
```

**Decisiones de arquitectura clave:**

- **FreeCAD como subproceso**: evita el conflicto entre Python 3.12 del proyecto y Python 3.11 de FreeCAD. La comunicación se realiza mediante un archivo JSON de parámetros (`FREECAD_PARAMS`).
- **Patrón Adapter para CAD**: `ICADEngine` (ABC) desacopla la GUI del motor específico; agregar SolidWorks en Fase 2 no requiere modificar la capa de aplicación.
- **Catálogo como datos JSON**: agregar una nueva pieza implica solo un nuevo JSON, sin modificar código.
- **Validación antes de generar**: ningún modelo inválido se escribe en disco sin aviso al usuario.

---

## 🧪 Testing

### Suite de Tests Automatizados

```bash
# Ejecutar todos los tests
python -m pytest cad_generator/tests/ -v

# Por módulo
pytest cad_generator/tests/test_validation_engine.py -v   # 11 reglas AISC/IRAM
pytest cad_generator/tests/test_bom_generator.py -v       # cálculo de peso + Excel/PDF
pytest cad_generator/tests/test_dxf_generator.py -v       # planos 2D, 3 vistas
pytest cad_generator/tests/test_piece_controller.py -v    # pipeline completo (CAD mockeado)
pytest cad_generator/tests/test_semana12.py -v            # ECO status, ZIP, configuración
pytest cad_generator/tests/test_semana13.py -v            # 3ra vista, tabla de agujeros, logging
```

### Casos de Validación

| Módulo de tests | Cobertura |
|----------------|-----------|
| `test_models.py` | Serialización JSON, relaciones ORM, propiedades calculadas |
| `test_repositories.py` | CRUD completo, lógica de revisiones, estados ECO |
| `test_validation_engine.py` | 11 reglas de manufacturabilidad (AISC/IRAM) |
| `test_piece_controller.py` | Pipeline completo con motor CAD mockeado |
| `test_bom_generator.py` | Cálculo de peso, generación Excel/PDF, resolución de material |
| `test_dxf_generator.py` | Selección de hoja/escala, posiciones de agujeros, generación DXF |
| `test_semana12.py` | ECO status, lógica ZIP, guardado de configuración |
| `test_semana13.py` | 3 vistas DXF, tabla de agujeros, notas, logging, historial |

---

## 📚 API Principal

### `PieceController` — fachada principal

```python
from cad_generator.core.piece_controller import PieceController

controller = PieceController(session=db_session)

resultado = controller.generate(
    design_id=1,        # ID del diseño en base de datos
    dry_run=False       # True = validar sin generar archivos
) -> GenerationResult
```

### `ValidationEngine`

```python
from cad_generator.core.validation_engine import ValidationEngine

engine = ValidationEngine(catalog_loader=catalog)

errores = engine.validate(
    piece_type="placa_base",
    params={"largo": 300, "ancho": 200, "espesor": 20, ...}
)
# → lista de ValidationError (vacía si todo OK)
```

**Propiedades de `GenerationResult`:**

| Propiedad | Tipo | Descripción |
|-----------|------|-------------|
| `fcstd_path` | `Path` | Ruta al modelo FreeCAD generado |
| `step_path` | `Path` | Ruta al archivo STEP |
| `dxf_path` | `Path` | Ruta al plano DXF |
| `pdf_path` | `Path` | Ruta al plano PDF |
| `bom_xlsx_path` | `Path` | Ruta a la BOM Excel |
| `bom_pdf_path` | `Path` | Ruta a la BOM PDF |
| `zip_path` | `Path` | Ruta al paquete ZIP |
| `success` | `bool` | True si todos los entregables se generaron |

---

## 📝 Changelog

### v1.0.0 (11 de Marzo de 2026)

**Implementado:**
- ✅ Data layer: SQLite + ORM (SQLAlchemy) + repositorios con patrón Repository
- ✅ GUI: catálogo de piezas + formulario paramétrico dinámico (PyQt6)
- ✅ SchematicViewer interactivo con actualización en tiempo real (QPainter)
- ✅ Motor CAD FreeCAD → `.FCStd` + `.STEP` (patrón subprocess Python 3.11)
- ✅ Motor de validación: 11 reglas de manufacturabilidad (AISC/IRAM)
- ✅ Planos 2D DXF + PDF con 3 vistas y cajetín IRAM 4505
- ✅ BOM automática Excel + PDF con cálculo de peso por material
- ✅ Historial de revisiones ECO + configuración + exportación ZIP
- ✅ Vista de perfil, tabla de coordenadas de agujeros, notas técnicas, logging rotativo
- ✅ 151 tests automatizados
- [ ] Empaquetado `.exe` con PyInstaller (Fase 14 — pendiente)

---

## 📄 Licencia

Uso personal / proyecto privado. No se permite distribución sin autorización del autor.

---

## 👨‍💻 Autor

**Federico Ariel Casado** — Ingeniería

- 💻 Stack técnico: Python 3.12, PyQt6, SQLAlchemy, FreeCAD, ezdxf, openpyxl, reportlab
- 📚 Dominio: CAD paramétrico, planos técnicos, gestión de ingeniería (ECO/BOM)
- 📧 federicoarielcasado@gmail.com

---

*Última actualización: 11 de Marzo de 2026*
