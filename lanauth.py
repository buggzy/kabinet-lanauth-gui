#!/usr/bin/python
# coding=utf-8

import gi
import signal
import os
import time
import subprocess
import select
import socket
import hashlib
import random

gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')

from gi.repository import Gtk
from gi.repository import AppIndicator3 as appindicator

GATEWAY_IP = '10.0.0.1'
GATEWAY_PORT = 8314
PASSWORD = '001319'
AUTH_LEVEL = 2

STATUS_CONNECTING = 1
STATUS_CONNECTED = 2
STATUS_DISCONNECTED = 3

STATUS_PROTOCOL_CONNECT = 1
STATUS_PROTOCOL_BEFORE_HANDSHAKE = 2
STATUS_PROTOCOL_HANDSHAKE = 3
STATUS_PROTOCOL_DIGEST_SENT = 4

KEEP_ALIVE = 300


class App:

    def build_menu(self):
        menu_items = [
            {'title': 'Включить', 'handle': self.enable},
            {'title': 'Выключить', 'handle': self.disable},
            {'title': 'Выход', 'handle': self.quit}
        ]

        menu = Gtk.Menu()
        for item_data in menu_items:
            item = Gtk.MenuItem(item_data['title'])
            item.connect('activate', item_data['handle'])
            menu.append(item)

        menu.show_all()
        return menu

    def network_routine(self):
        if (self.status == STATUS_CONNECTING) or (self.status == STATUS_CONNECTED):
            if self.socket is None:
                self.protocol_status = STATUS_PROTOCOL_CONNECT
                self.socket_buffer = ''
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    self.socket.connect((GATEWAY_IP, GATEWAY_PORT))

                except:
                    time.sleep(1)
                    self.socket = None
                    self.status = STATUS_CONNECTING

            else:

                poller = select.poll()
                poller.register(self.socket, select.POLLIN | select.POLLOUT | select.POLLERR | select.POLLHUP)
                events = poller.poll(0.1)

                for fd, flag in events:
                    if flag & select.POLLIN:
                        self.socket_buffer = self.socket_buffer + self.socket.recv(10000)

                    if (self.protocol_status == STATUS_PROTOCOL_CONNECT) and (flag & select.POLLOUT):
                        self.protocol_status = STATUS_PROTOCOL_BEFORE_HANDSHAKE

                if (self.protocol_status == STATUS_PROTOCOL_BEFORE_HANDSHAKE) and self.socket_buffer_has(1):
                    resp = ord (self.socket_buffer_get(1))
                    if resp == 1:
                        self.protocol_status = STATUS_PROTOCOL_HANDSHAKE
                    else:
                        self.status = STATUS_DISCONNECTED

                if (self.protocol_status == STATUS_PROTOCOL_HANDSHAKE) and self.socket_buffer_has(256):
                    h = hashlib.new('ripemd160')
                    challenge = self.socket_buffer_get(256)
                    challenge_len = ord(challenge[0])
                    challenge = challenge[1:challenge_len+1]
                    h.update(challenge)
                    h.update(PASSWORD)
                    digest = ''
                    for d in range (0, 254):
                        digest = digest + chr(random.randrange(255))

                    spamlen = 2 + random.randrange(230)
                    digest = chr(AUTH_LEVEL-1) + chr(spamlen) + digest
                    digest_ripe = h.digest()
                    digest = digest[0:spamlen] + digest_ripe + digest[spamlen + len (digest_ripe):]
                    self.socket.send(digest)
                    self.protocol_status = STATUS_PROTOCOL_DIGEST_SENT

                if (self.protocol_status == STATUS_PROTOCOL_DIGEST_SENT) and self.socket_buffer_has(1):
                    level = ord (self.socket_buffer_get(1))
                    self.protocol_status = STATUS_PROTOCOL_HANDSHAKE
                    self.status = STATUS_CONNECTED
                    self.keepalive = time.time()

        if (self.status == STATUS_DISCONNECTED):
            if self.socket is not None:
                self.socket.close()
                self.socket = None

        if (self.status == STATUS_CONNECTED):
            if time.time() - self.keepalive > KEEP_ALIVE:
                self.keepalive = time.time()
                if self.socket is not None:
                    self.socket.close()
                    self.socket = None


    def socket_buffer_has(self, required_length):
        return len (self.socket_buffer) >= required_length

    def socket_buffer_get(self, required_length):
        retval = self.socket_buffer[0:required_length]
        self.socket_buffer = self.socket_buffer[required_length:]
        return retval

    def enable(self, s):
        self.status = STATUS_CONNECTING

    def disable(self, s):
        self.status = STATUS_DISCONNECTED

    def quit(self, s):
        exit()

    def __init__(self):
        realPath = os.path.realpath(__file__)
        dirPath = os.path.dirname(realPath)
        os.chdir(dirPath)

        self.status = STATUS_CONNECTING
        self.protocol_status = None
        self.keepalive = time.time()
        self.icons = {
            STATUS_CONNECTING: os.path.abspath('internet_connecting.png'),
            STATUS_CONNECTED:  os.path.abspath('internet_connected.png'),
            STATUS_DISCONNECTED:  os.path.abspath('internet_disconnected.png')
        }
        self.socket = None
        self.create_indicator()
        self.loop()

    def loop(self):
        while 1:
            self.set_icon()
            self.network_routine()
            while Gtk.events_pending():
                Gtk.main_iteration_do(0)

            time.sleep(0.2)

    def create_indicator(self):
        self.indicator = appindicator.Indicator.new('lanauth_icon', self.icons[self.status], appindicator.IndicatorCategory.SYSTEM_SERVICES)
        self.indicator.set_status(appindicator.IndicatorStatus.ACTIVE)
        self.indicator.set_menu(self.build_menu())


    def set_icon(self):
        self.indicator.set_icon(self.icons[self.status])


App()
