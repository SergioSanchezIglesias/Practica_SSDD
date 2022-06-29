#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Servicio principal (main).
"""

import random
import secrets
import string
import sys
import threading
import time
import uuid

import Ice

try:
    import IceFlix
except ImportError:
    Ice.loadSlice("iceflix_full.ice")
    import IceFlix

from topic_management.topics import get_topic, get_topic_manager

EXIT_OK = 0
TOKEN_SIZE = 32

authenticators = {}
media_catalogs = {}
main_services = {}
streamings = {}

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


class ServiceAnnouncementsI(IceFlix.ServiceAnnouncements):
    """Canal de eventos de todos los microservicios para todos los microservicios."""

    def __init__(self):
        """Inicializador del sirviente ServiceAnnouncements."""
        self._id_ = str(uuid.uuid4())
        global authenticators
        global media_catalogs
        global main_services
        global streaming_service

        authenticators = {}
        media_catalogs = {}
        main_services = {}
        streamings = {}

        self.main_proxy = None
        self.auth_proxy = None
        self.users_db = None

    @property
    def known_services(self):
        """Método que permite obtener los srv de los servicios Auth y MediaCatalog."""
        return (
            list(authenticators.keys())
            + list(media_catalogs.keys())
            + list(main_services.keys())
            + list(streamings.keys())
        )

    @property
    def service_id(self):
        """Obtener instancia de ID."""
        return self._id_

    def set_users_db(self, users_db):
        """Método para establecer un valor de userDB (Authenticator)."""
        self.users_db = users_db

    def newService(self, service, srvId, current=None) -> None:
        """Emitido al inicio del servidor, antes de que este listo para atender al Cliente."""
        self.auxiliar_announcements(service, srvId)

    def announce(self, service, srvId, current=None) -> None:
        """Comprueba el tipo de servicio y lo añade."""
        self.auxiliar_announcements(service, srvId)

    def no_primer_servicio(self, srvId) -> None:
        """Método que permite  llamar al método de updateDB cuando es necesario."""
        auth_list = list(authenticators.values())
        catalog_list = list(media_catalogs.values())

        volatile_service = IceFlix.VolatileServices(auth_list, catalog_list)
        time.sleep(3)
        try:
            print(f"PROXY MAIN: {self.main_proxy}")
            self.main_proxy.updateDB(volatile_service, srvId)
        except:
            print("No se ha podido establecer conexión con el servicio main.\n")

    def auxiliar_announcements(self, service, srvId) -> None:
        """Método auxiliar que realiza una función dependiendo si es un announce un newService."""

        global authenticators
        global media_catalogs
        global main_services

        if srvId in self.known_services:
            return
        # Comprobaciones si el servicio es del tipo AUTHENTICATOR.
        if service.ice_isA("::IceFlix::Authenticator"):
            authenticators[srvId] = IceFlix.AuthenticatorPrx.uncheckedCast(service)
            self.auth_proxy = authenticators[srvId]
            if len(authenticators) >= 2:
                self.auth_proxy.updateDB(self.users_db, srvId)
                self.no_primer_servicio(srvId)
        # Comprobaciones si el servicio es del tipo MEDIA CATALOG.
        elif service.ice_isA("::IceFlix::MediaCatalog"):
            media_catalogs[srvId] = IceFlix.MediaCatalogPrx.uncheckedCast(service)
            if len(media_catalogs) >= 2:
                print("")
                self.no_primer_servicio(srvId)
        # Comprobaciones si el servicio es del tipo MAIN.
        elif service.ice_isA("::IceFlix::Main"):
            main_services[srvId] = IceFlix.MainPrx.uncheckedCast(service)
            self.main_proxy = main_services[srvId]

            if len(main_services) >= 2:
                print("")
                self.no_primer_servicio(srvId)


class VolatileServices(IceFlix.VolatileServices):
    """Una estructura de slice se mapea como una clase Python con el mismo nombre."""

    def __init__(self, AuthenticatorList, MediaCatalogList):
        """Inicialización de objetos con listas vacías."""

        self.authenticators = []
        self.mediaCatalogs = []

        for item in AuthenticatorList:
            self.authenticators.append(IceFlix.AuthenticatorPrx.uncheckedCast(item))

        for item in MediaCatalogList:
            self.mediaCatalogs.append(IceFlix.MediaCatalogPrx.uncheckedCast(item))

    def get_autenticators(self):
        """Método get para autenticators."""
        return self.AuthenticatorList

    def set_autenticators(self, auth):
        """Método set para autenticators."""
        self._authenticators = auth

    def get_catalogs(self):
        """Método get para catalog."""
        return self._mediaCatalog

    def set_catalogs(self, catalogs):
        """Método set para catalog."""
        self._mediaCatalog = catalogs


class MainI(IceFlix.Main):
    """Sirviente de Main."""

    def __init__(self, admin_token, service_announcements):
        """Inicializador del sirviente Main."""
        global authenticators
        self.token = admin_token
        self._service_announcements_ = service_announcements
        self.srvId = str(uuid.uuid4())
        self.id_token = {"id": self.srvId, "token": self.token}

    def obtener_clave_valor(self, service_dictionary, item):
        """Método para obtener la clave para eliminar un servicio no válido."""
        dictionary = service_dictionary
        buscar_valor = item
        for clave, valor in dictionary.items():
            if valor == buscar_valor:
                index = clave
        return index

    def getAuthenticator(self, current=None):
        """Devulve el proxy al servicio de autenticación configurado."""
        global authenticators
        print(authenticators)
        while True:
            if not list(authenticators):
                raise IceFlix.TemporaryUnavailable()
            auth_item = random.choice(list(authenticators.values()))
            try:
                auth_item.ice_ping()
            except:
                clave = self.obtener_clave_valor(authenticators, auth_item)
                authenticators.pop(clave)

            return auth_item

    def getCatalog(self, current=None):
        """Devulve el proxy al servicio de catálogo configurado."""
        global media_catalogs
        while True:
            if not list(media_catalogs):
                raise IceFlix.TemporaryUnavailable()
            catalog_item = random.choice(list(media_catalogs.values()))
            try:
                catalog_item.ice_ping()
            except:
                clave = self.obtener_clave_valor(media_catalogs, catalog_item)
                media_catalogs.pop(clave)

            return catalog_item

    def updateDB(self, currentServices, srvId, current=None):
        """Método del main relacionado con la BBDD."""
        global authenticators
        global media_catalogs

        for auth in currentServices.authenticators:
            index = str(uuid.uuid4())
            authenticators[index] = auth

        for catalog in currentServices.mediaCatalogs:
            index = str(uuid.uuid4())
            media_catalogs[uuid] = catalog

    def isAdmin(self, admin_token, current=None) -> bool:
        """Compara el token generado con el introducido por el usuario."""
        return admin_token == self.token


class main_service(Ice.Application):
    """Implementacion del servidor."""

    def no_default_token_generator(self):
        """Devuelve un token en caso de no existir en el archivo de configuración."""
        return "".join(
            secrets.choice((string.ascii_letters).upper() + string.digits)
            for i in range(TOKEN_SIZE)
        )

    def iniciar_announcements(self, publicador, service, srvId):
        """Inciar los anouncemments."""
        publicador.newService(service, str(srvId))
        time.sleep(10)
        lista_segundos = [-2, -1, 0, 1, 2]

        while True:
            publicador.announce(service, str(srvId))
            constante_d = random.choice(lista_segundos)
            tiempo_espera = 10 + constante_d
            time.sleep(tiempo_espera)

    def run(self, argv):  # pylint: disable=invalid-name,unused-argument
        """Método principal para la ejecución del servidor."""

        broker = self.communicator()
        adapter = broker.createObjectAdapter("MainAdapter")
        adapter.activate()

        properties = broker.getProperties()
        admin_token = properties.getProperty("AdminToken")

        if admin_token == "":
            admin_token = self.no_default_token_generator()

        announce_topic = get_topic(get_topic_manager(broker), "ServiceAnnouncements")
        announce_subscriber = ServiceAnnouncementsI()
        announce_subscriber_proxy = adapter.addWithUUID(announce_subscriber)
        announce_topic.subscribeAndGetPublisher({}, announce_subscriber_proxy)

        main_service = MainI(admin_token, announce_subscriber)
        proxy = adapter.addWithUUID(main_service)

        announce_publisher = announce_topic.getPublisher()
        announce_publicador = IceFlix.ServiceAnnouncementsPrx.uncheckedCast(
            announce_publisher
        )

        if main_service.id_token["token"] == main_service.token:
            print(proxy, main_service.token, flush=True)
            try:
                threading.Thread(
                    target=self.iniciar_announcements,
                    args=(
                        announce_publicador,
                        proxy,
                        main_service.srvId,
                    ),
                ).start()
            except Exception as exception:
                print(exception)
        else:
            print("El servicio main ha comprobado los datos, pero no coinciden.\n")
            return EXIT_OK

        self.shutdownOnInterrupt()
        broker.waitForShutdown()
        announce_topic.unsubscribe(announce_subscriber_proxy)

        return EXIT_OK


if __name__ == "__main__":
    # Entry point
    sys.exit(main_service().main(sys.argv))
