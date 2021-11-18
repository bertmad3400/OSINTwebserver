#!/usr/bin/python3

import markdown
import psycopg2
import secrets

articleTable = "articles"
userTable = "osinter_users"
articlePath = "/srv/OSINTbackend/articles"
credentialsPath = "/srv/OSINTbackend/credentials"

from flask import Flask, abort, render_template, request, redirect, flash, send_file, url_for

import flask_login

import logging

import werkzeug

import OSINTforms

import json

import re

import io
import os

import uuid

from urllib.parse import urlparse, urljoin

from datetime import timedelta, date

from zipfile import ZipFile

from pathlib import Path

from OSINTmodules import *

app = Flask(__name__)
app.static_folder = "./static"
app.template_folder = "./templates"
app.REMEMBER_COOKIE_DURATION = timedelta(days=30)
app.REMEMBER_COOKIE_HTTPONLY = True

login_manager = flask_login.LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

logging.basicConfig(filename='log.log', level=logging.INFO)

@login_manager.user_loader
def load_user(userID):
    if userID == 1:
        return OSINTuser.AdminUser(openDBConn(user="osinter_admin"), userTable)
    else:
        conn = openDBConn(user="auth")
        username = OSINTuser.getUsernameFromID(conn, userTable, userID)
        if username:
            currentUser = OSINTuser.User(conn, userTable, username)
            if currentUser.checkIfUserExists():
                return currentUser

    return None

def loadSecretKey():
    if os.path.isfile("./secret.key"):
        app.secret_key = Path("./secret.key").read_text()
    else:
        currentSecretKey = secrets.token_urlsafe(256)
        with os.fdopen(os.open(Path("./secret.key"), os.O_WRONLY | os.O_CREAT, 0o400), 'w') as file:
            file.write(currentSecretKey)
        app.secret_key = currentSecretKey


# If the user isn't reader, it's assumed that the user has a password specified in a file in the credentials directory
def openDBConn(user="reader"):
    app.logger.info("Connecting to DB as {}".format(user))
    password = Path("{}/{}.password".format(credentialsPath, user)).read_text()

    return psycopg2.connect("dbname=osinter user={} password={}".format(user, password))

def extractLimitParamater(request):
    try:
        limit = int(request.args.get('limit', 50))
    except:
        abort(422)
    if limit > 1000 or limit < 0:
        abort(422)
    else:
        return limit

def extractProfileParamaters(request, conn):
    profiles = request.args.getlist('profiles')

    if profiles == []:
        # Get a list of scrambled OG tags
        return OSINTdatabase.requestProfileListFromDB(conn, articleTable)
    # Making sure that the profiles given by the user both exist as local profiles and in the DB
    elif OSINTwebserver.verifyProfiles(profiles, conn, articleTable):
        # Just simply return the list of profiles
        return profiles
    else:
        abort(422)

def renderMDFile(MDFilePath):
    if Path('{}/{}.md'.format(articlePath, MDFilePath)).exists():
        with open('{}/{}.md'.format(articlePath, MDFilePath)) as MDFile:
            MDContents = markdown.markdown(MDFile.read())
            return render_template("githubMD.html", markdown=MDContents)
    else:
        abort(404)

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
           ref_url.netloc == test_url.netloc

def showFrontPage(showingSaved):

    if flask_login.current_user.is_authenticated:
        markedArticleIDs = flask_login.current_user.getMarkedArticles()
    else:
        markedArticleIDs = {"saved_article_ids" : {}, "read_article_ids" : []}

    # Opening connection to database for OG tag retrieval
    conn = openDBConn()

    limit = extractLimitParamater(request)
    profiles = extractProfileParamaters(request, conn)

    # Get a list of dicts containing the OGTags
    if showingSaved:
        OGTagCollection = OSINTdatabase.requestOGTagsFromDB(conn, articleTable, profiles, limit, markedArticleIDs["saved_article_ids"])
    else:
        OGTagCollection = OSINTdatabase.requestOGTagsFromDB(conn, articleTable, profiles, limit)

    for OGTagDict in OGTagCollection:
        if flask_login.current_user.is_authenticated:
            OGTagDict['saved'] = OGTagDict['id'] in markedArticleIDs['saved_article_ids']
            OGTagDict['read'] = OGTagDict['id'] in markedArticleIDs['read_article_ids']

        if request.args.get('reading', False):
            OGTagDict['url'] = url_for("renderMDFileById", articleId=OGTagDict['id'])

    return (render_template("feed.html", detailList=OGTagCollection, showingSaved=showingSaved, savedCount=len(markedArticleIDs['saved_article_ids'])))



