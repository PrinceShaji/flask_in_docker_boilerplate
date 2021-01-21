# Production ready Flask API in Docker.
Flask is am amazing framework for creating APIs'. But Flask on it'sown i snot production ready although it comes with a built in web server. FOr making it production ready, it has to be put behind a web server which can communicate through WSGI (Web Server Gateway Interface) protocol. This tutorial is focused on creating a basic production ready API using Flask with uWSGI as the web server and RQ for the task queue for executing tasks in the baground. The project will be containarised in Docker. It will also touch in how to use Nginx docker image as a reverse proxy for the application and how everything can be bundled into a docker-compose file.

## Topics covered in this tutorial.
1. Setting up a Flask server uWSGI.
2. Setting up RQ (Redis Queue) to handle long-running tasks.
3. Containarise the project in Docker.
4. Using Nginx docker image as a reverse proxy.
5. Bundle the project in docker-compose.


## Requirements.
- Git
- Python 3+
- Pipenv
- Docker
- docker-compose

## Creating the Flask App
Let us start with creating the project folders and initiating git.

```shell
# Create the repository folder.
mkdir flask_in_docker_builderplate
cd flask_in_docker_builderplate

# Initiate a Git repository
git init

# Folder for the Flask Application
mkdir flask_api

# Folder for Nginx config files.
mkdir -p nginx/conf.d

```

Once the basic folder structure is created, let's go to the `flask_api` folder and install the dependencies for the Flask App.

```shell
# Go to flask_api folder.
cd flask_api

# Install project dependencies and save them to requirements.txt
pipenv install flask rq redis uwsgi
pipenv lock -r > requirements.txt

# Create a folder named `app` to store the Flask app.
mkdir app
```

> It is advisable to use black as the code formatter. If you choose to install it, use the following command.
```shell
pipenv install black --dev --pre
```

<br>
<br>

After the dependencies are installed, let's create the following files with it's contents in the specified directories.

`./flask_api/app/__init__.py`
```python
from flask import Flask, request, Response, jsonify
import redis
from rq import Queue
import json
from datetime import datetime
from .counter import counter

# Initiate the Flask App
app = Flask(__name__)


# Redis and RQ configuration
r = redis.Redis(host="redis", port=6379, db=0)
q = Queue("rq_worker", connection=r)


@app.route("/date/", methods=["GET"])
def current_date():
    current_date = datetime.now().strftime("%d-%m-%Y")
    data = {"date": current_date}
    return Response(response=json.dumps(data), status=200, mimetype="application/json")


@app.route("/background_count/", methods=["POST"])
def count_in_background():
    data = request.data()
    number = data["number"]

    job = q(counter, number)
    job_data = {"job_id": f"{job.id}"}

    return Response(
        response=json.dumps(job_data), status=200, mimetype="application/json"
    )

```
This is the main Flask application file. It cotains two routes. One accepts a GET request and returns the current date as a JSON response and the other one accepts a POST request which starts a long-running task and will send it to the task queue.

The `current_date` function creates a date string in the format `%d-%m-%Y` and returns it as a JSON response.

The `count_in_background` function is an interesting one. It uses Redis and Redis Queue to put that function into the background so that the Flask App is freed up to accept more requests. 

The redis server will be running in a separate container and is reachable using the hostname `redis` as opposed to `localhost` because Docker will create a separate network through with the Flask App and the Redis server cam communicate (will be explained in the docker-compse step).

To put a function in to the queue, ass in the function name, followed by the arguments in to the `Queue` object created at the beginning. The resulting Queue object will have the attribues of that task, and one of them is `id` which is sent in the response body back to the user.
<br>
<br>


`./flask_api/app/counter.py`

```python
from time import sleep


def counter(number):
    """ This function counts from 0 to %number and sleeps for a second in between """
    for i in range(number):
        sleep(1)
        print(f"The number is {i}")

```

The counter function takes longer to execute as the value of number increases. This emulates a long-running task which has to be sent to the task queue.

<br>

`./flask_api/run.py`
```python
from app import app

if __name__ == "__main__":
    app.run()

```
This is the entrypoint file for the Flask App.

<br>

`./flask_api/app.ini`
```ini
[uwsgi]
wsgi-file = run.py
callable = app
processes = 4
threads = 2
master = true
chmod-socket = 660
vacuum = true
die-on-term = true
http = 0.0.0.0:5000
```
These are the settings for uWSGI.

<br>

## Containarising the Flask App
For building the Docker image of the flask app, the base image used is `python:3`. The following `Dockerfile` will be used to build the image.

`./flask_api/Dockerfile`
```Dockerfile
FROM python:3

LABEL maintainer="github.com/PrinceShaji"

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

EXPOSE 5000

CMD ["uwsgi", "app.ini"]
```
Here, the `requirements.txt` file is copied in a separate step than copying all the files at once. It is so that we can utilize the build cache of Docker. Since the `requirements.txt` file won't change as frequently as the code does, Docker will use the cached images and fast forward the dependency installation step.
<br>
<br>

