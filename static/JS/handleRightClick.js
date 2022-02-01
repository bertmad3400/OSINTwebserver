var articles = document.querySelectorAll("a[articleID]");

function getCollapseObject(articleObject) {
	var articleID = articleObject.getAttribute("articleID")
	collapsedText = document.getElementById(`${articleID}-summary`)
	return new bootstrap.Collapse(collapsedText, {"toggle" : false})
}

articles.forEach(function(article) {
	article.addEventListener('contextmenu', function(event){
		event.preventDefault();
		getCollapseObject(article).toggle()
		return false;

	}, false);


});
