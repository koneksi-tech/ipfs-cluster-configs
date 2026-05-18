FROM nginx:alpine

COPY progress-report.html /usr/share/nginx/html/index.html

EXPOSE 80