@app.errorhandler(werkzeug.exceptions.HTTPException)
def handleHTTPErrors(e):
    return render_template("HTTPError.html", errorCode=e.code, errorName=e.name, errorDescription=e.description), e.code

@app.route('/')
def index():
    return showFrontPage(False)


@app.route('/admin', methods=["GET", "POST"])
def showAdminPanel():
    if flask_login.current_user.is_admin and flask_login.login_fresh:
        deleteForm = OSINTforms.AdminDelete()
        changeForm = OSINTforms.AdminChangePassword()

        if deleteForm.validate_on_submit():
            print(deleteForm.delete.data)
        elif changeForm.validate_on_submit():
            print(changeForm.newPassword.data)
        else:
            conn = openDBConn()
            users = OSINTuser.listUsers(conn, userTable)
            return render_template("adminPanel.html", users=users, deleteForm=deleteForm, changeForm=changeForm)

        return redirect(url_for("showAdminPanel"))
    else:
        flash("You unfortunatly does not seem to be logged in as admin. Please login as admin to continue")
        return redirect(url_for("login"))


@app.route('/savedArticles')
@flask_login.login_required
def showSavedArticles():
    if len(flask_login.current_user.getMarkedArticles()["saved_article_ids"]) < 1:
        return redirect(url_for("index"))
    else:
        return showFrontPage(True)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = OSINTforms.LoginForm()
    if form.validate_on_submit():
        conn = openDBConn(user="auth")

        username = form.username.data
        password = form.password.data
        remember = form.remember_me.data

        if username == "admin":
            adminPassword = Path("{}/{}.password".format(credentialsPath, "osinter_admin")).read_text()
            if password == adminPassword:
                currentUser = OSINTuser.AdminUser(psycopg2.connect("dbname=osinter user=osinter_admin password={}".format(password)), userTable)
                flask_login.login_user(currentUser, duration=timedelta(minutes=10))
                return redirect(url_for('showAdminPanel'))

        currentUser = OSINTuser.User(conn, userTable, username)

        if not currentUser.checkIfUserExists():
            flash('User doesn\'t seem to exist, sign-up using the link above.')
            return redirect(url_for('login'))
        elif currentUser.verifyPassword(password):
            app.logger.info("The user \"{}\" succesfully logged in.".format(username))
            flask_login.login_user(currentUser, remember=remember)

            next = request.args.get('next', url_for("index"))

            # is_safe_url should check if the url is safe for redirects to avoid open redirects
            if "api" in next:
                return redirect(url_for("index"))
            elif not is_safe_url(next):
                return flask.abort(400)

            return redirect(next)
        else:
            app.logger.info("The user \"{}\" failed to logging.".format(username))
            flash('Please check your login credentials and try again, or signup using the link above.')
            return redirect(url_for('login'))

    return render_template("login.html", form=form)

@app.route('/signup', methods=["GET", "POST"])
def signup():
    form = OSINTforms.SignupForm()
    if form.validate_on_submit():
        conn = openDBConn(user="auth")

        username = form.username.data
        password = form.password.data

        currentUser = OSINTuser.User(conn, userTable, username)

        if currentUser.checkIfUserExists():
            flash('User already exists, log in here.')
            return redirect(url_for('login'))
        else:
            conn = openDBConn(user="user_creator")
            if OSINTuser.createUser(conn, userTable, username, password):
                app.logger.info("Created user \"{}\".".format(username))
                flash('Created user, log in here.')
                return redirect(url_for('login'))
            else:
                abort(500)

    return render_template("signup.html", form=form)


