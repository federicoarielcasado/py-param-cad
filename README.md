# py-param-cad

Generador paramétrico de escritorio para modelos CAD 3D y planos técnicos 2D de piezas de ingeniería estructural. Desarrollado en Python/PyQt6 para uso profesional en Windows.

---

## Descripción

Aplicación de escritorio que automatiza la generación de modelos CAD 3D editables y planos 2D de fabricación a partir de parámetros técnicos ingresados por el usuario. Simula el flujo real de trabajo multidisciplina (mecánica, estructura).

### Pieza implementada — MVP: Placa Base Estructural

- **Geometría paramétrica**: largo, ancho, espesor, 4 patrones de perforaciones, ranuras de ajuste
- **Materiales**: ASTM A36, ASTM A572 Gr.50, Inox 304, Inox 316, Aluminio 6061-T6
- **Validaciones de manufacturabilidad** en tiempo real: 11 reglas (criterios AISC / IRAM)
- **Modelo 3D**: `.FCStd` (FreeCAD nativo) + `.STEP` (intercambio universal)
- **Planos 2D** (DXF + PDF): 3 vistas (planta, alzado, perfil), tabla de coordenadas de agujeros, notas técnicas, cajetín IRAM 4505
- **BOM automática**: Excel (`.xlsx`) + PDF con peso calculado por material
- **Historial de revisiones**: trazabilidad completa con flujo ECO (Borrador → Emitido → Obsoleto)
- **Exportación de paquete**: ZIP con todos los entregables de fabricación

---

## Requisitos

| Dependencia | Versión | Descripción |
|-------------|---------|-------------|
| Python | 3.12+ | Intérprete principal |
| PyQt6 | ≥ 6.6 | Interfaz gráfica |
| SQLAlchemy | ≥ 2.0 | ORM / SQLite |
| pydantic-settings | ≥ 2.0 | Configuración tipada con `.env` |
| ezdxf | ≥ 1.4 | Generación de archivos DXF |
| matplotlib | ≥ 3.8 | Exportación DXF → PDF |
| openpyxl | ≥ 3.1 | BOM en formato Excel |
| reportlab | ≥ 4.0 | BOM en formato PDF |
| **FreeCAD 1.0** | 1.0 | Motor CAD 3D — instalación separada |

> **FreeCAD** debe estar instalado en `C:\Program Files\FreeCAD 1.0\`.
> Descarga: <https://www.freecad.org/downloads.php>

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

**Flujo de trabajo básico:**

1. Seleccioná la pieza en el catálogo (panel izquierdo)
2. Ingresá los parámetros — el diagrama esquemático se actualiza en tiempo real
3. Verificá que las validaciones estén en verde ✅
4. Hacé clic en **Crear Diseño** para registrarlo en la base de datos
5. Hacé clic en **⚙ Generar CAD** → se generan todos los entregables en `outputs/`
6. Desde el panel de resultado:
   - Abrí directamente el modelo 3D, plano DXF/PDF o BOM
   - Exportá el **paquete ZIP** completo para enviar al taller
   - Consultá el **Historial** de revisiones del diseño

**Configuración de la aplicación:**

Menú **Archivo → ⚙ Configuración…** (o `Ctrl+,`) permite ajustar:
- Nombre de empresa (aparece en todos los rótulos y BOM)
- Autor por defecto
- Ruta de FreeCAD y carpeta de salida

Los cambios se guardan en `.env` y se aplican al reiniciar la aplicación.

---

## Estructura del proyecto

```
py-param-cad/
├── cad_generator/
│   ├── main.py                      # Punto de entrada + inicialización de logging
│   ├── config/
│   │   ├── settings.py              # Configuración tipada (pydantic-settings, prefijo CAD_)
│   │   ├── piece_catalog.json       # Definición de piezas, parámetros y reglas de validación
│   │   └── catalog_loader.py        # Acceso tipado al catálogo (singleton)
│   ├── data/
│   │   ├── models.py                # ORM: PieceType, Design, Revision, BOMItem
│   │   ├── database.py              # Engine SQLite + get_session() (context manager)
│   │   └── repositories.py          # Patrón repositorio: CRUD + lógica de negocio de datos
│   ├── core/
│   │   ├── validation_engine.py     # Motor de validación (11 reglas, eval() con namespace restringido)
│   │   ├── piece_controller.py      # Fachada: orquesta el pipeline completo de generación
│   │   ├── bom_generator.py         # Generador de BOM (Excel + PDF, cálculo de peso)
│   │   ├── revision_manager.py      # Utilidades de gestión de revisiones
│   │   └── logging_setup.py         # Configuración de logging rotativo a archivo
│   ├── cad/
│   │   ├── base_engine.py           # Interfaz ICADEngine (ABC)
│   │   ├── freecad_engine.py        # Adaptador FreeCAD (patrón subprocess)
│   │   ├── solidworks_engine.py     # Stub SolidWorks (Fase 2)
│   │   └── scripts/
│   │       └── freecad_generate.py  # Script standalone Python 3.11 (corre dentro de FreeCAD)
│   ├── drawing/
│   │   └── dxf_generator.py         # Planos 2D: 3 vistas, tabla de agujeros, notas, cajetín IRAM 4505
│   ├── gui/
│   │   ├── main_window.py           # Ventana principal (QSplitter + QStackedWidget)
│   │   ├── catalog_widget.py        # Árbol de catálogo de piezas
│   │   ├── parameter_form.py        # Formulario paramétrico dinámico con validación en tiempo real
│   │   ├── schematic_viewer.py      # Diagrama esquemático interactivo (QPainter)
│   │   ├── new_design_dialog.py     # Diálogo de creación de nuevo diseño
│   │   ├── revision_panel.py        # Panel de historial de revisiones con control ECO
│   │   └── settings_dialog.py       # Diálogo de configuración de la aplicación
│   ├── assets/
│   │   └── schematics/              # Imágenes esquemáticas estáticas por parámetro (PNG)
│   └── tests/
│       ├── conftest.py
│       ├── test_models.py
│       ├── test_repositories.py
│       ├── test_validation_engine.py
│       ├── test_piece_controller.py
│       ├── test_bom_generator.py
│       ├── test_dxf_generator.py
│       ├── test_semana12.py
│       └── test_semana13.py
├── PROXIMOS_PASOS.md                # Planificación y estado de desarrollo
├── requirements.txt
└── requirements-dev.txt
```

---

## Tests

```bash
python -m pytest cad_generator/tests/ -v
```

```
151 passed in ~12s
```

| Módulo de tests | Cobertura |
|----------------|-----------|
| `test_models.py` | Serialización JSON, relaciones ORM, propiedades calculadas |
| `test_repositories.py` | CRUD completo, lógica de revisiones, ECO status |
| `test_validation_engine.py` | 11 reglas de manufacturabilidad (AISC/IRAM) |
| `test_piece_controller.py` | Pipeline completo con motor CAD mockeado |
| `test_bom_generator.py` | Cálculo de peso, generación Excel/PDF, resolución de material |
| `test_dxf_generator.py` | Selección de hoja/escala, posiciones de agujeros, generación DXF |
| `test_semana12.py` | ECO status, lógica ZIP, guardado de configuración |
| `test_semana13.py` | 3 vistas DXF, tabla de agujeros, notas, logging, historial de revisiones |

---

## Arquitectura

```
┌─────────────────────────────────────────────────────┐
│                 GUI (PyQt6)                         │
│  MainWindow │ ParameterForm │ SchematicViewer │ ... │
└─────────────────────┬───────────────────────────────┘
                      │ señales/slots
