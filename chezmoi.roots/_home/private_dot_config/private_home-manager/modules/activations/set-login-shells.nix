{ config, pkgs, lib, ... }:

let
  cfgUser = config.sz.activations.setUserShell;
  cfgRoot = config.sz.activations.setRootShell;
  cfg = cfgUser.enable || cfgRoot.enable;

  sudoHint = "Re-run with: SUDO=sudo home-manager switch --flake .#sz";

  userShellScript =
    let
      username = config.home.username;
    in
    ''
      user_shell=$("$getent" passwd "${username}" | cut -d: -f7)
      if [ "$user_shell" != "$zsh_bin" ] && [ -x "$zsh_bin" ]; then
        if ! grep -Fxq "$zsh_bin" /etc/shells 2>/dev/null; then
          if [ -z "''${SUDO:-}" ]; then
            echo "user login shell needs updating (${username} -> zsh)."
            echo "${sudoHint}"
          else
            echo "$zsh_bin" | $DRY_RUN_CMD "$SUDO" tee -a /etc/shells >/dev/null
          fi
        fi
        if grep -Fxq "$zsh_bin" /etc/shells 2>/dev/null; then
          $DRY_RUN_CMD "$chsh" -s "$zsh_bin" "${username}" </dev/null 2>/dev/null || true
        fi
      fi
    '';

  rootShellScript = ''
    root_current=$("$getent" passwd root | cut -d: -f7)
    case "$root_current" in
      /bin/sh|/bin/dash) ;;
      *)
        if [ -z "''${SUDO:-}" ]; then
          echo "root login shell needs updating (root -> /bin/sh)."
          echo "${sudoHint}"
        else
          $DRY_RUN_CMD "$SUDO" chsh -s "$root_shell" root </dev/null 2>/dev/null || true
        fi
        ;;
    esac
  '';
in
{
  options.sz.activations.setUserShell.enable = lib.mkEnableOption "set zsh as user login shell";
  options.sz.activations.setRootShell.enable = lib.mkEnableOption "set /bin/sh as root login shell";

  config = lib.mkIf cfg {
    home.activation.setLoginShells = lib.hm.dag.entryAfter [ "installPackages" ] ''
      set +e
      zsh_bin="${pkgs.zsh}/bin/zsh"
      root_shell="/bin/sh"
      getent=/bin/getent
      chsh=/usr/bin/chsh
      ${lib.optionalString cfgUser.enable userShellScript}
      ${lib.optionalString cfgRoot.enable rootShellScript}
      set -e
    '';
  };
}
