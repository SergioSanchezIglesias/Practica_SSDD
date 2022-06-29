#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Author: Sergio Sanchez Iglesias
# Project: Practica SSDD 2122
# Date: 19/11/2021
# Version 1: Creation of the DataBase
# Version 2: MediaCatalogI class implementation

"""
Servicio Media Catalog.
"""

import random
import sqlite3
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


from sqlite3 import Error
from topic_management.topics import get_topic, get_topic_manager

EXIT_OK = 0

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
        global streamings

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
            self.media_Catalog = media_catalogs[srvId]
            if len(media_catalogs) >= 2:
                self.media_Catalog.updateDB(self.users_db, srvId)
                self.no_primer_servicio(srvId)
        # Comprobaciones si el servicio es del tipo MAIN.
        elif service.ice_isA("::IceFlix::Main"):
            main_services[srvId] = IceFlix.MainPrx.uncheckedCast(service)
            self.main_proxy = main_services[srvId]

            if len(main_services) >= 2:
                self.no_primer_servicio(srvId)
        elif service.ice_isA("::IceFlix::StreamProvider"):
            streamings[srvId] = IceFlix.StreamProviderPrx.uncheckedCast(service)


class bcolors:
    OK = "\033[92m"  # GREEN
    WARNING = "\033[93m"  # YELLOW
    FAIL = "\033[91m"  # RED
    RESET = "\033[0m"  # RESET COLOR


class Media(IceFlix.Media):
    def __init__(self, mediaId, provider, info):
        self.mediaId = mediaId
        self.provider = provider
        self.info = info


class MediaInfo(IceFlix.MediaInfo):
    def __init__(self, name, tags):
        self.name = name
        self.tags = tags


class ObjectNewMedia(object):
    def __init__(self, mediaId, initialName, srvId):
        self.mediaId = mediaId
        self.initialName = initialName
        self.srvId = srvId


class MediaDB(IceFlix.MediaDB):
    def __init__(self, mediaId, name, tagsPerUser):
        self.mediaId = mediaId
        self.name = name
        self.tagsPerUser = tagsPerUser


class StreamAnnouncementsI(IceFlix.StreamAnnouncements):
    """Canal de eventros para notificaciones de StreamProvider() a MediaCatalog()."""

    def __init__(self):
        self._lista_new_media = []
        self._almacen_medias = {}

    def newMedia(self, mediaId, initialName, srvId, current=None) -> None:
        """Emitido cuando un nuevo media es encontrado/subido en StreamProvider()."""
        object_new_media = ObjectNewMedia(mediaId, initialName, srvId)
        self._lista_new_media.append(object_new_media)
        self._almacen_medias[mediaId] = srvId
        self.almacenar_DB()

    def removedMedia(self, mediaId, srvId, current=None) -> None:
        """Emitido cuando un media es eliminado de StreamProvider()."""
        del self._almacen_medias[mediaId]

    def almacenar_DB(self):
        if self._lista_new_media:
            conexion = self.obtener_conexion()
            cursor_obj = conexion.cursor()

            for item in self._lista_new_media:
                is_register = self.comprobar_EntradaDB(cursor_obj, item)
                if not is_register:
                    sql = """INSERT INTO peliculas VALUES (?, ?)"""
                    sql_data = (item.mediaId, item.initialName)
                    cursor_obj.execute(sql, sql_data)
                    conexion.commit()
                    self._lista_new_media.remove(item)

    def comprobar_EntradaDB(self, cursor_obj, item):
        sql = """SELECT * FROM peliculas WHERE ID = ?"""
        cursor_obj.execute(sql, (item.mediaId,))
        row = cursor_obj.fetchone()
        if row:
            return True
        else:
            return False

    def obtener_conexion(self):
        """Método que permite obtener la conexión a la BBDD."""
        try:
            conexion = sqlite3.connect("Database.db")
        except Error:
            print(Error)
        return conexion


