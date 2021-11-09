var linksToTrack = document.querySelectorAll("a[articleID]");

linksToTrack.forEach(function(link) {
	link.addEventListener('click', function(event){
		var articleID = link.getAttribute("articleID")

		markArticle(articleID, "read", true)


	});


});
