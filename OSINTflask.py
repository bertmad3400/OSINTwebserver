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
from OSINTconfig import Config

import sqlite3

from jinja_markdown import MarkdownExtension

app = Flask(__name__)
app.config.from_object(Config)
app.static_folder = "./static"
app.template_folder = "./templates"
app.REMEMBER_COOKIE_DURATION = timedelta(days=30)
app.REMEMBER_COOKIE_HTTPONLY = True

OSINTwebserver.initiateUserDB(app.config["DB_FILE_PATH"], app.config["DB_USER_TABLE"])

app.esClient = OSINTelastic.elasticDB(app.config["ELASTICSEARCH_URL"], app.config["ELASTICSEARCH_ARTICLE_INDEX"])

app.jinja_env.add_extension(MarkdownExtension)

login_manager = flask_login.LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

logging.basicConfig(level=logging.INFO)

@login_manager.user_loader
def load_user(userID):
    conn = sqlite3.connect(app.config["DB_FILE_PATH"])
    username = OSINTuser.getUsernameFromID(userID, app.config["DB_FILE_PATH"], app.config["DB_USER_TABLE"])
    if username:
        currentUser = OSINTuser.User(username, app.config["DB_FILE_PATH"], app.config["DB_USER_TABLE"])
        if currentUser.checkIfUserExists():
            return currentUser

    return None

def extractLimitParamater():
    try:
        limit = int(request.args.get('limit', 50))
    except:
        abort(422)
    if limit > 1000 or limit < 0:
        abort(422)
    else:
        return limit

def extractProfileParamaters():
    profiles = request.args.getlist('profiles')

    if profiles == []:
        # Get a list of scrambled OG tags
        return app.esClient.requestProfileListFromDB()
    # Making sure that the profiles given by the user both exist as local profiles and in the DB
    elif OSINTwebserver.verifyProfiles(profiles, app.esClient):
        # Just simply return the list of profiles
        return profiles
    else:
        abort(422)

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
           ref_url.netloc == test_url.netloc

def showFrontPage(showingSaved, articleList):

    if flask_login.current_user.is_authenticated:
        markedArticleIDs = flask_login.current_user.getMarkedArticles()
    else:
        markedArticleIDs = {"saved_article_ids" : {}, "read_article_ids" : []}

    if flask_login.current_user.is_authenticated:
        for article in articleList["articles"]:
            article.saved = article.id in markedArticleIDs['saved_article_ids']
            article.read = article.id in markedArticleIDs['read_article_ids']

    if request.args.get('reading', False):
        for article in articleList["articles"]:
            article.url = url_for("renderMDFileById", articleId=article.id)

    flash(f"Returned {str(articleList['result_number'])} articles.")

    return (render_template("feed.html", articleList=articleList["articles"], showingSaved=showingSaved, savedCount=len(markedArticleIDs['saved_article_ids'])))



@app.errorhandler(werkzeug.exceptions.HTTPException)
def handleHTTPErrors(e):
    return render_template("HTTPError.html", errorCode=e.code, errorName=e.name, errorDescription=e.description), e.code

@app.route('/')
def index():
    limit = extractLimitParamater()
    profiles = extractProfileParamaters()

    searchQuery = request.args.get("q")

    if searchQuery:
        articleList = app.esClient.searchArticles(searchQuery, limit=limit, profileList=profiles)
    else:
        articleList = app.esClient.requestArticlesFromDB(profiles, limit)

    return showFrontPage(False, articleList)

@app.route("/search/")
def searchInArticles():
    searchQuery = request.args.get("q")

    if searchQuery == "":
        return redirect(url_for("index"))

    limit = extractLimitParamater()
    profiles = extractProfileParamaters()

    articleList = app.esClient.searchArticles(searchQuery, limit=limit, profileList=profiles)

    return showFrontPage(False, articleList=articleList)


