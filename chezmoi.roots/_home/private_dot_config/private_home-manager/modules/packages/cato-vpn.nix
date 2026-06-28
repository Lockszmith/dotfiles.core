{ config, pkgs, lib, ... }:

let
  cfg = config.sz.packages.catoVpn;
  # Official Cato RPM (exception: not packaged via nix; vendor postinst sets up systemd + setgid binaries).
  catoRpmUrl = "https://clients.catonetworks.com/linux/5.7.0.5525/cato-client-install.rpm";
  catoRpmName = "cato_client";
  sudoHint = "Re-run with: ~/bin/hm-setup-system";
in
{
  options.sz.packages.catoVpn.enable = lib.mkEnableOption ''
    Cato Networks VPN client via official vendor RPM (not nixpkgs).

    Installs cato_client RPM, enables cato-client.service, adds you to group cato-client.
    Connect as your user: cato-sdp start --save ~/.config/cato/creds.cfg

    Requires root once: ~/bin/hm-setup-system
    Then log out/in (or: newgrp cato-client).
  '';

  config = lib.mkIf cfg.enable {
    home.activation.catoVpnRpm = lib.hm.dag.entryAfter [ "installPackages" ] ''
      set +e
      user="${config.home.username}"
      getent=/bin/getent
      rpm=${pkgs.rpm}/bin/rpm
      systemctl=${pkgs.systemd}/bin/systemctl

      rpm_ok=false
      if "$rpm" -q ${catoRpmName} >/dev/null 2>&1; then
        rpm_ok=true
      fi

      group_ok=false
      if "$getent" group cato-client >/dev/null 2>&1; then
        members=$("$getent" group cato-client | cut -d: -f4-)
        if echo ",$members," | grep -Fq ",$user,"; then
          group_ok=true
        fi
      fi
      if [ "$group_ok" = false ] \
        && id -nG "$user" | tr ' ' '\n' | grep -Fxq cato-client; then
        group_ok=true
      fi

      service_ok=false
      if "$systemctl" is-enabled --quiet cato-client.service 2>/dev/null; then
        service_ok=true
      fi

      cleanup_ok=true
      if [ -f /etc/systemd/system/cato-client.service ] \
        || [ -f /opt/cato/bin/cato-clientd ] \
        || [ -f /opt/cato/bin/cato-sdp ]; then
        cleanup_ok=false
      fi

      needs_priv=false
      if [ "$rpm_ok" = false ] || [ "$group_ok" = false ] \
        || [ "$service_ok" = false ] || [ "$cleanup_ok" = false ]; then
        needs_priv=true
      fi

      if [ -z "''${SUDO:-}" ]; then
        if [ "$needs_priv" = true ]; then
          if [ "$rpm_ok" = false ]; then
            echo "Cato VPN: RPM not installed (requires root)."
          elif [ "$group_ok" = false ]; then
            echo "Cato VPN: user not in cato-client group (requires root)."
          elif [ "$service_ok" = false ]; then
            echo "Cato VPN: cato-client.service not enabled (requires root)."
          elif [ "$cleanup_ok" = false ]; then
            echo "Cato VPN: stale override files need cleanup (requires root)."
          fi
          echo "${sudoHint}"
        fi
      else
        unit_removed=false
        if [ -f /etc/systemd/system/cato-client.service ]; then
          $DRY_RUN_CMD "$SUDO" rm -f /etc/systemd/system/cato-client.service
          unit_removed=true
        fi
        if [ -f /opt/cato/bin/cato-clientd ]; then
          $DRY_RUN_CMD "$SUDO" rm -f /opt/cato/bin/cato-clientd
        fi
        if [ -f /opt/cato/bin/cato-sdp ]; then
          $DRY_RUN_CMD "$SUDO" rm -f /opt/cato/bin/cato-sdp
        fi

        if ! "$rpm" -q ${catoRpmName} >/dev/null 2>&1; then
          tmp_rpm=$(${pkgs.coreutils}/bin/mktemp)
          if ${pkgs.curl}/bin/curl -fsSL -o "$tmp_rpm" "${catoRpmUrl}"; then
            $DRY_RUN_CMD "$SUDO" "$rpm" -Uvh "$tmp_rpm"
          else
            echo "Cato VPN: failed to download RPM from ${catoRpmUrl}" >&2
            rm -f "$tmp_rpm"
            set -e
            exit 1
          fi
          rm -f "$tmp_rpm"
        fi

        if ! "$getent" group cato-client >/dev/null 2>&1; then
          $DRY_RUN_CMD "$SUDO" groupadd --system cato-client
        fi

        in_group=false
        if "$getent" group cato-client >/dev/null 2>&1; then
          members=$("$getent" group cato-client | cut -d: -f4-)
          if echo ",$members," | grep -Fq ",$user,"; then
            in_group=true
          fi
        fi
        if [ "$in_group" = false ] \
          && id -nG "$user" | tr ' ' '\n' | grep -Fxq cato-client; then
          in_group=true
        fi
        if [ "$in_group" = false ]; then
          $DRY_RUN_CMD "$SUDO" usermod -aG cato-client "$user"
          echo "Added $user to cato-client (log out/in or: newgrp cato-client)."
        fi

        if [ "$unit_removed" = true ]; then
          $DRY_RUN_CMD "$SUDO" "$systemctl" daemon-reload
        fi

        if [ "$service_ok" = false ]; then
          $DRY_RUN_CMD "$SUDO" "$systemctl" enable --now cato-client.service
        fi
      fi

      set -e
    '';
  };
}
