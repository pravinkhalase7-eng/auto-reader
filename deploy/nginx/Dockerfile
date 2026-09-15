# Bake config into the image so Jenkins-in-Docker does not need a host bind mount.
FROM nginx:1.27-alpine
COPY default.conf /etc/nginx/conf.d/default.conf