## Configuring Nginx docker image.
The Nginx docker [image](https://hub.docker.com/_/nginx) comes with everything required to run. We will be using `nginx:alpine` as it is lightweight. It comes with a default config file that servers a test page on port 80. We have to add a new config file for the project into that directory before running the container so that it can accept requests on port 80 and route it to the Fask App.

The file will be copied into `/var/nginx/conf.d` inside the Nginx container, and because of this, the config file must have a file extension of `.conf` . If it is any other file extension, Nginx won't load it. It is a good feature to have because it prevents Nginx from loading duplicate/temporary config files by accident and breaking the service.

`./nginx/conf.d/example.com.ssl.conf`
```conf
server {
    listen 80;
    listen 443;
    server_name example.com;
    # Store the certs in this dir
    ssl_certificate /etc/nginx/ssl/example.com/fullchain.crt;
    ssl_certificate_key /etc/nginx/ssl/example.com/server.key;
    ssl_protocols TLSv1 TLSv1.1 TLSv1.2;
    ssl_ciphers HIGH:!aNULL:!MD5;
    # redirect to non-www domain
    return   301 https://example.com$request_uri;
}

# HTTP to HTTPS redirection
server {
        listen 80;
        server_name your-site.com;
        return 301 https://example.com$request_uri;
}

server {
        listen 443 ssl;
        # Store the certs in this dir
        ssl_certificate /etc/nginx/ssl/example.com/fullchain.crt;
        ssl_certificate_key /etc/nginx/ssl/example.com/server.key;
        ssl_protocols TLSv1 TLSv1.1 TLSv1.2;
        ssl_ciphers HIGH:!aNULL:!MD5;
        # Maximum size of files user can upload with HTTP POST
        client_max_body_size 10M;
        server_name example.com;
        location / {
                add_header 'Access-Control-Allow-Origin' '*' always;
                add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS';
                add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization';
                add_header 'Access-Control-Expose-Headers' 'Content-Length,Content-Range';

                proxy_read_timeout 10;
                proxy_send_timeout 10;
                send_timeout 60;
                resolver_timeout 120;
                client_body_timeout 120;
                
                # set headers to pass request info to Flask
                proxy_set_header   Host $http_host;
                proxy_set_header   X-Forwarded-Proto $scheme;
                proxy_set_header   X-Forwarded-For $remote_addr;
                proxy_redirect     off;

                resolver 127.0.0.11 ipv6=off;  # Using docker emedded dns resolver.
    
                proxy_pass http://flask_api:5000$uri;
        }
}
```
Replace `example.com` with your domain name. The above config file requires SSL certificate to be in the specified path. Copy the SSL certificates to the specified path. This file is currently disabled. To enable it, rename `example.com.ssl.conf.disabled` to `example.com.conf` after deleting or disabling the existing `example.com.conf` file.

If you are using Let's Encrypt as the certificate provider, you can use the following config file (`example.com`) as a template. Use the following [tutorial](https://www.digitalocean.com/community/tutorials/how-to-secure-nginx-with-let-s-encrypt-on-ubuntu-18-04) to use Certbot to generate and manage SSL certificates.

`./nginx/conf.d/example.com.conf`
```conf
server {
    server_name example.com;

    location / {
        add_header 'Access-Control-Allow-Origin' '*' always;
            add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS';
            add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization';
            add_header 'Access-Control-Expose-Headers' 'Content-Length,Content-Range';

            proxy_read_timeout 10;
            proxy_send_timeout 10;
            send_timeout 60;
            resolver_timeout 120;
            client_body_timeout 120;
            
            # set headers to pass request info to Flask
            proxy_set_header   Host $http_host;
            proxy_set_header   X-Forwarded-Proto $scheme;
            proxy_set_header   X-Forwarded-For $remote_addr;
            proxy_redirect     off;

            resolver 127.0.0.11 ipv6=off;  # Using docker emedded dns resolver.

            proxy_pass http://flask_api:5000$uri;
    }
}
```
<br>
<br>

## Bundle the project in docker-compose.
Compose is a tool for defining and running multi-container Docker applications. With Compose, you use a YAML file to configure your application’s services. Then, with a single command, you create and start all the services from your configuration. From [compose docs](https://docs.docker.com/compose/).



`./docker-compose.yaml`
```yaml
version: "3"

services: 
    flask_api:
        build: ./flask_api
        restart: unless-stopped
        expose:
          - 5000
        depends_on: 
            - redis
            - rq_worker
        links: 
            - redis

    rq_worker:
        build: ./flask_api
        command: rq worker --url redis://redis:6379 rq_worker
        depends_on: 
            - redis
        links: 
            - redis
        restart: unless-stopped

    redis:
        image: redis:alpine
        expose:
            - 6379
        restart: unless-stopped
    nginx:
        build: ./nginx
        depends_on:
          - flask_api
        restart: unless-stopped
        links:
          - flask_api
        ports:
          - 80:80
          - 443:443
```
This file instructs Docker to start the services, creates a default networks and forwards ports to the local system from the container.

<br>

### Starting the services.
#### Development
To run the services in development, use `docker-compose up --build --force-recreate`
#### Production
To run the services in production, use `docker-compose up -d --build --force-recreate`

> `-d` flag runs the services in detached/background mode.

