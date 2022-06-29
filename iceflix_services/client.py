#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Código perteneciente al Cliente de la aplicación.
"""

import hashlib
import os
import sys
import threading
import time
from getpass import getpass
import Ice

from topic_management.topics import get_topic, get_topic_manager

try:
    import IceFlix
except ImportError:
    Ice.loadSlice("iceflix_full.ice")
    import IceFlix

EXIT_OK = 0
EXIT_ERROR = 1

# pylint: disable=C0103
# pylint: disable=C0116
# pylint: disable=W0613
# pylint: disable=R1723
# pylint: disable=W0212
# pylint: disable=C0301
# pylint: disable=R1710
# pylint: disable=R0913
# pylint: disable=C0115
# pylint: disable=W0603
# pylint: disable=R0201
# pylint: disable=bare-except


class bcolors:
    """Clase para cambiar de color los prints."""

    OK = "\033[92m"  # GREEN
    WARNING = "\033[93m"  # YELLOW
    FAIL = "\033[91m"  # RED
    RESET = "\033[0m"  # RESET COLOR
    MENU = "\033[1;36m"  # MENUS COLOR


class MediaUploaderI(IceFlix.MediaUploader):
    """Maneja la administración acerca de subir media."""

    def __init__(self, filename):
        """Inicializador del MediaUploader."""
        self._filename_ = filename
        self._fd_ = open("directorio_videos/" + filename, "rb")

    def receive(self, size, current=None) -> bytes:
        """Lee un bloque de tamaño size y lo devuelve."""
        chunk = self._fd_.read(size)
        return chunk

    def close(self, current=None):
        """Cierra el envío del fichero y elemina el objeto del adaptador."""
        self._fd_.close()
        current.adapter.remove(current.id)


class Client(Ice.Application):
    """Clase del Cliente."""

    def __init__(self):
        """Inicializador del Cliente."""
        self.publicador_revocation = None
        self.admin_token = None
        self.proxy_streaming = None
        self.user_token = None
        self.user = None
        self.password_hash = None
        self.main_service = None

        threading.Thread(target=self.control_token, args=()).start()

    def suscripcion_user_revocations(self, user, password_hash):
        """Método que permite suscribirse al topic de Revocations."""
        ### Revocations
        broker = self.communicator()
        adapter_revocations = broker.createObjectAdapter("RevocationsAdapter")
        adapter_revocations.activate()
        revocation_topic = get_topic(get_topic_manager(broker), "Revocations")
        revocation_publisher = revocation_topic.getPublisher()
        revocation_publicador = IceFlix.RevocationsPrx.uncheckedCast(
            revocation_publisher
        )

        return revocation_publicador

    def establecer_rango_opciones(self, mn, mx) -> int:
        """Método que comprueba que la opción del menú es un entero válido."""
        while True:
            option = input()
            if not int(option.isdigit()) or (int(option) < mn or int(option) > mx):
                print(
                    f"{bcolors.WARNING}Rango de opciones [{str(mn)}-{str(mx)}]{bcolors.RESET}"
                )
            else:
                break
        return int(option)

    def select_option(self, choice):
        """Método que devulve un servicio en función de una opción."""
        try:
            if choice == 1:
                return self.main_service.getAuthenticator()
            elif choice == 2:
                return self.main_service.getCatalog()
            else:
                print(f"{bcolors.OK}[!] Saliendo...{bcolors.RESET}")
        except IceFlix.TemporaryUnavailable as ice_flix_error:
            print(
                f"{bcolors.FAIL}{ice_flix_error}\nServicio no disponible.{bcolors.RESET}"
            )

    def show_menu(self) -> int:
        """Método que muestra el menú principal."""
        print(
            f"""{bcolors.MENU}\n-- MENÚ PRINCIPAL --{bcolors.RESET} Selecciona que desea hacer:
    1.- Autenticarse en el sistema.
    2.- Catalogo del sistema.
    3.- Salir del sistema.\n"""
        )
        return int(self.establecer_rango_opciones(1, 3))

    def menu_authentication(self, service) -> None:
        """Método que muestra el menú autenticación."""
        while True:
            print(
                f"""{bcolors.MENU}\n-- MENÚ AUTH. --{bcolors.RESET}Selecciona que desea hacer:
        1.- Crear nuevo token de autorizacion.
        2.- Comprobar token.
        3.- Buscar usuario por TOKEN.
        4.- Añadir usuario.
        5.- Eliminar usuario.
        6.- Salir del menú autenticación.\n"""
            )

            choice = int(self.establecer_rango_opciones(1, 6))

            if choice == 1:
                try:
                    self.user = input("Introduce el usuario: ")
                    password = getpass("Introduce la contraseña: ")
                    self.password_hash = hashlib.sha256(password.encode()).hexdigest()

                    self.user_token = service.refreshAuthorization(
                        self.user, self.password_hash
                    )
                    self.publicador_revocation = self.suscripcion_user_revocations(
                        self.user, self.password_hash
                    )
                    print(f"{bcolors.OK}TOKEN generado correctamente.{bcolors.RESET}")
                except IceFlix.Unauthorized as ice_flix_error:
                    print(
                        f"{bcolors.FAIL}{ice_flix_error}\nUSUARIO no registrado. {bcolors.RESET}"
                    )

            elif choice == 2:
                if service.isAuthorized(self.user_token):
                    print(f"{bcolors.OK}El TOKEN es válido. {bcolors.RESET}")
                else:
                    print(f"{bcolors.FAIL}El TOKEN NO es válido.{bcolors.RESET}")

            elif choice == 3:
                try:
                    user = service.whois(self.user_token)
                    print(f"{bcolors.OK}USER asociado al TOKEN: {user}{bcolors.RESET}")
                except IceFlix.Unauthorized as ice_flix_error:
                    print(
                        f"{bcolors.FAIL}{ice_flix_error}\nTOKEN no válido. {bcolors.RESET}"
                    )

            elif choice == 4:
                try:
                    new_user = input("Introduce un usuario: ")
                    new_pass = getpass("Introduce la contrasena: ")
                    pass_hash = hashlib.sha256(new_pass.encode())
                    service.addUser(new_user, pass_hash.hexdigest(), self.admin_token)
                    print(f"{bcolors.OK}USER añadido correctamente. {bcolors.RESET}")
                except (
                    IceFlix.Unauthorized,
                    IceFlix.TemporaryUnavailable,
                ) as ice_flix_error:
                    print(f"{bcolors.FAIL}{ice_flix_error}\nOperación no realizada.")

            elif choice == 5:
                try:
                    user = input("Introduce un usuario: ")
                    service.removeUser(user, self.admin_token)
                    print(f"{bcolors.OK}USER borrado correctamente. {bcolors.RESET}")
                except (
                    IceFlix.Unauthorized,
                    IceFlix.TemporaryUnavailable,
                ) as ice_flix_error:
                    print(f"{bcolors.FAIL}{ice_flix_error}\nOperación no realizada.")

            elif choice == 6:
                print(f"{bcolors.OK}[!] Saliendo de Authenticator...{bcolors.RESET}")
                break

    def menu_catalog(self, service) -> None:
        """Método que muestra el menú del catálogo."""
        while True:
            print(
                f"""{bcolors.MENU}\n-- MENÚ CATÁLOGO --{bcolors.RESET} Selecciona que desea hacer:
        1.- Buscar en el catálogo por TÍTULO.
        2.- Buscar en el catálogo título por NOMBRE.
        3.- Buscar en el catálogo título por TAG.
        4.- Añadir TAG.
        5.- Eliminar TAG.
        6.- Renombrar película.
        7.- Salir del menú catálogo.\n"""
            )

            choice = int(self.establecer_rango_opciones(1, 7))

            if choice == 1:
                try:
                    media_id = input("Introduce un identificador: ")
                    media = service.getTile(media_id, self.user_token)
                    self.proxy_streaming = media.provider

                    self.menu_Streaming()
                except (
                    IceFlix.WrongMediaId,
                    IceFlix.Unauthorized,
                    IceFlix.TemporaryUnavailable,
                ) as ice_flix_error:
                    print(f"{bcolors.FAIL}{ice_flix_error}\nOperación no realizada.")

            elif choice == 2:
                exact = False
                name = input("Introduce el nombre de la pelicula: ")
                while True:
                    answer = str(input("Quieres una busqueda exacta? [y/n]: "))
                    if answer.upper() == "Y":
                        exact = True
                        break
                    elif answer.upper() == "N":
                        exact = False
                        break
                    else:
                        print(
                            f"{bcolors.WARNING}Introduce opciones válidas. {bcolors.RESET}"
                        )
                lista_peliculas = service.getTilesByName(name, exact)
                if lista_peliculas:
                    lista_final_peliculas = "".join(map(str, lista_peliculas))
                    print(f"{bcolors.OK}{lista_final_peliculas}{bcolors.RESET}")
                else:
                    print(f"{bcolors.WARNING}Película no encontrada. {bcolors.RESET}")

            elif choice == 3:
                try:
                    lista_tags = []
                    anhadir = True
                    include_all_tags = False

                    while anhadir:
                        tag = input("Introduce un tag: ")
                        lista_tags.append(tag)
                        while True:
                            answer = str(input("¿Deseas añadir otro tag?: [y/n]: "))
                            if answer.upper() == "Y":
                                anhadir = True
                                break
                            elif answer.upper() == "N":
                                anhadir = False
                                break
                            else:
                                print(
                                    f"{bcolors.WARNING}Introduce opciones válidas. {bcolors.RESET}"
                                )

                    answer = str(input("¿Deseas una búsqueda exacta por tags? [y/n]: "))
                    while True:
                        if answer.upper() == "Y":
                            include_all_tags = True
                            break
                        elif answer.upper() == "N":
                            include_all_tags = False
                            break
                        else:
                            print(
                                f"{bcolors.WARNING}Introduce opciones válidas. {bcolors.RESET}"
                            )

                    lista_peliculas = service.getTilesByTags(
                        lista_tags, include_all_tags, self.user_token
                    )
                    if lista_peliculas:
                        lista_final_peliculas = "".join(map(str, lista_peliculas))
                        print(f"{bcolors.OK}{lista_final_peliculas}{bcolors.RESET}")
                    else:
                        print(
                            f"{bcolors.WARNING}Película no encontrada. {bcolors.RESET}"
                        )
                except (IceFlix.Unauthorized) as ice_flix_error:
                    print(f"{bcolors.FAIL}{ice_flix_error}\nTOKEN no válido.")

            elif choice == 4:
                try:
                    lista_tags = []
                    anhadir = True
                    media_id = input("Introduce el ID de la pelicula: ")
                    while anhadir:
                        tag = input("Introduce un TAG: ")
                        lista_tags.append(tag)
                        while True:
                            answer = str(input("¿Deseas añadir otro tag?: [y/n]: "))
                            if answer.upper() == "Y":
                                anhadir = True
                                break
                            elif answer.upper() == "N":
                                anhadir = False
                                break
                            else:
                                print(
                                    f"{bcolors.WARNING}Introduce opciones válidas. {bcolors.RESET}"
                                )
                    service.addTags(media_id, lista_tags, self.user_token)
                    print(f"{bcolors.OK}TAGS añadidos correctamente. {bcolors.RESET}")
                except (IceFlix.WrongMediaId, IceFlix.Unauthorized) as ice_flix_error:
                    print(
                        f"{bcolors.FAIL} {ice_flix_error}\nNo se ha podido hacer la operación. {bcolors.RESET}"
                    )

            elif choice == 5:
                try:
                    lista_tags = []
                    anhadir = True
                    media_id = input("Introduce el ID de la película: ")
                    while anhadir:
                        tag = input("Introduce un TAG: ")
                        lista_tags.append(tag)
                        while True:
                            answer = str(input("¿Deseas añadir otro tag?: [y/n]: "))
                            if answer.upper() == "Y":
                                anhadir = True
                                break
                            elif answer.upper() == "N":
                                anhadir = False
                                break
                            else:
                                print(
                                    f"{bcolors.WARNING}Introduce opciones válidas. {bcolors.RESET}"
                                )
                    service.removeTags(media_id, lista_tags, self.user_token)
                    print(f"{bcolors.OK}TAGS borrados correctamente. {bcolors.RESET}")
                except (IceFlix.WrongMediaId, IceFlix.Unauthorized) as ice_flix_error:
                    print(
                        f"{bcolors.FAIL} {ice_flix_error}\nNo se ha podido hacer la operación. {bcolors.RESET}"
                    )

            elif choice == 6:
                try:
                    media_id = input("Introduce el ID de la película: ")
                    new_name = input("Introduce el NUEVO nombre de la película: ")
                    service.renameTile(media_id, new_name, self.admin_token)
                    print(
                        f"{bcolors.OK}Nombre de la película ACTUALIZADO. {bcolors.RESET}"
                    )
                except (IceFlix.WrongMediaId, IceFlix.Unauthorized) as ice_flix_error:
                    print(
                        f"{bcolors.FAIL} {ice_flix_error}\nNo se ha podido hacer la operación. {bcolors.RESET}"
                    )

            elif choice == 7:
                print(f"{bcolors.OK}[!] Saliendo de catalogo...{bcolors.RESET}")
                break

    def getUploader(self, filename):
        """Método relacionado con el streaming."""
        sirviente = MediaUploaderI(filename)
        adapter_uploader = self.communicator().createObjectAdapter("UploaderAdapter")
        adapter_uploader.activate()
        subscriber = adapter_uploader.addWithUUID(sirviente)

        return subscriber

    def prueba_remove_media_streaming(self):
        """Método relacionado con el streaming."""
        media_id = input("Introduce un ID: ")
        self.proxy_streaming.deleteMedia(media_id, self.admin_token)

    def menu_Streaming(self):
        """Método que muestra el menú del streaming."""
        while True:
            print(
                f"""{bcolors.MENU}\n-- MENÚ STREAMING --{bcolors.RESET} Selecciona que desea hacer:
        1.- Upload Media.
        2.- Delete Media.
        3.- Reannounce Media.
        4.- Salir del menú streaming.\n"""
            )

            choice = int(self.establecer_rango_opciones(1, 4))

            if choice == 1:
                try:
                    file_name = input("Introduce el nombre del archivo: ")
                    proxy = self.getUploader(file_name)
                    sirviente = IceFlix.MediaUploaderPrx.uncheckedCast(proxy)
                    self.proxy_streaming.uploadMedia(
                        file_name, sirviente, self.admin_token
                    )
                except (IceFlix.Unauthorized, IceFlix.UploadError) as ice_flix_error:
                    print(f"{bcolors.FAIL}{ice_flix_error}\nOperación no realizada.")
            elif choice == 2:
                try:
                    media_id = input("Introduce un ID: ")
                    self.proxy_streaming.deleteMedia(media_id, self.admin_token)
                except (IceFlix.Unauthorized, IceFlix.WrongMediaId) as ice_flix_error:
                    print(f"{bcolors.FAIL}{ice_flix_error}\nOperación no realizada.")
            elif choice == 3:
                try:
                    self.proxy_streaming.reannounceMedia(None)
                except:
                    print(f"{bcolors.FAIL}{ice_flix_error}\nOperación no realizada.")
            else:
                break

    def control_token(self):
        """Método que permite controlar cuando un token caduca y lo renueva automaticamente."""
        while True:
            if self.user_token is not None:
                time.sleep(120)
                print(f"{bcolors.OK}TOKEN renovado automaticamente.\n{bcolors.RESET}")

                auth_item = self.main_service.getAuthenticator()
                self.user_token = auth_item.refreshAuthorization(
                    self.user, self.password_hash
                )
                self.publicador_revocation.revokeToken(self.user_token, self.user)

    def comprobacion_argumentos(self):
        """Método que comprueba los argumentos de entrada."""
        if len(sys.argv) != 3:
            print(
                f"{bcolors.FAIL}\nNúmero de argumentos incorrectos: "
                "python3 client.py <main_proxy> <admin_token>.\n"
            )
            sys.exit(1)

    def run(self, argv):
        """Implemtación del cliente."""
        self.comprobacion_argumentos()
        self.admin_token = argv[2]
        proxy = self.communicator().stringToProxy(argv[1])
        intentos = 3

        # Bucle que permite establecer la conexión.
        while True:
            if intentos != 0:
                try:
                    self.main_service = IceFlix.MainPrx.checkedCast(proxy)
                    self.main_service.isAdmin(self.admin_token)
                    break
                except:
                    print(f"{bcolors.FAIL}\nServicio no disponible.{bcolors.RESET}")
                    print(f"{bcolors.WARNING}Intentos: {intentos}.\n{bcolors.RESET}")
                    # time.sleep(5)
                    try:
                        proxy_intento = input("Introduce el proxy nuevamente: ")
                        proxy = self.communicator().stringToProxy(proxy_intento)
                        intentos = intentos - 1
                    except:
                        print(f"{bcolors.FAIL}Proxy no detectado.{bcolors.RESET}")
            else:
                print(f"{bcolors.FAIL}\nConexión NO establecida.\n{bcolors.RESET}")
                sys.exit(1)

        # Bucle con la conexión establecida y acceso a las funcionalidades
        while True:
            if self.main_service.isAdmin(self.admin_token):
                print(f"{bcolors.OK}\nTOKEN introducido CORRECTO.{bcolors.RESET}")

                choice = int(self.show_menu())
                service = self.select_option(choice)

                if (choice == 1) and (service is not None):
                    self.menu_authentication(service)
                elif (choice == 2) and (service is not None):
                    self.menu_catalog(service)
                elif choice == 3:
                    os._exit(EXIT_OK)
                else:
                    print("Introduzca una opción válida.")

            else:
                print(f"{bcolors.FAIL}\nTOKEN introducido NO CORRECTO.{bcolors.RESET}")
                self.admin_token = input("Introduce un TOKEN válido: ")


if __name__ == "__main__":
    # Entry point
    sys.exit(Client().main(sys.argv))