┌─────────────────────▼───────────────────────────────┐
│              Capa de Aplicación (Core)              │
│  PieceController │ ValidationEngine │ BOMGenerator  │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│            Adaptadores CAD / Drawing                │
│  ICADEngine                                         │
│  ├── FreeCADEngine  ← subprocess Python 3.11        │
│  └── SolidWorksEngine (Fase 2)                      │
│  DXFDrawingGenerator (ezdxf)                        │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│           Capa de Datos (SQLAlchemy / SQLite)       │
│  DesignRepository │ RevisionRepository │ BOMRepo    │
└─────────────────────────────────────────────────────┘
```

**Decisiones de arquitectura clave:**

- **FreeCAD como subproceso**: evita el conflicto entre Python 3.12 del proyecto y Python 3.11 de FreeCAD. La comunicación se realiza mediante un archivo JSON de parámetros (variable de entorno `FREECAD_PARAMS`).
- **Patrón Adapter para CAD**: `ICADEngine` (ABC) desacopla la GUI del motor específico; agregar SolidWorks en Fase 2 no requiere modificar la capa de aplicación.
- **Catálogo como datos JSON**: agregar una nueva pieza implica solo un nuevo JSON, sin modificar código.
- **Validación antes de generar**: ningún modelo inválido se escribe en disco sin aviso al usuario.

---

## Estado de desarrollo

| Semana | Módulo | Estado |
|--------|--------|--------|
| 1-2 | Data layer: SQLite + ORM + repositorios | ✅ |
| 3-4 | GUI: catálogo de piezas + formulario paramétrico | ✅ |
| 5-6 | SchematicViewer dinámico (QPainter) | ✅ |
| 7-8 | Motor CAD FreeCAD → `.FCStd` + `.STEP` | ✅ |
| 9 | Validaciones de manufacturabilidad (11 reglas) + panel de resultado | ✅ |
| 10 | Planos 2D DXF + PDF con cajetín IRAM 4505 | ✅ |
| 11 | BOM automática Excel + PDF con cálculo de peso | ✅ |
| 12 | Historial de revisiones + ECO + configuración + exportación ZIP | ✅ |
| 13 | 3ra vista, tabla de agujeros, notas técnicas, logging | ✅ |
| 14 | Empaquetado `.exe` (PyInstaller) | ⏳ |

Ver [PROXIMOS_PASOS.md](PROXIMOS_PASOS.md) para el detalle de la Semana 14.

---

## Licencia

Uso personal / proyecto privado. No se permite distribución sin autorización del autor.
