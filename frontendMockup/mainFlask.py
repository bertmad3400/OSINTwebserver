import requests, json

from flask import Flask, render_template, g

app = Flask(__name__)
app.template_folder = "./templates"
app.static_folder = "./static"

@app.before_request
def gatherArticleList():
    g.articleList = json.loads(requests.get("https://osinter.dk/api/newArticles/").text)

@app.route('/<string:template>')
def large(template):
    return render_template(f"{template}.html")

if __name__ == '__main__':
    app.run(debug=True)
