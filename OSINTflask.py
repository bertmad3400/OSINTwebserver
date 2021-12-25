#!/usr/bin/python3

import markdown
import secrets

from flask import Flask, abort, render_template, request, redirect, flash, send_file, url_for, Response

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

esClient = OSINTelastic.elasticDB("osinter_articles")

import sqlite3
userTable = "osinter_users"
DBName = "./osinter_users.db"

from jinja_markdown import MarkdownExtension


app = Flask(__name__)
app.static_folder = "./static"
app.template_folder = "./templates"
app.REMEMBER_COOKIE_DURATION = timedelta(days=30)
app.REMEMBER_COOKIE_HTTPONLY = True

app.jinja_env.add_extension(MarkdownExtension)

login_manager = flask_login.LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

logging.basicConfig(level=logging.INFO)

@login_manager.user_loader
def load_user(userID):
    conn = sqlite3.connect(DBName)
    username = OSINTuser.getUsernameFromID(userID)
    if username:
        currentUser = OSINTuser.User(username)
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

def extractLimitParamater(request):
    try:
        limit = int(request.args.get('limit', 50))
    except:
        abort(422)
    if limit > 1000 or limit < 0:
        abort(422)
    else:
        return limit

def extractProfileParamaters(request):
    profiles = request.args.getlist('profiles')

    if profiles == []:
        # Get a list of scrambled OG tags
        return esClient.requestProfileListFromDB()
    # Making sure that the profiles given by the user both exist as local profiles and in the DB
    elif OSINTwebserver.verifyProfiles(profiles, esClient):
        # Just simply return the list of profiles
        return profiles
    else:
        abort(422)

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


    limit = extractLimitParamater(request)
    profiles = extractProfileParamaters(request)

    # Get a list of dicts containing the OGTags
    if showingSaved:
        articleList = esClient.requestArticlesFromDB(profiles, limit, markedArticleIDs["saved_article_ids"])
    else:
        articleList = esClient.requestArticlesFromDB(profiles, limit)

    for article in articleList:
        if flask_login.current_user.is_authenticated:
            article.saved = article.id in markedArticleIDs['saved_article_ids']
            article.read = article.id in markedArticleIDs['read_article_ids']

        if request.args.get('reading', False):
            article.url = url_for("renderMDFileById", articleId=article.id)

    return (render_template("feed.html", articleList=articleList, showingSaved=showingSaved, savedCount=len(markedArticleIDs['saved_article_ids'])))



@app.errorhandler(werkzeug.exceptions.HTTPException)
def handleHTTPErrors(e):
    return render_template("HTTPError.html", errorCode=e.code, errorName=e.name, errorDescription=e.description), e.code

@app.route('/')
def index():
    return showFrontPage(False)

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

        username = form.username.data
        password = form.password.data
        remember = form.remember_me.data

        currentUser = OSINTuser.User(username)

        if not currentUser.checkIfUserExists():
            flash("User doesn't seem to exist, sign-up using the link above.")
            return redirect(url_for('login'))
        elif currentUser.verifyPassword(password):
            app.logger.info(f'The user "{username}" succesfully logged in.')
            flask_login.login_user(currentUser, remember=remember)

            next = request.args.get('next', url_for("index"))

            # is_safe_url should check if the url is safe for redirects to avoid open redirects
            if "api" in next or not is_safe_url(next):
                return redirect(url_for("index"))

            return redirect(next)
        else:
            app.logger.info(f'The user "{username}" failed to logging.')
            flash('Please check your login credentials and try again, or signup using the link above.')
            return redirect(url_for('login'))

    return render_template("login.html", form=form)

@app.route('/signup', methods=["GET", "POST"])
def signup():
    form = OSINTforms.SignupForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        currentUser = OSINTuser.User(username)

        if currentUser.checkIfUserExists():
            flash('User already exists, log in here.')
            return redirect(url_for('login'))
        else:
            if OSINTuser.createUser(username, password):
                app.logger.info(f'Created user "{username}".')
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
    sourcesDetails = OSINTprofiles.collectWebsiteDetails(esClient)
    return render_template("chooseNewsSource.html", sourceDetailsDict={source: sourcesDetails[source] for source in sorted(sourcesDetails)})

@app.route('/renderMarkdownById/<string:articleId>/')
def renderMDFileById(articleId):
    article = esClient.requestArticlesFromDB(limit=1, idList=[articleId])[0]

    if article != []:
        return render_template("githubMD.html", article=article)
    else:
        abort(404)



@app.route('/api')
def listAPIEndpoints():
    APIEndpointList = []
    for rule in app.url_map.iter_rules():
        rule = str(rule)
        if rule.startswith('/api/'):
            APIEndpointList.append(rule)

    return Response(json.dumps(APIEndpointList), mimetype='application/json')

@app.route('/api/newArticles')
def api():
    limit = extractLimitParamater(request)

    profiles = extractProfileParamaters(request)

    articleDictsList = [ article.as_dict() for article in esClient.requestArticlesFromDB(profiles, limit) ]

    return Response(json.dumps(articleDictsList, default=str), mimetype='application/json')

@app.route('/api/profileList')
def apiProfileList():
    return Response(json.dumps(esClient.requestProfileListFromDB()), mimetype='application/json')

@app.route('/api/markArticles/ID/', methods=['POST'])
@flask_login.login_required
def markArticleByID():
    # This is not only used to translate the command type comming from the front end, to allow the front end to use more human understandable names (like save and read), but its also - in combination with the following try/except statement - used to validate the input WHICH GOES DIRECTLY TO THE SQL QUERY so be EXTREMLY careful if replacing it
    markCollumnNameTranslation = {"save" : "saved_article_ids", "read" : "read_article_ids"}

    try:
        add = bool(request.get_json()['add'])
        articleID = str(request.get_json()['articleID'])
        markType = str(request.get_json()['markType'])
        markCollumnName = markCollumnNameTranslation[markType]
    except:
        abort(422)

    app.logger.info(f"{flask_login.current_user.username} marked {articleID} using {markType} type and add set to {str(add)}")

    saveArticleResponse = flask_login.current_user.markArticle(markCollumnName, articleID, add)

    if saveArticleResponse == True:
        return "Article succesfully saved", 200
    else:
        return markArticleResponse, 404

@app.route('/api/downloadAllSaved')
@flask_login.login_required
def downloadAllSavedArticles():
    abort(404)
   # app.logger.info("Markdown files download initiated by {}".format(flask_login.current_user.username))
   # conn = openDBConn()
   # articlePaths = OSINTuser.getSavedArticlePaths(conn, flask_login.current_user.username, userTable, articleTable)
   # zipFileName = str(uuid.uuid4()) + ".zip"

   # with ZipFile(zipFileName, "w") as zipFile:
   #     for path in articlePaths:
   #         currentFile = "{}/{}.md".format(articlePath, path)
   #         if os.path.isfile(currentFile):
   #             zipFile.write(currentFile, "OSINTer-MD-Articles/{}".format(path))
   #         else:
   #             app.logger.warning("Markdown file {} requested by {} couldn't be found".format(path, flask_login.current_user.username))

   # return_data = io.BytesIO()
   # with open(zipFileName, 'rb') as fo:
   #     return_data.write(fo.read())
   # # after writing, cursor will be at last byte, so move it to start
   # return_data.seek(0)

   # os.remove(zipFileName)

   # return send_file(return_data, mimetype='application/zip', download_name='OSINTer-MD-articles-{}.zip'.format(date.today()))

loadSecretKey()

if __name__ == '__main__':
    app.run(debug=True)