@app.route('/logout')
@flask_login.login_required
def logout():
    flask_login.logout_user()
    return redirect(url_for('index'))

@app.route('/config')
def configureNewsSources():
    # Opening connection to database for a list of stored profiles
    conn = openDBConn()
    sourcesDetails = OSINTprofiles.collectWebsiteDetails(conn, articleTable)
    return render_template("chooseNewsSource.html", sourceDetailsDict={source: sourcesDetails[source] for source in sorted(sourcesDetails)})

@app.route('/renderMarkdownById/<int:articleId>/')
def renderMDFileById(articleId):
    if type(articleId) != int:
        abort(422)

    MDFilePath = OSINTdatabase.returnArticleFilePathById(openDBConn(), articleId, 'articles')
    if MDFilePath:
        return renderMDFile(MDFilePath)
    else:
        abort(404)


@app.route('/api')
def listAPIEndpoints():
    APIEndpointList = []
    for rule in app.url_map.iter_rules():
        rule = str(rule)
        if rule.startswith('/api/'):
            APIEndpointList.append(rule)

    return json.dumps(APIEndpointList)

@app.route('/api/newArticles')
def api():
    conn = openDBConn()

    limit = extractLimitParamater(request)

    profiles = extractProfileParamaters(request, conn)

    return json.dumps(OSINTdatabase.requestOGTagsFromDB(conn, articleTable, profiles, limit), default=str)

@app.route('/api/profileList')
def apiProfileList():
    conn = openDBConn()
    return json.dumps(OSINTdatabase.requestProfileListFromDB(conn, articleTable))

@app.route('/api/markArticles/ID/', methods=['POST'])
@flask_login.login_required
def markArticleByID():
    # This is not only used to translate the command type comming from the front end, to allow the front end to use more human understandable names (like save and read), but its also - in combination with the following try/except statement - used to validate the input WHICH GOES DIRECTLY TO THE SQL QUERY so be EXTREMLY careful if replacing it
    markCollumnNameTranslation = {"save" : "saved_article_ids", "read" : "read_article_ids"}

    try:
        add = bool(request.get_json()['add'])
        articleID = int(request.get_json()['articleID'])
        markType = str(request.get_json()['markType'])
        markCollumnName = markCollumnNameTranslation[markType]
    except:
        abort(422)

    app.logger.info("{} marked {} using {} type and add set to {}".format(flask_login.current_user.username, str(articleID), str(markType), markType))

    conn = openDBConn(user="article_marker")
    saveArticleResponse = OSINTdatabase.markArticle(conn, articleTable, userTable, flask_login.current_user.username, markCollumnName, articleID, add)

    if saveArticleResponse == True:
        return "Article succesfully saved", 200
    else:
        return markArticleResponse, 404

@app.route('/api/downloadAllSaved')
@flask_login.login_required
def downloadAllSavedArticles():
    app.logger.info("Markdown files download initiated by {}".format(flask_login.current_user.username))
    conn = openDBConn()
    articlePaths = OSINTuser.getSavedArticlePaths(conn, flask_login.current_user.username, userTable, articleTable)
    zipFileName = str(uuid.uuid4()) + ".zip"

    with ZipFile(zipFileName, "w") as zipFile:
        for path in articlePaths:
            currentFile = "{}/{}.md".format(articlePath, path)
            if os.path.isfile(currentFile):
                zipFile.write(currentFile, "OSINTer-MD-Articles/{}".format(path))
            else:
                app.logger.warning("Markdown file {} requested by {} couldn't be found".format(path, flask_login.current_user.username))

    return_data = io.BytesIO()
    with open(zipFileName, 'rb') as fo:
        return_data.write(fo.read())
    # after writing, cursor will be at last byte, so move it to start
    return_data.seek(0)

    os.remove(zipFileName)

    return send_file(return_data, mimetype='application/zip', download_name='OSINTer-MD-articles-{}.zip'.format(date.today()))

loadSecretKey()

if __name__ == '__main__':
    app.run(debug=True)
