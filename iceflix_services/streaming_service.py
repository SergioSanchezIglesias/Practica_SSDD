#!/usr/bin/python3
# -*- coding: utf-8 -*-

import glob
import hashlib
from pathlib import Path
import os
import random
import secrets
import string
import sys
import threading
import hashlib
import time
import uuid
import Ice
import IceStorm

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

EXIT_OK = 0
CHUNK_SIZE = 4096
NAME_CHANNEL_SIZE = 40
DEFAULT_TOPICMANAGER_PROXY = "IceStorm/TopicManager:tcp -p 10000"


class Media:
    def __init__(self, mediaId, initialName):
        self.mediaId = mediaId
        self.initialName = initialName


class ServiceAnnouncementsI(IceFlix.ServiceAnnouncements):
    """Canal de eventos de todos los microservicios para todos los microservicios."""

    def __init__(self):
        """Inicialización de objetos con listas vacías."""
        self._id_ = str(uuid.uuid4())
        self.authenticators = {}
        self.mediaCatalogs = {}
        self.main_services = {}
        self.streamings = {}

    @property
    def known_services(self):
        """Método que permite obtener los srv de los servicios Auth y MediaCatalog."""
        return (
            list(self.authenticators.keys())
            + list(self.mediaCatalogs.keys())
            + list(self.main_services.keys())
            + list(self.streamings.keys())
        )

    @property
    def service_id(self):
        """Obtener instancia ID."""
        return self._id_

    def newService(
        self, service, srvId, current=None
    ) -> None:  # pylint: disable=invalid-name,unused-argument
        """Emitido al inicio del servidor, antes de que este listo para atender al Cliente."""
        print(f"SreamingService envía newService {srvId}")
        sys.stdout.flush()

    def announce(self, service, srvId, current=None) -> None:
        """Método que compruba el tipo de servicio."""
        """Emitido cuando el servidor comienza a estar disponible."""

        if srvId in self.known_services:
            return
        if service.ice_isA("::IceFlix::Authenticator"):
            self.authenticators[srvId] = IceFlix.AuthenticatorPrx.uncheckedCast(service)
        elif service.ice_isA("::IceFlix::MediaCatalog"):
            self.mediaCatalogs[srvId] = IceFlix.MediaCatalogPrx.uncheckedCast(service)
        elif service.ice_isA("::IceFlix::Main"):
            self.main_services[srvId] = IceFlix.MainPrx.uncheckedCast(service)
        elif service.ice_isA("::IceFlix::StreamProvider"):
            self.streamings[srvId] = IceFlix.StreamProviderPrx.uncheckedCast(service)


class StreamControllerI(IceFlix.StreamController):
    """Maneja los flujos de media."""

    def __init__(self):
        self._proc_ = None

    def getSDP(
        self, userToken, port, current=None
    ):  # pylint: disable=invalid-name,unused-argument
        return None

    def getSyncTopic(self, current=None):
        """Método que permite generar un nombre aleatorio para un canal de eventos."""

        return "".join(
            secrets.choice(string.ascii_letters) for i in range(NAME_CHANNEL_SIZE)
        ).upper()

    def refreshAuthentication(
        self, userToken, current=None
    ):  # pylint: disable=invalid-name,unused-argument
        return None

    def stop(self, current=None):
        """Parar el flujo."""
        self._proc_.terminate()


class StreamSyncI(IceFlix.StreamSync):
    """Canal de Eventos para las notificaciones de StreamController() al cliente."""

    def requestAuthentication(
        self, current=None
    ):  # pylint: disable=invalid-name,unused-argument
        return None


