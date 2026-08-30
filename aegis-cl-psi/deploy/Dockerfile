FROM ubuntu:22.04
RUN apt-get update && apt-get install -y libssl-dev pkg-config ca-certificates && rm -rf /var/lib/apt/lists/*
COPY target/release/aegis_cl_psi /usr/local/bin/
COPY deploy/audit_schema.json /etc/aegis/
RUN mkdir -p /var/log/aegis
VOLUME /var/log/aegis
EXPOSE 8080
CMD ["aegis_cl_psi", "--json"]
