FROM rockylinux/rockylinux:latest

RUN dnf upgrade --assumeyes && dnf install --assumeyes git zsh curl

ENV UMASK=0022
ENV ZELLIJ_AUTO_EXIT=1

