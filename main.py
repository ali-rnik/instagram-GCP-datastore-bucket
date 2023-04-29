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


def replace_address_with_photo(data):
    for row in data:
        if row.get("profile_photo"):
            row["profile_photo"] = download_blob(row["profile_photo"])
        if row.get("post_photo"):
            row["post_photo"] = download_blob(row["post_photo"])
    return data


def retrieve_row(kind, name):
    key = datastore_client.key(kind, name)
    result = datastore_client.get(key)
    if result == None:
        return None

    if result.get("profile_photo"):
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

    result = retrieve_row("user", email)

    return result


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


def query_result(key, comp, val, kind):
    if key == "" or comp == "" or kind == "":
        return [None]
    query = datastore_client.query(kind=kind)
    query.add_filter(key, comp, val)
    fetched = query.fetch()
    if fetched == None or fetched == []:
        return [None]

    result = list(fetched)

    if result == []:
        return [None]
    result_list = []
    for item in result:
        result_list.append(item.copy())

    return result_list


@app.route("/search/<searchtype>/<userkey>/", methods=["POST", "GET"])
def users_list(searchtype, userkey):
    userinfo = get_session_info()
    if userinfo == None:
        return flash_redirect("You should first login to access this page", "/")

    if request.method == "POST":
        start_char = request.form["search_user"]
        if start_char == "" or start_char == None:
            return flash_redirect("No User found for this query", "/")

        if searchtype == "freetype":
            query = datastore_client.query(kind="user")
            query.add_filter("profile_name", ">=", start_char[0])
            query.add_filter("profile_name", "<", chr(ord(start_char[0]) + 1))
            user_list = list(query.fetch())
            user_list = replace_address_with_photo(user_list)
            if user_list == []:
                return flash_redirect("No User found for this query", "/")

            return render_template("index.html", userinfo=userinfo, user_list=user_list)

    return flash_redirect("TODO users_list", "/")
    # TODO
    # res = retrieve_row("user", userkey)
    # return render_template("index.html", userinfo=userinfo, )


@app.route("/userpage/<username>", methods=["GET"])
def userpage(username):
    userinfo = get_session_info()
    if userinfo == None:
        return flash_redirect("You should first login to access this page", "/")

    ownpage = False
    if userinfo["email"] == username:
        ownpage = True

    result = retrieve_row("user", username)
    return render_template(
        "index.html", ownpage=ownpage, userinfo=userinfo, userpage=result
    )


@app.route("/error")
def error():
    return render_template("50x.html")


@app.route("/", methods=["GET"])
def root():
    userinfo = get_session_info()
    print(userinfo)

    return render_template("index.html", userinfo=userinfo)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
