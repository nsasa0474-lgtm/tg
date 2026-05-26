"""Доступ к Java API на Android (Chaquopy, не pyjnius)."""
from __future__ import annotations


def app_context():
    from com.chaquo.python import Python

    return Python.getPlatform().getApplication()


def tunnel_network_helper():
    from org.tgtunnel.app import TunnelNetworkHelper

    return TunnelNetworkHelper
