"""Доступ к Java API на Android (Chaquopy, не pyjnius)."""
from __future__ import annotations


def app_context():
    from com.chaquo.python import Python

    return Python.getPlatform().getApplication()


def tgonpc_network_helper():
    from org.tgonpc.app import TgonpcNetworkHelper

    return TgonpcNetworkHelper
