const scanList = [];

function clearForm() {
	document.getElementById("helpdesk_warranty_input_portal_lot_serial_number").value = "";
};

function beep(vol, freq, duration) {
	const audioContext = new AudioContext();
	const oscillator = audioContext.createOscillator();
	const gainNode = audioContext.createGain();

	oscillator.connect(gainNode);
	oscillator.frequency.value = freq;
	oscillator.type = "square";

	gainNode.connect(audioContext.destination);
	gainNode.gain.value = vol * 0.01;

	oscillator.start(audioContext.currentTime);
	oscillator.stop(audioContext.currentTime + duration * 0.001);
};

function onScanSuccess(decodedText, decodedResults) {
	if (!scanList.includes(decodedText)) {
		scanList.push(decodedText);
	}
	const inputData = document.getElementById("helpdesk_warranty_input_portal_lot_serial_number");
	if (!inputData.value.includes(decodedText)) {
		inputData.value += decodedText + ",";
	}
	beep(50, 1000, 200);
};

const formatsToSupport = [
	Html5QrcodeSupportedFormats.QR_CODE,
	Html5QrcodeSupportedFormats.AZTEC,
	Html5QrcodeSupportedFormats.CODABAR,
	Html5QrcodeSupportedFormats.CODE_39,
	Html5QrcodeSupportedFormats.CODE_93,
	Html5QrcodeSupportedFormats.CODE_128,
	Html5QrcodeSupportedFormats.EAN_13,
	Html5QrcodeSupportedFormats.EAN_8,
	Html5QrcodeSupportedFormats.UPC_A,
	Html5QrcodeSupportedFormats.UPC_E,
	Html5QrcodeSupportedFormats.UPC_EAN_EXTENSION,
];

let config = {
    fps: 10,
    facingMode: { exact: "environment" },
    qrbox: { width: 230, height: 100 },
    formatsToSupport: formatsToSupport,
    rememberLastUsedCamera: true,
    showTorchButtonIfSupported: false,
    supportedScanTypes: [Html5QrcodeScanType.SCAN_TYPE_CAMERA],
    aspectRatio: 2
};
let html5QrcodeScanner = new Html5QrcodeScanner(
	"qr-reader", config, /* verbose= */ false
);
html5QrcodeScanner.render(onScanSuccess);