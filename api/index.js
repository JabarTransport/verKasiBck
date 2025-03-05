const express = require("express");
const cors = require("cors");
const axios = require("axios");
require("dotenv").config();

const app = express();
app.use(express.json());
app.use(cors({
    origin: [process.env.FRONTEND_URL, process.env.FIREBASE_LOGIN_URL],
    credentials: true,
}));

const sessionStore = new Map();  // Sederhana pakai Map untuk simpan session

app.post("/api/check-keyword", (req, res) => {
    const { keyword } = req.body;
    if (keyword === process.env.SECRET_KEYWORD) {
        const sessionId = Date.now().toString();
        sessionStore.set(sessionId, { keywordValid: true });
        return res.json({ success: true, sessionId });
    }
    return res.status(401).json({ error: "Invalid keyword" });
});

app.get("/api/auth/github", (req, res) => {
    const sessionId = req.query.sessionId;
    const session = sessionStore.get(sessionId);

    if (!session || !session.keywordValid) {
        return res.status(401).json({ error: "Unauthorized" });
    }

    const params = new URLSearchParams({
        client_id: process.env.GITHUB_CLIENT_ID,
        redirect_uri: process.env.GITHUB_REDIRECT_URI,
        scope: "user:email"
    }).toString();

    res.redirect(`https://github.com/login/oauth/authorize?${params}`);
});

app.get("/api/auth/github/callback", async (req, res) => {
    const { code, sessionId } = req.query;

    if (!code || !sessionStore.get(sessionId)) {
        return res.redirect(process.env.FIREBASE_LOGIN_URL);
    }

    try {
        const tokenResponse = await axios.post("https://github.com/login/oauth/access_token", {
            client_id: process.env.GITHUB_CLIENT_ID,
            client_secret: process.env.GITHUB_CLIENT_SECRET,
            code,
            redirect_uri: process.env.GITHUB_REDIRECT_URI
        }, {
            headers: { Accept: "application/json" }
        });

        const accessToken = tokenResponse.data.access_token;

        const userResponse = await axios.get("https://api.github.com/user", {
            headers: { Authorization: `token ${accessToken}` }
        });

        sessionStore.set(sessionId, {
            ...sessionStore.get(sessionId),
            userData: userResponse.data
        });

        res.redirect(`${process.env.FRONTEND_URL}?sessionId=${sessionId}`);
    } catch (error) {
        console.error("GitHub Auth Error:", error.response?.data || error.message);
        res.redirect(process.env.FIREBASE_LOGIN_URL);
    }
});

app.get("/api/profile", (req, res) => {
    const sessionId = req.query.sessionId;
    const session = sessionStore.get(sessionId);

    if (!session) {
        return res.status(401).json({ error: "Unauthorized" });
    }

    if (session.userData) {
        return res.json({ type: "github", data: session.userData });
    }

    if (session.keywordValid) {
        return res.json({
            type: "keyword",
            data: {
                name: "Guest User",
                avatar_url: "https://via.placeholder.com/150",
                message: "Logged in with secret keyword"
            }
        });
    }

    res.status(401).json({ error: "Unauthorized" });
});

app.get("/api/logout", (req, res) => {
    const sessionId = req.query.sessionId;
    sessionStore.delete(sessionId);
    res.json({ success: true });
});

app.listen(5000, () => console.log("Server running on port 5000"));