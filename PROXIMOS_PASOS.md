# Próximos pasos — py-param-cad

> Última actualización: 2026-03-05
> Estado actual: **Semana 13 completa** — 151/151 tests ✅

---

## Estado de avance

| Semana | Módulo | Estado | Tests |
|--------|--------|--------|-------|
| 1-2 | Data layer: SQLite + ORM + repositorios | ✅ Completo | 22 |
| 3-4 | GUI: catálogo + formulario paramétrico | ✅ Completo | 12 |
| 5-6 | SchematicViewer dinámico (QPainter) | ✅ Completo | — |
| 7-8 | Motor CAD FreeCAD → `.FCStd` + `.STEP` | ✅ Completo | 23 |
| 9 | Validaciones de manufacturabilidad + `_ResultPanel` | ✅ Completo | 17 |
| 10 | Planos 2D DXF + PDF (cajetín IRAM 4505) | ✅ Completo | 27 |
| 11 | BOM automática Excel + PDF | ✅ Completo | 22 |
| 12 | Historial revisiones + ECO + configuración + ZIP | ✅ Completo | 21 |
| 13 | 3ra vista, tabla de agujeros, notas técnicas, logging | ✅ Completo | 17 |
| **14** | **Empaquetado `.exe` (PyInstaller)** | ⏳ Próximo | — |

---

## Semana 14 — Empaquetado y distribución

### Objetivo
Generar un ejecutable standalone `.exe` para Windows que no requiera instalación de Python ni dependencias.

### Tareas

#### 14.1 — Preparar spec de PyInstaller

```bash
pip install pyinstaller
```

Crear `py_param_cad.spec` con inclusión de datos necesarios:

```python
# py_param_cad.spec
a = Analysis(
    ['cad_generator/main.py'],
    datas=[
        ('cad_generator/config/piece_catalog.json',  'cad_generator/config'),
        ('cad_generator/cad/scripts/freecad_generate.py', 'cad_generator/cad/scripts'),
        ('cad_generator/assets',                     'cad_generator/assets'),
    ],
    hiddenimports=['ezdxf', 'openpyxl', 'reportlab'],
    ...
)
```

Consideraciones:
- FreeCAD **no** se incluye en el `.exe` — se detecta en runtime por `settings.freecad_bin`
- La base de datos SQLite se crea en `outputs/` relativo al ejecutable
- `freecad_generate.py` debe incluirse como dato (lo ejecuta FreeCAD, no PyInstaller)

#### 14.2 — Ajustes de rutas para modo empaquetado

Detectar si la app corre como bundle de PyInstaller:

```python
import sys

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent
```

Actualizar `settings.py` para usar `get_base_dir()` en lugar de `Path(__file__).parent.parent.parent`.

#### 14.3 — Verificación de dependencias en runtime

Mostrar mensaje claro si FreeCAD no está instalado o la ruta es incorrecta (al inicio de la app, antes de intentar generar).

#### 14.4 — Build y prueba del ejecutable

```bash
pyinstaller py_param_cad.spec --clean
# Resultado en dist/py_param_cad/py_param_cad.exe
```

Verificar:
- [ ] Arranca correctamente en máquina limpia (sin Python instalado)
- [ ] Genera modelo 3D con FreeCAD disponible
- [ ] Genera plano DXF + PDF
- [ ] Genera BOM Excel + PDF
- [ ] El log se escribe en `outputs/cad_generator.log`

#### 14.5 — Instalador opcional (Inno Setup)

Para distribución más profesional, generar un instalador `.exe` con:
- Acceso directo en escritorio y menú inicio
- Opción de desinstalar
- Detecta FreeCAD y alerta si no está instalado

---

## Fase 2 — Expansión del catálogo de piezas

Una vez estabilizado el MVP (Semana 14), incorporar nuevas piezas al catálogo:

| Pieza | Disciplina | Complejidad |
|-------|------------|-------------|
| Viga HEB / IPE | Estructura | Media |
| Angular L | Estructura | Baja |
| Perno de anclaje | Mecánica | Media |
| Placa de apoyo | Estructura | Baja |
| Soporte de equipos | Mecánica | Alta |

