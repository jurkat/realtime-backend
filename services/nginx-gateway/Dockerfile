FROM nginx:latest

# Erstelle Verzeichnis für SSL-Zertifikate
RUN mkdir -p /etc/nginx/ssl

# Erstelle selbstsignierte Zertifikate als Fallback (werden nur verwendet, wenn keine gemountet werden)
RUN apt-get update && apt-get install -y openssl && \
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/privkey.pem \
    -out /etc/nginx/ssl/fullchain.pem \
    -subj "/C=DE/ST=State/L=City/O=Organization/CN=localhost" && \
    chmod 600 /etc/nginx/ssl/privkey.pem && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Leeres Basic Auth-Passwort-File erstellen als Fallback
RUN touch /etc/nginx/.htpasswd

# Ports freigeben
EXPOSE 80 443

# Healthcheck
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f -k https://localhost/ || curl -f http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]