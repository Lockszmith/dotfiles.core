{ lib }:

{
  stripPackageDesktopEntries =
    pkg: basenames:
    if basenames == [ ] then
      pkg
    else
      pkg.overrideAttrs (oldAttrs: {
        postInstall =
          (oldAttrs.postInstall or "")
          + lib.concatMapStringsSep "\n" (basename: ''
            rm -f "$out/share/applications/${basename}"
          '') basenames;
      });
}