@app.route('/savedArticles/')
@flask_login.login_required
def showSavedArticles():
    savedArticleIDs = flask_login.current_user.getMarkedArticles()["saved_article_ids"]
    if len(savedArticleIDs) < 1:
        return redirect(url_for("index"))
    else:
        limit = extractLimitParamater()
        profiles = extractProfileParamaters()
        articleList = app.esClient.requestArticlesFromDB(profiles, limit, savedArticleIDs)
        return showFrontPage(True, articleList)


@app.route('/login/', methods=["GET", "POST"])
def login():
    form = OSINTforms.LoginForm()
    if form.validate_on_submit():

        username = form.username.data
        password = form.password.data
        remember = form.remember_me.data

        currentUser = OSINTuser.User(username, app.config["DB_FILE_PATH"], app.config["DB_USER_TABLE"])

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

@app.route('/signup/', methods=["GET", "POST"])
def signup():
    form = OSINTforms.SignupForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        currentUser = OSINTuser.User(username, app.config["DB_FILE_PATH"], app.config["DB_USER_TABLE"])

        if currentUser.checkIfUserExists():
            flash('User already exists, log in here.')
            return redirect(url_for('login'))
        else:
            if OSINTuser.createUser(username, password, app.config["DB_FILE_PATH"], app.config["DB_USER_TABLE"]):
                app.logger.info(f'Created user "{username}".')
                flash('Created user, log in here.')
                return redirect(url_for('login'))
            else:
                abort(500)

    return render_template("signup.html", form=form)


@app.route('/logout/')
@flask_login.login_required
def logout():
    flask_login.logout_user()
    return redirect(url_for('index'))

@app.route('/config/')
def configureNewsSources():
    # Opening connection to database for a list of stored profiles
    sourcesDetails = OSINTprofiles.collectWebsiteDetails(app.esClient)
    return render_template("config.html", sourceDetailsDict={source: sourcesDetails[source] for source in sorted(sourcesDetails)})


@app.route('/renderMarkdownById/<string:articleId>/')
def renderMDFileById(articleId):
    article = app.esClient.requestArticlesFromDB(limit=1, idList=[articleId])["articles"][0]

    if article != []:
        return render_template("githubMD.html", article=article)
    else:
        abort(404)



@app.route('/api/')
def listAPIEndpoints():
    APIEndpointList = []
    for rule in app.url_map.iter_rules():
        rule = str(rule)
        if rule.startswith('/api/'):
            APIEndpointList.append(rule)

    return Response(json.dumps(APIEndpointList), mimetype='application/json')

@app.route('/api/newArticles/')
def api():
    limit = extractLimitParamater()

    profiles = extractProfileParamaters()

    articleDictsList = [ article.as_dict() for article in app.esClient.requestArticlesFromDB(profiles, limit)["articles"] ]

    return Response(json.dumps(articleDictsList, default=str), mimetype='application/json')

@app.route('/api/profileList/')
def apiProfileList():
    return Response(json.dumps(app.esClient.requestProfileListFromDB()), mimetype='application/json')

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

@app.route('/api/downloadAllSaved/')
@flask_login.login_required
def downloadAllSavedArticles():
    app.logger.info("Markdown files download initiated by {}".format(flask_login.current_user.username))
    articleIDs = flask_login.current_user.getMarkedArticles(tableNames=["saved_article_ids"])["saved_article_ids"]
    articles = app.esClient.requestArticlesFromDB(limit=10000, idList = articleIDs)["articles"]
    zipFileName = str(uuid.uuid4()) + ".zip"

    with ZipFile(zipFileName, "w") as zipFile:
        for article in articles:
            filePath = f"{article.profile}/{article.id}.md"

            articleFile = OSINTfiles.convertArticleToMD(article)
            zipFile.writestr(f"OSINTer-MD-Articles/{filePath}", articleFile.getvalue())
            articleFile.close()

    return_data = io.BytesIO()
    with open(zipFileName, 'rb') as fo:
        return_data.write(fo.read())
    # after writing, cursor will be at last byte, so move it to start
    return_data.seek(0)

    os.remove(zipFileName)

    return send_file(return_data, mimetype='application/zip', download_name=f'OSINTer-MD-articles-{date.today()}.zip')

if __name__ == '__main__':
    app.run(debug=True)
