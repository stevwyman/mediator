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