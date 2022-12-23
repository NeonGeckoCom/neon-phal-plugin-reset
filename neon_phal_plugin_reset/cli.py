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

import click
import requests
from click_default_group import DefaultGroup


@click.group("neon_reset", cls=DefaultGroup,
             no_args_is_help=True, invoke_without_command=True,
             help="Neon Core Commands\n\n"
                  "See also: neon COMMAND --help")
def neon_reset_cli():
    pass


@neon_reset_cli.command(help="Configure Reset Service")
def configure_reset():
    from os import remove
    from os.path import isfile, expanduser
    from subprocess import run
    if isfile("/usr/lib/systemd/system/neon-reset.service"):
        click.echo("Reset service already enabled")
        exit(0)
    script = requests.get('https://raw.githubusercontent.com/NeonGeckoCom/'
                          'neon-image-recipe/FEAT_FactoryReset/patches/'
                          'add_reset_service.sh').text
    script_path = expanduser('~/.cache/add_reset_service.sh')
    with open(script_path, 'w+') as f:
        f.write(script)
    run(['/bin/bash', script_path])
    remove(script_path)
    click.echo("Reset service configured")
