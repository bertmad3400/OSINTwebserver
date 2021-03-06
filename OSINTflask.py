#!/usr/bin/python3

import markdown
import secrets

from flask import Flask, abort, render_template, request, redirect, flash, send_file, url_for, Response, g, make_response

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

import sqlite3

from jinja_markdown import MarkdownExtension

app = Flask(__name__)
app.config.from_object(OSINTconfig.frontendConfig())
app.static_folder = "./static"
app.template_folder = "./templates"
app.REMEMBER_COOKIE_DURATION = timedelta(days=30)
app.REMEMBER_COOKIE_HTTPONLY = True

OSINTwebserver.initiateUserDB(app.config["DB_FILE_PATH"], app.config["DB_USER_TABLE"])

app.esClient = OSINTelastic.elasticDB(app.config["ELASTICSEARCH_URL"], app.config["ELASTICSEARCH_CERT_PATH"], app.config["ELASTICSEARCH_ARTICLE_INDEX"])

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

def extractParamaters():
    paramaters = {}

    if request.args.get("limit"):
        try:
            limit = int(request.args.get('limit'))
            if limit > 1000 or limit < 0:
                abort(422)
            else:
                paramaters["limit"] = limit
        except:
            abort(422)

    profiles = request.args.getlist('profiles')

    if profiles and OSINTwebserver.verifyProfiles(profiles, app.esClient):
        paramaters["profiles"] = profiles
    elif profiles:
        abort(422)

    for dateType in ["firstDate", "lastDate"]:
        currentDate = request.args.get(dateType)

        if currentDate:
            try:
                paramaters[dateType] = date.fromisoformat(request.args.get(dateType))
            except:
                abort(422)

    searchQuery = request.args.get("searchTerm")

    if searchQuery:
        paramaters["searchTerm"] = searchQuery

    if request.args.get("saved") and flask_login.current_user.is_authenticated:
        paramaters["saved"] = "on"
        savedArticleIDs = flask_login.current_user.getMarkedArticles()["saved_article_ids"]
        if len(savedArticleIDs) >= 0:
            paramaters["IDs"] = savedArticleIDs

    if request.args.get('reading', False):
        paramaters["reading"] = "on"

    sortingDetails = [request.args.get("sortBy", None), request.args.get("sortOrder", None)]

    if sortingDetails[0] and sortingDetails[1]:
        if sortingDetails[0] in ["publish_date", "read_times", "source", "author", "url", "inserted_at"] and sortingDetails[1] in ["desc", "asc"]:
            paramaters["sortBy"] = sortingDetails[0]
            paramaters["sortOrder"] = sortingDetails[1]
        else:
            abort(422)

    return paramaters

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
           ref_url.netloc == test_url.netloc

def showFrontPage(articleList):

    if flask_login.current_user.is_authenticated:
        markedArticleIDs = flask_login.current_user.getMarkedArticles()
    else:
        markedArticleIDs = {"saved_article_ids" : {}, "read_article_ids" : []}

    if flask_login.current_user.is_authenticated:
        for article in articleList["articles"]:
            article.saved = article.id in markedArticleIDs['saved_article_ids']
            article.read = article.id in markedArticleIDs['read_article_ids']
    
    if "reading" in g.paramaters:
        for article in articleList["articles"]:
            article.url = url_for("renderMDFileById", articleId=article.id)

    sourcesDetails = OSINTprofiles.collectWebsiteDetails(app.esClient)

    flash(f"Returned {str(articleList['result_number'])} articles.")

    return (render_template("feed.html", articleList=articleList["articles"], savedCount=len(markedArticleIDs['saved_article_ids']), sourcesDetailsDict=sourcesDetails))

@app.before_request
def gatherQueryParamaters():
    g.paramaters = extractParamaters()

@app.errorhandler(werkzeug.exceptions.HTTPException)
def handleHTTPErrors(e):
    return render_template("HTTPError.html", errorCode=e.code, errorName=e.name, errorDescription=e.description), e.code

@app.route('/')
def index():
    articleList = app.esClient.searchArticles(g.paramaters)

    return showFrontPage(articleList)

@app.route('/rss')
def rssFeed():
    articleList = app.esClient.searchArticles(g.paramaters)["articles"]

    feed = OSINTwebserver.generateRSSFeed(articleList)

    response = make_response(feed.rss_str(pretty=True))
    response.headers.set('Content-Type', 'application/rss+xml')

    return response

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

@app.route('/search/')
def search():
    # Opening connection to database for a list of stored profiles
    sourcesDetails = OSINTprofiles.collectWebsiteDetails(app.esClient)
    return render_template("search.html", sourcesDetailsDict=sourcesDetails)


@app.route('/renderMarkdownById/<string:articleId>/')
def renderMDFileById(articleId):
    article = app.esClient.searchArticles({"limit" : 1, "IDs" : [articleId]})["articles"][0]

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
    articleDictsList = [ article.as_dict() for article in app.esClient.searchArticles(g.paramaters)["articles"] ]

    return Response(json.dumps(articleDictsList, default=str), mimetype='application/json')

@app.route('/api/getArticleByID/<string:articleId>/')
def getArticleObjectByID(articleId):
    article = app.esClient.searchArticles({"limit" : 1, "IDs" : [articleId]})["articles"][0]

    return Response(json.dumps(article.as_dict()), mimetype='application/json')


@app.route('/api/profileList/')
def apiProfileList():
    return Response(json.dumps(app.esClient.requestProfileListFromDB()), mimetype='application/json')

@app.route('/api/markArticles/ID/', methods=['POST'])
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

    if markCollumnName == "read_article_ids":
        app.esClient.incrementReadCounter(articleID)

    if flask_login.current_user.is_authenticated:
        app.logger.info(f"{flask_login.current_user.username} marked {articleID} using {markType} type and add set to {str(add)}")

        saveArticleResponse = flask_login.current_user.markArticle(markCollumnName, articleID, add)

        if saveArticleResponse == True:
            return "Article succesfully saved", 200
        else:
            return markArticleResponse, 404
    elif markCollumnName == "read_article_ids":
        return "Article marked as read", 200
    else:
        abort(401)

@app.route('/api/downloadMarkdownById/<string:articleId>/')
def downloadArticleByID(articleId):
    article = app.esClient.searchArticles({"limit" : 1, "IDs" : [articleId]})["articles"][0]

    if article != []:
        articleFile = OSINTfiles.convertArticleToMD(article)
        return send_file(articleFile.read().encode("utf-8"), mimetype='text/markdown', download_name=f'{article.title}.md')
    else:
        abort(404)

@app.route('/api/downloadAllSaved/')
@flask_login.login_required
def downloadAllSavedArticles():
    app.logger.info("Markdown files download initiated by {}".format(flask_login.current_user.username))
    articleIDs = flask_login.current_user.getMarkedArticles(tableNames=["saved_article_ids"])["saved_article_ids"]
    articles = app.esClient.searchArticles({"limit" : 10000, "IDs" : articleIDs})["articles"]
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