class StreamProviderI(IceFlix.StreamProvider):
    """Maneja el almacenamiento de media."""

    def __init__(self, broker, service_announcements, publicador_Stream_Announcement):
        """Inicializador del Stream Provider."""
        self.broker = broker
        self.publicador_Stream_Announcement = publicador_Stream_Announcement
        self.srvId = str(uuid.uuid4())
        self._folder_videos = self.broker.getProperties().getProperty(
            "DirectorioVideos"
        )

        self._lista_videos = self.obtener_directorio_videos(self.broker)
        self._service_announcements_ = service_announcements

        self._lista_Media = self.analizar_media(
            self._lista_videos
        )  # Lista donde se alamcenan objetos de tipo Media
        self._lista_Id_Media = []

        for media in self._lista_Media:

            self.publicador_Stream_Announcement.newMedia(
                media.mediaId, media.initialName, self.srvId
            )
            self._lista_Id_Media.append(media.mediaId)

    def analizar_media(self, lista_videos):
        """Analizamos los archivos para obtener sus datos."""
        lista_objetos_media = []

        for media in lista_videos:
            hash = self.calcular_hash(media)

            objectMedia = Media(hash, media[2:])
            lista_objetos_media.append(objectMedia)
        return lista_objetos_media

    def calcular_hash(self, media):
        with open("resources/" + media, "rb") as f:
            file_hash = hashlib.sha256()
            while chunk := f.read(8192):
                file_hash.update(chunk)

        return file_hash.hexdigest()

    def getUploader(self, filename):
        sirviente = MediaUploaderI(filename)
        adapter_uploader = self.broker.createObjectAdapter("UploaderAdapter")
        adapter_uploader.activate()

        subscriber = adapter_uploader.addWithUUID(sirviente)
        return subscriber

    def inicializar_ID_media(self, nueva_lista):
        """Incializa la lista con los IDs del objeto media."""

        for i in range(len(nueva_lista)):
            self._lista_id_media[i] = nueva_lista[i].mediaId

    def obtener_directorio_videos(self, broker):
        """Permite obtener una lista con los archivos en un directorio."""

        file_set = set()
        folder_videos = broker.getProperties().getProperty("FolderVideosDirectorio")
        for dir_, _, files in os.walk(folder_videos):
            for file_name in files:
                rel_dir = os.path.relpath(dir_, folder_videos)
                rel_file = os.path.join(rel_dir, file_name)
                file_set.add(rel_file)

        return list(file_set)

    def obtener_clave_valor(self, service_dictionary, item):
        """Método para obtener la clave para eliminar un servicio no válido."""
        dictionary = service_dictionary
        buscar_valor = item
        for clave, valor in dictionary.items():
            if valor == buscar_valor:
                index = clave
        return index

    def obtener_main(self):
        """Devulve el proxy al servicio de main configurado."""

        while True:
            if not list(self._service_announcements_.main_services):
                raise IceFlix.TemporaryUnavailable()
            main_item = random.choice(
                list(self._service_announcements_.main_services.values())
            )
            try:
                main_item.ice_ping()
            except:
                print("Entra")
                clave = self.obtener_clave_valor(
                    self._service_announcements_.main_services, main_item
                )
                self._service_announcements_.main_services.pop(clave)

            return main_item

    def getStream(self, mediaId, userToken, current=None):
        """Factoría de objetos StreamProvider."""

        auth_item = self.obtener_main().getAuthenticator()

        if auth_item.isAuthorized(userToken):
            while True:
                if self.isAvailable(mediaId):
                    raise IceFlix.WrongMediaId(mediaId)
                else:
                    stream_controller = StreamControllerI()
                    proxy_stream_controller = current.adapter.addWithUUID(
                        stream_controller
                    )
                    return IceFlix.StreamControllerPrx.uncheckedCast(
                        proxy_stream_controller
                    )
        else:
            raise IceFlix.Unauthorized()

    def isAvailable(self, mediaId, current=None) -> bool:
        """Compara el mediaId"""
        for id_media in self._lista_Id_Media:
            if mediaId == id_media:
                return True

    def reannounceMedia(self, srvId, current=None):
        lista_Media = self.analizar_media(self._lista_videos)
        for media in lista_Media:
            self.publicador_Stream_Announcement.newMedia(
                media.mediaId, media.initialName, self.srvId
            )

    ### Subir archivos de medio y retornar ID media

    def uploadMedia(self, filename, uploader, adminToken, current=None):
        """Método que permite subir elementos de tipo media."""

        candidates = glob.glob(os.path.join(self._folder_videos, "*"), recursive=True)
        prefix_len = len(self._folder_videos) + 1
        self._files = [filename[prefix_len:] for filename in candidates]

        destination_filename = "resources/" + str(filename)

        # main_item = self.obtener_main()

        # if main_item.isAdmin(adminToken):

        if filename not in self._files:
            print("Archivo no encontrados.")
            return EXIT_OK
        else:
            try:
                with open(destination_filename, "wb") as out:
                    count = 0
                    filesize = Path("directorio_videos/" + filename).stat().st_size
                    while True:
                        chunk = uploader.receive(CHUNK_SIZE)
                        if not chunk:
                            break

                        out.write(chunk)
                        count += len(chunk)
                        print(f"Subiendo archivo... {count}/{filesize}")

                uploader.close()

                with open("resources/" + filename, "rb") as f:
                    file_hash = hashlib.sha256()
                    while chunk := f.read(8192):
                        file_hash.update(chunk)

                self.publicador_Stream_Announcement.newMedia(
                    str(file_hash.hexdigest()), str(filename), str(self.srvId)
                )
                dev = "Video subido correctamente"
                return dev
            except:
                raise IceFlix.UploadError()
        # else:
        #     raise IceFlix.Unauthorized()

    def deleteMedia(self, mediaId, adminToken, current=None):
        """Método que permite eleminar un elemento de tipo media."""

        # main_item = self.obtener_main()

        # if main_item.isAdmin(adminToken):
        if self.isAvailable(mediaId):

            for dir_, _, files in os.walk("resources"):
                for file_name in files:
                    rel_dir = os.path.relpath(dir_, "resources")
                    rel_file = os.path.join(rel_dir, file_name)
                    hashFile = self.calcular_hash(rel_file)
                    if hashFile == mediaId:
                        os.remove("resources/" + rel_file[2:])
                        self.publicador_Stream_Announcement.removedMedia(
                            str(hashFile), str(self.srvId)
                        )

        else:
            raise IceFlix.WrongMediaId(mediaId)
        # else:
        #     raise IceFlix.Unauthorized()


