{ config, pkgs, ... }:

{
  home.file = {
    "bin/hm-setup-shells".text = ''
      #!${pkgs.bash}/bin/bash
      exec env SUDO=sudo home-manager switch --flake ${config.home.homeDirectory}/.config/home-manager#${config.home.username}
    '';
    "bin/hm-setup-shells".executable = true;
  };

  home.sessionPath = [
    "$HOME/bin"
  ];

  home.sessionVariables = {
    EDITOR = /usr/bin/vi;
    SZ_WAS_HERE = 1;
  };
}
