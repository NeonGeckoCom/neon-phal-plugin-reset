# NEON AI (TM) SOFTWARE, Software Development Kit & Application Framework
# All trademark and other rights reserved by their respective owners
# Copyright 2008-2025 Neongecko.com Inc.
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

from time import sleep
import unittest
import neon_utils
import os.path
import shutil

from unittest.mock import patch, MagicMock
from ovos_bus_client import Message

import neon_phal_plugin_reset.create_media
from neon_phal_plugin_reset import DeviceReset


class TestDeviceReset(unittest.TestCase):
    def setUp(self):
        self.bus = MagicMock()
        self.config = {
            "username": "test_user",
            "reset_command": "test_command",
            "default_image_url": "https://download.neonaiservices.com/neon_os/recommended/mark_2.img.xz",
            "default_config_url": "https://github.com/NeonGeckoCom/NeonCore/archive/refs/tags/{}.zip",
            "default_config_path": "test_path"
        }
        # Create the plugin instance with our mocked bus and config
        self.plugin = DeviceReset(self.bus, config=self.config)

    def test_init(self):
        # Test that the plugin initializes correctly with the given config
        self.assertEqual(self.plugin.username, "test_user")
        self.assertEqual(self.plugin.reset_command, "test_command")
        self.assertEqual(self.plugin.default_image_url,
                          self.config['default_image_url'])
        self.assertEqual(self.plugin.default_config_url, 
                         self.config['default_config_url'])
        
        # Test that the message handlers are registered
        self.bus.on.assert_any_call("system.factory.reset.ping", 
                                     self.plugin.handle_register_factory_reset_handler)
        self.bus.on.assert_any_call("system.factory.reset.phal",
                                     self.plugin.handle_factory_reset)
        self.bus.on.assert_any_call("neon.update_config",
                                     self.plugin.handle_update_config)
        self.bus.on.assert_any_call("neon.download_os_image",
                                     self.plugin.handle_download_image)
        self.bus.on.assert_any_call("neon.install_os_image",
                                     self.plugin.handle_os_installation)

    def test_handle_register_factory_reset_handler(self):
        # Create a mock message
        message = Message("system.factory.reset.ping")
        
        # Call the handler
        self.plugin.handle_register_factory_reset_handler(message)
        
        # Verify the response was emitted
        self.bus.emit.assert_called_with(message.reply("system.factory.reset.register",
                                                       {"skill_id": self.plugin.name}))

    def test_check_complete(self):
        self.bus.reset_mock()
        # Create a mock message
        message = Message("test.message")
        
        # Test when reset is not complete
        self.plugin.reset_compete = False
        self.plugin.check_complete(message)
        self.bus.emit.assert_not_called()
        
        # Test when reset is complete
        self.plugin.reset_compete = True
        self.plugin.check_complete(message)
        self.bus.emit.assert_called_once()
        args = self.bus.emit.call_args[0][0]
        self.assertEqual(args.msg_type, "system.factory.reset.phal.complete")
        self.assertEqual(args.data.get("skill_id"), self.plugin.name)

    def test_handle_factory_reset(self):
        # TODO
        pass

    @patch('neon_phal_plugin_reset.create_media.download_image')
    @patch('os.path.isfile')
    def test_handle_download_image(self, mock_isfile, mock_download_image):
        self.bus.reset_mock()

        # Test when file already exists in cache
        mock_isfile.return_value = True
        message = Message("neon.download_os_image")
        
        self.plugin.handle_download_image(message)
        self.bus.emit.assert_called_once()
        args = self.bus.emit.call_args[0][0]
        self.assertEqual(args.msg_type, "neon.download_os_image.complete")
        self.assertTrue(args.data.get("success"), 
                        f"Response indicates failure: {args}")
        self.assertIsInstance(args.data.get("from_cache"), bool)
        
        # Reset mocks
        self.bus.emit.reset_mock()
        
        # Test successful download
        mock_isfile.return_value = False
        mock_download_image.return_value = "/tmp/downloaded_image.img.xz"
        
        self.plugin.handle_download_image(message)
        self.bus.emit.assert_called_once()
        args = self.bus.emit.call_args[0][0]
        self.assertEqual(args.msg_type, "neon.download_os_image.complete")
        self.assertTrue(args.data.get("success"),
                        f"Response indicates failure: {args}")
        self.assertFalse(args.data.get("from_cache"))

    @patch('neon_phal_plugin_reset.create_media.prep_drive_for_write')
    @patch('neon_phal_plugin_reset.create_media.write_xz_image_to_drive')
    @patch('os.path.isfile')
    def test_handle_os_installation(self, mock_isfile, mock_write, mock_prep):
        # Test with invalid device
        mock_prep.return_value = False
        message = Message("neon.install_os_image", {
            "device": "/dev/sda",
            "image_file": "/tmp/test.img.xz"
        })
        
        self.plugin.handle_os_installation(message)
        args = self.bus.emit.call_args[0][0]
        self.assertEqual(args.msg_type, "neon.install_os_image.complete")
        self.assertFalse(args.data.get("success"))
        self.assertEqual(args.data.get("error"), "no_valid_device")
        
        # Reset mocks
        self.bus.emit.reset_mock()
        
        # Test with invalid file
        mock_prep.return_value = True
        mock_isfile.return_value = False
        
        self.plugin.handle_os_installation(message)
        args = self.bus.emit.call_args[0][0]
        self.assertFalse(args.data.get("success"))
        self.assertEqual(args.data.get("error"), "no_image_file")
        
        # Reset mocks
        self.bus.emit.reset_mock()
        
        # TODO: Test successful installation
        # mock_isfile.return_value = True
        
        # self.plugin.handle_os_installation(message)
        # args = self.bus.emit.call_args[0][0]
        # self.assertEqual(args.msg_type, "neon.install_os_image.complete")
        # self.assertTrue(args.data.get("success"))
        # mock_write.assert_called_once_with("/tmp/test.img.xz", "/dev/sda")

    @patch('neon_utils.packaging_utils.get_package_version_spec')
    @patch('ovos_skill_installer.download_extract_zip')
    @patch('shutil.copytree')
    @patch('shutil.copyfile')
    @patch('os.path.isdir')
    @patch('shutil.rmtree')
    def test_handle_update_config(self, mock_rmtree, mock_isdir, mock_copyfile, 
                                 mock_copytree, mock_download, mock_version):
        self.bus.reset_mock()
        # Setup
        mock_version.return_value = "24.5.1"
        mock_isdir.return_value = True
        message = Message("neon.update_config", {"skill_config": False,
                                                 "restart": True})
        
        # Call handler
        self.plugin.handle_update_config(message)
        
        # Verify correct version used, files copied, and restart message sent
        # mock_download.assert_called_once()
        # mock_copytree.assert_called()
        sleep(1)
        self.bus.emit.assert_called_once()
        args = self.bus.emit.call_args[0][0]
        self.assertEqual(args.msg_type, "system.mycroft.service.restart")


if __name__ == "__main__":
    unittest.main()