class CatalogUpdatesI(IceFlix.CatalogUpdates):
    """Emitido cuando cualquier MediaCatalog() actualiza sus datos almacenados."""

    def __init__(self, service_announcements):
        self.service_announcements = service_announcements

    def renameTile(self, mediaId, name, srvId, current=None) -> None:
        if srvId in self.service_announcements.known_services:
            con = self.obtener_conexion()
            cursor_obj = con.cursor()

            sql = """SELECT * FROM peliculas WHERE ID LIKE ?"""
            cursor_obj.execute(sql, (mediaId,))
            row = cursor_obj.fetchone()

            if row:
                sql_update = """UPDATE peliculas SET Nombre=? WHERE ID=?"""
                sql_data = (name, mediaId)
                cursor_obj.execute(sql_update, sql_data)
                con.commit()

            con.close()

    def addTags(self, mediaId, tags, user, srvId, current=None) -> None:
        if srvId in self.service_announcements.known_services:
            con = self.obtener_conexion()
            cursor_obj = con.cursor()

            sql = """SELECT ID FROM usuarios WHERE UPPER(Nombre) = ?"""
            cursor_obj.execute(sql, (user,))
            user_Id = cursor_obj.fetchone()

            for tag in tags:
                sql = """SELECT * FROM relacciones WHERE ID_Pelicula=? AND ID_Usuario=? AND Tag=?"""
                sql_data = (mediaId, user_Id, tag)
                row = cursor_obj.fetchone()
                if not row:
                    sql = """INSERT INTO relacciones(ID_Pelicula, ID_Usuario, Tag) VALUES(?, ?, ?)"""
                    sql_data = (mediaId, user_Id[0], tag)
                    cursor_obj.execute(sql, sql_data)
                    con.commit()

            con.close()

    def removeTags(self, mediaId, tags, user, srvId, current=None) -> None:
        if srvId in self.service_announcements.known_services:
            con = self.obtener_conexion()
            cursor_obj = con.cursor()

            sql = """SELECT ID FROM usuarios WHERE UPPER(Nombre) = ?"""
            cursor_obj.execute(sql, (user,))
            user_Id = cursor_obj.fetchone()

            for tag in tags:
                sql = """DELETE FROM relacciones WHERE ID_pelicula=? AND ID_Usuario=? AND UPPER(tag) LIKE ?"""
                sql_data = (mediaId, user_Id[0], tag.upper())
                cursor_obj.execute(sql, sql_data)
                con.commit()

            con.close()

    def obtener_conexion(self):
        """Método que permite obtener la conexión a la BBDD."""
        try:
            conexion = sqlite3.connect("Database.db")
        except Error:
            print(Error)
        return conexion


