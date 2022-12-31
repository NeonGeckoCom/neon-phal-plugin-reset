# Neon Reset Plugin
Plugin to handle factory reset requests. Note that this plugin will install system
services and modify system config as part of its installation. Installation may
fail if not completed as `root`.

## Default Reset Behavior
By default, the reset plugin will reset your Python environment to the state it
was in when this plugin was installed. It will also restore the user `.local`, 
`.cache`, and `.config` directories to the state their original state.
`/etc/neon/neon.yaml` will be updated to the latest default if an internet connection
is available. The reset script comes from the 
[neon-image-recipe repository](https://github.com/NeonGeckoCom/neon-image-recipe/blob/master/11_factory_reset/overlay/opt/neon/reset).