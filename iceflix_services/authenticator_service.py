#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Author: Julián Román Alberca
# Project: Practica SSDD 2122

"""
Servicio Autenticación.
"""

import json
import random
import string
import sys
import threading
import time
import uuid
import Ice

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

try:
    import IceFlix
except ImportError:
    Ice.loadSlice("iceflix_full.ice")
    import IceFlix

from topic_management.topics import get_topic, get_topic_manager

EXIT_OK = 0
TOKEN_SIZE = 30
USERS_FILE = "users.json"

user_password = {}
user_token = {}


class ServiceAnnouncementsI(IceFlix.ServiceAnnouncements):
    """Canal de eventos de todos los microservicios para todos los microservicios."""

    def __init__(self):
        """Inicializador del sirviente ServiceAnnouncements."""
        self._id_ = str(uuid.uuid4())
        global authenticators
        global media_catalogs
        global main_services

        authenticators = {}
        media_catalogs = {}
        main_services = {}

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


class UsersDB(IceFlix.UsersDB):
    def __init__(self, UsersPasswords, UsersToken):
        self.UserPasswords = UsersPasswords
        self.UsersToken = UsersToken


class AuthenticatorI(IceFlix.Authenticator):
    """Sirviente de Authenticator."""

    def __init__(self, service_announcements, broker):
        """Inicializador del sirviente Authenticator."""
        global user_token
        global user_password

        self._service_announcements_ = service_announcements
        self.srvId = str(uuid.uuid4())
        user_password = self.read_json()
        user_token = {}
        self.users_db = IceFlix.UsersDB(user_password, user_token)
        self._service_announcements_.set_users_db(self.users_db)
        self.file_id = 0
        ### Suscripciones
        self.broker = broker
        self.update_publicador = self.suscripcion_users_updates()
        self.revocations_publicador = self.suscripcion_user_revocations()

        # print(f"srvId authenticator: {self.srvId}")

    def suscripcion_users_updates(self):
        """Método que permite suscribirse al topic de UserUpdates."""

        ### UserUpdates

        adapter_user_updates = self.broker.createObjectAdapter("UserUpdatesAdapter")
        adapter_user_updates.activate()

        update_topic = get_topic(get_topic_manager(self.broker), "UserUpdates")
        update_subscriber = UserUpdatesI(self._service_announcements_, self.srvId)
        update_subscriber_proxy = adapter_user_updates.addWithUUID(update_subscriber)
        update_topic.subscribeAndGetPublisher({}, update_subscriber_proxy)

        update_publisher = update_topic.getPublisher()
        update_publicador = IceFlix.UserUpdatesPrx.uncheckedCast(update_publisher)

        return update_publicador

    def suscripcion_user_revocations(self):
        """Método que permite suscribirse al topic de Revocations."""

        ### Revocations

        adapter_revocations = self.broker.createObjectAdapter("RevocationsAdapter")
        adapter_revocations.activate()

        revocation_topic = get_topic(get_topic_manager(self.broker), "Revocations")
        revocation_subscriber = RevocationsI(
            self._service_announcements_, self.srvId, None
        )
        revocation_subscriber_proxy = adapter_revocations.addWithUUID(
            revocation_subscriber
        )
        revocation_topic.subscribeAndGetPublisher({}, revocation_subscriber_proxy)

        revocation_publisher = revocation_topic.getPublisher()
        revocation_publicador = IceFlix.RevocationsPrx.uncheckedCast(
            revocation_publisher
        )

        return revocation_publicador

    def build_token(self):
        """Método que permite generar un token aleatorio."""
        return "".join(
            [
                random.choice(string.digits + string.ascii_letters)
                for _ in range(TOKEN_SIZE)
            ]
        )

    def read_json(self):
        """Método que permite leer del JSON con los usarios y claves."""
        with open("users.json") as file:
            data = json.load(file)

        diccionario = {}

        for user in data["users"]:
            diccionario[user["user"]] = user["password"]
        return diccionario

    def obtener_clave_valor(self, service_dictionary, item):
        """Método para obtener la clave para eliminar un servicio no válido."""
        dictionary = service_dictionary
        buscar_valor = item
        for clave, valor in dictionary.items():
            if valor == buscar_valor:
                index = clave
        return index

    def obtener_main(self):
        """Método que permite acceder a las funciones del servicio main."""
        global main_services

        while True:
            if not list(main_services):
                raise IceFlix.TemporaryUnavailable()
            main_item = random.choice(list(main_services.values()))
            try:
                main_item.ice_ping()
            except:
                clave = self.obtener_clave_valor(main_services, main_item)
                main_services.pop(clave)
            return main_item

    def refreshAuthorization(self, user, passwordHash, current=None) -> string:
        """Método que comprueba si las credenciales enviadas son válidas."""
        global user_token

        passwordHash = passwordHash.upper()
        for clave in user_password:
            if (user == clave) and (passwordHash == user_password[clave]):
                user_token[clave] = self.build_token()
                self.update_publicador.newToken(user, user_token[clave], self.srvId)
                return user_token[clave]
        raise IceFlix.Unauthorized()

    def isAuthorized(self, userToken, current=None) -> bool:
        """Compara el UserToken."""
        for token in user_token:
            if userToken == user_token[token]:
                return True
        return False

    def whois(self, userToken, current=None) -> string:
        """Método que compara si el token es válido devuelve el nombre de usuario."""
        for user in user_token:
            if userToken == user_token[user]:
                return user
        raise IceFlix.Unauthorized()

    def addUser(self, user, passwordHash, adminToken, current=None) -> None:
        """Método administrativo para añadir un usuario."""
        existe_usuario = False
        servicio_main = self.obtener_main()

        if servicio_main.isAdmin(adminToken):
            for clave in user_password.keys():
                if user == clave:
                    print(f"El usuario {user} ya existe")
                    existe_usuario = True

            if not existe_usuario:
                user_password[user] = passwordHash
                with open(USERS_FILE) as file:
                    data = json.load(file)

                data["users"].append({"user": user, "password": passwordHash.upper()})

                with open(USERS_FILE, "w") as file:
                    json.dump(data, file, indent=4)

                print(user_password)
                self.update_publicador.newUser(user, passwordHash, self.srvId)
        else:
            raise IceFlix.Unauthorized()

    def removeUser(self, user, adminToken, current=None) -> None:
        """Método administrativo para eliminar un usuario."""
        servicio_main = self.obtener_main()

        if servicio_main.isAdmin(adminToken):
            with open(USERS_FILE) as file:
                data = json.load(file)

            for indice in range(len(data["users"])):
                if data["users"][indice - 1]["user"] == user:
                    del data["users"][indice - 1]
                    del user_password[user]

            with open(USERS_FILE, "w") as file:
                json.dump(data, file, indent=4)

            self.revocations_publicador.revokeUser(user, self.srvId)
        else:
            raise IceFlix.Unauthorized()

    def addJson(self, user, passwordHash):
        existe_usuario = False

        for clave in user_password.keys():
            if user == clave:
                print(f"El usuario {user} ya existe")
                existe_usuario = True

        if not existe_usuario:
            user_password[user] = passwordHash
            with open(USERS_FILE) as file:
                data = json.load(file)

            data["users"].append({"user": user, "password": passwordHash.upper()})

            with open(USERS_FILE, "w") as file:
                json.dump(data, file, indent=4)

    def updateDB(self, currentDatabase, srvId, current=None):
        """Método relacionado con la base de datos."""
        global user_token

        if srvId != self.srvId:
            for item in currentDatabase:
                password = item.users_passwords
                for clave, valor in password.iteritems():
                    self.addJson(clave, valor)
                user_token = item.users_token


