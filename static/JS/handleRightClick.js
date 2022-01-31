var articles = document.querySelectorAll("a[articleID]");

articles.forEach(function(article) {
	article.addEventListener('contextmenu', function(event){
		event.preventDefault();
		var articleID = article.getAttribute("articleID")
		collapsedText = document.getElementById(`${articleID}-summary`)
		new bootstrap.Collapse(collapsedText, {toggle: true})
		return false;

	}, false);


});
