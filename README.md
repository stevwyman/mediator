# mediator
a tool to compare to negotiation prices


```sh
pip install -r requirements.txt


. ~/virtualenv/mediator/bin/activate

# build an image for the cloud container
docker buildx build --platform=linux/amd64 -t mediator .

# prepare for deployment
docker tag mediator stevwyman/mediator
docker push stevwyman/mediator

````

When TLS is terminated by a reverse proxy in front of Gunicorn, set `TRUSTED_PROXY_IPS` to that proxy's address (comma-separated if there is more than one). The proxy has to overwrite `X-Forwarded-Proto` and `X-Forwarded-Host` itself. Leave `TRUSTED_PROXY_IPS` empty when clients connect to Gunicorn directly, otherwise a client can point the share link at their own host. Without a trusted proxy, `SECURE_SSL_REDIRECT` will loop because Gunicorn only sees HTTP.