# NEON AI (TM) SOFTWARE, Software Development Kit & Application Framework
# All trademark and other rights reserved by their respective owners
# Copyright 2008-2022 Neongecko.com Inc.
# Contributors: Daniel McKnight, Guy Daniels, Elon Gasper, Richard Leeds,
# Regina Bloomstine, Casimiro Ferreira, Andrii Pernatii, Kirill Hrymailo
# BSD-3 License
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from this
#    software without specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS  BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS;  OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE,  EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from subprocess import Popen
from os import remove
from os.path import isfile
from threading import RLock
from mycroft_bus_client import Message
from ovos_utils.log import LOG
from ovos_plugin_manager.phal import PHALPlugin


class DeviceReset(PHALPlugin):
    def __init__(self, bus=None, name="neon-phal-plugin-reset",
                 config=None):
        PHALPlugin.__init__(self, bus, name, config)
        self.reset_compete = False
        self.reset_lock = RLock()
        self.username = self.config.get('username') or 'neon'
        self.reset_command = self.config.get('reset_command',
                                             "systemctl start neon-reset")
        self.bus.on("system.factory.reset.start", self.handle_factory_reset)
        self.bus.on("system.factory.reset.ping",
                    self.handle_register_factory_reset_handler)
        self.bus.on('system.factory.reset.phal', self.check_complete)

        # TODO: Add option to reset to latest config

        # In case this plugin starts after system plugin, emit registration
        self.bus.emit(Message("system.factory.reset.register",
                              {"skill_id": self.name}))

    def handle_register_factory_reset_handler(self, message):
        LOG.debug("Got factory reset registration request")
        self.bus.emit(message.reply("system.factory.reset.register",
                                    {"skill_id": self.name}))

    def check_complete(self, message):
        if self.reset_compete:
            LOG.debug("Notify reset is complete")
            completed_message = message.forward(
                "system.factory.reset.phal.complete", {"skill_id": self.name})
            self.bus.emit(completed_message)

    def handle_factory_reset(self, message):
        """
        Handle a `system.factory.reset.start` request. This should put Neon in
        the state it was in when this plugin was installed.
        """
        LOG.info("Handling factory reset request")
        if self.reset_lock.acquire(timeout=1):
            self.reset_compete = False
            if message.data.get('wipe_configs', True):
                LOG.debug(f"Removing user configuration")
                config_files = (
                    f'/home/{self.username}/.config/neon/ngi_user_info.yml',
                    f'/home/{self.username}/.config/neon/.ngi_user_info.tmp'
                )
                try:
                    for file in config_files:
                        if isfile(file):
                            remove(file)
                except Exception as e:
                    LOG.exception(e)

            if self.reset_command:
                LOG.info(f"Calling {self.reset_command}")
                Popen(self.reset_command, shell=True, start_new_session=True)
            self.reset_compete = True
            LOG.debug("Notify reset is complete")
            self.bus.emit(message.forward(
                "system.factory.reset.phal.complete", {"skill_id": self.name}))
            self.reset_lock.release()
        else:
            LOG.warning(f"Requested reset but a reset is in progress")