class UserUpdatesI(IceFlix.UserUpdates):
    """Canal de Eventos para notificar al Authenticator() de otros Authenticators()."""

    def __init__(self, sirviente_announcement, srvId) -> None:
        """Inicializador del sirviente UserUpdates."""
        self.sirviente_announcement = sirviente_announcement
        self.srvId = srvId

    def newUser(self, user, passwordHash, srvId, current=None) -> None:
        """Emitido cuando un usario es añadido."""
        global user_password

        if srvId in self.sirviente_announcement.known_services:
            user_password[user] = passwordHash

    def newToken(self, user, userToken, srvId, current=None) -> None:
        """Emitido cuando un token es creado."""
        global user_token

        if srvId in self.sirviente_announcement.known_services:
            user_token[user] = userToken


class RevocationsI(IceFlix.Revocations):
    """Canal de Eventos para notificar al Authenticator() de todos los demás microservicios."""

    def __init__(self, sirviente_announcement, srvId, token) -> None:
        """Inicializador del sirviente Revocations."""
        self.sirviente_announcement = sirviente_announcement
        self.srvId = srvId
        self.token = token

    def revokeToken(self, userToken, srvId, current=None) -> None:
        """Emitido cuando token expira."""
        global user_token
        user_token[srvId] = userToken

    def revokeUser(self, user, srvId, current=None) -> None:
        """Emitido cuando un usario es eliminado."""
        global user_password

        if srvId in self.sirviente_announcement.known_services:
            del user_password[user]


class authenticator_service(Ice.Application):
    """Implementacion del servidor."""

    def iniciar_announcements(self, publicador, service, srvId):
        """Inciar los anouncemments."""

        publicador.newService(service, str(srvId))
        time.sleep(5)
        lista_segundos = [0, 1, 2]

        while True:
            publicador.announce(service, str(srvId))
            constante_d = random.choice(lista_segundos)
            tiempo_espera = 10 + constante_d
            time.sleep(tiempo_espera)

    def run(self, argv):
        """Método principal para la ejecución del servidor."""
        print(f"Inicializando Autenticator...")

        broker = self.communicator()
        adapter_auth = broker.createObjectAdapter("AuthenticatorAdapter")
        adapter_auth.activate()

        ### Announcements

        announce_topic = get_topic(get_topic_manager(broker), "ServiceAnnouncements")
        announce_subscriber = ServiceAnnouncementsI()
        announce_subscriber_proxy = adapter_auth.addWithUUID(announce_subscriber)
        announce_topic.subscribeAndGetPublisher({}, announce_subscriber_proxy)

        auth_service_implementation = AuthenticatorI(announce_subscriber, broker)
        proxy = adapter_auth.addWithUUID(auth_service_implementation)

        announce_publisher = announce_topic.getPublisher()
        announce_publicador = IceFlix.ServiceAnnouncementsPrx.uncheckedCast(
            announce_publisher
        )

        try:
            threading.Thread(
                target=self.iniciar_announcements,
                args=(
                    announce_publicador,
                    proxy,
                    auth_service_implementation.srvId,
                ),
            ).start()
        except Exception as e:
            print(e)

        self.shutdownOnInterrupt()
        broker.waitForShutdown()

        announce_topic.unsubscribe(announce_subscriber_proxy)

        return EXIT_OK


if __name__ == "__main__":
    # Entry point
    sys.exit(authenticator_service().main(sys.argv))
