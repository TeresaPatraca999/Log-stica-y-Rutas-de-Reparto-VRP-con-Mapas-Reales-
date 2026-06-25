# VRP - Logistica y Rutas de Reparto

Aplicacion de escritorio para resolver un problema de rutas de vehiculos (VRP) usando un algoritmo genetico. El sistema organiza entregas desde un deposito hacia varios paquetes/clientes, respetando la capacidad maxima de los camiones y buscando reducir la distancia total recorrida.

## Objetivo

Encontrar rutas de reparto para `M` vehiculos con capacidad maxima `Q`, minimizando la distancia total:

```text
min sum Distancia(Ruta_k)
```

Si una ruta excede la capacidad del camion o se requieren mas camiones de los disponibles, la solucion recibe una penalizacion fuerte.

## Funcionalidades

- App de escritorio con interfaz grafica.
- Alta de vehiculos: cantidad de camiones `M` y capacidad maxima `Q`.
- Carga de paquetes desde CSV.
- Tabla editable para agregar, actualizar o eliminar paquetes.
- Seleccion de varios destinos desde un mapa interactivo.
- Deposito configurable por coordenadas.
- Parametros del algoritmo: poblacion, generaciones y tasa de mutacion.
- Funcion objetivo visible y explicada dentro de la app.
- Cruza OX para permutaciones.
- Mutacion por intercambio de paquetes.
- Mapa interactivo generado con Folium.
- Rutas por camion con colores diferentes.
- Marcador claro del deposito como origen y destino final.
- Tabla resumen con paquetes asignados, carga, distancia y ruta.
- Grafica de convergencia del algoritmo.
- Grafica de convergencia en una ventana aparte y desplazable.
- Distancia individual por camion dentro de la grafica detallada.

## Modos de ruta

### Local con calles OSMnx

Usa OSMnx y NetworkX para calcular rutas sobre calles reales. Este modo es el recomendado para entregas dentro de una misma ciudad o region cercana. El ejemplo principal usa puntos del Istmo de Tehuantepec, Oaxaca.

### Nacional aproximado

Permite probar entregas a estados lejanos como Jalisco, Baja California o Quintana Roo. En este modo la distancia es aproximada y el mapa muestra conexiones directas entre puntos, porque descargar toda la red carretera nacional seria demasiado pesado para esta app.

## Archivos principales

- `desktop_app.py`: app de escritorio principal.
- `ga_vrp.py`: algoritmo genetico, penalizacion, cruza OX y mutacion.
- `map_utils.py`: calculo de distancias, rutas y utilidades de mapa.
- `data/clientes.csv`: ejemplo local de entregas en el Istmo de Tehuantepec, Oaxaca.
- `data/clientes_nacional.csv`: ejemplo nacional aproximado.
- `run_app.bat`: ejecuta la app de escritorio.
- `requirements.txt`: librerias necesarias.

## Instalacion

Desde PowerShell, entra a la carpeta del proyecto:

```powershell
cd C:\Users\teres\vrp_app
```

Crea y activa el entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instala las librerias:

```powershell
pip install -r requirements.txt
```

Si PowerShell bloquea la activacion del entorno, ejecuta primero:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

## Como ejecutar

La forma mas sencilla:

```powershell
cd C:\Users\teres\vrp_app
.\run_app.bat
```

Tambien se puede ejecutar manualmente:

```powershell
.\.venv\Scripts\Activate.ps1
python desktop_app.py
```

## Formato del CSV

El archivo debe tener estas columnas:

```csv
destino,lat,lon,demanda
El Espinal,16.485600,-95.040300,5
Ciudad Ixtepec,16.562000,-95.103000,6
```

Campos:

- `destino`: nombre del lugar o cliente.
- `lat`: latitud del paquete.
- `lon`: longitud del paquete.
- `demanda`: peso o carga requerida por el paquete.

## Uso de la app

1. Define la cantidad de vehiculos disponibles.
2. Define la capacidad maxima de cada camion.
3. Configura el deposito con latitud y longitud.
4. Selecciona el tipo de ruta.
5. Carga un CSV o edita la tabla manualmente.
6. Para elegir destinos desde el mapa, presiona `Elegir en mapa` y haz clic una o varias veces.
7. Ajusta poblacion, generaciones y tasa de mutacion.
8. Presiona `Ejecutar Optimizacion`.
9. Revisa la tabla resumen y el mapa interactivo.
10. Presiona `Abrir grafica detallada` para ver la convergencia por aparte.

## Funcion objetivo

La app optimiza:

```text
Z = suma de distancias de todas las rutas + penalizaciones
```

Las penalizaciones se aplican cuando:

- Un camion excede la capacidad maxima `Q`.
- La solucion requiere mas vehiculos que los disponibles `M`.

La grafica de convergencia muestra como mejora el mejor valor de `Z` durante las generaciones del algoritmo genetico.

## Notas importantes

- Para rutas locales reales se necesita internet, porque OSMnx descarga datos de OpenStreetMap.
- Ningun paquete debe tener exactamente la misma ubicacion que el deposito.
- En modo local, los destinos deben estar dentro de la misma ciudad o region cercana.
- En modo nacional, las rutas son una aproximacion visual y de distancia, no caminos carretera por carretera.
