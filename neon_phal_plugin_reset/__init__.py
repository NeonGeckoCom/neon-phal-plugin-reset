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

from shutil import move, rmtree
from subprocess import Popen
from os import remove
from os.path import isfile, join
from threading import RLock
from mycroft_bus_client import Message
from ovos_utils.log import LOG
from ovos_plugin_manager.phal import PHALPlugin
from ovos_skill_installer import download_extract_zip
from ovos_utils.xdg_utils import xdg_cache_home


class DeviceReset(PHALPlugin):
    def __init__(self, bus=None, name="neon-phal-plugin-reset",
                 config=None):
        PHALPlugin.__init__(self, bus, name, config)
        self.reset_compete = False
        self.reset_lock = RLock()
        self.username = self.config.get('username') or 'neon'
        self.reset_command = self.config.get('reset_command',
                                             "systemctl start neon-reset")
        self.default_image_url = self.config.get("default_image_url") or \
            "https://2222.us/app/files/neon_images/pi/mycroft_mark_2/" \
            "recommended_mark_2.img.xz"

        self.bus.on("system.factory.reset.ping",
                    self.handle_register_factory_reset_handler)
        self.bus.on('system.factory.reset.phal', self.handle_factory_reset)
        self.bus.on("neon.update_config", self.handle_update_config)
        self.bus.on("neon.download_os_image", self.handle_download_image)
        self.bus.on("neon.install_os_image", self.handle_os_installation)

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

    def handle_update_config(self, message):
        """
        Handle a request to update configuration. Optionally restarts core
        services after update to ensure reload of default params
        """
        LOG.info("Getting default config for Neon")
        download_url = "https://github.com/neongeckocom/neon-image-recipe/archive/master.zip"
        LOG.debug(f"Downloading from {download_url}")
        download_extract_zip(download_url, "/tmp/neon/")

        # Contents are now at /tmp/neon/neon-image-recipe
        try:
            if message.data.get('skill_config'):
                LOG.debug("Updating skill config from default")
                Popen(["/usr/bin/cp", "-r",
                       "/tmp/neon/neon-image-recipe-master/05_neon_core"
                       "/overlay/home/neon/.config/neon",
                       "/home/neon/.config/"])
                Popen("chown -R neon:neon /home/neon", shell=True)
            if message.data.get('core_config'):
                LOG.debug("Updating system config from default")
                move("/tmp/neon/neon-image-recipe-master/05_neon_core/overlay"
                     "/etc/neon/neon.yaml", "/etc/neon/neon.yaml")
            LOG.info(f"Restored default configuration")
            rmtree("/tmp/neon/neon-image-recipe-master")
        except Exception as e:
            LOG.exception(e)
        if message.data.get("restart", True):
            self.bus.emit(message.forward("system.mycroft.service.restart"))
        else:
            self.bus.emit(message.response(message.data, message.context))

    def handle_factory_reset(self, message):
        """
        Handle a `system.factory.reset.phal` request.
        """
        LOG.info(f"Handling factory reset request: data={message.data} "
                 f"context={message.context}")
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

    def handle_download_image(self, message: Message):
        """
        Handle a request to download a Neon OS Image
        """
        image_url = message.data.get("url") or self.default_image_url
        filename = image_url.rsplit('/', 1)[1]
        cache_file = join("/home/neon/.cache/neon", filename)
        if isfile(cache_file):
            LOG.debug(f"Already downloaded: {cache_file}")
            self.bus.emit(message.reply("neon.download_os_image.complete",
                                        {"success": True,
                                         "from_cache": True,
                                         "image_file": cache_file}))
            return
        from neon_phal_plugin_reset.create_media import download_image
        image_file = download_image(image_url, cache_file)
        if not image_file:
            LOG.error("Download Failed!")
            self.bus.emit(message.reply("neon.download_os_image.complete",
                                        {"success": False}))
            return

        LOG.info(f"Image cached at: {cache_file}")
        self.bus.emit(message.reply("neon.download_os_image.complete",
                                    {"success": True,
                                     "from_cache": False,
                                     "image_file": cache_file}))

    def handle_os_installation(self, message):
        from neon_phal_plugin_reset.create_media import prep_drive_for_write, \
            write_xz_image_to_drive
        device = message.data.get("device")
        image_file = message.data.get("image_file")
        if not prep_drive_for_write(device):
            LOG.error(f"Invalid device requested: {device}")
            resp = message.reply("neon.install_os_image.complete",
                                 {"success": False,
                                  "device": device,
                                  "image_file": image_file})
        elif not isfile(image_file):
            LOG.error(f"Invalid file requested: {image_file}")
            resp = message.reply("neon.install_os_image.complete",
                                 {"success": False,
                                  "device": device,
                                  "image_file": image_file})
        else:
            try:
                LOG.info(f"Starting write of {image_file} to {device}")
                write_xz_image_to_drive(image_file, device)
                resp = message.reply("neon.install_os_image.complete",
                                     {"success": True,
                                      "device": device,
                                      "image_file": image_file})
                LOG.debug("Image write completed")
            except Exception as e:
                LOG.exception(e)
                resp = message.reply("neon.install_os_image.complete",
                                     {"success": False,
                                      "device": device,
                                      "image_file": image_file})
        self.bus.emit(resp)