class MediaCatalogI(IceFlix.MediaCatalog):
    """Sirviente de Media Catalog."""

    def __init__(self, service_announcements, broker):
        """Inicializador del sirviente MediaCatalog."""
        self._service_announcements_ = service_announcements
        self.srvId = str(uuid.uuid4())
        self.broker = broker
        self._servant_stream_announcements = self.subscripcion_Stream_Announcements(
            broker
        )
        self.publicador_Catalog_Updates = self.subscripcion_Catalog_Updates(broker)

        mediaDb = self.getMediaDBList()
        self._service_announcements_.set_users_db(mediaDb)

    def subscripcion_Stream_Announcements(self, broker):
        adapter_stream_announcement = self.broker.createObjectAdapter(
            "StreamAnnouncementsAdapter"
        )
        adapter_stream_announcement.activate()

        # Suscripcion a StreamAnnouncement
        ### MediaCatalog se subscribe a StreamAnnouncement
        topic_stream_a = get_topic(
            get_topic_manager(self.broker), "StreamAnnouncements"
        )
        servant_stream_announce = StreamAnnouncementsI()
        subscriber_stream_announcement = adapter_stream_announcement.addWithUUID(
            servant_stream_announce
        )
        topic_stream_a.subscribeAndGetPublisher({}, subscriber_stream_announcement)
        return servant_stream_announce

    def subscripcion_Catalog_Updates(self, broker):
        adapter_Catalog_updates = self.broker.createObjectAdapter(
            "CatalogUpdatesAdapter"
        )
        adapter_Catalog_updates.activate()

        topic_stream_c = get_topic(get_topic_manager(self.broker), "CatalogUpdates")
        servant_Catalog_Updates = CatalogUpdatesI(self._service_announcements_)
        subscriber_Catalog_Updates = adapter_Catalog_updates.addWithUUID(
            servant_Catalog_Updates
        )
        topic_stream_c.subscribeAndGetPublisher({}, subscriber_Catalog_Updates)

        catalog_publisher = topic_stream_c.getPublisher()
        catalog_publicador = IceFlix.CatalogUpdatesPrx.uncheckedCast(catalog_publisher)
        return catalog_publicador

    def obtener_conexion(self):
        """Método que permite obtener la conexión a la BBDD."""
        try:
            conexion = sqlite3.connect("Database.db")
        except Error:
            print(Error)
        return conexion

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

    def obtener_provider(self):
        """Método que permite obtener un streamingProvider y funcionalidades."""
        global streamings
        while True:
            if not list(streamings):
                raise IceFlix.TemporaryUnavailable()
            provider_item = random.choice(list(streamings.values()))
            try:
                provider_item.ice_ping()
            except:
                clave = self.obtener_clave_valor(streamings, provider_item)
                streamings.pop(clave)
            return provider_item

    def obtener_authenticator(self):
        """Método que permite obtener un Authenticator y funcionalidades."""
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
            break

        return main_item.getAuthenticator()

    def getTile(self, mediaId, userToken, current=None):
        """Método que acepta el Id de un medio y devuelve una estructura Media."""
        conexion = self.obtener_conexion()
        auth_item = self.obtener_authenticator()
        cursor_obj = conexion.cursor()

        if auth_item.isAuthorized(userToken):
            name_user = auth_item.whois(userToken)
            sql = """SELECT Nombre FROM peliculas WHERE UPPER(ID) LIKE ?"""
            cursor_obj.execute(sql, (mediaId.upper(),))  # hay que cambiar por id
            name_media = cursor_obj.fetchone()

            if not name_media:
                raise IceFlix.WrongMediaId(mediaId)
            sql = """SELECT ID FROM usuarios WHERE UPPER(Nombre) = ?"""
            cursor_obj.execute(sql, (name_user.upper(),))
            id_user = cursor_obj.fetchone()

            if not id_user:
                sql = """INSERT INTO usuarios(Nombre) VALUES (?)"""
                cursor_obj.execute(sql, (name_user,))
                conexion.commit()
                sql = """SELECT ID FROM usuarios WHERE UPPER(Nombre) = ?"""
                cursor_obj.execute(sql, (name_user.upper(),))
                id_user = cursor_obj.fetchone()

            sql = """SELECT tag FROM relacciones WHERE ID_Pelicula = ? AND ID_Usuario = ?"""
            sql_data = (mediaId.upper(), id_user[0])  # hay que cambiar por id
            cursor_obj.execute(sql, sql_data)
            lista_Tags = cursor_obj.fetchall()

            string_tags = []
            for tag in lista_Tags:
                string_tags.append(tag[0])

            mediaInfo = MediaInfo(name_media[0], string_tags)
            srvId = self._servant_stream_announcements._almacen_medias[mediaId]
            provider = streamings[srvId]
            print(provider)
            media = Media(mediaId, provider, mediaInfo)

            return media
        else:
            raise IceFlix.Unauthorized()

    def getTilesByName(self, name, exact, current=None):
        """Método que permite buscar títulos cuyo nombre incluya el texto indicado."""
        conexion = self.obtener_conexion()
        cursor_obj = conexion.cursor()
        lista_peliculas = []

        if exact:
            sql = """SELECT * FROM peliculas WHERE UPPER(Nombre) LIKE ?"""
            cursor_obj.execute(sql, (name.upper(),))
            rows = cursor_obj.fetchall()
            if not rows:
                print(
                    f"{bcolors().FAIL}[-] Nombre de la pelicula no encontrado.{bcolors().RESET}"
                )
            else:
                for row in rows:
                    lista_peliculas.append(row)

                lista_final_peliculas = " ".join(map(str, lista_peliculas))
                return lista_final_peliculas
        else:
            sql = """SELECT * FROM peliculas WHERE (INSTR(UPPER(Nombre), ?) > 0)"""
            cursor_obj.execute(sql, (name.upper(),))
            rows = cursor_obj.fetchall()
            if not rows:
                print(
                    f"{bcolors().FAIL}[-] Nombre de la pelicula no encontrado.{bcolors().RESET}"
                )
            else:
                for row in rows:
                    lista_peliculas.append(row)

                lista_final_peliculas = ", ".join(map(str, lista_peliculas))
                return lista_final_peliculas

    def getTilesByTags(self, tags, includeAllTags, userToken, current=None):
        """Método que permite buscar en el catálogo vídeos con tags."""
        conexion = self.obtener_conexion()
        auth_item = self.obtener_authenticator()
        cursor_obj = conexion.cursor()
        movie_list = []

        if auth_item.isAuthorized(userToken):
            name_user = auth_item.whois(userToken)
            if includeAllTags:
                id_movie_list = []  # Lista final donde se guardan los ids correctos
                for tag in tags:
                    id_movie_list_overwrite = (
                        []
                    )  # Lista donde se almacenan las coincidencias para despues sobreescribir la lista final
                    id_movie_list_auxiliar = (
                        []
                    )  # Lista donde se guardan los ids de las consultas

                    # Comprobacion de que el usuario se encuentra en la base de datos, y si no, se registra
                    sql = """SELECT ID FROM usuarios WHERE UPPER(Nombre) = ?"""
                    cursor_obj.execute(sql, (name_user,))
                    id_user = cursor_obj.fetchone()
                    if not id_user:
                        sql = """INSERT INTO usuarios(Nombre) VALUES (?)"""
                        cursor_obj.execute(sql, (name_user,))
                        conexion.commit()
                        sql = """SELECT ID FROM usuarios WHERE UPPER(Nombre) = ?"""
                        cursor_obj.execute(sql, (name_user,))
                        id_user = cursor_obj.fetchone()

                    sql = """SELECT ID_pelicula FROM relacciones WHERE ID_Usuario=? AND UPPER(Tag) = ?"""
                    sql_data = (id_user, tag.upper())
                    cursor_obj.execute(sql, sql_data)
                    row = cursor_obj.fetchall()
                    if row:
                        i = 0
                        while i < len(row):
                            if row[i][0] not in id_movie_list_auxiliar:
                                id_movie_list_auxiliar.append(str(row[i][0]))
                            i += 1
                        if len(id_movie_list) < 1:
                            id_movie_list_overwrite = id_movie_list_auxiliar
                        else:
                            for id in id_movie_list:
                                if id in id_movie_list_auxiliar:
                                    id_movie_list_overwrite.append(id)
                        id_movie_list = id_movie_list_overwrite
                    else:
                        print(
                            f"{bcolors().FAIL}[!] No se encuentra el tag{bcolors().RESET}"
                        )
                        id_movie_list = []
                        break

                if id_movie_list:
                    for id in id_movie_list:
                        sql = """SELECT * FROM peliculas WHERE id=?"""
                        cursor_obj.execute(sql, (id,))
                        row = cursor_obj.fetchone()
                        if row:
                            movie_list.append(row)

                    lista_final_peliculas = ", ".join(map(str, movie_list))
                    return lista_final_peliculas

            else:
                id_movie_list = []  # Lista final donde se guardan los ids correctos
                for tag in tags:
                    # Comprobacion de que el usuario se encuentra en la base de datos, y si no, se registra
                    sql = """SELECT ID FROM usuarios WHERE UPPER(Nombre) = ?"""
                    cursor_obj.execute(sql, (name_user.upper(),))
                    id_user = cursor_obj.fetchone()
                    if not id_user:
                        sql = """INSERT INTO usuarios(Nombre) VALUES (?)"""
                        cursor_obj.execute(sql, (name_user,))
                        conexion.commit()
                        sql = """SELECT ID FROM usuarios WHERE UPPER(Nombre) = ?"""
                        cursor_obj.execute(sql, (name_user.upper(),))
                        id_user = cursor_obj.fetchone()

                    sql = """SELECT ID_Pelicula FROM relacciones WHERE ID_Usuario=? AND UPPER(Tag) = ?"""
                    sql_data = (id_user[0], tag.upper())
                    cursor_obj.execute(sql, sql_data)
                    row = cursor_obj.fetchall()
                    if row:
                        i = 0
                        while i < len(row):
                            if row[i][0] not in id_movie_list:
                                id_movie_list.append(str(row[i][0]))
                            i += 1

                if id_movie_list:
                    for id in id_movie_list:
                        sql = """SELECT * FROM peliculas WHERE id=?"""
                        cursor_obj.execute(sql, (id,))
                        row = cursor_obj.fetchone()
                        if row:
                            movie_list.append(row)

                    lista_final_peliculas = ", ".join(map(str, movie_list))
                    return lista_final_peliculas
        else:
            raise IceFlix.Unauthorized()

    def addTags(self, mediaId, tags, userToken, current=None) -> None:
        """Método que permite añadir una lista de tags a un medio concreto."""
        conexion = self.obtener_conexion()
        auth_item = self.obtener_authenticator()
        cursor_obj = conexion.cursor()

        if auth_item.isAuthorized(userToken):
            name_user = auth_item.whois(userToken)
            # Comprobación de que la película existe
            sql = """SELECT * FROM peliculas WHERE ID LIKE ?"""
            cursor_obj.execute(sql, (mediaId.upper(),))
            row = cursor_obj.fetchone()

            if row:
                for tag in tags:
                    sql = """SELECT tag FROM tags WHERE UPPER(tag) = ?"""
                    cursor_obj.execute(sql, (tag.upper(),))
                    row = cursor_obj.fetchone()
                    if not row:
                        sql_insert_tags = """INSERT INTO tags VALUES (?)"""
                        cursor_obj.execute(sql_insert_tags, (tag,))
                        conexion.commit()
                    # Obtener el id del usuario
                    sql = """SELECT ID FROM usuarios WHERE UPPER(Nombre) = ?"""
                    cursor_obj.execute(sql, (name_user.upper(),))
                    id_user = cursor_obj.fetchone()
                    if not id_user:
                        sql = """INSERT INTO usuarios(Nombre) VALUES (?)"""
                        cursor_obj.execute(sql, (name_user,))
                        conexion.commit()
                        sql = """SELECT ID FROM usuarios WHERE UPPER(Nombre) = ?"""
                        cursor_obj.execute(sql, (name_user.upper(),))
                        id_user = cursor_obj.fetchone()

                    sql = """SELECT * FROM relacciones WHERE ID_Pelicula=? AND ID_Usuario=? AND Tag=?"""
                    sql_data = (mediaId, id_user[0], tag)
                    cursor_obj.execute(sql, sql_data)
                    row = cursor_obj.fetchone()
                    if not row:
                        sql_insert_relacciones = """INSERT INTO relacciones(ID_Pelicula, ID_Usuario, Tag) VALUES (?, ?, ?)"""
                        sql_data = (mediaId, id_user[0], tag)
                        cursor_obj.execute(sql_insert_relacciones, sql_data)
                        conexion.commit()
                        self.publicador_Catalog_Updates.addTags(None, None, None, None)
            else:
                raise IceFlix.WrongMediaId(mediaId)
        else:
            raise IceFlix.Unauthorized()

    def removeTags(self, mediaId, tags, userToken, current=None) -> None:
        """Método que permite eliminar una lista de tags de un medio concreto."""
        conexion = self.obtener_conexion()
        auth_item = self.obtener_authenticator()
        cursor_obj = conexion.cursor()

        if auth_item.whois(userToken):
            name_user = auth_item.whois(userToken)
            sql = """SELECT * FROM peliculas WHERE ID = ?"""
            cursor_obj.execute(sql, (mediaId,))
            row = cursor_obj.fetchone()

            if row:
                for tag in tags:
                    # Obtener el ID del usuario.
                    sql = """SELECT ID FROM usuarios WHERE UPPER(Nombre) = ?"""
                    cursor_obj.execute(sql, (name_user.upper(),))
                    id_user = cursor_obj.fetchone()

                    if not id_user:
                        sql = """INSERT INTO usuarios(Nombre) VALUES (?)"""
                        cursor_obj.execute(sql, (name_user,))
                        conexion.commit()
                        sql = """SELECT ID FROM usuarios WHERE UPPER(Nombre) = ?"""
                        cursor_obj.execute(sql, (name_user.upper(),))
                        id_user = cursor_obj.fetchone()

                    sql = """DELETE FROM relacciones WHERE ID_pelicula=? AND ID_Usuario=? AND UPPER(tag) LIKE ?"""
                    sql_data = (mediaId, id_user[0], tag.upper())
                    cursor_obj.execute(sql, sql_data)
                    conexion.commit()
            else:
                raise IceFlix.WrongMediaId(mediaId)
        else:
            raise IceFlix.Unauthorized()

    def renameTile(self, mediaId, name, adminToken, current=None) -> None:
        """Método administrativo para modificar el nombre del medio asociado a un ID."""
        conexion = self.obtener_conexion()
        main_item = self.obtener_main()
        cursor_obj = conexion.cursor()

        if main_item.isAdmin(adminToken):
            sql = """SELECT * FROM peliculas WHERE ID = ?"""
            cursor_obj.execute(sql, (mediaId,))
            row = cursor_obj.fetchone()
            if row:
                sql_update = """UPDATE peliculas SET Nombre=? WHERE ID=?"""
                sql_data = (name, mediaId)
                cursor_obj.execute(sql_update, sql_data)
                conexion.commit()
            else:
                raise IceFlix.WrongMediaId(mediaId)
        else:
            raise IceFlix.Unauthorized()

    def updateDB(self, catalogDatabase, srvId, current=None) -> None:
        """Método que permite actualizar BBDD."""

        if srvId != self.srvId:
            for item in catalogDatabase:
                media_Id = item.media_Id
                media_name = item.name
                tagsPerUser = item.tagsPerUser
                # Comprobar que la película existe
                if not self.comprobar_Media(media_name):
                    self.addTile(media_Id, media_name)

                for user_name, tagslist in tagsPerUser.items():
                    # comprobamos si el usuario existe
                    if self.comprobar_Usuario(user_name) == False:
                        self.addUser(user_name)

                    for tag in tagslist:
                        # Comprobamos que esta en la tabla TAG
                        if not self.comprobar_Tag(tag):
                            self.addSingleTag(tag)
                            self.anhadir_Entrada_Relacciones(media_Id, user_name, tag)
                        else:
                            # COmprobamos que esta en la tabla Common
                            if not self.comprobar_Entrada_Relacciones(
                                media_Id, user_name, tag
                            ):
                                self.anhadir_Entrada_Relacciones(
                                    media_Id, user_name, tag
                                )

    def comprobar_Media(self, media_name):
        con = self.obtener_conexion()
        cObj = con.cursor()
        sql = """SELECT ID FROM peliculas WHERE UPPER(Nombre)=?"""
        sql_data = media_name.upper()
        cObj.execute(sql, sql_data)
        row = cObj.fetchone()
        if not row:
            con.close()
            return False
        else:
            con.close()
            return True

    def comprobar_Tag(self, tag):
        con = self.obtener_conexion()
        cObj = con.cursor()
        sql = """SELECT * FROM Tags WHERE UPPER(tag)=?"""
        sql_data = tag.upper()
        cObj.execute(sql, sql_data)
        row = cObj.fetchone()
        if not row:
            con.close()
            return False
        else:
            con.close()
            return True

    def comprobar_Entrada_Relacciones(self, media_Id, user_name, tag):
        con = self.obtener_conexion()
        user_id = self.userExist(user_name)
        cObj = con.cursor()
        sql = """SELECT * FROM relacciones WHERE ID_Pelicula=? AND ID_Usuario=? AND UPPER(tag)=?"""
        sql_data = (media_Id, user_id, tag.upper())
        cObj.execute(sql, sql_data)
        row = cObj.fetchone()
        if not row:
            con.close()
            return False
        else:
            con.close()
            return True

    def comprobar_Usuario(self, user_name):
        con = self.obtener_conexion()
        cObj = con.cursor()
        sql = """SELECT ID FROM usuarios WHERE UPPER(Nombre)=?"""
        sql_data = user_name.upper()
        cObj.execute(sql, sql_data)
        row = cObj.fetchone()
        if not row:
            con.close()
            return False
        else:
            con.close()
            return row[0]

    def anhadir_Entrada_Relacciones(self, media_Id, user_name, tag):
        user_id = self.userExist(user_name)
        con = self.obtener_conexion()
        cObj = con.cursor()
        sql_insert = (
            """INSERT INTO relacciones(ID_Pelicula, ID_Usuario, Tag) VALUES (?, ?, ?)"""
        )
        sql_data = (media_Id, user_id, tag)
        cObj.execute(sql_insert, sql_data)
        con.commit()
        con.close()

    def addTile(self, mediaId, name):
        print("Añadiendo tile...")
        con = self.obtener_conexion()
        ## check mediaId
        cObj = con.cursor()
        sql_insert = """INSERT INTO peliculas(ID, Nombre) VALUES (?, ?)"""
        sql_data = (mediaId, name)
        cObj.execute(sql_insert, sql_data)
        con.commit()
        con.close()

    def addUser(self, user_name):
        con = self.obtener_conexion()
        cObj = con.cursor()
        sql_insert = """INSERT INTO usuarios(Nombre) VALUES (?)"""
        sql_data = user_name
        cObj.execute(sql_insert, sql_data)
        con.commit()
        con.close()

    def addSingleTag(self, tag):
        con = self.obtener_conexion()
        cObj = con.cursor()
        sql_insert = """INSERT INTO Tags(tag) VALUES (?)"""
        sql_data = tag
        cObj.execute(sql_insert, sql_data)
        con.commit()
        con.close()

    def getMediaDBList(self):
        MediaDBList = []
        con = self.obtener_conexion()
        cObj = con.cursor()
        sql = """SELECT * FROM peliculas"""
        cObj.execute(
            sql,
        )
        films = cObj.fetchall()
        for film in films:
            tagsPerUser = {}

            # Obtenemos el nombre de la pelicula
            media_Id = film[0]
            name = film[1]
            # Ahora sacamos los usuarios de esa película
            sql = """SELECT DISTINCT ID_Usuario FROM relacciones WHERE ID_Pelicula=?"""
            cObj.execute(sql, (media_Id,))
            users = cObj.fetchall()
            for user in users:
                tagsList = []
                # Cuando tengamos un usuario, miramos los tags que tiene
                sql = """SELECT Tag FROM relacciones WHERE ID_Pelicula=? AND ID_Usuario=?"""
                sql_data = (media_Id, user[0])
                cObj.execute(sql, sql_data)
                tags = cObj.fetchall()
                for tag in tags:
                    tagsList.append(tag[0])

                # add user with his tags
                user_name = self.getUserbyId(user[0])
                tagsPerUser[user_name] = tagsList

            # insertamos un MediaDB object en MediaDBList
            MediaDBList.append(IceFlix.MediaDB(media_Id, name, tagsPerUser))

        return MediaDBList

    def getUserbyId(self, user_id):
        con = self.obtener_conexion()
        cObj = con.cursor()
        sql = """SELECT Nombre FROM usuarios WHERE ID=?"""
        cObj.execute(sql, (user_id,))
        name = cObj.fetchone()[0]
        con.close()
        return name


