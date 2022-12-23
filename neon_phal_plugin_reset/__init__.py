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

import subprocess

from os import remove
from os.path import isdir, isfile
from shutil import copytree, rmtree
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
        LOG.info("Handling factory reset request")
        if self.reset_lock.acquire(timeout=1):
            self.reset_compete = False
            # LOG.debug("Stopping skills service")
            # subprocess.run("systemctl stop neon-skills", timeout=30)
            if message.data.get('wipe_configs', True):
                LOG.debug(f"Removing user configuration")
                try:
                    for file in (f'/home/{self.username}/.config/neon/ngi_user_info.yml',
                                 f'/home/{self.username}/.config/neon/.ngi_user_info.tmp'):
                        if isfile(file):
                            remove(file)
                except Exception as e:
                    LOG.exception(e)
            if isdir('/opt/neon/default_config'):
                LOG.info("Restoring default ~/.config from /opt/neon/default_config")
                rmtree(f"/home/{self.username}/.config")
                copytree("/opt/neon/default_config",
                         f"/home/{self.username}/.config")
            else:
                LOG.info("Loading default config from git")
                try:
                    subprocess.run([
                        "/usr/bin/git", "clone",
                        "https://github.com/neongeckocom/neon-image-recipe",
                        "/opt/neon/neon-image-recipe"], check=True)
                    LOG.debug(f"Cloned image repo")
                    rmtree(f"/home/{self.username}/.config/neon")
                    copytree(f"/opt/neon/neon-image-recipe/05_neon_core/"
                             f"overlay/home/neon/.config/neon",
                             f"/home/{self.username}/.config/neon")
                    LOG.debug("Restored default config")
                    rmtree("/opt/neon/neon-image-recipe")
                except Exception as e:
                    LOG.exception(e)
            subprocess.run(["chown", "-R", f"{self.username}:{self.username}",
                            f"/home/{self.username}"])
            if self.reset_command:
                LOG.info(f"Calling {self.reset_command}")
                subprocess.Popen(self.reset_command)
            self.reset_compete = True
            LOG.debug("Notify reset is complete")
            self.bus.emit(message.forward(
                "system.factory.reset.phal.complete", {"skill_id": self.name}))
            self.reset_lock.release()
        else:
            LOG.warning(f"Requested reset but a reset is in progress")
