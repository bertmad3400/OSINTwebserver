#!/usr/bin/python3

from flask import Flask
from flask import render_template
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


if __name__ == '__main__':
    app.run(debug=True)
