#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Herramientas IceStorm.
"""

import IceStorm

DEFAULT_TOPICMANAGER_PROXY = "IceStorm/TopicManager:tcp -p 10000"

# pylint: disable=no-member
# pylint: disable=W0150


def get_topic_manager(broker, proxy=DEFAULT_TOPICMANAGER_PROXY):
    """Obteber objeto TopicManager."""
    proxy = broker.stringToProxy(proxy)
    topic_manager = IceStorm.TopicManagerPrx.checkedCast(proxy)
    if not topic_manager:
        raise ValueError(f"Proxy {proxy} no válido para TopicManager()")
    return topic_manager


def get_topic(topic_manager, topic):
    """Obtener el Topic de un proxy."""
    try:
        topic = topic_manager.retrieve(topic)
    except IceStorm.NoSuchTopic:
        topic = topic_manager.create(topic)
    finally:
        return topic