class catalog_service(Ice.Application):
    """Implementacion del servidor."""

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

    def run(self, args):
        """Método principal para la ejecución del servidor."""
        print(f"Inicializando MediaCatalog...")

        broker = self.communicator()
        adapter_media_catalog = broker.createObjectAdapter("MediaCatalogAdapter")
        adapter_service_announcements = broker.createObjectAdapter(
            "ServiceAnnouncementsAdapter"
        )
        adapter_media_catalog.activate()

        # Suscripcion a ServiceAnnouncement
        topic_stream_b = get_topic(get_topic_manager(broker), "ServiceAnnouncements")
        servant_announcement = ServiceAnnouncementsI()
        sirviente_media_catalog = MediaCatalogI(servant_announcement, broker)
        subscriber_media_catalog = adapter_media_catalog.addWithUUID(
            sirviente_media_catalog
        )
        subscriber = adapter_service_announcements.addWithUUID(servant_announcement)
        ### MediaCatalog se suscribe al canal ServiceAnnouncments()
        topic_stream_b.subscribeAndGetPublisher({}, subscriber)

        ### MediaCatalog puede publicar en el canal ServiceAnnouncemts()
        publisher = topic_stream_b.getPublisher()
        publicador = IceFlix.ServiceAnnouncementsPrx.uncheckedCast(publisher)
        try:
            threading.Thread(
                target=self.iniciar_announcements,
                args=(
                    publicador,
                    subscriber_media_catalog,
                    sirviente_media_catalog.srvId,
                ),
            ).start()
        except Exception as e:
            print(e)

        adapter_service_announcements.activate()

        self.shutdownOnInterrupt()
        self.communicator().waitForShutdown()

        return EXIT_OK


if __name__ == "__main__":
    # Entry point
    sys.exit(catalog_service().main(sys.argv))
