# Estructura para el proyecto de ssdd-lab

## Estructura.
Este repositorio es el proyecto en Python de la asignatura SSDD y contiene los siguientes
archivos y directorios:

- `iceflix_services` es el paquete principal en Python. Se ha decidio llamarlo
  de esta manera debido a que tendrá los archivos relacionados con los servicios
  que realizarán las funcionalidades principales del sistema.
- `iceflix_services/__init__.py` es un directorio vacío que Python necesita
  para reconocer el directorio de `iceflix_services` como paquete/módulo. En
  nuestro caso tenemos las importaciones procedentes del paquete `topic_management`.
- `iceflix_services/topic_management` es un directorio que hemos creado con un archivo
  topics que contiene los métodos de get_topic y get_topic_manager para realizar
  distintas operaciones con IceStorm. También contiene un `__init__.py`.
- `packagename/cli.py` contains several functions that can handle the
  basic console entry points defined in `python.cfg`. The name of the
  submodule and the functions can be modified if you need.
- `pyproject.toml` define el 'build system' usado en el Proyecto.
- `run_client` script que puede ser ejecutado directamente desde el root del repositorio. 
  Tiene que ser capaz de ejecutar un cliente.
- `run_iceflix` shcript que puede ser ejecutado directamente desde el root del repositorio. 
  Tiene que ser capaz de ejecutar todos los servicios de fondo para superar el test total del sistema.
- `setup.cfg` es el archivo de distribución de configuración de Python para
  Setuptools.

## Ejecución de la Práctica.
  - **1.-** Ejecutar __run_iceflix__. En el caso de querer utilizar otro ADMIN TOKEN que no sea el de por defecto, se debe modificar la línea 8 del __run_iceflix__ concretamente después --Ice.Config=client.config. **IMPORTANTE** EL TOKEN deberá llevar 'comillas'. 
  - **2.-** Ejecutar __run_client__. 
  - **3.-** Introcir copiando el proxy que imprime el servicio main al ejecutar **__run_iceflix__**.
  - **4.-** Dentro del sistema tenemos distintas opciones:
    - **4.1.-** Menú de **autenticación** (Pulsar 1).
      - **4.1.1.-** Crear un nuevo TOKEN de autorización (Pulsar 1).
      - **4.1.2.-** Comprobar TOKEN (Pulsar 2).
      - **4.1.3.-** Buscar usuario por TOKEN (Pulsar 3).
      - **4.1.1.-** Añadir usuario (Pulsar 4).
      - **4.1.1.-** Eliminar usuario (Pulsar 5).
      - **4.1.1.-** Salir del menú autenticación (Pulsar 6).
    - **4.2.-** Menú de **catálogo** (Pulsar 2).
      - **4.2.1.-** Buscar en el catálogo por TÍTULO (Pulsar 1).
      - **4.2.2.-** Buscar en el catálogo por NOMBRE (Pulsar 2).
      - **4.2.3.-** Buscar en el catálogo por TAG (Pulsar 3).
      - **4.2.4.-** Añadir TAG (Pulsar 4).
      - **4.2.5.-** Eliminar TAG (Pulsar 5).
      - **4.2.6.-** Renombrar película (Pulsar 6).
      - **4.2.7.-** Salir del menú catálogo (Pulsar 7).
    - **4.3.-** Salir del sistema (Pulsar 3).
    
 ## Ejecución de un medio.
  - Para reproducir un medio tendríamos que seleccionar la opción de catálogo y pulsar en el **4.2.1**, haciendo esto nos aparecerá un menú especiífico para
  el **streaming** donde podremos **subir** y **elimanar** medios. 
  - En la opción de **subir** introducimos el nombre de un medio que se encuentre en la carpeta **directorio_videos** y   el sistema te la incluirá en la carpeta **resources**. **IMPORTANTE** cuanod se introduzca el nombre del archivo deberá ser incluyendo la extensión.
  - En la opción de **eliminar** media te lo borrará de la carpeta **resources** introduciendo el correspondiente ID.
