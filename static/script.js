'use strict';
window.addEventListener('load', function () {
	document.getElementById('sign-out').onclick = function() {
		firebase.auth().signOut();
		window.location.replace('/');

	};

	var uiConfig = {
		signInSuccessUrl: '/',
		signInOptions: [
			firebase.auth.EmailAuthProvider.PROVIDER_ID
		]
	};
	firebase.auth().onAuthStateChanged(function(user) {
		if(user) {
			document.getElementById('sign-out').hidden = false;
			document.getElementById('popup-firebase').hidden = true;
			user.getIdToken().then(function(token) {
				document.cookie = "token=" + token + ";path=/";
			});
		} else {
			var ui = new firebaseui.auth.AuthUI(firebase.auth());
			ui.start('#firebase-auth-container', uiConfig);
			document.getElementById('sign-out').hidden = true;
			document.getElementById('popup-firebase').hidden = false;

			document.cookie = "token=;selected_date=;selected_cals=;path=/";
		}
	}, function(error) {
		console.log(error);
		alert('Unable to log in: ' + error);
	});
});

function makeVis() {
	document.getElementById("firebase-auth-container").hidden = false;
	document.getElementById("popup-firebase").hidden = true;
}

function makingVis(identi) {
	console.log("Making Vis")
	var inputs = document.getElementsByTagName("DIV");
	for(var i = 0; i < inputs.length; i++) {
		if(inputs[i].id.indexOf(identi) == 0) {
			inputs[i].hidden = false;
			console.log(inputs[i]+"became vis");
		}
		if(inputs[i].id == ("fire_"+identi)) {
			inputs[i].hidden = true;
			console.log(inputs[i].id+" became invis");
		}
	}
	return;
}

