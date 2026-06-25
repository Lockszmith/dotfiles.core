{ lib, ... }:

{
  nixpkgs.config = {
    allowUnfreePredicate = pkg:
      lib.elem (lib.getName pkg) [
        "rambox"
        "slack"
        "cursor"
        "zoom"
        "libsciter"
      ] || lib.hasPrefix "nvidia" (lib.getName pkg);
    nvidia.acceptLicense = true;
  };
}
