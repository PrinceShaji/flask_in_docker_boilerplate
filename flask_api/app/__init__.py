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
