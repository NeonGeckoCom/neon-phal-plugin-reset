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
from tempfile import mkstemp

import psutil

from subprocess import run, PIPE, Popen
from os import close
from os.path import exists
from typing import List, Optional

import requests
from ovos_utils.log import LOG


def get_drive_mountpoints(drive: str = "/dev/sdb") -> List[str]:
    """
    Get a list of all mountpoints associated with a disk device.
    """
    parts = psutil.disk_partitions(all=False)
    valid_parts = [part for part in parts
                   if part.device.startswith(drive)]
    LOG.debug(valid_parts)
    return [part.mountpoint for part in valid_parts]


def prep_drive_for_write(drive: str = "/dev/sdb") -> bool:
    if not exists(drive):
        LOG.warning(f"Drive doesn't exist: {drive}")
        return False

    for mp in get_drive_mountpoints(drive):
        run(["/usr/bin/umount", mp])
    return True


def write_xz_image_to_drive(image_path: str, drive: str = "/dev/sdb"):
    """
    Write an image to a USB drive
    """
    image_data = Popen(["/usr/bin/xzcat", image_path], stdout=PIPE)
    run(["/usr/bin/dd", f"of={drive}"], stdin=image_data.stdout)
    LOG.info("Drive creation completed")


def download_image(image_url: str = None,
                   cache_file: str = None) -> Optional[str]:
    """
    Download an image file from the specified URL. This streams the download to
    an output file for use on low-memory systems
    """
    image_url = image_url or "https://2222.us/app/files/neon_images/pi/" \
                             "mycroft_mark_2/recommended_mark_2.img.xz"
    if not cache_file:
        fp, cache_file = mkstemp()
        close(fp)
    LOG.debug(f"Downloading {image_url} to {cache_file}")
    try:
        with requests.get(image_url, stream=True) as stream:
            with open(cache_file, 'wb') as f:
                for chunk in stream.iter_content(4096):
                    if chunk:
                        f.write(chunk)
    except Exception as e:
        LOG.exception(e)
        return None
    LOG.debug(f"Download Complete")
    return cache_file