class streaming_service(Ice.Application):
    """Implementación del servidor."""

    def get_topic_manager(self):
        key = "IceStorm.TopicManager.Proxy"
        proxy = self.communicator().propertyToProxy(key)
        if proxy is None:
            print("property '{}' not set".format(key))
            return None

        print("Using IceStorm in: '%s'" % key)
        return IceStorm.TopicManagerPrx.checkedCast(proxy)

    def inicio(self, publicador, service, srvId):
        publicador.newService(service, str(srvId))
        time.sleep(5)

        list_Sec = [0, 1, 2]

        while True:
            publicador.announce(service, str(srvId))
            d = random.choice(list_Sec)
            time_Sleep = 10 + d
            time.sleep(time_Sleep)

    def run(self, argv):
        """Método principal para la ejecución del servidor."""
        print(f"Inicializando StreamingService...")

        topic_mgr = self.get_topic_manager()
        if not topic_mgr:
            print("Invalid proxy")
            return 2

        ic = self.communicator()

        adapter_Provider = ic.createObjectAdapter("StreamingProviderAdapter")
        adapter_Provider.activate()

        ### StreamAnnouncement
        topic_Name_Stream_Announcement = "StreamAnnouncements"
        try:
            topic_Stream_Announcement = topic_mgr.retrieve(
                topic_Name_Stream_Announcement
            )
        except IceStorm.NoSuchTopic:
            print("no such topic found, creating")
            topic_Stream_Announcement = topic_mgr.create(topic_Name_Stream_Announcement)

        publisher_Stream_Announcement = topic_Stream_Announcement.getPublisher()
        publicador_Stream_Announcement = IceFlix.StreamAnnouncementsPrx.uncheckedCast(
            publisher_Stream_Announcement
        )

        # Announcements
        servant_service_announcement = ServiceAnnouncementsI()
        sirviente_Provider = StreamProviderI(
            ic, servant_service_announcement, publicador_Stream_Announcement
        )
        subscriber_Provider = adapter_Provider.addWithUUID(sirviente_Provider)
        # sirviente_Provider.srvId = subscriber_Provider

        adapter_Service_Announcement = ic.createObjectAdapter(
            "ServiceAnnouncementsAdapter"
        )

        subscriber_announcement = adapter_Service_Announcement.addWithUUID(
            servant_service_announcement
        )

        topic_announcement = "ServiceAnnouncements"
        qos = {}
        try:
            topic_service_announcement = topic_mgr.retrieve(topic_announcement)
        except IceStorm.NoSuchTopic:
            topic_service_announcement = topic_mgr.create(topic_announcement)

        topic_service_announcement.subscribeAndGetPublisher(
            qos, subscriber_announcement
        )

        publisher_announcement = topic_service_announcement.getPublisher()
        publicador_announcement = IceFlix.ServiceAnnouncementsPrx.uncheckedCast(
            publisher_announcement
        )
        try:
            threading.Thread(
                target=self.inicio,
                args=(
                    publicador_announcement,
                    subscriber_Provider,
                    sirviente_Provider.srvId,
                ),
            ).start()
        except Exception as e:
            print(e)

        self.shutdownOnInterrupt()
        ic.waitForShutdown()

        return EXIT_OK


if __name__ == "__main__":
    # Entry point
    sys.exit(streaming_service().main(sys.argv))
