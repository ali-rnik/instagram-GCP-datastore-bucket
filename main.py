import google.oauth2.id_token
import base64
from google.cloud import datastore
from google.cloud import storage
from google.auth.transport import requests
from flask import Flask, render_template, request, redirect, flash, make_response

PROJECT_NAME = "first-project-cpa"
PROJECT_STORAGE_BUCKET = "first-project-cpa.appspot.com"

app = Flask(__name__, static_url_path="/templates")

app.config["SECRET_KEY"] = "somesecretisagoodideatohaveprivacy"
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False

datastore_client = datastore.Client()
storage_client = storage.Client()

firebase_request_adapter = requests.Request()

user_att = [
    # key = email
    "email",
    "profile_name",
    "followers",
    "following",
    "profile_photo",
]
post_att = [
    # key = author+created_date
    "author",
    "post_photo",
    "created_date",
    "caption",
]

comment_att = [
    # key = author+created_date+post_id
    "author",
    "created_date",
    "text",
    "post_id",
]

att_list = {"user": user_att, "post": post_att, "comment": comment_att}


def flash_redirect(message, path):
    flash(message)
    return redirect(path)


def retrieve_row(kind, name):
    key = datastore_client.key(kind, name)
    result = datastore_client.get(key)
    if result == None:
        return None

    if result.get("profile_photo") != None:
        result["profile_photo"] = download_blob(result["profile_photo"])

    return result.copy()


def create_row(kind, name, data):
    key = datastore_client.key(kind, name)
    entity = datastore.Entity(key)
    entity.update(data)
    datastore_client.put(entity)


def upload_blob(address, content):
    bucket = storage_client.bucket(PROJECT_STORAGE_BUCKET)
    blob = bucket.blob(address)
    blob.upload_from_string(content)

def download_blob(address):
    bucket = storage_client.bucket(PROJECT_STORAGE_BUCKET)
    blob = bucket.blob(address)
    content = blob.download_as_string().decode("utf-8")
    return content


def add_user_if_not_added(email):
    address = "/profile_photos/" + email + ".jpg"

    result = retrieve_row("user", email)
    if result != None:
        return result

    with open("default_photo.jpg", mode="rb") as file:
        content = base64.b64encode(file.read()).decode("utf-8")
    
    upload_blob(address, content)
    create_row(
        "user",
        email,
        {
            "email": email,
            "profile_name": email,
            "following": {},
            "followers": {},
            "profile_photo": address,
        },
    )

    return content


def get_session_info():
    id_token = request.cookies.get("token")
    claims = None
    err_msg = None

    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter
            )
        except ValueError as exc:
            err_msg = str(exc)
            return flash_redirect(err_msg, "/error")
        userinfo = add_user_if_not_added(claims["email"].split("@")[0])
        return userinfo
    return None


@app.route("/error")
def error():
    return render_template("50x.html")


@app.route("/", methods=["GET", "POST"])
def root():
    userinfo = get_session_info()
    
    return render_template("index.html", userinfo=userinfo)
    


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
