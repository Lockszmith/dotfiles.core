{ config, pkgs, lib, ... }:

let
  cfg = config.sz.packages.digikam;
  facesEngineDir = "${config.home.homeDirectory}/.local/share/digikam/facesengine";
  yuNetModel = pkgs.fetchurl {
    url = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx";
    hash = "sha256-jyOD5N08+7RVPqhxgQf8BCMhDclk+fQoBgSATtJVL6Q=";
  };
in
{
  options.sz.packages.digikam.enable = lib.mkEnableOption "digiKam photo manager with Showfoto AI config";

  config = lib.mkIf cfg.enable {
    home.packages = [ pkgs.digikam ];

    xdg.configFile."showfoto_systemrc".text = lib.generators.toINI {
      listsAsDuplicateKeys = true;
    } {
      System = {
        enableAIAutoTools = true;
        enableFaceEngine = true;
        enableAesthetic = true;
        enableAutoTags = true;
        enableDnnOpenCL = false;
        enableOpenCL = false;
        dnnOpenCLTested = false;
        enableHWTConv = true;
        enableHWVideo = true;
        enableLogging = false;
        facesEnginePath = facesEngineDir;
        softwareOpenGL = false;
        videoBackend = "ffmpeg";
        proxyAuth = false;
        proxyPort = 8080;
        proxyType = 0;
        proxyUrl = "";
      };
    };

    xdg.dataFile."digikam/facesengine/face_detection_yunet_2023mar.onnx".source = yuNetModel;
  };
}
