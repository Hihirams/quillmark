<p align="center">
  <img src="docs/assets/quillmark-banner.svg" alt="Quillmark: laboratorio de escritura" width="100%">
</p>

[English](README.md) · **Español**

# Quillmark

Un espacio para revisar borradores y leer las señales, no para acusar a quien
escribió un texto. Pega un borrador, carga un PDF o un documento de Word, o
analiza una página web. Puedes consultar el resultado por motor y usar el
asesor de estilo para revisar cambios sin reemplazar tu texto en automático.

Es una edición mantenida por Hiram G. El análisis se ejecuta en tu propio
servidor y no envía el texto a APIs externas de IA. Los resultados de un
detector no prueban autoría, especialmente en textos cortos.

## Empezar en Windows

Desde la carpeta del proyecto:

```powershell
py -3.12 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\start-local.ps1 -Profile lite -Open
```

Sin `-Open`, entra en <http://localhost:8000>. La primera ejecución puede
descargar varios GB de modelos. Consulta [el tamaño de los
modelos](docs/MODELS.md) y las [formas de instalación](README.md#quick-start).

## Investigación y créditos

La base del detector y la evaluación publicada son de SlopTotal. Consulta
[créditos y procedencia](CREDITS.md), [resultados y limitaciones
originales](tests/eval/slopbench/FINDINGS.md), y la [licencia MIT](LICENSE).
