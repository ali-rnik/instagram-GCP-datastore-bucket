import google.oauth2.id_token
import base64
from google.cloud import datastore
from google.cloud import storage
from google.auth.transport import requests
from flask import Flask, render_template, request, redirect, flash, make_response
import datetime


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
    # key = key
    "key",
    "profile_name",
    "followers",
    "following",
    "profile_photo",
]
post_att = [
    # key = author+created_date
    "key",
    "author",
    "post_photo",
    "created_date",
    "caption",
]

comment_att = [
    # key = author+created_date+post_key
    "key",
    "author",
    "created_date",
    "text",
    "post_key",
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
    content = base64.b64encode(content).decode("utf-8")
    bucket = storage_client.bucket(PROJECT_STORAGE_BUCKET)
    blob = bucket.blob(address)
    blob.upload_from_string(content)


def download_blob(address):
    bucket = storage_client.bucket(PROJECT_STORAGE_BUCKET)
    blob = bucket.blob(address)
    content = blob.download_as_string().decode("utf-8")
    return content


def add_user_if_not_added(key):
    address = "/profile_photos/" + key + ".jpg"

    result = retrieve_row("user", key)
    if result != None and result.get("key") != None:
        return result

    with open("default_photo.jpg", mode="rb") as file:
        content = file.read()

    upload_blob(address, content)
    create_row(
        "user",
        key,
        {
            "key": key,
            "profile_name": key,
            "following": {},
            "followers": {},
            "profile_photo": address,
        },
    )

    result = retrieve_row("user", key)
    if result != None and result.get("key") != None:
        return result
    else:
        return None


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


def get_one_post(userkey, created_date):
    query = datastore_client.query(kind="post")
    query.add_filter("author", "=", userkey)
    query.add_filter("created_date", "=", created_date)
    post = list(query.fetch())[0]

    comments = None
    query = list(datastore_client.query(kind="comment").fetch())
    if query != []:
        query = datastore_client.query(kind="comment")
        query.order = ["-created_date"]
        query.add_filter("post_key", "=", post["key"])
        comments = list(query.fetch())

    post["post_photo"] = download_blob(post["post_photo"])
    return (post, comments)


def get_user_posts(users, timeline=False):
    posts_and_comments = []
    query = datastore_client.query(kind="post")
    query.add_filter("author", "IN", users)
    query.order = ["-created_date"]
    posts = list(query.fetch())

    for post in posts:
        posts_and_comments.append(get_one_post(post["author"], post["created_date"]))

    if timeline:
        return posts_and_comments[:50]

    return posts_and_comments


@app.route("/action/<actiontype>/<userkey>/", methods=["GET"])
def action(actiontype, userkey):
    userinfo = get_session_info()
    if userinfo == None:
        return flash_redirect("You should first login to access this page", "/")

    my_key = datastore_client.key("user", userinfo["key"])
    my_user = datastore_client.get(my_key)

    other_key = datastore_client.key("user", userkey)
    other_user = datastore_client.get(other_key)

    now_time = datetime.datetime.now().timestamp()
    if actiontype == "follow":
        my_user["following"][userkey] = now_time
        other_user["followers"][userinfo["key"]] = now_time
    if actiontype == "unfollow":
        del my_user["following"][userkey]
        del other_user["followers"][userinfo["key"]]

    datastore_client.put(my_user)
    datastore_client.put(other_user)

    return flash_redirect(actiontype + "ed Sunccessfully", "/")


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

    user_list = []
    result = retrieve_row("user", userkey)
    list_of_follow = result[searchtype].copy()
    if list_of_follow != {}:
        query = datastore_client.query(kind="user")

        query.add_filter("key", "IN", list_of_follow.keys())
        user_list = list(query.fetch())

    return flash_redirect("TODO users_list", "/")

    # query = datastore_client.query(kind="user")
    # query.add_filter("profile_name", ">=", start_char[0])
    # query.add_filter("profile_name", "<", chr(ord(start_char[0]) + 1))
    # user_list = list(query.fetch())
    # user_list = replace_address_with_photo(user_list)
    # TODO
    # res = retrieve_row("user", userkey)
    # return render_template("index.html", userinfo=userinfo, )


@app.route("/userpage/<username>/", methods=["GET"])
def userpage(username):
    userinfo = get_session_info()
    if userinfo == None:
        return flash_redirect("You should first login to access this page", "/")

    ownpage = False
    if userinfo["key"] == username:
        ownpage = True

    posts_and_comments = get_user_posts([username])
    result = retrieve_row("user", username)
    return render_template(
        "index.html",
        ownpage=ownpage,
        userinfo=userinfo,
        userpage=result,
        posts_and_comments=posts_and_comments,
    )


@app.route("/addcomment/<user>/<post_key>/<created_time>/", methods=["POST"])
def addcomment(user, post_key, created_time):
    userinfo = get_session_info()
    if userinfo == None:
        return flash_redirect("You should first login to access this page", "/")

    text = request.form.get("addcomment")
    if text == None or len(text) <= 0 or len(text) > 200:
        return flash_redirect("Your comment does not follows the rules!", "/")

    key = user + post_key + created_time
    create_row(
        "comment",
        key,
        {
            "key": key,
            "created_date": created_time,
            "text": text,
            "author": user,
            "post_key": post_key,
        },
    )
    return flash_redirect("Comment added successfully.", "/")


@app.route("/addpost", methods=["GET", "POST"])
def addpost():
    userinfo = get_session_info()
    if userinfo == None:
        return flash_redirect("You should first login to access this page", "/addpost")

    if request.method == "GET":
        return render_template("index.html", userinfo=userinfo, addpost=True)

    imagepost = request.files.get("imagepost")
    caption = request.form.get("caption")

    if imagepost == None or caption == None or caption == "":
        return flash_redirect("Check All fields are correct and has value.", "/")

    imagepost = request.files["imagepost"].read()

    now_time = datetime.datetime.now().timestamp()
    bucketkey = "/posts/" + userinfo["key"] + str(now_time)
    upload_blob(bucketkey, imagepost)
    post_key = userinfo["key"] + str(now_time)
    create_row(
        "post",
        post_key,
        {
            "key": post_key,
            "author": userinfo["key"],
            "post_photo": bucketkey,
            "created_date": str(now_time),
            "caption": caption,
        },
    )

    return flash_redirect("Post Added successfully", "/")


@app.route("/error")
def error():
    return render_template("50x.html")


@app.route("/", methods=["GET"])
def root():
    userinfo = get_session_info()

    if type(userinfo) != type({}):
        return render_template("index.html", userinfo=userinfo)

    timeline_posts = None
    keys = list(userinfo["following"].keys())
    keys.append(userinfo["key"])
    timeline_posts = get_user_posts(keys, timeline=True)

    return render_template(
        "index.html",
        userinfo=userinfo,
        timeline_posts=timeline_posts,
        timestamp=datetime.datetime.now().timestamp(),
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
