{ config, pkgs, lib, ... }:

let
  cfg = config.services.browsers;

  zenLinuxEntry = ''

[[apps]]
id = "zen-beta"
config_dir_relative = ".config/zen"
kind = "FIREFOX"
os = "LINUX"
'';

  browsersPkg = pkgs.browsers.overrideAttrs (old: {
    postInstall =
      (old.postInstall or "")
      + ''
        echo -n '${zenLinuxEntry}' >> $out/resources/repository/application-repository.toml
      '';
  });
in
{
  options.services.browsers = {
    enable = lib.mkEnableOption "Browsers link handler (browsers.software)";

    defaultUrlHandler = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = ''
        Register Browsers as the default handler for http and https URLs
        via xdg.mimeApps.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = [ browsersPkg ];

    xdg.mimeApps = lib.mkIf cfg.defaultUrlHandler {
      enable = true;
      defaultApplications = {
        "x-scheme-handler/http" = "software.Browsers.desktop";
        "x-scheme-handler/https" = "software.Browsers.desktop";
      };
    };
  };
}
