# SearXNG with the JSON API switched on.
#
# The official image cannot be used unchanged: JSON output is disabled by
# default, and the backend needs it. This bakes the settings file in, so the
# service needs no volume or mounted config.

FROM searxng/searxng:latest

COPY settings.production.yml /etc/searxng/settings.yml

# The image's own entrypoint reads this path and substitutes SEARXNG_SECRET.
ENV SEARXNG_SETTINGS_PATH=/etc/searxng/settings.yml
