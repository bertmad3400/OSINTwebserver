import requests, json

apiURL = "https://osinter.dk/api/newArticles/"

for a in json.loads(requests.get(apiURL).text)[0:10]:
    print("<article>")
    print(f"    <img src='{a['image_url']}'>")
    print(f'    <div class="article-content">')
    print(f'        <div class="article-details">')
    print(f"            <p class='source'>{a['source']}</p>")
    print(f"            <time>yesterday</time>")
    print(f'        </div>')
    print(f"        <h3>{a['title']}</h3>")
    print(f"        <p class='description'>{a['description']}</p>")
    print(f'    </div>')
    print("</article>")
