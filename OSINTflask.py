#!/usr/bin/python3

import markdown
import psycopg2
import secrets

articleTable = "articles"
userTable = "osinter_users"

from flask import Flask, abort
from flask import render_template
from flask import request
from flask import redirect

import flask_login

import werkzeug

import json

import re

from datetime import timedelta

from pathlib import Path

from OSINTmodules import *

app = Flask(__name__)
app.static_folder = "./static"
app.template_folder = "./templates"
app.secret_key = secrets.token_urlsafe(256)
app.REMEMBER_COOKIE_DURATION = timedelta(seconds=30)
app.REMEMBER_COOKIE_HTTPONLY = True

login_manager = flask_login.LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(userID):
    conn = openDBConn(user="auth")
    username = OSINTuser.getUsernameFromID(conn, userTable, userID)
    if username:
        currentUser = OSINTuser.User(conn, userTable, username)
        if currentUser.checkIfUserExists():
            return currentUser

    return None

# If the user isn't reader, it's assumed that the user has a password specified in a file in the credentials directory
def openDBConn(user="reader"):
    password = ""
    if user != "reader":
        password = Path("./credentials/{}.password".format(user)).read_text()

    return psycopg2.connect("dbname=osinter user={} password={}".format(user, password))

def extractLimitParamater(request):
    try:
        limit = int(request.args.get('limit', 10))
    except:
        abort(422)
    if limit > 100 or limit < 0:
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
    if Path('./MDFiles/{}.md'.format(MDFilePath)).exists():
        with open('./MDFiles/{}.md'.format(MDFilePath)) as MDFile:
            MDContents = markdown.markdown(MDFile.read())
            return render_template("githubMD.html", markdown=MDContents)
    else:
        abort(404)

def createFeedURLList(idList, conn, tableName):
    URLList = []
    for articleId in idList:
        articleMDFile = OSINTdatabase.returnArticleFilePathById(conn, articleId, tableName)
        internURL = '/renderMarkdownByProfile/{}/'.format(articleMDFile)
        URLList.append(internURL)

    return URLList



@app.errorhandler(werkzeug.exceptions.HTTPException)
def handleHTTPErrors(e):
    return render_template("HTTPError.html", errorCode=e.code, errorName=e.name, errorDescription=e.description), e.code

@app.route('/')
def showFrontpage():
    # Opening connection to database for OG tag retrieval
    conn = openDBConn()

    limit = extractLimitParamater(request)
    profiles = extractProfileParamaters(request, conn)

    # Get a list of scrambled OG tags
    scrambledOGTags = OSINTtags.scrambleOGTags(OSINTdatabase.requestOGTagsFromDB(conn, articleTable, profiles, limit))

    # Will order the OG tags in a dict containing individual lists with IDs, URLs, imageURLs, titles and descriptions
    listCollection = OSINTwebserver.collectFeedDetails(scrambledOGTags)

    if flask_login.current_user.is_authenticated:
        listCollection['marked'] = OSINTdatabase.checkIfArticleMarked(conn, userTable, listCollection['id'], flask_login.current_user.username)
    else:
        listCollection['marked'] = []


    # Will change the URLs to intern URLs if the user has reading mode turned on
    if request.args.get('reading', False):
        listCollection['url'] = createFeedURLList(listCollection['id'], conn, articleTable)
    else:
        listCollection['url'] = listCollection['url']

    return (render_template("feed.html", detailList=listCollection))

@app.route('/login', methods=["GET", "POST"])
def chooseUser():
    if request.method == "GET":
        return render_template("login.html")
    else:
        conn = openDBConn(user="auth")

        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        currentUser = OSINTuser.User(conn, userTable, username)

        if currentUser.verifyPassword(password):
            flask_login.login_user(currentUser, remember=remember)
            return redirect('/')
        else:
            flash('Please check your login credentials and try again, or signup using the link above.')
            return redirect(url_for('login'))

@app.route('/logout')
@flask_login.login_required
def logout():
    flask_login.logout_user()
    return redirect('/')

@app.route('/config')
def configureNewsSources():
    # Opening connection to database for a list of stored profiles
    conn = openDBConn()
    sourcesDetails = OSINTprofiles.collectWebsiteDetails(conn, articleTable)
    return render_template("chooseNewsSource.html", sourceDetailsDict={source: sourcesDetails[source] for source in sorted(sourcesDetails)})

@app.route('/renderMarkdownByProfile/<profile>/<fileName>/')
def renderMDFileByProfile(profile, fileName):
    profileName = OSINTmisc.fileSafeString(profile)
    MDFileName = OSINTmisc.fileSafeString(fileName)
    return renderMDFile('{}/{}'.format(profileName, MDFileName))

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

    return OSINTdatabase.requestOGTagsFromDB(conn, articleTable, profiles, limit)

@app.route('/api/profileList')
def apiProfileList():
    conn = openDBConn()
    return json.dumps(OSINTdatabase.requestProfileListFromDB(conn, articleTable))

@app.route('/api/markArticles/ID/<int:articleID>/', methods=['POST'])
@flask_login.login_required
def markArticleByID(articleID):
    conn = openDBConn(user="article_marker")
    mark = request.get_json()['mark']
    markArticleResponse = OSINTdatabase.markArticle(conn, articleTable, userTable, flask_login.current_user.username, articleID, mark)
    if markArticleResponse == True:
        return "Article succesfully marked", 200
    else:
        return markArticleResponse, 404

if __name__ == '__main__':
    app.run(debug=True)
