var resultContainer = document.getElementById('qr-reader-results');
var lastResult, countResults = 0;
function onScanSuccess(decodedText, decodedResult) {
    if (decodedText !== lastResult) {
        var audio = new Audio('/sebigus/static/src/audio/notification.mp3');
        audio.play();
        ++countResults;
        lastResult = decodedText;
        // Handle on success condition with the decoded message.
        console.log("Scan result ${decodedText}", decodedResult);
        var div = document.getElementById('qr-reader-results');
        div.innerHTML += decodedText;
        div.innerHTML += "<br>";
        console.log('Redirecciono');
        console.log(pedido_id);
        window.location.replace("cantidad/?pedido_id="+pedido_id+"&ean="+decodedText);
    }
}

var html5QrcodeScanner = new Html5QrcodeScanner(
    "qr-reader", { fps: 10, qrbox: 250 });
html5QrcodeScanner.render(onScanSuccess);