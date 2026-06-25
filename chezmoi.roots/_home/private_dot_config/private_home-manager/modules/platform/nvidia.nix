{ config, lib, ... }:

let
  cfg = config.sz.platform.nvidia;
in
{
  options.sz.platform.nvidia.enable = lib.mkEnableOption "NVIDIA driver via genericLinux target";

  config = lib.mkIf cfg.enable {
    targets.genericLinux.gpu.nvidia = {
      enable = true;
      version = "595.71.05";
      sha256 = "sha256-NiA7iWC35JyKQva6H1hjzeNKBek9KyS3mK8G3YRva4I=";
    };
  };
}
