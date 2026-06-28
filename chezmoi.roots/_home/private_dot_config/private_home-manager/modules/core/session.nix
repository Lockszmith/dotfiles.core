{ config, pkgs, ... }:

{
  home.file = {
    "bin/hm-setup-system".text = ''
      #!${pkgs.bash}/bin/bash
      # One-time privileged HM switch (login shells, nix trusted-user, vendor RPMs).
      # Routine rebuilds: use hms / home-manager switch — no SUDO.
      exec env SUDO=$(command -pv sudo) home-manager switch --flake ${config.home.homeDirectory}/.config/home-manager#${config.home.username}
    '';
    "bin/hm-setup-system".executable = true;
  };

  home.sessionPath = [
    "$HOME/bin"
  ];

  home.sessionVariables = {
    EDITOR = /usr/bin/vi;
    SZ_WAS_HERE = 1;
  };
}
