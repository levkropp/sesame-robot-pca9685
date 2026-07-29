const express = require("express");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.static(path.join(__dirname, "public")));

app.get("/healthz", (req, res) => res.status(200).send("ok"));

app.listen(PORT, () => {
  console.log(`Sesame PCA9685 fork site running at http://localhost:${PORT}`);
});
