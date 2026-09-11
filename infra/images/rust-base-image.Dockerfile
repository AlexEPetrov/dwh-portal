FROM registry.red-soft.ru/ubi8/ubi-minimal:8.0.2-260707
RUN microdnf install -y ca-certificates \
 && microdnf clean all 