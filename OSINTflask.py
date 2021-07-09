#!/usr/bin/python3

import psycopg2
postgresqlPassword = ""

from flask import Flask
from flask import render_template
from flask import send_from_directory

from OSINTmodules import *
import getOGTagsInHTML

app = Flask(__name__)
app.static_folder = "./static"
app.template_folder = "./templates"


@app.route('/')
def selectUser():
    return (render_template("selectUser.html"))

@app.route('/feed')
def showFrontpage():
    HTML, CSS, JS = getOGTagsInHTML.main()
    return (render_template("feed.html", HTML=HTML, CSS=CSS, JS=JS))


@app.route('/api')
def api():
    conn = psycopg2.connect("dbname=osinter user=postgres password=" + postgresqlPassword)
    return OSINTdatabase.requestOGTagsFromDB(conn, 'articles')

if __name__ == '__main__':
    app.run(debug=True)
