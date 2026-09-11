# syntax=docker/dockerfile:1.6

FROM registry.red-soft.ru/ubi8/ubi:8.0.2-260707 AS builder

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:/usr/local/rustup/bin:$PATH

RUN dnf -y update && dnf -y install \
      gcc gcc-c++ make \
      curl git \
      pkgconf-pkg-config \
      openssl-devel \
      protobuf-compiler \
      clang \
      ca-certificates \
    && dnf -y clean all

# rustup installer сам по себе требует интернет. В изолированном контуре
# лучше ставить rust toolchain из внутреннего зеркала ИЛИ иметь предсобранный builder image.
# поэтому данный образ собираем и кладем во внутренний репо
RUN curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal

# Создаем пользователя (выберите одну команду в зависимости от ОС builder)
# Для Debian/Ubuntu:
RUN useradd -r -u 10001 -g 0 appuser
# ИЛИ для Alpine:
# RUN adduser -D -u 10001 -G root appuser