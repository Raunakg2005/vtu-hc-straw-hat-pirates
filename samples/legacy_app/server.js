// Sample legacy Node service for the scanner demo
const crypto = require("crypto");
const { publicKey, privateKey } = crypto.generateKeyPairSync("ec", { namedCurve: "prime256v1" });
const ecdh = crypto.createECDH("prime256v1");
const token = jwt.sign(payload, key, { algorithm: "ES256" });
const digest = crypto.createHash("sha1").update(body).digest("hex");