Cada pieza requiere:
- Entrada en `piece_catalog.json` (parámetros + reglas de validación + BOM template)
- Script FreeCAD de generación en `cad/scripts/`
- Generador DXF en `drawing/dxf_generator.py`
- Tests unitarios

Estimación: < 1 día de desarrollo por pieza, sin modificar el núcleo.

---

## Fase 2 — SolidWorks/Inventor (Adaptador COM)

Implementar `SolidWorksEngine` usando `win32com`:

```python
class SolidWorksEngine(ICADEngine):
    def generate(self, params, output_dir) -> GenerationResult:
        import win32com.client
        sw = win32com.client.Dispatch("SldWorks.Application")
        # ...
```

Requiere licencia de SolidWorks activa. El patrón Adapter ya está preparado en `cad/base_engine.py`.

---

## Fase 2 — Feedback de fabricación

Agregar campo de notas por revisión para registrar observaciones del taller (RF-09):
- Campo `fabrication_notes` en el modelo `Revision`
- Editor de texto en `RevisionPanel`
- Exportado en el paquete ZIP

---

## Deuda técnica conocida

| Item | Impacto | Prioridad |
|------|---------|-----------|
| `solidworks_engine.py` es stub | Bajo (Fase 2 opcional) | Baja |
| Imágenes esquemáticas PNG no implementadas | Medio (SchematicViewer usa QPainter como fallback) | Media |
| 3ra vista DXF usa texto en lugar de cota formal para ANCHO del perfil | Bajo | Baja |
| PyInstaller no configurado | Alto para distribución | Alta (Semana 14) |
| Tests de integración end-to-end (pipeline real con FreeCAD) | Medio | Media |

---

## Notas técnicas de referencia

### Protocolo subprocess FreeCAD (crítico)

```python
# freecadcmd.exe NO acepta args posicionales — los trata como documentos a abrir.
# Pasar el path del JSON de parámetros por variable de entorno:
env["FREECAD_PARAMS"] = str(params_file)
subprocess.run([freecadcmd_exe, freecad_generate_py], env=env, ...)

# freecadcmd.exe NO setea __name__ == "__main__"
# Al final del script, llamar main() incondicionalmente:
main()
```

### Valores de material en el catálogo

Los valores de la opción `material` en `piece_catalog.json` son:
`"ASTM_A36"`, `"ASTM_A572_G50"`, `"SS304"`, `"SS316"`, `"AL6061T6"`

El dict `_DENSITY` en `bom_generator.py` usa exactamente estas claves.

### Estructura de outputs generados

```
outputs/
└── base_plate/
    └── {nombre_diseño}/
        └── {codigo_revision}/       ← A, B, C ...
            ├── base_plate_A.FCStd
            ├── base_plate_A.step
            ├── base_plate_A.dxf
            ├── base_plate_A.pdf
            ├── BOM_A.xlsx
            ├── BOM_A.pdf
            └── result.json
```

### Patrón de tests para PieceController

Ver `cad_generator/tests/test_piece_controller.py` — fixture `patched_controller`
que inyecta DB en memoria + settings mockeados + motor CAD como `MagicMock`.

### Reglas de validación activas (Placa Base)

| ID | Descripción | Severidad |
|----|-------------|-----------|
| VR-BP-01 | Espesor mínimo 4 mm | error |
| VR-BP-02 | Largo ≥ 50 mm | error |
| VR-BP-03 | Ancho ≥ 50 mm | error |
| VR-BP-04 | Relación largo/ancho ≤ 10 | warning |
| VR-BP-05 | Margen ≥ 1.5× diámetro (borde a centro) | error |
| VR-BP-06 | Diámetro perforación ≥ 6 mm | error |
| VR-BP-07 | Diámetro perforación ≤ min(largo, ancho) / 3 | error |
| VR-BP-08 | Espesor ≥ diámetro / 3 (relación taladro) | warning |
| VR-BP-09 | Separación entre agujeros ≥ 3× diámetro (AISC) | error |
| VR-BP-10 | Relación largo_ranura / ancho_ranura ≤ 8 | warning |
| VR-BP-11 | Ancho suficiente para patrón rectangular_6 | error |
